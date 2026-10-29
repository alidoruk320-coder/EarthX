#!/usr/bin/env python3
"""Compare boundary-sampled and area-weighted regional analyses using live GEE.

Run from the repository root after configuring backend/.env:
    backend/.venv312/bin/python scripts/validate_region.py
"""

import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import analyze_region
from app.services.trend_engine import analyze_annual_series, analyze_point


def geocode_polygon(query):
    params = urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "polygon_geojson": 1,
        "polygon_threshold": 0.01,
    })
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "EarthVerse-RegionValidation/1.0 (NASA Space Apps validation)"},
    )
    with urlopen(request, timeout=30) as response:
        places = json.load(response)
    if not places or places[0].get("geojson", {}).get("type") not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError(f"Could not retrieve a polygon boundary for {query}")
    return places[0]["geojson"]


def polygon_rings(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def point_in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i, (xi, yi, *_) in enumerate(ring):
        xj, yj = ring[j][:2]
        if ((yi > lat) != (yj > lat)) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def inside_geometry(lon, lat, geometry):
    return any(
        point_in_ring(lon, lat, rings[0])
        and not any(point_in_ring(lon, lat, hole) for hole in rings[1:])
        for rings in polygon_rings(geometry)
    )


def boundary_sample_points(geometry, max_points=16):
    all_coords = [position for polygon in polygon_rings(geometry) for ring in polygon for position in ring]
    west = min(position[0] for position in all_coords)
    east = max(position[0] for position in all_coords)
    south = min(position[1] for position in all_coords)
    north = max(position[1] for position in all_coords)
    side = min(4, max(1, int(math.sqrt(max_points))))
    points = []
    for row in range(side):
        lat = south + (north - south) * (row + 0.5) / side
        for column in range(side):
            lon = west + (east - west) * (column + 0.5) / side
            if inside_geometry(lon, lat, geometry):
                points.append({"lat": lat, "lon": lon, "weight": math.cos(math.radians(lat))})
    return points[:max_points]


def sampled_analysis(geometry, variable, start_year, end_year):
    started = time.perf_counter()
    points = boundary_sample_points(geometry)
    if not points:
        raise RuntimeError("No 4×4 quick-mode sample point fell inside the polygon")
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(analyze_point, point["lat"], point["lon"], variable, start_year, end_year): point
            for point in points
        }
        for future in as_completed(futures):
            try:
                results.append((future.result(), futures[future]))
            except Exception as error:
                print(f"  quick sample failed: {error}", file=sys.stderr)
    by_year = {}
    for result, point in results:
        for observation in result.get("raw_series", []):
            year = int(observation["year"])
            weight = max(0.0, point["weight"])
            current = by_year.setdefault(year, [0.0, 0.0])
            current[0] += float(observation["value"]) * weight
            current[1] += weight
    series = [
        {"year": year, "value": total / weight}
        for year, (total, weight) in sorted(by_year.items()) if weight > 0
    ]
    trend = analyze_annual_series([(item["year"], item["value"]) for item in series])
    return {
        **trend,
        "method": "sampled_boundary_filtered",
        "raw_series": series,
        "sample_count": len(results),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def fmt(value):
    return "—" if value is None else f"{value:.6g}" if isinstance(value, (int, float)) else str(value)


def summarize(label, mode, result):
    if result.get("method") == "polygon_area_weighted_single_cell":
        pixel_count = f"{result.get('valid_pixel_count', 0)} px (center-cell)"
    elif result.get("method") == "polygon_area_weighted":
        counts = result.get("valid_pixel_count_range", {})
        pixel_count = f"{counts.get('min', 0)}–{counts.get('max', 0)} px/year"
    else:
        pixel_count = f"{result.get('sample_count', 0)} samples (pixel count n/a)"
    print(
        f"| {label} | {mode} | {len(result.get('raw_series', []))} | "
        f"{fmt(result.get('sen_slope'))} | {fmt(result.get('p_value'))} | "
        f"{pixel_count} | {result.get('elapsed_seconds', 0):.3f}s |"
    )
    values = ", ".join(f"{point['year']}:{point['value']:.5g}" for point in result.get("raw_series", []))
    print(f"|  | series |  |  |  |  | `{values or 'empty'}` |")
    if result.get("resolution_warning"):
        print(f"|  | warning |  |  |  |  | {result['resolution_warning']} |")
    if result.get("missing_year_warning"):
        print(f"|  | warning |  |  |  |  | {result['missing_year_warning']} |")


def main():
    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        raise SystemExit("Earth Engine initialization failed; check backend/.env credentials and project id.")

    istanbul = geocode_polygon("Istanbul, Türkiye")
    time.sleep(1.1)  # Respect Nominatim's public service usage policy.
    turkey = geocode_polygon("Türkiye")
    center_coords = [position for polygon in polygon_rings(istanbul) for ring in polygon for position in ring]
    center_lon = sum(point[0] for point in center_coords) / len(center_coords)
    center_lat = sum(point[1] for point in center_coords) / len(center_coords)
    tiny = {
        "type": "Polygon",
        "coordinates": [[
            [center_lon - 0.01, center_lat - 0.01],
            [center_lon + 0.01, center_lat - 0.01],
            [center_lon + 0.01, center_lat + 0.01],
            [center_lon - 0.01, center_lat + 0.01],
            [center_lon - 0.01, center_lat - 0.01],
        ]],
    }
    # Illustrative Bosphorus/Marmara coastal window; land fraction is not a named administrative boundary.
    coast = {
        "type": "Polygon",
        "coordinates": [[[29.00, 40.92], [29.20, 40.92], [29.20, 41.08], [29.00, 41.08], [29.00, 40.92]]],
    }
    scenarios = [
        ("Istanbul · NDVI", istanbul, "ndvi", 2001, 2023),
        ("Istanbul small · GRACE", tiny, "grace_tws", 2003, 2016),
        ("Bosphorus coast · NDVI", coast, "ndvi", 2001, 2023),
        ("Türkiye · MERRA-2 T2M", turkey, "merra2_t2m", 2000, 2023),
    ]

    print("| Scenario | Method | Annual obs | Sen slope | p-value | Pixel/sample count | Time |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for label, geometry, variable, start_year, end_year in scenarios:
        print(f"\n<!-- {label}: {start_year}–{end_year}; {region_config[variable]['unit']} -->")
        try:
            fast = sampled_analysis(geometry, variable, start_year, end_year)
            polygon = analyze_region(geometry, variable, start_year, end_year)
            summarize(label, "Fast sample", fast)
            summarize(label, polygon["method"], polygon)
        except Exception as error:
            print(f"| {label} | ERROR | — | — | — | — | {error} |")


if __name__ == "__main__":
    main()
