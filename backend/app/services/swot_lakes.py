import csv
import io
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HYDROCRON_ENDPOINT = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"
HYDROCRON_COLLECTION = "SWOT_L2_HR_LakeSP_D"
HYDROCRON_FIELDS = (
    "lake_id,time_str,wse,wse_u,wse_std,area_total,area_detct,"
    "quality_f,ice_clim_f,ice_dyn_f,lake_name"
)
DOCUMENTATION_URL = "https://podaac.github.io/hydrocron/"
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "swot_lake_observations.json"
EARLIEST_DATA_YEAR = 2023
MAX_LAKE_DISTANCE_KM = 200
FILL_VALUES = {-999999999999.0}

SWOT_LAKES = {
    "large_aral": {
        "lake_name": "Large Aral Sea",
        "lake_id": "4610055052",
        "center": {"lat": 45.149449, "lon": 58.560971},
    },
    "lake_chad": {
        "lake_name": "Lake Chad",
        "lake_id": "1620031382",
        "center": {"lat": 13.251389, "lon": 15.173245},
    },
}


class SwotCacheUnavailableError(RuntimeError):
    pass


def _finite_number(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number in FILL_VALUES:
        return None
    return number


def parse_hydrocron_csv(content: str, expected_lake_id: str) -> list[dict]:
    rows = csv.DictReader(io.StringIO(content))
    required = {"lake_id", "time_str", "wse"}
    if not required.issubset(rows.fieldnames or set()):
        raise ValueError("Hydrocron CSV is missing required LakeSP fields")

    observations = []
    for row in rows:
        time_value = (row.get("time_str") or "").strip()
        if not time_value or time_value.lower() == "no_data":
            continue
        try:
            observation_time = datetime.fromisoformat(time_value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if str(row.get("lake_id", "")).strip() != expected_lake_id:
            continue
        wse = _finite_number(row.get("wse"))
        if wse is None:
            continue

        observations.append({
            "date": observation_time.isoformat().replace("+00:00", "Z"),
            "wse": wse,
            "wse_u": _finite_number(row.get("wse_u")),
            "wse_std": _finite_number(row.get("wse_std")),
            "area_total_km2": _finite_number(row.get("area_total")),
            "area_detected_km2": _finite_number(row.get("area_detct")),
            "quality_f": row.get("quality_f") or None,
            "ice_clim_f": row.get("ice_clim_f") or None,
            "ice_dyn_f": row.get("ice_dyn_f") or None,
        })

    observations.sort(key=lambda observation: observation["date"])
    return observations


def _haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    earth_radius_km = 6371.0088
    lat_delta = math.radians(lat_b - lat_a)
    lon_delta = math.radians(lon_b - lon_a)
    value = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(lon_delta / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(min(1.0, value)))


def _descriptive_sen_trend(observations: list[dict]) -> dict:
    dated_values = []
    for observation in observations:
        try:
            timestamp = datetime.fromisoformat(
                str(observation.get("date", "")).replace("Z", "+00:00")
            )
            value = float(observation.get("wse"))
        except (AttributeError, TypeError, ValueError):
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if math.isfinite(value):
            dated_values.append((timestamp.timestamp(), value))

    dated_values.sort()
    if len(dated_values) < 2:
        return {
            "sen_slope": None,
            "trend": "descriptive_insufficient_data",
            "trendline_start_value": None,
            "trendline_end_value": None,
        }

    seconds_per_year = 365.2425 * 24 * 60 * 60
    first_timestamp = dated_values[0][0]
    elapsed_years = [
        (timestamp - first_timestamp) / seconds_per_year
        for timestamp, _ in dated_values
    ]
    slopes = []
    for earlier_index, (earlier_year, (_, earlier_value)) in enumerate(
        zip(elapsed_years, dated_values)
    ):
        for later_year, (_, later_value) in zip(
            elapsed_years[earlier_index + 1:],
            dated_values[earlier_index + 1:],
        ):
            if later_year > earlier_year:
                slopes.append((later_value - earlier_value) / (later_year - earlier_year))
    if not slopes:
        return {
            "sen_slope": None,
            "trend": "descriptive_insufficient_data",
            "trendline_start_value": None,
            "trendline_end_value": None,
        }

    slope = statistics.median(slopes)
    intercept = statistics.median(
        value - slope * elapsed
        for elapsed, (_, value) in zip(elapsed_years, dated_values)
    )
    trend = (
        "descriptive_increasing" if slope > 0
        else "descriptive_decreasing" if slope < 0
        else "descriptive_no_change"
    )
    return {
        "sen_slope": round(slope, 6),
        "trend": trend,
        "trendline_start_value": round(intercept, 6),
        "trendline_end_value": round(intercept + slope * elapsed_years[-1], 6),
    }


def analyze_swot_lake(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    cache_path: Optional[Path] = None,
) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Latitude and longitude are outside valid ranges")
    if start_year < EARLIEST_DATA_YEAR:
        raise ValueError(f"SWOT observations begin in {EARLIEST_DATA_YEAR}")
    if end_year < start_year:
        raise ValueError("End year must be equal to or later than start year")

    lake_key, lake_definition, distance = min(
        (
            (
                key,
                definition,
                _haversine_km(
                    lat,
                    lon,
                    definition["center"]["lat"],
                    definition["center"]["lon"],
                ),
            )
            for key, definition in SWOT_LAKES.items()
        ),
        key=lambda item: item[2],
    )
    if distance > MAX_LAKE_DISTANCE_KM:
        raise ValueError(
            "Cached SWOT LakeSP observations are currently available only near the Large Aral Sea and Lake Chad"
        )

    selected_cache_path = cache_path or CACHE_PATH
    try:
        cache = json.loads(selected_cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SwotCacheUnavailableError(
            f"SWOT observation cache is missing: {selected_cache_path}. Refresh it with backend/scripts/refresh_swot_lake_cache.py."
        ) from error
    except (OSError, ValueError) as error:
        raise SwotCacheUnavailableError(
            f"SWOT observation cache could not be read: {error}"
        ) from error

    if not isinstance(cache, dict) or not isinstance(cache.get("lakes"), dict):
        raise SwotCacheUnavailableError("SWOT observation cache has an invalid structure")
    cached_lake = cache["lakes"].get(lake_key)
    if not isinstance(cached_lake, dict) or cached_lake.get("lake_id") != lake_definition["lake_id"]:
        raise SwotCacheUnavailableError(
            f"SWOT cache does not contain the verified {lake_definition['lake_name']} feature"
        )
    cached_observations = cached_lake.get("observations")
    if not isinstance(cached_observations, list):
        raise SwotCacheUnavailableError("SWOT cache does not contain a valid observation list")

    try:
        observations = [
            observation
            for observation in cached_observations
            if isinstance(observation, dict)
            and start_year <= datetime.fromisoformat(
                str(observation.get("date", "")).replace("Z", "+00:00")
            ).year <= end_year
        ]
    except (AttributeError, TypeError, ValueError) as error:
        raise SwotCacheUnavailableError(
            f"SWOT cache contains an invalid observation date: {error}"
        ) from error
    if not observations:
        raise ValueError(
            f"No cached SWOT observations are available for {lake_definition['lake_name']} in {start_year}–{end_year}"
        )
    descriptive_trend = _descriptive_sen_trend(observations)

    return {
        "status": "ok",
        "lake_name": lake_definition["lake_name"],
        "lake_id": lake_definition["lake_id"],
        "lake_center": lake_definition["center"],
        "distance_to_lake_km": round(distance, 1),
        "source": "NASA PO.DAAC Hydrocron · SWOT",
        "dataset_id": f"{HYDROCRON_COLLECTION} · PriorLake",
        "documentation_url": DOCUMENTATION_URL,
        "unit": "m (WGS84 ellipsoidal water-surface elevation)",
        "temporal_resolution": "Irregular SWOT satellite overpasses (nominal 21-day repeat)",
        "cache_updated_at": cache.get("updated_at"),
        "quality_note": "Quality and ice flags are retained as reported; this app does not apply an undocumented quality filter.",
        "observation_count": len(observations),
        "observed_start_date": observations[0]["date"],
        "observed_end_date": observations[-1]["date"],
        "raw_series": [
            {
                "date": observation["date"],
                "value": observation["wse"],
                "uncertainty": observation.get("wse_u"),
                "standard_deviation": observation.get("wse_std"),
                "area_total_km2": observation.get("area_total_km2"),
                "area_detected_km2": observation.get("area_detected_km2"),
                "quality_f": observation.get("quality_f"),
                "ice_clim_f": observation.get("ice_clim_f"),
                "ice_dyn_f": observation.get("ice_dyn_f"),
            }
            for observation in observations
        ],
        "stats": {
            **descriptive_trend,
            "z_score": None,
            "p_value": None,
            "significant": None,
            "test_status": "not_applicable",
            "test_method": None,
            "message": "Exploratory Sen slope uses the unfiltered irregular observations; no inferential trend test or significance claim is made.",
        },
    }
