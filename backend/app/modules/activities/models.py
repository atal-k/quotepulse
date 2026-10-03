import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.context.embeddings import EMBEDDING_DIMENSIONS
from app.context.models import HNSW_COSINE_OPTIONS
from app.core.base import Base, TimestampMixin, UUIDPkMixin
from app.modules.activities.enums import ActivityType, EntityType, in_list_sql


class Activity(Base, UUIDPkMixin, TimestampMixin):
    """An interaction logged against one parent entity. `entity_type`/`entity_id` is a
    deliberate polymorphic reference with no DB-level FK (see ARCHITECTURE §5): the CHECK below
    guards the type, and the service confirms the parent exists and is visible to the actor.
    owner/team are inherited from the parent, so the parent's owner sees the whole thread."""

    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(f"entity_type IN {in_list_sql(EntityType)}", name="entity_type"),
        CheckConstraint(f"type IN {in_list_sql(ActivityType)}", name="type"),
        Index("ix_activities_entity_timeline", "entity_type", "entity_id", "occurred_at"),
        Index("ix_activities_embedding_hnsw", "embedding", **HNSW_COSINE_OPTIONS),
    )

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # Null until the process_activity job embeds it (Phase 2B); embedding_model records which
    # model produced the vector so a model change can be detected and re-embedded.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True
    )
