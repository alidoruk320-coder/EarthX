import logging
import math
from fastapi import APIRouter, HTTPException
from app.config import LABEL_TO_ID, VARIABLES
from app.models.schemas import PointAnalysisRequest, RegionAnalysisRequest, SeriesAnalysisRequest
from app.services.trend_engine import analyze_point
from app.services.gee_client import is_gee_initialized
from app.services.trend_engine import analyze_annual_series
from app.services.sea_level import analyze_sea_level
from app.services.region_analysis import analyze_region

router = APIRouter()
logger = logging.getLogger(__name__)


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
    result = analyze_annual_series(rows)
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
        return analyze_region(req.geometry, variable, req.start_year, req.end_year)
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
