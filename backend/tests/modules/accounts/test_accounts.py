from collections.abc import Awaitable, Callable
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import Team, User


async def _create_account(client: AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post("/api/v1/accounts", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_defaults_owner_and_team_to_actor(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
    team: Team,
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    assert account["owner_id"] == str(rep.id)
    assert account["team_id"] == str(team.id)


async def test_rep_only_sees_own_accounts(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    await _create_account(client, auth_headers(rep_a), "Rep A's Account")
    await _create_account(client, auth_headers(rep_b), "Rep B's Account")

    response = await client.get("/api/v1/accounts", headers=auth_headers(rep_a))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Rep A's Account"


async def test_manager_sees_team_but_not_other_teams(
    client: AsyncClient,
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
    team: Team,
) -> None:
    other_team = Team(name="Other Team")
    session.add(other_team)
    await session.flush()

    rep_in_team = await make_user("rep", team_id=team.id)
    rep_in_other_team = await make_user("rep", team_id=other_team.id)
    manager = await make_user("manager", team_id=team.id)

    await _create_account(client, auth_headers(rep_in_team), "In Team")
    await _create_account(client, auth_headers(rep_in_other_team), "Other Team")

    response = await client.get("/api/v1/accounts", headers=auth_headers(manager))
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"In Team"}


async def test_out_of_scope_get_returns_404(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account = await _create_account(client, auth_headers(rep_a), "Rep A's Account")

    response = await client.get(f"/api/v1/accounts/{account['id']}", headers=auth_headers(rep_b))
    assert response.status_code == 404


async def test_admin_sees_all_accounts(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    rep = await make_user("rep")
    admin = await make_user("admin")
    await _create_account(client, auth_headers(rep), "Visible To Admin")

    response = await client.get("/api/v1/accounts", headers=auth_headers(admin))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_rep_cannot_reassign_owner(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    rep = await make_user("rep")
    other = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Rep's Account")

    response = await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"owner_id": str(other.id)},
        headers=auth_headers(rep),
    )
    assert response.status_code == 403


async def test_manager_can_reassign_owner(
    client: AsyncClient,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
    team: Team,
) -> None:
    rep = await make_user("rep")
    other_rep = await make_user("rep")
    manager = await make_user("manager")
    account = await _create_account(client, auth_headers(rep), "Reassign Me")

    response = await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"owner_id": str(other_rep.id)},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200
    assert response.json()["owner_id"] == str(other_rep.id)


async def test_create_writes_audit_log(
    client: AsyncClient,
    session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Audited Account")

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "account",
        AuditLog.entity_id == UUID(account["id"]),
        AuditLog.action == "create",
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert entry.actor_id == rep.id
    assert entry.changes["name"] == [None, "Audited Account"]
