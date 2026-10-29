import json
import logging
import math
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.trend_engine import analyze_annual_series

logger = logging.getLogger(__name__)
NASA_SLCP_URL = "https://sealevel-nexus.jpl.nasa.gov/timeSeriesSpark"
NASA_SLCP_DATASET = "Sea_Surface_Anomalies"
REQUEST_TIMEOUT_SECONDS = 45


def analyze_sea_level(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates")
    # The portal interpolates its analysis datasets to 1-degree cells. Query a
    # one-degree window around the point so the containing grid cell is included.
    # This is an ocean grid product,
    # not a shoreline tide-gauge measurement or a measurement on land.
    half_width = 0.5
    bounds = [lon - half_width, lat - half_width, lon + half_width, lat + half_width]
    start = f"{start_year}-01-01T00:00:00Z"
    end = f"{end_year + 1}-01-01T00:00:00Z"
    query = urlencode({
        "ds": NASA_SLCP_DATASET,
        "b": ",".join(f"{value:.4f}" for value in bounds),
        "startTime": start,
        "endTime": end,
        "seasonalFilter": "False",
        "lowPassFilter": "False",
        "output": "JSON",
    })
    request = Request(NASA_SLCP_URL + "?" + query, headers={"Accept": "application/json", "User-Agent": "EarthVerse/1.0"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except Exception as error:
        logger.exception("NASA SLCP request failed")
        raise RuntimeError("NASA sea-level service could not be reached") from error

    data = payload.get("data") or payload.get("result") or []
    if isinstance(data, dict):
        data = data.get("data") or data.get("values") or []
    if not isinstance(data, list) or not data:
        raise ValueError("No ocean sea-level grid data is available at this coordinate; check that the location is over the ocean")

    annual = {}
    for point in data:
        try:
            timestamp = float(point.get("time"))
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            year = datetime.fromtimestamp(timestamp, tz=timezone.utc).year
            value = float(point.get("mean"))
            count = int(point.get("cnt", 1))
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(value) or count <= 0 or not (start_year <= year <= end_year):
            continue
        annual.setdefault(year, []).append((value, count))

    # The service returns centimeters; expose millimeters as the user-facing unit.
    series = [
        (year, sum(value * count for value, count in observations) / sum(count for _, count in observations) * 10)
        for year, observations in sorted(annual.items())
    ]
    if not series:
        raise ValueError("NASA returned no valid ocean sea-level observations for this interval")
    trend = analyze_annual_series(series)
    return {
        "region": {"lat": lat, "lon": lon, "grid_bounds": bounds},
        "variable": "Sea Level Anomaly",
        "source": "NASA/JPL Sea Level Change Portal",
        "dataset_id": NASA_SLCP_DATASET,
        "unit": "mm sea-level anomaly",
        "period": f"{series[0][0]}-{series[-1][0]}",
        "observation_count": len(series),
        **trend,
        "raw_series": [{"date": f"{year}-01-01", "year": year, "value": round(value, 3)} for year, value in series],
        "message": trend.get("message"),
        "measurement_note": "Approximately 1° gridded ocean sea-surface height anomaly; not relative shoreline sea level or a tide-gauge record.",
    }
