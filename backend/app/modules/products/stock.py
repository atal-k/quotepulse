"""Stock movements. Only the orders module calls these, and only inside its own transaction.

Every function locks the affected product rows with `SELECT ... FOR UPDATE`, in id order, so two
concurrent callers serialize on the same SKUs and cannot both reserve the last unit. Each change
is audited on the product row.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import Conflict
from app.core.rbac import Actor
from app.modules.products.models import Product


@dataclass(frozen=True)
class StockLine:
    product_id: UUID
    qty: Decimal


def _needed(lines: Sequence[StockLine]) -> dict[UUID, Decimal]:
    totals: dict[UUID, Decimal] = defaultdict(Decimal)
    for line in lines:
        totals[line.product_id] += line.qty
    return dict(totals)


async def _lock(session: AsyncSession, product_ids: list[UUID]) -> dict[UUID, Product]:
    stmt = (
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
        # Re-read the row after the lock is taken, so we see the committed value that the
        # previous lock-holder wrote rather than a stale copy already in this session.
        .execution_options(populate_existing=True)
    )
    return {p.id: p for p in (await session.execute(stmt)).scalars().all()}


async def reserve(session: AsyncSession, actor: Actor, lines: Sequence[StockLine]) -> None:
    needed = _needed(lines)
    products = await _lock(session, list(needed))
    shortages = [
        {
            "sku": products[pid].sku,
            "requested": str(qty),
            "available": str(products[pid].available_qty),
        }
        for pid, qty in needed.items()
        if products[pid].available_qty < qty
    ]
    if shortages:
        raise Conflict("Insufficient stock for one or more products.", {"shortages": shortages})
    for pid, qty in needed.items():
        product = products[pid]
        old = str(product.reserved_qty)
        product.reserved_qty += qty
        await _audit_stock(
            session, actor, product, "reserve", {"reserved_qty": [old, str(product.reserved_qty)]}
        )


async def release(session: AsyncSession, actor: Actor, lines: Sequence[StockLine]) -> None:
    needed = _needed(lines)
    products = await _lock(session, list(needed))
    for pid, qty in needed.items():
        product = products[pid]
        old = str(product.reserved_qty)
        product.reserved_qty -= qty
        await _audit_stock(
            session, actor, product, "release", {"reserved_qty": [old, str(product.reserved_qty)]}
        )


async def consume(session: AsyncSession, actor: Actor, lines: Sequence[StockLine]) -> None:
    """Goods physically leave the warehouse: stock and reservation both drop."""
    needed = _needed(lines)
    products = await _lock(session, list(needed))
    for pid, qty in needed.items():
        product = products[pid]
        old_stock, old_reserved = str(product.stock_qty), str(product.reserved_qty)
        product.stock_qty -= qty
        product.reserved_qty -= qty
        await _audit_stock(
            session,
            actor,
            product,
            "consume",
            {
                "stock_qty": [old_stock, str(product.stock_qty)],
                "reserved_qty": [old_reserved, str(product.reserved_qty)],
            },
        )


async def _audit_stock(
    session: AsyncSession,
    actor: Actor,
    product: Product,
    action: str,
    changes: dict[str, list[str]],
) -> None:
    await session.flush()
    await audit.record(session, actor, action, "product", product.id, changes)
