from collections.abc import AsyncGenerator, Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.db import build_engine, get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.identity.models import Team, User


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    # Function-scoped (not session-scoped): an AsyncEngine's connection pool is bound to the
    # event loop it was created under, and pytest-asyncio gives each test its own loop —
    # reusing one engine across tests raises "Event loop is closed" on later teardown.
    engine = build_engine(settings.test_database_url.get_secret_value())
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """One real-Postgres connection per test, wrapped in an outer transaction that's rolled
    back at the end. The ORM session joins it via a SAVEPOINT so service-layer flush() calls
    behave normally but nothing survives the test."""
    async with test_engine.connect() as connection:
        outer_tx = await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        async with session_factory() as db_session:
            yield db_session
        await outer_tx.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def team(session: AsyncSession) -> Team:
    t = Team(name="Test Team")
    session.add(t)
    await session.flush()
    return t


@pytest.fixture
def make_user(session: AsyncSession, team: Team) -> Callable[..., Awaitable[User]]:
    async def _make(role: str, *, email: str | None = None, team_id: UUID | None = None) -> User:
        user = User(
            email=email or f"{role}-{uuid4().hex[:8]}@test.dev",
            full_name=f"Test {role.title()}",
            hashed_password=hash_password("password123"),
            role=role,
            team_id=team_id or team.id,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        return user

    return _make


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers


@pytest.fixture
async def catalog_headers(
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> dict[str, str]:
    """Catalog products are admin-managed (DOMAIN.md), so tests create them with admin headers."""
    return auth_headers(await make_user("admin"))
