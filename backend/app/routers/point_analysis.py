import logging
import math
from fastapi import APIRouter, HTTPException, Query
import ee
from app.config import LABEL_TO_ID, VARIABLES
from app.models.schemas import PointAnalysisRequest, RegionAnalysisRequest, SeriesAnalysisRequest
from app.services.trend_engine import analyze_point
from app.services.gee_client import is_gee_initialized
from app.services.trend_engine import analyze_annual_series
from app.services.sea_level import analyze_sea_level, check_sea_level_availability
from app.services.region_analysis import (
    analyze_region,
    analyze_sampled_merra2_t2m,
    analyze_sampled_soil_moisture,
    polygonal_geometry,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/region-boundary")
def region_boundary_endpoint(
    name: str = Query(min_length=1, max_length=160),
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    country_code: str = Query(default="", max_length=2),
    level: int = Query(default=1, ge=0, le=2),
):
    """Return an administrative GAUL boundary when OSM search has no polygon."""
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    try:
        point = ee.Geometry.Point([lon, lat])
        levels = [0] if level == 0 else list(dict.fromkeys([level, 1, 2]))
        selected = None
        selected_level = None
        candidates = []
        for candidate_level in levels:
            if candidate_level in (1, 2):
                candidates.append((f"FAO/GAUL/2025/level{candidate_level}", candidate_level, "GAUL0_NAME", "GAUL1_NAME", "GAUL2_NAME"))
                candidates.append((f"FAO/GAUL_SIMPLIFIED_500m/2025/level{candidate_level}", candidate_level, "GAUL0_NAME", "GAUL1_NAME", "GAUL2_NAME"))
            candidates.extend([
                (f"FAO/GAUL/2015/level{candidate_level}", candidate_level, "ADM0_NAME", "ADM1_NAME", "ADM2_NAME"),
            ])
        selected_source = None
        errors = []
        for collection_id, candidate_level, country_property, level1_property, level2_property in candidates:
            try:
                collection = ee.FeatureCollection(collection_id)
                if candidate_level == 0:
                    named = collection.filter(ee.Filter.stringContains(
                        country_property, name.split(",")[0]
                    ))
                    feature = ee.Feature(named.first()).getInfo() if named.size().getInfo() else None
                    if not feature:
                        feature = ee.Feature(collection.filterBounds(point).first()).getInfo()
                else:
                    matches = collection.filterBounds(point)
                    feature = ee.Feature(matches.first()).getInfo() if matches.size().getInfo() else None
                if feature and feature.get("geometry"):
                    selected, selected_level = feature, candidate_level
                    selected_source = collection_id
                    break
            except Exception as error:
                errors.append(f"{collection_id}: {error}")
        if not selected:
            reason = "; ".join(errors[-4:])
            raise ValueError(
                "No GAUL administrative polygon contains the search point"
                + (f"; attempted current GAUL and compatibility sources: {reason}" if reason else "")
            )

        geometry = polygonal_geometry(selected["geometry"])
        coordinates = geometry.get("coordinates", [])
        flat = []
        def walk(value):
            if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
                isinstance(part, (int, float)) for part in value[:2]
            ):
                flat.append((float(value[0]), float(value[1])))
            elif isinstance(value, (list, tuple)):
                for child in value:
                    walk(child)
        walk(coordinates)
        if not flat:
            raise ValueError("GAUL polygon has no coordinates")
        longitudes, latitudes = zip(*flat)
        bounds = [min(latitudes), max(latitudes), min(longitudes), max(longitudes)]
        props = selected.get("properties", {})
        return {
            "geometry": geometry,
            "boundingbox": [str(value) for value in bounds],
            "source": f"{selected_source} (Google Earth Engine)",
            "region_type": "country" if selected_level == 0 else "administrative area",
            "region_name": props.get("GAUL0_NAME") or props.get("ADM0_NAME") if selected_level == 0 else (
                props.get("GAUL2_NAME") or props.get("ADM2_NAME")
                or props.get("GAUL1_NAME") or props.get("ADM1_NAME")
                or props.get("GAUL0_NAME") or props.get("ADM0_NAME")
            ),
            "country_code_hint": country_code or None,
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("GAUL boundary lookup failed for %s", name)
        raise HTTPException(status_code=404, detail=f"Administrative boundary unavailable: {error}") from error


@router.post("/analyze-series")
def analyze_series_endpoint(req: SeriesAnalysisRequest):
    try:
        rows = []
        for row in req.series:
            if row.get("year") is None or row.get("value") is None:
                continue
            year, value = int(row["year"]), float(row["value"])
            if math.isfinite(value):
                rows.append((year, value))
        rows.sort(key=lambda item: item[0])
    except (TypeError, ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail="Series must contain numeric year/value pairs") from error
    rows = [(year, value) for year, value in rows if req.start_year <= year <= req.end_year]
    result = analyze_annual_series(
        rows,
        expected_start_year=req.start_year,
        expected_end_year=req.end_year,
    )
    return {**result, "unit": req.unit, "dataset_id": req.dataset_id,
            "raw_series": [{"year": y, "value": v} for y, v in rows]}


@router.post("/analyze-point")
def analyze_point_endpoint(req: PointAnalysisRequest):
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    try:
        if req.end_year <= req.start_year:
            raise ValueError("end_year must be greater than start_year")
        variable = LABEL_TO_ID.get(req.variable, req.variable)
        if variable not in VARIABLES:
            raise ValueError(f"Bilinmeyen değişken: {req.variable}")
        return analyze_point(
            lat=req.lat,
            lon=req.lon,
            variable=variable,
            start_year=req.start_year,
            end_year=req.end_year,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("NASA point analysis failed for %s", req.variable)
        detail = str(e)
        if not detail.startswith("Bu değişken/tarih için NASA verisi şu anda alınamıyor:"):
            detail = f"Bu değişken/tarih için NASA verisi şu anda alınamıyor: {detail}"
        raise HTTPException(status_code=503, detail=detail)


@router.post("/analyze-region")
def analyze_region_endpoint(req: RegionAnalysisRequest):
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    variable = LABEL_TO_ID.get(req.variable, req.variable)
    try:
        if req.end_year < req.start_year:
            raise ValueError("end_year must be greater than or equal to start_year")
        if req.sampling_method == "sampled_boundary_filtered":
            if variable == "soil_moisture":
                return analyze_sampled_soil_moisture(
                    req.geometry, req.sample_points, req.start_year, req.end_year,
                )
            if variable == "merra2_t2m":
                return analyze_sampled_merra2_t2m(
                    req.geometry, req.sample_points, req.start_year, req.end_year,
                )
            raise ValueError(
                "Sampled-region endpoint mode is currently enabled only for SMAP soil moisture and MERRA-2 air temperature"
            )
        result = analyze_region(req.geometry, variable, req.start_year, req.end_year)
        if req.series_only:
            return {
                "status": result.get("status"),
                "variable": result.get("variable"),
                "series_only": True,
                "raw_series": result.get("raw_series", []),
                "missing_years": result.get("missing_years", []),
                "partial_year_excluded": result.get("partial_year_excluded", []),
                "elapsed_seconds": result.get("elapsed_seconds"),
            }
        return result
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("NASA polygon analysis failed for %s", variable)
        raise HTTPException(status_code=503, detail=f"Regional NASA data unavailable: {error}") from error


@router.post("/analyze-sea-level")
def analyze_sea_level_endpoint(req: PointAnalysisRequest):
    try:
        if req.end_year <= req.start_year:
            raise ValueError("end_year must be greater than start_year")
        return analyze_sea_level(req.lat, req.lon, req.start_year, req.end_year)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("NASA sea-level analysis failed at %.3f, %.3f", req.lat, req.lon)
        raise HTTPException(status_code=503, detail=f"NASA sea-level data unavailable: {error}") from error


@router.get("/sea-level-availability")
def sea_level_availability_endpoint(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
):
    try:
        return check_sea_level_availability(lat, lon)
    except Exception as error:
        logger.exception("Sea-level availability check failed at %.3f, %.3f", lat, lon)
        raise HTTPException(status_code=503, detail=f"Sea-level availability could not be checked: {error}") from error
