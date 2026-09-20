"""
Explore 화면용 관광지 목록/상세 조회.

itinerary_service.py는 "일정을 짜주는" 용도라 조건에 맞춰 알아서 장소를 골라주는 반면,
여기는 프론트가 지역/카테고리를 고르면 그냥 있는 그대로 목록을 보여주는 단순 조회용.
"""

from sqlalchemy.orm import Session

from app.models.place import Place, PlaceTheme


class PlaceError(Exception):
    """존재하지 않는 장소 등 조회 관련 오류"""


def list_places(
    db: Session,
    area_code: str | None = None,
    theme: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Place]:
    query = db.query(Place)
    if area_code:
        query = query.filter(Place.area_code == area_code)
    if theme:
        # place_theme로 매칭 - 장소가 여러 테마를 가진 경우도 잡히도록 (itinerary_service.py와 동일 이유)
        query = query.join(PlaceTheme, PlaceTheme.place_id == Place.id).filter(
            PlaceTheme.theme_code == theme
        )

    return query.order_by(Place.score.desc()).offset(offset).limit(limit).all()


def get_place(db: Session, place_id: int) -> Place:
    place = db.query(Place).filter(Place.id == place_id).first()
    if place is None:
        raise PlaceError("존재하지 않는 장소입니다")
    return place
