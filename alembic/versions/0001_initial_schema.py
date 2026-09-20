"""initial schema

app/models/*.py 전체를 반영한 첫 마이그레이션. 아직 운영 DB에 아무것도 배포된 적이
없는 상태(greenfield)라, 기존 테이블 + 프론트엔드 연동을 위해 새로 추가한 테이블/컬럼
(board_post.image_url/like_count/comment_count/place_id/rating, board_post_companion,
board_post_like, board_comment.like_count, board_comment_like)을 한 번에 담았다.

앞으로 모델을 바꿀 때는 이 파일을 손으로 고치지 말고:
    alembic revision --autogenerate -m "설명"
로 새 리비전을 추가할 것.

Revision ID: 0001
Revises:
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("nickname", sa.String(50), nullable=False),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_user_email"),
        sa.UniqueConstraint("nickname", name="uq_user_nickname"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "place",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("content_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("area_code", sa.String(10), nullable=True),
        sa.Column("mapx", sa.Float, nullable=True),
        sa.Column("mapy", sa.Float, nullable=True),
        sa.Column("first_image", sa.String(500), nullable=True),
        sa.Column("tel", sa.String(50), nullable=True),
        sa.Column("content_type_id", sa.String(10), nullable=True),
        sa.Column("cat1", sa.String(10), nullable=True),
        sa.Column("cat2", sa.String(10), nullable=True),
        sa.Column("cat3", sa.String(10), nullable=True),
        sa.Column("theme_code", sa.String(30), nullable=True),
        sa.Column("overview", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=True, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("content_id", name="uq_place_content_id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_place_area_code", "place", ["area_code"])
    op.create_index("ix_place_theme_code", "place", ["theme_code"])

    op.create_table(
        "theme_map",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("content_type_id", sa.String(10), nullable=False),
        sa.Column("cat1", sa.String(10), nullable=True),
        sa.Column("cat2", sa.String(10), nullable=True),
        sa.Column("cat3", sa.String(10), nullable=True),
        sa.Column("theme_code", sa.String(30), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "review",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.Integer, sa.ForeignKey("place.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_review_place_id", "review", ["place_id"])
    op.create_index("ix_review_user_id", "review", ["user_id"])
    op.create_index("ix_review_place_created", "review", ["place_id", "created_at"])

    op.create_table(
        "review_like",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.Integer, sa.ForeignKey("review.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("review_id", "user_id", name="uq_review_like_user"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_review_like_review_id", "review_like", ["review_id"])
    op.create_index("ix_review_like_user_id", "review_like", ["user_id"])

    op.create_table(
        "board_post",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("area_code", sa.String(10), nullable=True),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("place_id", sa.Integer, sa.ForeignKey("place.id"), nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_board_post_rating"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_board_post_user_id", "board_post", ["user_id"])
    op.create_index("ix_board_post_area_code", "board_post", ["area_code"])
    op.create_index("ix_board_post_category", "board_post", ["category"])
    op.create_index("ix_board_post_place_id", "board_post", ["place_id"])
    op.create_index("ix_board_post_list", "board_post", ["area_code", "category", "created_at"])

    op.create_table(
        "board_post_companion",
        sa.Column("post_id", sa.Integer, sa.ForeignKey("board_post.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("travelers_needed", sa.Integer, nullable=True),
        sa.Column("travelers_joined", sa.Integer, nullable=False, server_default="1"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "board_post_like",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Integer, sa.ForeignKey("board_post.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("post_id", "user_id", name="uq_board_post_like_user"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_board_post_like_post_id", "board_post_like", ["post_id"])
    op.create_index("ix_board_post_like_user_id", "board_post_like", ["user_id"])

    op.create_table(
        "board_comment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Integer, sa.ForeignKey("board_post.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_board_comment_post_id", "board_comment", ["post_id"])
    op.create_index("ix_board_comment_user_id", "board_comment", ["user_id"])

    op.create_table(
        "board_comment_like",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("comment_id", sa.Integer, sa.ForeignKey("board_comment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("comment_id", "user_id", name="uq_board_comment_like_user"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_board_comment_like_comment_id", "board_comment_like", ["comment_id"])
    op.create_index("ix_board_comment_like_user_id", "board_comment_like", ["user_id"])


def downgrade() -> None:
    op.drop_table("board_comment_like")
    op.drop_table("board_comment")
    op.drop_table("board_post_like")
    op.drop_table("board_post_companion")
    op.drop_table("board_post")
    op.drop_table("review_like")
    op.drop_table("review")
    op.drop_table("theme_map")
    op.drop_table("place")
    op.drop_table("user")
