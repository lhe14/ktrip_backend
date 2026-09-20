"""
게시판 모델. PPT 4번 기능("사용자 게시판 - 지역별로 날씨, 동행, 양도, 사담 등 공유")에 해당.

게시글은 지역(area_code)별로 필터링해서 볼 수 있게 area_code를 갖고,
카테고리는 실제 프론트엔드(K-TRIP) 커뮤니티 화면 기준(Q&A/TIPS/REVIEW/COMPANION)으로 맞춤
- 기존 PPT 초안의 날씨/양도/사담 카테고리는 현재 프론트 화면에 없어서 뺐음, 다시 필요해지면
  BoardCategory에 추가하면 됨 (DB 컬럼 자체는 문자열이라 제약 없음).

REVIEW/COMPANION 타입은 프론트 목업(mockData.js의 POSTS)에 맞춰 전용 컬럼/테이블을 뒀음:
- REVIEW: 특정 장소(place_id)에 대한 별점(rating)이 같이 달림
- COMPANION: 동행 모집 정보(BoardPostCompanion)가 1:1로 붙음
좋아요는 Review와 동일한 패턴(집계 컬럼 + 유니크 좋아요 테이블)으로 구현.
"""

import enum

from sqlalchemy import Column, Date, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class BoardCategory(str, enum.Enum):
    QNA = "qna"                # Q&A
    TIPS = "tips"               # TIPS
    REVIEW = "review"           # REVIEW (place_id/rating 필수)
    COMPANION = "companion"     # COMPANION (동행 모집 정보 필수)


class BoardPost(Base):
    __tablename__ = "board_post"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # 지역별 게시판이므로 area_code로 필터링. NULL이면 전체 지역 공용 게시글로 취급
    area_code = Column(String(10), index=True, nullable=True)
    category = Column(String(20), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)

    # REVIEW 타입 전용 (그 외 타입은 NULL)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=True, index=True)
    rating = Column(Integer, nullable=True)  # 1~5

    # 캐시 컬럼 - 매번 세지 않고 좋아요/댓글 버튼에 바로 찍어주기 위함
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    place = relationship("Place")
    companion = relationship(
        "BoardPostCompanion", uselist=False, back_populates="post", cascade="all, delete-orphan"
    )


class BoardPostCompanion(Base):
    """COMPANION 타입 게시글에만 붙는 동행 모집 상세 정보 (게시글 1개당 1행)"""
    __tablename__ = "board_post_companion"

    post_id = Column(Integer, ForeignKey("board_post.id"), primary_key=True)
    destination = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    travelers_needed = Column(Integer, nullable=True)   # 모집 정원
    travelers_joined = Column(Integer, nullable=False, default=1)  # 작성자 포함 현재 인원

    post = relationship("BoardPost", back_populates="companion")


class BoardPostLike(Base):
    """게시글 좋아요. (post_id, user_id) 조합이 유일해야 중복 방지됨 (review_like와 동일 패턴)"""
    __tablename__ = "board_post_like"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_board_post_like_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("board_post.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)


class BoardComment(Base):
    __tablename__ = "board_comment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("board_post.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)
    like_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class BoardCommentLike(Base):
    """댓글 좋아요. (comment_id, user_id) 조합이 유일해야 중복 방지됨"""
    __tablename__ = "board_comment_like"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_board_comment_like_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("board_comment.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
