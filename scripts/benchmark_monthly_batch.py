#!/usr/bin/env python3
"""Sequentially probe monthly server aggregation blocks with a 5-minute EE deadline."""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID
from app.services.gee_client import init_gee, is_gee_initialized
from app.services import region_analysis
from app.services.region_analysis import analyze_region, ee, polygonal_geometry

LIMIT_MS = 300_000
VARIABLES = ("soil_moisture", "merra2_t2m", "merra2_evaporation")


def initialize():
    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        raise RuntimeError("Earth Engine initialization failed; check backend/.env and credentials.")
    ee.data.setDeadline(LIMIT_MS)


def boundary():
    candidates = [
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Turkey"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Turkey"),
    ]
    errors = []
    for collection_id, country_field, region_field, country in candidates:
        try:
            feature = ee.FeatureCollection(collection_id).filter(
                ee.Filter.eq(country_field, country)
            ).filter(ee.Filter.eq(region_field, "Istanbul")).first().getInfo()
            if feature and feature.get("geometry"):
                return polygonal_geometry(feature["geometry"]), collection_id
        except Exception as error:
            errors.append(f"{collection_id}: {error}")
    raise RuntimeError("Could not fetch Istanbul polygon: " + "; ".join(errors[-2:]))


def run_block(geometry, variable, start, end, batch_years):
    started = time.perf_counter()
    try:
        # A previous probe may have cached this exact region/period/mode.
        # Clear it so every benchmark row performs a fresh Earth Engine run.
        with region_analysis._cache_lock:
            region_analysis._cache.clear()
        result = analyze_region(
            geometry, variable, start, end,
            aggregation_mode="monthly_server_batch", batch_years=batch_years,
        )
        reducer_requests = (end - start + batch_years) // batch_years
        return {
            "status": result.get("status", "ok"),
            "elapsed_seconds": time.perf_counter() - started,
            # One geometry-area getInfo plus one FeatureCollection getInfo per batch.
            "requests": 1 + reducer_requests,
            "observations": len(result.get("raw_series", [])),
            "missing_months": len(result.get("missing_months", [])),
            "error": None,
        }
    except Exception as error:
        return {
            "status": "ERROR" if "memory" not in str(error).lower() else "MEMORY_ERROR",
            "elapsed_seconds": time.perf_counter() - started,
            "requests": None,
            "observations": None,
            "missing_months": None,
            "error": str(error),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variable", choices=VARIABLES, required=True)
    parser.add_argument("--region", choices=["istanbul"], required=True)
    parser.add_argument("--full-run", action="store_true")
    parser.add_argument("--batch-years", type=int, choices=range(1, 27))
    args = parser.parse_args()
    initialize()
    geometry, source = boundary()
    start, end = (2015, 2025) if args.variable == "soil_moisture" else (2000, 2025)
    print(f"Region: {args.region}; boundary: {source}; variable: {args.variable}; requested period: {start}-{end}")
    measurements = []
    for years in (1, 5, end - start + 1):
        if any(years == row["block_years"] for row in measurements):
            continue
        print(f"Running {years}-year block sequentially (each EE request deadline: 300 seconds)...", flush=True)
        row = run_block(geometry, args.variable, start, min(end, start + years - 1), years)
        row["block_years"] = years
        measurements.append(row)
    successful = [row["block_years"] for row in measurements if row["status"] == "ok"]
    failed = [row["block_years"] for row in measurements if row["status"] != "ok"]
    low = max(successful, default=0)
    high = min((value for value in failed if value > low), default=end - start + 2)
    while low and high - low > 1:
        candidate = (low + high) // 2
        print(f"Probing block size {candidate} sequentially (300-second per-request deadline)...", flush=True)
        row = run_block(geometry, args.variable, start, min(end, start + candidate - 1), candidate)
        row["block_years"] = candidate
        measurements.append(row)
        if row["status"] == "ok":
            low = candidate
        else:
            high = candidate
    max_successful_block = low or None
    if args.full_run:
        full_batch_years = args.batch_years or max_successful_block or 1
        if max_successful_block is None:
            print("Full-period run skipped: no successful probe block size was established.")
        else:
            print(f"Running complete {start}-{end} series in sequential {full_batch_years}-year blocks; each EE request deadline is 300 seconds.", flush=True)
            full_started = time.perf_counter()
            full_requests = 0
            full_errors = []
            for block_start in range(start, end + 1, full_batch_years):
                block_end = min(end, block_start + full_batch_years - 1)
                block = run_block(geometry, args.variable, block_start, block_end, full_batch_years)
                if block["status"] != "ok":
                    full_errors.append(f"{block_start}-{block_end}: {block['error']}")
                    break
                full_requests += block["requests"]
            full_elapsed = time.perf_counter() - full_started
            print(f"Full period measured: analysis_requests={full_requests if not full_errors else 'incomplete/unknown'}; elapsed_seconds={full_elapsed:.3f}; status={'ERROR' if full_errors else 'ok'}")
            if full_errors:
                print("Full-period error: " + full_errors[0])
    print("| Block years | Status | Elapsed seconds | EE request count | Annual observations | Missing months | Error |")
    print("|---:|---|---:|---:|---:|---:|---|")
    for row in measurements:
        print(f"| {row['block_years']} | {row['status']} | {row['elapsed_seconds']:.3f} | {row['requests'] if row['requests'] is not None else '—'} | {row['observations'] if row['observations'] is not None else '—'} | {row['missing_months'] if row['missing_months'] is not None else '—'} | {row['error'] or '—'} |")
    print(f"Largest successful block among tested sizes: {max_successful_block if max_successful_block is not None else 'not established'} year(s)")
    print("Boundary lookup was one additional Earth Engine getInfo call; it is outside the analysis-request counts above.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error))
