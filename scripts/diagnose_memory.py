#!/usr/bin/env python3
"""Diagnose memory blow-ups in Earth Engine regional requests.

Examples:
  backend/.venv312/bin/python scripts/diagnose_memory.py --region istanbul --variable soil_moisture --start-year 2015 --end-year 2016
  backend/.venv312/bin/python scripts/diagnose_memory.py --region turkey --variable merra2_t2m --start-year 2024 --end-year 2024
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import ee, polygonal_geometry


VARIABLES = (
    "soil_moisture",
    "merra2_t2m",
    "merra2_evaporation",
)


def feature_collection_geometry(collection_id, filters):
    collection = ee.FeatureCollection(collection_id)
    for key, value in filters:
        collection = collection.filter(ee.Filter.eq(key, value))
    feature = collection.first()
    if feature is None:
        raise RuntimeError(f"No boundary found in {collection_id}: {filters}")
    result = feature.getInfo()
    if not result or not result.get("geometry"):
        raise RuntimeError(f"No polygon geometry found in {collection_id}: {filters}")
    return polygonal_geometry(result["geometry"])


def turkey_boundary():
    for name in ("Turkey", "Türkiye"):
        try:
            return feature_collection_geometry("FAO/GAUL/2015/level0", [("ADM0_NAME", name)])
        except Exception:
            pass
    raise RuntimeError("Could not find Türkiye boundary")


def istanbul_boundary():
    candidates = (
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Turkey"),
        ("FAO/GAUL_SIMPLIFIED_500m/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Turkey"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Türkiye"),
    )
    for collection_id, country_property, region_property, country in candidates:
        try:
            return feature_collection_geometry(
                collection_id,
                [(country_property, country), (region_property, "Istanbul")],
            )
        except Exception:
            continue
    raise RuntimeError("Could not find Istanbul boundary")


def region_geometry(region_name):
    if region_name == "istanbul":
        return istanbul_boundary()
    if region_name == "turkey":
        return turkey_boundary()
    raise ValueError(f"Unsupported region: {region_name}")


def apply_quality_mask(cfg, collection):
    quality_mask = cfg.get("mask")
    if not quality_mask:
        return collection.select(cfg["band"])
    quality_band = quality_mask["band"]
    accepted_values = quality_mask["accepted_values"]

    def _mask(image):
        qa = image.select(quality_band)
        quality = qa.bitwiseAnd(3)
        accepted = quality.eq(accepted_values[0])
        for value in accepted_values[1:]:
            accepted = accepted.Or(quality.eq(value))
        return image.updateMask(accepted)

    return collection.map(_mask).select(cfg["band"])


def probe_month(variable, geometry, year, month):
    cfg = region_config[variable]
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    collection = ee.ImageCollection(cfg["collection"]).filterBounds(geometry).filterDate(start, end)
    collection = apply_quality_mask(cfg, collection)
    image = collection.mean().rename(cfg["band"])
    image = image.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
    scale = cfg.get("scale")
    stats = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=scale,
        maxPixels=1_000_000_000,
        tileScale=16,
    )
    return stats.getInfo()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=["istanbul", "turkey"], required=True)
    parser.add_argument("--variable", choices=VARIABLES, required=True)
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    if not GEE_PROJECT_ID or not init_gee() or not is_gee_initialized():
        raise SystemExit("Earth Engine is not initialized for this project. Configure backend/.env and authenticate first.")

    geometry = region_geometry(args.region)
    print(f"Region={args.region}; variable={args.variable}; years={args.start_year}-{args.end_year}")
    print("year,month,status,seconds,error")
    for year in range(args.start_year, args.end_year + 1):
        for month in range(1, 13):
            started = time.perf_counter()
            try:
                result = probe_month(args.variable, geometry, year, month)
                duration = time.perf_counter() - started
                print(f"{year},{month},OK,{duration:.3f},{result}")
            except Exception as error:
                duration = time.perf_counter() - started
                print(f"{year},{month},ERROR,{duration:.3f},{type(error).__name__}: {error}")
                if "memory" in str(error).lower() or "limit" in str(error).lower():
                    print(f"BREAKING_AT={year}-{month:02d}")
                    return


if __name__ == "__main__":
    main()
