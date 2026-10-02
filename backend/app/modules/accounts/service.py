from typing import Any

from sqlalchemy import select

from app.core.errors import PermissionDenied
from app.core.rbac import Action, Actor, Role
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate, AccountUpdate
from app.modules.base import CrudService
from app.modules.ownership import cascade_ownership


class AccountService(CrudService[Account, AccountCreate, AccountUpdate]):
    model = Account
    resource = "accounts"
    entity_type = "account"

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        if actor.role == Role.REP:
            payload["owner_id"] = actor.user_id
            payload["team_id"] = actor.team_id
        else:
            payload.setdefault("owner_id", actor.user_id)
            payload.setdefault("team_id", actor.team_id)
        if payload.get("domain"):
            payload["domain"] = payload["domain"].lower()
        return payload

    async def authorize_update(self, actor: Actor, obj: Account, payload: dict[str, Any]) -> None:
        if actor.role == Role.REP and ("owner_id" in payload or "team_id" in payload):
            raise PermissionDenied("Only managers/admins can reassign account ownership.")
        if payload.get("domain"):
            payload["domain"] = payload["domain"].lower()

    async def after_update(self, actor: Actor, obj: Account, changes: dict[str, list[Any]]) -> None:
        if "owner_id" in changes or "team_id" in changes:
            await cascade_ownership(
                self.session, actor, self.entity_type, obj.id, obj.owner_id, obj.team_id
            )

    async def find_by_domain(self, actor: Actor, domain: str) -> Account | None:
        """The account with this domain, if the actor can see it."""
        self._require(actor, Action.READ)
        stmt = select(Account).where(Account.domain == domain.lower(), self._visible(actor))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def domain_exists(self, domain: str) -> bool:
        """Whether any account has this domain, regardless of visibility. Domain is globally
        unique, so callers use this to turn a would-be unique violation into a clean Conflict."""
        stmt = select(Account.id).where(Account.domain == domain.lower())
        return (await self.session.execute(stmt)).first() is not None
