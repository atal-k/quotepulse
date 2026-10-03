from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import User
from tests.modules.sales_helpers import accepted_quote

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _only_order(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    (order,) = (await client.get("/api/v1/orders", headers=headers)).json()["items"]
    return order


async def _act(client: AsyncClient, headers: dict[str, str], order_id: str, action: str) -> Any:
    return await client.post(f"/api/v1/orders/{order_id}/{action}", headers=headers)


async def _product(client: AsyncClient, headers: dict[str, str], product_id: str) -> dict[str, Any]:
    return (await client.get(f"/api/v1/products/{product_id}", headers=headers)).json()


async def test_acceptance_creates_an_order_that_reserves_stock(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    _, product = await accepted_quote(client, headers, catalog_headers, stock="10", qty="3")

    order = await _only_order(client, headers)

    assert order["number"].startswith(f"SO-{datetime.now(UTC).year}-")
    assert (order["status"], order["owner_id"]) == ("confirmed", str(rep.id))
    assert Decimal(order["total"]) == Decimal("354.00")
    assert Decimal(order["items"][0]["qty"]) == 3
    stock = await _product(client, headers, product["id"])
    assert (Decimal(stock["stock_qty"]), Decimal(stock["reserved_qty"])) == (10, 3)


async def test_shipping_consumes_stock_and_issues_an_invoice_on_payment_terms(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    _, product = await accepted_quote(
        client, headers, catalog_headers, stock="10", qty="3", payment_terms_days=45
    )
    order = await _only_order(client, headers)

    assert (await _act(client, headers, order["id"], "process")).json()["status"] == "processing"
    shipped = await _act(client, headers, order["id"], "ship")

    assert shipped.json()["status"] == "shipped"
    stock = await _product(client, headers, product["id"])
    assert (Decimal(stock["stock_qty"]), Decimal(stock["reserved_qty"])) == (7, 0)
    (invoice,) = (await client.get("/api/v1/invoices", headers=headers)).json()["items"]
    assert invoice["number"].startswith("INV-")
    assert invoice["status"] == "issued"
    assert Decimal(invoice["total"]) == Decimal("354.00")
    issued, due = date.fromisoformat(invoice["issue_date"]), date.fromisoformat(invoice["due_date"])
    assert (due - issued).days == 45


async def test_delivery_follows_shipping_and_order_moves_are_checked(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    await accepted_quote(client, headers, catalog_headers)
    order = await _only_order(client, headers)

    too_early = await _act(client, headers, order["id"], "deliver")
    assert too_early.status_code == 409
    await _act(client, headers, order["id"], "process")
    await _act(client, headers, order["id"], "ship")
    delivered = await _act(client, headers, order["id"], "deliver")

    assert delivered.json()["status"] == "delivered"
    after_ship_cancel = await _act(client, headers, order["id"], "cancel")
    assert after_ship_cancel.status_code == 409


async def test_cancelling_before_shipping_releases_the_reservation(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    _, product = await accepted_quote(client, headers, catalog_headers, stock="10", qty="4")
    order = await _only_order(client, headers)

    cancelled = await _act(client, headers, order["id"], "cancel")

    assert cancelled.json()["status"] == "cancelled"
    stock = await _product(client, headers, product["id"])
    assert (Decimal(stock["stock_qty"]), Decimal(stock["reserved_qty"])) == (10, 0)


async def test_shipping_writes_audit_rows_on_the_product(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    _, product = await accepted_quote(client, headers, catalog_headers, qty="2")
    order = await _only_order(client, headers)
    await _act(client, headers, order["id"], "process")
    await _act(client, headers, order["id"], "ship")

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "product", AuditLog.entity_id == UUID(product["id"])
    )
    actions = [e.action for e in (await session.execute(stmt)).scalars().all()]
    assert "reserve" in actions and "consume" in actions


async def test_only_logistics_fields_are_editable(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    await accepted_quote(client, headers, catalog_headers)
    order = await _only_order(client, headers)

    response = await client.patch(
        f"/api/v1/orders/{order['id']}",
        json={
            "shipping_address": "Plot 4, MIDC, Pune",
            "total": "1",
            "expected_delivery_date": "2026-11-01",
        },
        headers=headers,
    )

    body = response.json()
    assert body["shipping_address"] == "Plot 4, MIDC, Pune"
    assert body["expected_delivery_date"] == "2026-11-01"
    assert Decimal(body["total"]) == Decimal("354.00")


async def test_orders_are_visible_only_to_their_scope(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    await accepted_quote(client, auth_headers(rep_a), catalog_headers)
    order = await _only_order(client, auth_headers(rep_a))

    assert (
        await client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers(rep_b))
    ).status_code == 404
    assert (await client.get("/api/v1/orders", headers=auth_headers(rep_b))).json()["total"] == 0
