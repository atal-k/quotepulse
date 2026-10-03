"""add duplicate candidates

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-10-03 23:32:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3e5a7b9d1f3"
down_revision: str | None = "b2d4f6a8c0e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_candidates",
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_a_id", sa.UUID(), nullable=False),
        sa.Column("entity_b_id", sa.UUID(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('account', 'contact', 'lead')",
            name=op.f("ck_duplicate_candidates_entity_type"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'dismissed')", name=op.f("ck_duplicate_candidates_status")
        ),
        sa.CheckConstraint("type IN ('fuzzy_name')", name=op.f("ck_duplicate_candidates_type")),
        sa.CheckConstraint(
            "entity_a_id < entity_b_id", name=op.f("ck_duplicate_candidates_pair_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_duplicate_candidates_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_duplicate_candidates_team_id_teams")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_candidates")),
        sa.UniqueConstraint(
            "type",
            "entity_type",
            "entity_a_id",
            "entity_b_id",
            name=op.f("uq_duplicate_candidates_type"),
        ),
    )
    op.create_index(
        op.f("ix_duplicate_candidates_owner_id"), "duplicate_candidates", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_duplicate_candidates_team_id"), "duplicate_candidates", ["team_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_duplicate_candidates_team_id"), table_name="duplicate_candidates")
    op.drop_index(op.f("ix_duplicate_candidates_owner_id"), table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")
