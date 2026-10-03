"""Shared fixtures-as-functions for the quote-to-cash tests. Each helper goes through the public API
so the tests exercise the same paths a client would."""

from typing import Any
from uuid import uuid4

from httpx import AsyncClient, Response


async def _created(response: Response) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    return response.json()


async def create_product(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    body = {
        "sku": f"TST-{uuid4().hex[:8].upper()}",
        "name": "Hex Bolt M6",
        "unit_price": "100.00",
        "tax_pct": "18",
        "stock_qty": "10",
        **fields,
    }
    return await _created(await client.post("/api/v1/products", json=body, headers=headers))


async def create_account(
    client: AsyncClient, headers: dict[str, str], *, name: str = "Acme", **fields: Any
) -> dict[str, Any]:
    return await _created(
        await client.post("/api/v1/accounts", json={"name": name, **fields}, headers=headers)
    )


async def create_quote(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: str,
    lines: list[tuple[str, str, str]],
    **fields: Any,
) -> dict[str, Any]:
    """`lines` are (product_id, qty, discount_pct) tuples."""
    items = [{"product_id": pid, "qty": qty, "discount_pct": disc} for pid, qty, disc in lines]
    body = {"account_id": account_id, "items": items, **fields}
    return await _created(await client.post("/api/v1/quotations", json=body, headers=headers))


async def step(
    client: AsyncClient, headers: dict[str, str], quote_id: str, action: str
) -> Response:
    return await client.post(f"/api/v1/quotations/{quote_id}/{action}", headers=headers)


async def accepted_quote(
    client: AsyncClient,
    headers: dict[str, str],
    catalog_headers: dict[str, str],
    *,
    stock: str = "10",
    qty: str = "3",
    payment_terms_days: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A quote with a 0%-discount line, submitted, sent and accepted. Returns (quote, product)."""
    product = await create_product(client, catalog_headers, stock_qty=stock)
    fields = {} if payment_terms_days is None else {"payment_terms_days": payment_terms_days}
    account = await create_account(client, headers, **fields)
    quote = await create_quote(client, headers, account["id"], [(product["id"], qty, "0")])
    for action in ("submit", "send", "accept"):
        response = await step(client, headers, quote["id"], action)
        assert response.status_code == 200, response.text
    return quote, product
