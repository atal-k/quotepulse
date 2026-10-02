from typing import Any

from sqlalchemy import select

from app.core.errors import Conflict, ValidationFailed
from app.core.rbac import Actor
from app.modules.base import CrudService
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreate, ProductUpdate

_NULLABLE_ON_UPDATE = {"category"}


class ProductService(CrudService[Product, ProductCreate, ProductUpdate]):
    model = Product
    resource = "products"
    entity_type = "product"
    owned = False

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        payload["sku"] = payload["sku"].strip().upper()
        payload["currency"] = payload["currency"].upper() if "currency" in payload else "INR"
        exists = await self.session.scalar(select(Product.id).where(Product.sku == payload["sku"]))
        if exists is not None:
            raise Conflict("A product with this SKU already exists.", {"sku": payload["sku"]})
        return payload

    async def authorize_update(self, actor: Actor, obj: Product, payload: dict[str, Any]) -> None:
        for field, value in payload.items():
            if value is None and field not in _NULLABLE_ON_UPDATE:
                raise ValidationFailed(f"{field} cannot be null.", {"field": field})
        if "currency" in payload:
            payload["currency"] = payload["currency"].upper()
        new_stock = payload.get("stock_qty", obj.stock_qty)
        if new_stock < obj.reserved_qty:
            raise Conflict(
                "Stock cannot be set below the quantity already reserved by orders.",
                {"stock_qty": str(new_stock), "reserved_qty": str(obj.reserved_qty)},
            )
