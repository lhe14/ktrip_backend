"""
프론트엔드(K-TRIP) Pace <-> places_per_day(하루 방문 장소 수) 매핑.

프론트 src/data/mockData.js의 PACES 상수(RELAXED/BALANCED/PACKED)를 그대로 받아서
itinerary_service.py가 쓰는 하루 방문 장소 수(숙소 제외)로 변환한다.
숫자 자체는 임의로 정한 값이라, 실제 사용해보고 팀에서 조정하면 됨.
"""

FRONTEND_PACE_TO_PLACES_PER_DAY: dict[str, int] = {
    "RELAXED": 3,   # Slow mornings, long meals, no rush.
    "BALANCED": 5,  # A steady mix of sights and downtime.
    "PACKED": 7,    # See as much as possible, every day.
}


def resolve_places_per_day(pace: str | None) -> int | None:
    """프론트 pace 값(대소문자 무관)을 places_per_day 숫자로 변환. 매핑에 없으면 None."""
    if not pace:
        return None
    return FRONTEND_PACE_TO_PLACES_PER_DAY.get(pace.strip().upper())
