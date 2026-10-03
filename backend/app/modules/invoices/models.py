import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPkMixin

OPEN_STATUSES = ("issued", "partially_paid")


class Invoice(Base, UUIDPkMixin, TimestampMixin):
    """Issued when its order ships. `overdue` is derived from the due date, not stored."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint("amount_paid >= 0 AND amount_paid <= total", name="amount_paid_in_range"),
    )

    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="issued", index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0")
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True
    )

    @property
    def overdue(self) -> bool:
        return self.status in OPEN_STATUSES and self.due_date < datetime.now(UTC).date()
