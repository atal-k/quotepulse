from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import Team, User
from app.modules.quotations.models import Quotation
from tests.modules.sales_helpers import (
    accepted_quote,
    create_account,
    create_product,
    create_quote,
    step,
)

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


def _today() -> date:
    return datetime.now(UTC).date()


async def _quote_with_discount(
    client: AsyncClient,
    headers: dict[str, str],
    catalog_headers: dict[str, str],
    discount: str,
    **fields: Any,
) -> dict[str, Any]:
    product = await create_product(client, catalog_headers)
    account = await create_account(client, headers)
    return await create_quote(
        client, headers, account["id"], [(product["id"], "1", discount)], **fields
    )


async def test_totals_come_from_the_catalog_and_client_totals_are_ignored(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    product = await create_product(client, catalog_headers, unit_price="100.00", tax_pct="18")
    account = await create_account(client, headers)

    quote = await create_quote(
        client, headers, account["id"], [(product["id"], "10", "10")], total="1", subtotal="0"
    )

    assert Decimal(quote["total"]) == Decimal("1062.00")
    assert Decimal(quote["subtotal"]) == Decimal("900.00")
    assert Decimal(quote["discount_total"]) == Decimal("100.00")
    assert Decimal(quote["tax_total"]) == Decimal("162.00")
    assert Decimal(quote["items"][0]["line_total"]) == Decimal("1062.00")
    assert Decimal(quote["items"][0]["unit_price"]) == Decimal("100.00")


async def test_number_owner_version_and_audit_on_create(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    team: Team,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    product = await create_product(client, catalog_headers)
    account = await create_account(client, auth_headers(rep))

    quote = await create_quote(
        client, auth_headers(manager), account["id"], [(product["id"], "1", "0")]
    )

    assert quote["number"].startswith(f"QT-{datetime.now(UTC).year}-")
    assert (quote["version"], quote["status"], quote["created_by_kind"]) == (1, "draft", "human")
    assert quote["owner_id"] == str(rep.id)
    assert quote["team_id"] == str(team.id)
    stmt = select(AuditLog).where(
        AuditLog.entity_type == "quotation", AuditLog.entity_id == UUID(quote["id"])
    )
    (entry,) = (await session.execute(stmt)).scalars().all()
    assert entry.changes["number"] == [None, quote["number"]]


async def test_unknown_or_inactive_product_is_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    retired = await create_product(client, catalog_headers, is_active=False)
    account = await create_account(client, headers)

    for product_id in (str(uuid4()), retired["id"]):
        response = await client.post(
            "/api/v1/quotations",
            json={"account_id": account["id"], "items": [{"product_id": product_id, "qty": "1"}]},
            headers=headers,
        )
        assert response.status_code == 422


async def test_account_and_opportunity_must_be_visible_and_related(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    admin = await make_user("admin")
    product = await create_product(client, catalog_headers)
    account_a = await create_account(client, auth_headers(rep_a), name="A")
    account_b = await create_account(client, auth_headers(rep_b), name="B")
    opp_b = (
        await client.post(
            "/api/v1/opportunities",
            json={"account_id": account_b["id"], "name": "B deal"},
            headers=auth_headers(rep_b),
        )
    ).json()

    hidden = await client.post(
        "/api/v1/quotations",
        json={"account_id": account_a["id"], "items": [{"product_id": product["id"], "qty": "1"}]},
        headers=auth_headers(rep_b),
    )
    mismatched = await client.post(
        "/api/v1/quotations",
        json={
            "account_id": account_a["id"],
            "opportunity_id": opp_b["id"],
            "items": [{"product_id": product["id"], "qty": "1"}],
        },
        headers=auth_headers(admin),
    )
    assert hidden.status_code == 404
    assert mismatched.status_code == 422


async def test_quotes_are_visible_by_scope(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    team: Team,
    catalog_headers: dict[str, str],
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    manager = await make_user("manager")
    admin = await make_user("admin")
    quote = await _quote_with_discount(client, auth_headers(rep_a), catalog_headers, "0")

    assert (
        await client.get(f"/api/v1/quotations/{quote['id']}", headers=auth_headers(rep_b))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/quotations/{quote['id']}", headers=auth_headers(manager))
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/quotations/{quote['id']}", headers=auth_headers(admin))
    ).status_code == 200


async def test_small_discount_is_approved_on_submit(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    quote = await _quote_with_discount(client, auth_headers(rep), catalog_headers, "5")

    assert quote["approver_role"] is None
    response = await step(client, auth_headers(rep), quote["id"], "submit")
    assert response.json()["status"] == "approved"


async def test_mid_discount_needs_a_manager_and_reps_cannot_approve(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    quote = await _quote_with_discount(client, auth_headers(rep), catalog_headers, "10")
    assert quote["approver_role"] == "manager"

    submitted = await step(client, auth_headers(rep), quote["id"], "submit")
    assert submitted.json()["status"] == "pending_approval"
    rep_try = await step(client, auth_headers(rep), quote["id"], "approve")
    assert rep_try.status_code == 403
    approved = await step(client, auth_headers(manager), quote["id"], "approve")
    assert approved.json()["status"] == "approved"


async def test_large_discount_needs_an_admin(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    admin = await make_user("admin")
    quote = await _quote_with_discount(client, auth_headers(rep), catalog_headers, "20")
    assert quote["approver_role"] == "admin"
    await step(client, auth_headers(rep), quote["id"], "submit")

    manager_try = await step(client, auth_headers(manager), quote["id"], "approve")
    assert manager_try.status_code == 403
    approved = await step(client, auth_headers(admin), quote["id"], "approve")
    assert approved.json()["status"] == "approved"


async def test_reviewer_can_return_a_pending_quote_for_edits(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    quote = await _quote_with_discount(client, auth_headers(rep), catalog_headers, "10")
    await step(client, auth_headers(rep), quote["id"], "submit")

    returned = await step(client, auth_headers(manager), quote["id"], "return-for-edit")

    assert returned.json()["status"] == "draft"
    edited = await client.patch(
        f"/api/v1/quotations/{quote['id']}", json={"terms": "Net 30"}, headers=auth_headers(rep)
    )
    assert edited.status_code == 200


async def test_only_drafts_are_editable_and_revision_supersedes_the_old_version(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    quote = await _quote_with_discount(client, headers, catalog_headers, "0")
    await step(client, headers, quote["id"], "submit")

    locked = await client.patch(
        f"/api/v1/quotations/{quote['id']}", json={"terms": "x"}, headers=headers
    )
    assert locked.status_code == 409

    revision = (await step(client, headers, quote["id"], "revise")).json()
    assert (revision["number"], revision["version"], revision["status"]) == (
        quote["number"],
        2,
        "draft",
    )
    old = (await client.get(f"/api/v1/quotations/{quote['id']}", headers=headers)).json()
    assert old["status"] == "superseded"

    edited = await client.patch(
        f"/api/v1/quotations/{revision['id']}", json={"terms": "Net 45"}, headers=headers
    )
    assert edited.status_code == 200
    assert edited.json()["terms"] == "Net 45"


async def test_patching_items_replaces_lines_and_recomputes_totals(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    product = await create_product(client, catalog_headers, unit_price="100.00", tax_pct="18")
    account = await create_account(client, headers)
    quote = await create_quote(client, headers, account["id"], [(product["id"], "1", "0")])

    response = await client.patch(
        f"/api/v1/quotations/{quote['id']}",
        json={"items": [{"product_id": product["id"], "qty": "3", "discount_pct": "0"}]},
        headers=headers,
    )

    body = response.json()
    assert len(body["items"]) == 1
    assert Decimal(body["total"]) == Decimal("354.00")


async def test_invalid_transition_is_a_conflict_with_allowed_moves(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    quote = await _quote_with_discount(client, auth_headers(rep), catalog_headers, "0")

    response = await step(client, auth_headers(rep), quote["id"], "send")

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {
        "from": "draft",
        "to": "sent",
        "allowed": ["approved", "pending_approval"],
    }


async def test_accept_creates_the_order_and_wins_the_opportunity(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    product = await create_product(client, catalog_headers)
    account = await create_account(client, headers)
    opportunity = (
        await client.post(
            "/api/v1/opportunities",
            json={"account_id": account["id"], "name": "Bolts"},
            headers=headers,
        )
    ).json()
    quote = await create_quote(
        client,
        headers,
        account["id"],
        [(product["id"], "2", "0")],
        opportunity_id=opportunity["id"],
    )
    await step(client, headers, quote["id"], "submit")
    await step(client, headers, quote["id"], "send")

    accepted = await step(client, headers, quote["id"], "accept")

    assert accepted.json()["status"] == "accepted"
    orders = (await client.get("/api/v1/orders", headers=headers)).json()["items"]
    assert [o["quotation_id"] for o in orders] == [quote["id"]]
    won = (await client.get(f"/api/v1/opportunities/{opportunity['id']}", headers=headers)).json()
    assert won["stage"] == "won"


async def test_accept_with_insufficient_stock_is_a_conflict_and_changes_nothing(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    product = await create_product(client, catalog_headers, stock_qty="1")
    account = await create_account(client, headers)
    quote = await create_quote(client, headers, account["id"], [(product["id"], "2", "0")])
    await step(client, headers, quote["id"], "submit")
    await step(client, headers, quote["id"], "send")

    response = await step(client, headers, quote["id"], "accept")

    assert response.status_code == 409
    (shortage,) = response.json()["error"]["details"]["shortages"]
    assert shortage["sku"] == product["sku"]
    assert (await client.get(f"/api/v1/quotations/{quote['id']}", headers=headers)).json()[
        "status"
    ] == "sent"
    assert (await client.get("/api/v1/orders", headers=headers)).json()["total"] == 0


async def test_decline_marks_the_quotation_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    quote = await _quote_with_discount(client, headers, catalog_headers, "0")
    await step(client, headers, quote["id"], "submit")
    await step(client, headers, quote["id"], "send")

    declined = await step(client, headers, quote["id"], "decline")

    assert declined.json()["status"] == "rejected"


async def test_expiry_blocks_acceptance_and_is_only_allowed_after_validity(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    quote = await _quote_with_discount(
        client, headers, catalog_headers, "0", valid_until=_today().isoformat()
    )
    await step(client, headers, quote["id"], "submit")
    await step(client, headers, quote["id"], "send")

    too_early = await step(client, headers, quote["id"], "expire")
    assert too_early.status_code == 409

    yesterday = _today() - timedelta(days=1)
    await session.execute(
        update(Quotation).where(Quotation.id == UUID(quote["id"])).values(valid_until=yesterday)
    )
    late_accept = await step(client, headers, quote["id"], "accept")
    assert late_accept.status_code == 409
    assert late_accept.json()["error"]["message"] == "This quotation has expired."

    expired = await step(client, headers, quote["id"], "expire")
    assert expired.json()["status"] == "expired"


async def test_past_valid_until_is_rejected_on_create(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    response = await client.post(
        "/api/v1/quotations",
        json={
            "account_id": (await create_account(client, auth_headers(rep)))["id"],
            "valid_until": (_today() - timedelta(days=1)).isoformat(),
            "items": [
                {"product_id": (await create_product(client, catalog_headers))["id"], "qty": "1"}
            ],
        },
        headers=auth_headers(rep),
    )
    assert response.status_code == 422


async def test_status_changes_are_audited(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    catalog_headers: dict[str, str],
) -> None:
    rep = await make_user("rep")
    quote, _ = await accepted_quote(client, auth_headers(rep), catalog_headers)

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "quotation",
        AuditLog.entity_id == UUID(quote["id"]),
        AuditLog.action == "update",
    )
    statuses = [
        e.changes["status"]
        for e in (await session.execute(stmt)).scalars().all()
        if "status" in e.changes
    ]
    expected = [["draft", "approved"], ["approved", "sent"], ["sent", "accepted"]]
    assert sorted(statuses) == sorted(expected)
