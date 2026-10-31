import copy
import ee
import logging
import pymannkendall as mk
import math
from statistics import median
from app.config import VARIABLES

logger = logging.getLogger(__name__)


def _apply_quality_masks(collection, cfg):
    quality_band = cfg.get("quality_band")
    if not quality_band:
        return collection

    def mask_low_quality(image):
        quality = image.select(quality_band)
        return image.updateMask(quality.bitwiseAnd(3).eq(0))

    return collection.map(mask_low_quality)


def analyze_annual_series(
    series: list[tuple[int, float]],
    expected_start_year: int | None = None,
    expected_end_year: int | None = None,
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
    empty = (
        ee.Image.constant(0).rename(cfg["band"])
        .updateMask(ee.Image.constant(0))
        .setDefaultProjection(projection)
    )

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


def analyze_point(lat: float, lon: float, variable: str,
                   start_year: int, end_year: int) -> dict:
    if variable not in VARIABLES:
        raise ValueError(f"Bilinmeyen değişken: {variable}")

    cfg = copy.deepcopy(VARIABLES[variable])
    if start_year < cfg.get("start_year", 2000):
        raise ValueError(f"{variable} verisi {cfg.get('start_year', 2000)} yılından önce mevcut değil.")
    if end_year > cfg.get("latest_complete_year", end_year):
        raise ValueError(f"{variable} için son tam yıllık veri {cfg.get('latest_complete_year')}.")
    point = ee.Geometry.Point([lon, lat])

    try:
        if variable == "merra2_t2m":
            annual_features = _fetch_merra2_t2m_point_features(
                point, cfg, start_year, end_year
            )
        else:
            collection = _apply_quality_masks(
                ee.ImageCollection(cfg["collection"]).filterBounds(point), cfg
            )

            def extract_year(year):
                year = ee.Number(year)
                start = ee.Date.fromYMD(year, 1, 1)
                end = start.advance(1, "year")
                annual_collection = collection.filterDate(start, end).select(cfg["band"])
                empty_band = ee.Image.constant(0).rename(cfg["band"]).updateMask(ee.Image.constant(0))
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

    trend_result = analyze_annual_series(series)
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
            "period": f"{start_year}-{end_year}",
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
        **trend_result,
        "raw_series": [
            {"date": f"{year}-01-01", "year": year, "value": value}
            for year, value in series
        ],
    }
