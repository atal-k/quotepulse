import re

from app.core.errors import ValidationFailed

_PHONE_NOISE = re.compile(r"[\s\-().]")
_INDIA_CODE = "91"


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    """Normalize to E.164 (`+919876543210`). Numbers without a country code are taken to be
    Indian (this is an India-market CRM); a single leading `0` trunk prefix is dropped."""
    cleaned = _PHONE_NOISE.sub("", value)
    if cleaned.startswith("+"):
        digits = cleaned[1:]
    elif cleaned.startswith("00"):
        digits = cleaned[2:]
    else:
        local = cleaned[1:] if cleaned.startswith("0") else cleaned
        if len(local) == 10:
            digits = _INDIA_CODE + local
        else:
            digits = local
    if not digits.isdigit() or digits.startswith("0") or not 8 <= len(digits) <= 15:
        raise ValidationFailed("Invalid phone number.", {"field": "phone", "value": value})
    return f"+{digits}"
