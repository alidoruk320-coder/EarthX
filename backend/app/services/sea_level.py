import csv
import io
import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import ee

from app.services.trend_engine import analyze_annual_series

logger = logging.getLogger(__name__)
NOAA_ERDDAP_URL = "https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDsshDaily.csvp"
NOAA_DATASET_ID = "noaacwBLENDEDsshDaily"
NOAA_START_YEAR = 2017
NOAA_DOCUMENTATION_URL = "https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsshDaily/index.html"
REQUEST_TIMEOUT_SECONDS = 45
NOAA_SERIES_TIMEOUT_SECONDS = 90
HYCOM_START_YEAR = 1992
HYCOM_LATEST_COMPLETE_YEAR = 2023


from typing import Optional


def _read_noaa_rows(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    deadline: Optional[float] = None,
) -> list[dict]:
    query = f"sla[({start_date}T00:00:00Z):({end_date}T00:00:00Z)][({lat:.6f})][({lon:.6f})]"
    request = Request(
        f"{NOAA_ERDDAP_URL}?{quote(query, safe='(),:TZ-.')}",
        headers={"Accept": "text/csv", "User-Agent": "EarthVerse/1.0"},
    )
    for attempt in range(3):
        try:
            remaining = deadline - time.monotonic() if deadline is not None else REQUEST_TIMEOUT_SECONDS
            if remaining <= 0:
                raise TimeoutError("NOAA altimetry request exceeded its 90-second analysis limit.")
            with urlopen(request, timeout=min(REQUEST_TIMEOUT_SECONDS, remaining)) as response:
                content = response.read().decode("utf-8")
            return list(csv.DictReader(io.StringIO(content)))
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            logger.warning(
                "NOAA CoastWatch request for %s to %s returned HTTP %s; retrying",
                start_date,
                end_date,
                error.code,
            )
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            logger.warning(
                "NOAA CoastWatch request for %s to %s failed; retrying",
                start_date,
                end_date,
                exc_info=True,
            )
        time.sleep(0.5 * (attempt + 1))


def _read_noaa_series_rows(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
) -> list[dict]:
    rows = []
    deadline = time.monotonic() + NOAA_SERIES_TIMEOUT_SECONDS
    for year in range(start_year, end_year + 1):
        chunks = (
            (date(year, 1, 1), date(year, 7, 1) - timedelta(days=1)),
            (date(year, 7, 1), date(year + 1, 1, 1) - timedelta(days=1)),
        )
        for chunk_start, chunk_end in chunks:
            rows.extend(
                _read_noaa_rows(
                    lat,
                    lon,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                    deadline,
                )
            )
    return rows


def _row_value(row: dict) -> Optional[float]:
    value = row.get("sla (m)", row.get("sla"))
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def check_sea_level_availability(lat: float, lon: float) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates")
    rows = _read_noaa_rows(lat, lon, "2025-01-01", "2025-01-01")
    for row in rows:
        value = _row_value(row)
        if value is None:
            continue
        return {
            "available": True,
            "status": "available",
            "latitude": row.get("latitude (degrees_north)", row.get("latitude")),
            "longitude": row.get("longitude (degrees_east)", row.get("longitude")),
            "dataset_id": NOAA_DATASET_ID,
        }
    return {"available": False, "status": "land_or_no_ocean_cell", "dataset_id": NOAA_DATASET_ID}


def _detect_step_change(series: list[tuple[int, float]]) -> Optional[int]:
    if len(series) < 7:
        return None
    annual_differences = [
        (next_value - value) / (next_year - year)
        for (year, value), (next_year, next_value) in zip(series, series[1:])
        if next_year > year
    ]
    if len(annual_differences) < 6:
        return None
    median_difference = sorted(annual_differences)[len(annual_differences) // 2]
    deviations = sorted(abs(value - median_difference) for value in annual_differences)
    mad = deviations[len(deviations) // 2]
    threshold = max(50.0, 5 * 1.4826 * mad)
    for index, difference in enumerate(annual_differences, start=1):
        if index < 3 or len(series) - index < 3:
            continue
        if abs(difference - median_difference) >= threshold:
            return series[index][0]
    return None


def _analyze_hycom_fallback(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    portal_error: str,
) -> dict:
    fallback_start_year = max(start_year, HYCOM_START_YEAR)
    fallback_end_year = min(end_year, HYCOM_LATEST_COMPLETE_YEAR)
    if fallback_start_year > fallback_end_year:
        raise RuntimeError(
            f"NOAA altimetry is unavailable ({portal_error}); HYCOM has no complete year in this interval."
        )

    point = ee.Geometry.Point([lon, lat])
    collection = (
        ee.ImageCollection("HYCOM/sea_surface_elevation")
        .filterBounds(point)
        .filterDate(f"{fallback_start_year}-01-01", f"{fallback_end_year + 1}-01-01")
        .select("surface_elevation")
    )

    def annual_feature(year):
        year = ee.Number(year)
        start = ee.Date.fromYMD(year, 1, 1)
        annual = collection.filterDate(start, start.advance(1, "year")).mean()
        value = annual.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=8906,
            maxPixels=100_000,
        ).get("surface_elevation")
        return ee.Feature(None, {"year": year, "value": value})

    try:
        features = ee.FeatureCollection(
            ee.List.sequence(fallback_start_year, fallback_end_year).map(annual_feature)
        ).getInfo()["features"]
    except Exception as error:
        raise RuntimeError(
            f"NOAA altimetry failed ({portal_error}); HYCOM fallback also failed: {error}"
        ) from error

    series = []
    for feature in features:
        props = feature.get("properties", {})
        try:
            year = int(props["year"])
            # The catalog scale is 0.001 m, so raw Earth Engine values are millimeters.
            value = float(props["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            series.append((year, value))
    if not series:
        raise RuntimeError(
            f"NOAA altimetry failed ({portal_error}); HYCOM contains no ocean cell at this coordinate."
        )

    trend = analyze_annual_series(
        series,
        expected_start_year=fallback_start_year,
        expected_end_year=fallback_end_year,
    )
    step_year = _detect_step_change(series)
    warning = (
        "Model output, not satellite altimetry. HYCOM model/version transitions can create abrupt steps; "
        "the trend is not reliable and statistical significance is not reported."
    )
    if step_year is not None:
        warning += f" A possible step change was detected at {step_year}."
    return {
        "region": {"lat": lat, "lon": lon},
        "variable": "Sea Surface Height Anomaly",
        "source": "HYCOM ocean model (NOPP) via Google Earth Engine · fallback",
        "dataset_id": "HYCOM/sea_surface_elevation · surface_elevation",
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/HYCOM_sea_surface_elevation",
        "unit": "mm sea-surface-height anomaly",
        "period": f"{series[0][0]}-{series[-1][0]}",
        "observation_count": len(series),
        "temporal_resolution": "Daily; annual mean",
        "model_output": True,
        "step_change_year": step_year,
        "fallback_warning": warning,
        **{
            **trend,
            "trend": "model_output_not_statistically_tested",
            "z_score": None,
            "p_value": None,
            "significant": None,
            "test_status": "not_applicable_model",
            "test_method": None,
            "message": warning,
        },
        "raw_series": [
            {"date": f"{year}-01-01", "year": year, "value": value}
            for year, value in series
        ],
    }


def analyze_sea_level(lat: float, lon: float, start_year: int, end_year: int) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates")
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    if start_year < NOAA_START_YEAR:
        if end_year > HYCOM_LATEST_COMPLETE_YEAR:
            raise ValueError(
                f"NOAA satellite-altimetry coverage begins in {NOAA_START_YEAR}; "
                f"the historical HYCOM model record ends in {HYCOM_LATEST_COMPLETE_YEAR}. "
                "Choose a period covered by one source."
            )
        return _analyze_hycom_fallback(
            lat,
            lon,
            max(start_year, HYCOM_START_YEAR),
            end_year,
            f"Requested historical period predates NOAA satellite-altimetry coverage in {NOAA_START_YEAR}.",
        )

    analysis_start_year = max(start_year, NOAA_START_YEAR)
    analysis_end_year = min(end_year, datetime.now(timezone.utc).year - 1)
    if analysis_start_year > analysis_end_year:
        raise ValueError(f"NOAA altimetry coverage begins in {NOAA_START_YEAR}.")

    try:
        rows = _read_noaa_series_rows(lat, lon, analysis_start_year, analysis_end_year)
    except Exception as error:
        logger.exception("NOAA CoastWatch altimetry request failed")
        return _analyze_hycom_fallback(
            lat, lon, analysis_start_year, analysis_end_year, f"{type(error).__name__}: {error}"
        )

    annual_values: dict[int, list[float]] = {}
    for row in rows:
        value = _row_value(row)
        timestamp = row.get("time (UTC)", row.get("time"))
        if value is None or not timestamp:
            continue
        try:
            year = datetime.strptime(timestamp[:10], "%Y-%m-%d").year
        except ValueError:
            continue
        if analysis_start_year <= year <= analysis_end_year:
            annual_values.setdefault(year, []).append(value)

    series = [
        (year, sum(values) / len(values))
        for year, values in sorted(annual_values.items())
        if values
    ]
    if not series:
        raise ValueError(
            "NOAA returned no valid ocean-altimetry cells at this coordinate; "
            "select a point over open water."
        )

    trend = analyze_annual_series(
        series,
        expected_start_year=analysis_start_year,
        expected_end_year=analysis_end_year,
    )
    return {
        "region": {"lat": lat, "lon": lon},
        "variable": "Sea Level Anomaly",
        "source": "NOAA CoastWatch blended satellite altimetry",
        "dataset_id": NOAA_DATASET_ID,
        "documentation_url": NOAA_DOCUMENTATION_URL,
        "unit": "m sea-surface-height anomaly",
        "period": f"{series[0][0]}-{series[-1][0]}",
        "observation_count": len(series),
        "temporal_resolution": "Daily; annual mean",
        "model_output": False,
        **trend,
        "raw_series": [
            {"date": f"{year}-01-01", "year": year, "value": round(value, 6)}
            for year, value in series
        ],
        "message": trend.get("message"),
        "measurement_note": (
            "Global 0.25-degree satellite-altimetry sea-surface-height anomaly; "
            "not relative shoreline sea level or a tide-gauge record."
        ),
    }
