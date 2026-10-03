from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class OrderUpdate(BaseModel):
    # Only logistics details are editable; quantities, prices and totals are fixed at acceptance.
    shipping_address: str | None = Field(default=None, max_length=500)
    expected_delivery_date: date | None = None


class OrderItemRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    position: int
    product_id: UUID
    description: str
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    tax_pct: Decimal
    line_total: Decimal


class OrderRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    number: str
    quotation_id: UUID
    account_id: UUID
    status: str
    shipping_address: str | None
    expected_delivery_date: date | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    owner_id: UUID
    team_id: UUID | None
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime
