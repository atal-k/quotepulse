from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.modules.identity.models import User


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    stmt = select(User).where(User.email == email.lower().strip())
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_active_user(session: AsyncSession, user_id: UUID) -> User | None:
    stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()
