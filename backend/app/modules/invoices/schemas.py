from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class InvoiceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    number: str
    order_id: UUID
    account_id: UUID
    status: str
    issue_date: date
    due_date: date
    total: Decimal
    amount_paid: Decimal
    overdue: bool
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
