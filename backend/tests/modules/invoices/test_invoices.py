from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User
from app.modules.invoices.models import Invoice
from tests.modules.sales_helpers import accepted_quote

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _shipped_invoice(
    client: AsyncClient,
    headers: dict[str, str],
    catalog_headers: dict[str, str],
    **quote_fields: Any,
) -> dict[str, Any]:
    await accepted_quote(client, headers, catalog_headers, **quote_fields)
    orders = (await client.get("/api/v1/orders", headers=headers)).json()["items"]
    (order,) = [o for o in orders if o["status"] == "confirmed"]
    await client.post(f"/api/v1/orders/{order['id']}/process", headers=headers)
    await client.post(f"/api/v1/orders/{order['id']}/ship", headers=headers)
    invoices = (await client.get("/api/v1/invoices", headers=headers)).json()["items"]
    (invoice,) = [i for i in invoices if i["order_id"] == order["id"]]
    return invoice


async def _pay(client: AsyncClient, headers: dict[str, str], invoice_id: str, amount: str) -> Any:
    return await client.post(
        f"/api/v1/invoices/{invoice_id}/payments", json={"amount": amount}, headers=headers
    )


async def test_due_date_defaults_to_thirty_days_when_terms_are_unset(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    invoice = await _shipped_invoice(client, auth_headers(rep), catalog_headers)

    issued, due = date.fromisoformat(invoice["issue_date"]), date.fromisoformat(invoice["due_date"])
    assert (due - issued).days == 30


async def test_payments_move_through_partially_paid_to_paid(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    invoice = await _shipped_invoice(client, headers, catalog_headers)

    partial = await _pay(client, headers, invoice["id"], "100.00")
    assert partial.json()["status"] == "partially_paid"
    assert Decimal(partial.json()["amount_paid"]) == Decimal("100.00")

    settled = await _pay(client, headers, invoice["id"], "254.00")
    assert settled.json()["status"] == "paid"


async def test_overpayment_and_payment_on_a_settled_invoice_are_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    invoice = await _shipped_invoice(client, headers, catalog_headers)

    over = await _pay(client, headers, invoice["id"], "354.01")
    assert over.status_code == 422
    assert over.json()["error"]["details"] == {"outstanding": "354.00"}

    await _pay(client, headers, invoice["id"], "354.00")
    again = await _pay(client, headers, invoice["id"], "1.00")
    assert again.status_code == 409


async def test_only_an_unpaid_issued_invoice_can_be_voided(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    unpaid = await _shipped_invoice(client, headers, catalog_headers)
    voided = await client.post(f"/api/v1/invoices/{unpaid['id']}/void", headers=headers)
    assert voided.json()["status"] == "void"

    other = await _shipped_invoice(client, headers, catalog_headers)
    await _pay(client, headers, other["id"], "10.00")
    refused = await client.post(f"/api/v1/invoices/{other['id']}/void", headers=headers)
    assert refused.status_code == 409


async def test_overdue_is_derived_from_the_due_date(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    invoice = await _shipped_invoice(client, headers, catalog_headers)
    assert invoice["overdue"] is False

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    await session.execute(
        update(Invoice).where(Invoice.id == UUID(invoice["id"])).values(due_date=yesterday)
    )
    late = (await client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)).json()
    assert late["overdue"] is True

    await _pay(client, headers, invoice["id"], "354.00")
    settled = (await client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)).json()
    assert settled["overdue"] is False


async def test_invoices_are_scoped_and_payments_are_audited(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    from sqlalchemy import select

    from app.core.audit import AuditLog

    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    invoice = await _shipped_invoice(client, auth_headers(rep_a), catalog_headers)

    hidden = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers(rep_b))
    assert hidden.status_code == 404
    await _pay(client, auth_headers(rep_a), invoice["id"], "54.00")

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "invoice",
        AuditLog.entity_id == UUID(invoice["id"]),
        AuditLog.action == "update",
    )
    (entry,) = (await session.execute(stmt)).scalars().all()
    assert entry.actor_id == rep_a.id
    assert entry.changes["amount_paid"] == ["0.00", "54.00"]
