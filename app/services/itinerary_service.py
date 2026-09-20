"""
AI 일정 추천 메인 서비스.

최종발표 PPT(23~27번 슬라이드)에 나온 실제 알고리즘 진화 과정을 최대한 그대로 반영했어:

  v1: 필터링 -> 매칭점수 -> 최적경로(점수*10 - 거리) -> 일정분배
  개선①: 카테고리(맛집/카페/쇼핑/관광지) 도입, 숙박은 후보에서 빼고 마지막에만 배치,
          테마별 데이터 개수 편차(예: 맛집 1821 vs 자연 302) 때문에 테마별로 "균등 추출"
  개선②: 하루 안에서 먼저 테마를 배분한 다음 그 안에서만 동선 최적화 (전체 균등 후
          최적화하면 특정 요일에 테마가 몰리는 문제가 있었음). 맛집 연속 배치 금지
  개선③: 선택한 테마 조합에 따라 맛집 개수 차등(맛집만/맛집+기타), 한류는 음식슬롯/
          일반슬롯 분리, 데이터 부족한 지역은 used-id로 중복 방지하고 모자라면
          "빈 슬롯"으로 두고 억지로 채우지 않음

TourAPI 기반으로 옮기면서 못 살린 부분(한류 음식/일반 슬롯 분리 등)은 코드에 TODO로
표시해뒀어 - theme_mapper.py 상단 설명 참고.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.place import Place, PlaceTheme
from app.services.route_service import order_places_by_score_and_route, total_route_distance_km
from app.services.theme_mapper import FOOD_THEME, LODGING_THEME, HALLYU_THEME

# 맛집만 선택했을 때 자동으로 채우는 테마 (PPT: "맛집만 선택 -> 맛집3 + 관광지 자동2")
AUTO_FILL_THEME = "sightseeing"


@dataclass
class DayPlan:
    day_index: int
    places: list[Place] = field(default_factory=list)
    total_distance_km: float = 0.0


# ---------------------------------------------------------------------------
# 1) 하루 테마 슬롯 계획 (개선①③: 테마 조합에 따른 맛집 개수 차등 + 균등 배분)
# ---------------------------------------------------------------------------

def _split_evenly(themes: list[str], total: int) -> dict[str, int]:
    """total개를 themes에 최대한 고르게 나눠준다 (나머지는 앞쪽 테마부터 +1)"""
    if not themes or total <= 0:
        return {}

    base = total // len(themes)
    remainder = total % len(themes)

    counts: dict[str, int] = {}
    for i, theme in enumerate(themes):
        counts[theme] = base + (1 if i < remainder else 0)
    return counts


def _interleave(counts: dict[str, int]) -> list[str]:
    """
    {theme: 개수} 를 라운드로빈으로 섞어서 같은 테마가 되도록 연속되지 않게 나열.
    (개선②: "맛집이 연속되지 않게" 규칙을 여기서 구현)
    """
    remaining = dict(counts)
    order = list(remaining.keys())
    slots: list[str] = []

    while any(v > 0 for v in remaining.values()):
        for theme in order:
            if remaining[theme] > 0:
                slots.append(theme)
                remaining[theme] -= 1

    return slots


def _slot_plan(selected_themes: list[str], target_size: int) -> list[str]:
    """
    사용자가 고른 테마 조합을 보고 하루치 테마 슬롯 순서를 정한다.
    target_size=5 기준으로 PPT의 실제 수치(맛집만: 3+2, 맛집+기타: 2+3)를 그대로 쓰고,
    다른 target_size가 들어오면 같은 비율로 스케일링한다.
    """
    themes = list(dict.fromkeys(selected_themes)) if selected_themes else [AUTO_FILL_THEME]

    if themes == [FOOD_THEME]:
        # 맛집만 선택 -> 맛집 위주 + 관광지 자동 채움
        food_n = round(target_size * 3 / 5)
        counts = {FOOD_THEME: food_n, AUTO_FILL_THEME: max(target_size - food_n, 0)}

    elif FOOD_THEME in themes and len(themes) > 1:
        # 맛집 + 기타 테마 -> 맛집 비중을 줄이고 나머지 테마에 배분
        food_n = round(target_size * 2 / 5)
        other = [t for t in themes if t != FOOD_THEME]
        counts = {FOOD_THEME: food_n}
        counts.update(_split_evenly(other, max(target_size - food_n, 0)))

    elif themes == [HALLYU_THEME]:
        # TODO: PPT 원본은 "한류 음식 슬롯 2 + 한류 일반 슬롯 3"으로 분리했는데,
        # 지금 Place는 테마 하나만 가지고 있어서 "한류이면서 음식"을 따로 구분 못 함.
        # 우선은 한류 테마 하나로 target_size만큼 채우고, 다중 태그 구조로 확장하면
        # is_food_theme(place.theme_code)로 나눠서 이 부분을 개선①③처럼 분리하면 됨.
        counts = {HALLYU_THEME: target_size}

    else:
        # 맛집도 한류도 아닌 조합 (예: 자연+역사) -> 자동 맛집 채움 없이 균등 배분
        counts = _split_evenly(themes, target_size)

    return _interleave(counts)


# ---------------------------------------------------------------------------
# 2) 슬롯별 후보 조회 (개선①: 테마별 균등 추출 + 개선③: used-id로 중복 방지)
# ---------------------------------------------------------------------------

def _base_theme_query(db: Session, theme: str, area_code: str | None):
    query = (
        db.query(Place)
        .join(PlaceTheme, PlaceTheme.place_id == Place.id)
        .filter(PlaceTheme.theme_code == theme)
    )
    if area_code:
        query = query.filter(Place.area_code == area_code)
    return query


def _query_fresh_candidate(
    db: Session, theme: str, area_code: str | None, exclude_ids: set[int]
) -> Place | None:
    """해당 테마에서 점수가 가장 높은 미사용 장소 1곳을 가져온다. 없으면 None.

    place_theme를 통해 매칭하므로, 장소가 여러 테마를 가진 경우(예: culture이면서 hallyu)
    어느 테마로 찾아도 후보에 걸린다 - place.theme_code(주 테마) 하나만 보던 예전 방식보다
    한류처럼 AI가 "부가 태그"로 붙인 테마를 더 잘 잡아낸다.
    """
    query = _base_theme_query(db, theme, area_code)
    if exclude_ids:
        query = query.filter(~Place.id.in_(exclude_ids))
    return query.order_by(Place.score.desc()).first()


def _query_reuse_candidate(
    db: Session,
    theme: str,
    area_code: str | None,
    exclude_ids: set[int],
    last_used_day: dict[int, int],
) -> Place | None:
    """새 장소가 하나도 없을 때 재사용할 후보를 고른다.

    "가장 오래 전에 방문한 곳" 우선(동점이면 점수 높은 곳)으로 고른다 - 그냥 점수 1등을
    매번 다시 뽑으면 데이터 적은 지역/테마는 최근 며칠과 완전히 똑같은 조합이 반복돼서
    복붙한 일정처럼 보인다. 있는 장소를 돌아가며 재방문하게 해서 그나마 자연스럽게 만든다.
    """
    query = _base_theme_query(db, theme, area_code)
    if exclude_ids:
        query = query.filter(~Place.id.in_(exclude_ids))
    candidates = query.all()
    if not candidates:
        return None
    return min(candidates, key=lambda p: (last_used_day.get(p.id, 0), -(p.score or 0.0)))


def _pick_places_for_day(
    db: Session,
    slot_plan: list[str],
    area_code: str | None,
    used_ids: set[int],
    last_used_day: dict[int, int],
) -> list[Place]:
    """
    슬롯 계획대로 하루치 장소를 뽑는다. 슬롯마다 아래 순서로 시도해서, 웬만하면
    "정말 여행 일정처럼" 채워지게 한다 (완전히 못 채우는 경우에만 빈 슬롯):

      1) 원래 슬롯 테마 + 새 장소 (이전 날짜에서 안 쓴 곳)
      2) 그 테마로 새 장소가 없으면 -> 관광지/랜드마크(AUTO_FILL_THEME)로 유연하게 대체
         (예: 지방 소도시에서 한류 태그 장소가 이틀 만에 바닥나면, 3일 차부터 억지로
         같은 한류 장소를 또 넣기보다 그 지역 유적지/랜드마크를 자연스럽게 끼워 넣는 게
         실제 여행 일정에 가깝다)
      3) 그것도 없으면 원래 테마를 재사용 - 가장 오래 전에 쓴 곳부터 순환
      4) 그것도 없으면 관광지/랜드마크를 재사용 - 마찬가지로 순환
      5) 그래도 없으면 이 지역엔 정말 대체할 장소가 없다는 뜻 - 빈 슬롯
    """
    day_places: list[Place] = []
    day_used_ids: set[int] = set()  # 하루 안에서는 같은 장소가 두 번 뽑히지 않도록 항상 강제

    for theme in slot_plan:
        soft_exclude = day_used_ids | used_ids

        candidate = _query_fresh_candidate(db, theme, area_code, soft_exclude)
        if candidate is None and theme != AUTO_FILL_THEME:
            candidate = _query_fresh_candidate(db, AUTO_FILL_THEME, area_code, soft_exclude)
        if candidate is None:
            candidate = _query_reuse_candidate(db, theme, area_code, day_used_ids, last_used_day)
        if candidate is None and theme != AUTO_FILL_THEME:
            candidate = _query_reuse_candidate(db, AUTO_FILL_THEME, area_code, day_used_ids, last_used_day)
        if candidate is None:
            continue  # 이 지역엔 대체할 장소도 없음 - 빈 슬롯

        day_places.append(candidate)
        day_used_ids.add(candidate.id)

    return day_places


# ---------------------------------------------------------------------------
# 3) 숙소 배치 (개선①: 숙박은 후보에서 제외하고 마지막에만, 마지막 날엔 배치 안 함)
# ---------------------------------------------------------------------------

def _get_lodging_place(db: Session, area_code: str | None) -> Place | None:
    """
    지역 내 점수 가장 높은 숙소 1곳을 가져와서 전체 일정 동안 반복 사용한다.

    TODO: PPT 원본은 "단일 지역(서울/부산)은 숙소 1곳, 포괄 지역(전남/경기)은 일정에 맞춰
    여러 숙소"였음. 지금은 area_code 하나만 받는 구조라 숙소 1곳 재사용으로 단순화했고,
    여러 지역(area_code 리스트)을 넘길 수 있게 확장하면 지역이 바뀔 때마다 숙소도
    다시 조회하도록 고치면 됨.
    """
    query = db.query(Place).filter(Place.theme_code == LODGING_THEME)
    if area_code:
        query = query.filter(Place.area_code == area_code)
    return query.order_by(Place.score.desc()).first()


# ---------------------------------------------------------------------------
# 4) 최종 일정 생성
# ---------------------------------------------------------------------------

def generate_itinerary(
    db: Session,
    selected_themes: list[str],
    days: int = 3,
    places_per_day: int = 5,
    area_code: str | None = None,
) -> list[DayPlan]:
    """
    최종 일정 생성 함수. FastAPI 라우터(api/itinerary.py)에서 이 함수를 호출한다.

    selected_themes: 사용자가 고른 테마 조합, 예: ["food"], ["food", "nature"], ["hallyu"]
    area_code: TourAPI 시/도 코드. None이면 전체 지역 대상.

    흐름 (PPT 최종 로직 그대로):
      1) 선택한 테마 조합으로 하루 슬롯 계획 수립 (맛집 개수 차등 등)
      2) 슬롯마다 점수 높은 미사용 장소를 뽑음 (부족하면 빈 슬롯 유지)
      3) 뽑힌 장소를 "점수*10 - 거리" 기준으로 동선 정렬
      4) 마지막 날이 아니면 숙소를 맨 뒤에 붙임
      5) 다음 날에는 이미 쓴 장소를 제외하고 반복 (숙소는 반복 사용 가능하므로 제외 안 함)
    """
    used_ids: set[int] = set()
    last_used_day: dict[int, int] = {}  # place.id -> 마지막으로 쓰인 day_index (재사용 순환용)
    day_plans: list[DayPlan] = []

    slot_plan = _slot_plan(selected_themes, places_per_day)
    lodging_place = _get_lodging_place(db, area_code)

    for day_index in range(1, days + 1):
        raw_places = _pick_places_for_day(db, slot_plan, area_code, used_ids, last_used_day)

        if not raw_places:
            # _pick_places_for_day가 재사용까지 허용했는데도 하나도 못 뽑았다는 뜻 =
            # 이 지역/테마 조합엔 장소가 아예 없음. (단순히 며칠치를 다 써버린 것뿐이라면
            # _query_top_candidate의 soft_exclude 재사용 폴백으로 계속 채워지므로 여기까지
            # 안 옴 - 그래서 더 이상 미룰 이유 없이 여기서 중단)
            break

        ordered_places = order_places_by_score_and_route(raw_places, avoid_theme_repeat=True)

        is_last_day = day_index == days
        if lodging_place and not is_last_day:
            ordered_places = ordered_places + [lodging_place]

        distance = total_route_distance_km(ordered_places)
        day_plans.append(DayPlan(day_index=day_index, places=ordered_places, total_distance_km=distance))

        # 숙소는 반복 사용 가능해야 하므로 used_ids/last_used_day에는 안 넣음
        used_ids.update(p.id for p in raw_places)
        last_used_day.update({p.id: day_index for p in raw_places})

    return day_plans
