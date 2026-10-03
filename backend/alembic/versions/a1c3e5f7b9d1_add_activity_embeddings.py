"""add activity embeddings

Revision ID: a1c3e5f7b9d1
Revises: 53682f83126a
Create Date: 2026-10-03 23:30:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa

from alembic import op

revision: str = "a1c3e5f7b9d1"
down_revision: str | None = "53682f83126a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HNSW_COSINE = {
    "postgresql_using": "hnsw",
    "postgresql_with": {"m": 16, "ef_construction": 64},
    "postgresql_ops": {"embedding": "vector_cosine_ops"},
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "activities",
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    )
    op.add_column("activities", sa.Column("embedding_model", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_activities_embedding_hnsw", "activities", ["embedding"], unique=False, **HNSW_COSINE
    )


def downgrade() -> None:
    op.drop_index("ix_activities_embedding_hnsw", table_name="activities", **HNSW_COSINE)
    op.drop_column("activities", "embedding_model")
    op.drop_column("activities", "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
