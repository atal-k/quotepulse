import asyncio
import logging
from uuid import UUID

import httpx

from app.agents.llm import ActivityInsight, build_embedder, build_insight_extractor
from app.context.embeddings import EmbedTask
from app.core import audit
from app.core.db import unit_of_work
from app.core.rbac import Actor, ActorKind
from app.modules.activities.models import Activity

logger = logging.getLogger(__name__)

# ARCHITECTURE §7: embed "summary + body head", not the full body.
BODY_HEAD_CHARS = 500
# Defensive cap on top of that: the embedding model's `outputTokenLimit` metadata field is
# unreliable (verified live in Phase 2A), so length is bounded in code rather than trusted.
EMBED_MAX_INPUT_CHARS = 8000

# CLAUDE §2.3/§2.6: every service call takes an Actor, every mutation is audited. This job acts
# on its own behalf, not a user's, so it carries no user_id/role (Actor allows this for
# kind=system — see core/rbac.py).
_SYSTEM_ACTOR = Actor(
    user_id=None, role=None, team_id=None, kind=ActorKind.SYSTEM, agent_name="process_activity"
)


def process_activity(activity_id: str) -> None:
    """RQ entry point. RQ jobs are plain synchronous callables; this bridges into the async
    stack once per call. Enqueued with retry=PROCESS_ACTIVITY_RETRY (app/jobs/queue.py) so
    transient failures are RQ's concern, not a manual retry loop here."""
    asyncio.run(process_activity_async(UUID(activity_id)))


async def process_activity_async(activity_id: UUID) -> None:
    """The async core, callable directly from an already-running event loop (the backfill
    script) without the RQ sync wrapper's `asyncio.run`."""
    async with httpx.AsyncClient() as client:
        embedder = build_embedder(client)
        extractor = build_insight_extractor(client)
        # One transaction for the whole job (CLAUDE §2.5 / ARCHITECTURE §4): a failure midway
        # persists nothing, so a retry redoes both LLM calls rather than leaving a half-written
        # row. Simpler and safer than partial persistence, at the cost of some wasted calls on
        # a transient mid-job failure — acceptable at this data scale.
        async with unit_of_work() as session:
            activity = await session.get(Activity, activity_id)
            if activity is None:
                logger.warning("process_activity: activity %s not found", activity_id)
                return
            if activity.embedding is not None and activity.meta and "insight" in activity.meta:
                return  # idempotent: already processed, nothing to do

            insight = await extractor.extract(activity.subject or "", activity.body or "")
            embed_text = _embed_text(insight, activity.body)
            (vector,) = await embedder.embed([embed_text], EmbedTask.DOCUMENT)

            activity.meta = {**(activity.meta or {}), "insight": insight.model_dump(mode="json")}
            activity.embedding = vector
            activity.embedding_model = embedder.model

            # Summarized, not the literal before/after of the 768-float vector — that's not a
            # meaningful diff for a human reading the audit log.
            changes = {
                "embedding_model": [None, embedder.model],
                "embedding_dims": [None, len(vector)],
                "insight_summary": [None, insight.summary],
            }
            await audit.record(session, _SYSTEM_ACTOR, "update", "activity", activity.id, changes)


def _embed_text(insight: ActivityInsight, body: str | None) -> str:
    head = (body or "")[:BODY_HEAD_CHARS]
    text = f"{insight.summary}\n\n{head}"
    return text[:EMBED_MAX_INPUT_CHARS]
