from decimal import Decimal

import pytest

from app.modules.quotations.totals import LineInput, calculate_totals, price_line

D = Decimal


def test_line_follows_the_domain_formula() -> None:
    line = price_line(
        LineInput(qty=D("10"), unit_price=D("100.00"), discount_pct=D("10"), tax_pct=D("18"))
    )

    assert (line.discount, line.net, line.tax, line.line_total) == (
        D("100.00"),
        D("900.00"),
        D("162.00"),
        D("1062.00"),
    )


def test_tax_rounds_half_up_to_the_paisa() -> None:
    # 99.99 × 5% = 4.9995, which must round to 5.00 (half-up), not 4.99 (banker's rounding).
    line = price_line(
        LineInput(qty=D("3"), unit_price=D("33.33"), discount_pct=D("0"), tax_pct=D("5"))
    )

    assert line.tax == D("5.00")
    assert line.line_total == D("104.99")


def test_document_totals_are_sums_of_rounded_lines() -> None:
    totals = calculate_totals(
        [
            LineInput(qty=D("10"), unit_price=D("100.00"), discount_pct=D("10"), tax_pct=D("18")),
            LineInput(qty=D("3"), unit_price=D("33.33"), discount_pct=D("0"), tax_pct=D("5")),
        ]
    )

    assert totals.subtotal == D("999.99")
    assert totals.discount_total == D("100.00")
    assert totals.tax_total == D("167.00")
    assert totals.total == D("1166.99")
    assert totals.total == totals.subtotal + totals.tax_total


def test_full_discount_leaves_no_tax() -> None:
    totals = calculate_totals(
        [LineInput(qty=D("2"), unit_price=D("50"), discount_pct=D("100"), tax_pct=D("18"))]
    )

    assert totals.subtotal == D("0.00")
    assert totals.total == D("0.00")


def test_empty_quote_totals_to_zero() -> None:
    totals = calculate_totals([])

    assert (totals.subtotal, totals.discount_total, totals.tax_total, totals.total) == (
        D("0"),
        D("0"),
        D("0"),
        D("0"),
    )


@pytest.mark.parametrize(
    ("qty", "price", "discount", "expected_total"),
    [
        ("1", "100.00", "0", "118.00"),
        ("2.5", "40.00", "5", "112.10"),
        ("1", "0.10", "0", "0.12"),
    ],
)
def test_line_total_is_net_plus_tax(
    qty: str, price: str, discount: str, expected_total: str
) -> None:
    line = price_line(
        LineInput(qty=D(qty), unit_price=D(price), discount_pct=D(discount), tax_pct=D("18"))
    )

    assert line.line_total == D(expected_total)
