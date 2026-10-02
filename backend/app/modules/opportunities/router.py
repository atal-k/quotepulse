from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.opportunities.models import Opportunity
from app.modules.opportunities.schemas import (
    OpportunityCreate,
    OpportunityRead,
    OpportunityStage,
    OpportunityUpdate,
)
from app.modules.opportunities.service import OpportunityService

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def get_opportunity_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpportunityService:
    return OpportunityService(session)


@router.get("", response_model=Page[OpportunityRead])
async def list_opportunities(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[OpportunityService, Depends(get_opportunity_service)],
    account_id: UUID | None = None,
    stage: OpportunityStage | None = None,
) -> Page:
    return await service.list(actor, page, {"account_id": account_id, "stage": stage})


@router.post("", response_model=OpportunityRead, status_code=201)
async def create_opportunity(
    payload: OpportunityCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OpportunityService, Depends(get_opportunity_service)],
) -> Opportunity:
    return await service.create(actor, payload)


@router.get("/{opportunity_id}", response_model=OpportunityRead)
async def get_opportunity(
    opportunity_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OpportunityService, Depends(get_opportunity_service)],
) -> Opportunity:
    return await service.get(actor, opportunity_id)


@router.patch("/{opportunity_id}", response_model=OpportunityRead)
async def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OpportunityService, Depends(get_opportunity_service)],
) -> Opportunity:
    return await service.update(actor, opportunity_id, payload)
