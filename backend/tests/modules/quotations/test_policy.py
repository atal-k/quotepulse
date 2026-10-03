from decimal import Decimal

import pytest

from app.core.rbac import Role
from app.modules.quotations.policy import can_approve, required_approver


@pytest.mark.parametrize(
    ("discount", "required"),
    [
        ("0", None),
        ("5", None),
        ("5.01", Role.MANAGER),
        ("15", Role.MANAGER),
        ("15.01", Role.ADMIN),
        ("100", Role.ADMIN),
    ],
)
def test_discount_tiers(discount: str, required: Role | None) -> None:
    assert required_approver(Decimal(discount)) == required


@pytest.mark.parametrize(
    ("role", "required", "allowed"),
    [
        (Role.REP, None, True),
        (Role.REP, Role.MANAGER, False),
        (Role.MANAGER, Role.MANAGER, True),
        (Role.MANAGER, Role.ADMIN, False),
        (Role.ADMIN, Role.MANAGER, True),
        (Role.ADMIN, Role.ADMIN, True),
    ],
)
def test_approval_matrix(role: Role, required: Role | None, allowed: bool) -> None:
    assert can_approve(role, required) is allowed
