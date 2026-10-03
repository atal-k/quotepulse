"""Writes the demo dataset. Idempotent: skipped if the first hero account already exists."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.accounts.models import Account
from app.modules.activities.models import Activity
from app.modules.contacts.models import Contact
from app.modules.document_sequences.models import DocumentSequence
from app.modules.invoices.models import Invoice
from app.modules.leads.models import Lead
from app.modules.opportunities.models import Opportunity
from app.modules.orders.models import Order
from app.modules.products.models import Product
from app.modules.quotations.models import Quotation
from app.scripts.demo.builder import HERO_ACCOUNT_PUMPS, SEED_NAMESPACE, YEAR, Dataset

ENTITY_TYPES: dict[type, str] = {
    Account: "account",
    Contact: "contact",
    Lead: "lead",
    Opportunity: "opportunity",
    Activity: "activity",
    Product: "product",
    Quotation: "quotation",
    Order: "order",
    Invoice: "invoice",
}


FLUSH_ORDER: tuple[tuple[type, ...], ...] = (
    (Product,),
    (Account,),
    (Contact, Lead),
    (Opportunity,),
    (Activity,),
    (Quotation,),
    (Order,),
    (Invoice,),
)


async def already_loaded(session: AsyncSession) -> bool:
    return await session.get(Account, HERO_ACCOUNT_PUMPS) is not None


async def load(session: AsyncSession, dataset: Dataset) -> int:
    """Adds every row, a seed audit entry per aggregate, and the document counters. Returns the
    number of aggregates written. Flushes; the caller owns the transaction."""
    # Flush one tier at a time: Invoice → Order has no ORM relationship, so the unit of work
    # would otherwise be free to insert an invoice before the order it references.
    written = 0
    for tier in FLUSH_ORDER:
        session.add_all(obj for obj in dataset.objects if type(obj) in tier)
        await session.flush()
    for obj in dataset.objects:
        entity = ENTITY_TYPES.get(type(obj))
        if entity is None:
            continue
        written += 1
        session.add(
            AuditLog(
                actor_id=None,
                actor_kind="system",
                agent_name="seed",
                action="create",
                entity_type=entity,
                entity_id=obj.id,
                changes={"source": [None, "seed"]},
                occurred_at=obj.created_at,
            )
        )
    for kind, last_value in dataset.sequences.items():
        session.add(
            DocumentSequence(
                id=uuid.uuid5(SEED_NAMESPACE, f"sequence:{kind}"),
                kind=kind,
                year=YEAR,
                last_value=last_value,
            )
        )
    await session.flush()
    return written
