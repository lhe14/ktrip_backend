"""
TourAPI 서비스키 없이도 기능 테스트를 해볼 수 있도록 관광지 더미 데이터를 넣는 스크립트.

실행: python -m scripts.seed_dummy_places

sync_tourapi.py(실제 TourAPI 연동)를 아직 못 돌려봤을 때, 일정 추천/리뷰/위치기반 검색
같은 기능을 눈으로 확인해보기 위한 용도. 이미 데이터가 있으면 건너뜀 (중복 삽입 안 함).
"""

from app.db.session import SessionLocal, Base, engine
from app.models.place import Place, PlaceTheme

Base.metadata.create_all(bind=engine)

DUMMY_PLACES = [
    # (content_id, title, area_code, theme_code, mapx, mapy, score)
    ("dummy1", "경복궁", "1", "sightseeing", 126.9770, 37.5796, 92),
    ("dummy2", "광화문 광장", "1", "sightseeing", 126.9768, 37.5720, 85),
    ("dummy3", "북촌한옥마을", "1", "culture", 126.9850, 37.5826, 80),
    ("dummy4", "명동교자", "1", "food", 126.9855, 37.5636, 88),
    ("dummy5", "광장시장 맛집골목", "1", "food", 126.9997, 37.5701, 90),
    ("dummy6", "이태원 맛집거리", "1", "food", 126.9942, 37.5347, 78),
    ("dummy7", "동대문 쇼핑타운", "1", "shopping", 127.0098, 37.5663, 75),
    ("dummy8", "남산서울타워", "1", "sightseeing", 126.9882, 37.5512, 95),
    ("dummy9", "호텔 서울 센트럴", "1", "lodging", 126.9820, 37.5600, 70),
    ("dummy10", "해운대해수욕장", "6", "sightseeing", 129.1600, 35.1587, 91),
    ("dummy11", "부산 자갈치시장", "6", "food", 129.0306, 35.0968, 82),
    ("dummy12", "호텔 부산 비치", "6", "lodging", 129.1620, 35.1600, 68),
]


def _ensure_theme_rows(db, theme_codes: set[str]) -> None:
    """place_theme.theme_code가 theme.code를 FK로 참조하므로, alembic 없이 create_all()만
    돌린 상태여도 최소한 여기서 쓰는 코드들은 미리 채워둔다 (alembic이 이미 채워놨으면 건너뜀)."""
    from app.models.place import Theme

    existing = {t.code for t in db.query(Theme.code).all()}
    for code in theme_codes - existing:
        db.add(Theme(code=code, name=code))
    db.commit()


def main():
    db = SessionLocal()
    try:
        _ensure_theme_rows(db, {row[3] for row in DUMMY_PLACES})

        added = 0
        for content_id, title, area_code, theme_code, mapx, mapy, score in DUMMY_PLACES:
            exists = db.query(Place).filter(Place.content_id == content_id).first()
            if exists:
                continue
            place = Place(
                content_id=content_id,
                title=title,
                area_code=area_code,
                theme_code=theme_code,
                mapx=mapx,
                mapy=mapy,
                score=score,
                address=f"{title} 근처 (더미 주소)",
            )
            db.add(place)
            db.flush()  # place.id 확보
            db.add(PlaceTheme(place_id=place.id, theme_code=theme_code, source="rule"))
            added += 1
        db.commit()
        print(f"더미 관광지 {added}건 추가 (이미 있던 건 건너뜀)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
