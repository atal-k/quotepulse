import uuid
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.context.embeddings import EMBEDDING_DIMENSIONS
from app.context.enums import DuplicateEntityType, DuplicateStatus, DuplicateType
from app.core.base import Base, TimestampMixin, UUIDPkMixin
from app.modules.activities.enums import in_list_sql

HNSW_COSINE_OPTIONS = {
    "postgresql_using": "hnsw",
    "postgresql_with": {"m": 16, "ef_construction": 64},
    "postgresql_ops": {"embedding": "vector_cosine_ops"},
}


class KbDocument(Base, UUIDPkMixin, TimestampMixin):
    """A company-wide reference document (pricing policy, product sheet). Deliberately has no
    owner_id/team_id: it is not user-owned data. Readable by any active actor; written only by
    the ingest job (ARCHITECTURE §7)."""

    __tablename__ = "kb_documents"

    source_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class KbChunk(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        Index(
            "ix_kb_chunks_embedding_hnsw",
            "embedding",
            **HNSW_COSINE_OPTIONS,
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)


class DuplicateCandidate(Base, UUIDPkMixin, TimestampMixin):
    """A suspected duplicate pair surfaced by entity resolution. Never auto-merged: a merge is a
    gated action (CLAUDE §2.8). The pair is stored ordered (a < b) so each pair is one row."""

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        CheckConstraint(f"type IN {in_list_sql(DuplicateType)}", name="type"),
        CheckConstraint(f"entity_type IN {in_list_sql(DuplicateEntityType)}", name="entity_type"),
        CheckConstraint(f"status IN {in_list_sql(DuplicateStatus)}", name="status"),
        CheckConstraint("entity_a_id < entity_b_id", name="pair_ordered"),
        UniqueConstraint("type", "entity_type", "entity_a_id", "entity_b_id"),
    )

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DuplicateStatus.OPEN)

    # Denormalized from the entities so visibility_clause() applies without a join.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True
    )
