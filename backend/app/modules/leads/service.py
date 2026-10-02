import uuid
from typing import Any

from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.core.normalize import normalize_email, normalize_phone
from app.core.rbac import Action, Actor, Role
from app.modules.base import CrudService
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadCreate, LeadUpdate

TRANSITIONS: dict[str, set[str]] = {
    "new": {"contacted", "disqualified"},
    "contacted": {"qualified", "disqualified"},
    "qualified": {"converted", "disqualified"},
    "converted": set(),
    "disqualified": set(),
}

_NOT_NULLABLE = ("name", "status")


def _normalize(payload: dict[str, Any]) -> None:
    if payload.get("email"):
        payload["email"] = normalize_email(payload["email"])
    if payload.get("phone"):
        payload["phone"] = normalize_phone(payload["phone"])


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS[current]:
        raise Conflict(
            f"Lead cannot move from '{current}' to '{target}'.",
            {"from": current, "to": target, "allowed": sorted(TRANSITIONS[current])},
        )


class LeadService(CrudService[Lead, LeadCreate, LeadUpdate]):
    model = Lead
    resource = "leads"
    entity_type = "lead"

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        if actor.role == Role.REP:
            payload["owner_id"] = actor.user_id
            payload["team_id"] = actor.team_id
        else:
            payload.setdefault("owner_id", actor.user_id)
            payload.setdefault("team_id", actor.team_id)
        _normalize(payload)
        return payload

    async def authorize_update(self, actor: Actor, obj: Lead, payload: dict[str, Any]) -> None:
        for field in _NOT_NULLABLE:
            if field in payload and payload[field] is None:
                raise ValidationFailed(f"{field} cannot be null.", {"field": field})
        if actor.role == Role.REP and ("owner_id" in payload or "team_id" in payload):
            raise PermissionDenied("Only managers/admins can reassign lead ownership.")
        _normalize(payload)
        target = payload.get("status")
        if target is not None and target != obj.status:
            if target == "converted":
                raise Conflict("Leads are converted through the convert action, not by status.")
            check_transition(obj.status, target)

    async def mark_converted(
        self, actor: Actor, lead: Lead, account_id: uuid.UUID, contact_id: uuid.UUID
    ) -> Lead:
        """Internal transition to `converted`, used only by the convert flow."""
        self._require(actor, Action.UPDATE)
        check_transition(lead.status, "converted")
        payload = {
            "status": "converted",
            "converted_account_id": account_id,
            "converted_contact_id": contact_id,
        }
        return await self._apply_update(actor, lead, payload)
