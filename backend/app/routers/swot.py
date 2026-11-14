import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import SwotLakeAnalysisRequest
from app.services.swot_lakes import SwotCacheUnavailableError, analyze_swot_lake

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze-swot-lake")
def analyze_swot_lake_endpoint(req: SwotLakeAnalysisRequest):
    try:
        return analyze_swot_lake(req.lat, req.lon, req.start_year, req.end_year)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SwotCacheUnavailableError as error:
        logger.error("SWOT LakeSP cache unavailable: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error
