#!/usr/bin/env python3
"""Sequential Earth Engine timing probes for monthly temporal and geometry scaling."""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import ee, polygonal_geometry

LIMIT_MS = 300_000
VARIABLES = ("soil_moisture", "merra2_t2m", "merra2_evaporation")


def initialize():
    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        raise RuntimeError("Earth Engine initialization failed; check backend/.env and credentials.")
    ee.data.setDeadline(LIMIT_MS)


def load_istanbul():
    candidates = [
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Turkey"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Turkey"),
    ]
    for collection_id, country_field, region_field, country in candidates:
        try:
            fc = ee.FeatureCollection(collection_id).filter(ee.Filter.eq(country_field, country)).filter(
                ee.Filter.eq(region_field, "Istanbul")
            )
            geometry = fc.first().geometry()
            return polygonal_geometry(geometry.getInfo()), collection_id
        except Exception:
            continue
    raise RuntimeError("Could not load Istanbul administrative polygon from GAUL candidates.")


def select_timestamps(timestamps, targets):
    if not timestamps:
        raise ValueError("Empty collection in requested date interval")
    days = {}
    from datetime import datetime, timezone
    for value in timestamps:
        stamp = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        days.setdefault(stamp.date(), []).append((stamp, int(value)))
    selected = []
    for values in days.values():
        remaining = list(values)
        for target in targets:
            if not remaining:
                break
            def distance(item):
                hour = item[0].hour + item[0].minute / 60
                delta = abs(hour - target)
                return min(delta, 24 - delta)
            picked = min(remaining, key=distance)
            selected.append(picked[1])
            remaining.remove(picked)
    return selected


def build_composite(variable, geometry, start, months, base_year):
    cfg = region_config[variable]
    collection = ee.ImageCollection(cfg["collection"]).filterBounds(geometry).select(cfg["band"])
    end = start.advance(months, "month")
    selected_by_month = {}
    if not variable.startswith("merra2_"):
        timestamps = collection.filterDate(start, end).aggregate_array("system:time_start").getInfo() or []
        from datetime import datetime, timezone
        month_timestamps = {}
        for timestamp in timestamps:
            stamp = datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc)
            month_timestamps.setdefault((stamp.year, stamp.month), []).append(int(timestamp))
        for index in range(months):
            absolute_month = index
            key = (base_year + absolute_month // 12, absolute_month % 12 + 1)
            selected_by_month[key] = select_timestamps(month_timestamps.get(key, []), [0, 6, 12, 18])
    month_images = []
    for index in range(months):
        month_start = start.advance(index, "month")
        month_end = month_start.advance(1, "month")
        month_collection = collection.filterDate(month_start, month_end)
        if variable.startswith("merra2_"):
            hours = [0, 6, 12, 18]
            filters = [ee.Filter.calendarRange(hour, hour, "hour") for hour in hours]
            hour_filter = filters[0] if len(filters) == 1 else ee.Filter.Or(*filters)
            month_collection = month_collection.filter(hour_filter)
        else:
            key = (base_year + index // 12, index % 12 + 1)
            available = selected_by_month[key]
            month_collection = month_collection.filter(ee.Filter.inList("system:time_start", available))
        month_images.append(month_collection.mean().rename(cfg["band"]))
    return ee.ImageCollection.fromImages(month_images).mean().multiply(cfg["scale_factor"]).add(cfg.get("offset", 0)), cfg


def one_measurement(variable, geometry, year, months, tile_scale=16, simplify=True):
    cfg = region_config[variable]
    setup_started = time.perf_counter()
    source = ee.Geometry(geometry)
    area = float(source.area(maxError=1).getInfo())
    scale = max(float(cfg["scale"]), (area / 1_000_000) ** 0.5)
    reduced_geometry = source.simplify(maxError=min(scale * 0.25, 1000)) if simplify else source
    image, cfg = build_composite(
        variable, reduced_geometry, ee.Date.fromYMD(year, 1, 1), months, year
    )
    setup_seconds = time.perf_counter() - setup_started
    started = time.perf_counter()
    if cfg["equal_area"]:
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=reduced_geometry, scale=scale,
            maxPixels=1_000_000_000, tileScale=tile_scale,
        ).getInfo()
        value = stats.get(cfg["band"])
    else:
        area = ee.Image.pixelArea().updateMask(image.mask()).rename("area")
        stats = image.multiply(area).rename("weighted").addBands(area).reduceRegion(
            reducer=ee.Reducer.sum(), geometry=reduced_geometry, scale=scale,
            maxPixels=1_000_000_000, tileScale=tile_scale,
        ).getInfo()
        denominator = stats.get("area") or 0
        value = stats.get("weighted") / denominator if denominator else None
    reduce_seconds = time.perf_counter() - started
    return setup_seconds, reduce_seconds, value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variable", choices=VARIABLES, required=True)
    parser.add_argument("--region", choices=["istanbul"], required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    try:
        initialize()
        geometry, source = load_istanbul()
        print(f"Region: {args.region}; boundary: {source}; variable: {args.variable}; year: {args.year}")
        rows = []
        for months in (1, 3, 12):
            try:
                setup, reduce_time, value = one_measurement(args.variable, geometry, args.year, months)
                rows.append((f"{months} month(s)", "ok", setup, reduce_time, value))
            except Exception as error:
                rows.append((f"{months} month(s)", f"error: {error}", None, None, None))
        for tile_scale in (1, 4, 8, 16):
            try:
                setup, reduce_time, value = one_measurement(args.variable, geometry, args.year, 1, tile_scale=tile_scale)
                rows.append((f"1 month tileScale={tile_scale}", "ok", setup, reduce_time, value))
            except Exception as error:
                rows.append((f"1 month tileScale={tile_scale}", f"error: {error}", None, None, None))
        for simplify in (False, True):
            try:
                setup, reduce_time, value = one_measurement(args.variable, geometry, args.year, 1, simplify=simplify)
                rows.append((f"1 month simplify={simplify}", "ok", setup, reduce_time, value))
            except Exception as error:
                rows.append((f"1 month simplify={simplify}", f"error: {error}", None, None, None))
        print("| Case | Status | Geometry setup seconds | reduceRegion + getInfo seconds | Mean |")
        print("|---|---|---:|---:|---:|")
        for label, status, setup, reduce_time, value in rows:
            print(f"| {label} | {status} | {setup if setup is not None else '—'} | {reduce_time if reduce_time is not None else '—'} | {value if value is not None else '—'} |")
    except Exception as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
