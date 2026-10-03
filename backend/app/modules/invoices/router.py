import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.invoices.models import Invoice
from app.modules.invoices.schemas import InvoiceRead, PaymentCreate
from app.modules.invoices.service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])


def get_invoice_service(session: Annotated[AsyncSession, Depends(get_session)]) -> InvoiceService:
    return InvoiceService(session)


@router.get("", response_model=Page[InvoiceRead])
async def list_invoices(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    account_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page:
    return await service.list(actor, page, {"account_id": account_id, "status": status})


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> Invoice:
    return await service.get(actor, invoice_id)


@router.post("/{invoice_id}/payments", response_model=InvoiceRead)
async def record_payment(
    invoice_id: uuid.UUID,
    payload: PaymentCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> Invoice:
    return await service.record_payment(actor, invoice_id, payload)


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
async def void_invoice(
    invoice_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
) -> Invoice:
    return await service.void(actor, invoice_id)
