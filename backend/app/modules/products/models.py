from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPkMixin


class Product(Base, UUIDPkMixin, TimestampMixin):
    """Global catalog row: no owner_id/team_id, so no row-level visibility. `reserved_qty` is
    only ever moved by the orders module (stock reservation), never through the catalog API."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_qty >= 0", name="stock_qty_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="reserved_qty_non_negative"),
        CheckConstraint("reserved_qty <= stock_qty", name="reserved_within_stock"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("tax_pct >= 0 AND tax_pct <= 100", name="tax_pct_range"),
        CheckConstraint("reorder_level >= 0", name="reorder_level_non_negative"),
        CheckConstraint("min_order_qty > 0", name="min_order_qty_positive"),
        CheckConstraint("lead_time_days >= 0", name="lead_time_days_non_negative"),
    )

    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    tax_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("18"))
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    reserved_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    min_order_qty: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("1")
    )
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @property
    def available_qty(self) -> Decimal:
        return self.stock_qty - self.reserved_qty
