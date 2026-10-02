import uuid
from typing import Any

from sqlalchemy import select

from app.core import audit
from app.core.errors import ValidationFailed
from app.core.normalize import normalize_email, normalize_phone
from app.core.rbac import Actor
from app.modules.accounts.service import AccountService
from app.modules.base import CrudService
from app.modules.contacts.models import Contact
from app.modules.contacts.schemas import ContactCreate, ContactUpdate

_NOT_NULLABLE = ("first_name", "is_primary")


def _normalize(payload: dict[str, Any]) -> None:
    if payload.get("email"):
        payload["email"] = normalize_email(payload["email"])
    if payload.get("phone"):
        payload["phone"] = normalize_phone(payload["phone"])


class ContactService(CrudService[Contact, ContactCreate, ContactUpdate]):
    model = Contact
    resource = "contacts"
    entity_type = "contact"

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        # Scoped get: an account outside the actor's visibility is a 404, same as reading it.
        account = await AccountService(self.session).get(actor, payload["account_id"])
        payload["owner_id"] = account.owner_id
        payload["team_id"] = account.team_id
        _normalize(payload)
        if payload.get("is_primary"):
            await self._demote_primary(actor, account.id)
        return payload

    async def authorize_update(self, actor: Actor, obj: Contact, payload: dict[str, Any]) -> None:
        for field in _NOT_NULLABLE:
            if field in payload and payload[field] is None:
                raise ValidationFailed(f"{field} cannot be null.", {"field": field})
        _normalize(payload)
        if payload.get("is_primary") and not obj.is_primary:
            await self._demote_primary(actor, obj.account_id)

    async def _demote_primary(self, actor: Actor, account_id: uuid.UUID) -> None:
        """At most one primary contact per account: promoting one demotes the previous. Unscoped
        on purpose — contacts inherit the account's owner, and the DB has a partial unique index
        as the backstop."""
        stmt = select(Contact).where(Contact.account_id == account_id, Contact.is_primary.is_(True))
        for previous in (await self.session.execute(stmt)).scalars().all():
            previous.is_primary = False
            await self.session.flush()
            await audit.record(
                self.session,
                actor,
                "update",
                self.entity_type,
                previous.id,
                {"is_primary": [True, False]},
            )
