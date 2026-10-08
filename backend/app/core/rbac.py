from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, model_validator
from sqlalchemy import ColumnElement, and_, false, or_, true


class Role(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    REP = "rep"


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    MCP = "mcp"
    SYSTEM = "system"


class Action(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class Actor(BaseModel):
    """Carried into every service call. Agents/MCP delegate a human's scope — they never
    exceed the user_id/role/team_id they're acting on behalf of (ARCHITECTURE §3).

    `user_id`/`role` are optional only for `kind=system` (a background job acting on its own,
    e.g. process_activity) — every other kind must carry a real user to delegate from."""

    model_config = {"frozen": True}

    user_id: UUID | None
    role: Role | None = None
    team_id: UUID | None
    kind: ActorKind = ActorKind.HUMAN
    agent_name: str | None = None

    @model_validator(mode="after")
    def _system_actors_omit_identity(self) -> "Actor":
        if self.kind != ActorKind.SYSTEM and (self.user_id is None or self.role is None):
            raise ValueError("user_id and role are required unless kind=system")
        return self


# Resources whose rules diverge from DEFAULT_ROLE_ACTIONS. The catalog is global and
# admin-managed (DOMAIN.md): everyone reads it, only admins write.
RESOURCE_OVERRIDES: dict[str, dict[Role, set[Action]]] = {
    "products": {
        Role.REP: {Action.READ},
        Role.MANAGER: {Action.READ},
    },
}

DEFAULT_ROLE_ACTIONS: dict[Role, set[Action]] = {
    Role.REP: {Action.READ, Action.CREATE, Action.UPDATE},
    Role.MANAGER: {Action.READ, Action.CREATE, Action.UPDATE},
    Role.ADMIN: {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE},
}


def permissions_for(role: Role, resource: str) -> set[Action]:
    return RESOURCE_OVERRIDES.get(resource, {}).get(role, DEFAULT_ROLE_ACTIONS[role])


def can(actor: Actor, resource: str, action: Action) -> bool:
    if actor.role is None:  # a system actor never goes through permission checks
        return False
    return action in permissions_for(actor.role, resource)


def visibility_clause(actor: Actor, model: Any) -> ColumnElement[bool]:
    """Row visibility for an owned aggregate (owner_id + team_id columns required).
    rep: own rows only. manager: team's rows, falling back to owner match for rows with no
    team. admin: everything. Applied inside every scoped list/get query — out-of-scope single
    fetches must come back 404, never 403."""
    if actor.role is None:  # a system actor has no scoped visibility of its own
        return false()
    if actor.role == Role.ADMIN:
        return true()
    if actor.role == Role.MANAGER:
        return or_(
            model.team_id == actor.team_id,
            and_(model.team_id.is_(None), model.owner_id == actor.user_id),
        )
    return model.owner_id == actor.user_id
