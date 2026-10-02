from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.contacts.models import Contact
from app.modules.contacts.schemas import ContactCreate, ContactRead, ContactUpdate
from app.modules.contacts.service import ContactService
from app.modules.identity.dependencies import get_current_actor

router = APIRouter(prefix="/contacts", tags=["contacts"])


def get_contact_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ContactService:
    return ContactService(session)


@router.get("", response_model=Page[ContactRead])
async def list_contacts(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[ContactService, Depends(get_contact_service)],
    account_id: UUID | None = None,
) -> Page:
    return await service.list(actor, page, {"account_id": account_id})


@router.post("", response_model=ContactRead, status_code=201)
async def create_contact(
    payload: ContactCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ContactService, Depends(get_contact_service)],
) -> Contact:
    return await service.create(actor, payload)


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(
    contact_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ContactService, Depends(get_contact_service)],
) -> Contact:
    return await service.get(actor, contact_id)


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ContactService, Depends(get_contact_service)],
) -> Contact:
    return await service.update(actor, contact_id, payload)
