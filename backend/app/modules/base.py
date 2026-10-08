from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import NotFound, PermissionDenied
from app.core.pagination import Page, PageParams
from app.core.rbac import Action, Actor, can, visibility_clause


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID | Decimal):
        return str(value)
    if isinstance(value, date):  # also covers datetime, which subclasses date
        return value.isoformat()
    return value


class CrudService[ModelT, CreateT: BaseModel, UpdateT: BaseModel]:
    """Scoped + audited CRUD for a simple owned aggregate. No delete: DOMAIN.md requires hard
    deletes to go through a gated admin action, which doesn't exist until the approvals module
    (Phase 4) — subclasses add `delete` then, not before.

    Subclasses set `model`, `resource` (permission-matrix key) and `entity_type` (audit log key),
    and may override the async hooks `prepare_create`/`authorize_update`/`after_update` for
    aggregate-specific rules (who may assign ownership, parent lookups, cascades) without touching
    the scoping/audit plumbing.
    """

    model: type[ModelT]
    resource: str
    entity_type: str
    # False for global resources with no owner_id/team_id (the catalog): row visibility is then
    # unrestricted and access is governed by the permission matrix alone.
    owned: bool = True

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _visible(self, actor: Actor) -> ColumnElement[bool]:
        return visibility_clause(actor, self.model) if self.owned else true()

    def _require(self, actor: Actor, action: Action) -> None:
        if not can(actor, self.resource, action):
            raise PermissionDenied(f"{actor.role} may not {action.value} {self.resource}.")

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        """Default ownership: creator owns the row unless already supplied."""
        if self.owned:
            payload.setdefault("owner_id", actor.user_id)
            payload.setdefault("team_id", actor.team_id)
        return payload

    async def authorize_update(self, actor: Actor, obj: ModelT, payload: dict[str, Any]) -> None:
        """Field-level update rules and payload normalization; runs before the update is applied.
        No-op by default."""
        return None

    async def after_update(self, actor: Actor, obj: ModelT, changes: dict[str, list[Any]]) -> None:
        """Runs after the update is flushed and audited, only when something changed. No-op by
        default."""
        return None

    async def after_create(self, actor: Actor, obj: ModelT) -> None:
        """Runs after the create is flushed and audited. No-op by default; `activities`
        overrides this to enqueue `process_activity`."""
        return None

    async def get(self, actor: Actor, id: UUID) -> ModelT:
        self._require(actor, Action.READ)
        stmt = select(self.model).where(self.model.id == id, self._visible(actor))
        obj = (await self.session.execute(stmt)).scalar_one_or_none()
        if obj is None:
            raise NotFound(f"{self.entity_type} not found.", {"id": str(id)})
        return obj

    async def list(
        self, actor: Actor, page: PageParams, filters: Mapping[str, Any] | None = None
    ) -> Page[ModelT]:
        """`filters` are equality filters on model columns; `None` values are ignored."""
        self._require(actor, Action.READ)
        base_stmt = select(self.model).where(self._visible(actor))
        for column, value in (filters or {}).items():
            if value is not None:
                base_stmt = base_stmt.where(getattr(self.model, column) == value)
        total = (
            await self.session.execute(select(func.count()).select_from(base_stmt.subquery()))
        ).scalar_one()
        stmt = (
            base_stmt.order_by(self.model.created_at.desc(), self.model.id)
            .limit(page.limit)
            .offset(page.offset)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return Page(items=list(items), total=total, limit=page.limit, offset=page.offset)

    async def create(self, actor: Actor, data: CreateT) -> ModelT:
        self._require(actor, Action.CREATE)
        payload = await self.prepare_create(actor, data.model_dump(exclude_unset=True))
        obj = self.model(**payload)
        self.session.add(obj)
        await self.session.flush()
        changes = {field: [None, _jsonable(value)] for field, value in payload.items()}
        await audit.record(self.session, actor, "create", self.entity_type, obj.id, changes)
        await self.after_create(actor, obj)
        return obj

    async def update(self, actor: Actor, id: UUID, data: UpdateT) -> ModelT:
        obj = await self.get(actor, id)
        self._require(actor, Action.UPDATE)
        payload = data.model_dump(exclude_unset=True)
        await self.authorize_update(actor, obj, payload)
        return await self._apply_update(actor, obj, payload)

    async def _apply_update(self, actor: Actor, obj: ModelT, payload: dict[str, Any]) -> ModelT:
        """Set, flush and audit a payload that has already been authorized. Also the entry point
        for internal state changes that the public update path must not allow (e.g. `mark_won`)."""
        changes: dict[str, list[Any]] = {}
        for field, new_value in payload.items():
            old_value = getattr(obj, field)
            if old_value != new_value:
                changes[field] = [_jsonable(old_value), _jsonable(new_value)]
                setattr(obj, field, new_value)

        await self.session.flush()
        if changes:
            await audit.record(self.session, actor, "update", self.entity_type, obj.id, changes)
            await self.after_update(actor, obj, changes)
        return obj
