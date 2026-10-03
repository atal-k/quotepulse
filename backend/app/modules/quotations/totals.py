"""Quotation pricing (DOMAIN.md, Business rules). Pure and deterministic: the server computes every
amount from catalog prices and the requested quantities and discounts; client-supplied totals are
never read.

Per line, each amount is rounded half-up to 2 dp before summing:
  gross    = qty × unit_price
  discount = gross × discount_pct / 100
  net      = gross × (1 − discount_pct / 100)
  tax      = net × tax_pct / 100
  total    = net + tax
Document totals are sums of the rounded line amounts.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineInput:
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    tax_pct: Decimal


@dataclass(frozen=True)
class LineAmounts:
    discount: Decimal
    net: Decimal
    tax: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class Totals:
    lines: tuple[LineAmounts, ...]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def price_line(line: LineInput) -> LineAmounts:
    gross = line.qty * line.unit_price
    discount = _money(gross * line.discount_pct / HUNDRED)
    net = _money(gross * (HUNDRED - line.discount_pct) / HUNDRED)
    tax = _money(net * line.tax_pct / HUNDRED)
    return LineAmounts(discount=discount, net=net, tax=tax, line_total=net + tax)


def calculate_totals(lines: Sequence[LineInput]) -> Totals:
    priced = tuple(price_line(line) for line in lines)
    subtotal = sum((p.net for p in priced), Decimal("0"))
    tax_total = sum((p.tax for p in priced), Decimal("0"))
    return Totals(
        lines=priced,
        subtotal=subtotal,
        discount_total=sum((p.discount for p in priced), Decimal("0")),
        tax_total=tax_total,
        total=subtotal + tax_total,
    )
