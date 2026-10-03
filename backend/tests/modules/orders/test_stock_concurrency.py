"""Two transactions race for the last unit of a SKU. Uses real committed transactions on separate
connections (the SAVEPOINT harness shares one connection and cannot show a race), so the product
row is created and removed here explicitly."""

import asyncio
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.audit import AuditLog
from app.core.errors import Conflict
from app.core.rbac import Actor, Role
from app.modules.products.models import Product
from app.modules.products.stock import StockLine, reserve


async def test_two_concurrent_reservations_of_the_last_unit_only_one_succeeds(
    test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    actor = Actor(user_id=uuid4(), role=Role.ADMIN, team_id=None)

    async with factory() as setup, setup.begin():
        product = Product(
            sku=f"RACE-{uuid4().hex[:8].upper()}",
            name="Last unit",
            unit_price=100,
            tax_pct=18,
            stock_qty=1,
            reserved_qty=0,
        )
        setup.add(product)
        await setup.flush()
        product_id = product.id

    async def attempt() -> str:
        async with factory() as session, session.begin():
            try:
                await reserve(session, actor, [StockLine(product_id=product_id, qty=1)])
                await asyncio.sleep(0.3)  # hold the row lock long enough for the rival to queue
                return "reserved"
            except Conflict:
                return "conflict"

    try:
        outcomes = await asyncio.gather(attempt(), attempt())

        assert sorted(outcomes) == ["conflict", "reserved"]
        async with factory() as check:
            reserved = (
                await check.execute(
                    text("SELECT reserved_qty FROM products WHERE id = :id"), {"id": product_id}
                )
            ).scalar_one()
            assert reserved == 1
    finally:
        async with factory() as cleanup, cleanup.begin():
            await cleanup.execute(delete(AuditLog).where(AuditLog.entity_id == product_id))
            await cleanup.execute(delete(Product).where(Product.id == product_id))
