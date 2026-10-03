"""Deterministic demo dataset (roadmap 1C). Pure: unsaved ORM objects only; the loader writes them.

NEVER CHANGE `SEED_CONSTANT`, `SEED_NAMESPACE`, `AS_OF`, the hero UUIDs, or the order of `rng`
calls. Any change regenerates every row, and the planted demo scenarios (referenced by fixed UUID
from the demo video and tests) stop matching.
"""

import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.base import Base
from app.core.normalize import normalize_email, normalize_phone
from app.modules.accounts.models import Account
from app.modules.activities.enums import ActivityType, EntityType
from app.modules.activities.models import Activity
from app.modules.contacts.models import Contact
from app.modules.invoices.models import Invoice
from app.modules.leads.models import Lead
from app.modules.opportunities.models import Opportunity
from app.modules.orders.models import Order, OrderItem
from app.modules.products.models import Product
from app.modules.quotations.models import Quotation, QuotationItem
from app.modules.quotations.totals import LineInput, calculate_totals
from app.scripts.demo import pools
from app.scripts.demo.gstin import gstin

FAMILIES = ("Fastener", "Bearing", "Abrasives & tools", "MRO")

SEED_CONSTANT = 20260930  # NEVER CHANGE: see module docstring.
SEED_NAMESPACE = uuid.UUID("6f1c2a7e-9b1d-4c3e-8a5f-0d2b7e9c4a10")  # NEVER CHANGE
AS_OF = date(2026, 9, 30)  # fixed "today" so the dataset does not drift with the clock
YEAR = AS_OF.year

FILLER_ACCOUNTS = 20
FILLER_CONTACTS_PER_ACCOUNT = (2, 3)
FILLER_LEADS = 65
FILLER_OPPORTUNITIES = 26
FILLER_PRODUCTS = 70
FILLER_ACCEPTED_QUOTES = 7
FILLER_NON_ACCEPTED_QUOTES = 4
FILLER_ACTIVITIES = 170
NARRATIVE_OPPORTUNITIES = 6


def _hero(n: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{n:012x}")


def _derived(kind: str, n: int) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{n}")


# Hero records. Fixed UUIDs, numbered once and never renumbered.
HERO_ACCOUNT_PUMPS = _hero(1)
HERO_ACCOUNT_AUTO = _hero(2)
HERO_CONTACT_PUMPS = _hero(3)
HERO_CONTACT_AUTO = _hero(4)
HERO_LEAD_ORIGINAL = _hero(5)
HERO_LEAD_DUPLICATE = _hero(6)
HERO_OPP_STALLED = _hero(7)
HERO_OPP_BOLTS = _hero(8)
HERO_PRODUCT_BOLT_SS304 = _hero(9)
HERO_PRODUCT_BOLT_SS316 = _hero(10)
HERO_PRODUCT_BEARING_2RS = _hero(11)
HERO_PRODUCT_BEARING_ZZ = _hero(12)
HERO_QUOTE_OUT_OF_POLICY = _hero(13)
HERO_QUOTE_FREE_TEXT = _hero(14)
HERO_QUOTE_ACCEPTED = _hero(15)
HERO_ORDER_SHIPPED = _hero(16)
HERO_INVOICE_OVERDUE = _hero(17)
HERO_ACTIVITY_BASE = 100  # hero activities are _hero(HERO_ACTIVITY_BASE + i)

HERO_BOLT_SS304_STOCK = Decimal("1000")
HERO_BEARING_2RS_STOCK = Decimal("150")  # below the 200 requested in the free-text RFQ
HERO_BEARING_ZZ_STOCK = Decimal("90")


@dataclass(frozen=True)
class SeedOwners:
    rep: uuid.UUID
    manager: uuid.UUID
    team_id: uuid.UUID


@dataclass
class Dataset:
    objects: list[Base]
    sequences: dict[str, int]


def _ts(days_ago: int, hour: int = 10, minute: int = 0) -> datetime:
    day = AS_OF - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


class _Builder:
    def __init__(self, owners: SeedOwners) -> None:
        self.owners = owners
        self.rng = random.Random(SEED_CONSTANT)
        self.objects: list[Base] = []
        self.sequences = {"QT": 0, "SO": 0, "INV": 0}
        self.products: list[Product] = []
        self.accounts: list[Account] = []
        self.contacts: dict[uuid.UUID, list[Contact]] = {}
        self.won_opportunities: list[Opportunity] = []
        self.orders: list[Order] = []
        self.invoices: list[Invoice] = []
        self.quotations: list[Quotation] = []
        self.filler_orders: list[tuple[Quotation, Account]] = []

    # ---- helpers -------------------------------------------------------------------------

    def _owner(self) -> uuid.UUID:
        return self.owners.rep if self.rng.random() < 0.8 else self.owners.manager

    def _number(self, kind: str) -> str:
        self.sequences[kind] += 1
        return f"{kind}-{YEAR}-{self.sequences[kind]:05d}"

    def _add(self, obj: Base) -> Base:
        self.objects.append(obj)
        return obj

    def _mobile(self) -> str:
        digits = "9" + "".join(self.rng.choice("0123456789") for _ in range(9))
        return f"+91 {digits[:5]} {digits[5:]}"

    # ---- catalog -------------------------------------------------------------------------

    def build_products(self) -> None:
        self._hero_products()
        candidates = self._filler_product_specs()
        for spec in candidates:
            self._add_product(spec)

    def _hero_products(self) -> None:
        heroes = [
            (
                HERO_PRODUCT_BOLT_SS304,
                "HB-M6X20-SS304",
                "Hex Bolt M6x20 SS304",
                "pcs",
                "8.50",
                "18",
                3,
                100,
            ),
            (
                HERO_PRODUCT_BOLT_SS316,
                "HB-M6X20-SS316",
                "Hex Bolt M6x20 SS316",
                "pcs",
                "11.20",
                "18",
                3,
                100,
            ),
            (
                HERO_PRODUCT_BEARING_2RS,
                "BRG-6204-2RS",
                "Deep Groove Ball Bearing 6204 2RS",
                "pcs",
                "385.00",
                "18",
                7,
                1,
            ),
            (
                HERO_PRODUCT_BEARING_ZZ,
                "BRG-6204-ZZ",
                "Deep Groove Ball Bearing 6204 ZZ",
                "pcs",
                "365.00",
                "18",
                7,
                1,
            ),
        ]
        for pid, sku, name, unit, price, tax, lead_days, moq in heroes:
            self.products.append(
                self._add(
                    Product(
                        id=pid,
                        sku=sku,
                        name=name,
                        category="bolts" if "Bolt" in name else "bearings",
                        unit=unit,
                        unit_price=Decimal(price),
                        currency="INR",
                        tax_pct=Decimal(tax),
                        stock_qty=Decimal("0"),
                        reserved_qty=Decimal("0"),
                        reorder_level=Decimal("50"),
                        min_order_qty=Decimal(moq),
                        lead_time_days=lead_days,
                        is_active=True,
                        created_at=_ts(200),
                        updated_at=_ts(200),
                    )
                )
            )

    def _filler_product_specs(self) -> list[dict]:
        """Near-duplicate variants (size, material, sealing) are deliberate: they are what the
        semantic-matching work in Phase 2 has to tell apart."""
        sizes = {"4": "3.50", "5": "5.00", "6": "7.00", "8": "11.00", "10": "18.00", "12": "26.00"}
        lengths = ("16", "20", "25", "30", "40")
        materials = {"SS304": 1.00, "SS316": 1.30, "MS": 0.60}
        hero_sizes = {("6", "20", "SS304"), ("6", "20", "SS316")}
        bolt_combos = [
            (size, length, mat)
            for size in sizes
            for length in lengths
            for mat in materials
            if (size, length, mat) not in hero_sizes
        ]
        specs: list[dict] = []
        for size, length, mat in self.rng.sample(bolt_combos, 20):
            factor = 1 + (int(length) - 16) / 100
            price = Decimal(sizes[size]) * Decimal(str(factor)) * Decimal(str(materials[mat]))
            specs.append(
                _spec(
                    f"HB-M{size}X{length}-{mat}",
                    f"Hex Bolt M{size}x{length} {mat}",
                    "bolts",
                    "pcs",
                    _money(price),
                    "18",
                    3,
                    100,
                )
            )
        for size in sizes:
            for mat in ("SS304", "MS"):
                price = Decimal(sizes[size]) * Decimal("0.40") * Decimal(str(materials[mat]))
                specs.append(
                    _spec(
                        f"HN-M{size}-{mat}",
                        f"Hex Nut M{size} {mat}",
                        "nuts",
                        "pcs",
                        _money(price),
                        "18",
                        3,
                        100,
                    )
                )
        for size in ("6", "8", "10", "12"):
            specs.append(
                _spec(
                    f"WS-M{size}-SS304",
                    f"Plain Washer M{size} SS304",
                    "nuts",
                    "pcs",
                    _money(Decimal(sizes[size]) * Decimal("0.15")),
                    "18",
                    3,
                    100,
                )
            )
        for number, base in (
            ("6201", "220"),
            ("6202", "260"),
            ("6203", "290"),
            ("6204", "330"),
            ("6205", "340"),
            ("6206", "400"),
            ("6305", "520"),
            ("6306", "610"),
            ("6307", "700"),
        ):
            for variant, factor in (("2RS", "1.00"), ("ZZ", "0.95"), ("Open", "0.90")):
                if number == "6204" and variant in ("2RS", "ZZ"):
                    continue  # hero bearings
                price = Decimal(base) * Decimal(factor)
                specs.append(
                    _spec(
                        f"BRG-{number}-{variant.upper()}",
                        f"Deep Groove Ball Bearing {number} {variant}",
                        "bearings",
                        "pcs",
                        _money(price),
                        "18",
                        7,
                        1,
                    )
                )
        bearing_specs = [s for s in specs if s["category"] == "bearings"]
        specs = [s for s in specs if s["category"] != "bearings"] + self.rng.sample(
            bearing_specs, 12
        )
        for name, price in (
            ("Cutting disc 4 inch", "24.00"),
            ("Cutting disc 5 inch", "32.00"),
            ("Cutting disc 7 inch", "48.00"),
            ("Flap disc 4 inch", "78.00"),
            ("Flap disc 7 inch", "120.00"),
            ("Grinding wheel 6 inch", "165.00"),
            ("Wire brush cup 4 inch", "210.00"),
            ("Sanding disc 5 inch", "36.00"),
        ):
            specs.append(
                _spec(
                    f"AB-{name.upper().replace(' ', '-')}",
                    name,
                    "abrasives",
                    "pcs",
                    Decimal(price),
                    "18",
                    2,
                    10,
                )
            )
        for name, price in (
            ("MCB 6A single pole", "185.00"),
            ("MCB 16A single pole", "210.00"),
            ("MCB 32A single pole", "260.00"),
            ("MCB 32A double pole", "640.00"),
            ("Changeover switch 32A", "890.00"),
            ("Cable 2.5 sq mm Flexible 90m", "2450.00"),
        ):
            specs.append(
                _spec(
                    f"EL-{name.upper().replace(' ', '-')}",
                    name,
                    "electrical",
                    "pcs",
                    Decimal(price),
                    "18",
                    5,
                    1,
                )
            )
        for name, price in (
            ("Combination spanner set 6 pc", "850.00"),
            ("Allen key set 9 pc", "260.00"),
            ("Hacksaw blade 12 inch", "45.00"),
            ("Torque wrench 1/2 inch drive", "4200.00"),
        ):
            specs.append(
                _spec(
                    f"TL-{name.upper().replace(' ', '-').replace('/', '')}",
                    name,
                    "tools",
                    "pcs",
                    Decimal(price),
                    "18",
                    4,
                    1,
                )
            )
        for name, unit, price, tax in (
            ("Cotton waste 1 kg", "kg", "120.00", "5"),
            ("Packing tape 48mm roll", "roll", "65.00", "5"),
            ("PVC insulation tape 10m", "roll", "35.00", "5"),
            ("Emery paper roll 50m", "roll", "540.00", "5"),
        ):
            specs.append(
                _spec(
                    f"CN-{name.upper().replace(' ', '-')}",
                    name,
                    "consumables",
                    unit,
                    Decimal(price),
                    tax,
                    1,
                    1,
                )
            )
        return specs

    def _add_product(self, spec: dict) -> None:
        product = Product(
            id=_derived("product", len(self.products)),
            sku=spec["sku"],
            name=spec["name"],
            category=spec["category"],
            unit=spec["unit"],
            unit_price=spec["price"],
            currency="INR",
            tax_pct=Decimal(spec["tax"]),
            stock_qty=Decimal("0"),
            reserved_qty=Decimal("0"),
            reorder_level=Decimal("50"),
            min_order_qty=Decimal(spec["moq"]),
            lead_time_days=spec["lead"],
            is_active=spec["name"] != "Wire brush cup 4 inch",
            created_at=_ts(200),
            updated_at=_ts(200),
        )
        self.products.append(self._add(product))

    # ---- accounts and contacts -----------------------------------------------------------

    def build_accounts(self) -> None:
        self._hero_accounts()
        combos = [f"{p} {s}" for p in pools.COMPANY_PREFIXES for s in pools.COMPANY_SUFFIXES]
        for name in self.rng.sample(combos, FILLER_ACCOUNTS):
            city, state, code = self.rng.choice(pools.CITIES)
            slug = name.lower().replace(" ", "")
            status = self.rng.choices(["customer", "prospect", "inactive"], [16, 3, 1])[0]
            account = self._add(
                Account(
                    id=_derived("account", len(self.accounts)),
                    name=name,
                    domain=f"{slug}.{self.rng.choice(['in', 'co.in'])}",
                    industry=self.rng.choice(
                        ["Fasteners", "Bearings", "Pumps", "Automotive", "Castings"]
                    ),
                    tax_id=gstin(self.rng, code),
                    city=city,
                    state=state,
                    country="India",
                    status=status,
                    credit_limit=Decimal(self.rng.randrange(100000, 1000001, 50000)),
                    payment_terms_days=self.rng.choice([15, 30, 30, 45, 60]),
                    owner_id=self._owner(),
                    team_id=self.owners.team_id,
                    created_at=_ts(self.rng.randint(120, 400)),
                    updated_at=_ts(10),
                )
            )
            self.accounts.append(account)
        for account in self.accounts[2:]:
            self._filler_contacts(account)

    def _hero_accounts(self) -> None:
        pumps = self._add(
            Account(
                id=HERO_ACCOUNT_PUMPS,
                name="Vel Murugan Pumps Pvt Ltd",
                domain="velmurugan-pumps.in",
                industry="Pumps",
                tax_id=gstin(self.rng, "33"),
                city="Coimbatore",
                state="Tamil Nadu",
                country="India",
                status="customer",
                credit_limit=Decimal("500000"),
                payment_terms_days=30,
                owner_id=self.owners.rep,
                team_id=self.owners.team_id,
                created_at=_ts(300),
                updated_at=_ts(5),
            )
        )
        auto = self._add(
            Account(
                id=HERO_ACCOUNT_AUTO,
                name="Sahyadri Auto Components LLP",
                domain="sahyadri-auto.co.in",
                industry="Automotive",
                tax_id=gstin(self.rng, "27"),
                city="Pune",
                state="Maharashtra",
                country="India",
                status="customer",
                credit_limit=Decimal("300000"),
                payment_terms_days=45,
                owner_id=self.owners.rep,
                team_id=self.owners.team_id,
                created_at=_ts(280),
                updated_at=_ts(2),
            )
        )
        self.accounts[:0] = [pumps, auto]
        for account, contact_id, first, last, title, email, phone in (
            (
                pumps,
                HERO_CONTACT_PUMPS,
                "Karthik",
                "Subramanian",
                "Purchasing Manager",
                "karthik.subramanian@velmurugan-pumps.in",
                "+91 98432 12345",
            ),
            (
                auto,
                HERO_CONTACT_AUTO,
                "Meghana",
                "Joshi",
                "Plant Head",
                "meghana.joshi@sahyadri-auto.co.in",
                "9822012345",
            ),
        ):
            self.contacts[account.id] = [
                self._add(
                    Contact(
                        id=contact_id,
                        account_id=account.id,
                        first_name=first,
                        last_name=last,
                        email=normalize_email(email),
                        phone=normalize_phone(phone),
                        job_title=title,
                        is_primary=True,
                        owner_id=account.owner_id,
                        team_id=account.team_id,
                        created_at=_ts(250),
                        updated_at=_ts(20),
                    )
                )
            ]

    def _filler_contacts(self, account: Account) -> None:
        contacts: list[Contact] = []
        for index in range(self.rng.randint(*FILLER_CONTACTS_PER_ACCOUNT)):
            first, last = self.rng.choice(pools.FIRST_NAMES), self.rng.choice(pools.LAST_NAMES)
            contacts.append(
                self._add(
                    Contact(
                        id=_derived("contact", len(self.objects)),
                        account_id=account.id,
                        first_name=first,
                        last_name=last,
                        email=normalize_email(f"{first}.{last}@{account.domain}"),
                        phone=normalize_phone(self._mobile()),
                        job_title=self.rng.choice(pools.JOB_TITLES),
                        is_primary=index == 0,
                        owner_id=account.owner_id,
                        team_id=account.team_id,
                        created_at=account.created_at + timedelta(days=5),
                        updated_at=account.created_at + timedelta(days=5),
                    )
                )
            )
        self.contacts[account.id] = contacts

    # ---- leads ----------------------------------------------------------------------------

    def build_leads(self) -> None:
        self._hero_leads()
        used = {a.name for a in self.accounts}
        companies = [
            f"{p} {s}"
            for p in pools.COMPANY_PREFIXES
            for s in pools.COMPANY_SUFFIXES
            if f"{p} {s}" not in used
        ]
        for name in self.rng.sample(companies, FILLER_LEADS):
            first, last = self.rng.choice(pools.FIRST_NAMES), self.rng.choice(pools.LAST_NAMES)
            slug = name.lower().replace(" ", "")
            free_mail = self.rng.random() < 0.3
            email = (
                f"{first.lower()}{self.rng.randint(1, 99)}@gmail.com"
                if free_mail
                else f"{first.lower()}.{last.lower()}@{slug}.in"
            )
            status = self.rng.choices(
                ["new", "contacted", "qualified", "disqualified"], [25, 20, 12, 8]
            )[0]
            self._add(
                Lead(
                    id=_derived("lead", len(self.objects)),
                    name=f"{first} {last}",
                    company_name=name,
                    email=normalize_email(email),
                    phone=normalize_phone(self._mobile()),
                    source=self.rng.choice(pools.LEAD_SOURCES),
                    status=status,
                    score=None if status == "new" else self.rng.randint(20, 90),
                    qualification=(
                        {
                            "budget": "INR 2-5 lakh",
                            "authority": "Purchasing Manager",
                            "need": "Monthly fastener & bearing supply",
                            "timeline": "Q4",
                        }
                        if status == "qualified"
                        else None
                    ),
                    owner_id=self._owner(),
                    team_id=self.owners.team_id,
                    created_at=_ts(self.rng.randint(1, 120)),
                    updated_at=_ts(self.rng.randint(0, 20)),
                )
            )

    def _hero_leads(self) -> None:
        self._add(
            Lead(
                id=HERO_LEAD_ORIGINAL,
                name="Suresh Iyer",
                company_name="Iyer Forgings",
                email="suresh.iyer@iyerforgings.in",
                phone=normalize_phone("+91 98765 43210"),
                source="referral",
                status="contacted",
                score=60,
                qualification=None,
                owner_id=self.owners.rep,
                team_id=self.owners.team_id,
                created_at=_ts(20),
                updated_at=_ts(3),
            )
        )
        # Same person, different email domain, differently formatted phone: fuzzy-matchable.
        self._add(
            Lead(
                id=HERO_LEAD_DUPLICATE,
                name="Suresh R. Iyer",
                company_name="Iyer Forgings Pvt Ltd",
                email="suresh@iyer-forgings.co.in",
                phone=normalize_phone("+91 90031 45872"),
                source="website",
                status="new",
                score=None,
                qualification=None,
                owner_id=self.owners.manager,
                team_id=self.owners.team_id,
                created_at=_ts(4),
                updated_at=_ts(4),
            )
        )

    # ---- opportunities, quotations, orders, invoices -------------------------------------

    def build_sales(self) -> None:
        self._hero_sales()
        self._filler_sales()

    def _hero_sales(self) -> None:
        pumps, auto = self.accounts[0], self.accounts[1]
        self._add(
            Opportunity(
                id=HERO_OPP_STALLED,
                account_id=pumps.id,
                contact_id=HERO_CONTACT_PUMPS,
                name="Pump impeller bearing refit",
                stage="proposal",
                amount=Decimal("450000"),
                currency="INR",
                probability=40,
                expected_close_date=AS_OF + timedelta(days=30),
                requirements="Bearings and fasteners for 3 pump lines",
                lost_reason=None,
                closed_at=None,
                owner_id=pumps.owner_id,
                team_id=pumps.team_id,
                created_at=_ts(60),
                updated_at=_ts(25),
            )
        )
        self._add(
            Opportunity(
                id=HERO_OPP_BOLTS,
                account_id=auto.id,
                contact_id=HERO_CONTACT_AUTO,
                name="Bolts & bearings Q4 supply",
                stage="negotiation",
                amount=Decimal("260000"),
                currency="INR",
                probability=70,
                expected_close_date=AS_OF + timedelta(days=21),
                requirements="SS bolts and 6204 bearings, monthly call-offs",
                lost_reason=None,
                closed_at=None,
                owner_id=auto.owner_id,
                team_id=auto.team_id,
                created_at=_ts(35),
                updated_at=_ts(2),
            )
        )
        self._quote(
            HERO_QUOTE_OUT_OF_POLICY,
            pumps,
            HERO_OPP_STALLED,
            "pending_approval",
            _ts(25),
            [(HERO_PRODUCT_BOLT_SS316, "40", "20"), (HERO_PRODUCT_BEARING_ZZ, "10", "20")],
            valid_until=AS_OF + timedelta(days=15),
        )
        self._quote(
            HERO_QUOTE_FREE_TEXT,
            auto,
            HERO_OPP_BOLTS,
            "draft",
            _ts(2),
            [(HERO_PRODUCT_BOLT_SS304, "500", "0"), (HERO_PRODUCT_BEARING_2RS, "200", "0")],
            valid_until=AS_OF + timedelta(days=20),
        )
        accepted = self._quote(
            HERO_QUOTE_ACCEPTED,
            pumps,
            None,
            "accepted",
            _ts(52),
            [(HERO_PRODUCT_BOLT_SS304, "300", "0")],
            valid_until=AS_OF + timedelta(days=15),
        )
        order = self._order(accepted, pumps, "shipped", HERO_ORDER_SHIPPED, _ts(50))
        self._invoice(
            order, pumps, HERO_INVOICE_OVERDUE, "issued", issue_days_ago=50, paid=Decimal("0")
        )

    def _quote(
        self,
        quote_id: uuid.UUID,
        account: Account,
        opportunity_id: uuid.UUID | None,
        status: str,
        created: datetime,
        lines: list[tuple[uuid.UUID, str, str]],
        valid_until: date,
    ) -> Quotation:
        priced = {p.id: p for p in self.products}
        inputs = [
            LineInput(Decimal(qty), priced[pid].unit_price, Decimal(disc), priced[pid].tax_pct)
            for pid, qty, disc in lines
        ]
        totals = calculate_totals(inputs)
        items = [
            QuotationItem(
                id=_derived("quotation_item", len(self.objects) * 10 + position),
                position=position,
                product_id=pid,
                description=priced[pid].name,
                qty=Decimal(qty),
                unit_price=priced[pid].unit_price,
                discount_pct=Decimal(disc),
                tax_pct=priced[pid].tax_pct,
                line_total=amounts.line_total,
            )
            for position, ((pid, qty, disc), amounts) in enumerate(
                zip(lines, totals.lines, strict=True), 1
            )
        ]
        quotation = Quotation(
            id=quote_id,
            number=self._number("QT"),
            version=1,
            status=status,
            account_id=account.id,
            opportunity_id=opportunity_id,
            valid_until=valid_until,
            terms="Payment as per account terms. Prices are ex-works and exclude freight.",
            subtotal=totals.subtotal,
            discount_total=totals.discount_total,
            tax_total=totals.tax_total,
            total=totals.total,
            created_by_kind="human",
            owner_id=account.owner_id,
            team_id=account.team_id,
            items=items,
            created_at=created,
            updated_at=created,
        )
        self.quotations.append(self._add(quotation))
        return quotation

    def _order(
        self,
        quotation: Quotation,
        account: Account,
        status: str,
        order_id: uuid.UUID,
        created: datetime,
    ) -> Order:
        order = Order(
            id=order_id,
            number=self._number("SO"),
            quotation_id=quotation.id,
            account_id=account.id,
            status=status,
            shipping_address=f"Plot {self.rng.randint(1, 99)}, Industrial Area, {account.city}, "
            f"{account.state} {self.rng.randint(100000, 699999)}",
            expected_delivery_date=(created + timedelta(days=10)).date(),
            subtotal=quotation.subtotal,
            discount_total=quotation.discount_total,
            tax_total=quotation.tax_total,
            total=quotation.total,
            owner_id=quotation.owner_id,
            team_id=quotation.team_id,
            items=[
                OrderItem(
                    id=_derived("order_item", len(self.objects) * 10 + item.position),
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
            ],
            created_at=created + timedelta(days=2),
            updated_at=created + timedelta(days=2),
        )
        self.orders.append(self._add(order))
        return order

    def _invoice(
        self,
        order: Order,
        account: Account,
        invoice_id: uuid.UUID,
        status: str,
        issue_days_ago: int,
        paid: Decimal,
    ) -> Invoice:
        issue_date = AS_OF - timedelta(days=issue_days_ago)
        terms = account.payment_terms_days or 30
        invoice = Invoice(
            id=invoice_id,
            number=self._number("INV"),
            order_id=order.id,
            account_id=account.id,
            status=status,
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=terms),
            total=order.total,
            amount_paid=paid,
            owner_id=order.owner_id,
            team_id=order.team_id,
            created_at=_ts(issue_days_ago),
            updated_at=_ts(issue_days_ago),
        )
        self.invoices.append(self._add(invoice))
        return invoice

    def _filler_sales(self) -> None:
        open_accounts = self.accounts[2:]
        stages = ["discovery", "proposal", "negotiation", "lost"]
        for index in range(FILLER_OPPORTUNITIES):
            account = self.rng.choice(open_accounts)
            won = index < FILLER_ACCEPTED_QUOTES
            stage = "won" if won else self.rng.choice(stages)
            contact = self.contacts[account.id][0]
            created = _ts(self.rng.randint(70, 150) if won else self.rng.randint(5, 110))
            opportunity = self._add(
                Opportunity(
                    id=_derived("opportunity", index),
                    account_id=account.id,
                    contact_id=contact.id,
                    name=f"{self.rng.choice(FAMILIES)} supply, {account.city}",
                    stage=stage,
                    amount=Decimal(self.rng.randrange(50000, 800001, 5000)),
                    currency="INR",
                    probability={
                        "discovery": 10,
                        "proposal": 40,
                        "negotiation": 70,
                        "lost": 0,
                        "won": 100,
                    }[stage],
                    expected_close_date=AS_OF + timedelta(days=self.rng.randint(10, 90)),
                    requirements=None,
                    lost_reason="Price higher than local vendor" if stage == "lost" else None,
                    closed_at=_ts(self.rng.randint(1, 30)) if stage in ("won", "lost") else None,
                    owner_id=account.owner_id,
                    team_id=account.team_id,
                    created_at=created,
                    updated_at=created,
                )
            )
            if won:
                self.won_opportunities.append(opportunity)

        for index in range(FILLER_ACCEPTED_QUOTES):
            opportunity = self.won_opportunities[index]
            account_obj = next(a for a in self.accounts if a.id == opportunity.account_id)
            created = _ts(self.rng.randint(70, 150))
            lines = self._random_lines()
            quote = self._quote(
                _derived("quotation", index),
                account_obj,
                opportunity.id,
                "accepted",
                created,
                lines,
                valid_until=AS_OF + timedelta(days=15),
            )
            self.filler_orders.append((quote, account_obj))

        for index in range(FILLER_NON_ACCEPTED_QUOTES):
            account = self.rng.choice(open_accounts)
            status = ["draft", "sent", "rejected", "pending_approval"][index]
            disc = "8" if status == "pending_approval" else "0"
            self._quote(
                _derived("quotation", FILLER_ACCEPTED_QUOTES + index),
                account,
                None,
                status,
                _ts(self.rng.randint(5, 60)),
                self._random_lines(discount=disc),
                valid_until=AS_OF + timedelta(days=15),
            )

        shipping = [
            "delivered",
            "delivered",
            "delivered",
            "shipped",
            "shipped",
            "processing",
            "confirmed",
        ]
        for index, (quote, account) in enumerate(self.filler_orders):
            status = shipping[index]
            order = self._order(
                quote,
                account,
                status,
                _derived("order", index),
                quote.created_at + timedelta(days=2),
            )
            if status in ("delivered", "shipped"):
                issue_days = self.rng.randint(15, 75)
                # Fixed mix of settled, part-paid and open invoices across the shipped orders.
                if index in (0, 1):
                    self._invoice(
                        order, account, _derived("invoice", index), "paid", issue_days, order.total
                    )
                elif index == 2:
                    half = _money(order.total / 2)
                    self._invoice(
                        order,
                        account,
                        _derived("invoice", index),
                        "partially_paid",
                        issue_days,
                        half,
                    )
                else:
                    self._invoice(
                        order,
                        account,
                        _derived("invoice", index),
                        "issued",
                        issue_days,
                        Decimal("0"),
                    )

        self._activities()

    def _random_lines(self, discount: str = "0") -> list[tuple[uuid.UUID, str, str]]:
        filler = [p for p in self.products if p.id not in _HERO_PRODUCT_IDS and p.is_active]
        count = self.rng.randint(1, 4)
        lines = []
        for product in self.rng.sample(filler, count):
            qty = str(self.rng.choice([10, 20, 25, 50, 100, 200, 300, 500]))
            disc = discount if discount != "0" else self.rng.choice(["0", "0", "2", "3", "5"])
            lines.append((product.id, qty, disc))
        return lines

    # ---- activities -----------------------------------------------------------------------

    def _activities(self) -> None:
        self._hero_activities()
        open_filler = [
            o
            for o in self._filler_opportunities()
            if o.stage in ("discovery", "proposal", "negotiation")
        ]
        for opp in self.rng.sample(open_filler, NARRATIVE_OPPORTUNITIES):
            for step, template in enumerate(pools.FOLLOW_UP_TEMPLATES):
                product = self.rng.choice(self.products)
                self._activity(
                    EntityType.OPPORTUNITY,
                    opp.id,
                    opp.owner_id,
                    opp.team_id,
                    template.format(
                        product=self._colloquial(product),
                        contact=self._contact_first_name(opp.contact_id),
                        qty="300 pcs",
                    ),
                    days_ago=60 - step * 12,
                )
        for _ in range(FILLER_ACTIVITIES):
            pick = self.rng.random()
            if pick < 0.35:
                parent: Base = self.rng.choice(self.accounts[2:])
                entity, parent_id = EntityType.ACCOUNT, parent.id
            elif pick < 0.65:
                account = self.rng.choice(self.accounts[2:])
                parent = self.rng.choice(self.contacts[account.id])
                entity, parent_id = EntityType.CONTACT, parent.id
            elif pick < 0.90:
                parent = self.rng.choice(self._leads())
                entity, parent_id = EntityType.LEAD, parent.id
            else:
                parent = self.rng.choice(self._filler_opportunities())
                entity, parent_id = EntityType.OPPORTUNITY, parent.id
            body = self._body(self._who(entity, parent))
            self._activity(
                entity,
                parent_id,
                parent.owner_id,
                parent.team_id,
                body,
                days_ago=self.rng.randint(1, 90),
            )

    def _hero_activities(self) -> None:
        pumps, auto = self.accounts[0], self.accounts[1]
        hero = iter(range(HERO_ACTIVITY_BASE, HERO_ACTIVITY_BASE + 50))

        def hero_activity(
            entity: EntityType,
            parent_id: uuid.UUID,
            owner: uuid.UUID,
            team: uuid.UUID | None,
            type_: ActivityType,
            subject: str,
            body: str,
            days_ago: int,
        ) -> None:
            self._add(
                Activity(
                    id=_hero(next(hero)),
                    type=type_.value,
                    subject=subject,
                    body=body,
                    occurred_at=_ts(days_ago, hour=11),
                    entity_type=entity.value,
                    entity_id=parent_id,
                    created_by_kind="human",
                    meta=None,
                    owner_id=owner,
                    team_id=team,
                    created_at=_ts(days_ago, hour=11),
                    updated_at=_ts(days_ago, hour=11),
                )
            )

        hero_activity(
            EntityType.ACCOUNT,
            pumps.id,
            pumps.owner_id,
            pumps.team_id,
            ActivityType.CALL,
            "Impeller bearing pricing",
            "Call: Karthik ko pump impeller bearing ka rate bheja, kal tak confirm karenge bola.",
            50,
        )
        hero_activity(
            EntityType.ACCOUNT,
            pumps.id,
            pumps.owner_id,
            pumps.team_id,
            ActivityType.MEETING,
            "Plant visit",
            "Plant visit. Pump lines ki bearing failure pe discussion, "
            "6204 ki demand 3 lines ke liye.",
            40,
        )
        hero_activity(
            EntityType.OPPORTUNITY,
            HERO_OPP_STALLED,
            pumps.owner_id,
            pumps.team_id,
            ActivityType.NOTE,
            "Proposal shared",
            "Note: proposal bheja, procurement ne local vendor se comparison ka bola.",
            45,
        )
        hero_activity(
            EntityType.OPPORTUNITY,
            HERO_OPP_STALLED,
            pumps.owner_id,
            pumps.team_id,
            ActivityType.CALL,
            "Follow-up",
            "Call: Karthik ne bola approval wait kar rahe hain.",
            25,
        )
        hero_activity(
            EntityType.ACCOUNT,
            auto.id,
            auto.owner_id,
            auto.team_id,
            ActivityType.EMAIL,
            "RFQ",
            "Need 500 pcs 6mm SS bolts + 200 bearings 6204, delivery in 10 days",
            2,
        )
        hero_activity(
            EntityType.OPPORTUNITY,
            HERO_OPP_BOLTS,
            auto.owner_id,
            auto.team_id,
            ActivityType.CALL,
            "Negotiation",
            "Call: Meghana ne bola 200 pe better rate chahiye.",
            2,
        )
        hero_activity(
            EntityType.LEAD,
            HERO_LEAD_ORIGINAL,
            self.owners.rep,
            self.owners.team_id,
            ActivityType.NOTE,
            "Referral",
            "Note: referral se aaye, pump aur forging ke liye bearings chahiye.",
            3,
        )

    def _activity(
        self,
        entity: EntityType,
        parent_id: uuid.UUID,
        owner: uuid.UUID,
        team: uuid.UUID | None,
        body: str,
        days_ago: int,
    ) -> None:
        when = _ts(days_ago, hour=self.rng.randint(9, 18), minute=self.rng.randint(0, 59))
        self._add(
            Activity(
                id=_derived("activity", len(self.objects)),
                type=self.rng.choice(list(ActivityType)).value,
                subject=None,
                body=body,
                occurred_at=when,
                entity_type=entity.value,
                entity_id=parent_id,
                created_by_kind="human",
                meta=None,
                owner_id=owner,
                team_id=team,
                created_at=when,
                updated_at=when,
            )
        )

    def _body(self, who: str) -> str:
        if self.rng.random() < 0.35:
            product = self.rng.choice(self.products)
            return self.rng.choice(pools.ACTIVITY_TEMPLATES).format(
                product=self._colloquial(product),
                contact=who,
                qty=f"{self.rng.choice([100, 200, 300, 500])} pcs",
            )
        # Generic bodies have no product slot. The two draws below are the ones the original
        # generation made, so the random stream stays aligned; the template draw is unused.
        kind = self.rng.choice(sorted(pools.GENERIC_BODIES))
        self.rng.choice(pools.ACTIVITY_TEMPLATES)
        return pools.GENERIC_BODIES[kind].format(who=who, qty="100 pcs")

    @staticmethod
    def _colloquial(product: Product) -> str:
        if product.category == "bolts":
            size = product.name.split()[2].split("x")[0].lower()
            material = pools.FASTENER_COLLOQUIAL.get(product.name.split()[-1], "steel")
            return f"{size[1:]}mm {material} bolt"
        if product.category == "bearings":
            return f"bearing {product.name.split()[4]}"
        return product.name

    def _contact_first_name(self, contact_id: uuid.UUID | None) -> str:
        contact = next(
            (o for o in self.objects if isinstance(o, Contact) and o.id == contact_id), None
        )
        return contact.first_name if contact is not None else "buyer"

    def _who(self, entity: EntityType, parent: Base) -> str:
        """The real person an activity is about, so the text never carries a placeholder name."""
        if entity is EntityType.ACCOUNT:
            return self.contacts[parent.id][0].first_name
        if entity is EntityType.CONTACT:
            return parent.first_name
        if entity is EntityType.LEAD:
            return parent.name.split()[0]
        return self._contact_first_name(parent.contact_id)

    def _leads(self) -> list[Lead]:
        return [
            o
            for o in self.objects
            if isinstance(o, Lead) and o.id not in (HERO_LEAD_ORIGINAL, HERO_LEAD_DUPLICATE)
        ]

    def _filler_opportunities(self) -> list[Opportunity]:
        hero = {HERO_OPP_STALLED, HERO_OPP_BOLTS}
        return [o for o in self.objects if isinstance(o, Opportunity) and o.id not in hero]

    # ---- stock ----------------------------------------------------------------------------

    def settle_stock(self) -> None:
        """Stock = what was consumed by shipped/delivered orders + what is still reserved + a
        buffer. Hero bearings are fixed (the low-stock demo depends on them), not derived."""
        consumed: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
        reserved: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
        for order in self.orders:
            if order.status in ("shipped", "delivered"):
                books = consumed
            elif order.status in ("processing", "confirmed"):
                books = reserved
            else:
                continue
            for item in order.items:
                books[item.product_id] += item.qty
        for product in self.products:
            used, held = consumed[product.id], reserved[product.id]
            product.reserved_qty = held
            if product.id == HERO_PRODUCT_BEARING_2RS:
                product.stock_qty = HERO_BEARING_2RS_STOCK
            elif product.id == HERO_PRODUCT_BEARING_ZZ:
                product.stock_qty = HERO_BEARING_ZZ_STOCK
            elif product.id == HERO_PRODUCT_BOLT_SS304:
                product.stock_qty = HERO_BOLT_SS304_STOCK
            else:
                product.stock_qty = used + held + Decimal(self.rng.randint(40, 400))


_HERO_PRODUCT_IDS = {
    HERO_PRODUCT_BOLT_SS304,
    HERO_PRODUCT_BOLT_SS316,
    HERO_PRODUCT_BEARING_2RS,
    HERO_PRODUCT_BEARING_ZZ,
}


def _spec(
    sku: str, name: str, category: str, unit: str, price: Decimal, tax: str, lead: int, moq: int
) -> dict:
    return {
        "sku": sku,
        "name": name,
        "category": category,
        "unit": unit,
        "price": price,
        "tax": tax,
        "lead": lead,
        "moq": moq,
    }


def build_dataset(owners: SeedOwners) -> Dataset:
    """Pure: returns every row to insert. Deterministic for a given `owners` mapping."""
    builder = _Builder(owners)
    builder.build_products()
    builder.build_accounts()
    builder.build_leads()
    builder.build_sales()
    builder.settle_stock()
    return Dataset(objects=builder.objects, sequences=dict(builder.sequences))
