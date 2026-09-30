from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.modules.identity.models import User


async def test_login_success_returns_token(
    client: AsyncClient, make_user: Callable[..., Awaitable[User]]
) -> None:
    user = await make_user("rep", email="login-ok@test.dev")
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_login_wrong_password_rejected(
    client: AsyncClient, make_user: Callable[..., Awaitable[User]]
) -> None:
    user = await make_user("rep", email="login-bad@test.dev")
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_me_returns_current_user(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = await make_user("manager", email="me-check@test.dev")
    response = await client.get("/api/v1/me", headers=auth_headers(user))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["role"] == "manager"
