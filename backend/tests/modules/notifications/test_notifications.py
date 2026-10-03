from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import User
from app.modules.notifications.models import Notification

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _reassign_account(
    client: AsyncClient, manager: User, owner: User, headers: dict[str, str], account_id: str
) -> None:
    response = await client.patch(
        f"/api/v1/accounts/{account_id}",
        json={"owner_id": str(owner.id)},
        headers=headers,
    )
    assert response.status_code == 200, response.text


async def _account(client: AsyncClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    response = await client.post("/api/v1/accounts", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_reassignment_notifies_the_new_owner_only(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    new_owner = await make_user("rep")
    manager = await make_user("manager")
    account = await _account(client, auth_headers(rep), "Acme Bolts")

    await _reassign_account(client, manager, new_owner, auth_headers(manager), account["id"])

    feed = await client.get("/api/v1/notifications", headers=auth_headers(new_owner))
    body = feed.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "ownership_assigned"
    assert body["items"][0]["title"] == "Acme Bolts was assigned to you"
    assert body["items"][0]["entity_id"] == account["id"]
    other = await client.get("/api/v1/notifications", headers=auth_headers(manager))
    assert other.json()["total"] == 0


async def test_self_assignment_does_not_notify(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    manager = await make_user("manager")
    account = await _account(client, auth_headers(manager), "Self")

    await _reassign_account(client, manager, manager, auth_headers(manager), account["id"])

    feed = await client.get("/api/v1/notifications", headers=auth_headers(manager))
    assert feed.json()["total"] == 0


async def test_feed_is_own_only_even_for_admin_and_supports_unread_filter(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
) -> None:
    rep = await make_user("rep")
    admin = await make_user("admin")
    manager = await make_user("manager")
    for name in ("One", "Two"):
        account = await _account(client, auth_headers(manager), name)
        await _reassign_account(client, manager, rep, auth_headers(manager), account["id"])

    rep_feed = await client.get("/api/v1/notifications", headers=auth_headers(rep))
    assert rep_feed.json()["total"] == 2
    admin_feed = await client.get("/api/v1/notifications", headers=auth_headers(admin))
    assert admin_feed.json()["total"] == 0

    first = rep_feed.json()["items"][0]["id"]
    await client.post(f"/api/v1/notifications/{first}/read", headers=auth_headers(rep))
    unread = await client.get("/api/v1/notifications?unread_only=true", headers=auth_headers(rep))
    assert unread.json()["total"] == 1


async def test_mark_read_sets_read_at_once_and_is_404_for_others(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
) -> None:
    rep = await make_user("rep")
    other = await make_user("rep")
    manager = await make_user("manager")
    account = await _account(client, auth_headers(manager), "Acme")
    await _reassign_account(client, manager, rep, auth_headers(manager), account["id"])
    item_id = (await client.get("/api/v1/notifications", headers=auth_headers(rep))).json()[
        "items"
    ][0]["id"]

    hidden = await client.post(f"/api/v1/notifications/{item_id}/read", headers=auth_headers(other))
    assert hidden.status_code == 404

    first = await client.post(f"/api/v1/notifications/{item_id}/read", headers=auth_headers(rep))
    second = await client.post(f"/api/v1/notifications/{item_id}/read", headers=auth_headers(rep))
    assert first.json()["read_at"] is not None
    assert second.json()["read_at"] == first.json()["read_at"]

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "notification",
        AuditLog.entity_id == item_id,
        AuditLog.action == "update",
    )
    assert len((await session.execute(stmt)).scalars().all()) == 1


async def test_notification_rows_are_audited_on_creation(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    account = await _account(client, auth_headers(manager), "Acme")
    await _reassign_account(client, manager, rep, auth_headers(manager), account["id"])

    stmt = select(Notification).where(Notification.user_id == rep.id)
    (item,) = (await session.execute(stmt)).scalars().all()
    entry = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "notification", AuditLog.entity_id == item.id
            )
        )
    ).scalar_one()
    assert entry.actor_id == manager.id
    assert entry.changes["kind"] == [None, "ownership_assigned"]
