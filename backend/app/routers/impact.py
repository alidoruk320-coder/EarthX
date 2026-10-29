import logging

import ee
from fastapi import APIRouter, HTTPException, Query

from app.services.gee_client import is_gee_initialized

router = APIRouter()
logger = logging.getLogger(__name__)

POPULATION_DATASET = "WorldPop/GP/100m/pop_age_sex_cons_unadj"
VIIRS_DATASET = "NASA/VIIRS/002/VNP46A2"
POPULATION_YEAR = 2020
LIGHT_START_YEAR = 2014
LIGHT_END_YEAR = 2024


@router.get("/impact/exposure")
def regional_exposure(
    south: float = Query(ge=-90, le=90),
    north: float = Query(ge=-90, le=90),
    west: float = Query(ge=-180, le=180),
    east: float = Query(ge=-180, le=180),
):
    """Bounding-box population context and 2014–2024 VIIRS radiance change."""
    if south >= north or west >= east:
        raise HTTPException(status_code=422, detail="Invalid regional bounds")
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Impact analysis requires configured Google Earth Engine credentials")

    try:
        region = ee.Geometry.Rectangle([west, south, east, north], "EPSG:4326", False)
        population = (
            ee.ImageCollection(POPULATION_DATASET)
            .filterDate(f"{POPULATION_YEAR}-01-01", f"{POPULATION_YEAR + 1}-01-01")
            .select("population")
            .mosaic()
        )
        population_at_1km = population.reduceResolution(
            reducer=ee.Reducer.sum(), maxPixels=1024
        ).reproject(crs=population.projection(), scale=1000)
        population_total = population_at_1km.reduceRegion(
            reducer=ee.Reducer.sum(), geometry=region, scale=1000,
            maxPixels=1_000_000_000, bestEffort=True, tileScale=4,
        ).get("population")

        daily_lights = ee.ImageCollection(VIIRS_DATASET)

        def annual_mean(year):
            start = ee.Date.fromYMD(year, 1, 1)
            annual = daily_lights.filterDate(start, start.advance(1, "year"))

            def mask_low_quality(image):
                quality = image.select("Mandatory_Quality_Flag")
                radiance = image.select("DNB_BRDF_Corrected_NTL")
                return radiance.updateMask(quality.eq(0))

            return annual.map(mask_low_quality).mean().rename("radiance")

        baseline = annual_mean(LIGHT_START_YEAR)
        recent = annual_mean(LIGHT_END_YEAR)
        radiance_change = recent.subtract(baseline).rename("radiance_change")
        reduced = ee.Image.cat([
            baseline.rename("baseline"), recent.rename("recent"), radiance_change
        ]).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=5000,
            maxPixels=100_000_000, bestEffort=True, tileScale=4,
        )
        result = ee.Dictionary({"population_total": population_total}).combine(reduced, True).getInfo()
        if result.get("population_total") is None:
            raise ValueError("No population estimate is available for this bounding box")
        lights_available = result.get("radiance_change") is not None
        return {
            "population_total": int(round(result["population_total"])),
            "viirs_baseline_mean": result.get("baseline"),
            "viirs_recent_mean": result.get("recent"),
            "viirs_change_mean": result.get("radiance_change"),
            "viirs_unit": "nW/sr/cm²",
            "period": f"VIIRS {LIGHT_START_YEAR}–{LIGHT_END_YEAR}; WorldPop {POPULATION_YEAR}",
            "population_source": POPULATION_DATASET,
            "night_lights_source": VIIRS_DATASET if lights_available else None,
            "population_method": "Bounding-box sum, approximately 1 km scale from 100 m WorldPop grid",
            "night_lights_method": "Difference of annual area-mean radiance using high-quality NASA Black Marble observations",
            "scope": "Bounding box; exposure context, not causal impact",
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Regional exposure analysis failed")
        raise HTTPException(status_code=503, detail=f"Regional exposure analysis failed: {error}") from error
