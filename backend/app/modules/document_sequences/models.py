from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, UUIDPkMixin


class DocumentSequence(Base, UUIDPkMixin):
    """One counter per (kind, year). Only ever advanced through `service.next_number`."""

    __tablename__ = "document_sequences"
    __table_args__ = (
        UniqueConstraint("kind", "year"),
        CheckConstraint("last_value >= 0", name="last_value_non_negative"),
    )

    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
