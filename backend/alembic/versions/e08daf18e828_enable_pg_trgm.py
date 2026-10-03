"""enable pg_trgm

Revision ID: e08daf18e828
Revises: ad4b3589c571
Create Date: 2026-10-03 16:01:21.978267

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e08daf18e828"
down_revision: str | None = "ad4b3589c571"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
