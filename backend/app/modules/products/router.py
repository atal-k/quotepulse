from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.rbac import Actor
from app.modules.identity.dependencies import get_current_actor
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreate, ProductRead, ProductUpdate
from app.modules.products.service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def get_product_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ProductService:
    return ProductService(session)


@router.get("", response_model=Page[ProductRead])
async def list_products(
    actor: Annotated[Actor, Depends(get_current_actor)],
    page: Annotated[PageParams, Depends(page_params)],
    service: Annotated[ProductService, Depends(get_product_service)],
    category: str | None = None,
    is_active: bool | None = None,
) -> Page:
    return await service.list(actor, page, {"category": category, "is_active": is_active})


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(
    payload: ProductCreate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    return await service.create(actor, payload)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    return await service.get(actor, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    actor: Annotated[Actor, Depends(get_current_actor)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    return await service.update(actor, product_id, payload)
