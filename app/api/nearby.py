"""
위치기반 주변 관광지 검색 API.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.nearby_service import find_nearby_places

router = APIRouter(prefix="/places", tags=["nearby"])


class NearbyPlaceOut(BaseModel):
    id: int
    title: str
    address: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    first_image: str | None = None
    theme_code: str | None = None
    distance_km: float


@router.get("/nearby", response_model=list[NearbyPlaceOut])
def get_nearby_places(
    lat: float = Query(..., description="사용자 현재 위도"),
    lon: float = Query(..., description="사용자 현재 경도"),
    radius_km: float = Query(3.0, gt=0, le=50, description="검색 반경(km)"),
    limit: int = Query(20, ge=1, le=100),
    theme: str | None = Query(None, description="특정 테마만 보고 싶을 때 (예: food)"),
    db: Session = Depends(get_db),
):
    """예시 호출: GET /places/nearby?lat=37.5665&lon=126.9780&radius_km=2&theme=food"""
    results = find_nearby_places(db, lat, lon, radius_km=radius_km, limit=limit, theme=theme)
    return [
        NearbyPlaceOut(
            id=place.id,
            title=place.title,
            address=place.address,
            mapx=place.mapx,
            mapy=place.mapy,
            first_image=place.first_image,
            theme_code=place.theme_code,
            distance_km=distance,
        )
        for place, distance in results
    ]
