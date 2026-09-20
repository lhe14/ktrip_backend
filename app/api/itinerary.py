"""
AI 일정 추천 API 라우터.

프론트엔드(웹)에서는 이 엔드포인트 하나만 호출하면
경로까지 계산된 일자별 일정을 받을 수 있음.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.itinerary_service import generate_itinerary
from app.services.region_mapper import resolve_area_code
from app.services.theme_mapper import resolve_theme_code
from app.services.pace_mapper import resolve_places_per_day

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class PlaceOut(BaseModel):
    id: int
    title: str
    address: str | None = None
    mapx: float | None = None
    mapy: float | None = None
    first_image: str | None = None
    theme_code: str | None = None
    score: float

    class Config:
        from_attributes = True  # SQLAlchemy 모델 -> Pydantic 자동 변환


class DayPlanOut(BaseModel):
    day_index: int
    total_distance_km: float
    places: list[PlaceOut]


@router.get("", response_model=list[DayPlanOut])
def get_itinerary(
    themes: list[str] | None = Query(
        None,
        description="백엔드 테마 코드 직접 지정 (복수 선택 가능, 예: themes=food&themes=culture). "
        "넘기면 categories보다 우선.",
    ),
    categories: list[str] | None = Query(
        None,
        description="프론트 Explore 카테고리 그대로 전달 (예: categories=FOOD&categories=HALLYU)",
    ),
    days: int = Query(3, ge=1, le=14, description="여행 일수"),
    places_per_day: int | None = Query(
        None, ge=1, le=10, description="하루 방문 장소 수 직접 지정 (숙소 제외). 넘기면 pace보다 우선"
    ),
    pace: str | None = Query(None, description="프론트 페이스 그대로 전달 (예: RELAXED, BALANCED, PACKED)"),
    area_code: str | None = Query(
        None, description="TourAPI 시/도 코드 직접 지정 (예: 1=서울, 6=부산). 넘기면 region보다 우선"
    ),
    region: str | None = Query(None, description="프론트 지역명 그대로 전달 (예: SEOUL, BUSAN)"),
    db: Session = Depends(get_db),
):
    """
    예시 호출:
    - GET /itinerary?categories=FOOD&categories=CULTURE&days=3&region=SEOUL&pace=BALANCED  (프론트 이름 그대로)
    - GET /itinerary?themes=food&themes=culture&days=3&area_code=1&places_per_day=5        (백엔드 값 직접 지정)

    themes/area_code/places_per_day를 직접 넘기면 categories/region/pace는 무시됨.
    """
    resolved_themes = themes
    if not resolved_themes and categories:
        resolved_themes = [t for t in (resolve_theme_code(c) for c in categories) if t]
    if not resolved_themes:
        resolved_themes = ["food"]

    resolved_area_code = area_code or resolve_area_code(region)
    resolved_places_per_day = places_per_day or resolve_places_per_day(pace) or 5

    day_plans = generate_itinerary(
        db,
        selected_themes=resolved_themes,
        days=days,
        places_per_day=resolved_places_per_day,
        area_code=resolved_area_code,
    )
    return day_plans
