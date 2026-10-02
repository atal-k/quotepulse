from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(default="pcs", min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    tax_pct: Decimal = Field(default=Decimal("18"), ge=0, le=100, max_digits=5, decimal_places=2)
    stock_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    min_order_qty: Decimal = Field(default=Decimal("1"), gt=0, max_digits=14, decimal_places=3)
    lead_time_days: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductUpdate(BaseModel):
    # sku is the catalog key quoted on documents, so it is immutable; reserved_qty is owned by
    # the orders module.
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax_pct: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    stock_qty: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    reorder_level: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    min_order_qty: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    lead_time_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    sku: str
    name: str
    category: str | None
    unit: str
    unit_price: Decimal
    currency: str
    tax_pct: Decimal
    stock_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal
    reorder_level: Decimal
    min_order_qty: Decimal
    lead_time_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
