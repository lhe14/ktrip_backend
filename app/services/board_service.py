"""
게시판 글/댓글 비즈니스 로직.
"""

import datetime

from sqlalchemy.orm import Session

from app.models.board import (
    BoardPost,
    BoardPostCompanion,
    BoardPostLike,
    BoardComment,
    BoardCommentLike,
    BoardCategory,
)
from app.models.place import Place


class BoardError(Exception):
    """존재하지 않는 글 등 게시판 관련 오류"""


def create_post(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    category: str,
    area_code: str | None,
    image_url: str | None = None,
    place_id: int | None = None,
    rating: int | None = None,
    companion_destination: str | None = None,
    companion_start_date: datetime.date | None = None,
    companion_end_date: datetime.date | None = None,
    companion_travelers_needed: int | None = None,
) -> BoardPost:
    if category not in {c.value for c in BoardCategory}:
        raise BoardError(f"알 수 없는 카테고리입니다: {category}")

    if category == BoardCategory.REVIEW.value:
        if place_id is None or rating is None:
            raise BoardError("REVIEW 게시글은 place_id와 rating이 필요합니다")
        if not (1 <= rating <= 5):
            raise BoardError("평점은 1~5 사이여야 합니다")
        if db.query(Place).filter(Place.id == place_id).first() is None:
            raise BoardError("존재하지 않는 장소입니다")
    else:
        place_id = None
        rating = None

    if category == BoardCategory.COMPANION.value and not companion_destination:
        raise BoardError("COMPANION 게시글은 destination이 필요합니다")

    post = BoardPost(
        user_id=user_id,
        title=title,
        content=content,
        category=category,
        area_code=area_code,
        image_url=image_url,
        place_id=place_id,
        rating=rating,
    )
    db.add(post)
    db.flush()  # post.id 확보 (companion 행에서 FK로 참조하기 위함)

    if category == BoardCategory.COMPANION.value:
        db.add(
            BoardPostCompanion(
                post_id=post.id,
                destination=companion_destination,
                start_date=companion_start_date,
                end_date=companion_end_date,
                travelers_needed=companion_travelers_needed,
            )
        )

    db.commit()
    db.refresh(post)
    return post


def list_posts(
    db: Session,
    area_code: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[BoardPost]:
    query = db.query(BoardPost)
    if area_code:
        query = query.filter(BoardPost.area_code == area_code)
    if category:
        query = query.filter(BoardPost.category == category)

    return query.order_by(BoardPost.created_at.desc()).offset(offset).limit(limit).all()


def get_post(db: Session, post_id: int) -> BoardPost:
    post = db.query(BoardPost).filter(BoardPost.id == post_id).first()
    if post is None:
        raise BoardError("존재하지 않는 게시글입니다")
    return post


def create_comment(db: Session, post_id: int, user_id: int, content: str) -> BoardComment:
    post = get_post(db, post_id)  # 존재 확인 (없으면 BoardError 발생)

    comment = BoardComment(post_id=post_id, user_id=user_id, content=content)
    db.add(comment)
    post.comment_count += 1
    db.commit()
    db.refresh(comment)
    return comment


def list_comments(db: Session, post_id: int) -> list[BoardComment]:
    return (
        db.query(BoardComment)
        .filter(BoardComment.post_id == post_id)
        .order_by(BoardComment.created_at.asc())
        .all()
    )


def toggle_post_like(db: Session, post_id: int, user_id: int) -> bool:
    """게시글 좋아요 토글. 반환값 True=이번 호출로 좋아요가 눌린 상태, False=취소된 상태."""
    post = get_post(db, post_id)

    existing = (
        db.query(BoardPostLike)
        .filter(BoardPostLike.post_id == post_id, BoardPostLike.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        post.like_count = max(post.like_count - 1, 0)
        liked_now = False
    else:
        db.add(BoardPostLike(post_id=post_id, user_id=user_id))
        post.like_count += 1
        liked_now = True

    db.commit()
    return liked_now


def toggle_comment_like(db: Session, comment_id: int, user_id: int) -> bool:
    """댓글 좋아요 토글. 반환값 True=이번 호출로 좋아요가 눌린 상태, False=취소된 상태."""
    comment = db.query(BoardComment).filter(BoardComment.id == comment_id).first()
    if comment is None:
        raise BoardError("존재하지 않는 댓글입니다")

    existing = (
        db.query(BoardCommentLike)
        .filter(BoardCommentLike.comment_id == comment_id, BoardCommentLike.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        comment.like_count = max(comment.like_count - 1, 0)
        liked_now = False
    else:
        db.add(BoardCommentLike(comment_id=comment_id, user_id=user_id))
        comment.like_count += 1
        liked_now = True

    db.commit()
    return liked_now
