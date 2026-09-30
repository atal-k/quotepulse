from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Unauthorized
from app.core.rbac import Actor, ActorKind, Role
from app.core.security import decode_access_token
from app.modules.identity import service
from app.modules.identity.models import User


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing or invalid Authorization header.")
    token = authorization.split(" ", 1)[1]
    user_id = decode_access_token(token)
    if user_id is None:
        raise Unauthorized("Invalid or expired token.")
    user = await service.get_active_user(session, user_id)
    if user is None:
        raise Unauthorized("Invalid or expired token.")
    return user


async def get_current_actor(user: Annotated[User, Depends(get_current_user)]) -> Actor:
    """The one dependency other modules import cross-module (ARCHITECTURE §2's stated
    exception for identity). Agents/MCP build their Actor the same way, from the delegating
    user, elsewhere — this path is for human sessions."""
    return Actor(
        user_id=user.id,
        role=Role(user.role),
        team_id=user.team_id,
        kind=ActorKind.HUMAN,
    )
