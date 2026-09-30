from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.core.rbac import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: str
    full_name: str
    role: Role
    team_id: UUID | None
    is_active: bool
