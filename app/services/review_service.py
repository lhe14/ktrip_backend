"""
리뷰 작성/조회/좋아요 비즈니스 로직.

리뷰가 새로 생기거나 좋아요 수가 바뀌면 그 장소의 score_service 점수도 같이
갱신해줘야 추천 알고리즘(itinerary_service)이 최신 평점을 반영함.
"""

from sqlalchemy.orm import Session

from app.models.place import Place
from app.models.review import Review, ReviewLike
from app.services.score_service import refresh_place_score


class ReviewError(Exception):
    """존재하지 않는 장소, 잘못된 평점 등 리뷰 관련 오류"""


def create_review(db: Session, place_id: int, user_id: int, rating: int, content: str | None) -> Review:
    if not (1 <= rating <= 5):
        raise ReviewError("평점은 1~5 사이여야 합니다")

    place = db.query(Place).filter(Place.id == place_id).first()
    if place is None:
        raise ReviewError("존재하지 않는 장소입니다")

    review = Review(place_id=place_id, user_id=user_id, rating=rating, content=content)
    db.add(review)
    db.commit()
    db.refresh(review)

    refresh_place_score(db, place_id)  # 새 리뷰가 점수에 바로 반영되도록

    return review


def list_reviews_for_place(db: Session, place_id: int, limit: int = 20, offset: int = 0) -> list[Review]:
    return (
        db.query(Review)
        .filter(Review.place_id == place_id)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_all_reviews(db: Session, limit: int = 20, offset: int = 0) -> list[Review]:
    """장소 상관없이 사이트 전체 리뷰를 최신순으로 조회 (관리자 화면/전체 피드용)"""
    return (
        db.query(Review)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def toggle_like(db: Session, review_id: int, user_id: int) -> bool:
    """
    좋아요를 눌렀다 뗐다 토글. 반환값 True=이번 호출로 좋아요가 눌린 상태, False=취소된 상태.
    """
    review = db.query(Review).filter(Review.id == review_id).first()
    if review is None:
        raise ReviewError("존재하지 않는 리뷰입니다")

    existing = (
        db.query(ReviewLike)
        .filter(ReviewLike.review_id == review_id, ReviewLike.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        review.like_count = max(review.like_count - 1, 0)
        liked_now = False
    else:
        db.add(ReviewLike(review_id=review_id, user_id=user_id))
        review.like_count += 1
        liked_now = True

    db.commit()

    refresh_place_score(db, review.place_id)  # 좋아요도 점수에 반영

    return liked_now
