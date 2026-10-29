from fastapi import APIRouter, HTTPException
from app.models.schemas import CascadeRequest
from app.services.trend_engine import analyze_point
from app.services.cascade_engine import (
    insufficient_data_result,
    lagged_cross_correlation,
)
from app.services.gee_client import is_gee_initialized

router = APIRouter()


@router.post("/cascade-correlation")
def cascade_correlation(req: CascadeRequest):
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    try:
        if req.end_year <= req.start_year:
            raise ValueError("end_year must be greater than start_year")
        try:
            result_a = analyze_point(req.lat, req.lon, req.variable_a, req.start_year, req.end_year)
            result_b = analyze_point(req.lat, req.lon, req.variable_b, req.start_year, req.end_year)
        except Exception as error:
            error_message = str(error).lower()
            empty_image_data = (
                "image.multiply" in error_message
                and ("no bands" in error_message or "got 0 and 1" in error_message)
            )
            if empty_image_data:
                return insufficient_data_result()
            raise

        if result_a["trend"] == "insufficient_data" or result_b["trend"] == "insufficient_data":
            return insufficient_data_result()

        correlation = lagged_cross_correlation(
            result_a["raw_series"], result_b["raw_series"], req.max_lag_years
        )
        correlation["variable_a"] = req.variable_a
        correlation["variable_b"] = req.variable_b
        return correlation

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GEE hatası: {e}")
