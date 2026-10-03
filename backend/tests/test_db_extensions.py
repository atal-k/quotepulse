from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_pg_trgm_extension_is_installed(session: AsyncSession) -> None:
    installed = (
        await session.execute(text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'"))
    ).scalar_one()
    assert installed == 1
