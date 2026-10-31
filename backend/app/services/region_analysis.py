import copy
import hashlib
import json
import math
import threading
import time
from collections import OrderedDict

import ee
from ee.ee_exception import EEException

from app.config import region_config
from app.services.trend_engine import analyze_annual_series

CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 64
LOW_COVERAGE_PIXEL_THRESHOLD = 3
MAX_YEARS_PER_REGION_BATCH = 5
TARGET_REGION_PIXELS = 1_000_000
MAX_GEOMETRY_SIMPLIFY_METERS = 1000
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


def _cache_key(geometry: dict, variable: str, start_year: int, end_year: int,
               method: str = "polygon_area_weighted", sample_points: list | None = None) -> str:
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
    native_projection = collection.first().select(cfg["band"]).projection()
    empty_band = (
        ee.Image.constant(0)
        .rename(cfg["band"])
        .updateMask(ee.Image.constant(0))
        .setDefaultProjection(native_projection)
    )
    temporal_reducer = ee.Reducer.sum() if cfg["aggregate"] == "sum" else ee.Reducer.mean()
    monthly_first = cfg.get("monthly_first", False)

    def annual_image(year):
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
        return annual.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))

    def annual_feature(year):
        year = ee.Number(year)
        annual = annual_image(year)
        reduce_args = {
            "geometry": geometry,
            "scale": scale_used,
            "maxPixels": 1_000_000_000,
            "tileScale": 8,
        }
        if small_polygon:
            center_value = annual.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=center,
                scale=scale_used,
                maxPixels=1_000_000_000,
                tileScale=8,
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
    batch_size = 3 if cfg.get("variable_id") == "merra2_t2m" else MAX_YEARS_PER_REGION_BATCH
    for batch_start in range(start_year, end_year + 1, batch_size):
        batch_end = min(end_year, batch_start + batch_size - 1)
        batch = ee.FeatureCollection(
            ee.List.sequence(batch_start, batch_end).map(annual_feature)
        )
        try:
            rows.extend(batch.getInfo()["features"])
        except EEException as error:
            if (
                "too many concurrent aggregations" not in str(error).lower()
                or batch_start == batch_end
            ):
                raise
            for year in range(batch_start, batch_end + 1):
                single_year = ee.FeatureCollection(
                    ee.List.sequence(year, year).map(annual_feature)
                )
                rows.extend(single_year.getInfo()["features"])
    if not small_polygon:
        for feature in rows:
            properties = feature.get("properties", {})
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
                            tileScale=8,
                        ).get(cfg["band"]),
                    })
                )
            ).getInfo()["features"][0]
            properties["center_value"] = center_feature["properties"].get("center_value")
    return rows


def analyze_sampled_merra2_t2m(geometry_payload: dict, sample_points: list[dict],
                               start_year: int, end_year: int) -> dict:
    """Memory-bounded MERRA-2 regional estimate at up to sixteen interior points."""
    started = time.perf_counter()
    variable = "merra2_t2m"
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
            .map(lambda image: image.clip(sample_area))
            .select(cfg["band"])
        )
        projection = collection.first().select(cfg["band"]).projection()
        empty = (
            ee.Image.constant(0).rename(cfg["band"])
            .updateMask(ee.Image.constant(0))
            .setDefaultProjection(projection)
        )

        def annual_samples(year):
            year = ee.Number(year)

            def monthly_image(month):
                month_start = ee.Date.fromYMD(year, month, 1)
                month_collection = collection.filterDate(
                    month_start, month_start.advance(1, "month")
                ).merge(ee.ImageCollection.fromImages([empty]))
                return month_collection.mean().rename(cfg["band"])

            annual = ee.ImageCollection.fromImages(
                ee.List.sequence(1, 12).map(monthly_image)
            ).mean()
            annual = annual.multiply(cfg["scale_factor"]).add(cfg["offset"])
            samples = annual.sampleRegions(
                collection=ee_points,
                properties=["sample_id", "area_weight"],
                scale=cfg["scale"],
                tileScale=8,
                geometries=False,
            )
            return samples.map(lambda feature: ee.Feature(None, {
                "year": year,
                "value": feature.get(cfg["band"]),
                "sample_id": feature.get("sample_id"),
                "area_weight": feature.get("area_weight"),
            }))

        features = []
        # A short batch prevents the hourly, global MERRA collection from
        # exhausting Earth Engine's user-memory quota in one long request.
        for batch_start in range(start_year, end_year + 1, 3):
            batch_end = min(end_year, batch_start + 2)
            nested = ee.FeatureCollection(
                ee.List.sequence(batch_start, batch_end).map(annual_samples)
            ).flatten()
            features.extend(nested.getInfo()["features"])
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
        raise ValueError("MERRA-2 returned no valid temperature samples inside this boundary")

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
        "temporal_resolution": "Hourly; monthly mean then annual mean",
        "aggregation_label": "monthly means, then annual mean",
        "method": "sampled_boundary_filtered",
        "sample_count": len(points),
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
    if len(series) < 15:
        result["short_series_warning"] = (
            "Fewer than 15 annual observations are available; a longer record may be needed to detect a trend reliably."
        )
    _cache_set(key, result)
    return result


def _build_result(features: list, geometry: dict, variable: str, cfg: dict,
                  start_year: int, end_year: int, elapsed_seconds: float) -> dict:
    rows_by_year = {}
    fallback_used = False
    nominal_cell_area = float(
        cfg.get("nominal_cell_area_m2", cfg.get("native_scale_meters", cfg["scale"]) ** 2)
    )

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


def analyze_region(geometry_payload: dict, variable: str, start_year: int, end_year: int) -> dict:
    started = time.perf_counter()
    if variable not in region_config:
        raise ValueError(f"Polygon area-weighted analysis is not configured for {variable}")
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")

    cfg = copy.deepcopy(region_config[variable])
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
    if result["status"] != "insufficient_data":
        _cache_set(key, result)
    return result


def _fetch_smap_sample_features(sample_points: list[dict], cfg: dict,
                                start_year: int, end_year: int) -> list:
    """Fetch SMAP samples year-by-year to bound Earth Engine's working memory."""
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
        .map(lambda image: image.clip(sample_area))
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
    reducer = ee.Reducer.sum() if cfg["aggregate"] == "sum" else ee.Reducer.mean()
    projection = collection.first().select(cfg["band"]).projection()
    empty_band = (
        ee.Image.constant(0).rename(cfg["band"])
        .updateMask(ee.Image.constant(0))
        .setDefaultProjection(projection)
    )

    features = []
    for year_value in range(start_year, end_year + 1):
        year = ee.Number(year_value)
        year_start = ee.Date.fromYMD(year, 1, 1)
        year_end = year_start.advance(1, "year")
        year_collection = collection.filterDate(year_start, year_end)
        monthly_images = []
        for month_value in range(1, 13):
            month = ee.Number(month_value)
            month_start = ee.Date.fromYMD(year, month, 1)
            month_end = month_start.advance(1, "month")
            month_collection = year_collection.filterDate(month_start, month_end)
            month_collection = month_collection.merge(ee.ImageCollection.fromImages([empty_band]))
            monthly_images.append(month_collection.reduce(reducer).rename(cfg["band"]))

        annual = (
            ee.ImageCollection.fromImages(monthly_images)
            .mean()
            .multiply(cfg["scale_factor"])
            .add(cfg.get("offset", 0))
        )
        sampled = annual.sampleRegions(
            collection=ee_points,
            properties=["sample_id", "area_weight"],
            scale=cfg["scale"],
            tileScale=4,
            geometries=False,
        )
        annual_rows = sampled.map(lambda feature: ee.Feature(None, {
            "year": year,
            "value": feature.get(cfg["band"]),
            "sample_id": feature.get("sample_id"),
            "area_weight": feature.get("area_weight"),
        }))
        # One bounded request per annual image keeps SMAP tile reductions from
        # constructing an 11-year × 12-month graph in one user-memory context.
        features.extend(ee.FeatureCollection(annual_rows).getInfo()["features"])
    return features


def analyze_sampled_soil_moisture(geometry_payload: dict, sample_points: list[dict],
                                  start_year: int, end_year: int) -> dict:
    """Fast, boundary-filtered SMAP estimate without one full series request per point."""
    started = time.perf_counter()
    variable = "soil_moisture"
    cfg = copy.deepcopy(region_config[variable])
    if not sample_points or len(sample_points) > 16:
        raise ValueError("SMAP quick mode needs between 1 and 16 boundary-filtered sample points")
    if start_year < cfg["start_year"] or end_year > cfg["latest_complete_year"] or end_year < start_year:
        raise ValueError(
            f"SMAP annual data is available from {cfg['start_year']} through {cfg['latest_complete_year']}"
        )
    points = []
    for point in sample_points:
        lat, lon = float(point["lat"]), float(point["lon"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Invalid SMAP sample coordinate")
        weight = float(point.get("weight", math.cos(math.radians(lat))))
        points.append({"lat": lat, "lon": lon, "weight": max(0.0, weight)})

    geometry = _normalize_geometry(geometry_payload)
    key = _cache_key(
        geometry,
        variable,
        start_year,
        end_year,
        method="sampled_boundary_filtered",
        sample_points=points,
    )
    cached = _cache_get(key)
    if cached is not None:
        cached["cache_hit"] = True
        cached["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        return cached

    try:
        features = _fetch_smap_sample_features(points, cfg, start_year, end_year)
    except Exception as error:
        raise RuntimeError(f"SMAP quick regional analysis failed: {error}") from error

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
        accumulator = by_year.setdefault(year, {"weighted_sum": 0.0, "weight_sum": 0.0, "count": 0})
        accumulator["weighted_sum"] += value * weight
        accumulator["weight_sum"] += weight
        accumulator["count"] += 1

    series = []
    for year, values in sorted(by_year.items()):
        if values["weight_sum"] <= 0:
            continue
        series.append({
            "date": f"{year}-01-01",
            "year": year,
            "value": round(values["weighted_sum"] / values["weight_sum"], 6),
            "valid_pixel_count": values["count"],
            "low_coverage": values["count"] < LOW_COVERAGE_PIXEL_THRESHOLD,
        })
    if not series:
        raise ValueError("SMAP has no valid land observations at the supplied boundary sample points")

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
        "source": cfg.get("source") or "NASA SMAP L4 via Google Earth Engine",
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "unit": cfg["unit"],
        "temporal_resolution": "3-hourly; monthly mean then annual mean",
        "aggregation_label": "monthly means, then annual mean",
        "method": "sampled_boundary_filtered",
        "sample_count": len(points),
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
    if len(series) < 15:
        result["short_series_warning"] = (
            "Fewer than 15 annual observations are available; a longer record may be needed to detect a trend reliably."
        )
    _cache_set(key, result)
    return result
