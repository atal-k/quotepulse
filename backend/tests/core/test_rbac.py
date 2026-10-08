from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import false

from app.core.rbac import Action, Actor, ActorKind, Role, can, permissions_for, visibility_clause
from app.modules.accounts.models import Account


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


def test_human_actor_requires_user_id_and_role() -> None:
    with pytest.raises(ValidationError, match="user_id and role are required"):
        Actor(user_id=None, role=None, team_id=None, kind=ActorKind.HUMAN)
    with pytest.raises(ValidationError, match="user_id and role are required"):
        Actor(user_id=uuid4(), role=None, team_id=None, kind=ActorKind.AGENT)


def test_system_actor_may_omit_user_id_and_role() -> None:
    system = Actor(user_id=None, role=None, team_id=None, kind=ActorKind.SYSTEM)
    assert system.user_id is None
    assert system.role is None


def test_system_actor_can_nothing_and_sees_nothing() -> None:
    system = Actor(user_id=None, role=None, team_id=None, kind=ActorKind.SYSTEM)
    assert can(system, "accounts", Action.READ) is False
    assert visibility_clause(system, Account).compare(false())
