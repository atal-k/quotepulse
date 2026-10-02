from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OpportunityStage = Literal["discovery", "proposal", "negotiation", "won", "lost"]


class OpportunityCreate(BaseModel):
    # Opportunities always start in `discovery`; owner/team come from the account.
    account_id: UUID
    contact_id: UUID | None = None
    lead_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    requirements: str | None = Field(default=None, max_length=10000)


class OpportunityUpdate(BaseModel):
    # account_id and lead_id are immutable links.
    contact_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    stage: OpportunityStage | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    requirements: str | None = Field(default=None, max_length=10000)
    lost_reason: str | None = Field(default=None, min_length=1, max_length=500)
    # Reassignment is manager/admin only — service rejects this for reps.
    owner_id: UUID | None = None
    team_id: UUID | None = None


class OpportunityRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    account_id: UUID
    contact_id: UUID | None
    lead_id: UUID | None
    name: str
    stage: OpportunityStage
    amount: Decimal
    currency: str
    probability: int | None
    expected_close_date: date | None
    requirements: str | None
    lost_reason: str | None
    closed_at: datetime | None
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
