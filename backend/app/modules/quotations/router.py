import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.quotations.models import Quotation
from app.modules.quotations.schemas import QuotationCreate, QuotationRead, QuotationUpdate
from app.modules.quotations.service import QuotationService

router = APIRouter(prefix="/quotations", tags=["quotations"])


def get_quotation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> QuotationService:
    return QuotationService(session)


@router.get("", response_model=Page[QuotationRead])
async def list_quotations(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
    account_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page:
    return await service.list(actor, page, {"account_id": account_id, "status": status})


@router.post("", response_model=QuotationRead, status_code=201)
async def create_quotation(
    payload: QuotationCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.create(actor, payload)


@router.get("/{quotation_id}", response_model=QuotationRead)
async def get_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.get(actor, quotation_id)


@router.patch("/{quotation_id}", response_model=QuotationRead)
async def update_quotation(
    quotation_id: uuid.UUID,
    payload: QuotationUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.update(actor, quotation_id, payload)


@router.post("/{quotation_id}/submit", response_model=QuotationRead)
async def submit_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.submit(actor, quotation_id)


@router.post("/{quotation_id}/approve", response_model=QuotationRead)
async def approve_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.approve(actor, quotation_id)


@router.post("/{quotation_id}/return-for-edit", response_model=QuotationRead)
async def return_for_edit_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.return_for_edit(actor, quotation_id)


@router.post("/{quotation_id}/send", response_model=QuotationRead)
async def send_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.send(actor, quotation_id)


@router.post("/{quotation_id}/accept", response_model=QuotationRead)
async def accept_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.accept(actor, quotation_id)


@router.post("/{quotation_id}/decline", response_model=QuotationRead)
async def decline_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.decline(actor, quotation_id)


@router.post("/{quotation_id}/expire", response_model=QuotationRead)
async def expire_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.expire(actor, quotation_id)


@router.post("/{quotation_id}/revise", response_model=QuotationRead)
async def revise_quotation(
    quotation_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[QuotationService, Depends(get_quotation_service)],
) -> Quotation:
    return await service.revise(actor, quotation_id)
