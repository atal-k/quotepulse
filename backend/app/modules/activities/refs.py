from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Actor
from app.modules.accounts.service import AccountService
from app.modules.activities.enums import EntityType
from app.modules.contacts.service import ContactService
from app.modules.leads.service import LeadService
from app.modules.opportunities.service import OpportunityService

_PARENT_SERVICES = {
    EntityType.ACCOUNT: AccountService,
    EntityType.CONTACT: ContactService,
    EntityType.LEAD: LeadService,
    EntityType.OPPORTUNITY: OpportunityService,
}


async def load_parent(
    session: AsyncSession, actor: Actor, entity_type: EntityType, entity_id: UUID
) -> Any:
    """The polymorphic parent, loaded through its own service so existence and visibility are
    checked by the same rules as reading it. Missing or out of scope is a 404."""
    service = _PARENT_SERVICES[entity_type](session)
    return await service.get(actor, entity_id)
