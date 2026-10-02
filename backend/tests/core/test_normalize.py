import pytest

from app.core.errors import ValidationFailed
from app.core.normalize import normalize_email, normalize_phone


def test_email_is_trimmed_and_lowercased() -> None:
    assert normalize_email("  Rohan.Verma@ACME-Bolts.IN ") == "rohan.verma@acme-bolts.in"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+91 98765 43210", "+919876543210"),
        ("98765-43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("0091 98765 43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("(022) 2345 6789", "+912223456789"),
        ("+1 (415) 555-0132", "+14155550132"),
    ],
)
def test_phone_normalizes_to_e164(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "abc", "12345", "+0123456789", "98765 4321 0X", "+1234567890123456"]
)
def test_invalid_phone_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationFailed):
        normalize_phone(raw)
