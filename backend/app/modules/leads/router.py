from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.leads.conversion import LeadConversionService
from app.modules.leads.models import Lead
from app.modules.leads.schemas import (
    LeadConvert,
    LeadConvertResult,
    LeadCreate,
    LeadRead,
    LeadStatus,
    LeadUpdate,
)
from app.modules.leads.service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


def get_lead_service(session: Annotated[AsyncSession, Depends(get_session)]) -> LeadService:
    return LeadService(session)


@router.get("", response_model=Page[LeadRead])
async def list_leads(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[LeadService, Depends(get_lead_service)],
    status: LeadStatus | None = None,
    source: str | None = None,
) -> Page:
    return await service.list(actor, page, {"status": status, "source": source})


@router.post("", response_model=LeadRead, status_code=201)
async def create_lead(
    payload: LeadCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> Lead:
    return await service.create(actor, payload)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> Lead:
    return await service.get(actor, lead_id)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[LeadService, Depends(get_lead_service)],
) -> Lead:
    return await service.update(actor, lead_id, payload)


@router.post("/{lead_id}/convert", response_model=LeadConvertResult)
async def convert_lead(
    lead_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: LeadConvert | None = None,
) -> LeadConvertResult:
    return await LeadConversionService(session).convert(actor, lead_id, payload or LeadConvert())
