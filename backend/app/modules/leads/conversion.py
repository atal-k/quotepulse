from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.normalize import business_domain
from app.core.pagination import PageParams
from app.core.rbac import Actor
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate
from app.modules.accounts.service import AccountService
from app.modules.contacts.schemas import ContactCreate
from app.modules.contacts.service import ContactService
from app.modules.leads.models import Lead
from app.modules.leads.schemas import LeadConvert, LeadConvertResult, LeadRead
from app.modules.leads.service import LeadService, check_transition
from app.modules.opportunities.schemas import OpportunityCreate
from app.modules.opportunities.service import OpportunityService


class LeadConversionService:
    """Lead → Account + Contact + Opportunity in the caller's single transaction, composed purely
    from the other modules' services (each does its own RBAC and audit). Lives beside, not inside,
    `LeadService` because `OpportunityService` already depends on `LeadService`."""

    def __init__(self, session: AsyncSession) -> None:
        self.leads = LeadService(session)
        self.accounts = AccountService(session)
        self.contacts = ContactService(session)
        self.opportunities = OpportunityService(session)

    async def convert(self, actor: Actor, lead_id: UUID, data: LeadConvert) -> LeadConvertResult:
        lead = await self.leads.get(actor, lead_id)
        if lead.status == "converted":
            return await self._existing_result(actor, lead)
        check_transition(lead.status, "converted")

        account, created = await self._resolve_account(actor, lead, data.account_id)
        first_name, _, last_name = lead.name.strip().partition(" ")
        contact = await self.contacts.create(
            actor,
            ContactCreate(
                account_id=account.id,
                first_name=first_name,
                last_name=last_name or None,
                email=lead.email,
                phone=lead.phone,
                is_primary=created,
            ),
        )
        opportunity = await self.opportunities.create(
            actor,
            OpportunityCreate(
                account_id=account.id,
                contact_id=contact.id,
                lead_id=lead.id,
                name=data.opportunity_name or f"{lead.company_name or lead.name} opportunity",
            ),
        )
        lead = await self.leads.mark_converted(actor, lead, account.id, contact.id)
        return self._result(lead, opportunity.id)

    async def _resolve_account(
        self, actor: Actor, lead: Lead, account_id: UUID | None
    ) -> tuple[Account, bool]:
        """The account to attach to, and whether it was just created."""
        if account_id is not None:
            return await self.accounts.get(actor, account_id), False
        domain = business_domain(lead.email)
        if domain is not None:
            existing = await self.accounts.find_by_domain(actor, domain)
            if existing is not None:
                return existing, False
            if await self.accounts.domain_exists(domain):
                raise Conflict(
                    "An account with this email domain exists but is outside your visibility; "
                    "ask a manager to convert this lead or pass an account_id.",
                    {"domain": domain},
                )
        account = await self.accounts.create(
            actor,
            AccountCreate(
                name=lead.company_name or lead.name,
                domain=domain,
                owner_id=lead.owner_id,
                team_id=lead.team_id,
            ),
        )
        return account, True

    async def _existing_result(self, actor: Actor, lead: Lead) -> LeadConvertResult:
        """Re-converting is a no-op that returns the original links, so retries are safe."""
        page = await self.opportunities.list(actor, PageParams(limit=1, offset=0), {"lead_id": lead.id})
        if not page.items or lead.converted_account_id is None or lead.converted_contact_id is None:
            raise NotFound("Converted records for this lead are not visible.", {"id": str(lead.id)})
        return self._result(lead, page.items[0].id)

    @staticmethod
    def _result(lead: Lead, opportunity_id: UUID) -> LeadConvertResult:
        assert lead.converted_account_id is not None and lead.converted_contact_id is not None
        return LeadConvertResult(
            lead=LeadRead.model_validate(lead),
            account_id=lead.converted_account_id,
            contact_id=lead.converted_contact_id,
            opportunity_id=opportunity_id,
        )
