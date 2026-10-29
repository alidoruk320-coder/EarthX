from fastapi import APIRouter, Query

from app.services.biodiversity import get_biodiversity_context


router = APIRouter()


@router.get("/biodiversity")
def biodiversity_context(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=50, gt=0, le=500),
):
    return get_biodiversity_context(lat, lon, radius_km)
