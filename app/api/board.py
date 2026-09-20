"""
게시판 API.
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.region_mapper import resolve_area_code
from app.services.board_service import (
    create_post,
    list_posts,
    get_post,
    create_comment,
    list_comments,
    toggle_post_like,
    toggle_comment_like,
    BoardError,
)

router = APIRouter(prefix="/board", tags=["board"])


class CompanionInfo(BaseModel):
    destination: str
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    travelers_needed: int | None = None
    travelers_joined: int | None = None

    class Config:
        from_attributes = True


class PostCreateRequest(BaseModel):
    title: str
    content: str
    category: str  # qna / tips / review / companion
    area_code: str | None = None    # TourAPI 코드 직접 지정 (넘기면 region보다 우선)
    region: str | None = None       # 프론트 지역명 그대로 전달 (예: SEOUL)
    image_url: str | None = None
    place_id: int | None = None          # category=review일 때 필수
    rating: int | None = None            # category=review일 때 필수 (1~5)
    companion: CompanionInfo | None = None  # category=companion일 때 필수


class PostOut(BaseModel):
    id: int
    user_id: int
    author_nickname: str
    area_code: str | None
    category: str
    title: str
    content: str
    image_url: str | None
    place_id: int | None
    rating: int | None
    like_count: int
    comment_count: int
    companion: CompanionInfo | None = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class CommentCreateRequest(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    post_id: int
    user_id: int
    author_nickname: str
    content: str
    like_count: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class LikeToggleOut(BaseModel):
    liked: bool


def _post_out(post) -> PostOut:
    """post.user는 BoardPost.user 관계로 항상 로드 가능 - author_nickname은 여기서만 채움
    (ORM에 없는 필드라 from_attributes 자동 매핑이 안 돼서 수동 변환)"""
    return PostOut(
        id=post.id,
        user_id=post.user_id,
        author_nickname=post.user.nickname,
        area_code=post.area_code,
        category=post.category,
        title=post.title,
        content=post.content,
        image_url=post.image_url,
        place_id=post.place_id,
        rating=post.rating,
        like_count=post.like_count,
        comment_count=post.comment_count,
        companion=post.companion,
        created_at=post.created_at,
    )


def _comment_out(comment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        author_nickname=comment.user.nickname,
        content=comment.content,
        like_count=comment.like_count,
        created_at=comment.created_at,
    )


@router.post("/posts", response_model=PostOut)
def post_board_post(
    payload: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    companion = payload.companion
    resolved_area_code = payload.area_code or resolve_area_code(payload.region)
    try:
        post = create_post(
            db,
            current_user.id,
            payload.title,
            payload.content,
            payload.category,
            resolved_area_code,
            image_url=payload.image_url,
            place_id=payload.place_id,
            rating=payload.rating,
            companion_destination=companion.destination if companion else None,
            companion_start_date=companion.start_date if companion else None,
            companion_end_date=companion.end_date if companion else None,
            companion_travelers_needed=companion.travelers_needed if companion else None,
        )
    except BoardError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _post_out(post)


@router.post("/posts/{post_id}/like", response_model=LikeToggleOut)
def like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        liked = toggle_post_like(db, post_id, current_user.id)
    except BoardError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return LikeToggleOut(liked=liked)


@router.get("/posts", response_model=list[PostOut])
def get_board_posts(
    area_code: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    posts = list_posts(db, area_code=area_code, category=category, limit=limit, offset=offset)
    return [_post_out(p) for p in posts]


@router.get("/posts/{post_id}", response_model=PostOut)
def get_board_post(post_id: int, db: Session = Depends(get_db)):
    try:
        post = get_post(db, post_id)
    except BoardError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _post_out(post)


@router.post("/posts/{post_id}/comments", response_model=CommentOut)
def post_comment(
    post_id: int,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        comment = create_comment(db, post_id, current_user.id, payload.content)
    except BoardError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _comment_out(comment)


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    comments = list_comments(db, post_id)
    return [_comment_out(c) for c in comments]


@router.post("/comments/{comment_id}/like", response_model=LikeToggleOut)
def like_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        liked = toggle_comment_like(db, comment_id, current_user.id)
    except BoardError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return LikeToggleOut(liked=liked)
