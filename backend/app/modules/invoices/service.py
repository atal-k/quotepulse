import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core import audit
from app.core.errors import Conflict, ValidationFailed
from app.core.rbac import Action, Actor
from app.modules.base import CrudService
from app.modules.document_sequences.service import DocumentKind, next_number
from app.modules.invoices.models import OPEN_STATUSES, Invoice
from app.modules.invoices.schemas import PaymentCreate

DEFAULT_PAYMENT_TERMS_DAYS = 30


class InvoiceService(CrudService[Invoice, PaymentCreate, PaymentCreate]):
    """Invoices are created only by shipping an order, and changed only by payments and voiding.
    The generic update path is not exposed, so the create/update generics are only for typing."""

    model = Invoice
    resource = "invoices"
    entity_type = "invoice"

    async def create_for_order(
        self,
        actor: Actor,
        *,
        order_id: uuid.UUID,
        account_id: uuid.UUID,
        owner_id: uuid.UUID,
        team_id: uuid.UUID | None,
        total: Decimal,
        payment_terms_days: int | None,
    ) -> Invoice:
        issue_date = datetime.now(UTC).date()
        terms = payment_terms_days if payment_terms_days is not None else DEFAULT_PAYMENT_TERMS_DAYS
        invoice = Invoice(
            number=await next_number(self.session, DocumentKind.INVOICE),
            order_id=order_id,
            account_id=account_id,
            status="issued",
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=terms),
            total=total,
            amount_paid=Decimal("0"),
            owner_id=owner_id,
            team_id=team_id,
        )
        self.session.add(invoice)
        await self.session.flush()
        await audit.record(
            self.session,
            actor,
            "create",
            self.entity_type,
            invoice.id,
            {"number": [None, invoice.number], "total": [None, str(total)]},
        )
        return invoice

    async def record_payment(self, actor: Actor, id: uuid.UUID, data: PaymentCreate) -> Invoice:
        invoice = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        if invoice.status not in OPEN_STATUSES:
            raise Conflict(f"Cannot record a payment on a {invoice.status} invoice.")
        new_paid = invoice.amount_paid + data.amount
        if new_paid > invoice.total:
            raise ValidationFailed(
                "Payment exceeds the outstanding balance.",
                {"outstanding": str(invoice.total - invoice.amount_paid)},
            )
        new_status = "paid" if new_paid == invoice.total else "partially_paid"
        return await self._apply_update(
            actor,
            invoice,
            {"amount_paid": new_paid, "status": new_status},
        )

    async def void(self, actor: Actor, id: uuid.UUID) -> Invoice:
        invoice = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        if invoice.status != "issued" or invoice.amount_paid != 0:
            raise Conflict(
                "Only an unpaid issued invoice can be voided.", {"status": invoice.status}
            )
        return await self._apply_update(actor, invoice, {"status": "void"})
