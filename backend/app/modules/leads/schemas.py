from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

LeadStatus = Literal["new", "contacted", "qualified", "converted", "disqualified"]


class Qualification(BaseModel):
    budget: str | None = Field(default=None, max_length=500)
    authority: str | None = Field(default=None, max_length=500)
    need: str | None = Field(default=None, max_length=500)
    timeline: str | None = Field(default=None, max_length=500)


class LeadCreate(BaseModel):
    # Leads always start as `new`; status only moves through the state machine afterwards.
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = None
    source: str | None = Field(default=None, max_length=50)
    score: int | None = Field(default=None, ge=0, le=100)
    qualification: Qualification | None = None
    # Manager/admin may assign a different owner/team on create; forced to self for reps.
    owner_id: UUID | None = None
    team_id: UUID | None = None


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = None
    source: str | None = Field(default=None, max_length=50)
    status: LeadStatus | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    qualification: Qualification | None = None
    # Reassignment is manager/admin only — service rejects this for reps.
    owner_id: UUID | None = None
    team_id: UUID | None = None


class LeadRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    company_name: str | None
    email: str | None
    phone: str | None
    source: str | None
    status: LeadStatus
    score: int | None
    qualification: Qualification | None
    converted_account_id: UUID | None
    converted_contact_id: UUID | None
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
