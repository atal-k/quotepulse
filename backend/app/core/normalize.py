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


# Consumer mail providers: an address on one of these says nothing about the sender's company,
# so it must never be used to match or create an account by domain.
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.in",
        "yahoo.co.in",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "rediffmail.com",
        "rediff.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "zoho.com",
        "gmx.com",
        "mail.com",
        "yandex.com",
    }
)


def business_domain(email: str | None) -> str | None:
    """The company domain of an email address, or None if absent or a free-mail provider."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().lower()
    return None if not domain or domain in FREE_EMAIL_DOMAINS else domain
