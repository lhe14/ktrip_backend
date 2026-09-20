"""
지도 · 위치기반 주변 관광지 추천. PPT 2번 기능
("사용자 위치 기반 주변 관광지 추천 및 지도 기능 - 외부 API 활용")에 해당.

지금은 sync_tourapi.py로 이미 적재해둔 자체 DB(Place)를 기준으로 Haversine 거리 계산해서
가까운 순으로 반환하는 방식으로 구현했어 - TourAPI 서비스키 없이도 sqlite로 바로 테스트 가능함.

나중에 실시간성이 더 중요해지면 tourapi_client.fetch_location_based_list()로 바꿔서
TourAPI locationBasedList2를 직접 호출하는 버전으로 교체할 수 있음 (이미 구현되어 있음).
그 경우 매 요청마다 외부 API를 호출하게 되니 캐싱이나 호출 빈도 제한을 같이 고려해야 함.
"""

from sqlalchemy.orm import Session

from app.models.place import Place, PlaceTheme
from app.services.route_service import haversine_distance_km


def find_nearby_places(
    db: Session,
    lat: float,
    lon: float,
    radius_km: float = 3.0,
    limit: int = 20,
    theme: str | None = None,
) -> list[tuple[Place, float]]:
    """
    (lat, lon) 기준 반경 radius_km 안에 있는 장소를 가까운 순으로 반환.
    반환값: [(place, distance_km), ...]
    """
    query = db.query(Place).filter(Place.mapx.isnot(None), Place.mapy.isnot(None))
    if theme:
        # place_theme로 매칭 - 장소가 여러 테마를 가진 경우도 잡히도록 (itinerary_service.py와 동일 이유)
        query = query.join(PlaceTheme, PlaceTheme.place_id == Place.id).filter(
            PlaceTheme.theme_code == theme
        )

    candidates = query.all()

    scored: list[tuple[Place, float]] = []
    for place in candidates:
        distance = haversine_distance_km(lat, lon, place.mapy, place.mapx)
        if distance <= radius_km:
            scored.append((place, round(distance, 3)))

    scored.sort(key=lambda pair: pair[1])
    return scored[:limit]
