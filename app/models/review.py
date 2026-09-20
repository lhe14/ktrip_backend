"""
리뷰 모델. PPT 4번 기능("여행지 리뷰 - 별점 및 좋아요")에 해당.

Review 하나당 좋아요는 여러 사용자가 누를 수 있으니 좋아요 자체는
별도 ReviewLike 테이블로 분리해서 "이미 좋아요 눌렀는지" 판단과 중복 방지를 함.
Review.like_count는 매번 세는 대신 빠른 조회를 위한 캐시 컬럼으로 둠
(좋아요 누를 때마다 review_service에서 같이 갱신).
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)  # 1~5
    content = Column(Text, nullable=True)
    like_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    place = relationship("Place")
    user = relationship("User")


class ReviewLike(Base):
    """리뷰 좋아요. (review_id, user_id) 조합이 유일해야 중복 좋아요를 막을 수 있음"""
    __tablename__ = "review_like"
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_review_like_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("review.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
