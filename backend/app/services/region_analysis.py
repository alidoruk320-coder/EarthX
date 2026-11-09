import copy
import hashlib
import json
import logging
import math
import threading
import time
from collections import OrderedDict
from typing import Optional

import ee
from ee.ee_exception import EEException

from app.config import region_config
from app.services.trend_engine import analyze_annual_series

CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 64
LOW_COVERAGE_PIXEL_THRESHOLD = 3
MAX_YEARS_PER_REGION_BATCH = 5
MEMORY_LIMITED_REGION_VARIABLES = frozenset({
    "soil_moisture",
    "merra2_t2m",
    "merra2_evaporation",
})
TARGET_REGION_PIXELS = 1_000_000
MAX_GEOMETRY_SIMPLIFY_METERS = 1000
_cache = OrderedDict()
_cache_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _is_ee_memory_error(error: Exception) -> bool:
    return "memory limit exceeded" in str(error).lower()


def _quick_point_attempt_sizes(point_count: int) -> list[int]:
    """Return deterministic, descending sample sizes for memory retries."""
    return list(dict.fromkeys(size for size in (min(point_count, 16), 8, 4) if 0 < size <= point_count)) or [point_count]


def _quick_failure_result(variable: str, cfg: dict, geometry: dict, points: list[dict],
                          start_year: int, end_year: int, started: float,
                          failed_years: list[dict], attempted_point_counts: dict,
                          source_image_count: Optional[int]) -> dict:
    trend = analyze_annual_series([], expected_start_year=start_year, expected_end_year=end_year)
    return {
        "status": "insufficient_data",
        "region": {"type": geometry["type"]},
        "variable": variable,
        "source": cfg.get("source") or "NASA data via Google Earth Engine",
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "unit": cfg["unit"],
        "temporal_resolution": cfg.get("temporal_resolution"),
        "aggregation_label": "monthly means, then annual mean",
        "method": "sampled_boundary_filtered",
        "sample_count": min(attempted_point_counts.values(), default=0),
        "requested_sample_count": len(points),
        "sample_count_by_year": attempted_point_counts,
        "source_image_count": source_image_count,
        "failed_years": failed_years,
        "missing_years": list(range(start_year, end_year + 1)),
        "valid_pixel_count": 0,
        "valid_pixel_count_range": {"min": 0, "max": 0},
        "low_coverage_years": [],
        "raw_series": [],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "cache_hit": False,
        **trend,
    }


def polygonal_geometry(payload: dict) -> dict:
    """Extract polygon members from a GeoJSON geometry/feature collection."""
    if payload.get("type") == "Feature":
        payload = payload.get("geometry") or {}
    if payload.get("type") == "FeatureCollection":
        geometries = [feature.get("geometry") for feature in payload.get("features", [])]
        polygons = []

        def collect(geometry):
            geometry_type = (geometry or {}).get("type")
            if geometry_type == "Polygon":
                polygons.append(geometry.get("coordinates"))
            elif geometry_type == "MultiPolygon":
                polygons.extend(geometry.get("coordinates") or [])
            elif geometry_type == "GeometryCollection":
                for child in geometry.get("geometries", []):
                    collect(child)

        for geometry in geometries:
            collect(geometry)
        if not polygons:
            raise ValueError("GeoJSON collection contains no Polygon or MultiPolygon members")
        return {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1 else {
            "type": "MultiPolygon", "coordinates": polygons,
        }
    if payload.get("type") == "GeometryCollection":
        polygons = []

        def collect(geometry):
            geometry_type = geometry.get("type")
            if geometry_type == "Polygon":
                polygons.append(geometry.get("coordinates"))
            elif geometry_type == "MultiPolygon":
                polygons.extend(geometry.get("coordinates") or [])
            elif geometry_type == "GeometryCollection":
                for child in geometry.get("geometries", []):
                    collect(child)

        collect(payload)
        if not polygons:
            raise ValueError("GeoJSON GeometryCollection contains no Polygon or MultiPolygon members")
        return {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1 else {
            "type": "MultiPolygon", "coordinates": polygons,
        }
    if payload.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("geometry must be a GeoJSON Polygon, MultiPolygon, or polygon-containing GeometryCollection")
    return payload


def _normalize_geometry(payload: dict) -> dict:
    payload = polygonal_geometry(payload)
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


def _cache_key(geometry: dict, variable: str, start_year: int, end_year: int,
               method: str = "polygon_area_weighted", sample_points: Optional[list] = None) -> str:
    encoded = json.dumps(
        {
            "geometry": geometry,
            "variable": variable,
            "start_year": start_year,
            "end_year": end_year,
            "method": method,
            "sample_points": sample_points or [],
        },
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


def _scale_for_region(area_m2: float, native_scale_meters: float) -> int:
    target_scale = math.sqrt(area_m2 / TARGET_REGION_PIXELS) if area_m2 > 0 else 0
    return int(math.ceil(max(native_scale_meters, target_scale)))


def _fetch_ee_features(geojson: dict, cfg: dict, start_year: int, end_year: int) -> list:
    """Fetch polygon summaries with one main region reduction per year."""
    source_geometry = ee.Geometry(geojson)
    area_m2 = float(source_geometry.area(maxError=1).getInfo())
    native_scale = float(cfg["scale"])
    source_used = cfg["collection"]
    large_region = cfg.get("large_region")
    if cfg["variable_id"] == "ndvi" and large_region and area_m2 >= large_region["area_threshold_m2"]:
        cfg.update({
            "collection": large_region["collection"],
            "band": large_region["band"],
            "scale": large_region["scale_meters"],
            "native_scale_meters": large_region["scale_meters"],
            "nominal_cell_area_m2": large_region["scale_meters"] ** 2,
            "mask": {
                "band": large_region["quality_band"],
                "accepted_values": [0],
            },
            "temporal_resolution": large_region["temporal_resolution"],
        })
        source_used = large_region["collection"]

    scale_used = _scale_for_region(area_m2, float(cfg["scale"]))
    simplify_tolerance_m = max(
        1,
        min(scale_used * 0.25, MAX_GEOMETRY_SIMPLIFY_METERS),
    )
    geometry = source_geometry.simplify(maxError=simplify_tolerance_m)
    center = source_geometry.centroid(maxError=1)
    nominal_cell_area = float(cfg.get("nominal_cell_area_m2", native_scale ** 2))
    small_polygon = 0 < area_m2 < nominal_cell_area
    cfg["scale_used"] = scale_used
    cfg["native_scale_meters"] = float(cfg.get("native_scale_meters", native_scale))
    cfg["scale"] = scale_used
    cfg["source_used"] = source_used
    cfg["area_m2"] = area_m2
    cfg["geometry_simplify_m"] = simplify_tolerance_m
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
    # Keep the empty fallback's type and projection identical to source data.
    empty_band = collection.first().select(cfg["band"]).updateMask(ee.Image.constant(0))
    temporal_reducer = ee.Reducer.sum() if cfg["aggregate"] == "sum" else ee.Reducer.mean()
    monthly_first = cfg.get("monthly_first", False)
    tile_scale = 16

    def annual_image(year):
        year = ee.Number(year)
        annual_start = ee.Date.fromYMD(year, 1, 1)
        annual_end = annual_start.advance(1, "year")
        annual_collection = collection.filterDate(annual_start, annual_end)

        if monthly_first:
            monthly_images = []
            for month in range(1, 13):
                month_start = ee.Date.fromYMD(year, month, 1)
                month_end = month_start.advance(1, "month")
                monthly_collection = annual_collection.filterDate(month_start, month_end)
                monthly_image = ee.Algorithms.If(
                    monthly_collection.size().eq(0),
                    empty_band,
                    monthly_collection.mean().rename(cfg["band"]),
                )
                monthly_images.append(monthly_image)
            annual = ee.ImageCollection.fromImages(monthly_images).mean()
        else:
            annual = ee.Algorithms.If(
                annual_collection.size().eq(0),
                empty_band,
                annual_collection.select(cfg["band"]).mean().rename(cfg["band"]),
            )

        return annual.rename(cfg["band"]).multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))

    def annual_feature(year):
        year = ee.Number(year)
        annual = annual_image(year)
        reduce_args = {
            "geometry": geometry,
            "scale": scale_used,
            "maxPixels": 1_000_000_000,
            "tileScale": tile_scale,
        }
        if small_polygon:
            center_value = annual.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=center,
                scale=scale_used,
                maxPixels=1_000_000_000,
                tileScale=tile_scale,
            ).get(cfg["band"])
            numerator = None
            denominator = 0
            valid_pixels = 0
        elif cfg["equal_area"]:
            equal_area_stats = annual.reduceRegion(
                reducer=ee.Reducer.mean().combine(
                    reducer2=ee.Reducer.count(),
                    sharedInputs=True,
                ),
                **reduce_args,
            )
            numerator = equal_area_stats.get(f"{cfg['band']}_mean")
            denominator = 1
            valid_pixels = equal_area_stats.get(f"{cfg['band']}_count")
            center_value = None
        else:
            pixel_area = ee.Image.pixelArea().updateMask(annual.mask()).rename("pixel_area")
            weighted_image = annual.multiply(pixel_area).rename("weighted_value")
            valid_pixel_band = (
                ee.Image.constant(1)
                .updateMask(annual.mask())
                .rename("valid_pixel_count")
            )
            # Sum value × pixel area, pixel area, and valid-pixel count together.
            area_stats = (
                weighted_image
                .addBands(pixel_area)
                .addBands(valid_pixel_band)
                .reduceRegion(reducer=ee.Reducer.sum(), **reduce_args)
            )
            numerator = area_stats.get("weighted_value")
            denominator = area_stats.get("pixel_area")
            valid_pixels = area_stats.get("valid_pixel_count")
            center_value = None
        return ee.Feature(None, {
            "year": year,
            "numerator": numerator,
            "denominator": denominator,
            "center_value": center_value,
            "valid_pixel_count": valid_pixels,
            "area_m2": area_m2,
        })

    rows = []
    batch_size = (
        1 if cfg.get("variable_id") in MEMORY_LIMITED_REGION_VARIABLES
        else MAX_YEARS_PER_REGION_BATCH
    )
    for batch_start in range(start_year, end_year + 1, batch_size):
        batch_end = min(end_year, batch_start + batch_size - 1)
        batch = ee.FeatureCollection(
            ee.List.sequence(batch_start, batch_end).map(annual_feature)
        )
        try:
            rows.extend(batch.getInfo()["features"])
        except EEException as error:
            message = str(error).lower()
            if batch_start == batch_end and batch_size == 1 and "memory limit exceeded" in message:
                rows.append({"properties": {
                    "year": batch_start,
                    "numerator": None,
                    "denominator": None,
                    "center_value": None,
                    "valid_pixel_count": 0,
                    "area_m2": area_m2,
                    "year_error": str(error),
                }})
                logger.warning("Polygon annual request exceeded GEE memory: variable=%s year=%d", cfg.get("variable_id"), batch_start)
                continue
            if "too many concurrent aggregations" not in message or batch_start == batch_end:
                raise
            for year in range(batch_start, batch_end + 1):
                single_year = ee.FeatureCollection(
                    ee.List.sequence(year, year).map(annual_feature)
                )
                try:
                    rows.extend(single_year.getInfo()["features"])
                except EEException as single_error:
                    if batch_size != 1 or "memory limit exceeded" not in str(single_error).lower():
                        raise
                    rows.append({"properties": {
                        "year": year, "numerator": None, "denominator": None,
                        "center_value": None, "valid_pixel_count": 0,
                        "area_m2": area_m2, "year_error": str(single_error),
                    }})
    if not small_polygon:
        for feature in rows:
            properties = feature.get("properties", {})
            if properties.get("year_error"):
                continue
            denominator = properties.get("denominator")
            if (
                properties.get("numerator") is not None
                and denominator is not None
                and float(denominator or 0) > 0
            ):
                continue
            year = int(properties["year"])
            center_feature = ee.FeatureCollection(
                ee.List.sequence(year, year).map(
                    lambda value: ee.Feature(None, {
                        "year": value,
                        "center_value": annual_image(value).reduceRegion(
                            reducer=ee.Reducer.first(),
                            geometry=center,
                            scale=scale_used,
                            maxPixels=1_000_000_000,
                            tileScale=tile_scale,
                        ).get(cfg["band"]),
                    })
                )
            ).getInfo()["features"][0]
            properties["center_value"] = center_feature["properties"].get("center_value")
    return rows


def _fetch_server_month_features(geojson: dict, cfg: dict, start_year: int,
                                 end_year: int, batch_years: int) -> list:
    """Return monthly area summaries from one EE getInfo per year block."""
    source_geometry = ee.Geometry(geojson)
    area_m2 = float(source_geometry.area(maxError=1).getInfo())
    scale_used = _scale_for_region(area_m2, float(cfg["scale"]))
    geometry = source_geometry.simplify(maxError=min(max(scale_used * 0.25, 1), MAX_GEOMETRY_SIMPLIFY_METERS))
    cfg["area_m2"] = area_m2
    cfg["scale_used"] = scale_used
    cfg["geometry_simplify_m"] = min(max(scale_used * 0.25, 1), MAX_GEOMETRY_SIMPLIFY_METERS)
    collection = ee.ImageCollection(cfg["collection"]).filterBounds(geometry).select(cfg["band"])
    quality_mask = cfg.get("mask")
    if quality_mask:
        def apply_quality_mask(image):
            qa = image.select(quality_mask["band"]).bitwiseAnd(3)
            accepted = qa.eq(quality_mask["accepted_values"][0])
            for value in quality_mask["accepted_values"][1:]:
                accepted = accepted.Or(qa.eq(value))
            return image.updateMask(accepted)
        collection = collection.map(apply_quality_mask)
    empty = collection.first().select(cfg["band"]).updateMask(ee.Image.constant(0))
    temporal_reducer = ee.Reducer.sum() if cfg["aggregate"] == "sum" else ee.Reducer.mean()
    reducer = ee.Reducer.mean().combine(reducer2=ee.Reducer.count(), sharedInputs=True) if cfg["equal_area"] else ee.Reducer.sum()

    def month_feature(year, month):
        year, month = ee.Number(year), ee.Number(month)
        month_start = ee.Date.fromYMD(year, month, 1)
        month_collection = collection.filterDate(month_start, month_start.advance(1, "month"))
        image = month_collection.merge(ee.ImageCollection.fromImages([empty])).reduce(temporal_reducer)
        if cfg["aggregate"] != "sum":
            image = image.rename(cfg["band"])
        else:
            image = image.rename(cfg["band"])
        image = image.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
        if cfg["equal_area"]:
            stats = image.reduceRegion(
                reducer=ee.Reducer.mean().combine(reducer2=ee.Reducer.count(), sharedInputs=True),
                geometry=geometry, scale=scale_used, maxPixels=1_000_000_000, tileScale=16,
            )
            value = stats.get(f"{cfg['band']}_mean")
            count = stats.get(f"{cfg['band']}_count")
            numerator, denominator = value, 1
        else:
            pixel_area = ee.Image.pixelArea().updateMask(image.mask()).rename("pixel_area")
            valid = ee.Image.constant(1).updateMask(image.mask()).rename("valid_pixel_count")
            stats = image.multiply(pixel_area).rename("weighted_value").addBands(pixel_area).addBands(valid).reduceRegion(
                reducer=ee.Reducer.sum(), geometry=geometry, scale=scale_used,
                maxPixels=1_000_000_000, tileScale=16,
            )
            numerator = stats.get("weighted_value")
            denominator = stats.get("pixel_area")
            count = stats.get("valid_pixel_count")
        return ee.Feature(None, {
            "year": year, "month": month, "numerator": numerator,
            "denominator": denominator, "valid_pixel_count": count,
        })

    rows = []
    for batch_start in range(start_year, end_year + 1, batch_years):
        batch_end = min(end_year, batch_start + batch_years - 1)
        # Keep the result as nested Lists until both list levels are flattened.
        # Wrapping the inner monthly Features in FeatureCollections and then
        # flattening an outer FeatureCollection makes Earth Engine interpret
        # individual Features as collections for a one-year block.
        nested_features = ee.List.sequence(batch_start, batch_end).map(
            lambda year: ee.List.sequence(1, 12).map(
                lambda month: month_feature(year, month)
            )
        )
        flat_features = ee.List(nested_features).flatten().flatten()
        rows.extend(ee.FeatureCollection(flat_features).getInfo()["features"])
    return rows


def _annualize_month_features(month_features: list, cfg: dict, start_year: int, end_year: int):
    by_year = {year: {} for year in range(start_year, end_year + 1)}
    missing_months = []
    for feature in month_features:
        props = feature.get("properties", {})
        if props.get("year") is None or props.get("month") is None:
            continue
        year, month = int(props["year"]), int(props["month"])
        denominator = props.get("denominator")
        numerator = props.get("numerator")
        value = None
        if numerator is not None and (cfg["equal_area"] or (denominator is not None and float(denominator or 0) > 0)):
            value = float(numerator) if cfg["equal_area"] else float(numerator) / float(denominator)
            value = value if math.isfinite(value) else None
        by_year.setdefault(year, {})[month] = {
            "value": value,
            "count": int(props.get("valid_pixel_count") or 0),
        }
    annual_features = []
    for year, months in sorted(by_year.items()):
        for month in range(1, 13):
            if months.get(month, {}).get("value") is None:
                missing_months.append(f"{year}-{month:02d}")
        valid = [months[month] for month in range(1, 13) if months.get(month, {}).get("value") is not None]
        if len(valid) != 12:
            annual_features.append({"properties": {
                "year": year, "numerator": None, "denominator": 0,
                "center_value": None, "valid_pixel_count": 0, "area_m2": cfg.get("area_m2", 0),
            }})
            continue
        values = [month["value"] for month in valid]
        annual_value = sum(values) if cfg["aggregate"] == "sum" else sum(values) / 12
        annual_features.append({"properties": {
            "year": year, "numerator": annual_value, "denominator": 1,
            "center_value": None, "valid_pixel_count": min(month["count"] for month in valid),
            "area_m2": cfg.get("area_m2", 0),
        }})
    return annual_features, missing_months


def analyze_sampled_merra2_region(geometry_payload: dict, sample_points: list[dict],
                                  start_year: int, end_year: int,
                                  variable: str = "merra2_t2m") -> dict:
    """Memory-bounded MERRA-2 estimate at interior points, one year at a time."""
    started = time.perf_counter()
    cfg = copy.deepcopy(region_config[variable])
    if not sample_points or len(sample_points) > 16:
        raise ValueError("MERRA-2 quick mode needs between 1 and 16 boundary-filtered sample points")
    if start_year < cfg["start_year"] or end_year > cfg["latest_complete_year"] or end_year < start_year:
        raise ValueError(
            f"MERRA-2 annual data is available from {cfg['start_year']} through {cfg['latest_complete_year']}"
        )

    points = []
    for point in sample_points:
        lat, lon = float(point["lat"]), float(point["lon"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Invalid MERRA-2 sample coordinate")
        points.append({
            "lat": lat,
            "lon": lon,
            "weight": max(0.0, float(point.get("weight", math.cos(math.radians(lat))))),
        })
    geometry = _normalize_geometry(geometry_payload)
    key = _cache_key(
        geometry, variable, start_year, end_year,
        method="sampled_boundary_filtered", sample_points=points,
    )
    cached = _cache_get(key)
    if cached is not None:
        cached["cache_hit"] = True
        cached["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        return cached

    try:
        ee_points = ee.FeatureCollection([
            ee.Feature(
                ee.Geometry.Point([point["lon"], point["lat"]]),
                {"sample_id": index, "area_weight": point["weight"]},
            )
            for index, point in enumerate(points)
        ])
        sample_area = ee_points.geometry().buffer(cfg["scale"] * 2)
        collection = (
            ee.ImageCollection(cfg["collection"])
            .filterBounds(sample_area)
            .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
            .select(cfg["band"])
        )
        projection = collection.first().select(cfg["band"]).projection()
        empty = collection.first().select(cfg["band"]).updateMask(ee.Image.constant(0))

        def annual_samples(year, sample_collection=ee_points):
            year = ee.Number(year)
            monthly_images = []
            for month in range(1, 13):
                month_start = ee.Date.fromYMD(year, month, 1)
                month_collection = collection.filterDate(
                    month_start, month_start.advance(1, "month")
                ).merge(ee.ImageCollection.fromImages([empty]))
                monthly_images.append(month_collection.mean().rename(cfg["band"]))
            annual = ee.ImageCollection.fromImages(monthly_images).mean()
            annual = annual.multiply(cfg["scale_factor"]).add(cfg["offset"])
            samples = annual.sampleRegions(
                collection=sample_collection,
                properties=["sample_id", "area_weight"],
                scale=cfg["scale"],
                tileScale=16,
                geometries=False,
            )
            return samples.map(lambda feature: ee.Feature(None, {
                "year": year,
                "value": feature.get(cfg["band"]),
                "sample_id": feature.get("sample_id"),
                "area_weight": feature.get("area_weight"),
            }))

        logger.warning(
            "MERRA-2 quick request plan: variable=%s points=%d years=%d request_scope=one_year monthly_composites_per_year=12",
            variable, len(points), end_year - start_year + 1,
        )
        features = []
        failed_years = []
        attempted_point_counts = {}
        request_count = 0
        for year_value in range(start_year, end_year + 1):
            succeeded = False
            last_error = None
            for point_limit in _quick_point_attempt_sizes(len(points)):
                selected_points = points[:point_limit]
                selected_ee_points = ee.FeatureCollection([
                    ee.Feature(
                        ee.Geometry.Point([point["lon"], point["lat"]]),
                        {"sample_id": index, "area_weight": point["weight"]},
                    )
                    for index, point in enumerate(selected_points)
                ])
                try:
                    # One annual reduction per request bounds the MERRA graph.
                    request_count += 1
                    nested = ee.FeatureCollection(
                        ee.List.sequence(year_value, year_value).map(
                            lambda year: annual_samples(year, selected_ee_points)
                        )
                    ).flatten()
                    features.extend(nested.getInfo()["features"])
                    attempted_point_counts[year_value] = point_limit
                    succeeded = True
                    break
                except Exception as error:
                    last_error = error
                    if not _is_ee_memory_error(error):
                        break
                    logger.warning("MERRA-2 quick memory limit: variable=%s year=%d points=%d; retrying smaller sample", variable, year_value, point_limit)
            if not succeeded and last_error is not None:
                failed_years.append({"year": year_value, "error": str(last_error)})
                logger.error("MERRA-2 quick annual request failed: variable=%s year=%d error=%s", variable, year_value, last_error)
    except Exception as error:
        raise RuntimeError(f"MERRA-2 regional sample analysis failed: {error}") from error

    by_year = {}
    for feature in features:
        props = feature.get("properties", {})
        try:
            year = int(props["year"])
            value = float(props["value"])
            weight = float(props.get("area_weight") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(value) and math.isfinite(weight) and weight > 0):
            continue
        entry = by_year.setdefault(year, {"weighted_sum": 0.0, "weight_sum": 0.0, "count": 0})
        entry["weighted_sum"] += value * weight
        entry["weight_sum"] += weight
        entry["count"] += 1

    series = [
        {
            "date": f"{year}-01-01",
            "year": year,
            "value": values["weighted_sum"] / values["weight_sum"],
            "valid_pixel_count": values["count"],
            "low_coverage": values["count"] < LOW_COVERAGE_PIXEL_THRESHOLD,
        }
        for year, values in sorted(by_year.items())
        if values["weight_sum"] > 0
    ]
    if not series:
        if failed_years:
            failure_result = _quick_failure_result(
                variable, cfg, geometry, points, start_year, end_year, started,
                failed_years, attempted_point_counts, None,
            )
            failure_result.update({
                "retrieval_method": "monthly_means_sequential_single_year_requests",
                "earth_engine_request_count": request_count,
            })
            return failure_result
        raise ValueError(f"MERRA-2 {variable} returned no valid samples inside this boundary")

    missing_years = sorted(set(range(start_year, end_year + 1)) - {point["year"] for point in series})
    trend = analyze_annual_series(
        [(point["year"], point["value"]) for point in series],
        expected_start_year=start_year,
        expected_end_year=end_year,
    )
    counts = [point["valid_pixel_count"] for point in series]
    result = {
        "region": {"type": geometry["type"]},
        "variable": variable,
        "source": cfg.get("source") or "NASA MERRA-2 via Google Earth Engine",
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "unit": cfg["unit"],
        "temporal_resolution": f"{cfg.get('temporal_resolution', 'Hourly')}; monthly mean then annual mean",
        "aggregation_label": "monthly means, then annual mean",
        "method": "sampled_boundary_filtered",
        "sample_count": min(attempted_point_counts.values(), default=len(points)),
        "requested_sample_count": len(points),
        "sample_count_by_year": attempted_point_counts,
        "source_image_count": None,
        "retrieval_method": "monthly_means_sequential_single_year_requests",
        "earth_engine_request_count": request_count,
        "failed_years": failed_years,
        "valid_pixel_count": min(counts),
        "valid_pixel_count_range": {"min": min(counts), "max": max(counts)},
        "low_coverage_years": [point["year"] for point in series if point["low_coverage"]],
        "missing_years": missing_years,
        "raw_series": series,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "cache_hit": False,
        **trend,
    }
    if missing_years:
        result["missing_year_warning"] = (
            "Missing annual observations were excluded; Mann–Kendall significance is withheld for a gapped series."
        )
    if failed_years:
        result["failed_year_warning"] = "Some annual Earth Engine requests failed; remaining valid years were retained."
    if len(series) < 15:
        result["short_series_warning"] = (
            "Fewer than 15 annual observations are available; a longer record may be needed to detect a trend reliably."
        )
    _cache_set(key, result)
    return result


def analyze_sampled_merra2_t2m(geometry_payload: dict, sample_points: list[dict],
                               start_year: int, end_year: int) -> dict:
    """Backward-compatible wrapper for the existing T2M route."""
    return analyze_sampled_merra2_region(
        geometry_payload, sample_points, start_year, end_year, "merra2_t2m",
    )


def _build_result(features: list, geometry: dict, variable: str, cfg: dict,
                  start_year: int, end_year: int, elapsed_seconds: float) -> dict:
    rows_by_year = {}
    fallback_used = False
    failed_years = []
    nominal_cell_area = float(
        cfg.get("nominal_cell_area_m2", cfg.get("native_scale_meters", cfg["scale"]) ** 2)
    )

    for feature in features:
        props = feature.get("properties", {})
        if props.get("year") is None:
            continue
        year = int(props["year"])
        if props.get("year_error"):
            failed_years.append({"year": year, "error": props["year_error"]})
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
            # Preserve source precision: rounding here can flatten small but
            # real year-to-year changes before the trend test is calculated.
            "value": value,
            "valid_pixel_count": pixel_count,
            "low_coverage": pixel_count < LOW_COVERAGE_PIXEL_THRESHOLD,
            "method": method,
        }

    series = [rows_by_year[year] for year in sorted(rows_by_year) if rows_by_year[year] is not None]
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
        "status": "ok" if series else "insufficient_data",
        "region": {"type": geometry["type"], "area_km2": round(area_m2 / 1_000_000, 3)},
        "variable": variable,
        "source": cfg.get("source") or "Google Earth Engine",
        "dataset_id": cfg["collection"],
        "source_used": cfg.get("source_used", cfg["collection"]),
        "documentation_url": cfg.get("documentation_url"),
        "temporal_resolution": cfg.get("temporal_resolution"),
        "unit": cfg["unit"],
        "aggregation_label": aggregate_label,
        "method": method,
        "aggregate": cfg["aggregate"],
        "scale_used": cfg.get("scale_used", cfg["scale"]),
        "geometry_simplify_m": cfg.get("geometry_simplify_m"),
        "valid_pixel_count": min(pixel_counts) if pixel_counts else 0,
        "valid_pixel_count_range": {
            "min": min(pixel_counts) if pixel_counts else 0,
            "max": max(pixel_counts) if pixel_counts else 0,
        },
        "low_coverage_years": [point["year"] for point in series if point["low_coverage"]],
        "raw_series": series,
        "missing_years": missing_years,
        "failed_years": failed_years,
        "elapsed_seconds": round(elapsed_seconds, 3),
        **trend,
        "message": (
            "No valid source pixels or center-cell observations were found inside this polygon for the selected period."
            if not series else trend.get("message")
        ),
    }
    if small_polygon or fallback_used:
        result["resolution_warning"] = (
            f"The polygon is smaller than one nominal {cfg.get('native_scale_meters', cfg['scale'])} m source cell, "
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


def analyze_region(geometry_payload: dict, variable: str, start_year: int, end_year: int,
                   aggregation_mode: str = "annual", batch_years: int = 1) -> dict:
    started = time.perf_counter()
    if variable not in region_config:
        raise ValueError(f"Polygon area-weighted analysis is not configured for {variable}")
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")
    if aggregation_mode not in {"annual", "monthly_server_batch"}:
        raise ValueError("aggregation_mode must be annual or monthly_server_batch")
    if aggregation_mode == "monthly_server_batch" and variable not in MEMORY_LIMITED_REGION_VARIABLES:
        raise ValueError("monthly_server_batch is supported only for SMAP and the enabled MERRA-2 variables")
    if not 1 <= int(batch_years) <= 26:
        raise ValueError("batch_years must be between 1 and 26")

    cfg = copy.deepcopy(region_config[variable])
    if start_year < cfg["start_year"]:
        raise ValueError(f"{variable} data starts in {cfg['start_year']}")
    if end_year > cfg["latest_complete_year"]:
        raise ValueError(f"{variable} latest complete year is {cfg['latest_complete_year']}")

    requested_start_year = start_year
    first_full_year = int(cfg.get("first_full_year", cfg["start_year"]))
    partial_year_excluded = list(range(
        start_year,
        min(end_year, first_full_year - 1) + 1,
    )) if start_year < first_full_year else []
    start_year = max(start_year, first_full_year)
    geojson = _normalize_geometry(geometry_payload)
    key = _cache_key(geojson, variable, requested_start_year, end_year,
                     method=aggregation_mode, sample_points=[{"batch_years": int(batch_years)}])
    cached = _cache_get(key)
    if cached is not None:
        cached["cache_hit"] = True
        cached["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        return cached

    try:
        missing_months = []
        if start_year <= end_year and aggregation_mode == "monthly_server_batch":
            monthly = _fetch_server_month_features(geojson, cfg, start_year, end_year, int(batch_years))
            features, missing_months = _annualize_month_features(monthly, cfg, start_year, end_year)
        else:
            features = (
                _fetch_ee_features(geojson, cfg, start_year, end_year)
                if start_year <= end_year else []
            )
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
    result["partial_year_excluded"] = partial_year_excluded
    result["first_full_year"] = first_full_year
    result["aggregation_mode"] = aggregation_mode
    if aggregation_mode == "monthly_server_batch":
        result["aggregation_label"] = "monthly area summaries; annual mean of 12 complete monthly values"
        result["missing_months"] = missing_months
        result["server_batch_years"] = int(batch_years)
        if missing_months:
            result["missing_month_warning"] = "Years with one or more missing monthly observations were excluded from trend analysis."
    if result["status"] != "insufficient_data":
        _cache_set(key, result)
    return result


def _fetch_smap_sample_features(sample_points: list[dict], cfg: dict,
                                start_year: int, end_year: int) -> tuple:
    """Fetch monthly composites for all years in one compact EE response.

    The source is 3-hourly. Exporting those source observations with getRegion
    creates a very large response/graph, so reduce each month on Earth Engine
    and return only one value per month and sample point. Memory failures retry
    the whole request with fewer points, strictly sequentially.
    """
    ee_points = ee.FeatureCollection([
        ee.Feature(
            ee.Geometry.Point([point["lon"], point["lat"]]),
            {"sample_id": index, "area_weight": point["weight"]},
        )
        for index, point in enumerate(sample_points)
    ])
    # Restrict the high-cadence SMAP collection spatially before building
    # monthly composites. Without this, a handful of point samples can still
    # make Earth Engine materialize a large global 3-hourly image graph.
    sample_area = ee_points.geometry().buffer(cfg["scale"] * 2)
    collection = (
        ee.ImageCollection(cfg["collection"])
        .filterBounds(sample_area)
        .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
    )
    collection = collection.map(
        lambda image: image.select([cfg["band"]]).cast({cfg["band"]: "float"}).rename(cfg["band"])
    )
    if cfg.get("mask"):
        quality_band = cfg["mask"]["band"]
        accepted_values = cfg["mask"]["accepted_values"]

        def apply_quality_mask(image):
            quality = image.select(quality_band).bitwiseAnd(3)
            accepted = quality.eq(accepted_values[0])
            for value in accepted_values[1:]:
                accepted = accepted.Or(quality.eq(value))
            return image.updateMask(accepted)

        collection = collection.map(apply_quality_mask)
    collection = collection.select(cfg["band"])
    projection = collection.first().select(cfg["band"]).projection()
    # A masked source image preserves the exact source band type and projection
    # for months with no observations (a masked constant can cause type errors).
    empty_band = collection.first().select(cfg["band"]).updateMask(ee.Image.constant(0))
    year_count = end_year - start_year + 1
    month_count = year_count * 12
    logger.warning(
        "SMAP quick request plan: points=%d years=%d monthly_composites=%d annual_outputs=%d source_cadence=3-hourly",
        len(sample_points), year_count, month_count, year_count,
    )
    year_offsets = ee.List.sequence(0, year_count - 1)

    def make_annual(year_offset):
        year = ee.Number(start_year).add(year_offset)

        def make_month(month_number):
            month_start = ee.Date.fromYMD(year, month_number, 1)
            month_collection = collection.filterDate(month_start, month_start.advance(1, "month"))
            month_collection = month_collection.merge(ee.ImageCollection.fromImages([empty_band]))
            return month_collection.mean().rename(cfg["band"])

        monthly_images = ee.List.sequence(1, 12).map(make_month)
        annual = ee.ImageCollection.fromImages(monthly_images).mean()
        annual = annual.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
        return annual.set({"year": year})

    annual_images = year_offsets.map(make_annual)
    annual_collection = ee.ImageCollection.fromImages(annual_images)
    failed_years = []
    attempted_point_counts = {}
    last_error = None
    request_count = 0
    for point_limit in _quick_point_attempt_sizes(len(sample_points)):
        selected_points = sample_points[:point_limit]
        selected_ee_points = ee.FeatureCollection([
            ee.Feature(
                ee.Geometry.Point([point["lon"], point["lat"]]),
                {"sample_id": index, "area_weight": point["weight"]},
            )
            for index, point in enumerate(selected_points)
        ])

        def sample_year(image):
            image = ee.Image(image)
            sampled = image.sampleRegions(
                collection=selected_ee_points,
                properties=["sample_id", "area_weight"],
                scale=cfg["scale"],
                projection=projection,
                tileScale=16,
                geometries=False,
            )
            return sampled.map(lambda feature: ee.Feature(None, {
                "year": image.get("year"),
                "value": feature.get(cfg["band"]),
                "sample_id": feature.get("sample_id"),
                "area_weight": feature.get("area_weight"),
            }))

        request_count += 1
        try:
            response = ee.FeatureCollection(annual_collection.toList(year_count).map(sample_year)).flatten().getInfo()
            annual_rows = []
            for feature in response.get("features", []):
                props = feature.get("properties", {})
                try:
                    year = int(props["year"])
                    sample_id = int(props["sample_id"])
                    value = float(props["value"])
                    if not math.isfinite(value):
                        continue
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                annual_rows.append({"properties": {
                    "year": year,
                    "value": value,
                    "sample_id": sample_id,
                    "area_weight": props.get("area_weight"),
                }})
            attempted_point_counts = {year: point_limit for year in range(start_year, end_year + 1)}
            return annual_rows, failed_years, attempted_point_counts, None, request_count
        except Exception as error:
            last_error = error
            if not _is_ee_memory_error(error):
                break
            logger.warning(
                "SMAP quick memory limit: years=%d-%d points=%d; retrying smaller sample",
                start_year, end_year, point_limit,
            )

    failed_years = [{"year": year, "error": str(last_error or "SMAP request failed")}
                    for year in range(start_year, end_year + 1)]
    logger.error("SMAP quick request failed: years=%d-%d error=%s", start_year, end_year, last_error)
    return [], failed_years, attempted_point_counts, None, request_count


def analyze_sampled_soil_moisture(geometry_payload: dict, sample_points: list[dict],
                                  start_year: int, end_year: int) -> dict:
    """SMAP soil-moisture quick region mode is intentionally disabled.

    GEE data for NASA/SMAP/SPL4SMGP/008 is too memory-sensitive for sampled
    regional aggregation across multi-year windows; point analysis and a short,
    small-area polygon request are the only stable options.
    """
    raise ValueError(
        "SMAP soil moisture sampled region mode is disabled because Google Earth Engine exceeds the user memory limit for multi-year regional requests. Use a single point analysis or a much smaller/shorter polygon request."
    )
