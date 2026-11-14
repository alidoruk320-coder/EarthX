#!/usr/bin/env python3
"""Sequentially benchmark the frontend's 16-point quick-analysis path.

Each region/variable case runs in a child process with a hard five-minute
wall-clock limit. Earth Engine HTTP requests also receive a 300-second deadline.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import CURRENT_COMPLETE_YEAR, GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import ee, polygonal_geometry

REQUEST_TIMEOUT_MS = 300_000
CASE_TIMEOUT_SECONDS = 300
VARIABLES = {
    "ndvi": (2001, CURRENT_COMPLETE_YEAR),
    "soil_moisture": (2015, CURRENT_COMPLETE_YEAR),
    "grace_tws": (2003, 2016),
    "gpm_precipitation": (2001, 2024),
    "total_column_ozone": (1979, CURRENT_COMPLETE_YEAR),
    "merra2_t2m": (1980, CURRENT_COMPLETE_YEAR),
    "merra2_evaporation": (1980, CURRENT_COMPLETE_YEAR),
    "temperature": (2002, CURRENT_COMPLETE_YEAR),
    "precipitation": (2002, CURRENT_COMPLETE_YEAR),
    "sea_level": (2017, CURRENT_COMPLETE_YEAR),
}
REGIONS = ("istanbul", "turkey")
WORKER_FLAG = "--internal-worker"


def feature_collection_geometry(collection_id, filters):
    collection = ee.FeatureCollection(collection_id)
    for property_name, value in filters:
        collection = collection.filter(ee.Filter.eq(property_name, value))
    feature = collection.first().getInfo()
    if not feature or not feature.get("geometry"):
        raise RuntimeError(f"No boundary geometry in {collection_id}: {filters}")
    return polygonal_geometry(feature["geometry"])


def boundary(region):
    if region == "turkey":
        errors = []
        for name in ("Turkey", "Türkiye"):
            try:
                return feature_collection_geometry(
                    "FAO/GAUL/2015/level0", [("ADM0_NAME", name)]
                ), "FAO/GAUL/2015/level0"
            except Exception as error:
                errors.append(str(error))
        raise RuntimeError("Could not load Türkiye boundary: " + "; ".join(errors))

    candidates = (
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Turkey"),
        ("FAO/GAUL_SIMPLIFIED_500m/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Turkey"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Türkiye"),
    )
    errors = []
    for collection_id, country_field, region_field, country in candidates:
        try:
            return feature_collection_geometry(collection_id, [
                (country_field, country), (region_field, "Istanbul"),
            ]), collection_id
        except Exception as error:
            errors.append(f"{collection_id}/{country}: {error}")
    raise RuntimeError("Could not load Istanbul boundary: " + "; ".join(errors[-3:]))


def initialize_gee_with_deadline():
    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        return False
    ee.data.setDeadline(REQUEST_TIMEOUT_MS)
    return True


def iter_polygon_rings(geometry):
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    polygons = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
    for polygon in polygons:
        if polygon:
            yield polygon


def bounds_from_geometry(geometry):
    longitudes = []
    latitudes = []

    def visit(node):
        if isinstance(node, (list, tuple)) and len(node) >= 2 and all(
            isinstance(value, (int, float)) for value in node[:2]
        ):
            longitudes.append(float(node[0]))
            latitudes.append(float(node[1]))
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(geometry.get("coordinates", []))
    if not latitudes or not longitudes:
        raise ValueError("Polygon has no coordinate bounds")
    return min(latitudes), max(latitudes), min(longitudes), max(longitudes)


def point_in_ring(lat, lon, ring):
    inside = False
    j = len(ring) - 1
    for i, point in enumerate(ring):
        xi, yi = point[0], point[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < ((xj - xi) * (lat - yi)) / (yj - yi + sys.float_info.epsilon) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def frontend_sample_points(geometry, max_points=16, grid_size=24):
    """Match Earth.jsx's 24×24 in-polygon, cosine-weighted farthest-point sampler."""
    south, north, west, east = bounds_from_geometry(geometry)
    lat_values = [south + (north - south) * ((index + 0.5) / grid_size) for index in range(grid_size)]
    lon_values = [west + (east - west) * ((index + 0.5) / grid_size) for index in range(grid_size)]
    polygons = list(iter_polygon_rings(geometry))
    candidates = []
    for row, lat in enumerate(lat_values):
        for column, lon in enumerate(lon_values):
            inside = not polygons or any(
                point_in_ring(lat, lon, rings[0])
                and not any(point_in_ring(lat, lon, hole) for hole in rings[1:])
                for rings in polygons
            )
            if inside:
                candidates.append({
                    "lat": lat,
                    "lon": lon,
                    "weight": math.cos(math.radians(lat)),
                    "row": row,
                    "column": column,
                })

    if len(candidates) <= max_points:
        return [{key: point[key] for key in ("lat", "lon", "weight")} for point in candidates]
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2
    selected = [min(candidates, key=lambda point: (
        (point["lat"] - center_lat) ** 2
        + ((point["lon"] - center_lon) * math.cos(math.radians(center_lat))) ** 2
    ))]
    while len(selected) < max_points:
        remaining = [point for point in candidates if point not in selected]
        if not remaining:
            break
        next_point = max(remaining, key=lambda point: min(
            (point["lat"] - chosen["lat"]) ** 2
            + ((point["lon"] - chosen["lon"]) * math.cos(math.radians(chosen["lat"]))) ** 2
            for chosen in selected
        ))
        selected.append(next_point)
    return [{key: point[key] for key in ("lat", "lon", "weight")} for point in selected]


def _weighted_merged_series(point_results, points):
    by_year = {}
    for result, point in zip(point_results, points):
        weight = float(point["weight"])
        for observation in result.get("raw_series", []):
            year = int(observation.get("year") or str(observation.get("date", ""))[:4])
            value = float(observation["value"])
            if not math.isfinite(value):
                continue
            item = by_year.setdefault(year, {"weighted_sum": 0.0, "weight_sum": 0.0})
            item["weighted_sum"] += value * weight
            item["weight_sum"] += weight
    return [
        (year, item["weighted_sum"] / item["weight_sum"])
        for year, item in sorted(by_year.items())
        if item["weight_sum"] > 0
    ]


def run_worker(payload):
    from app.services.region_analysis import analyze_sampled_merra2_t2m, analyze_sampled_soil_moisture
    from app.services.trend_engine import analyze_annual_series, analyze_point
    from app.services.sea_level import analyze_sea_level

    variable = payload["variable"]
    if variable not in {"temperature", "precipitation", "sea_level"} and not initialize_gee_with_deadline():
        raise RuntimeError("Earth Engine initialization failed; configure backend/.env and credentials.")

    start_year, end_year = payload["start_year"], payload["end_year"]
    geometry, points = payload["geometry"], payload["sample_points"]
    if variable == "soil_moisture":
        result = analyze_sampled_soil_moisture(geometry, points, start_year, end_year)
        sample_count = result.get("sample_count", len(points))
        stats = result
    elif variable == "merra2_t2m":
        result = analyze_sampled_merra2_t2m(geometry, points, start_year, end_year)
        sample_count = result.get("sample_count", len(points))
        stats = result
    elif variable in {"temperature", "precipitation"}:
        parameter = "T2M" if variable == "temperature" else "PRECTOTCORR"
        point_results = []
        failures = []
        for point in points:
            query = urllib.parse.urlencode({
                "parameters": parameter,
                "community": "RE",
                "longitude": point["lon"],
                "latitude": point["lat"],
                "start": f"{start_year}0101",
                "end": f"{end_year}1231",
                "format": "JSON",
                "header": "true",
                "time-standard": "UTC",
            })
            try:
                with urllib.request.urlopen(
                    f"https://power.larc.nasa.gov/api/temporal/daily/point?{query}", timeout=60
                ) as response:
                    payload_json = json.loads(response.read())
                daily = payload_json.get("properties", {}).get("parameter", {}).get(parameter, {})
                by_year = {}
                for date, raw in daily.items():
                    value = float(raw)
                    if math.isfinite(value) and value > -999:
                        by_year.setdefault(int(date[:4]), []).append(value)
                point_results.append((point, {"raw_series": [
                    {"year": year, "value": sum(values) / len(values)}
                    for year, values in by_year.items()
                    if len(values) >= 0.9 * (366 if year % 4 == 0 else 365)
                ]}))
            except Exception as error:
                failures.append(str(error))
        series = _weighted_merged_series(
            [item for _, item in point_results], [point for point, _ in point_results]
        )
        stats = analyze_annual_series(series, expected_start_year=start_year, expected_end_year=end_year)
        sample_count = len(point_results)
        result = {**stats, "raw_series": [{"year": year, "value": value} for year, value in series],
                  "failed_point_count": len(failures), "error": "; ".join(failures[:2]) or None}
    elif variable == "sea_level":
        point_results = []
        failures = []
        for point in points:
            try:
                point_results.append((point, analyze_sea_level(point["lat"], point["lon"], start_year, end_year)))
            except Exception as error:
                failures.append(str(error))
        usable = [(point, item) for point, item in point_results if not item.get("model_output")]
        series = _weighted_merged_series(
            [item for _, item in usable], [point for point, _ in usable]
        )
        stats = analyze_annual_series(series, expected_start_year=start_year, expected_end_year=end_year)
        sample_count = len(usable)
        result = {**stats, "raw_series": [{"year": year, "value": value} for year, value in series],
                  "failed_point_count": len(failures), "error": "; ".join(failures[:2]) or None}
    else:
        memory_sensitive = variable in {
            "merra2_evaporation",
        }
        retry_counts = [count for count in (min(len(points), 16), 8, 4) if 0 < count <= len(points)] if memory_sensitive else [len(points)]
        point_results = []
        failures = []
        for point_count in retry_counts:
            point_results = []
            failures = []
            for point in points[:point_count]:
                try:
                    point_results.append((point, analyze_point(
                        point["lat"], point["lon"], variable, start_year, end_year
                    )))
                except Exception as error:
                    failures.append(str(error))
            if not memory_sensitive or not any("memory limit exceeded" in item.lower() for item in failures):
                break
        series = _weighted_merged_series(
            [item for _, item in point_results], [point for point, _ in point_results]
        )
        stats = analyze_annual_series(
            series,
            expected_start_year=start_year,
            expected_end_year=end_year,
        )
        sample_count = len(point_results)
        result = {**stats, "raw_series": [
            {"year": year, "value": value} for year, value in series
        ], "failed_point_count": len(failures), "error": "; ".join(failures[:2]) or None}
    return {
        "status": "ERROR" if not result.get("raw_series") else "PARTIAL" if result.get("failed_point_count") else result.get("status", "OK"),
        "sample_count": sample_count,
        "observation_count": len(result.get("raw_series", [])),
        "sen_slope": stats.get("sen_slope"),
        "p_value": stats.get("p_value"),
        "test_status": stats.get("test_status"),
        "failed_point_count": result.get("failed_point_count", 0),
        "error": result.get("error"),
    }


def run_case(region, variable, geometry, boundary_source):
    start_year, end_year = VARIABLES[variable]
    points = frontend_sample_points(geometry)
    if not points:
        return {"status": "NO_SAMPLE_POINTS", "seconds": 0, "sample_count": 0, "sen_slope": None}
    payload = {
        "region": region,
        "variable": variable,
        "start_year": start_year,
        "end_year": end_year,
        "geometry": geometry,
        "sample_points": points,
        "boundary_source": boundary_source,
    }
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as stream:
        json.dump(payload, stream)
        input_path = stream.name
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), WORKER_FLAG, input_path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=CASE_TIMEOUT_SECONDS,
        )
        elapsed = time.perf_counter() - started
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"worker exited {completed.returncode}"
            status = "TIMEOUT" if "timed out" in detail.lower() or "deadline" in detail.lower() else "ERROR"
            return {"status": status, "seconds": elapsed, "sample_count": len(points), "error": detail[-1200:]}
        marker = next((line[len("RESULT_JSON="):] for line in completed.stdout.splitlines() if line.startswith("RESULT_JSON=")), None)
        if marker is None:
            return {"status": "ERROR", "seconds": elapsed, "sample_count": len(points), "error": "Worker returned no result record"}
        result = json.loads(marker)
        return {**result, "seconds": elapsed, "status": result.get("status", "OK")}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "seconds": float(CASE_TIMEOUT_SECONDS), "sample_count": len(points), "sen_slope": None}
    finally:
        try:
            os.unlink(input_path)
        except OSError:
            pass


def worker_main(input_path):
    with open(input_path, encoding="utf-8") as stream:
        payload = json.load(stream)
    result = run_worker(payload)
    print("RESULT_JSON=" + json.dumps(result, allow_nan=False))


def main():
    global CASE_TIMEOUT_SECONDS
    if len(sys.argv) == 3 and sys.argv[1] == WORKER_FLAG:
        try:
            worker_main(sys.argv[2])
        except Exception as error:
            print(f"Worker error: {type(error).__name__}: {error}", file=sys.stderr)
            raise SystemExit(1)
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=CASE_TIMEOUT_SECONDS)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= CASE_TIMEOUT_SECONDS:
        parser.error("--timeout-seconds must be between 1 and 300")
    CASE_TIMEOUT_SECONDS = args.timeout_seconds

    if not initialize_gee_with_deadline():
        raise SystemExit("Earth Engine initialization failed; configure backend/.env and credentials.")
    geometries = {}
    for region in REGIONS:
        try:
            geometries[region] = boundary(region)
        except Exception as error:
            geometries[region] = (None, f"BOUNDARY ERROR: {error}")

    print("| Region | Variable | Period | Status | Seconds | Points used | Annual observations | Sen slope | p-value | Boundary source / note |")
    print("|---|---|---|---|---:|---:|---:|---:|---:|---|")
    for region in REGIONS:
        geometry, boundary_source = geometries[region]
        for variable, (start_year, end_year) in VARIABLES.items():
            if variable in {"temperature", "precipitation", "sea_level"} and geometry is None:
                result = {"status": "ERROR", "seconds": None, "sample_count": 0, "error": boundary_source}
            elif variable not in {"temperature", "precipitation", "sea_level"} and geometry is None:
                result = {"status": "ERROR", "seconds": None, "sample_count": 0, "error": boundary_source}
            else:
                print(
                    f"Starting {region}/{variable} ({start_year}-{end_year}), "
                    f"up to {CASE_TIMEOUT_SECONDS}s...",
                    flush=True,
                )
                result = run_case(region, variable, geometry, boundary_source)
            seconds = "—" if result.get("seconds") is None else f"{result['seconds']:.2f}"
            slope = "—" if result.get("sen_slope") is None else f"{result['sen_slope']:.8g}"
            p_value = "—" if result.get("p_value") is None else f"{result['p_value']:.6g}"
            note = result.get("error") or boundary_source
            print(
                f"| {region} | {variable} | {start_year}–{end_year} | {result['status']} | {seconds} | "
                f"{result.get('sample_count', 0)} | {result.get('observation_count', '—')} | {slope} | {p_value} | {str(note).replace('|', '/')} |",
                flush=True,
            )


if __name__ == "__main__":
    main()
