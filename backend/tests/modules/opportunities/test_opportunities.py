from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.errors import Conflict, NotFound
from app.core.rbac import Actor, Role
from app.modules.identity.models import Team, User
from app.modules.opportunities.models import Opportunity
from app.modules.opportunities.service import TRANSITIONS, OpportunityService

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]
OPEN_STAGES = ["discovery", "proposal", "negotiation"]


async def _post(
    client: AsyncClient, path: str, headers: dict[str, str], **body: Any
) -> dict[str, Any]:
    response = await client.post(f"/api/v1/{path}", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_opportunity(
    client: AsyncClient, headers: dict[str, str], account_id: str, **fields: Any
) -> dict[str, Any]:
    return await _post(
        client, "opportunities", headers, account_id=account_id, name="Bolt supply", **fields
    )


async def _account_with_opportunity(
    client: AsyncClient, rep: User, headers: dict[str, str], **fields: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    account = await _post(client, "accounts", headers, name=f"Acme {uuid4().hex[:6]}")
    return account, await _create_opportunity(client, headers, account["id"], **fields)


async def _patch(client: AsyncClient, headers: dict[str, str], opp_id: str, **fields: Any) -> Any:
    return await client.patch(f"/api/v1/opportunities/{opp_id}", json=fields, headers=headers)


async def _insert(session: AsyncSession, owner: User, account_id: str, stage: str) -> Opportunity:
    opp = Opportunity(
        account_id=UUID(account_id),
        name="Seeded",
        stage=stage,
        lost_reason="price" if stage == "lost" else None,
        owner_id=owner.id,
        team_id=owner.team_id,
    )
    session.add(opp)
    await session.flush()
    return opp


def _actor(user: User) -> Actor:
    return Actor(user_id=user.id, role=Role(user.role), team_id=user.team_id)


async def _audit(session: AsyncSession, entity_id: str, action: str) -> list[AuditLog]:
    stmt = select(AuditLog).where(
        AuditLog.entity_type == "opportunity",
        AuditLog.entity_id == UUID(entity_id),
        AuditLog.action == action,
    )
    return list((await session.execute(stmt)).scalars().all())


async def test_create_defaults_and_inherits_owner_from_account(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, team: Team
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")

    opp = await _create_opportunity(client, auth_headers(manager), account["id"], currency="inr")

    assert opp["stage"] == "discovery"
    assert opp["owner_id"] == str(rep.id)
    assert opp["team_id"] == str(team.id)
    assert Decimal(opp["amount"]) == 0
    assert opp["currency"] == "INR"
    assert opp["closed_at"] is None


async def test_create_ignores_stage(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep), stage="won")
    assert opp["stage"] == "discovery"


async def test_create_on_out_of_scope_account_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep_a), name="A's")

    response = await client.post(
        "/api/v1/opportunities",
        json={"account_id": account["id"], "name": "Sneaky"},
        headers=auth_headers(rep_b),
    )
    assert response.status_code == 404


async def test_contact_must_belong_to_the_opportunity_account(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    account = await _post(client, "accounts", headers, name="Acme")
    other_account = await _post(client, "accounts", headers, name="Other")
    own_contact = await _post(client, "contacts", headers, account_id=account["id"], first_name="A")
    foreign_contact = await _post(
        client, "contacts", headers, account_id=other_account["id"], first_name="B"
    )

    ok = await _create_opportunity(client, headers, account["id"], contact_id=own_contact["id"])
    assert ok["contact_id"] == own_contact["id"]

    bad = await client.post(
        "/api/v1/opportunities",
        json={"account_id": account["id"], "name": "X", "contact_id": foreign_contact["id"]},
        headers=headers,
    )
    assert bad.status_code == 422
    bad_update = await _patch(client, headers, ok["id"], contact_id=foreign_contact["id"])
    assert bad_update.status_code == 422
    unlink = await _patch(client, headers, ok["id"], contact_id=None)
    assert unlink.json()["contact_id"] is None


async def test_out_of_scope_contact_or_lead_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account_a = await _post(client, "accounts", auth_headers(rep_a), name="A's")
    contact_a = await _post(
        client, "contacts", auth_headers(rep_a), account_id=account_a["id"], first_name="A"
    )
    lead_a = await _post(client, "leads", auth_headers(rep_a), name="A's lead")
    account_b = await _post(client, "accounts", auth_headers(rep_b), name="B's")

    for extra in ({"contact_id": contact_a["id"]}, {"lead_id": lead_a["id"]}):
        response = await client.post(
            "/api/v1/opportunities",
            json={"account_id": account_b["id"], "name": "X", **extra},
            headers=auth_headers(rep_b),
        )
        assert response.status_code == 404


async def test_lead_link_is_set_on_create_and_immutable(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    lead = await _post(client, "leads", headers, name="Lead")
    other_lead = await _post(client, "leads", headers, name="Other lead")
    account = await _post(client, "accounts", headers, name="Acme")
    opp = await _create_opportunity(client, headers, account["id"], lead_id=lead["id"])

    response = await _patch(
        client, headers, opp["id"], lead_id=other_lead["id"], account_id=str(uuid4())
    )

    assert response.status_code == 200
    assert response.json()["lead_id"] == lead["id"]
    assert response.json()["account_id"] == account["id"]


async def test_rep_only_sees_own_and_out_of_scope_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    _, opp_a = await _account_with_opportunity(client, rep_a, auth_headers(rep_a))
    await _account_with_opportunity(client, rep_b, auth_headers(rep_b))

    listing = await client.get("/api/v1/opportunities", headers=auth_headers(rep_a))
    assert [i["id"] for i in listing.json()["items"]] == [opp_a["id"]]
    assert (
        await client.get(f"/api/v1/opportunities/{opp_a['id']}", headers=auth_headers(rep_b))
    ).status_code == 404
    assert (
        await _patch(client, auth_headers(rep_b), opp_a["id"], name="Hijack")
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
    _, in_team = await _account_with_opportunity(client, rep_in_team, auth_headers(rep_in_team))
    _, elsewhere = await _account_with_opportunity(
        client, rep_elsewhere, auth_headers(rep_elsewhere)
    )

    manager_view = await client.get("/api/v1/opportunities", headers=auth_headers(manager))
    assert {i["id"] for i in manager_view.json()["items"]} == {in_team["id"]}
    admin_view = await client.get("/api/v1/opportunities?limit=100", headers=auth_headers(admin))
    assert {in_team["id"], elsewhere["id"]} <= {i["id"] for i in admin_view.json()["items"]}


async def test_rep_cannot_reassign_but_manager_can(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    other_rep = await make_user("rep")
    manager = await make_user("manager")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))

    denied = await _patch(client, auth_headers(rep), opp["id"], owner_id=str(other_rep.id))
    assert denied.status_code == 403
    moved = await _patch(client, auth_headers(manager), opp["id"], owner_id=str(other_rep.id))
    assert moved.json()["owner_id"] == str(other_rep.id)


async def test_list_filters_by_account_and_stage(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    account_1, opp_1 = await _account_with_opportunity(client, rep, headers)
    _, opp_2 = await _account_with_opportunity(client, rep, headers)
    await _patch(client, headers, opp_2["id"], stage="proposal")

    by_account = await client.get(
        f"/api/v1/opportunities?account_id={account_1['id']}", headers=headers
    )
    assert [i["id"] for i in by_account.json()["items"]] == [opp_1["id"]]
    by_stage = await client.get("/api/v1/opportunities?stage=proposal", headers=headers)
    assert [i["id"] for i in by_stage.json()["items"]] == [opp_2["id"]]
    assert (
        await client.get("/api/v1/opportunities?stage=bogus", headers=headers)
    ).status_code == 422


async def test_happy_path_walks_discovery_to_negotiation(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))

    for stage in ("proposal", "negotiation"):
        response = await _patch(client, auth_headers(rep), opp["id"], stage=stage)
        assert response.status_code == 200
        assert response.json()["stage"] == stage
        assert response.json()["closed_at"] is None


@pytest.mark.parametrize("start", OPEN_STAGES)
async def test_lost_requires_reason_and_sets_closed_at(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], start)

    missing = await _patch(client, auth_headers(rep), str(opp.id), stage="lost")
    assert missing.status_code == 422
    assert missing.json()["error"]["details"]["field"] == "lost_reason"

    lost = await _patch(
        client, auth_headers(rep), str(opp.id), stage="lost", lost_reason="Price too high"
    )
    assert lost.status_code == 200
    assert lost.json()["stage"] == "lost"
    assert lost.json()["lost_reason"] == "Price too high"
    assert lost.json()["closed_at"] is not None


async def test_lost_reason_only_applies_to_lost(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))

    response = await _patch(client, auth_headers(rep), opp["id"], lost_reason="because")

    assert response.status_code == 422


async def test_lost_reason_cannot_be_cleared_on_a_lost_opportunity(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))
    await _patch(client, auth_headers(rep), opp["id"], stage="lost", lost_reason="Price")

    response = await _patch(client, auth_headers(rep), opp["id"], lost_reason=None)

    assert response.status_code == 422


@pytest.mark.parametrize("start", OPEN_STAGES)
async def test_won_cannot_be_set_through_patch(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], start)

    response = await _patch(client, auth_headers(rep), str(opp.id), stage="won")

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (start, target)
        for start in TRANSITIONS
        for target in TRANSITIONS
        if start != target and target not in TRANSITIONS[start]
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
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], start)

    response = await _patch(
        client, auth_headers(rep), str(opp.id), stage=target, lost_reason="price"
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"]["from"] == start


async def test_same_stage_patch_is_a_noop_not_a_conflict(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], "lost")

    response = await _patch(client, auth_headers(rep), str(opp.id), stage="lost")

    assert response.status_code == 200


@pytest.mark.parametrize("start", OPEN_STAGES)
async def test_mark_won_closes_from_any_open_stage_and_audits(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    start: str,
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], start)

    won = await OpportunityService(session).mark_won(_actor(rep), opp.id)

    assert won.stage == "won"
    assert won.closed_at is not None
    (entry,) = await _audit(session, str(opp.id), "update")
    assert entry.changes["stage"] == [start, "won"]
    assert entry.actor_id == rep.id


@pytest.mark.parametrize("closed", ["won", "lost"])
async def test_mark_won_on_a_closed_opportunity_is_a_conflict(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    closed: str,
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    opp = await _insert(session, rep, account["id"], closed)

    with pytest.raises(Conflict):
        await OpportunityService(session).mark_won(_actor(rep), opp.id)


async def test_mark_won_respects_visibility(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep_a), name="A's")
    opp = await _insert(session, rep_a, account["id"], "proposal")

    with pytest.raises(NotFound):
        await OpportunityService(session).mark_won(_actor(rep_b), opp.id)


async def test_account_reassignment_cascades_to_opportunities(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    new_owner = await make_user("rep")
    manager = await make_user("manager")
    account, opp = await _account_with_opportunity(client, rep, auth_headers(rep))

    response = await client.patch(
        f"/api/v1/accounts/{account['id']}",
        json={"owner_id": str(new_owner.id)},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200

    moved = await client.get(f"/api/v1/opportunities/{opp['id']}", headers=auth_headers(new_owner))
    assert moved.json()["owner_id"] == str(new_owner.id)
    old = await client.get(f"/api/v1/opportunities/{opp['id']}", headers=auth_headers(rep))
    assert old.status_code == 404
    (entry,) = await _audit(session, opp["id"], "reassign")
    assert entry.changes == {"owner_id": [str(rep.id), str(new_owner.id)]}


async def test_invalid_input_is_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    for bad in (
        {"amount": "-1"},
        {"probability": 101},
        {"probability": -1},
        {"currency": "RUPEES"},
    ):
        response = await client.post(
            "/api/v1/opportunities",
            json={"account_id": account["id"], "name": "X", **bad},
            headers=auth_headers(rep),
        )
        assert response.status_code == 422, bad

    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))
    for field in ("name", "stage", "amount", "currency"):
        response = await _patch(client, auth_headers(rep), opp["id"], **{field: None})
        assert response.status_code == 422, field


async def test_database_enforces_amount_and_probability_ranges(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    account = await _post(client, "accounts", auth_headers(rep), name="Acme")
    for fields in ({"amount": Decimal("-1")}, {"probability": 101}):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    Opportunity(
                        account_id=UUID(account["id"]),
                        name="Bad",
                        owner_id=rep.id,
                        team_id=rep.team_id,
                        **fields,
                    )
                )
                await session.flush()


async def test_create_and_update_write_audit_logs(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    _, opp = await _account_with_opportunity(client, rep, auth_headers(rep))
    await _patch(client, auth_headers(rep), opp["id"], stage="proposal")

    (created,) = await _audit(session, opp["id"], "create")
    assert created.actor_id == rep.id
    assert created.changes["name"] == [None, "Bolt supply"]
    (updated,) = await _audit(session, opp["id"], "update")
    assert updated.changes == {"stage": ["discovery", "proposal"]}
