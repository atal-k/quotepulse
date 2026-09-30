"""Idempotent dev seed: one team + admin/manager/rep users. Credentials are documented in
README.md, not printed here — they're fixed dev-only fixtures, not real secrets, but CLAUDE.md
still says no secrets in logs, so we don't echo them.

Not a request/job, so it owns its own transaction (commit, not flush) — same pattern Alembic
migrations use, outside the request/job unit-of-work.
"""

import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.core.security import hash_password
from app.modules.identity.models import Team, User

SEED_TEAM_NAME = "Default Team"

SEED_USERS = [
    {
        "email": "admin@quotepulse.dev",
        "full_name": "Aditya Sharma",
        "role": "admin",
        "password": "admin-12345",
    },
    {
        "email": "manager@quotepulse.dev",
        "full_name": "Priya Nair",
        "role": "manager",
        "password": "manager-12345",
    },
    {
        "email": "rep@quotepulse.dev",
        "full_name": "Rohan Verma",
        "role": "rep",
        "password": "rep-12345",
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        team = (
            await session.execute(select(Team).where(Team.name == SEED_TEAM_NAME))
        ).scalar_one_or_none()
        if team is None:
            team = Team(name=SEED_TEAM_NAME)
            session.add(team)
            await session.flush()

        for entry in SEED_USERS:
            existing = (
                await session.execute(select(User).where(User.email == entry["email"]))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                User(
                    email=entry["email"],
                    full_name=entry["full_name"],
                    hashed_password=hash_password(entry["password"]),
                    role=entry["role"],
                    team_id=team.id,
                    is_active=True,
                )
            )
            print(f"seeded {entry['role']}: {entry['email']}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
