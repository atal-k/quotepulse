import re
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.modules.accounts.models import Account
from app.modules.activities.models import Activity
from app.modules.contacts.models import Contact
from app.modules.identity.models import Team, User
from app.modules.invoices.models import Invoice
from app.modules.leads.models import Lead
from app.modules.opportunities.models import Opportunity
from app.modules.orders.models import Order
from app.modules.products.models import Product
from app.modules.quotations.models import Quotation
from app.modules.quotations.totals import LineInput, calculate_totals
from app.scripts.demo import builder as demo
from app.scripts.demo.builder import SeedOwners, build_dataset
from app.scripts.demo.gstin import checksum, gstin
from app.scripts.demo.loader import ENTITY_TYPES, already_loaded, load

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
VALID_STATE_CODES = {"03", "06", "19", "23", "24", "27", "29", "33", "36"}


def _owners() -> SeedOwners:
    # Ids need not exist in the DB here: the builder is pure and nothing is written.
    return SeedOwners(rep=uuid4(), manager=uuid4(), team_id=uuid4())


def _dataset():
    return build_dataset(_owners())


def _by_id(objects: list, cls: type, id_: UUID):
    return next(o for o in objects if isinstance(o, cls) and o.id == id_)


def test_gstin_checksum_matches_the_official_example() -> None:
    assert checksum("27AAPFU0939F1Z") == "V"


def test_generated_gstins_are_format_valid_with_correct_checksum() -> None:
    import random

    rng = random.Random(1)
    for code in VALID_STATE_CODES:
        number = gstin(rng, code)
        assert GSTIN_PATTERN.match(number), number
        assert number[:2] == code
        assert checksum(number[:14]) == number[14]


def test_dataset_is_deterministic_for_the_same_owners() -> None:
    owners = _owners()

    def fingerprint(ds):
        return [
            (
                type(o).__name__,
                str(o.id),
                getattr(o, "sku", None),
                getattr(o, "number", None),
                getattr(o, "tax_id", None),
                getattr(o, "body", None),
            )
            for o in ds.objects
        ]

    assert fingerprint(build_dataset(owners)) == fingerprint(build_dataset(owners))


def test_volumes_match_the_roadmap_ranges() -> None:
    counts = Counter(type(o) for o in _dataset().objects)

    assert 70 <= counts[Product] <= 80
    assert 20 <= counts[Account] <= 24
    assert 40 <= counts[Contact] <= 60
    assert 60 <= counts[Lead] <= 80
    assert 25 <= counts[Opportunity] <= 30
    assert 12 <= counts[Quotation] <= 15
    assert 8 <= counts[Order] <= 10
    assert 6 <= counts[Invoice] <= 8
    assert 180 <= counts[Activity] <= 230


def test_indian_fields_are_valid() -> None:
    dataset = _dataset()
    accounts = [o for o in dataset.objects if isinstance(o, Account)]

    for account in accounts:
        assert GSTIN_PATTERN.match(account.tax_id), account.tax_id
        assert account.tax_id[:2] in VALID_STATE_CODES
    for product in (o for o in dataset.objects if isinstance(o, Product)):
        assert product.tax_pct in (Decimal("5"), Decimal("18")), product.sku


def test_stock_never_goes_negative_or_below_reservations() -> None:
    for product in (o for o in _dataset().objects if isinstance(o, Product)):
        assert product.stock_qty >= 0
        assert 0 <= product.reserved_qty <= product.stock_qty, product.sku


def test_quotation_totals_reconcile_with_their_lines() -> None:
    for quotation in (o for o in _dataset().objects if isinstance(o, Quotation)):
        recomputed = calculate_totals(
            [LineInput(i.qty, i.unit_price, i.discount_pct, i.tax_pct) for i in quotation.items]
        )
        assert quotation.total == recomputed.total, quotation.number
        assert quotation.subtotal + quotation.tax_total == quotation.total


def test_planted_stalled_deal_has_no_activity_for_seven_days() -> None:
    dataset = _dataset()
    last = max(
        a.occurred_at
        for a in dataset.objects
        if isinstance(a, Activity) and a.entity_id == demo.HERO_OPP_STALLED
    )
    assert demo.AS_OF - last.date() >= timedelta(days=7)


def test_planted_free_text_rfq_is_below_stock_for_the_6204_bearing() -> None:
    dataset = _dataset()
    rfq = _by_id(dataset.objects, Activity, demo._hero(demo.HERO_ACTIVITY_BASE + 4))
    bearing = _by_id(dataset.objects, Product, demo.HERO_PRODUCT_BEARING_2RS)

    assert rfq.body == "Need 500 pcs 6mm SS bolts + 200 bearings 6204, delivery in 10 days"
    assert bearing.name.endswith("2RS") and "6204" in bearing.name
    assert bearing.stock_qty == Decimal("150") < 200


def test_planted_duplicate_lead_is_fuzzy_not_exact() -> None:
    dataset = _dataset()
    original = _by_id(dataset.objects, Lead, demo.HERO_LEAD_ORIGINAL)
    duplicate = _by_id(dataset.objects, Lead, demo.HERO_LEAD_DUPLICATE)

    assert original.phone == duplicate.phone == "+919876543210"
    assert original.email != duplicate.email
    assert original.email.split("@")[1] != duplicate.email.split("@")[1]
    assert original.name != duplicate.name


def test_planted_overdue_invoice_is_past_due() -> None:
    invoice = _by_id(_dataset().objects, Invoice, demo.HERO_INVOICE_OVERDUE)

    assert invoice.status == "issued"
    assert invoice.due_date < demo.AS_OF
    assert invoice.amount_paid == 0


def test_planted_out_of_policy_quote_needs_an_admin() -> None:
    quote = _by_id(_dataset().objects, Quotation, demo.HERO_QUOTE_OUT_OF_POLICY)

    assert quote.status == "pending_approval"
    assert quote.max_discount_pct == Decimal("20")
    assert quote.approver_role == Role.ADMIN


async def test_loading_writes_every_aggregate_and_is_idempotent(
    session: AsyncSession, make_user: Callable[..., Awaitable[User]], team: Team
) -> None:
    rep = await make_user("rep")
    manager = await make_user("manager")
    dataset = build_dataset(SeedOwners(rep=rep.id, manager=manager.id, team_id=team.id))
    assert not await already_loaded(session)

    written = await load(session, dataset)

    assert written == sum(type(o) in ENTITY_TYPES for o in dataset.objects)
    assert await already_loaded(session)
    stored = (await session.execute(select(func.count()).select_from(Product))).scalar_one()
    assert stored == sum(isinstance(o, Product) for o in dataset.objects)
    numbers = (await session.execute(select(Quotation.number))).scalars().all()
    assert len(numbers) == len(set(numbers))
    hero = (
        await session.execute(select(Account).where(Account.id == demo.HERO_ACCOUNT_PUMPS))
    ).scalar_one()
    assert hero.name == "Vel Murugan Pumps Pvt Ltd"
