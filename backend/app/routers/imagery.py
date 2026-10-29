import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.services.visualization import get_change_tile_url, get_tile_url
from app.services.gee_client import is_gee_initialized

router = APIRouter()
logger = logging.getLogger(__name__)

CURRENT_COMPLETE_YEAR = datetime.now(timezone.utc).year - 1
LATEST_COMPLETE_YEAR = {
    "grace_tws": 2016,
    "precipitation": 2024,
    "temperature": CURRENT_COMPLETE_YEAR,
    "ndvi": CURRENT_COMPLETE_YEAR,
    "soil_moisture": CURRENT_COMPLETE_YEAR,
    "gpm_precipitation": 2024,
    "total_column_ozone": CURRENT_COMPLETE_YEAR,
    "merra2_t2m": CURRENT_COMPLETE_YEAR,
    "merra2_precipitable_water": CURRENT_COMPLETE_YEAR,
    "merra2_evaporation": CURRENT_COMPLETE_YEAR,
    "gldas_root_moisture": CURRENT_COMPLETE_YEAR,
    "gldas_surface_runoff": CURRENT_COMPLETE_YEAR,
}
FIRST_AVAILABLE_YEAR = {
    "temperature": 2000,
    "ndvi": 2000,
    "grace_tws": 2003,
    "soil_moisture": 2015,
    "precipitation": 2000,
    "gpm_precipitation": 2000,
    "total_column_ozone": 1979,
    "merra2_t2m": 1980,
    "merra2_precipitable_water": 1980,
    "merra2_evaporation": 1980,
    "gldas_root_moisture": 2000,
    "gldas_surface_runoff": 2000,
}


@router.get("/tile-url/{variable}/{year}")
def tile_url(variable: str, year: int):
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    try:
        if variable not in VARIABLES:
            raise ValueError(f"Bilinmeyen değişken: {variable}")
        first_year = FIRST_AVAILABLE_YEAR.get(variable, 2000)
        if year < first_year or year > 2100:
            raise ValueError(f"NASA {variable} verisi {first_year} yılından önce mevcut değil.")
        if variable in LATEST_COMPLETE_YEAR and year > LATEST_COMPLETE_YEAR[variable]:
            raise ValueError(
                f"NASA {variable} verisinin bu uygulamadaki son tam yılı "
                f"{LATEST_COMPLETE_YEAR[variable]}."
            )
        url = get_tile_url(variable, year)
        return {"variable": variable, "year": year, "tile_url": url}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("NASA imagery request failed for %s/%s", variable, year)
        detail = str(e)
        if not detail.startswith("Bu değişken/tarih için NASA verisi şu anda alınamıyor:"):
            detail = f"Bu değişken/tarih için NASA verisi şu anda alınamıyor: {detail}"
        raise HTTPException(status_code=503, detail=detail)


@router.get("/change-tile-url/{variable}/{start_year}/{end_year}")
def change_tile_url(variable: str, start_year: int, end_year: int):
    if not is_gee_initialized():
        raise HTTPException(status_code=503, detail="Google Earth Engine is not configured")
    try:
        if variable not in LATEST_COMPLETE_YEAR:
            raise ValueError(f"Bilinmeyen değişken: {variable}")
        if start_year < FIRST_AVAILABLE_YEAR.get(variable, 2000) or end_year - start_year < 2:
            raise ValueError("En az üç yıllık geçerli bir değişim dönemi seçin.")
        latest_year = LATEST_COMPLETE_YEAR.get(variable, CURRENT_COMPLETE_YEAR)
        if end_year > latest_year:
            raise ValueError(f"Bu değişken için son tam veri yılı {latest_year}.")
        url = get_change_tile_url(variable, start_year, end_year)
        return {
            "variable": variable,
            "start_year": start_year,
            "end_year": end_year,
            "tile_url": url,
        }
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.exception(
            "NASA change imagery request failed for %s/%s-%s",
            variable,
            start_year,
            end_year,
        )
        raise HTTPException(
            status_code=503,
            detail=f"NASA küresel değişim verisi şu anda alınamıyor: {error}",
        )
