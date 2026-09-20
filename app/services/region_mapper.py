"""
프론트엔드(K-TRIP) 지역명 <-> TourAPI area_code 매핑.

프론트 src/data/mockData.js의 DESTINATIONS 상수(SEOUL/INCHEON/GANGNEUNG/DAEJEON/
GYEONGJU/BUSAN/JEJU)를 그대로 받아서 area_code로 변환해준다.

주의: TourAPI area_code는 광역 시/도 단위라서, 강릉(강원도 소속)·경주(경상북도 소속)처럼
시/군 단위 지명은 그 지역이 속한 광역 area_code로 근사할 수밖에 없다 - 정확히 그 도시만
집어내는 게 아니라 도 전체가 후보에 포함된다는 뜻. 더 정밀하게 하려면 TourAPI의
sigunguCode(시/군/구 코드)까지 저장하도록 place 테이블을 확장해야 함 (지금은 area_code만 저장).
"""

FRONTEND_REGION_TO_AREA_CODE: dict[str, str] = {
    "SEOUL": "1",
    "INCHEON": "2",
    "GANGNEUNG": "32",   # 강원도 소속 (시/군 단위 -> 광역 코드로 근사)
    "DAEJEON": "3",
    "GYEONGJU": "35",    # 경상북도 소속 (시/군 단위 -> 광역 코드로 근사)
    "BUSAN": "6",
    "JEJU": "39",
}


def resolve_area_code(region_name: str | None) -> str | None:
    """프론트 지역명(대소문자 무관)을 TourAPI area_code로 변환. 매핑에 없으면 None."""
    if not region_name:
        return None
    return FRONTEND_REGION_TO_AREA_CODE.get(region_name.strip().upper())
