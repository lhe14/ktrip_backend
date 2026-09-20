"""
한국관광공사 TourAPI 4.0 호출 전담 모듈.

이 파일이 하는 일은 딱 하나: "TourAPI에 요청 보내고 JSON으로 응답 돌려주기".
DB 저장이나 데이터 가공 로직은 여기 넣지 않고 services/ 쪽에서 처리한다.
(나중에 API가 바뀌거나 다른 API로 교체해도 이 파일만 고치면 되도록 분리해둔 것)

주요 엔드포인트:
- areaBasedList2   : 지역 코드 기반으로 관광지 목록 조회 (배치 수집에 주로 사용)
- locationBasedList2 : 좌표(위도/경도) 기준 반경 내 관광지 조회 (4번 기능: 주변 관광지 추천에도 재사용 가능)
- detailCommon2    : 콘텐츠 상세 공통 정보 (설명, 이미지, 주소 등)
- detailIntro2     : 콘텐츠 타입별 소개 정보 (운영시간, 휴무일 등)
- categoryCode2    : 대/중/소분류 코드 목록 조회 (테마 매핑표 만들 때 참고용)
"""

import httpx
from app.core.config import settings

# TourAPI는 응답 형식을 JSON으로 받으려면 _type=json 파라미터가 필요함
_DEFAULT_PARAMS = {
    "serviceKey": settings.TOUR_API_SERVICE_KEY,
    "MobileOS": settings.TOUR_API_MOBILE_OS,
    "MobileApp": settings.TOUR_API_MOBILE_APP,
    "_type": "json",
}


def _get(endpoint: str, params: dict) -> dict:
    """
    공통 GET 요청 헬퍼.
    endpoint: "areaBasedList2" 같은 엔드포인트 이름
    params: 엔드포인트별 추가 파라미터
    """
    url = f"{settings.TOUR_API_BASE_URL}/{endpoint}"
    merged_params = {**_DEFAULT_PARAMS, **params}

    response = httpx.get(url, params=merged_params, timeout=10.0)
    response.raise_for_status()
    data = response.json()

    # TourAPI 공통 응답 구조: response.header.resultCode가 "0000"이면 정상
    result_code = data.get("response", {}).get("header", {}).get("resultCode")
    if result_code != "0000":
        result_msg = data.get("response", {}).get("header", {}).get("resultMsg")
        raise RuntimeError(f"TourAPI 호출 실패 [{endpoint}]: {result_code} {result_msg}")

    return data["response"]["body"]


def fetch_area_based_list(
    area_code: str,
    content_type_id: str | None = None,
    page_no: int = 1,
    num_of_rows: int = 100,
) -> dict:
    """
    지역 코드로 관광지 목록을 페이지 단위로 가져온다.
    배치 스크립트(sync_tourapi.py)에서 전체 데이터를 긁어올 때 이 함수를 반복 호출하게 됨.

    area_code: 시/도 코드 (예: 서울=1, 부산=6 ... TourAPI areaCode2로 조회 가능)
    content_type_id: 관광지=12, 문화시설=14, 음식점=39 등. None이면 전체 타입
    """
    params = {
        "areaCode": area_code,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "arrange": "C",  # 수정일 기준 정렬
    }
    if content_type_id:
        params["contentTypeId"] = content_type_id

    return _get("areaBasedList2", params)


def fetch_location_based_list(
    mapx: float,
    mapy: float,
    radius: int = 3000,
    content_type_id: str | None = None,
    page_no: int = 1,
    num_of_rows: int = 50,
) -> dict:
    """
    좌표 기준 반경(radius, 단위 m) 내 관광지 목록 조회.
    4번 기능 "사용자 위치 기반 주변 관광지 추천"에 그대로 쓸 수 있음.
    """
    params = {
        "mapX": mapx,
        "mapY": mapy,
        "radius": radius,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "arrange": "E",  # 거리순 정렬
    }
    if content_type_id:
        params["contentTypeId"] = content_type_id

    return _get("locationBasedList2", params)


def fetch_detail_common(content_id: str) -> dict:
    """콘텐츠 상세 공통 정보 (설명/이미지/주소 등)"""
    params = {
        "contentId": content_id,
        "defaultYN": "Y",
        "overviewYN": "Y",
        "firstImageYN": "Y",
        "addrinfoYN": "Y",
        "mapinfoYN": "Y",
    }
    return _get("detailCommon2", params)


def fetch_detail_intro(content_id: str, content_type_id: str) -> dict:
    """콘텐츠 타입별 소개 정보 (운영시간, 휴무일, 주차 가능 여부 등)"""
    params = {
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }
    return _get("detailIntro2", params)


def fetch_category_codes(content_type_id: str | None = None, cat1: str | None = None, cat2: str | None = None) -> dict:
    """
    대/중/소분류 코드 목록 조회.
    테마 매핑표(theme_mapper.py)를 만들 때 어떤 cat1/cat2/cat3 값이 있는지
    확인하는 용도로 한 번씩 호출해보면 됨 (매번 호출할 필요는 없음).
    """
    params = {}
    if content_type_id:
        params["contentTypeId"] = content_type_id
    if cat1:
        params["cat1"] = cat1
    if cat2:
        params["cat2"] = cat2

    return _get("categoryCode2", params)
