from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.normalize import business_domain
from app.modules.accounts.models import Account
from app.modules.contacts.models import Contact
from app.modules.identity.models import User
from app.modules.leads.models import Lead
from app.modules.opportunities.models import Opportunity

MakeUser = Callable[..., Awaitable[User]]
AuthHeaders = Callable[[User], dict[str, str]]


def _domain() -> str:
    return f"acme-{uuid4().hex[:8]}.in"


async def _qualified_lead(
    client: AsyncClient, headers: dict[str, str], **fields: Any
) -> dict[str, Any]:
    body = {"name": "Suresh Kumar Iyer", "company_name": "Iyer Forgings", "phone": "9876543210"}
    created = await client.post("/api/v1/leads", json={**body, **fields}, headers=headers)
    assert created.status_code == 201, created.text
    lead = created.json()
    for status in ("contacted", "qualified"):
        step = await client.patch(
            f"/api/v1/leads/{lead['id']}", json={"status": status}, headers=headers
        )
        assert step.status_code == 200, step.text
    return lead


async def _convert(client: AsyncClient, headers: dict[str, str], lead_id: str, **body: Any) -> Any:
    return await client.post(f"/api/v1/leads/{lead_id}/convert", json=body, headers=headers)


async def _get(client: AsyncClient, headers: dict[str, str], path: str, id: str) -> dict[str, Any]:
    response = await client.get(f"/api/v1/{path}/{id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _count(session: AsyncSession, model: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("a@Acme-Bolts.IN", "acme-bolts.in"),
        ("a@gmail.com", None),
        ("a@YAHOO.co.in", None),
        ("a@rediffmail.com", None),
        ("no-at-sign", None),
        (None, None),
        ("", None),
    ],
)
def test_business_domain_skips_free_mail(email: str | None, expected: str | None) -> None:
    assert business_domain(email) == expected


async def test_convert_creates_account_contact_and_opportunity(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    domain = _domain()
    lead = await _qualified_lead(client, headers, email=f"suresh@{domain}")

    response = await _convert(client, headers, lead["id"], opportunity_name="Forgings RFQ")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lead"]["status"] == "converted"
    assert body["lead"]["converted_account_id"] == body["account_id"]
    assert body["lead"]["converted_contact_id"] == body["contact_id"]
    account = await _get(client, headers, "accounts", body["account_id"])
    assert (account["name"], account["domain"], account["status"]) == (
        "Iyer Forgings",
        domain,
        "prospect",
    )
    contact = await _get(client, headers, "contacts", body["contact_id"])
    assert (contact["first_name"], contact["last_name"]) == ("Suresh", "Kumar Iyer")
    assert contact["email"] == f"suresh@{domain}"
    assert contact["phone"] == "+919876543210"
    assert contact["is_primary"] is True
    opp = await _get(client, headers, "opportunities", body["opportunity_id"])
    assert (opp["name"], opp["stage"], opp["lead_id"]) == ("Forgings RFQ", "discovery", lead["id"])
    assert opp["account_id"] == body["account_id"]
    assert opp["contact_id"] == body["contact_id"]


async def test_manager_conversion_keeps_the_leads_owner(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    lead = await _qualified_lead(client, auth_headers(rep), email=f"a@{_domain()}")

    body = (await _convert(client, auth_headers(manager), lead["id"])).json()

    for path, key in (
        ("accounts", "account_id"),
        ("contacts", "contact_id"),
        ("opportunities", "opportunity_id"),
    ):
        row = await _get(client, auth_headers(rep), path, body[key])
        assert row["owner_id"] == str(rep.id)


async def test_existing_visible_account_is_linked_not_duplicated(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    domain = _domain()
    created = await client.post(
        "/api/v1/accounts", json={"name": "Existing Co", "domain": domain}, headers=headers
    )
    lead = await _qualified_lead(client, headers, email=f"x@{domain.upper()}")
    before = await _count(session, Account)

    body = (await _convert(client, headers, lead["id"])).json()

    assert body["account_id"] == created.json()["id"]
    assert await _count(session, Account) == before
    assert (await _get(client, headers, "contacts", body["contact_id"]))["is_primary"] is False


async def test_free_mail_lead_gets_its_own_account_without_a_domain(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    first = await _qualified_lead(client, headers, email="one@gmail.com")
    second = await _qualified_lead(client, headers, email="two@gmail.com")

    a = (await _convert(client, headers, first["id"])).json()
    b = (await _convert(client, headers, second["id"])).json()

    assert a["account_id"] != b["account_id"]
    assert (await _get(client, headers, "accounts", a["account_id"]))["domain"] is None


async def test_lead_without_company_or_email_uses_its_name(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    headers = auth_headers(rep)
    lead = await _qualified_lead(client, headers, company_name=None)

    body = (await _convert(client, headers, lead["id"])).json()

    assert (await _get(client, headers, "accounts", body["account_id"]))["name"] == (
        "Suresh Kumar Iyer"
    )
    opp = await _get(client, headers, "opportunities", body["opportunity_id"])
    assert opp["name"] == "Suresh Kumar Iyer opportunity"


async def test_domain_owned_by_an_invisible_account_conflicts_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    domain = _domain()
    await client.post(
        "/api/v1/accounts",
        json={"name": "Owned by A", "domain": domain},
        headers=auth_headers(rep_a),
    )
    lead = await _qualified_lead(client, auth_headers(rep_b), email=f"x@{domain}")
    models = (Account, Contact, Opportunity)
    before = [await _count(session, m) for m in models]

    response = await _convert(client, auth_headers(rep_b), lead["id"])

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"domain": domain}
    assert [await _count(session, m) for m in models] == before
    assert (await _get(client, auth_headers(rep_b), "leads", lead["id"]))["status"] == "qualified"


async def test_explicit_account_id_is_used_and_must_be_visible(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    mine = await client.post("/api/v1/accounts", json={"name": "Mine"}, headers=auth_headers(rep_b))
    theirs = await client.post(
        "/api/v1/accounts", json={"name": "Theirs"}, headers=auth_headers(rep_a)
    )
    lead = await _qualified_lead(client, auth_headers(rep_b), email=f"x@{_domain()}")

    hidden = await _convert(client, auth_headers(rep_b), lead["id"], account_id=theirs.json()["id"])
    assert hidden.status_code == 404
    linked = await _convert(client, auth_headers(rep_b), lead["id"], account_id=mine.json()["id"])
    assert linked.json()["account_id"] == mine.json()["id"]


@pytest.mark.parametrize("status", ["new", "contacted", "disqualified"])
async def test_only_qualified_leads_convert(
    client: AsyncClient,
    session: AsyncSession,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    status: str,
) -> None:
    rep = await make_user("rep")
    lead = Lead(name="Not Ready", status=status, owner_id=rep.id, team_id=rep.team_id)
    session.add(lead)
    await session.flush()
    accounts = await _count(session, Account)

    response = await _convert(client, auth_headers(rep), str(lead.id))

    assert response.status_code == 409
    assert response.json()["error"]["details"]["from"] == status
    assert await _count(session, Account) == accounts


async def test_convert_is_idempotent_by_state(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _qualified_lead(client, auth_headers(rep), email=f"x@{_domain()}")
    first = (await _convert(client, auth_headers(rep), lead["id"])).json()
    models = (Account, Contact, Opportunity, AuditLog)
    counts = [await _count(session, m) for m in models]

    second = await _convert(client, auth_headers(rep), lead["id"])

    assert second.status_code == 200
    again = second.json()
    for key in ("account_id", "contact_id", "opportunity_id"):
        assert again[key] == first[key]
    assert [await _count(session, m) for m in models] == counts


async def test_out_of_scope_lead_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep_a = await make_user("rep")
    rep_b = await make_user("rep")
    lead = await _qualified_lead(client, auth_headers(rep_a))

    assert (await _convert(client, auth_headers(rep_b), lead["id"])).status_code == 404


async def test_conversion_audits_every_record(
    client: AsyncClient, session: AsyncSession, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    rep = await make_user("rep")
    lead = await _qualified_lead(client, auth_headers(rep), email=f"x@{_domain()}")
    body = (await _convert(client, auth_headers(rep), lead["id"])).json()

    async def entry(entity_type: str, entity_id: str, action: str) -> AuditLog:
        stmt = select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == UUID(entity_id),
            AuditLog.action == action,
        )
        return (await session.execute(stmt)).scalar_one()

    for entity_type, key in (
        ("account", "account_id"),
        ("contact", "contact_id"),
        ("opportunity", "opportunity_id"),
    ):
        assert (await entry(entity_type, body[key], "create")).actor_id == rep.id
    stmt = select(AuditLog).where(
        AuditLog.entity_type == "lead",
        AuditLog.entity_id == UUID(lead["id"]),
        AuditLog.action == "update",
    )
    updates = [e.changes for e in (await session.execute(stmt)).scalars().all()]
    (converting,) = [c for c in updates if c.get("status", [None, None])[1] == "converted"]
    assert converting["status"] == ["qualified", "converted"]
    assert converting["converted_account_id"] == [None, body["account_id"]]
