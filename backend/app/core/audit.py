import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base
from app.core.rbac import Actor


class AuditLog(Base):
    """Immutable. Written once via record(), same transaction as the mutation it describes.
    No update/delete — there is no API for either."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    # FKs added once the approvals / agent_runs modules exist (Phase 4).
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


async def record(
    session: AsyncSession,
    actor: Actor,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any],
    approval_id: uuid.UUID | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.user_id,
        actor_kind=actor.kind.value,
        agent_name=actor.agent_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        approval_id=approval_id,
    )
    session.add(entry)
    await session.flush()
    return entry
