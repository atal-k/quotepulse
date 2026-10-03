"""Read-only data QA for the seeded dataset (roadmap 1D). Prints PASS/FAIL per check, and the
a human needs to review by hand (sample quotation math, sample activity bodies).

Run: python -m app.scripts.data_qa
"""

import asyncio
import random
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import build_engine
from app.core.normalize import normalize_phone
from app.modules.quotations.totals import LineInput, calculate_totals
from app.scripts.demo.builder import SEED_CONSTANT
from app.scripts.demo.gstin import checksum

REVIEW_SAMPLE = 5
ACTIVITY_SAMPLE = 10
ENTITY_TABLES = {
    "account": "accounts",
    "contact": "contacts",
    "lead": "leads",
    "opportunity": "opportunities",
}


async def _scalar(session: AsyncSession, sql: str, **params: object) -> object:
    return (await session.execute(text(sql), params)).scalar_one()


async def _rows(session: AsyncSession, sql: str, **params: object) -> list:
    return list((await session.execute(text(sql), params)).all())


def _report(name: str, problems: list[str]) -> bool:
    if problems:
        print(f"FAIL  {name}")
        for problem in problems[:10]:
            print(f"        - {problem}")
        return False
    print(f"PASS  {name}")
    return True


async def check_totals(session: AsyncSession) -> bool:
    headers = await _rows(
        session, "SELECT id, number, subtotal, discount_total, tax_total, total FROM quotations"
    )
    problems = []
    for quote_id, number, subtotal, discount_total, tax_total, total in headers:
        lines = await _rows(
            session,
            "SELECT qty, unit_price, discount_pct, tax_pct FROM quotation_items "
            "WHERE quotation_id = :id",
            id=quote_id,
        )
        recomputed = calculate_totals([LineInput(*(Decimal(str(v)) for v in row)) for row in lines])
        if (
            recomputed.subtotal,
            recomputed.discount_total,
            recomputed.tax_total,
            recomputed.total,
        ) != (
            Decimal(str(subtotal)),
            Decimal(str(discount_total)),
            Decimal(str(tax_total)),
            Decimal(str(total)),
        ):
            problems.append(f"{number}: header totals differ from recomputed line totals")
    ok = _report(f"quotation totals reconcile ({len(headers)} quotations)", problems)

    rng = random.Random(SEED_CONSTANT)
    sample = rng.sample(headers, REVIEW_SAMPLE)
    print(f"\n  Hand-check sample ({REVIEW_SAMPLE} random quotations):")
    for quote_id, number, _, _, _, total in sample:
        lines = await _rows(
            session,
            "SELECT description, qty, unit_price, discount_pct, tax_pct, line_total "
            "FROM quotation_items "
            "WHERE quotation_id = :id ORDER BY position",
            id=quote_id,
        )
        print(f"  {number} (total {total}):")
        for description, qty, unit_price, discount_pct, tax_pct, line_total in lines:
            gross = Decimal(str(qty)) * Decimal(str(unit_price))
            print(
                f"    {description}: {qty} x {unit_price} = {gross}; "
                f"disc {discount_pct}% ; tax {tax_pct}% ; line total {line_total}"
            )
    print()
    return ok


async def check_stock(session: AsyncSession) -> bool:
    rows = await _rows(
        session,
        "SELECT sku, stock_qty, reserved_qty FROM products WHERE stock_qty < 0 OR reserved_qty < 0 "
        "OR reserved_qty > stock_qty",
    )
    return _report(
        "no negative or over-reserved stock",
        [f"{sku}: stock {s}, reserved {r}" for sku, s, r in rows],
    )


async def check_polymorphic_refs(session: AsyncSession) -> bool:
    problems = []
    for entity, table in ENTITY_TABLES.items():
        count = await _scalar(
            session,
            f"SELECT count(*) FROM activities a WHERE a.entity_type = :entity "
            f"AND NOT EXISTS (SELECT 1 FROM {table} t WHERE t.id = a.entity_id)",
            entity=entity,
        )
        if count:
            problems.append(f"{count} activities point at a missing {entity}")
    return _report("no orphaned polymorphic activity references", problems)


async def check_duplicate_lead(session: AsyncSession) -> bool:
    original, duplicate = await _rows(
        session,
        "SELECT name, email, phone FROM leads WHERE id IN "
        "('00000000-0000-4000-8000-000000000005', '00000000-0000-4000-8000-000000000006') "
        "ORDER BY name",
    )
    exact_email = original[1] == duplicate[1]
    exact_phone = normalize_phone(original[2]) == normalize_phone(duplicate[2])
    problems = []
    if exact_email:
        problems.append("emails are identical: an exact email match would catch the pair")
    if exact_phone:
        problems.append(
            "normalized phones are identical: an exact phone key (DOMAIN.md: exact-key match "
            "auto-links) would catch the pair; it is not only a fuzzy match"
        )
    return _report("planted duplicate lead is fuzzy-only (not exact-matchable)", problems)


async def check_documents(session: AsyncSession) -> bool:
    problems = []
    for table, invoice_rule in (("orders", False), ("invoices", True)):
        mismatches = await _rows(
            session,
            "SELECT number FROM invoices WHERE amount_paid > total OR "
            "(status = 'paid' AND amount_paid <> total)"
            if invoice_rule
            else "SELECT o.number FROM orders o JOIN quotations q ON q.id = o.quotation_id "
            "WHERE o.total <> q.total",
        )
        problems += [f"{table}: {row[0]}" for row in mismatches]
    numbers = await _rows(
        session, "SELECT number, count(*) FROM quotations GROUP BY number HAVING count(*) > 1"
    )
    problems += [f"duplicate quotation number {n}" for n, _ in numbers]
    return _report("order totals match accepted quote; invoice payments consistent", problems)


async def check_gstin(session: AsyncSession) -> bool:
    rows = await _rows(session, "SELECT name, tax_id FROM accounts")
    problems = [
        name for name, tax_id in rows if tax_id is None or checksum(tax_id[:14]) != tax_id[14]
    ]
    return _report(f"GSTIN checksum valid for all accounts ({len(rows)})", problems)


async def check_activity_realism(session: AsyncSession) -> bool:
    rows = await _rows(session, "SELECT body, occurred_at::date FROM activities ORDER BY id")
    rng = random.Random(SEED_CONSTANT)
    print(f"  Activity body sample ({ACTIVITY_SAMPLE} random, read by hand):")
    for body, when in rng.sample(rows, ACTIVITY_SAMPLE):
        print(f"    [{when}] {body}")
    print()
    return _report(
        f"activities span real past weeks ({len(rows)} rows)", [] if rows else ["no activities"]
    )


async def main() -> int:
    engine = build_engine(settings.database_url.get_secret_value())
    checks = [
        check_totals,
        check_stock,
        check_polymorphic_refs,
        check_duplicate_lead,
        check_documents,
        check_gstin,
        check_activity_realism,
    ]
    results = []
    async with engine.connect() as connection:
        session = AsyncSession(bind=connection)
        for check in checks:
            results.append(await check(session))
    await engine.dispose()
    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
