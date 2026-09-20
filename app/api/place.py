"""
관광지 목록(Explore)/상세 조회 API.

주의: nearby.py도 prefix="/places"를 쓰는데, 거기 있는 GET /places/nearby가
여기 GET /places/{place_id}보다 먼저 매칭돼야 "nearby"라는 문자열이 place_id로
잘못 해석되지 않는다. app/main.py에서 nearby 라우터를 이 라우터보다 먼저
include_router() 해야 하는 이유가 그것 - 순서 바꾸지 말 것.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.place_service import list_places, get_place, PlaceError
from app.services.region_mapper import resolve_area_code
from app.services.theme_mapper import resolve_theme_code
from app.services.score_service import get_review_stats

router = APIRouter(prefix="/places", tags=["place"])


class PlaceListOut(BaseModel):
    id: int
    title: str
    address: str | None = None
    area_code: str | None = None
    first_image: str | None = None
    theme_code: str | None = None
    score: float

    class Config:
        from_attributes = True


class PlaceDetailOut(BaseModel):
    id: int
    content_id: str
    title: str
    address: str | None = None
    area_code: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    first_image: str | None = None
    tel: str | None = None
    content_type_id: str | None = None
    theme_code: str | None = None
    overview: str | None = None
    score: float
    avg_rating: float
    review_count: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[PlaceListOut])
def get_places(
    region: str | None = Query(None, description="프론트 지역명 (예: SEOUL, BUSAN)"),
    category: str | None = Query(None, description="프론트 Explore 카테고리 (예: FOOD, HALLYU)"),
    area_code: str | None = Query(None, description="TourAPI 시/도 코드 직접 지정 (넘기면 region보다 우선)"),
    theme: str | None = Query(None, description="백엔드 theme_code 직접 지정 (넘기면 category보다 우선)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    예시 호출:
    - GET /places?region=SEOUL&category=FOOD  (프론트 이름 그대로)
    - GET /places?area_code=1&theme=food       (백엔드 코드 직접 지정)

    점수(score) 높은 순으로 정렬해서 반환.
    """
    resolved_area_code = area_code or resolve_area_code(region)
    resolved_theme = theme or resolve_theme_code(category)

    places = list_places(db, area_code=resolved_area_code, theme=resolved_theme, limit=limit, offset=offset)
    return places


@router.get("/{place_id}", response_model=PlaceDetailOut)
def get_place_detail(place_id: int, db: Session = Depends(get_db)):
    """
    예시 호출: GET /places/42

    목록 API보다 자세한 정보(상세 설명, 전화번호, 평균 평점·리뷰 개수)를 한 번에 반환.
    실제 리뷰 본문 목록이 필요하면 GET /places/{place_id}/reviews를 따로 호출할 것.
    """
    try:
        place = get_place(db, place_id)
    except PlaceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    stats = get_review_stats(db, place_id)
    return PlaceDetailOut(
        id=place.id,
        content_id=place.content_id,
        title=place.title,
        address=place.address,
        area_code=place.area_code,
        mapx=place.mapx,
        mapy=place.mapy,
        first_image=place.first_image,
        tel=place.tel,
        content_type_id=place.content_type_id,
        theme_code=place.theme_code,
        overview=place.overview,
        score=place.score,
        avg_rating=round(stats.avg_rating, 1),
        review_count=stats.review_count,
    )
