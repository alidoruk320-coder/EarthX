#!/usr/bin/env python3
"""Compare monthly full-cadence and fixed-time Earth Engine composites."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import ee, polygonal_geometry

REQUEST_TIMEOUT_MS = 300_000
REGION = "istanbul"
VARIABLES = (
    "soil_moisture",
    "merra2_t2m",
    "merra2_precipitable_water",
    "merra2_evaporation",
)


def feature_collection_geometry(collection_id, filters):
    collection = ee.FeatureCollection(collection_id)
    for property_name, value in filters:
        collection = collection.filter(ee.Filter.eq(property_name, value))
    feature = collection.first().getInfo()
    if not feature or not feature.get("geometry"):
        raise RuntimeError(f"No boundary geometry in {collection_id}: {filters}")
    return polygonal_geometry(feature["geometry"])


def initialize_gee_with_deadline():
    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        return False
    ee.data.setDeadline(REQUEST_TIMEOUT_MS)
    return True


def istanbul_boundary():
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


def _quality_mask(collection, cfg):
    mask = cfg.get("mask")
    if not mask:
        return collection

    def apply(image):
        quality = image.select(mask["band"]).bitwiseAnd(3)
        accepted = quality.eq(mask["accepted_values"][0])
        for value in mask["accepted_values"][1:]:
            accepted = accepted.Or(quality.eq(value))
        return image.updateMask(accepted)

    return collection.map(apply)


def _hour_filter(hours):
    filters = [ee.Filter.calendarRange(hour, hour, "hour") for hour in hours]
    return filters[0] if len(filters) == 1 else ee.Filter.Or(*filters)


def select_available_timestamps(timestamps, targets):
    """Pick nearest real UTC images for each target slot, once per day."""
    by_day = {}
    for timestamp in timestamps:
        stamp = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
        by_day.setdefault(stamp.date(), []).append((stamp, int(timestamp)))
    selected = []
    for day_images in by_day.values():
        remaining = list(day_images)
        for target in targets:
            if not remaining:
                break
            def distance(item):
                hour = item[0].hour + item[0].minute / 60
                delta = abs(hour - target)
                return min(delta, 24 - delta)
            chosen = min(remaining, key=distance)
            selected.append(chosen[1])
            remaining.remove(chosen)
    return selected


def variant_collection(variable, year, month, variant):
    cfg = region_config[variable]
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    collection = (
        ee.ImageCollection(cfg["collection"])
        .filterDate(start, end)
        .select(cfg["band"])
    )
    collection = _quality_mask(collection, cfg)

    if variant == "merra_4_per_day":
        collection = collection.filter(_hour_filter([0, 6, 12, 18]))
    elif variant in {"smap_2_per_day", "smap_1_per_day"}:
        # SPL4SMGP timestamps are not guaranteed to land on the requested
        # wall-clock hour bins. Choose from timestamps that really exist.
        timestamps = collection.aggregate_array("system:time_start").getInfo() or []
        if not timestamps:
            raise ValueError(f"No SMAP images exist for {year}-{month:02d}")
        targets = (0, 12) if variant == "smap_2_per_day" else (0,)
        selected = select_available_timestamps(timestamps, targets)
        if not selected:
            raise ValueError(f"No SMAP timestamps matched {variant} for {year}-{month:02d}")
        collection = collection.filter(ee.Filter.inList("system:time_start", selected))
    elif variant != "full":
        raise ValueError(f"Unknown sampling variant: {variant}")
    return collection


def measure_variant(variable, geometry, year, month, variant):
    cfg = region_config[variable]
    started = time.perf_counter()
    collection = variant_collection(variable, year, month, variant)
    image = collection.mean().multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
    stats = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=cfg["scale"],
        maxPixels=1_000_000_000,
        tileScale=16,
    )
    query = ee.Dictionary(stats).set("image_count", collection.size())
    result = query.getInfo()
    elapsed = time.perf_counter() - started
    return {
        "variant": variant,
        "seconds": elapsed,
        "image_count": result.get("image_count"),
        "mean": result.get(cfg["band"]),
    }


def variants_for(variable):
    return ("full", "merra_4_per_day") if variable.startswith("merra2_") else (
        "full", "smap_2_per_day", "smap_1_per_day"
    )


def format_number(value):
    return "—" if value is None else f"{float(value):.8g}"


def run_variant_isolated(variable, geometry, year, month, variant):
    payload = {
        "variable": variable,
        "geometry": geometry,
        "year": year,
        "month": month,
        "variant": variant,
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as stream:
        json.dump(payload, stream)
        path = stream.name
    started = time.perf_counter()
    try:
        try:
            child = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--internal-worker", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=REQUEST_TIMEOUT_MS / 1000,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "variant": variant,
                "status": "TIMEOUT",
                "seconds": REQUEST_TIMEOUT_MS / 1000,
                "image_count": None,
                "mean": None,
                "error": "Hard 300-second worker timeout; child process was terminated.",
            }
        if child.returncode != 0:
            detail = child.stderr.strip() or child.stdout.strip() or f"worker exited {child.returncode}"
            return {
                "variant": variant,
                "status": "TIMEOUT" if "timeout" in detail.lower() or "deadline" in detail.lower() else "ERROR",
                "seconds": time.perf_counter() - started,
                "image_count": None,
                "mean": None,
                "error": detail[-1200:],
            }
        line = next((line for line in child.stdout.splitlines() if line.startswith("RESULT_JSON=")), None)
        if line is None:
            return {"variant": variant, "status": "ERROR", "error": "Worker returned no result record"}
        result = json.loads(line[len("RESULT_JSON="):])
        return {"variant": variant, "status": "OK", **result}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def worker_main(path):
    with open(path, encoding="utf-8") as stream:
        payload = json.load(stream)
    if not initialize_gee_with_deadline():
        raise RuntimeError("Earth Engine initialization failed; configure backend/.env and credentials.")
    result = measure_variant(
        payload["variable"], payload["geometry"], payload["year"],
        payload["month"], payload["variant"],
    )
    print("RESULT_JSON=" + json.dumps(result, allow_nan=False))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--internal-worker":
        try:
            worker_main(sys.argv[2])
        except Exception as error:
            print(f"Worker error: {type(error).__name__}: {error}", file=sys.stderr)
            raise SystemExit(1)
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--variable", choices=VARIABLES, required=True)
    parser.add_argument("--region", choices=[REGION], required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, choices=range(1, 13), required=True)
    args = parser.parse_args()

    if not initialize_gee_with_deadline():
        raise SystemExit("Earth Engine initialization failed; configure backend/.env and credentials.")
    geometry, boundary_source = istanbul_boundary()
    print(f"Region: {args.region}; boundary: {boundary_source}; variable: {args.variable}; period: {args.year}-{args.month:02d}")
    print("Each synchronous Earth Engine request has a 300-second SDK deadline; variants run sequentially.")

    measurements = []
    for variant in variants_for(args.variable):
        print(f"Running {variant} sequentially (hard limit 300 seconds)...", flush=True)
        measurements.append(run_variant_isolated(
            args.variable, geometry, args.year, args.month, variant
        ))

    baseline = next((row.get("mean") for row in measurements if row["variant"] == "full" and row.get("status") == "OK"), None)
    print("| Variant | Status | Seconds | Images used | Monthly regional mean | Absolute difference | Percent difference |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for row in measurements:
        value = row.get("mean")
        absolute = abs(float(value) - float(baseline)) if value is not None and baseline is not None else None
        percent = absolute / abs(float(baseline)) * 100 if absolute is not None and float(baseline) != 0 else None
        percent_text = f"{format_number(percent)}%" if percent is not None else "—"
        seconds = "—" if row.get("seconds") is None else f"{row['seconds']:.3f}"
        print(
            f"| {row['variant']} | {row['status']} | {seconds} | {row.get('image_count', '—')} | "
            f"{format_number(value)} | {format_number(absolute)} | {percent_text} |"
        )
        if row.get("error"):
            print(f"  {row['variant']} error: {row['error']}")


if __name__ == "__main__":
    main()
