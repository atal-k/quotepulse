import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core import audit
from app.core.errors import Conflict
from app.core.rbac import Action, Actor
from app.modules.accounts.service import AccountService
from app.modules.base import CrudService
from app.modules.document_sequences.service import DocumentKind, next_number
from app.modules.invoices.service import InvoiceService
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import OrderUpdate
from app.modules.products.stock import StockLine, consume, release, reserve

ORDER_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def check_transition(current: str, target: str) -> None:
    if target not in ORDER_TRANSITIONS[current]:
        raise Conflict(
            f"Order cannot move from '{current}' to '{target}'.",
            {"from": current, "to": target, "allowed": sorted(ORDER_TRANSITIONS[current])},
        )


@dataclass(frozen=True)
class OrderItemDraft:
    position: int
    product_id: uuid.UUID
    description: str
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    tax_pct: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class OrderDraft:
    """Everything an order needs, already priced by the accepted quotation."""

    quotation_id: uuid.UUID
    account_id: uuid.UUID
    owner_id: uuid.UUID
    team_id: uuid.UUID | None
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: tuple[OrderItemDraft, ...]


def _stock_lines(order: Order) -> list[StockLine]:
    return [StockLine(product_id=item.product_id, qty=item.qty) for item in order.items]


class OrderService(CrudService[Order, OrderUpdate, OrderUpdate]):
    """Orders are created only by accepting a quotation (`create_order`); the generic create path
    is not exposed."""

    model = Order
    resource = "orders"
    entity_type = "order"

    async def create_order(self, actor: Actor, draft: OrderDraft) -> Order:
        await reserve(
            self.session,
            actor,
            [StockLine(product_id=item.product_id, qty=item.qty) for item in draft.items],
        )
        order = Order(
            number=await next_number(self.session, DocumentKind.ORDER),
            quotation_id=draft.quotation_id,
            account_id=draft.account_id,
            status="confirmed",
            subtotal=draft.subtotal,
            discount_total=draft.discount_total,
            tax_total=draft.tax_total,
            total=draft.total,
            owner_id=draft.owner_id,
            team_id=draft.team_id,
            items=[
                OrderItem(
                    position=item.position,
                    product_id=item.product_id,
                    description=item.description,
                    qty=item.qty,
                    unit_price=item.unit_price,
                    discount_pct=item.discount_pct,
                    tax_pct=item.tax_pct,
                    line_total=item.line_total,
                )
                for item in draft.items
            ],
        )
        self.session.add(order)
        await self.session.flush()
        await audit.record(
            self.session,
            actor,
            "create",
            self.entity_type,
            order.id,
            {"number": [None, order.number], "total": [None, str(order.total)]},
        )
        return order

    async def process(self, actor: Actor, id: uuid.UUID) -> Order:
        order = await self._writable(actor, id)
        await self._move(actor, order, "processing")
        return order

    async def ship(self, actor: Actor, id: uuid.UUID) -> Order:
        """Goods leave the warehouse: stock and reservation drop together, and the invoice is
        issued in the same transaction."""
        order = await self._writable(actor, id)
        await self._move(actor, order, "shipped")
        await consume(self.session, actor, _stock_lines(order))
        account = await AccountService(self.session).get(actor, order.account_id)
        await InvoiceService(self.session).create_for_order(
            actor,
            order_id=order.id,
            account_id=order.account_id,
            owner_id=order.owner_id,
            team_id=order.team_id,
            total=order.total,
            payment_terms_days=account.payment_terms_days,
        )
        return order

    async def deliver(self, actor: Actor, id: uuid.UUID) -> Order:
        order = await self._writable(actor, id)
        await self._move(actor, order, "delivered")
        return order

    async def cancel(self, actor: Actor, id: uuid.UUID) -> Order:
        order = await self._writable(actor, id)
        await self._move(actor, order, "cancelled")
        await release(self.session, actor, _stock_lines(order))
        return order

    async def _writable(self, actor: Actor, id: uuid.UUID) -> Order:
        order = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        return order

    async def _move(self, actor: Actor, order: Order, target: str) -> None:
        check_transition(order.status, target)
        old = order.status
        order.status = target
        await self.session.flush()
        await audit.record(
            self.session, actor, "update", self.entity_type, order.id, {"status": [old, target]}
        )
