"""Ownership cascade (ARCHITECTURE §3): child documents inherit `owner_id`/`team_id` from their
parent, so when a manager/admin reassigns a parent the change has to reach everything below it.

`CASCADE` is an explicit parent → children table rather than import-time self-registration, so
the full ownership graph is greppable in one place. Importing child models here is a deliberate,
documented exception to "modules don't import each other's models" (like `identity`).

The child queries are intentionally unscoped: this is a system-level propagation of a change the
actor was already authorized to make on the parent, not a read on the actor's behalf.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.rbac import Actor
from app.modules.contacts.models import Contact
from app.modules.opportunities.models import Opportunity


@dataclass(frozen=True)
class OwnedChild:
    entity_type: str  # the child's audit-log entity_type; also its key in CASCADE for recursion
    model: Any
    link: Callable[[uuid.UUID], ColumnElement[bool]]  # parent id → clause selecting its children


CASCADE: dict[str, list[OwnedChild]] = {
    "account": [
        OwnedChild("contact", Contact, lambda parent_id: Contact.account_id == parent_id),
        OwnedChild(
            "opportunity", Opportunity, lambda parent_id: Opportunity.account_id == parent_id
        ),
    ],
}


async def cascade_ownership(
    session: AsyncSession,
    actor: Actor,
    parent_type: str,
    parent_id: uuid.UUID,
    owner_id: uuid.UUID,
    team_id: uuid.UUID | None,
) -> None:
    for child in CASCADE.get(parent_type, []):
        rows = (await session.execute(select(child.model).where(child.link(parent_id)))).scalars()
        for row in rows.all():
            changes: dict[str, list[Any]] = {}
            if row.owner_id != owner_id:
                changes["owner_id"] = [str(row.owner_id), str(owner_id)]
            if row.team_id != team_id:
                changes["team_id"] = [
                    str(row.team_id) if row.team_id else None,
                    str(team_id) if team_id else None,
                ]
            if not changes:
                continue
            row.owner_id = owner_id
            row.team_id = team_id
            await session.flush()
            await audit.record(session, actor, "reassign", child.entity_type, row.id, changes)
            await cascade_ownership(session, actor, child.entity_type, row.id, owner_id, team_id)
