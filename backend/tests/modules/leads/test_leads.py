from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import Team, User
from app.modules.leads.models import Lead
from app.modules.leads.service import TRANSITIONS

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


async def _create_lead(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/leads", json={"name": "Suresh Iyer", **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _patch(client: AsyncClient, headers: dict[str, str], lead_id: str, **fields: Any) -> Any:
    return await client.patch(f"/api/v1/leads/{lead_id}", json=fields, headers=headers)


async def _insert_lead(session: AsyncSession, owner: User, status: str) -> Lead:
    lead = Lead(name="Seeded", status=status, owner_id=owner.id, team_id=owner.team_id)
    session.add(lead)
    await session.flush()
    return lead


async def test_create_defaults(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, team: Team
) -> None:
    rep = await make_user("rep")

    lead = await _create_lead(client, auth_headers(rep), company_name="Iyer Forgings")

    assert lead["status"] == "new"
    assert lead["owner_id"] == str(rep.id)
    assert lead["team_id"] == str(team.id)
    assert lead["converted_account_id"] is None
    assert lead["converted_contact_id"] is None


async def test_create_ignores_status_and_converted_links(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")

    lead = await _create_lead(client, auth_headers(rep), status="qualified")

    assert lead["status"] == "new"


async def test_email_and_phone_are_normalized(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")

    lead = await _create_lead(
        client, auth_headers(rep), email="Suresh@Iyer-Forgings.IN", phone="098765 43210"
    )

    assert lead["email"] == "suresh@iyer-forgings.in"
    assert lead["phone"] == "+919876543210"


async def test_qualification_and_score_round_trip(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _create_lead(client, auth_headers(rep), score=40)

    response = await _patch(
        client,
        auth_headers(rep),
        lead["id"],
        score=75,
        qualification={"budget": "INR 5L", "timeline": "Q4"},
    )

    body = response.json()
    assert body["score"] == 75
    assert body["qualification"] == {
        "budget": "INR 5L",
        "authority": None,
        "need": None,
        "timeline": "Q4",
    }


@pytest.mark.parametrize("score", [-1, 101])
async def test_score_out_of_range_is_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, score: int
) -> None:
    rep = await make_user("rep")
    response = await client.post(
        "/api/v1/leads", json={"name": "X", "score": score}, headers=auth_headers(rep)
    )
    assert response.status_code == 422


async def test_database_rejects_out_of_range_score(
    session: AsyncSession, make_user: MakeUser
) -> None:
    rep = await make_user("rep")
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(Lead(name="X", score=101, owner_id=rep.id, team_id=rep.team_id))
            await session.flush()


async def test_invalid_phone_and_null_name_are_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    bad_phone = await client.post(
        "/api/v1/leads", json={"name": "X", "phone": "12"}, headers=auth_headers(rep)
    )
    assert bad_phone.status_code == 422

    lead = await _create_lead(client, auth_headers(rep))
    null_name = await _patch(client, auth_headers(rep), lead["id"], name=None)
    assert null_name.status_code == 422


async def test_rep_only_sees_own_leads_and_out_of_scope_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    lead_a = await _create_lead(client, auth_headers(rep_a))
    await _create_lead(client, auth_headers(rep_b))

    listing = await client.get("/api/v1/leads", headers=auth_headers(rep_a))
    assert [item["id"] for item in listing.json()["items"]] == [lead_a["id"]]
    assert (
        await client.get(f"/api/v1/leads/{lead_a['id']}", headers=auth_headers(rep_b))
    ).status_code == 404
    assert (
        await _patch(client, auth_headers(rep_b), lead_a["id"], name="Hijack")
    ).status_code == 404


async def test_manager_sees_team_not_other_teams_and_admin_sees_all(
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
    in_team = await _create_lead(client, auth_headers(rep_in_team))
    elsewhere = await _create_lead(client, auth_headers(rep_elsewhere))

    manager_view = await client.get("/api/v1/leads", headers=auth_headers(manager))
    assert {item["id"] for item in manager_view.json()["items"]} == {in_team["id"]}
    admin_view = await client.get("/api/v1/leads?limit=100", headers=auth_headers(admin))
    assert {in_team["id"], elsewhere["id"]} <= {item["id"] for item in admin_view.json()["items"]}


async def test_rep_cannot_reassign_but_manager_can_and_rep_create_ignores_owner(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    other_rep = await make_user("rep")
    manager = await make_user("manager")
    lead = await _create_lead(client, auth_headers(rep), owner_id=str(other_rep.id))
    assert lead["owner_id"] == str(rep.id)

    denied = await _patch(client, auth_headers(rep), lead["id"], owner_id=str(other_rep.id))
    assert denied.status_code == 403

    moved = await _patch(client, auth_headers(manager), lead["id"], owner_id=str(other_rep.id))
    assert moved.status_code == 200
    assert moved.json()["owner_id"] == str(other_rep.id)


async def test_list_filters_by_status_and_source(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    web = await _create_lead(client, auth_headers(rep), source="website")
    await _create_lead(client, auth_headers(rep), source="referral")
    await _patch(client, auth_headers(rep), web["id"], status="contacted")

    by_status = await client.get("/api/v1/leads?status=contacted", headers=auth_headers(rep))
    assert [i["id"] for i in by_status.json()["items"]] == [web["id"]]
    by_source = await client.get("/api/v1/leads?source=referral", headers=auth_headers(rep))
    assert by_source.json()["total"] == 1
    bad_status = await client.get("/api/v1/leads?status=bogus", headers=auth_headers(rep))
    assert bad_status.status_code == 422


async def test_happy_path_walks_new_to_qualified(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _create_lead(client, auth_headers(rep))

    for status in ("contacted", "qualified"):
        response = await _patch(client, auth_headers(rep), lead["id"], status=status)
        assert response.status_code == 200
        assert response.json()["status"] == status


@pytest.mark.parametrize("start", ["new", "contacted", "qualified"])
async def test_any_open_status_can_be_disqualified(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
) -> None:
    rep = await make_user("rep")
    lead = await _insert_lead(session, rep, start)

    response = await _patch(client, auth_headers(rep), str(lead.id), status="disqualified")

    assert response.status_code == 200
    assert response.json()["status"] == "disqualified"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (start, target)
        for start in TRANSITIONS
        for target in TRANSITIONS
        if start != target and target not in TRANSITIONS[start] and target != "converted"
    ],
)
async def test_invalid_transitions_are_conflicts(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
    target: str,
) -> None:
    rep = await make_user("rep")
    lead = await _insert_lead(session, rep, start)

    response = await _patch(client, auth_headers(rep), str(lead.id), status=target)

    assert response.status_code == 409
    assert response.json()["error"]["details"]["from"] == start


@pytest.mark.parametrize("start", ["new", "contacted", "qualified", "converted", "disqualified"])
async def test_status_cannot_be_set_to_converted_through_patch(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
) -> None:
    rep = await make_user("rep")
    lead = await _insert_lead(session, rep, start)

    response = await _patch(client, auth_headers(rep), str(lead.id), status="converted")

    # converted -> converted is a no-op, everything else must go through the convert action.
    assert response.status_code == (200 if start == "converted" else 409)


async def test_same_status_patch_is_a_noop_not_a_conflict(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _insert_lead(session, rep, "disqualified")

    response = await _patch(client, auth_headers(rep), str(lead.id), status="disqualified")

    assert response.status_code == 200


async def test_create_update_and_status_change_write_audit_logs(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _create_lead(client, auth_headers(rep))
    await _patch(client, auth_headers(rep), lead["id"], status="contacted")

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "lead", AuditLog.entity_id == UUID(lead["id"])
    )
    entries = {e.action: e for e in (await session.execute(stmt)).scalars().all()}
    assert entries["create"].actor_id == rep.id
    assert entries["create"].changes["name"] == [None, "Suresh Iyer"]
    assert entries["update"].changes == {"status": ["new", "contacted"]}
