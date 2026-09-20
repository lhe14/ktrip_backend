"""
TourAPI 분류 코드 -> 기존 알고리즘이 쓰던 테마 라벨 변환.

기존 엑셀 버전에서는 사람이 직접 각 장소에 테마를 태깅했다면,
여기서는 TourAPI가 제공하는 contentTypeId/cat1/cat2/cat3 코드를 보고
자동으로 테마를 정해준다.

가장 간단한 방법: content_type_id만 보고 큰 틀에서 나누고,
세부 테마가 필요하면 cat1/cat2/cat3까지 내려가서 보정한다.

TourAPI 주요 contentTypeId (2026년 기준, 변경될 수 있으니 categoryCode2로 최신값 확인 권장):
  12 = 관광지        14 = 문화시설       15 = 축제/공연/행사
  25 = 여행코스       28 = 레포츠         32 = 숙박
  38 = 쇼핑          39 = 음식점

** 중요 - 실제 EngService2(영문) 호출해보고 발견한 것 **
외국어 서비스(EngService2/JpnService2/ChsService2 등)는 국문 서비스(KorService2)랑 완전히
다른 contentTypeId 번호 체계를 씀 (예: 영문 관광지=76, 국문 관광지=12). 서비스키가 영문
상품이면 이 값들이 나오니 아래 FOREIGN_CONTENT_TYPE_THEME으로 따로 매핑해뒀음.
  75 = 레포츠        76 = 관광지         78 = 문화시설
  79 = 쇼핑          80 = 숙박           82 = 음식점
  85 = 축제/공연/행사

기존 알고리즘이 "food / nonfood" 2분류였다면 아래 CONTENT_TYPE_THEME만 봐도 충분하고,
더 세분화하고 싶으면 CAT1_THEME_OVERRIDE에 규칙을 추가하면 됨.

** 중요 - PPT 확인 후 발견한 한계 **
최종발표 PPT를 보면 원래 알고리즘은 "자연/역사/한류/맛집/쇼핑" 같은 세부 테마를 썼고,
특히 "한류(hallyu)"는 TourAPI의 contentTypeId/cat1~3만으로는 절대 구분이 안 되는 테마야
(TourAPI는 관광지의 일반적인 분류 체계만 제공하지, "이 장소가 한류 콘텐츠와 관련있는지"는
알려주지 않음). 이 부분은 셋 중 하나로 풀어야 함:
  (a) TourAPI의 title/overview 텍스트에서 키워드 매칭(예: "촬영지", 특정 연예인/드라마명)으로
      직접 한류 태그를 다는 별도 로직 추가
  (b) 기존 엑셀에 있던 한류 장소 리스트를 그대로 살려서, TourAPI content_id와 매칭되는 것만
      수동/반자동으로 한류 태그 유지
  (c) 이번 버전에서는 한류 테마를 잠정 제외하고 나머지 테마부터 정확히 만들기
당장 정할 필요는 없고, 방향 정해지면 여기 CAT1_THEME_OVERRIDE 옆에 로직 추가하면 됨.
"""

# 1단계: contentTypeId 기준 기본 테마
CONTENT_TYPE_THEME: dict[str, str] = {
    "12": "sightseeing",   # 관광지
    "14": "culture",       # 문화시설
    "15": "festival",      # 축제/공연/행사
    "25": "course",        # 여행코스
    "28": "activity",      # 레포츠
    "32": "lodging",       # 숙박
    "38": "shopping",      # 쇼핑
    "39": "food",          # 음식점
}

# 2단계: cat1(대분류 코드) 기준으로 더 세밀하게 보정하고 싶을 때 여기 추가
# 예시로 자연/역사 정도만 넣어둠. 실제 cat1 코드값은 fetch_category_codes()로 확인해서 채우면 됨.
CAT1_THEME_OVERRIDE: dict[str, str] = {
    # "A01": "nature",   # 예: 자연 대분류 코드
    # "A02": "history",  # 예: 인문(역사/문화) 대분류 코드
}

# 외국어(EngService2 등) contentTypeId 매핑 - 위 "실제 EngService2 호출해보고 발견한 것" 참고.
# 값 이름은 CONTENT_TYPE_THEME과 동일한 어휘로 맞춰서 이후 로직(FOOD_THEME 등)이 그대로 통함.
FOREIGN_CONTENT_TYPE_THEME: dict[str, str] = {
    "75": "activity",      # 레포츠
    "76": "sightseeing",   # 관광지
    "78": "culture",       # 문화시설
    "79": "shopping",      # 쇼핑
    "80": "lodging",       # 숙박
    "82": "food",          # 음식점
    "85": "festival",      # 축제/공연/행사
}

DEFAULT_THEME = "etc"  # 어떤 규칙에도 안 걸리면 기타로 분류

# itinerary_service.py에서 특별 취급하는 테마 상수들
FOOD_THEME = "food"
LODGING_THEME = "lodging"
HALLYU_THEME = "hallyu"  # 위 설명대로 아직 TourAPI에서 자동으로 못 채움 (TODO)

# 서로 배타적인 "기본 카테고리" - 장소당 이 중 하나만 가짐 (한류는 별도 부가 태그, 아래
# label_themes_with_ai.py/place_theme 다대다 구조 참고). 국문/영문 contentTypeId 둘 다
# 결국 이 4개 라벨 중 하나로 귀결되기 때문에, AI 재분류 대상 판단 기준으로도 그대로 씀
# (label_themes_with_ai.py, scripts/sync_tourapi.py에서 import해서 사용).
BASE_CATEGORIES = {FOOD_THEME, "culture", "shopping", "sightseeing"}

# 위 두 매핑표(CONTENT_TYPE_THEME/FOREIGN_CONTENT_TYPE_THEME)에서 BASE_CATEGORIES로 귀결되는
# content_type_id만 모아둔 것 - label_themes_with_ai.py가 "AI 재분류가 의미있는 대상"을
# 국문/영문 서비스 구분 없이 한 번에 고를 때 씀.
AMBIGUOUS_CONTENT_TYPE_IDS: set[str] = {
    cid for cid, theme in {**CONTENT_TYPE_THEME, **FOREIGN_CONTENT_TYPE_THEME}.items()
    if theme in BASE_CATEGORIES
}

# "관광지"(contentTypeId 12/76)의 인문관광지(cat1=A02) > 웰니스관광(cat2=A0202) 밑에는
# 병원/의원(cat3=A02020500) 뿐 아니라 워터파크(A02020600)·공원(A02020700)·크루즈(A02020800)
# 같은 정상적인 관광지도 섞여 있음 - 실제 EngService2 응답 82건 표본으로 확인함.
# 그래서 cat2 전체가 아니라 cat3 단위로 정확히 병원/의원(의료관광)만 동기화 대상에서 제외한다.
EXCLUDED_CAT3_CODES = {"A02020500"}  # 병원/의원 (의료관광)


def resolve_theme(content_type_id: str, cat1: str | None = None, cat2: str | None = None, cat3: str | None = None) -> str:
    """
    Place 한 건의 분류 코드를 받아서 테마 라벨 하나를 반환.
    sync_tourapi.py에서 Place를 저장하기 직전에 이 함수를 호출해서 theme_code를 채운다.
    """
    # cat1 기준 override가 있으면 우선 적용
    if cat1 and cat1 in CAT1_THEME_OVERRIDE:
        return CAT1_THEME_OVERRIDE[cat1]

    if content_type_id in CONTENT_TYPE_THEME:
        return CONTENT_TYPE_THEME[content_type_id]
    if content_type_id in FOREIGN_CONTENT_TYPE_THEME:
        return FOREIGN_CONTENT_TYPE_THEME[content_type_id]
    return DEFAULT_THEME


def is_excluded_place(cat3: str | None) -> bool:
    """병원/의원(의료관광)처럼 여행 일정 추천에 부적합해서 동기화 자체를 건너뛰어야 하는 항목인지"""
    return bool(cat3) and cat3 in EXCLUDED_CAT3_CODES


def is_food_theme(theme_code: str) -> bool:
    """기존 알고리즘의 food/nonfood 밸런싱 로직과 호환되도록 만든 헬퍼"""
    return theme_code == "food"


# ---------------------------------------------------------------------------
# 프론트엔드(K-TRIP) Explore 카테고리 <-> 백엔드 theme_code 매핑
#
# 프론트 src/data/mockData.js의 CATEGORIES 상수(FOOD/CULTURE/HALLYU/SHOPPING/ATTRACTIONS)를
# 그대로 받아서 theme_code로 변환해준다.
#
# 주의: 지금 theme_code는 TourAPI contentTypeId 기준(위 CONTENT_TYPE_THEME)이라
# 프론트의 5개 카테고리보다 분류가 거칠다 - CULTURE/ATTRACTIONS를 각각 culture/sightseeing에
# 1:1로 매핑했지만 실제로는 겹치는 장소가 있을 수 있음(예: 고궁은 문화시설/관광지 둘 다 가능).
# HALLYU는 theme_mapper.py 상단 설명대로 아직 실제 데이터에 채워지지 않은 상태 (알려진 한계).
# ---------------------------------------------------------------------------
FRONTEND_CATEGORY_TO_THEME: dict[str, str] = {
    "FOOD": FOOD_THEME,
    "CULTURE": "culture",
    "SHOPPING": "shopping",
    "ATTRACTIONS": "sightseeing",
    "HALLYU": HALLYU_THEME,
}


def resolve_theme_code(frontend_category: str | None) -> str | None:
    """프론트 카테고리명(대소문자 무관)을 백엔드 theme_code로 변환. 매핑에 없으면 None."""
    if not frontend_category:
        return None
    return FRONTEND_CATEGORY_TO_THEME.get(frontend_category.strip().upper())
