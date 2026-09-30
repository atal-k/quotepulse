from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

AccountStatus = Literal["prospect", "customer", "inactive"]


class AccountBase(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    tax_id: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    status: AccountStatus = "prospect"
    credit_limit: Decimal | None = None
    payment_terms_days: int | None = None


class AccountCreate(AccountBase):
    # Manager/admin may assign a different owner/team on create; ignored (forced to self) for reps.
    owner_id: UUID | None = None
    team_id: UUID | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    industry: str | None = None
    tax_id: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    status: AccountStatus | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int | None = None
    # Reassignment is manager/admin only — service rejects this for reps.
    owner_id: UUID | None = None
    team_id: UUID | None = None


class AccountRead(AccountBase):
    model_config = {"from_attributes": True}

    id: UUID
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
