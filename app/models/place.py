"""
TourAPI에서 받아온 관광지 데이터를 저장하는 자체 DB 모델.

기존 엑셀 기반 로직에서 쓰던 컬럼들(이름/좌표/테마/점수 등)을
TourAPI 필드에 맞게 재정의한 것.
컬럼 이름 옆 주석은 "이 값이 TourAPI 어느 필드에서 왔는지" 표시해둠 -
나중에 sync_tourapi.py에서 매핑할 때 참고.
"""

from sqlalchemy import Boolean, Column, String, Float, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Place(Base):
    __tablename__ = "place"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # TourAPI의 contentId. 이후 detailCommon2 등 상세조회할 때도 이 값을 씀
    content_id = Column(String(20), unique=True, nullable=False, index=True)

    # 기본 정보 (areaBasedList2 응답 필드 기준)
    title = Column(String(200), nullable=False)  # title
    address = Column(String(300))  # addr1 + addr2

    # 시/도 지역 코드 (areacode). sync_tourapi.py가 어느 area_code로 조회했는지 그대로 저장.
    # 값 목록은 scripts/sync_tourapi.py 상단 주석 참고 (1=서울, 6=부산 ...)
    area_code = Column(String(10), index=True)
    mapx = Column(Float)  # mapx (경도)
    mapy = Column(Float)  # mapy (위도)
    first_image = Column(String(500))  # firstimage
    tel = Column(String(50))  # tel

    # 분류 코드 (원본 그대로 저장해두고, 테마 라벨은 theme_code로 별도 보관)
    content_type_id = Column(String(10))  # contentTypeId: 12=관광지, 14=문화시설, 39=음식점 ...
    cat1 = Column(String(10))
    cat2 = Column(String(10))
    cat3 = Column(String(10))

    # theme_mapper.py에서 content_type_id/cat1~3을 보고 계산해서 채워 넣는 컬럼
    # 기존 알고리즘에서 쓰던 "food"/"nonfood" 같은 테마 라벨이 여기 들어감
    theme_code = Column(String(30), index=True)

    # 상세 설명 (detailCommon2의 overview) - 필요할 때만 채움, 없어도 무방
    overview = Column(Text, nullable=True)

    # 점수제 (score_service.py가 계산해서 갱신)
    # 초기값은 0으로 두고, 리뷰가 쌓이면 재계산해서 업데이트하는 방식 추천
    score = Column(Float, default=0.0)

    # 데이터 최신화 시각 (배치 돌 때마다 갱신)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 장소 하나에 테마 여러 개를 붙일 수 있는 다대다 연결 (예: "역사"이면서 동시에 "한류").
    # theme_code는 그중 "주 테마" 하나를 그대로 들고 있는 캐시 컬럼 - 기존 코드/응답 호환용으로
    # 계속 유지하고, place_themes가 실제 매칭/검색에 쓰이는 진짜 소스임 (PlaceTheme 참고).
    place_themes = relationship("PlaceTheme", cascade="all, delete-orphan", back_populates="place")

    def __repr__(self) -> str:
        return f"<Place id={self.id} title={self.title!r} theme={self.theme_code}>"


class ThemeMap(Base):
    """
    TourAPI의 (content_type_id, cat1, cat2, cat3) 조합을
    기존 알고리즘이 쓰던 테마 라벨로 변환하기 위한 매핑 테이블.

    코드로 하드코딩해도 되지만, 캡스톤 특성상 테마 기준이 자주 바뀔 수 있어서
    테이블로 빼두면 코드 수정 없이 값만 바꿔서 재적용할 수 있음.
    (테마 종류가 몇 개 안 되면 theme_mapper.py 안에 dict로만 관리해도 충분함 - 5번 태스크 참고)
    """
    __tablename__ = "theme_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_type_id = Column(String(10), nullable=False)
    cat1 = Column(String(10), nullable=True)
    cat2 = Column(String(10), nullable=True)
    cat3 = Column(String(10), nullable=True)
    theme_code = Column(String(30), nullable=False)  # 예: "food", "nature", "culture", "activity"


class Theme(Base):
    """
    테마 종류를 코드가 아니라 DB로 관리하기 위한 마스터 테이블.
    theme_mapper.py의 하드코딩된 라벨들을 여기 값과 맞춰서 쓴다 (place_theme.theme_code가
    이 테이블의 code를 FK로 참조하므로, 새 테마를 쓰려면 여기 먼저 행을 추가해야 함).
    """
    __tablename__ = "theme"

    code = Column(String(30), primary_key=True)
    name = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlaceTheme(Base):
    """
    장소 <-> 테마 다대다 연결. 장소 하나가 테마 여러 개를 가질 수 있게 해주는 실제 매칭 테이블
    (예: 경복궁 = culture + hallyu 둘 다 가능).

    source: 이 태그가 어디서 왔는지 ("rule"=sync_tourapi.py의 규칙 기반 1차 분류,
            "ai"=label_themes_with_ai.py의 Gemini 재분류, "manual"=사람이 큐레이션한 목록 등)
    confidence: AI가 매긴 태그일 때만 신뢰도(0~1)를 남겨둠 - 나중에 낮은 신뢰도만 다시
                검수하고 싶을 때 필터링 용도. rule/manual 태그는 보통 None.
    """
    __tablename__ = "place_theme"
    __table_args__ = (UniqueConstraint("place_id", "theme_code", name="uq_place_theme"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(Integer, ForeignKey("place.id", ondelete="CASCADE"), nullable=False, index=True)
    theme_code = Column(String(30), ForeignKey("theme.code", ondelete="RESTRICT"), nullable=False, index=True)
    source = Column(String(20), nullable=False, server_default="rule")
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    place = relationship("Place", back_populates="place_themes")
