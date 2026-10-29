import ee
import pymannkendall as mk
import math
from statistics import median
from app.config import VARIABLES


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
        "sen_slope": round(sen_slope, 5) if sen_slope is not None else None,
        "p_value": None,
        "significant": False,
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
            "message": "The Sen slope is zero; no monotonic direction is reported.",
        })
        return result
    if len(clean) < 8:
        result["message"] = "At least 8 annual observations are required."
        return result
    if any(right - left != 1 for left, right in zip(years, years[1:])):
        result["message"] = "Significance was withheld because annual records have gaps; Sen's slope is descriptive only."
        return result
    test = mk.hamed_rao_modification_test(values, lag=None)
    result.update({
        "trend": test.trend,
        "z_score": round(float(test.z), 5),
        "p_value": float(test.p),
        "significant": bool(test.p < 0.05),
    })
    return result


def analyze_point(lat: float, lon: float, variable: str,
                   start_year: int, end_year: int) -> dict:
    if variable not in VARIABLES:
        raise ValueError(f"Bilinmeyen değişken: {variable}")

    cfg = VARIABLES[variable]
    if start_year < cfg.get("start_year", 2000):
        raise ValueError(f"{variable} verisi {cfg.get('start_year', 2000)} yılından önce mevcut değil.")
    if end_year > cfg.get("latest_complete_year", end_year):
        raise ValueError(f"{variable} için son tam yıllık veri {cfg.get('latest_complete_year')}.")
    point = ee.Geometry.Point([lon, lat])

    try:
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

    series = [
        (int(feature["properties"]["year"]), float(feature["properties"]["value"]))
        for feature in annual_features
        if feature["properties"].get("value") is not None
    ]

    trend_result = analyze_annual_series(series)
    if trend_result["trend"] == "insufficient_data":
        return {
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
            "message": trend_result.get("message", "Bu nokta ve dönem için geçerli trend testi hesaplanamadı."),
        }

    return {
        "region": {"lat": lat, "lon": lon},
        "variable": variable,
        "dataset_id": cfg["collection"],
        "documentation_url": cfg.get("documentation_url"),
        "temporal_resolution": cfg.get("temporal_resolution"),
        "data_source_note": cfg.get("source"),
        "unit": cfg["unit"],
        **trend_result,
        "raw_series": [
            {"date": f"{year}-01-01", "year": year, "value": round(value, 4)}
            for year, value in series
        ],
    }
