from uuid import uuid4

from app.core.rbac import Action, Actor, ActorKind, Role, can, permissions_for


def test_rep_has_no_delete_by_default() -> None:
    assert Action.DELETE not in permissions_for(Role.REP, "accounts")


def test_manager_has_no_delete_by_default() -> None:
    assert Action.DELETE not in permissions_for(Role.MANAGER, "accounts")


def test_admin_has_full_permissions_by_default() -> None:
    perms = permissions_for(Role.ADMIN, "accounts")
    assert perms == {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE}


def test_can_reflects_permissions_for() -> None:
    rep = Actor(user_id=uuid4(), role=Role.REP, team_id=None, kind=ActorKind.HUMAN)
    assert can(rep, "accounts", Action.READ) is True
    assert can(rep, "accounts", Action.DELETE) is False
