from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.activities.enums import EntityType
from app.modules.activities.models import Activity
from app.modules.activities.schemas import ActivityCreate, ActivityRead, ActivityUpdate
from app.modules.activities.service import ActivityService
from app.modules.identity.dependencies import get_current_actor

router = APIRouter(prefix="/activities", tags=["activities"])


def get_activity_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ActivityService:
    return ActivityService(session)


@router.get("", response_model=Page[ActivityRead])
async def list_activities(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
) -> Page:
    """Pass entity_type + entity_id to read one record's thread."""
    return await service.list(actor, page, {"entity_type": entity_type, "entity_id": entity_id})


@router.post("", response_model=ActivityRead, status_code=201)
async def create_activity(
    payload: ActivityCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
) -> Activity:
    return await service.create(actor, payload)


@router.get("/{activity_id}", response_model=ActivityRead)
async def get_activity(
    activity_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
) -> Activity:
    return await service.get(actor, activity_id)


@router.patch("/{activity_id}", response_model=ActivityRead)
async def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
) -> Activity:
    return await service.update(actor, activity_id, payload)
