"""
리뷰 API.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.review_service import (
    create_review,
    list_reviews_for_place,
    list_all_reviews,
    toggle_like,
    ReviewError,
)

router = APIRouter(tags=["review"])


class ReviewCreateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    content: str | None = None


class ReviewOut(BaseModel):
    id: int
    place_id: int
    user_id: int
    rating: int
    content: str | None
    like_count: int

    class Config:
        from_attributes = True


class LikeToggleOut(BaseModel):
    liked: bool


@router.post("/places/{place_id}/reviews", response_model=ReviewOut)
def post_review(
    place_id: int,
    payload: ReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        review = create_review(db, place_id, current_user.id, payload.rating, payload.content)
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return review


@router.get("/places/{place_id}/reviews", response_model=list[ReviewOut])
def get_reviews(place_id: int, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    return list_reviews_for_place(db, place_id, limit=limit, offset=offset)


@router.get("/reviews", response_model=list[ReviewOut])
def get_all_reviews(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """장소 상관없이 전체 리뷰를 최신순으로 조회. 예시: GET /reviews?limit=20&offset=0"""
    return list_all_reviews(db, limit=limit, offset=offset)


@router.post("/reviews/{review_id}/like", response_model=LikeToggleOut)
def like_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        liked = toggle_like(db, review_id, current_user.id)
    except ReviewError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return LikeToggleOut(liked=liked)
