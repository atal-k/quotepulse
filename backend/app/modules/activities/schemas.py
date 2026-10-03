from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.activities.enums import ActivityType, EntityType


class ActivityCreate(BaseModel):
    type: ActivityType
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=10000)
    occurred_at: datetime | None = None
    entity_type: EntityType
    entity_id: UUID
    meta: dict[str, Any] | None = None


class ActivityUpdate(BaseModel):
    # The parent entity is immutable: an activity stays on the thread it was logged against.
    type: ActivityType | None = None
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=10000)
    occurred_at: datetime | None = None
    meta: dict[str, Any] | None = None


class ActivityRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    type: ActivityType
    subject: str | None
    body: str | None
    occurred_at: datetime
    entity_type: EntityType
    entity_id: UUID
    created_by_kind: str
    meta: dict[str, Any] | None
    owner_id: UUID
    team_id: UUID | None
    created_at: datetime
    updated_at: datetime
