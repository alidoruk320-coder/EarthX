#!/usr/bin/env python3
"""Sequential live polygon benchmark for Türkiye and Istanbul (GEE required).

Run from repository root:
  backend/.venv312/bin/python scripts/benchmark_turkey.py

All Earth Engine calls are intentionally sequential. No concurrent requests are
created. The script measures what it actually receives and prints failures.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import GEE_PROJECT_ID, region_config
from app.services.gee_client import init_gee, is_gee_initialized
from app.services.region_analysis import analyze_region, ee, polygonal_geometry
from app.services.trend_engine import analyze_annual_series
import pymannkendall as mk


VARIABLES = (
    "ndvi", "soil_moisture", "grace_tws", "gpm_precipitation",
    "total_column_ozone", "merra2_t2m", "merra2_precipitable_water",
    "merra2_evaporation", "gldas_root_moisture", "gldas_surface_runoff",
)


def feature_collection_geometry(collection_id, filters):
    collection = ee.FeatureCollection(collection_id)
    for property_name, value in filters:
        collection = collection.filter(ee.Filter.eq(property_name, value))
    feature = collection.first()
    if feature is None:
        raise RuntimeError(f"No boundary found in {collection_id}: {filters}")
    result = feature.getInfo()
    if not result or not result.get("geometry"):
        raise RuntimeError(f"No polygon geometry found in {collection_id}: {filters}")
    return polygonal_geometry(result["geometry"])


def turkey_boundary():
    errors = []
    for name in ("Turkey", "Türkiye"):
        try:
            return feature_collection_geometry(
                "FAO/GAUL/2015/level0", [("ADM0_NAME", name)]
            ), "FAO GAUL 2015 level0"
        except Exception as error:
            errors.append(str(error))
    raise RuntimeError("Could not load Türkiye from FAO GAUL: " + "; ".join(errors))


def istanbul_boundary():
    errors = []
    candidates = (
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Turkey"),
        ("FAO/GAUL_SIMPLIFIED_500m/2025/level1", "GAUL0_NAME", "GAUL1_NAME", "Türkiye"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Turkey"),
        ("FAO/GAUL/2015/level1", "ADM0_NAME", "ADM1_NAME", "Türkiye"),
    )
    for collection_id, country_property, city_property, country in candidates:
        try:
            return feature_collection_geometry(
                collection_id,
                [(country_property, country), (city_property, "Istanbul")],
            ), collection_id
        except Exception as error:
            errors.append(f"{collection_id}/{country}: {error}")
    raise RuntimeError("Could not load Istanbul from FAO GAUL: " + "; ".join(errors))


def fmt(value):
    return "—" if value is None else f"{value:.8g}" if isinstance(value, (int, float)) else str(value)


def run_case(region_name, geometry, boundary_source, variable):
    cfg = region_config[variable]
    start_year = max(2000, cfg["start_year"])
    end_year = min(2025, cfg["latest_complete_year"])
    label = cfg.get("source") or cfg["collection"]
    try:
        result = analyze_region(geometry, variable, start_year, end_year)
        warnings = [
            key for key in (
                "resolution_warning", "short_series_warning", "missing_year_warning",
                "partial_year_excluded", "low_coverage_years",
            ) if result.get(key)
        ]
        print(
            f"| {region_name} | {variable} | {result.get('elapsed_seconds', 0):.3f} | "
            f"{result.get('scale_used', '—')} | {result.get('source_used', result.get('dataset_id', '—'))} | "
            f"{result.get('valid_pixel_count', 0)} | {len(result.get('raw_series', []))} | "
            f"{fmt(result.get('sen_slope'))} | {fmt(result.get('p_value'))} | "
            f"{', '.join(warnings) or '—'} |"
        )
        if warnings:
            for warning in warnings:
                print(f"  {warning}: {result[warning]}")
        if result.get("elapsed_seconds", 0) > 60:
            suggestion = (
                "The targeted products already use one year per sequential request, 12 explicit monthly filters, "
                "and tileScale=16. A further change must be measured before adoption; temporal subsampling is "
                "not enabled unless the full-resolution request still fails."
            )
            print(f"  SPEED (>60 s): {suggestion}")
        print(f"  source configuration: {label}; boundary: {boundary_source}; interval: {start_year}-{end_year}")
        if variable == "gldas_surface_runoff" and result.get("raw_series"):
            observations = result["raw_series"]
            values = [float(row["value"]) for row in observations if row.get("value") is not None]
            engine = analyze_annual_series(
                [(int(row["year"]), float(row["value"])) for row in observations if row.get("value") is not None],
                expected_start_year=start_year,
                expected_end_year=end_year,
            )
            direct = mk.hamed_rao_modification_test(values, lag=None) if len(values) >= 8 else None
            s_stat = getattr(direct, "s", None) if direct else None
            slope = mk.sens_slope(values).slope if len(values) >= 2 else None
            agrees = bool(direct and engine.get("p_value") is not None
                and engine.get("z_score") is not None and engine.get("sen_slope") is not None
                and abs(float(engine.get("p_value")) - float(direct.p)) < 1e-12 and
                abs(float(engine.get("z_score")) - float(direct.z)) < 1e-5 and
                abs(float(engine.get("sen_slope")) - float(slope)) < 1e-7)
            print(
                f"  GLDAS runoff independent MK: S={s_stat}, z={getattr(direct, 'z', None)}, "
                f"p={getattr(direct, 'p', None)}, pymannkendall Sen={slope}; "
                f"engine/direct agreement={agrees}"
            )
    except Exception as error:
        detail = str(error)
        concurrency = "too many concurrent aggregations" in detail.lower()
        print(
            f"| {region_name} | {variable} | ERROR | — | {label} | — | — | — | — | "
            f"{'concurrency: ' if concurrency else ''}{detail} |"
        )


def main():
    try:
        initialized = bool(GEE_PROJECT_ID and init_gee() and is_gee_initialized())
    except Exception as error:
        reason = (
            "Earth Engine initialization failed before any benchmark request: "
            f"{type(error).__name__}: {error}"
        )
        print(reason)
        print("| Region | Variable | seconds | scale m | source used | min valid pixels | annual obs | Sen slope | p-value | warnings/error |")
        print("|---|---|---:|---:|---|---:|---:|---:|---:|---|")
        for region_name in ("Türkiye", "Istanbul"):
            for variable in VARIABLES:
                print(f"| {region_name} | {variable} | NOT RUN | — | — | — | — | — | — | {reason} |")
        return
    if not initialized:
        raise SystemExit("Earth Engine initialization failed; configure backend/.env and GEE project credentials first.")
    print("Boundary lookup: GAUL 2025 level1 preferred for Istanbul; GAUL 2015 fallbacks. Every GEE analysis is sequential.")
    try:
        turkey, turkey_source = turkey_boundary()
    except Exception as error:
        turkey, turkey_source = None, f"UNAVAILABLE: {error}"
    try:
        istanbul, istanbul_source = istanbul_boundary()
    except Exception as error:
        istanbul, istanbul_source = None, f"UNAVAILABLE: {error}"

    print("| Region | Variable | seconds | scale m | source used | min valid pixels | annual obs | Sen slope | p-value | warnings/error |")
    print("|---|---|---:|---:|---|---:|---:|---:|---:|---|")
    for name, geometry, source in (
        ("Türkiye", turkey, turkey_source),
        ("Istanbul", istanbul, istanbul_source),
    ):
        if geometry is None:
            for variable in VARIABLES:
                print(f"| {name} | {variable} | NOT RUN | — | — | — | — | — | — | Boundary lookup failed: {source} |")
            continue
        for variable in VARIABLES:
            run_case(name, geometry, source, variable)


if __name__ == "__main__":
    main()
