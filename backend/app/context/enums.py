from enum import StrEnum


class DuplicateType(StrEnum):
    FUZZY_NAME = "fuzzy_name"


class DuplicateEntityType(StrEnum):
    ACCOUNT = "account"
    CONTACT = "contact"
    LEAD = "lead"


class DuplicateStatus(StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"
