from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def build_engine(database_url: str) -> AsyncEngine:
    """Accepts a plain Neon `postgresql://...` connection string as-is (no need for callers to
    hand-edit it) and adapts it for asyncpg: forces the `+asyncpg` driver, and strips
    `sslmode`/`channel_binding` query params that asyncpg doesn't understand (unlike psycopg),
    passing the SSL requirement via connect_args instead."""
    parts = urlsplit(database_url)
    scheme = "postgresql+asyncpg"

    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    clean_url = urlunsplit(parts._replace(scheme=scheme, query=urlencode(query)))

    connect_args = {}
    if sslmode is None or sslmode != "disable":
        connect_args["ssl"] = "require"

    return create_async_engine(clean_url, connect_args=connect_args, pool_pre_ping=True)


engine = build_engine(settings.database_url.get_secret_value())
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """One session per request. Services flush(); this commits on success and rolls back
    on exception, so the commit lands before the response is sent."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
