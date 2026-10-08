"""One-off backfill for the seeded activities (ROADMAP 2B). Runs process_activity directly
(not through the RQ queue — this script controls the batch itself) for activities that don't
yet have an embedding, oldest first. Run a small batch first and read the ActivityInsight
output before processing the rest: this spends real Gemini API calls against real seeded data.

Run: python -m app.scripts.backfill_activities --limit 15
"""

import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import build_engine
from app.jobs.process_activity import process_activity_async
from app.modules.activities.models import Activity

# Registers on Base.metadata: Activity.owner_id/team_id resolve their FKs against these at
# flush time, same reason alembic/env.py imports every model module.
from app.modules.identity.models import Team, User  # noqa: F401


async def _unprocessed_ids(session: AsyncSession, limit: int) -> list[UUID]:
    # Insight and embedding are written together in one transaction (process_activity_async),
    # so "embedding is NULL" alone identifies an unprocessed activity.
    stmt = (
        select(Activity.id)
        .where(Activity.embedding.is_(None))
        .order_by(Activity.created_at, Activity.id)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _print_result(session: AsyncSession, activity_id: UUID) -> None:
    activity = (
        await session.execute(select(Activity).where(Activity.id == activity_id))
    ).scalar_one()
    insight = (activity.meta or {}).get("insight")
    dims = len(activity.embedding) if activity.embedding is not None else None
    print(f"--- {activity.id} ({activity.type}, {activity.occurred_at.date()}) ---")
    print(f"  subject: {activity.subject}")
    print(f"  body: {(activity.body or '')[:200]}")
    if insight is None:
        print("  insight: MISSING (extraction failed — check logs)")
    else:
        print(f"  insight: {json.dumps(insight, indent=2)}")
    print(f"  embedding: {'MISSING' if dims is None else f'{dims} dims'}")
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, required=True, help="Max activities to process.")
    args = parser.parse_args()

    engine = build_engine(settings.database_url.get_secret_value())
    succeeded: list[UUID] = []
    failed: list[tuple[UUID, str]] = []
    async with engine.connect() as connection:
        session = AsyncSession(bind=connection)
        ids = await _unprocessed_ids(session, args.limit)
        print(f"{len(ids)} unprocessed activities selected (limit {args.limit})\n")
        for activity_id in ids:
            try:
                await process_activity_async(activity_id)
            except Exception as exc:
                # No retry-with-backoff here: process_activity_async is idempotent (skips
                # already-processed rows), so simply re-running this script later retries
                # whatever's left — one bad activity must not abort the rest of the batch.
                error = f"{type(exc).__name__}: {exc}"
                failed.append((activity_id, error))
                print(f"--- {activity_id} FAILED: {error} ---\n")
                continue
            succeeded.append(activity_id)
            await _print_result(session, activity_id)
    await engine.dispose()

    print(f"done: {len(succeeded)} succeeded, {len(failed)} failed")
    if failed:
        print("failed activity_ids:")
        for activity_id, error in failed:
            print(f"  {activity_id}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
