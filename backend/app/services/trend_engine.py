import copy
import ee
import logging
import pymannkendall as mk
import math
import time
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from app.config import VARIABLES

logger = logging.getLogger(__name__)
YEAR_CHUNKED_POINT_VARIABLES = frozenset({"merra2_evaporation"})


def _is_memory_limit_error(error: Exception) -> bool:
    return "memory limit exceeded" in str(error).lower()


def _apply_quality_masks(collection, cfg):
    quality_band = cfg.get("quality_band")
    if not quality_band:
        return collection

    def mask_low_quality(image):
        quality = image.select(quality_band)
        return image.updateMask(quality.bitwiseAnd(3).eq(0))

    return collection.map(mask_low_quality)


def _coerce_band_dtype(collection, band_name: str, dtype_name: str = "float"):
    """Normalize Earth Engine band types to avoid collection-wide schema mismatches."""
    return collection.map(
        lambda image: image.select([band_name]).cast({band_name: dtype_name}).rename(band_name)
    )


def _masked_band_template(collection, band_name: str):
    """Build an empty image with the source band's exact schema.

    A masked constant zero has the constrained pixel type ``Float<0, 0>`` in
    Earth Engine. Merging it into a collection of ordinary float SMAP images
    can make otherwise valid reductions fail the collection homogeneity check.
    Masking a source image keeps the product's band type and projection.
    """
    return collection.first().select([band_name]).updateMask(ee.Image.constant(0))


def _annualize_smap_region_table(table: list, band_name: str, start_year: int, end_year: int):
    """Parse annual SMAP composites returned by getRegion into year rows."""
    if not table:
        raise ValueError("Earth Engine getRegion returned an empty table")
    header = table[0]
    try:
        time_index = header.index("time")
        value_index = header.index(band_name)
    except ValueError as error:
        raise ValueError("Earth Engine getRegion response is missing time or soil-moisture columns") from error

    annual_values = {}
    valid_observations = 0
    for row in table[1:]:
        if len(row) <= max(time_index, value_index):
            continue
        try:
            timestamp_ms = float(row[time_index])
            value = float(row[value_index])
            if not math.isfinite(timestamp_ms) or not math.isfinite(value):
                continue
            observed = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if observed.year < start_year or observed.year > end_year:
            continue
        annual_values[observed.year] = value
        valid_observations += 1

    rows = [{
        "properties": {
            "year": year,
            "value": annual_values.get(year),
        },
    } for year in range(start_year, end_year + 1)]
    return rows, valid_observations


def _fetch_smap_get_region_features(point, cfg, start_year: int, end_year: int):
    """Build monthly then annual SMAP means on GEE; fetch annual point rows."""
    collection = (
        ee.ImageCollection(cfg["collection"])
        .filterBounds(point)
        .filterDate(
            ee.Date.fromYMD(start_year, 1, 1),
            ee.Date.fromYMD(end_year + 1, 1, 1),
        )
        .select(cfg["band"])
    )
    collection = _apply_quality_masks(collection, cfg)
    collection = _coerce_band_dtype(collection, cfg["band"], "float")
    first_image = collection.first().select(cfg["band"])
    projection = first_image.projection()
    empty_band = first_image.updateMask(ee.Image.constant(0))
    year_offsets = ee.List.sequence(0, end_year - start_year)

    def annual_composite(year_offset):
        year = ee.Number(start_year).add(year_offset)

        def monthly_composite(month_number):
            month_start = ee.Date.fromYMD(year, month_number, 1)
            month_collection = collection.filterDate(month_start, month_start.advance(1, "month"))
            composite = ee.Image(ee.Algorithms.If(
                month_collection.size().gt(0), month_collection.mean(), empty_band,
            ))
            return composite.select(cfg["band"])

        monthly_images = ee.List.sequence(1, 12).map(monthly_composite)
        annual = ee.ImageCollection.fromImages(monthly_images).mean()
        return annual.set({
            "system:time_start": ee.Date.fromYMD(year, 1, 1).millis(),
            "year": year,
        })

    annual_collection = ee.ImageCollection.fromImages(year_offsets.map(annual_composite))
    table = annual_collection.getRegion(
        point,
        scale=cfg["scale_meters"],
        crs=projection,
    ).getInfo()
    return _annualize_smap_region_table(table, cfg["band"], start_year, end_year)


def analyze_annual_series(
    series: list[tuple[int, float]],
    expected_start_year: Optional[int] = None,
    expected_end_year: Optional[int] = None,
) -> dict:
    """Compute Sen slope and Hamed–Rao MK; do not infer elapsed time across gaps."""
    clean = []
    for year, value in series:
        if year is None or value is None:
            continue
        try:
            numeric_year, numeric_value = int(year), float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(numeric_value):
            clean.append((numeric_year, numeric_value))
    clean.sort()
    # Keep the last valid annual value if duplicate years reach this boundary.
    by_year = {year: value for year, value in clean}
    clean = sorted(by_year.items())
    years = [year for year, _ in clean]
    values = [value for _, value in clean]
    slopes = [
        (values[j] - values[i]) / (years[j] - years[i])
        for i in range(len(clean)) for j in range(i + 1, len(clean))
    ]
    sen_slope = float(median(slopes)) if slopes else None
    result = {
        "trend": "insufficient_data",
        "z_score": None,
        "sen_slope": round(sen_slope, 8) if sen_slope is not None else None,
        "p_value": None,
        "significant": None,
        "test_status": "insufficient_data",
        "test_method": None,
        "observation_count": len(clean),
        "period": f"{years[0]}-{years[-1]}" if years else None,
    }
    if expected_start_year is not None and expected_end_year is not None:
        expected = set(range(expected_start_year, expected_end_year + 1))
        if expected - set(years):
            result["message"] = "Significance was withheld because one or more requested annual observations are missing."
            return result
    if len(clean) >= 2 and sen_slope == 0:
        result.update({
            "trend": "no trend",
            "z_score": 0.0,
            "p_value": 1.0,
            "significant": False,
            "test_status": "available",
            "test_method": "constant_series_exact",
            "message": "The Sen slope is zero; no monotonic direction is reported.",
        })
        return result
    if len(clean) < 8:
        result["message"] = "At least 8 annual observations are required."
        return result
    if any(right - left != 1 for left, right in zip(years, years[1:])):
        result["message"] = "Significance was withheld because annual records have gaps; Sen's slope is descriptive only."
        return result
    test = None
    test_method = "hamed_rao_modified_mann_kendall"
    try:
        test = mk.hamed_rao_modification_test(values, lag=None)
        if not (
            math.isfinite(float(test.z))
            and math.isfinite(float(test.p))
            and 0 <= float(test.p) <= 1
            and test.trend in {"increasing", "decreasing", "no trend"}
        ):
            raise ArithmeticError("Hamed–Rao Mann–Kendall returned non-finite or invalid statistics")
    except Exception as error:
        logger.warning("Hamed–Rao Mann–Kendall failed; falling back to classic test: %s", error)
        test_method = "mann_kendall_classic"
        try:
            test = mk.original_test(values)
            if not (
                math.isfinite(float(test.z))
                and math.isfinite(float(test.p))
                and 0 <= float(test.p) <= 1
                and test.trend in {"increasing", "decreasing", "no trend"}
            ):
                raise ArithmeticError("Classic Mann–Kendall returned non-finite or invalid statistics")
        except Exception as fallback_error:
            logger.exception("Classic Mann–Kendall fallback failed")
            result.update({
                "trend": "statistical_test_unavailable",
                "significant": None,
                "test_status": "unavailable",
                "message": (
                    "Mann–Kendall testing could not be calculated. "
                    f"Hamed–Rao error: {error}; classic test error: {fallback_error}"
                ),
            })
            return result
    result.update({
        "trend": test.trend,
        "z_score": round(float(test.z), 5),
        "p_value": float(test.p),
        "significant": bool(test.p < 0.05),
        "test_status": "available",
        "test_method": test_method,
    })
    return result


def _fetch_merra2_t2m_point_features(point, cfg, start_year: int, end_year: int) -> list:
    """Monthly-composite MERRA-2 hourly temperatures in bounded five-year calls."""
    collection = (
        ee.ImageCollection(cfg["collection"])
        .filterBounds(point)
        .select(cfg["band"])
    )
    projection = collection.first().select(cfg["band"]).projection()
    empty = _masked_band_template(collection, cfg["band"]).setDefaultProjection(projection)

    def annual_feature(year):
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
        value = annual.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=cfg["scale_meters"],
            maxPixels=100_000,
            tileScale=4,
        ).get(cfg["band"])
        return ee.Feature(None, {"year": year, "value": value})

    rows = []
    for batch_start in range(start_year, end_year + 1, 5):
        batch_end = min(end_year, batch_start + 4)
        batch = ee.FeatureCollection(
            ee.List.sequence(batch_start, batch_end).map(annual_feature)
        )
        rows.extend(batch.getInfo()["features"])
    return rows


def _fetch_memory_safe_point_features(
    point, cfg, start_year: int, end_year: int, batch_size: int = 5,
    continue_on_error: bool = False, return_metadata: bool = False,
):
    """Reduce high-cadence NASA collections in bounded, sequential year blocks."""
    collection = (
        ee.ImageCollection(cfg["collection"])
        .filterBounds(point.buffer(max(cfg.get("scale_meters", 1000) * 2, 10_000)))
        .select(cfg["band"])
    )
    collection = _apply_quality_masks(collection, cfg)
    collection = _coerce_band_dtype(collection, cfg["band"], "float")
    empty_band = _masked_band_template(collection, cfg["band"])

    def annual_feature(year):
        year = ee.Number(year)
        monthly_images = []
        for month in range(1, 13):
            month_start = ee.Date.fromYMD(year, month, 1)
            month_collection = collection.filterDate(
                month_start,
                month_start.advance(1, "month"),
            )
            month_collection = month_collection.merge(ee.ImageCollection.fromImages([empty_band]))
            monthly_images.append(month_collection.mean().rename(cfg["band"]))
        annual_image = ee.ImageCollection.fromImages(monthly_images).mean()
        annual_image = annual_image.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
        value = annual_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=cfg["scale_meters"],
            maxPixels=100_000,
            tileScale=4,
        ).get(cfg["band"])
        return ee.Feature(None, {"year": year, "value": value})

    rows = []
    failed_years = []
    request_count = 0
    for batch_start in range(start_year, end_year + 1, batch_size):
        batch_end = min(end_year, batch_start + batch_size - 1)
        batch = ee.FeatureCollection(
            ee.List.sequence(batch_start, batch_end).map(annual_feature)
        )
        request_count += 1
        try:
            rows.extend(batch.getInfo()["features"])
        except Exception as error:
            if (
                continue_on_error
                and batch_start == batch_end
                and batch_size == 1
                and _is_memory_limit_error(error)
            ):
                # If the one-year monthly graph still exceeds EE memory, make
                # twelve sequential month reductions and only retain a complete
                # annual mean. This trades time for bounded request memory.
                monthly_values = []
                month_error = None
                for month in range(1, 13):
                    month_start = ee.Date.fromYMD(batch_start, month, 1)
                    month_collection = collection.filterDate(
                        month_start, month_start.advance(1, "month")
                    ).merge(ee.ImageCollection.fromImages([empty_band]))
                    month_image = month_collection.mean().rename(cfg["band"])
                    month_image = month_image.multiply(cfg["scale_factor"]).add(cfg.get("offset", 0))
                    month_value = month_image.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=point,
                        scale=cfg["scale_meters"],
                        maxPixels=100_000,
                        tileScale=16,
                    ).get(cfg["band"])
                    month_feature = ee.Feature(None, {"value": month_value})
                    request_count += 1
                    try:
                        month_response = month_feature.getInfo()
                        value = month_response.get("properties", {}).get("value")
                        if value is None or not math.isfinite(float(value)):
                            month_error = f"No valid monthly value for {batch_start}-{month:02d}"
                            break
                        monthly_values.append(float(value))
                    except Exception as month_fetch_error:
                        month_error = str(month_fetch_error)
                        break
                if len(monthly_values) == 12:
                    rows.append({"properties": {
                        "year": batch_start,
                        "value": sum(monthly_values) / 12,
                    }})
                    logger.warning(
                        "MERRA high-cadence point year recovered with sequential monthly requests: variable=%s year=%d",
                        cfg.get("variable_id"), batch_start,
                    )
                    continue
                error = RuntimeError(
                    f"Annual query exceeded GEE memory; monthly fallback incomplete: {month_error or error}"
                )
            if not continue_on_error or batch_start != batch_end:
                raise
            failed_years.append({"year": batch_start, "error": str(error)})
            logger.warning(
                "High-cadence point year failed and will be omitted: variable=%s year=%d error=%s",
                cfg.get("variable_id"), batch_start, error,
            )
    if return_metadata:
        return rows, failed_years, request_count
    return rows


def analyze_point(lat: float, lon: float, variable: str,
                   start_year: int, end_year: int) -> dict:
    if variable not in VARIABLES:
        raise ValueError(f"Bilinmeyen değişken: {variable}")
    cfg = copy.deepcopy(VARIABLES[variable])
    if start_year < cfg.get("start_year", 2000):
        raise ValueError(f"{variable} verisi {cfg.get('start_year', 2000)} yılından önce mevcut değil.")
    if end_year > cfg.get("latest_complete_year", end_year):
        raise ValueError(f"{variable} için son tam yıllık veri {cfg.get('latest_complete_year')}.")
    first_full_year = int(cfg.get("first_full_year", cfg.get("start_year", 2000)))
    partial_year_excluded = list(range(
        start_year,
        min(end_year, first_full_year - 1) + 1,
    )) if start_year < first_full_year else []
    start_year = max(start_year, first_full_year)
    point = ee.Geometry.Point([lon, lat])
    retrieval_info = {}

    try:
        if start_year > end_year:
            annual_features = []
        elif variable == "merra2_t2m":
            annual_features = _fetch_merra2_t2m_point_features(
                point, cfg, start_year, end_year
            )
        elif variable == "soil_moisture":
            smap_started = time.perf_counter()
            try:
                annual_features, annual_observation_count = _fetch_smap_get_region_features(
                    point, cfg, start_year, end_year
                )
                retrieval_info = {
                    "retrieval_method": "getRegion_single_request_monthly_then_annual_mean",
                    "earth_engine_request_count": 1,
                    "annual_observation_count": annual_observation_count,
                    "retrieval_elapsed_seconds": round(time.perf_counter() - smap_started, 3),
                }
            except Exception as get_region_error:
                logger.warning(
                    "SMAP getRegion point query failed; falling back to monthly batches: %s",
                    get_region_error,
                )
                annual_features = _fetch_memory_safe_point_features(
                    point, cfg, start_year, end_year, batch_size=3
                )
                retrieval_info = {
                    "retrieval_method": "monthly_batched_fallback",
                    "earth_engine_request_count": (end_year - start_year + 3) // 3,
                    "retrieval_fallback_reason": str(get_region_error),
                    "retrieval_elapsed_seconds": round(time.perf_counter() - smap_started, 3),
                }
        elif variable in YEAR_CHUNKED_POINT_VARIABLES:
            retrieval_started = time.perf_counter()
            annual_features, failed_years, request_count = _fetch_memory_safe_point_features(
                point,
                cfg,
                start_year,
                end_year,
                batch_size=1,
                continue_on_error=True,
                return_metadata=True,
            )
            retrieval_info = {
                "retrieval_method": "monthly_means_sequential_single_year_requests",
                "earth_engine_request_count": request_count,
                "failed_years": failed_years,
                "retrieval_elapsed_seconds": round(time.perf_counter() - retrieval_started, 3),
            }
        else:
            collection = _apply_quality_masks(
                ee.ImageCollection(cfg["collection"]).filterBounds(point), cfg
            )
            collection = _coerce_band_dtype(collection, cfg["band"], "float")
            empty_band = _masked_band_template(collection, cfg["band"])

            def extract_year(year):
                year = ee.Number(year)
                start = ee.Date.fromYMD(year, 1, 1)
                end = start.advance(1, "year")
                annual_collection = collection.filterDate(start, end).select(cfg["band"])
                annual_collection = (
                    annual_collection
                    .merge(ee.ImageCollection.fromImages([empty_band]))
                )
                reducer = ee.Reducer.sum() if cfg.get("aggregation") == "sum" else ee.Reducer.mean()
                annual_image = annual_collection.reduce(reducer).rename(cfg["band"])
                annual_image = annual_image.multiply(cfg["scale_factor"]).add(cfg["offset"])
                value = annual_image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point,
                    scale=cfg["scale_meters"],
                    maxPixels=1_000_000,
                ).get(cfg["band"])
                return ee.Feature(None, {"year": year, "value": value})

            annual_features = ee.FeatureCollection(
                ee.List.sequence(start_year, end_year).map(extract_year)
            ).getInfo()["features"]
    except Exception as error:
        raise RuntimeError(
            f"Bu değişken/tarih için NASA verisi şu anda alınamıyor: {error}"
        ) from error

    series = []
    for feature in annual_features:
        properties = feature.get("properties", {})
        try:
            year = int(properties["year"])
            value = float(properties["value"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(value):
            series.append((year, value))

    trend_result = analyze_annual_series(
        series,
        expected_start_year=start_year,
        expected_end_year=end_year,
    )
    if trend_result["trend"] == "insufficient_data":
        return {
            "status": "insufficient_data",
            "region": {"lat": lat, "lon": lon},
            "variable": variable,
            "dataset_id": cfg["collection"],
            "documentation_url": cfg.get("documentation_url"),
            "temporal_resolution": cfg.get("temporal_resolution"),
            "data_source_note": cfg.get("source"),
            "unit": cfg["unit"],
            **retrieval_info,
            "period": f"{start_year}-{end_year}" if start_year <= end_year else None,
            "first_full_year": first_full_year,
            "partial_year_excluded": partial_year_excluded,
            **trend_result,
            "raw_series": [
                {"date": f"{year}-01-01", "year": year, "value": value}
                for year, value in series
            ],
            "observation_count": len(series),
            "message": (
                "Bu nokta ve dönem için geçerli yıllık gözlem bulunamadı."
                if not series
                else trend_result.get("message", "Bu nokta ve dönem için geçerli trend testi hesaplanamadı.")
            ),
        }

    return {
        "status": "ok",
        "region": {"lat": lat, "lon": lon},
        "variable": variable,
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "temporal_resolution": cfg.get("temporal_resolution"),
        "data_source_note": cfg.get("source"),
        "unit": cfg["unit"],
        **retrieval_info,
        "first_full_year": first_full_year,
        "partial_year_excluded": partial_year_excluded,
        **trend_result,
        "raw_series": [
            {"date": f"{year}-01-01", "year": year, "value": value}
            for year, value in series
        ],
    }
