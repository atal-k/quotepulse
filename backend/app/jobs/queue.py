import logging
from functools import lru_cache
from uuid import UUID

import redis
from rq import Queue, Retry

from app.core.config import settings

logger = logging.getLogger(__name__)

QUEUE_NAME = "activities"
# Transient failures (network, 5xx) are RQ's problem, not the job's — no manual retry loop.
PROCESS_ACTIVITY_RETRY = Retry(max=3, interval=[10, 30, 60])


@lru_cache
def _connection() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url)


@lru_cache
def _queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_connection())


def enqueue_process_activity(activity_id: UUID) -> None:
    """Enqueues process_activity for a newly created activity. The dotted path (rather than an
    imported function reference) avoids a service -> jobs -> service import cycle, and is what
    the worker process resolves it to. Enqueue failures (e.g. Redis unreachable) are logged and
    never fail the request that created the activity: the row is the source of truth, and the
    backfill script can reprocess it later."""
    try:
        _queue().enqueue(
            "app.jobs.process_activity.process_activity",
            str(activity_id),
            retry=PROCESS_ACTIVITY_RETRY,
        )
    except redis.RedisError:
        logger.exception("Failed to enqueue process_activity for activity %s", activity_id)
