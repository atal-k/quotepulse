import pytest

from app.core.errors import Conflict
from app.modules.quotations.service import TRANSITIONS, check_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [(c, t) for c in TRANSITIONS for t in TRANSITIONS if t in TRANSITIONS[c]],
)
def test_declared_transitions_are_allowed(current: str, target: str) -> None:
    check_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [(c, t) for c in TRANSITIONS for t in TRANSITIONS if t != c and t not in TRANSITIONS[c]],
)
def test_undeclared_transitions_are_conflicts(current: str, target: str) -> None:
    with pytest.raises(Conflict) as raised:
        check_transition(current, target)
    assert raised.value.details["from"] == current
    assert raised.value.details["to"] == target


def test_terminal_states_have_no_exits() -> None:
    for terminal in ("accepted", "rejected", "expired", "superseded"):
        assert TRANSITIONS[terminal] == set()
