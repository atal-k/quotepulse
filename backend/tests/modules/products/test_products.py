from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import User
from app.modules.products.models import Product

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


def _sku() -> str:
    return f"TST-{uuid4().hex[:8].upper()}"


async def _create_product(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    body = {"sku": _sku(), "name": "Hex Bolt M6 SS304", "unit_price": "12.50", **fields}
    response = await client.post("/api/v1/products", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_admin_creates_product_with_defaults_and_available_qty(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")

    product = await _create_product(client, auth_headers(admin), stock_qty="150.5")

    assert product["currency"] == "INR"
    assert Decimal(product["tax_pct"]) == Decimal("18")
    assert Decimal(product["reserved_qty"]) == 0
    assert Decimal(product["available_qty"]) == Decimal("150.5")
    assert product["is_active"] is True


async def test_sku_is_normalized_and_unique(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    sku = _sku()
    created = await _create_product(client, auth_headers(admin), sku=f"  {sku.lower()} ")
    assert created["sku"] == sku

    duplicate = await client.post(
        "/api/v1/products",
        json={"sku": sku, "name": "Dup", "unit_price": "1"},
        headers=auth_headers(admin),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize("role", ["rep", "manager"])
async def test_non_admins_can_read_but_not_write(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, role: str
) -> None:
    admin = await make_user("admin")
    user = await make_user(role)
    product = await _create_product(client, auth_headers(admin))

    listing = await client.get("/api/v1/products", headers=auth_headers(user))
    assert listing.status_code == 200
    assert product["id"] in {item["id"] for item in listing.json()["items"]}
    detail = await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers(user))
    assert detail.status_code == 200

    create = await client.post(
        "/api/v1/products",
        json={"sku": _sku(), "name": "Nope", "unit_price": "1"},
        headers=auth_headers(user),
    )
    assert create.status_code == 403
    update = await client.patch(
        f"/api/v1/products/{product['id']}", json={"name": "Nope"}, headers=auth_headers(user)
    )
    assert update.status_code == 403


async def test_unknown_product_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    response = await client.get(f"/api/v1/products/{uuid4()}", headers=auth_headers(rep))
    assert response.status_code == 404


async def test_list_filters_by_category_and_active(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    category = f"cat-{uuid4().hex[:8]}"
    bolt = await _create_product(client, auth_headers(admin), category=category)
    retired = await _create_product(client, auth_headers(admin), category=category, is_active=False)
    await _create_product(client, auth_headers(admin), category="other")

    in_category = await client.get(
        f"/api/v1/products?category={category}", headers=auth_headers(admin)
    )
    assert {i["id"] for i in in_category.json()["items"]} == {bolt["id"], retired["id"]}

    active_only = await client.get(
        f"/api/v1/products?category={category}&is_active=true", headers=auth_headers(admin)
    )
    assert [i["id"] for i in active_only.json()["items"]] == [bolt["id"]]


async def test_reserved_qty_and_sku_cannot_be_changed_through_the_api(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    product = await _create_product(client, auth_headers(admin), stock_qty="10")

    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"reserved_qty": "5", "sku": "HIJACK"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["reserved_qty"]) == 0
    assert response.json()["sku"] == product["sku"]


async def test_cannot_lower_stock_below_reserved(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    product = await _create_product(client, auth_headers(admin), stock_qty="10")
    row = await session.get(Product, UUID(product["id"]))
    assert row is not None
    row.reserved_qty = Decimal("8")
    await session.flush()

    response = await client.patch(
        f"/api/v1/products/{product['id']}", json={"stock_qty": "5"}, headers=auth_headers(admin)
    )

    assert response.status_code == 409
    assert Decimal(response.json()["error"]["details"]["reserved_qty"]) == 8


async def test_null_on_required_field_is_rejected_but_category_can_be_cleared(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    product = await _create_product(client, auth_headers(admin), category="fasteners")

    bad = await client.patch(
        f"/api/v1/products/{product['id']}", json={"unit_price": None}, headers=auth_headers(admin)
    )
    assert bad.status_code == 422

    cleared = await client.patch(
        f"/api/v1/products/{product['id']}", json={"category": None}, headers=auth_headers(admin)
    )
    assert cleared.status_code == 200
    assert cleared.json()["category"] is None


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"unit_price": "-1"},
        {"tax_pct": "101"},
        {"stock_qty": "-0.5"},
        {"min_order_qty": "0"},
        {"lead_time_days": -1},
        {"currency": "RUPEES"},
    ],
)
async def test_invalid_numbers_are_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, bad_fields: dict[str, Any]
) -> None:
    admin = await make_user("admin")
    response = await client.post(
        "/api/v1/products",
        json={"sku": _sku(), "name": "Bad", "unit_price": "1", **bad_fields},
        headers=auth_headers(admin),
    )
    assert response.status_code == 422


async def test_database_enforces_stock_invariants(session: AsyncSession) -> None:
    for fields in (
        {"stock_qty": Decimal("-1")},
        {"stock_qty": Decimal("5"), "reserved_qty": Decimal("6")},
        {"reserved_qty": Decimal("-1")},
    ):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(Product(sku=_sku(), name="Bad", unit_price=Decimal("1"), **fields))
                await session.flush()


async def test_create_and_update_write_audit_logs(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user("admin")
    product = await _create_product(client, auth_headers(admin), stock_qty="10")
    await client.patch(
        f"/api/v1/products/{product['id']}", json={"stock_qty": "25"}, headers=auth_headers(admin)
    )

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "product", AuditLog.entity_id == UUID(product["id"])
    )
    entries = {e.action: e for e in (await session.execute(stmt)).scalars().all()}
    assert entries["create"].actor_id == admin.id
    assert entries["create"].changes["sku"] == [None, product["sku"]]
    assert list(entries["update"].changes) == ["stock_qty"]
    old, new = entries["update"].changes["stock_qty"]
    assert (Decimal(old), Decimal(new)) == (10, 25)
