from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Unauthorized
from app.core.security import create_access_token
from app.modules.identity import service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.identity.schemas import LoginRequest, MeRead, TokenResponse

router = APIRouter(tags=["identity"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> TokenResponse:
    user = await service.authenticate(session, payload.email, payload.password)
    if user is None:
        raise Unauthorized("Invalid email or password.")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
