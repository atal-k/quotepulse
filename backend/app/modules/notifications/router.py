from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.notifications.models import Notification
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    kind: str
    title: str
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


def get_notification_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationService:
    return NotificationService(session)


@router.get("", response_model=Page[NotificationRead])
async def list_notifications(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    unread_only: bool = False,
) -> Page:
    return await service.list(actor, page, unread_only)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> Notification:
    return await service.mark_read(actor, notification_id)
