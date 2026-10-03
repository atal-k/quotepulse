"""Discount approval tiers (DOMAIN.md): a quotation's largest line discount decides who may
approve it. Thresholds are settings-level policy and must match the markdown policy in 1C."""

from decimal import Decimal

from app.core.rbac import Role

OWNER_LIMIT_PCT = Decimal("5")
MANAGER_LIMIT_PCT = Decimal("15")


def required_approver(max_discount_pct: Decimal) -> Role | None:
    """None means the quotation owner may send it without a second person."""
    if max_discount_pct <= OWNER_LIMIT_PCT:
        return None
    if max_discount_pct <= MANAGER_LIMIT_PCT:
        return Role.MANAGER
    return Role.ADMIN


def can_approve(role: Role, required: Role | None) -> bool:
    if required is None:
        return True
    if required == Role.MANAGER:
        return role in (Role.MANAGER, Role.ADMIN)
    return role == Role.ADMIN
