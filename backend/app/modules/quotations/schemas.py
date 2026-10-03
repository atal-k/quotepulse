from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.rbac import Role


class QuotationItemIn(BaseModel):
    # Price and tax come from the catalog on the server; the client only chooses what and how much.
    product_id: UUID
    qty: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    discount_pct: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )


class QuotationCreate(BaseModel):
    account_id: UUID
    opportunity_id: UUID | None = None
    valid_until: date | None = None
    terms: str | None = Field(default=None, max_length=5000)
    items: list[QuotationItemIn] = Field(min_length=1, max_length=100)


class QuotationUpdate(BaseModel):
    # Draft-only: the service rejects edits to any other status (revise instead).
    valid_until: date | None = None
    terms: str | None = Field(default=None, max_length=5000)
    items: list[QuotationItemIn] | None = Field(default=None, min_length=1, max_length=100)


class QuotationItemRead(BaseModel):
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


class QuotationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    number: str
    version: int
    status: str
    account_id: UUID
    opportunity_id: UUID | None
    valid_until: date | None
    terms: str | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    created_by_kind: str
    approver_role: Role | None
    owner_id: UUID
    team_id: UUID | None
    items: list[QuotationItemRead]
    created_at: datetime
    updated_at: datetime
