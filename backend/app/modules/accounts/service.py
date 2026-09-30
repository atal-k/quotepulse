from typing import Any

from app.core.errors import PermissionDenied
from app.core.rbac import Actor, Role
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate, AccountUpdate
from app.modules.base import CrudService


class AccountService(CrudService[Account, AccountCreate, AccountUpdate]):
    model = Account
    resource = "accounts"
    entity_type = "account"

    def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        if actor.role == Role.REP:
            payload["owner_id"] = actor.user_id
            payload["team_id"] = actor.team_id
        else:
            payload.setdefault("owner_id", actor.user_id)
            payload.setdefault("team_id", actor.team_id)
        if payload.get("domain"):
            payload["domain"] = payload["domain"].lower()
        return payload

    def authorize_update(self, actor: Actor, obj: Account, payload: dict[str, Any]) -> None:
        if actor.role == Role.REP and ("owner_id" in payload or "team_id" in payload):
            raise PermissionDenied("Only managers/admins can reassign account ownership.")
        if payload.get("domain"):
            payload["domain"] = payload["domain"].lower()
