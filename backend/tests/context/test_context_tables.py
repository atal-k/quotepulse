from collections.abc import Awaitable, Callable
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.context.embeddings import EMBEDDING_DIMENSIONS
from app.context.models import DuplicateCandidate, KbChunk, KbDocument
from app.modules.identity.models import User


async def test_hnsw_indexes_exist_on_the_database(session: AsyncSession) -> None:
    rows = (
        await session.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE indexname IN ('ix_activities_embedding_hnsw', 'ix_kb_chunks_embedding_hnsw')"
            )
        )
    ).all()
    assert len(rows) == 2
    assert all("USING hnsw" in definition for _, definition in rows)
    assert all("vector_cosine_ops" in definition for _, definition in rows)


async def test_wrong_dimension_embedding_is_rejected(session: AsyncSession) -> None:
    doc = KbDocument(source_key=f"test-{uuid4().hex[:8]}", title="t", content_hash="h")
    session.add(doc)
    await session.flush()
    session.add(
        KbChunk(
            document_id=doc.id,
            ordinal=0,
            text="x",
            token_count=1,
            embedding=[0.0] * (EMBEDDING_DIMENSIONS - 1),
            embedding_model="test",
        )
    )
    with pytest.raises(DBAPIError):
        await session.flush()


async def test_kb_chunk_ordinals_are_unique_per_document(session: AsyncSession) -> None:
    doc = KbDocument(source_key=f"test-{uuid4().hex[:8]}", title="t", content_hash="h")
    session.add(doc)
    await session.flush()
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for _ in range(2):
        session.add(
            KbChunk(
                document_id=doc.id,
                ordinal=0,
                text="x",
                token_count=1,
                embedding=vector,
                embedding_model="test",
            )
        )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_duplicate_pair_must_be_ordered(
    session: AsyncSession, make_user: Callable[..., Awaitable[User]]
) -> None:
    owner = await make_user("admin")
    low, high = sorted([uuid4(), uuid4()])
    session.add(
        DuplicateCandidate(
            type="fuzzy_name",
            entity_type="lead",
            entity_a_id=high,
            entity_b_id=low,
            confidence=Decimal("0.8000"),
            status="open",
            owner_id=owner.id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_duplicate_pair_is_unique(
    session: AsyncSession, make_user: Callable[..., Awaitable[User]]
) -> None:
    owner = await make_user("admin")
    low, high = sorted([uuid4(), uuid4()])
    for _ in range(2):
        session.add(
            DuplicateCandidate(
                type="fuzzy_name",
                entity_type="lead",
                entity_a_id=low,
                entity_b_id=high,
                confidence=Decimal("0.8000"),
                status="open",
                owner_id=owner.id,
            )
        )
    with pytest.raises(IntegrityError):
        await session.flush()
