"""
Gemini(무료 티어)를 이용한 관광지 테마 재분류 + 한류(hallyu) 보조 태깅 배치 스크립트.

배경: TourAPI의 contentTypeId/cat1~3만으로는 "한류(hallyu)" 같은 테마를 절대 구분할 수
없음 (theme_mapper.py 상단 설명 참고). 그렇다고 장소 하나하나 사람이 태깅하기엔 시간이
부족해서, title/overview 텍스트를 Gemini한테 읽혀서 대신 분류하게 시키는 스크립트.

한류는 "기본 카테고리"가 아니라 별도의 부가 태그로 취급한다 (팀원 제안으로 도입한
theme/place_theme 다대다 구조 덕분에 가능해짐 - alembic/versions/0002 참고). 예를 들어
경복궁은 category=culture이면서 동시에 실제로 드라마 촬영지였다면 is_hallyu=true로
같이 태깅될 수 있음 - 예전처럼 "한류로 분류되면 문화 라벨을 잃어버리는" 문제가 없어짐.

한류 판단 기준 (프롬프트에 그대로 반영): K-pop 기획사, 드라마/영화 촬영지, 아이돌 관련
명소, 팬 성지 등 - title/overview 텍스트에 그런 단서가 있는 경우만 잡힘. TourAPI 자체에
등록 안 된 장소나, 등록은 됐어도 설명글에 그런 언급이 없으면 못 잡는 한계가 있음.

무료로 유지하는 방법:
- 장소 하나당 API 호출 1번이 아니라, BATCH_SIZE개씩 묶어서 한 번에 물어봄 (호출 횟수 최소화)
- 애초에 분류가 애매한 content_type_id(관광지/문화시설/쇼핑/음식점)만 대상으로 함 -
  숙박/축제/레포츠/여행코스는 원래 규칙(theme_mapper.CONTENT_TYPE_THEME)만으로 충분히
  명확해서 AI한테 안 물어봄 (쿼터 절약)
- 배치 사이에 딜레이를 둬서 무료 티어 분당 요청 한도를 안 넘기게 함

실행 (프로젝트 루트에서, TourAPI 동기화 이후 한 번):
    python -m scripts.label_themes_with_ai

필요: .env에 GEMINI_API_KEY 설정 (무료 발급: https://aistudio.google.com/apikey)
"""

import json
import re
import sys
import time

from app.db.session import SessionLocal
from app.models.place import Place, PlaceTheme
from app.external.gemini_client import generate_text
from app.services.theme_mapper import BASE_CATEGORIES, AMBIGUOUS_CONTENT_TYPE_IDS

# AI 분류 대상: 원래부터 분류가 애매해서 세분화가 필요한 content_type_id만
# (국문 12/14/38/39 + 영문 76/78/79/82 - theme_mapper.py의 AMBIGUOUS_CONTENT_TYPE_IDS 참고.
# 처음엔 국문 코드만 넣어뒀다가, 실제로 EngService2로 동기화해보니 전혀 안 잡혀서 발견한 문제)
TARGET_CONTENT_TYPE_IDS = AMBIGUOUS_CONTENT_TYPE_IDS

BATCH_SIZE = 25
REQUEST_DELAY_SEC = 4.5  # 무료 티어 분당 요청 한도 대응용 딜레이
MAX_RETRIES = 3

PROMPT_TEMPLATE = """다음은 한국 관광지 목록입니다. 각 장소에 대해 두 가지를 판단해주세요.

1) category - 아래 4개 중 정확히 하나:
   - food: 음식점, 시장, 카페 등 먹거리 중심 장소
   - culture: 고궁, 박물관, 전통시장, 한옥마을 등 역사/문화 유산
   - shopping: 쇼핑몰, 상점가, 아울렛 등 쇼핑 중심 장소
   - sightseeing: 위 3개에 해당하지 않는 일반 관광지, 자연경관, 전망대 등

2) is_hallyu - 이 장소가 한류(K-pop/K-드라마/K-영화)와 명확히 관련 있는지 true/false.
   해당하는 예: 연예기획사 건물/투어, 드라마·영화 촬영지, 아이돌 관련 명소, 팬 성지,
   K-pop 관련 박물관/전시. category와는 독립적으로 판단 - 예를 들어 고궁이 실제로
   유명한 드라마 촬영지였다면 category=culture이면서 is_hallyu=true가 될 수 있음.
   설명에 그런 단서가 전혀 없으면 false로 판단할 것 (추측해서 true로 넣지 말 것).

장소 목록:
{place_list}

반드시 아래 형식의 JSON 배열만 출력하세요. 다른 설명, 마크다운 코드블록 없이 순수 JSON만:
[{{"content_id": "장소의 content_id", "category": "food|culture|shopping|sightseeing 중 하나", "is_hallyu": true 또는 false, "hallyu_confidence": is_hallyu가 true일 때 0~1 사이 확신도, false면 0}}, ...]
"""


def _build_place_list_text(places: list[Place]) -> str:
    lines = []
    for p in places:
        overview = (p.overview or "")[:200]
        lines.append(
            f"- content_id={p.content_id} | 이름: {p.title} | 분류코드: {p.content_type_id} | 설명: {overview}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> list[dict]:
    """마크다운 코드블록(```json ... ```)이 섞여 와도 안전하게 JSON 배열만 뽑아냄"""
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def _classify_batch(places: list[Place]) -> dict[str, dict]:
    """{content_id: {"category":..., "is_hallyu":..., "confidence":...}} 반환.
    실패하면 빈 딕셔너리 (기존 테마 유지됨)"""
    prompt = PROMPT_TEMPLATE.format(place_list=_build_place_list_text(places))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            text = generate_text(prompt)
            parsed = _extract_json(text)
            result = {}
            for item in parsed:
                content_id = item.get("content_id")
                category = item.get("category")
                if not content_id or category not in BASE_CATEGORIES:
                    continue
                is_hallyu = bool(item.get("is_hallyu"))
                confidence = item.get("hallyu_confidence")
                confidence = float(confidence) if isinstance(confidence, (int, float)) else None
                result[content_id] = {
                    "category": category,
                    "is_hallyu": is_hallyu,
                    "confidence": confidence if is_hallyu else None,
                }
            return result
        except Exception as e:
            print(f"  배치 처리 실패 (시도 {attempt}/{MAX_RETRIES}): {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY_SEC * attempt)  # 재시도할수록 더 오래 대기

    return {}


def _tag_exists(db, place_id: int, theme_code: str) -> bool:
    return (
        db.query(PlaceTheme)
        .filter(PlaceTheme.place_id == place_id, PlaceTheme.theme_code == theme_code)
        .first()
        is not None
    )


def _sync_ai_themes(db, place: Place, category: str, is_hallyu: bool, confidence: float | None) -> None:
    """AI 판단 결과를 place_theme에 반영.

    - 기본 카테고리(food/culture/shopping/sightseeing)는 장소당 하나만 유지 - AI가 새로
      판단한 category와 다른 기존 태그(rule이든 ai든)는 지우고 새 걸로 교체
    - hallyu는 완전히 별도의 부가 태그 - 기본 카테고리를 안 건드리고 붙였다 뗐다 함
      (단, 사람이 직접 큐레이션한 source='manual' hallyu 태그는 AI가 지우지 않음)
    """
    stale_base = (
        db.query(PlaceTheme)
        .filter(PlaceTheme.place_id == place.id, PlaceTheme.theme_code.in_(BASE_CATEGORIES))
        .filter(PlaceTheme.theme_code != category)
        .all()
    )
    for tag in stale_base:
        db.delete(tag)
    db.flush()

    if not _tag_exists(db, place.id, category):
        db.add(PlaceTheme(place_id=place.id, theme_code=category, source="ai"))

    if is_hallyu:
        if not _tag_exists(db, place.id, "hallyu"):
            db.add(PlaceTheme(place_id=place.id, theme_code="hallyu", source="ai", confidence=confidence))
    else:
        db.query(PlaceTheme).filter(
            PlaceTheme.place_id == place.id,
            PlaceTheme.theme_code == "hallyu",
            PlaceTheme.source == "ai",
        ).delete()


def main():
    db = SessionLocal()
    try:
        places = (
            db.query(Place)
            .filter(Place.content_type_id.in_(TARGET_CONTENT_TYPE_IDS))
            .all()
        )
        if not places:
            print("AI로 재분류할 대상 장소가 없습니다 (먼저 TourAPI 동기화를 실행하세요).")
            return

        print(f"AI 재분류 대상: {len(places)}건 (배치 크기 {BATCH_SIZE}개씩)")

        updated = 0
        hallyu_found = 0
        for i in range(0, len(places), BATCH_SIZE):
            batch = places[i : i + BATCH_SIZE]
            batch_no = i // BATCH_SIZE + 1
            print(f"[batch {batch_no}] {len(batch)}건 분류 요청 중...")

            results = _classify_batch(batch)
            batch_updated = 0
            for place in batch:
                result = results.get(place.content_id)
                if not result:
                    continue
                place.theme_code = result["category"]  # 하위호환용 "주 테마" 캐시 컬럼
                _sync_ai_themes(db, place, result["category"], result["is_hallyu"], result["confidence"])
                batch_updated += 1
                if result["is_hallyu"]:
                    hallyu_found += 1

            db.commit()
            updated += batch_updated
            print(f"[batch {batch_no}] {batch_updated}/{len(batch)}건 분류 완료")

            if i + BATCH_SIZE < len(places):
                time.sleep(REQUEST_DELAY_SEC)

        print(f"전체 완료: {updated}/{len(places)}건 테마 갱신, 한류 태깅 {hallyu_found}건")
    finally:
        db.close()


if __name__ == "__main__":
    main()
