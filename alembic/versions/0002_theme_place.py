"""theme master table + place<->theme many-to-many (multi-label themes)

팀원이 제안한 구조를 그대로 반영: place.theme_code(단일 컬럼) 하나로는 "역사이면서 동시에
한류"처럼 장소 하나에 테마가 여러 개인 경우를 표현할 수 없어서, theme(마스터) + place_theme
(다대다 연결) 테이블을 추가한다. source/confidence 컬럼으로 규칙 기반(rule)/AI 라벨링(ai)/
수동 큐레이션(manual) 태그를 구분해서 관리할 수 있게 함.

원본 팀원 마이그레이션과 다른 점 (호환성 때문에 손본 부분):
- 백필을 MySQL 전용 "INSERT IGNORE" 대신 SQLAlchemy Core insert로 바꿔서 SQLite에서도
  그대로 검증 가능하게 함 (운영 DB는 MySQL이라 동작은 동일).
- theme_map에 FK를 추가하는 부분을 batch_alter_table로 감싸서 SQLite에서도 동작하게 함
  (SQLite는 기존 테이블에 FK를 직접 ALTER로 못 붙임 - Alembic 배치 모드가 표준 해결법).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


THEMES = [
    {"code": "sightseeing", "name": "관광지", "is_active": True},
    {"code": "culture", "name": "문화", "is_active": True},
    {"code": "festival", "name": "축제·공연·행사", "is_active": True},
    {"code": "course", "name": "여행코스", "is_active": True},
    {"code": "activity", "name": "레포츠·액티비티", "is_active": True},
    {"code": "lodging", "name": "숙박", "is_active": True},
    {"code": "shopping", "name": "쇼핑", "is_active": True},
    {"code": "food", "name": "음식", "is_active": True},
    {"code": "nature", "name": "자연", "is_active": True},
    {"code": "history", "name": "역사", "is_active": True},
    {"code": "hallyu", "name": "한류", "is_active": True},
    {"code": "etc", "name": "기타", "is_active": True},
]


def upgrade() -> None:
    op.create_table(
        "theme",
        sa.Column("code", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    theme_table = sa.table(
        "theme",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(theme_table, THEMES)

    op.create_table(
        "place_theme",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("place_id", sa.Integer, nullable=False),
        sa.Column("theme_code", sa.String(30), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="rule"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["place_id"], ["place.id"], name="fk_place_theme_place", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["theme_code"], ["theme.code"], name="fk_place_theme_theme", ondelete="RESTRICT"),
        sa.UniqueConstraint("place_id", "theme_code", name="uq_place_theme"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_place_theme_place_id", "place_theme", ["place_id"])
    op.create_index("ix_place_theme_theme_code", "place_theme", ["theme_code"])

    # theme_map은 지금 코드에서 실제로 안 쓰이는 테이블이지만(비어있음), 스키마 정합성을 위해
    # FK만 걸어둠. batch_alter_table로 감싸서 SQLite에서도 동작하게 함.
    with op.batch_alter_table("theme_map") as batch_op:
        batch_op.create_foreign_key(
            "fk_theme_map_theme", "theme", ["theme_code"], ["code"], ondelete="RESTRICT"
        )

    # 기존 place.theme_code 값을 place_theme로 백필 (source='rule')
    connection = op.get_bind()
    place_table = sa.table("place", sa.column("id", sa.Integer), sa.column("theme_code", sa.String))
    place_theme_table = sa.table(
        "place_theme",
        sa.column("place_id", sa.Integer),
        sa.column("theme_code", sa.String),
        sa.column("source", sa.String),
    )
    rows = connection.execute(
        sa.select(place_table.c.id, place_table.c.theme_code).where(
            place_table.c.theme_code.isnot(None), place_table.c.theme_code != ""
        )
    ).fetchall()
    if rows:
        connection.execute(
            place_theme_table.insert(),
            [{"place_id": r.id, "theme_code": r.theme_code, "source": "rule"} for r in rows],
        )


def downgrade() -> None:
    with op.batch_alter_table("theme_map") as batch_op:
        batch_op.drop_constraint("fk_theme_map_theme", type_="foreignkey")

    op.drop_index("ix_place_theme_theme_code", table_name="place_theme")
    op.drop_index("ix_place_theme_place_id", table_name="place_theme")
    op.drop_table("place_theme")
    op.drop_table("theme")
