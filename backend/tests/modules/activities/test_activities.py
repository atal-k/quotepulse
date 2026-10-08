from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.activities.models import Activity
from app.modules.identity.models import Team, User

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _post(client: AsyncClient, path: str, headers: dict[str, str], **body: Any) -> dict:
    response = await client.post(f"/api/v1/{path}", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _account(client: AsyncClient, headers: dict[str, str], name: str = "Acme") -> dict:
    return await _post(client, "accounts", headers, name=name)


async def _log(client: AsyncClient, headers: dict[str, str], **fields: Any) -> dict:
    body = {"type": "call", "subject": "Follow-up", "entity_type": "account", **fields}
    return await _post(client, "activities", headers, **body)


async def test_activity_inherits_owner_team_and_records_actor_kind(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, team: Team
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    account = await _account(client, auth_headers(rep))

    activity = await _log(client, auth_headers(manager), entity_id=account["id"])

    assert activity["owner_id"] == str(rep.id)
    assert activity["team_id"] == str(team.id)
    assert activity["created_by_kind"] == "human"
    assert activity["occurred_at"] is not None


async def test_occurred_at_defaults_to_now_and_keeps_given_value(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _account(client, auth_headers(rep))
    given = "2026-09-01T10:00:00+00:00"

    defaulted = await _log(client, auth_headers(rep), entity_id=account["id"])
    explicit = await _log(client, auth_headers(rep), entity_id=account["id"], occurred_at=given)

    assert datetime.fromisoformat(defaulted["occurred_at"]).year == datetime.now(UTC).year
    assert datetime.fromisoformat(explicit["occurred_at"]) == datetime.fromisoformat(given)


@pytest.mark.parametrize("entity_type", ["account", "contact", "lead", "opportunity"])
async def test_each_parent_type_accepts_an_activity(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, entity_type: str
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    account = await _account(client, headers)
    if entity_type == "account":
        parent_id = account["id"]
    elif entity_type == "contact":
        parent_id = (
            await _post(client, "contacts", headers, account_id=account["id"], first_name="A")
        )["id"]
    elif entity_type == "lead":
        parent_id = (await _post(client, "leads", headers, name="Lead"))["id"]
    else:
        parent_id = (
            await _post(client, "opportunities", headers, account_id=account["id"], name="Deal")
        )["id"]

    activity = await _log(client, headers, entity_type=entity_type, entity_id=parent_id)

    assert activity["entity_type"] == entity_type
    assert activity["entity_id"] == parent_id


async def test_unknown_or_out_of_scope_parent_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account = await _account(client, auth_headers(rep_a))
    from uuid import uuid4

    hidden = await client.post(
        "/api/v1/activities",
        json={"type": "note", "entity_type": "account", "entity_id": account["id"]},
        headers=auth_headers(rep_b),
    )
    missing = await client.post(
        "/api/v1/activities",
        json={"type": "note", "entity_type": "account", "entity_id": str(uuid4())},
        headers=auth_headers(rep_a),
    )

    assert hidden.status_code == 404
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "bad",
    [{"entity_type": "quotation"}, {"type": "direction"}, {"type": "task"}],
)
async def test_unknown_entity_or_activity_type_is_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, bad: dict[str, str]
) -> None:
    rep = await make_user("rep")
    account = await _account(client, auth_headers(rep))
    body = {"type": "call", "entity_type": "account", "entity_id": account["id"], **bad}

    response = await client.post("/api/v1/activities", json=body, headers=auth_headers(rep))

    assert response.status_code == 422


async def test_database_rejects_unknown_entity_type(
    session: AsyncSession, make_user: MakeUser
) -> None:
    rep = await make_user("rep")
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                Activity(
                    type="note",
                    occurred_at=datetime.now(UTC),
                    entity_type="task",
                    entity_id=UUID(int=1),
                    created_by_kind="human",
                    owner_id=rep.id,
                    team_id=rep.team_id,
                )
            )
            await session.flush()


async def test_rep_sees_own_thread_manager_sees_team_and_filters_by_entity(
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
    mine = await _account(client, auth_headers(rep_in_team), "Mine")
    theirs = await _account(client, auth_headers(rep_elsewhere), "Theirs")
    own = await _log(client, auth_headers(rep_in_team), entity_id=mine["id"])
    await _log(client, auth_headers(rep_elsewhere), entity_id=theirs["id"])

    rep_view = await client.get("/api/v1/activities", headers=auth_headers(rep_in_team))
    assert [i["id"] for i in rep_view.json()["items"]] == [own["id"]]
    manager_view = await client.get("/api/v1/activities", headers=auth_headers(manager))
    assert {i["id"] for i in manager_view.json()["items"]} == {own["id"]}
    timeline = await client.get(
        f"/api/v1/activities?entity_type=account&entity_id={mine['id']}",
        headers=auth_headers(rep_in_team),
    )
    assert timeline.json()["total"] == 1


async def test_update_changes_content_but_never_the_parent(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _account(client, auth_headers(rep))
    other = await _account(client, auth_headers(rep), "Other")
    activity = await _log(client, auth_headers(rep), entity_id=account["id"])

    response = await client.patch(
        f"/api/v1/activities/{activity['id']}",
        json={"body": "Quoted 500 pcs", "entity_id": other["id"], "entity_type": "lead"},
        headers=auth_headers(rep),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["body"] == "Quoted 500 pcs"
    assert body["entity_id"] == account["id"]
    assert body["entity_type"] == "account"


async def test_create_and_update_write_audit_logs(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _account(client, auth_headers(rep))
    activity = await _log(client, auth_headers(rep), entity_id=account["id"])
    await client.patch(
        f"/api/v1/activities/{activity['id']}",
        json={"subject": "Renamed"},
        headers=auth_headers(rep),
    )

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "activity", AuditLog.entity_id == UUID(activity["id"])
    )
    entries = {e.action: e for e in (await session.execute(stmt)).scalars().all()}
    assert entries["create"].actor_id == rep.id
    assert entries["update"].changes == {"subject": ["Follow-up", "Renamed"]}


async def test_account_reassignment_moves_its_activities_and_its_contacts_activities(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    new_owner = await make_user("rep")
    manager = await make_user("manager")
    headers = auth_headers(rep)
    account = await _account(client, headers)
    contact = await _post(client, "contacts", headers, account_id=account["id"], first_name="A")
    on_account = await _log(client, headers, entity_id=account["id"])
    on_contact = await _log(client, headers, entity_type="contact", entity_id=contact["id"])

    await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"owner_id": str(new_owner.id)},
        headers=auth_headers(manager),
    )

    for activity_id in (on_account["id"], on_contact["id"]):
        moved = await client.get(
            f"/api/v1/activities/{activity_id}", headers=auth_headers(new_owner)
        )
        assert moved.status_code == 200
        assert moved.json()["owner_id"] == str(new_owner.id)


async def test_lead_reassignment_moves_its_activities(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    new_owner = await make_user("rep")
    manager = await make_user("manager")
    lead = await _post(client, "leads", auth_headers(rep), name="Lead")
    activity = await _log(client, auth_headers(rep), entity_type="lead", entity_id=lead["id"])

    await client.patch(
        f"/api/v1/leads/{lead['id']}",
        json={"owner_id": str(new_owner.id)},
        headers=auth_headers(manager),
    )

    moved = await client.get(
        f"/api/v1/activities/{activity['id']}", headers=auth_headers(new_owner)
    )
    assert moved.json()["owner_id"] == str(new_owner.id)


async def test_create_enqueues_process_activity(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    stub_enqueue: list[UUID],
) -> None:
    rep = await make_user("rep")
    account = await _account(client, auth_headers(rep))
    activity = await _log(client, auth_headers(rep), entity_id=account["id"])
    assert stub_enqueue == [UUID(activity["id"])]
