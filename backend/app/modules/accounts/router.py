from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate, AccountRead, AccountUpdate
from app.modules.accounts.service import AccountService
from app.modules.identity.dependencies import get_current_actor

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AccountService:
    return AccountService(session)


@router.get("", response_model=Page[AccountRead])
async def list_accounts(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[AccountService, Depends(get_account_service)],
) -> Page:
    # Deliberately unparameterized: annotating -> Page[Account] here would make FastAPI's
    # signature inspection construct that pydantic generic submodel eagerly, and pydantic
    # can't build a schema for the raw ORM Account class (only response_model=Page[AccountRead]
    # needs to, and that one's fine since AccountRead is pydantic-compatible).
    return await service.list(actor, page)


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    payload: AccountCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[AccountService, Depends(get_account_service)],
) -> Account:
    return await service.create(actor, payload)


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[AccountService, Depends(get_account_service)],
) -> Account:
    return await service.get(actor, account_id)


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[AccountService, Depends(get_account_service)],
) -> Account:
    return await service.update(actor, account_id, payload)
