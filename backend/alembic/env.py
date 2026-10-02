import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from app.core.audit import AuditLog  # noqa: F401  (registers on Base.metadata)
from app.core.base import Base
from app.core.config import settings
from app.core.db import build_engine
from app.modules.accounts.models import Account  # noqa: F401
from app.modules.contacts.models import Contact  # noqa: F401
from app.modules.identity.models import Team, User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _target_url() -> str:
    # `make test` sets this so migrations run against TEST_DATABASE_URL, never DATABASE_URL.
    if os.environ.get("QUOTEPULSE_ALEMBIC_DB") == "test":
        return settings.test_database_url.get_secret_value()
    return settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_target_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = build_engine(_target_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
