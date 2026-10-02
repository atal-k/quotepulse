import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_sequences.models import DocumentSequence


class DocumentKind(StrEnum):
    QUOTATION = "QT"
    ORDER = "SO"
    INVOICE = "INV"


async def next_number(session: AsyncSession, kind: DocumentKind, *, year: int | None = None) -> str:
    """Allocate the next document number, e.g. `QT-2026-00001`.

    A single upsert: the first call for a (kind, year) inserts 1, later calls increment under the
    row lock that `ON CONFLICT DO UPDATE` takes, so concurrent callers serialize and never get a
    duplicate. The increment lives in the caller's transaction, so a rollback leaves no gap.
    `year` defaults to the current UTC year.
    """
    year = year if year is not None else datetime.now(UTC).year
    stmt = (
        insert(DocumentSequence)
        .values(id=uuid.uuid4(), kind=kind.value, year=year, last_value=1)
        .on_conflict_do_update(
            index_elements=["kind", "year"],
            set_={"last_value": DocumentSequence.last_value + 1},
        )
        .returning(DocumentSequence.last_value)
    )
    value = (await session.execute(stmt)).scalar_one()
    return f"{kind.value}-{year}-{value:05d}"
