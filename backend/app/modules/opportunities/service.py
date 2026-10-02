import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.core.rbac import Action, Actor, Role
from app.modules.accounts.service import AccountService
from app.modules.base import CrudService
from app.modules.contacts.service import ContactService
from app.modules.leads.service import LeadService
from app.modules.opportunities.models import Opportunity
from app.modules.opportunities.schemas import OpportunityCreate, OpportunityUpdate
from app.modules.ownership import cascade_ownership

# `won` is reachable from every open stage because a quotation can be accepted at any of them,
# but only through `mark_won` (see `authorize_update`).
TRANSITIONS: dict[str, set[str]] = {
    "discovery": {"proposal", "won", "lost"},
    "proposal": {"negotiation", "won", "lost"},
    "negotiation": {"won", "lost"},
    "won": set(),
    "lost": set(),
}

_NOT_NULLABLE = ("name", "stage", "amount", "currency")


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS[current]:
        raise Conflict(
            f"Opportunity cannot move from '{current}' to '{target}'.",
            {"from": current, "to": target, "allowed": sorted(TRANSITIONS[current])},
        )


def _now() -> datetime:
    return datetime.now(UTC)


class OpportunityService(CrudService[Opportunity, OpportunityCreate, OpportunityUpdate]):
    model = Opportunity
    resource = "opportunities"
    entity_type = "opportunity"

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        # Scoped get: an account the actor can't see is a 404, same as reading it.
        account = await AccountService(self.session).get(actor, payload["account_id"])
        payload["owner_id"] = account.owner_id
        payload["team_id"] = account.team_id
        if payload.get("contact_id"):
            await self._require_contact_of(actor, payload["contact_id"], account.id)
        if payload.get("lead_id"):
            await LeadService(self.session).get(actor, payload["lead_id"])
        if payload.get("currency"):
            payload["currency"] = payload["currency"].upper()
        return payload

    async def authorize_update(
        self, actor: Actor, obj: Opportunity, payload: dict[str, Any]
    ) -> None:
        for field in _NOT_NULLABLE:
            if field in payload and payload[field] is None:
                raise ValidationFailed(f"{field} cannot be null.", {"field": field})
        if actor.role == Role.REP and ("owner_id" in payload or "team_id" in payload):
            raise PermissionDenied("Only managers/admins can reassign opportunity ownership.")
        if payload.get("contact_id"):
            await self._require_contact_of(actor, payload["contact_id"], obj.account_id)
        if payload.get("currency"):
            payload["currency"] = payload["currency"].upper()
        self._apply_stage_rules(obj, payload)

    async def after_update(
        self, actor: Actor, obj: Opportunity, changes: dict[str, list[Any]]
    ) -> None:
        if "owner_id" in changes or "team_id" in changes:
            await cascade_ownership(
                self.session, actor, self.entity_type, obj.id, obj.owner_id, obj.team_id
            )

    async def mark_won(self, actor: Actor, id: uuid.UUID) -> Opportunity:
        """Internal transition to `won`, called when a quotation is accepted. Not reachable through
        the public update path."""
        obj = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        check_transition(obj.stage, "won")
        return await self._apply_update(actor, obj, {"stage": "won", "closed_at": _now()})

    async def _require_contact_of(
        self, actor: Actor, contact_id: uuid.UUID, account_id: uuid.UUID
    ) -> None:
        contact = await ContactService(self.session).get(actor, contact_id)
        if contact.account_id != account_id:
            raise ValidationFailed(
                "Contact does not belong to this opportunity's account.",
                {"field": "contact_id"},
            )

    @staticmethod
    def _apply_stage_rules(obj: Opportunity, payload: dict[str, Any]) -> None:
        target = payload.get("stage")
        if target is not None and target != obj.stage:
            check_transition(obj.stage, target)
            if target == "won":
                raise Conflict("Opportunities are won when a quotation is accepted, not by stage.")
            if target == "lost":
                payload["closed_at"] = _now()
        resulting = target or obj.stage
        if resulting == "lost":
            if not payload.get("lost_reason", obj.lost_reason):
                raise ValidationFailed("lost_reason is required to mark lost.", {"field": "lost_reason"})
        elif payload.get("lost_reason"):
            raise ValidationFailed("lost_reason only applies to lost opportunities.", {"field": "lost_reason"})
