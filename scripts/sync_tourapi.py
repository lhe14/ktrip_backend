"""
TourAPI -> 자체 DB 적재 배치 스크립트.

실행 방법 (프로젝트 루트에서):
    python -m scripts.sync_tourapi

cron이나 APScheduler로 하루 1회 정도 돌리는 걸 추천.
같은 content_id가 이미 있으면 update, 없으면 insert (upsert) 방식으로 동작.

TourAPI 시/도 area code (자주 쓰는 것 위주, 필요하면 areaCode2로 전체 목록 확인):
    1=서울  2=인천  3=대전  4=대구  5=광주  6=부산  7=울산  8=세종
    31=경기 32=강원 33=충북 34=충남 35=경북 36=경남 37=전북 38=전남 39=제주
"""

import sys
import time

from app.db.session import SessionLocal
from app.models.place import Place, PlaceTheme
from app.services.theme_mapper import resolve_theme, is_excluded_place, BASE_CATEGORIES
from app.external.tourapi_client import fetch_area_based_list

# 전국구 - TourAPI 시/도 전체 코드 (위 표 참고)
TARGET_AREA_CODES = [
    "1", "2", "3", "4", "5", "6", "7", "8",
    "31", "32", "33", "34", "35", "36", "37", "38", "39",
]

REQUEST_DELAY_SEC = 0.3  # TourAPI 트래픽 제한 대응용 딜레이. 429 뜨면 값을 늘릴 것


def _sync_rule_theme(db, place: Place, new_theme_code: str) -> str:
    """place_theme의 "rule" 출처 태그를 규칙 기반 재분류 결과와 맞춰준다.

    - 재동기화로 분류가 바뀌면 예전 rule 태그는 지우고 새 걸로 교체
    - 이미 같은 theme_code로 태깅돼있으면(rule이든 ai/manual이든) 손대지 않음
      - AI가 이미 더 정확하게 분류해둔 걸 규칙 기반 재동기화가 덮어쓰지 않기 위함

    반환값: 이 장소의 "주 테마"로 실제 써야 할 theme_code.
    AI가 이미 기본 카테고리(BASE_CATEGORIES)를 재분류해뒀으면 그 값을 그대로 우선시해서
    반환한다 - 안 그러면 재동기화할 때마다 place.theme_code(캐시 컬럼)가 AI 판단 이전의
    규칙 기반 값으로 되돌아가버려서, place_theme(진짜 소스)와 어긋나게 됨.
    """
    db.flush()  # 신규 place면 여기서 id가 확정됨

    ai_base_tag = (
        db.query(PlaceTheme)
        .filter(PlaceTheme.place_id == place.id, PlaceTheme.source == "ai")
        .filter(PlaceTheme.theme_code.in_(BASE_CATEGORIES))
        .first()
    )
    if ai_base_tag:
        # AI가 이미 기본 카테고리를 정해뒀으면 규칙 기반 재분류는 손 떼고 그 값을 그대로 씀
        # (여기서 더 진행하면 AI가 지워둔 예전 rule 태그를 되살려버림)
        return ai_base_tag.theme_code

    stale_rule_tags = (
        db.query(PlaceTheme)
        .filter(PlaceTheme.place_id == place.id, PlaceTheme.source == "rule")
        .filter(PlaceTheme.theme_code != new_theme_code)
        .all()
    )
    for tag in stale_rule_tags:
        db.delete(tag)

    already_tagged = (
        db.query(PlaceTheme)
        .filter(PlaceTheme.place_id == place.id, PlaceTheme.theme_code == new_theme_code)
        .first()
    )
    if not already_tagged:
        db.add(PlaceTheme(place_id=place.id, theme_code=new_theme_code, source="rule"))

    return new_theme_code


def upsert_place(db, item: dict, area_code: str) -> bool:
    """TourAPI 응답 item 하나를 Place 테이블에 upsert. 실제로 저장했으면 True, 건너뛰었으면 False.

    area_code: 이 item을 조회할 때 사용한 지역 코드 (areaBasedList2 호출 파라미터).
    TourAPI 응답에도 areacode 필드가 같이 오는데, 혹시 비어있는 경우를 대비해서
    호출 시점에 쓴 area_code를 fallback으로 사용한다.
    """
    content_id = item.get("contentid")
    if not content_id:
        return False  # contentId 없는 이상한 응답은 skip

    content_type_id = item.get("contenttypeid", "")
    cat1 = item.get("cat1")
    cat2 = item.get("cat2")
    cat3 = item.get("cat3")

    if is_excluded_place(cat3):
        # 의료관광(병원/의원) 등 제외 대상 - 예전에 잘못 들어간 게 있으면 같이 정리
        db.query(Place).filter(Place.content_id == content_id).delete()
        return False

    theme_code = resolve_theme(content_type_id, cat1, cat2, cat3)

    place = db.query(Place).filter(Place.content_id == content_id).first()
    if place is None:
        place = Place(content_id=content_id)
        db.add(place)

    place.title = item.get("title", "")
    place.address = (item.get("addr1") or "") + " " + (item.get("addr2") or "")
    place.area_code = item.get("areacode") or area_code
    place.mapx = float(item["mapx"]) if item.get("mapx") else None
    place.mapy = float(item["mapy"]) if item.get("mapy") else None
    place.first_image = item.get("firstimage")
    place.tel = item.get("tel")
    place.content_type_id = content_type_id
    place.cat1 = cat1
    place.cat2 = cat2
    place.cat3 = cat3

    # place.theme_code는 하위호환용 "주 테마" 캐시 컬럼 - _sync_rule_theme이 AI가 이미 더 정확하게
    # 재분류해둔 게 있으면 그 값을 돌려주므로, 규칙 기반 값(theme_code)으로 무조건 덮어쓰지 않음
    place.theme_code = _sync_rule_theme(db, place, theme_code)
    return True


def sync_area(db, area_code: str) -> int:
    """특정 지역의 데이터를 페이지 끝까지 순회하며 적재. 실제로 저장된 건수 반환 (제외된 건 안 셈)"""
    page_no = 1
    num_of_rows = 100
    total_synced = 0
    total_seen = 0

    while True:
        body = fetch_area_based_list(area_code, page_no=page_no, num_of_rows=num_of_rows)
        total_count = body.get("totalCount", 0)
        items = body.get("items", {})

        # TourAPI는 결과가 없으면 items가 빈 문자열("")로 오는 경우가 있어서 방어 처리
        item_list = items.get("item", []) if isinstance(items, dict) else []
        if isinstance(item_list, dict):  # 결과가 1건이면 list가 아니라 dict로 옴 (TourAPI 특징)
            item_list = [item_list]

        for item in item_list:
            if upsert_place(db, item, area_code):
                total_synced += 1
            total_seen += 1

        db.commit()
        print(f"[area={area_code}] page {page_no} 처리 완료 (저장 {total_synced}건 / 조회 {total_seen}/{total_count}건)")

        if page_no * num_of_rows >= total_count:
            break

        page_no += 1
        time.sleep(REQUEST_DELAY_SEC)

    return total_synced


def main():
    db = SessionLocal()
    try:
        grand_total = 0
        for area_code in TARGET_AREA_CODES:
            grand_total += sync_area(db, area_code)
        print(f"전체 동기화 완료: 총 {grand_total}건")
    except Exception as e:
        print(f"동기화 중 오류 발생: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
