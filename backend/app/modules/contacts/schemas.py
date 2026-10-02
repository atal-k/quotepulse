from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class ContactCreate(BaseModel):
    account_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = Field(default=None, max_length=100)
    is_primary: bool = False


class ContactUpdate(BaseModel):
    # account_id is immutable and owner/team follow the account, so neither is updatable here.
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = Field(default=None, max_length=100)
    is_primary: bool | None = None


class ContactRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    account_id: UUID
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    job_title: str | None
    is_primary: bool
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
