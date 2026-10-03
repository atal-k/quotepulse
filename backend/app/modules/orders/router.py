import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.orders.models import Order
from app.modules.orders.schemas import OrderRead, OrderUpdate
from app.modules.orders.service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_service(session: Annotated[AsyncSession, Depends(get_session)]) -> OrderService:
    return OrderService(session)


@router.get("", response_model=Page[OrderRead])
async def list_orders(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[OrderService, Depends(get_order_service)],
    account_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page:
    return await service.list(actor, page, {"account_id": account_id, "status": status})


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.get(actor, order_id)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.update(actor, order_id, payload)


@router.post("/{order_id}/process", response_model=OrderRead)
async def process_order(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.process(actor, order_id)


@router.post("/{order_id}/ship", response_model=OrderRead)
async def ship_order(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.ship(actor, order_id)


@router.post("/{order_id}/deliver", response_model=OrderRead)
async def deliver_order(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.deliver(actor, order_id)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> Order:
    return await service.cancel(actor, order_id)
