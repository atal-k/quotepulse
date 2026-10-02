import re
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_sequences.service import DocumentKind, next_number


async def test_number_format_uses_prefix_year_and_zero_padding(session: AsyncSession) -> None:
    number = await next_number(session, DocumentKind.QUOTATION, year=2031)
    assert number == "QT-2031-00001"

    year = datetime.now(UTC).year
    assert re.fullmatch(rf"SO-{year}-\d{{5}}", await next_number(session, DocumentKind.ORDER))
    assert re.fullmatch(rf"INV-{year}-\d{{5}}", await next_number(session, DocumentKind.INVOICE))


async def test_numbers_increase_monotonically_without_gaps(session: AsyncSession) -> None:
    numbers = [await next_number(session, DocumentKind.ORDER, year=2032) for _ in range(3)]
    assert numbers == ["SO-2032-00001", "SO-2032-00002", "SO-2032-00003"]


async def test_kinds_and_years_count_independently(session: AsyncSession) -> None:
    assert await next_number(session, DocumentKind.QUOTATION, year=2033) == "QT-2033-00001"
    assert await next_number(session, DocumentKind.QUOTATION, year=2033) == "QT-2033-00002"
    assert await next_number(session, DocumentKind.INVOICE, year=2033) == "INV-2033-00001"
    assert await next_number(session, DocumentKind.QUOTATION, year=2034) == "QT-2034-00001"


async def test_rolled_back_allocation_leaves_no_gap(session: AsyncSession) -> None:
    assert await next_number(session, DocumentKind.QUOTATION, year=2035) == "QT-2035-00001"

    savepoint = await session.begin_nested()
    assert await next_number(session, DocumentKind.QUOTATION, year=2035) == "QT-2035-00002"
    await savepoint.rollback()

    assert await next_number(session, DocumentKind.QUOTATION, year=2035) == "QT-2035-00002"
