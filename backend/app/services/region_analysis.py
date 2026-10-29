import copy
import hashlib
import json
import math
import threading
import time
from collections import OrderedDict

import ee

from app.config import region_config
from app.services.trend_engine import analyze_annual_series

CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 64
LOW_COVERAGE_PIXEL_THRESHOLD = 3
_cache = OrderedDict()
_cache_lock = threading.Lock()


def _normalize_geometry(payload: dict) -> dict:
    if payload.get("type") == "Feature":
        payload = payload.get("geometry") or {}
    if payload.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("geometry must be a GeoJSON Polygon or MultiPolygon")

    coordinates = payload.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("GeoJSON geometry has no coordinates")

    def validate_ring(ring):
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Each polygon ring must contain at least four coordinates")
        normalized = []
        for position in ring:
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                raise ValueError("Invalid GeoJSON coordinate")
            lon, lat = float(position[0]), float(position[1])
            if not (math.isfinite(lon) and math.isfinite(lat)
                    and -180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("GeoJSON coordinate is outside longitude/latitude limits")
            normalized.append((lon, lat))
        if normalized[0] != normalized[-1]:
            raise ValueError("GeoJSON linear rings must be closed")

    polygons = [coordinates] if payload["type"] == "Polygon" else coordinates
    if not polygons:
        raise ValueError("GeoJSON geometry contains no polygons")
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Polygon must contain an exterior ring")
        for ring in polygon:
            validate_ring(ring)
    return {"type": payload["type"], "coordinates": coordinates}


def _cache_key(geometry: dict, variable: str, start_year: int, end_year: int) -> str:
    encoded = json.dumps(
        {"geometry": geometry, "variable": variable, "start_year": start_year, "end_year": end_year},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_get(key: str):
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached is None:
            return None
        expires_at, result = cached
        if expires_at <= now:
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return copy.deepcopy(result)


def _cache_set(key: str, result: dict):
    with _cache_lock:
        _cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, copy.deepcopy(result))
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _fetch_ee_features(geojson: dict, cfg: dict, start_year: int, end_year: int) -> list:
    """Build one server-side yearly FeatureCollection and make one getInfo call."""
    geometry = ee.Geometry(geojson)
    center = geometry.centroid(maxError=1)
    collection = ee.ImageCollection(cfg["collection"]).filterBounds(geometry)
    quality_mask = cfg.get("mask")
    if quality_mask:
        quality_band = quality_mask["band"]
        accepted_values = quality_mask["accepted_values"]

        def apply_quality_mask(image):
            qa = image.select(quality_band)
            quality = qa.bitwiseAnd(3)
            accepted = quality.eq(accepted_values[0])
            for value in accepted_values[1:]:
                accepted = accepted.Or(quality.eq(value))
            return image.updateMask(accepted)

        collection = collection.map(apply_quality_mask)
    collection = collection.select(cfg["band"])
    native_projection = collection.first().select(cfg["band"]).projection()
    empty_band = (
        ee.Image.constant(0)
        .rename(cfg["band"])
        .updateMask(ee.Image.constant(0))
        .setDefaultProjection(native_projection)
    )
    temporal_reducer = ee.Reducer.sum() if cfg["aggregate"] == "sum" else ee.Reducer.mean()
    monthly_first = cfg.get("monthly_first", False)

    def annual_feature(year):
        year = ee.Number(year)
        annual_start = ee.Date.fromYMD(year, 1, 1)
        annual_end = annual_start.advance(1, "year")
        annual_collection = collection.filterDate(annual_start, annual_end)

        if monthly_first:
            def monthly_image(month):
                month_start = ee.Date.fromYMD(year, month, 1)
                month_end = month_start.advance(1, "month")
                monthly_collection = annual_collection.filterDate(month_start, month_end)
                monthly_collection = monthly_collection.merge(
                    ee.ImageCollection.fromImages([empty_band])
                )
                return monthly_collection.reduce(temporal_reducer).rename(cfg["band"])

            annual_collection = ee.ImageCollection.fromImages(
                ee.List.sequence(1, 12).map(monthly_image)
            )
        else:
            annual_collection = annual_collection.merge(
                ee.ImageCollection.fromImages([empty_band])
            )

        annual = annual_collection.reduce(temporal_reducer).rename(cfg["band"])
        annual = annual.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
        pixel_area = ee.Image.pixelArea().updateMask(annual.mask()).rename("pixel_area")
        weighted_image = annual.multiply(pixel_area).rename("weighted_value")
        reduce_args = {
            "geometry": geometry,
            "scale": cfg["scale"],
            "maxPixels": 1_000_000_000,
            "tileScale": 4,
        }
        numerator = weighted_image.reduceRegion(
            reducer=ee.Reducer.sum(), **reduce_args
        ).get("weighted_value")
        denominator = pixel_area.reduceRegion(
            reducer=ee.Reducer.sum(), **reduce_args
        ).get("pixel_area")
        valid_pixels = annual.reduceRegion(
            reducer=ee.Reducer.count(), **reduce_args
        ).get(cfg["band"])
        center_value = annual.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=center,
            scale=cfg["scale"],
            maxPixels=1_000_000_000,
            tileScale=4,
        ).get(cfg["band"])
        return ee.Feature(None, {
            "year": year,
            "numerator": numerator,
            "denominator": denominator,
            "center_value": center_value,
            "valid_pixel_count": valid_pixels,
            "area_m2": geometry.area(maxError=1),
        })

    features = ee.FeatureCollection(
        ee.List.sequence(start_year, end_year).map(annual_feature)
    )
    return features.getInfo()["features"]


def _build_result(features: list, geometry: dict, variable: str, cfg: dict,
                  start_year: int, end_year: int, elapsed_seconds: float) -> dict:
    rows_by_year = {}
    fallback_used = False
    nominal_cell_area = float(cfg.get("nominal_pixel_area_m2", cfg["scale"] ** 2))

    for feature in features:
        props = feature.get("properties", {})
        if props.get("year") is None:
            continue
        year = int(props["year"])
        numerator = props.get("numerator")
        denominator = props.get("denominator")
        center_value = props.get("center_value")
        area_m2 = float(props.get("area_m2") or 0)
        raw_pixel_count = props.get("valid_pixel_count")
        pixel_count = int(raw_pixel_count or 0)
        small_polygon = 0 < area_m2 < nominal_cell_area

        value = None
        method = "polygon_area_weighted"
        has_area_weighted_value = (
            numerator is not None
            and denominator is not None
            and float(denominator or 0) > 0
        )
        if small_polygon or not has_area_weighted_value:
            if center_value is not None and math.isfinite(float(center_value)):
                value = float(center_value)
                pixel_count = max(pixel_count, 1)
                method = "polygon_area_weighted_single_cell"
                fallback_used = True
        if value is None and has_area_weighted_value:
            value = float(numerator) / float(denominator)
            if not math.isfinite(value):
                value = None

        if value is None:
            rows_by_year[year] = None
            continue
        rows_by_year[year] = {
            "date": f"{year}-01-01",
            "year": year,
            "value": round(value, 6),
            "valid_pixel_count": pixel_count,
            "low_coverage": pixel_count < LOW_COVERAGE_PIXEL_THRESHOLD,
            "method": method,
        }

    series = [rows_by_year[year] for year in sorted(rows_by_year) if rows_by_year[year] is not None]
    if not series:
        raise ValueError("No valid source pixels or center-cell observations were found inside this polygon for the selected period.")

    years = [point["year"] for point in series]
    missing_years = sorted(set(range(start_year, end_year + 1)) - set(years))
    annual_values = [(point["year"], point["value"]) for point in series]
    trend = analyze_annual_series(
        annual_values,
        expected_start_year=start_year,
        expected_end_year=end_year,
    )
    pixel_counts = [point["valid_pixel_count"] for point in series]
    area_m2 = next((float(item["properties"].get("area_m2") or 0) for item in features), 0)
    small_polygon = 0 < area_m2 < nominal_cell_area
    single_cell = fallback_used
    method = "polygon_area_weighted_single_cell" if single_cell else "polygon_area_weighted"
    aggregate_label = "annual total" if cfg["aggregate"] == "sum" else "annual mean"
    result = {
        "region": {"type": geometry["type"], "area_km2": round(area_m2 / 1_000_000, 3)},
        "variable": variable,
        "source": cfg.get("source") or "Google Earth Engine",
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "temporal_resolution": cfg.get("temporal_resolution"),
        "unit": cfg["unit"],
        "aggregation_label": aggregate_label,
        "method": method,
        "aggregate": cfg["aggregate"],
        "scale_meters": cfg["scale"],
        "valid_pixel_count": min(pixel_counts) if pixel_counts else 0,
        "valid_pixel_count_range": {
            "min": min(pixel_counts) if pixel_counts else 0,
            "max": max(pixel_counts) if pixel_counts else 0,
        },
        "low_coverage_years": [point["year"] for point in series if point["low_coverage"]],
        "raw_series": series,
        "missing_years": missing_years,
        "elapsed_seconds": round(elapsed_seconds, 3),
        **trend,
    }
    if small_polygon or fallback_used:
        result["resolution_warning"] = (
            f"The polygon is smaller than one nominal {cfg['scale']} m source cell, "
            "or its valid-area denominator was empty; center-cell values are used where available."
        )
    if missing_years:
        result["missing_year_warning"] = (
            "Missing annual observations were excluded; Mann–Kendall significance is withheld for a gapped series."
        )
    if len(series) < 15:
        result["short_series_warning"] = (
            "Fewer than 15 annual observations are available; a longer record may be needed to detect a trend reliably."
        )
    if result.get("trend") == "insufficient_data" and missing_years:
        result["significance_withheld"] = True
    return result


def analyze_region(geometry_payload: dict, variable: str, start_year: int, end_year: int) -> dict:
    started = time.perf_counter()
    if variable not in region_config:
        raise ValueError(f"Polygon area-weighted analysis is not configured for {variable}")
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    cfg = region_config[variable]
    if start_year < cfg["start_year"]:
        raise ValueError(f"{variable} data starts in {cfg['start_year']}")
    if end_year > cfg["latest_complete_year"]:
        raise ValueError(f"{variable} latest complete year is {cfg['latest_complete_year']}")

    geojson = _normalize_geometry(geometry_payload)
    key = _cache_key(geojson, variable, start_year, end_year)
    cached = _cache_get(key)
    if cached is not None:
        cached["cache_hit"] = True
        cached["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        return cached

    try:
        features = _fetch_ee_features(geojson, cfg, start_year, end_year)
    except Exception as error:
        raise RuntimeError(f"Earth Engine regional analysis failed: {error}") from error

    result = _build_result(
        features,
        geojson,
        variable,
        cfg,
        start_year,
        end_year,
        0,
    )
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result["cache_hit"] = False
    _cache_set(key, result)
    return result
