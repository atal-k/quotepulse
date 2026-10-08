import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.agents.llm import ActivityEntities, ActivityInsight, InsightExtractionError
from app.context.embeddings import EMBEDDING_DIMENSIONS, EmbedTask
from app.core import db as db_module
from app.core.audit import AuditLog
from app.core.rbac import ActorKind
from app.jobs.process_activity import EMBED_MAX_INPUT_CHARS, _embed_text, process_activity_async
from app.modules.activities.models import Activity
from app.modules.identity.models import Team, User

CANNED_INSIGHT = ActivityInsight(
    summary="Customer asked for a quote on 500 pcs 6mm SS bolts.",
    sentiment="neutral",
    intents=["quote_request"],
    next_steps=["send_quote"],
    entities=ActivityEntities(products=["6mm SS bolts"], quantities=["500 pcs"], dates=[]),
)


class _FakeEmbedder:
    model = "fake-embed-model"

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls = 0

    async def embed(self, texts: list[str], task: EmbedTask) -> list[list[float]]:
        assert task == EmbedTask.DOCUMENT
        self.calls += 1
        return [self._vector for _ in texts]


class _FakeExtractor:
    def __init__(
        self, insight: ActivityInsight | None = None, error: Exception | None = None
    ) -> None:
        self._insight = insight
        self._error = error
        self.calls = 0

    async def extract(self, subject: str, body: str) -> ActivityInsight:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._insight is not None
        return self._insight


@pytest.fixture
async def job_session(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncSession, None]:
    """process_activity_async opens its own session via core.db.unit_of_work (a job's
    transaction is independent of any request), so it needs its own connection to the test
    database rather than the shared `session` fixture's savepoint-per-test trick."""
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "async_session_factory", factory)
    async with factory() as setup_session:
        yield setup_session


async def _make_activity(session: AsyncSession, **overrides: object) -> Activity:
    team = Team(name=f"job-test-{uuid.uuid4().hex[:8]}")
    session.add(team)
    await session.flush()
    user = User(
        email=f"job-test-{uuid.uuid4().hex[:8]}@test.dev",
        full_name="Job Test Owner",
        hashed_password="x",
        role="rep",
        team_id=team.id,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    activity = Activity(
        type="note",
        subject=overrides.get("subject", "Call about bolts"),
        body=overrides.get("body", "Customer wants 500 pcs 6mm SS bolts next week."),
        occurred_at=datetime.now(UTC),
        entity_type="account",
        entity_id=uuid.uuid4(),
        created_by_kind="human",
        owner_id=user.id,
        team_id=team.id,
        meta=overrides.get("meta"),
        embedding=overrides.get("embedding"),
        embedding_model=overrides.get("embedding_model"),
    )
    session.add(activity)
    await session.commit()
    return activity


async def _cleanup(session: AsyncSession, activity: Activity) -> None:
    owner_id, team_id = activity.owner_id, activity.team_id
    audit_rows = (
        await session.execute(select(AuditLog).where(AuditLog.entity_id == activity.id))
    ).scalars()
    for row in audit_rows:
        await session.delete(row)
    await session.delete(activity)
    user = await session.get(User, owner_id)
    if user is not None:
        await session.delete(user)
    if team_id is not None:
        team = await session.get(Team, team_id)
        if team is not None:
            await session.delete(team)
    await session.commit()


async def test_processes_activity_sets_insight_and_embedding(
    job_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    activity = await _make_activity(job_session)
    fake_embedder = _FakeEmbedder([0.1] * EMBEDDING_DIMENSIONS)
    fake_extractor = _FakeExtractor(insight=CANNED_INSIGHT)
    monkeypatch.setattr("app.jobs.process_activity.build_embedder", lambda client: fake_embedder)
    monkeypatch.setattr(
        "app.jobs.process_activity.build_insight_extractor", lambda client: fake_extractor
    )
    try:
        await process_activity_async(activity.id)
        await job_session.refresh(activity)
        assert activity.embedding == pytest.approx([0.1] * EMBEDDING_DIMENSIONS)
        assert activity.embedding_model == "fake-embed-model"
        assert activity.meta["insight"]["summary"] == CANNED_INSIGHT.summary
        assert fake_embedder.calls == 1
        assert fake_extractor.calls == 1

        audit_row = (
            await job_session.execute(select(AuditLog).where(AuditLog.entity_id == activity.id))
        ).scalar_one()
        assert audit_row.actor_id is None
        assert audit_row.actor_kind == ActorKind.SYSTEM.value
        assert audit_row.agent_name == "process_activity"
        assert audit_row.action == "update"
        assert audit_row.entity_type == "activity"
        assert audit_row.changes["embedding_model"] == [None, "fake-embed-model"]
        assert audit_row.changes["insight_summary"] == [None, CANNED_INSIGHT.summary]
    finally:
        await _cleanup(job_session, activity)


async def test_idempotent_skip_when_already_processed(
    job_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    activity = await _make_activity(
        job_session,
        meta={"insight": CANNED_INSIGHT.model_dump(mode="json")},
        embedding=[0.2] * EMBEDDING_DIMENSIONS,
        embedding_model="already-done",
    )
    fake_embedder = _FakeEmbedder([0.9] * EMBEDDING_DIMENSIONS)
    fake_extractor = _FakeExtractor(insight=CANNED_INSIGHT)
    monkeypatch.setattr("app.jobs.process_activity.build_embedder", lambda client: fake_embedder)
    monkeypatch.setattr(
        "app.jobs.process_activity.build_insight_extractor", lambda client: fake_extractor
    )
    try:
        await process_activity_async(activity.id)
        assert fake_embedder.calls == 0
        assert fake_extractor.calls == 0
        audit_rows = (
            await job_session.execute(select(AuditLog).where(AuditLog.entity_id == activity.id))
        ).scalars()
        assert audit_rows.first() is None
    finally:
        await _cleanup(job_session, activity)


async def test_missing_activity_returns_without_error(job_session: AsyncSession) -> None:
    await process_activity_async(uuid.uuid4())


async def test_extraction_failure_propagates_and_persists_nothing(
    job_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    activity = await _make_activity(job_session)
    fake_extractor = _FakeExtractor(error=InsightExtractionError("boom"))
    monkeypatch.setattr(
        "app.jobs.process_activity.build_embedder",
        lambda client: _FakeEmbedder([0.0] * EMBEDDING_DIMENSIONS),
    )
    monkeypatch.setattr(
        "app.jobs.process_activity.build_insight_extractor", lambda client: fake_extractor
    )
    try:
        with pytest.raises(InsightExtractionError):
            await process_activity_async(activity.id)
        await job_session.refresh(activity)
        assert activity.embedding is None
        assert activity.meta is None
        audit_rows = (
            await job_session.execute(select(AuditLog).where(AuditLog.entity_id == activity.id))
        ).scalars()
        assert audit_rows.first() is None
    finally:
        await _cleanup(job_session, activity)


def test_embed_text_uses_summary_and_body_head_and_caps_length() -> None:
    long_body = "x" * 10000
    text = _embed_text(CANNED_INSIGHT, long_body)
    assert text.startswith(CANNED_INSIGHT.summary)
    assert len(text) <= EMBED_MAX_INPUT_CHARS
    assert text.count("x") == 500  # body head only, not the full 10000-char body
