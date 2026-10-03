from enum import StrEnum


class EntityType(StrEnum):
    """Entities an activity or notification can point at. Kept in an import-free module so the
    models, schemas, parent lookup and ownership cascade can all share it without import cycles.
    Widened by the migration that adds each new parent entity (quotations, orders, invoices)."""

    ACCOUNT = "account"
    CONTACT = "contact"
    LEAD = "lead"
    OPPORTUNITY = "opportunity"


class ActivityType(StrEnum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    CHAT = "chat"
    WHATSAPP = "whatsapp"


def in_list_sql(values: type[StrEnum]) -> str:
    return "(" + ", ".join(f"'{v.value}'" for v in values) + ")"
