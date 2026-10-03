import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPkMixin
from app.modules.activities.enums import EntityType, in_list_sql


class Notification(Base, UUIDPkMixin, TimestampMixin):
    """A thin in-app feed item for one user. Visible only to its recipient, whatever their role."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            f"entity_type IS NULL OR entity_type IN {in_list_sql(EntityType)}",
            name="entity_type",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
