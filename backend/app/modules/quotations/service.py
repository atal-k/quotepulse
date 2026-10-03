import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core import audit
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.core.rbac import Action, Actor
from app.modules.accounts.service import AccountService
from app.modules.base import CrudService
from app.modules.document_sequences.service import DocumentKind, next_number
from app.modules.opportunities.service import OpportunityService
from app.modules.orders.service import OrderDraft, OrderItemDraft, OrderService
from app.modules.products.models import Product
from app.modules.quotations.models import Quotation, QuotationItem
from app.modules.quotations.policy import can_approve
from app.modules.quotations.schemas import QuotationCreate, QuotationUpdate
from app.modules.quotations.totals import LineInput, Totals, calculate_totals

TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_approval", "approved"},
    "pending_approval": {"approved", "draft"},
    "approved": {"sent", "superseded", "expired"},
    "sent": {"accepted", "rejected", "expired", "superseded"},
    "accepted": set(),
    "rejected": set(),
    "expired": set(),
    "superseded": set(),
}


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS[current]:
        raise Conflict(
            f"Quotation cannot move from '{current}' to '{target}'.",
            {"from": current, "to": target, "allowed": sorted(TRANSITIONS[current])},
        )


@dataclass(frozen=True)
class LineRequest:
    product_id: uuid.UUID
    qty: Decimal
    discount_pct: Decimal


def _today() -> date:
    return datetime.now(UTC).date()


def _check_valid_until(valid_until: date | None) -> None:
    if valid_until is not None and valid_until < _today():
        raise ValidationFailed("valid_until cannot be in the past.", {"field": "valid_until"})


def _apply_totals(quotation: Quotation, totals: Totals) -> None:
    quotation.subtotal = totals.subtotal
    quotation.discount_total = totals.discount_total
    quotation.tax_total = totals.tax_total
    quotation.total = totals.total


class QuotationService(CrudService[Quotation, QuotationCreate, QuotationUpdate]):
    model = Quotation
    resource = "quotations"
    entity_type = "quotation"

    async def create(self, actor: Actor, data: QuotationCreate) -> Quotation:
        self._require(actor, Action.CREATE)
        account = await AccountService(self.session).get(actor, data.account_id)
        if data.opportunity_id is not None:
            opportunity = await OpportunityService(self.session).get(actor, data.opportunity_id)
            if opportunity.account_id != account.id:
                raise ValidationFailed(
                    "Opportunity does not belong to this account.", {"field": "opportunity_id"}
                )
        _check_valid_until(data.valid_until)
        items, totals = await self._price(
            [LineRequest(i.product_id, i.qty, i.discount_pct) for i in data.items]
        )
        quotation = Quotation(
            number=await next_number(self.session, DocumentKind.QUOTATION),
            version=1,
            status="draft",
            account_id=account.id,
            opportunity_id=data.opportunity_id,
            valid_until=data.valid_until,
            terms=data.terms,
            created_by_kind=actor.kind.value,
            owner_id=account.owner_id,
            team_id=account.team_id,
            items=items,
        )
        _apply_totals(quotation, totals)
        self.session.add(quotation)
        await self.session.flush()
        await audit.record(
            self.session,
            actor,
            "create",
            self.entity_type,
            quotation.id,
            {"number": [None, quotation.number], "total": [None, str(totals.total)]},
        )
        return quotation

    async def update(self, actor: Actor, id: uuid.UUID, data: QuotationUpdate) -> Quotation:
        quotation = await self._writable(actor, id)
        if quotation.status != "draft":
            raise Conflict(
                "Only draft quotations can be edited. Revise an approved or sent quotation.",
                {"status": quotation.status},
            )
        payload = data.model_dump(exclude_unset=True)
        if "items" in payload and data.items is None:
            raise ValidationFailed("items cannot be null.", {"field": "items"})
        if "valid_until" in payload:
            _check_valid_until(data.valid_until)
        changes: dict[str, list[str | None]] = {}
        if "valid_until" in payload and quotation.valid_until != data.valid_until:
            changes["valid_until"] = [_str(quotation.valid_until), _str(data.valid_until)]
            quotation.valid_until = data.valid_until
        if "terms" in payload and quotation.terms != data.terms:
            changes["terms"] = [quotation.terms, data.terms]
            quotation.terms = data.terms
        if data.items is not None:
            old_total = str(quotation.total)
            items, totals = await self._price(
                [LineRequest(i.product_id, i.qty, i.discount_pct) for i in data.items]
            )
            quotation.items = items
            _apply_totals(quotation, totals)
            changes["items"] = ["replaced", str(len(items))]
            changes["total"] = [old_total, str(totals.total)]
        await self.session.flush()
        if changes:
            await audit.record(
                self.session, actor, "update", self.entity_type, quotation.id, changes
            )
        return quotation

    async def submit(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        target = "approved" if quotation.approver_role is None else "pending_approval"
        await self._move(actor, quotation, target)
        return quotation

    async def approve(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        self._check_approver(actor, quotation)
        await self._move(actor, quotation, "approved")
        return quotation

    async def return_for_edit(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        self._check_approver(actor, quotation)
        await self._move(actor, quotation, "draft")
        return quotation

    async def send(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        await self._move(actor, quotation, "sent")
        return quotation

    async def decline(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        await self._move(actor, quotation, "rejected")
        return quotation

    async def expire(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self._writable(actor, id)
        if quotation.valid_until is None or quotation.valid_until >= _today():
            raise Conflict("Quotation is still within its validity period.")
        await self._move(actor, quotation, "expired")
        return quotation

    async def accept(self, actor: Actor, id: uuid.UUID) -> Quotation:
        """Customer accepts: the order is created (reserving stock, all-or-nothing with this
        transaction) and the linked opportunity is won."""
        quotation = await self._writable(actor, id)
        if quotation.valid_until is not None and quotation.valid_until < _today():
            raise Conflict(
                "This quotation has expired.", {"valid_until": str(quotation.valid_until)}
            )
        # Order first: a stock shortage raises before the quotation changes state.
        await OrderService(self.session).create_order(actor, _order_draft(quotation))
        await self._move(actor, quotation, "accepted")
        if quotation.opportunity_id is not None:
            opportunities = OpportunityService(self.session)
            opportunity = await opportunities.get(actor, quotation.opportunity_id)
            if opportunity.stage != "won":
                await opportunities.mark_won(actor, opportunity.id)
        return quotation

    async def revise(self, actor: Actor, id: uuid.UUID) -> Quotation:
        """Change an approved or sent quotation: the current one is superseded and a new draft
        version (same number, next version) is created from the catalog's current prices."""
        quotation = await self._writable(actor, id)
        await self._move(actor, quotation, "superseded")
        items, totals = await self._price(
            [LineRequest(i.product_id, i.qty, i.discount_pct) for i in quotation.items]
        )
        revision = Quotation(
            number=quotation.number,
            version=quotation.version + 1,
            status="draft",
            account_id=quotation.account_id,
            opportunity_id=quotation.opportunity_id,
            valid_until=quotation.valid_until,
            terms=quotation.terms,
            created_by_kind=actor.kind.value,
            owner_id=quotation.owner_id,
            team_id=quotation.team_id,
            items=items,
        )
        _apply_totals(revision, totals)
        self.session.add(revision)
        await self.session.flush()
        await audit.record(
            self.session,
            actor,
            "create",
            self.entity_type,
            revision.id,
            {"number": [None, revision.number], "version": [None, revision.version]},
        )
        return revision

    async def _writable(self, actor: Actor, id: uuid.UUID) -> Quotation:
        quotation = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        return quotation

    async def _move(self, actor: Actor, quotation: Quotation, target: str) -> None:
        check_transition(quotation.status, target)
        old = quotation.status
        quotation.status = target
        await self.session.flush()
        await audit.record(
            self.session, actor, "update", self.entity_type, quotation.id, {"status": [old, target]}
        )

    def _check_approver(self, actor: Actor, quotation: Quotation) -> None:
        required = quotation.approver_role
        if not can_approve(actor.role, required):
            raise PermissionDenied(
                f"A {quotation.max_discount_pct}% discount needs {required.value} approval."
            )

    async def _price(self, lines: list[LineRequest]) -> tuple[list[QuotationItem], Totals]:
        """Catalog prices and tax, server-side. Every amount comes out of calculate_totals."""
        products = await self._active_products([line.product_id for line in lines])
        inputs = [
            LineInput(
                qty=line.qty,
                unit_price=products[line.product_id].unit_price,
                discount_pct=line.discount_pct,
                tax_pct=products[line.product_id].tax_pct,
            )
            for line in lines
        ]
        totals = calculate_totals(inputs)
        items = [
            QuotationItem(
                position=position,
                product_id=line.product_id,
                description=products[line.product_id].name,
                qty=line.qty,
                unit_price=products[line.product_id].unit_price,
                discount_pct=line.discount_pct,
                tax_pct=products[line.product_id].tax_pct,
                line_total=amounts.line_total,
            )
            for position, (line, amounts) in enumerate(zip(lines, totals.lines, strict=True), 1)
        ]
        return items, totals

    async def _active_products(self, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, Product]:
        rows = (
            (await self.session.execute(select(Product).where(Product.id.in_(set(product_ids)))))
            .scalars()
            .all()
        )
        products = {p.id: p for p in rows}
        for product_id in product_ids:
            product = products.get(product_id)
            if product is None or not product.is_active:
                raise ValidationFailed(
                    "Unknown or inactive product.", {"product_id": str(product_id)}
                )
        return products


def _order_draft(quotation: Quotation) -> OrderDraft:
    return OrderDraft(
        quotation_id=quotation.id,
        account_id=quotation.account_id,
        owner_id=quotation.owner_id,
        team_id=quotation.team_id,
        subtotal=quotation.subtotal,
        discount_total=quotation.discount_total,
        tax_total=quotation.tax_total,
        total=quotation.total,
        items=tuple(
            OrderItemDraft(
                position=item.position,
                product_id=item.product_id,
                description=item.description,
                qty=item.qty,
                unit_price=item.unit_price,
                discount_pct=item.discount_pct,
                tax_pct=item.tax_pct,
                line_total=item.line_total,
            )
            for item in quotation.items
        ),
    )


def _str(value: date | None) -> str | None:
    return None if value is None else value.isoformat()
