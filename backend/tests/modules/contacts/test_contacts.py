from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.contacts.models import Contact
from app.modules.identity.models import Team, User

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _create_account(
    client: AsyncClient, headers: dict[str, str], name: str
) -> dict[str, Any]:
    response = await client.post("/api/v1/accounts", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_contact(
    client: AsyncClient, headers: dict[str, str], account_id: str, **fields: Any
) -> dict[str, Any]:
    body = {"account_id": account_id, "first_name": "Rohan", **fields}
    response = await client.post("/api/v1/contacts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _audit(session: AsyncSession, entity_id: str, action: str) -> list[AuditLog]:
    stmt = select(AuditLog).where(
        AuditLog.entity_type == "contact",
        AuditLog.entity_id == UUID(entity_id),
        AuditLog.action == action,
    )
    return list((await session.execute(stmt)).scalars().all())


async def test_contact_inherits_owner_and_team_from_account(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, team: Team
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")

    contact = await _create_contact(client, auth_headers(manager), account["id"])

    assert contact["owner_id"] == str(rep.id)
    assert contact["team_id"] == str(team.id)


async def test_email_and_phone_are_normalized(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")

    contact = await _create_contact(
        client, auth_headers(rep), account["id"], email="Rohan@Acme.IN", phone="098765 43210"
    )

    assert contact["email"] == "rohan@acme.in"
    assert contact["phone"] == "+919876543210"


async def test_invalid_phone_is_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")

    response = await client.post(
        "/api/v1/contacts",
        json={"account_id": account["id"], "first_name": "Rohan", "phone": "123"},
        headers=auth_headers(rep),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_null_first_name_on_update_is_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    contact = await _create_contact(client, auth_headers(rep), account["id"])

    response = await client.patch(
        f"/api/v1/contacts/{contact['id']}", json={"first_name": None}, headers=auth_headers(rep)
    )
    assert response.status_code == 422


async def test_rep_only_sees_own_contacts_and_out_of_scope_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account_a = await _create_account(client, auth_headers(rep_a), "A's Account")
    account_b = await _create_account(client, auth_headers(rep_b), "B's Account")
    contact_a = await _create_contact(client, auth_headers(rep_a), account_a["id"])
    await _create_contact(client, auth_headers(rep_b), account_b["id"])

    listing = await client.get("/api/v1/contacts", headers=auth_headers(rep_a))
    assert [item["id"] for item in listing.json()["items"]] == [contact_a["id"]]

    response = await client.get(f"/api/v1/contacts/{contact_a['id']}", headers=auth_headers(rep_b))
    assert response.status_code == 404


async def test_create_on_out_of_scope_account_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account_a = await _create_account(client, auth_headers(rep_a), "A's Account")

    response = await client.post(
        "/api/v1/contacts",
        json={"account_id": account_a["id"], "first_name": "Sneaky"},
        headers=auth_headers(rep_b),
    )
    assert response.status_code == 404


async def test_manager_sees_team_contacts_not_other_teams_and_admin_sees_all(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    team: Team,
) -> None:
    other_team = Team(name="Other Team")
    session.add(other_team)
    await session.flush()
    rep_in_team = await make_user("rep", team_id=team.id)
    rep_elsewhere = await make_user("rep", team_id=other_team.id)
    manager = await make_user("manager", team_id=team.id)
    admin = await make_user("admin")
    in_team_account = await _create_account(client, auth_headers(rep_in_team), "In Team")
    elsewhere_account = await _create_account(client, auth_headers(rep_elsewhere), "Elsewhere")
    in_team = await _create_contact(client, auth_headers(rep_in_team), in_team_account["id"])
    elsewhere = await _create_contact(client, auth_headers(rep_elsewhere), elsewhere_account["id"])

    manager_view = await client.get("/api/v1/contacts", headers=auth_headers(manager))
    assert {item["id"] for item in manager_view.json()["items"]} == {in_team["id"]}

    for contact, account in ((in_team, in_team_account), (elsewhere, elsewhere_account)):
        admin_view = await client.get(
            f"/api/v1/contacts?account_id={account['id']}", headers=auth_headers(admin)
        )
        assert [item["id"] for item in admin_view.json()["items"]] == [contact["id"]]


async def test_list_filters_by_account(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account_1 = await _create_account(client, auth_headers(rep), "One")
    account_2 = await _create_account(client, auth_headers(rep), "Two")
    wanted = await _create_contact(client, auth_headers(rep), account_1["id"])
    await _create_contact(client, auth_headers(rep), account_2["id"])

    response = await client.get(
        f"/api/v1/contacts?account_id={account_1['id']}", headers=auth_headers(rep)
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == wanted["id"]


async def test_create_and_update_write_audit_logs(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    contact = await _create_contact(client, auth_headers(rep), account["id"])
    await client.patch(
        f"/api/v1/contacts/{contact['id']}",
        json={"job_title": "Purchase Head"},
        headers=auth_headers(rep),
    )

    (created,) = await _audit(session, contact["id"], "create")
    assert created.actor_id == rep.id
    assert created.changes["first_name"] == [None, "Rohan"]
    (updated,) = await _audit(session, contact["id"], "update")
    assert updated.changes == {"job_title": [None, "Purchase Head"]}


async def test_promoting_a_primary_contact_demotes_the_previous_one(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    first = await _create_contact(client, auth_headers(rep), account["id"], is_primary=True)
    second = await _create_contact(client, auth_headers(rep), account["id"])

    promote = await client.patch(
        f"/api/v1/contacts/{second['id']}", json={"is_primary": True}, headers=auth_headers(rep)
    )
    assert promote.status_code == 200

    demoted = await client.get(f"/api/v1/contacts/{first['id']}", headers=auth_headers(rep))
    assert demoted.json()["is_primary"] is False
    (entry,) = await _audit(session, first["id"], "update")
    assert entry.changes == {"is_primary": [True, False]}


async def test_creating_a_second_primary_demotes_the_first(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    first = await _create_contact(client, auth_headers(rep), account["id"], is_primary=True)
    await _create_contact(client, auth_headers(rep), account["id"], is_primary=True)

    demoted = await client.get(f"/api/v1/contacts/{first['id']}", headers=auth_headers(rep))
    assert demoted.json()["is_primary"] is False


async def test_database_rejects_two_primary_contacts_on_one_account(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    await _create_contact(client, auth_headers(rep), account["id"], is_primary=True)

    duplicate = Contact(
        account_id=UUID(account["id"]),
        first_name="Dup",
        is_primary=True,
        owner_id=rep.id,
        team_id=rep.team_id,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.flush()


async def test_account_reassignment_cascades_to_contacts(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    team: Team,
) -> None:
    rep = await make_user("rep")
    new_owner = await make_user("rep")
    manager = await make_user("manager")
    account = await _create_account(client, auth_headers(rep), "Reassign Me")
    contact = await _create_contact(client, auth_headers(rep), account["id"])

    response = await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"owner_id": str(new_owner.id)},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200

    moved = await client.get(f"/api/v1/contacts/{contact['id']}", headers=auth_headers(new_owner))
    assert moved.status_code == 200
    assert moved.json()["owner_id"] == str(new_owner.id)
    old_owner_view = await client.get(
        f"/api/v1/contacts/{contact['id']}", headers=auth_headers(rep)
    )
    assert old_owner_view.status_code == 404
    (entry,) = await _audit(session, contact["id"], "reassign")
    assert entry.actor_id == manager.id
    assert entry.changes == {"owner_id": [str(rep.id), str(new_owner.id)]}


async def test_account_update_without_ownership_change_does_not_cascade(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _create_account(client, auth_headers(rep), "Acme Bolts")
    contact = await _create_contact(client, auth_headers(rep), account["id"])

    await client.patch(
        f"/api/v1/accounts/{account['id']}", json={"city": "Pune"}, headers=auth_headers(rep)
    )

    assert await _audit(session, contact["id"], "reassign") == []
