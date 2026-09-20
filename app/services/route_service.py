"""
경로(동선) 계산 서비스.

최종발표 PPT(v1 알고리즘 설명)에 나온 실제 로직을 반영했어:
  "첫 방문지는 최고 점수, 이후 점수×10 − 거리(km)"
즉 순수 최단거리(nearest-neighbor)가 아니라, 각 단계에서
"점수가 높으면서도 가까운 곳"을 같이 고려하는 방식이야.
그래서 order_places_by_route()는 기존처럼 거리만 보는 버전으로 남겨두고,
order_places_by_score_and_route()를 새로 추가해서 원본 공식을 그대로 구현했어.
itinerary_service.py는 이 score 버전을 사용함.
"""

import math

from app.models.place import Place


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이의 직선거리(km)를 구하는 Haversine 공식"""
    R = 6371.0  # 지구 반지름 (km)

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def order_places_by_route(places: list[Place], start_place: Place | None = None) -> list[Place]:
    """
    주어진 장소 리스트를 방문 순서대로 정렬 (nearest-neighbor 방식).

    1) 시작점(start_place)이 없으면 리스트의 첫 장소를 시작점으로 삼음
    2) 현재 위치에서 가장 가까운 미방문 장소를 순서대로 골라나감

    참고: 장소 개수가 적을 때(하루 일정 기준 보통 4~6곳)는 이 방식으로 충분히 괜찮은 동선이 나옴.
    장소가 많아지면 2-opt 같은 개선 알고리즘을 추가로 고려.
    """
    if not places:
        return []

    remaining = places.copy()

    if start_place and start_place in remaining:
        current = start_place
        remaining.remove(current)
    else:
        current = remaining.pop(0)

    ordered = [current]

    while remaining:
        # mapx/mapy가 없는 장소는 방어적으로 아무 값이나 넣어 처리 (실무에서는 사전 필터링 권장)
        nearest = min(
            remaining,
            key=lambda p: haversine_distance_km(
                current.mapy or 0, current.mapx or 0, p.mapy or 0, p.mapx or 0
            ),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest

    return ordered


def order_places_by_score_and_route(
    places: list[Place],
    score_lookup: dict[int, float] | None = None,
    score_weight: float = 10.0,
    avoid_theme_repeat: bool = False,
) -> list[Place]:
    """
    PPT에 나온 원본 경로 계산 공식 그대로 구현한 버전.

    1) 첫 방문지: score_lookup 기준으로 가장 점수 높은 곳
    2) 이후: 남은 후보 중에서 (score * score_weight - 거리km) 값이 가장 큰 곳을 순서대로 선택
       -> 그냥 가까운 곳이 아니라, "점수도 높고 어느 정도 가까운 곳"을 우선하게 됨

    score_lookup: {place.id: score} 형태. 안 넘기면 place.score(품질 점수)를 그대로 사용.
    (itinerary_service에서 테마 매칭 점수를 따로 계산했다면 그 값을 넘겨서 쓰면 됨)

    avoid_theme_repeat: True면 "직전 장소와 같은 테마는 가능하면 피한다"는 규칙을 추가로 적용.
    PPT 개선②의 "맛집이 연속되지 않게" 규칙 - 순수 점수*거리 계산만으로는 같은 테마가
    연달아 뽑힐 수 있어서, 매 단계마다 "직전과 다른 테마인 후보들" 중에서 먼저 고르고,
    그런 후보가 하나도 없을 때만(예: 남은 게 전부 같은 테마) 전체 후보 중에서 고른다.
    """
    if not places:
        return []

    def _score(p: Place) -> float:
        if score_lookup is not None:
            return score_lookup.get(p.id, 0.0)
        return p.score or 0.0

    def _rank_key(p: Place, current: Place):
        return _score(p) * score_weight - haversine_distance_km(
            current.mapy or 0, current.mapx or 0, p.mapy or 0, p.mapx or 0
        )

    remaining = places.copy()

    # 1) 첫 방문지 = 최고 점수
    current = max(remaining, key=_score)
    remaining.remove(current)
    ordered = [current]

    # 2) 이후 = score*10 - distance 최대인 곳을 순서대로
    while remaining:
        pool = remaining
        if avoid_theme_repeat:
            different_theme = [p for p in remaining if p.theme_code != current.theme_code]
            if different_theme:
                pool = different_theme  # 직전과 다른 테마가 있으면 그중에서만 고른다

        best = max(pool, key=lambda p: _rank_key(p, current))
        ordered.append(best)
        remaining.remove(best)
        current = best

    return ordered


def total_route_distance_km(ordered_places: list[Place]) -> float:
    """정렬된 경로의 총 이동 거리(km) 계산. 일정 카드에 '총 이동거리 n km' 같은 걸 보여줄 때 사용"""
    total = 0.0
    for i in range(len(ordered_places) - 1):
        a, b = ordered_places[i], ordered_places[i + 1]
        total += haversine_distance_km(a.mapy or 0, a.mapx or 0, b.mapy or 0, b.mapx or 0)
    return round(total, 2)
