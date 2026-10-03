import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import NotFound
from app.core.pagination import Page, PageParams
from app.core.rbac import Actor
from app.modules.notifications.models import Notification


async def notify(
    session: AsyncSession,
    actor: Actor,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> Notification:
    """Called directly by other services in the same transaction as the change they describe."""
    item = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(item)
    await session.flush()
    await audit.record(
        session,
        actor,
        "create",
        "notification",
        item.id,
        {"user_id": [None, str(user_id)], "kind": [None, kind]},
    )
    return item


class NotificationService:
    """Own-feed only: every query is pinned to the actor's user_id, regardless of role."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, actor: Actor, page: PageParams, unread_only: bool) -> Page[Notification]:
        base = select(Notification).where(Notification.user_id == actor.user_id)
        if unread_only:
            base = base.where(Notification.read_at.is_(None))
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = (
            base.order_by(Notification.created_at.desc(), Notification.id)
            .limit(page.limit)
            .offset(page.offset)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        return Page(items=items, total=total, limit=page.limit, offset=page.offset)

    async def mark_read(self, actor: Actor, id: uuid.UUID) -> Notification:
        stmt = select(Notification).where(
            Notification.id == id, Notification.user_id == actor.user_id
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFound("notification not found.", {"id": str(id)})
        if item.read_at is None:
            item.read_at = datetime.now(UTC)
            await self.session.flush()
            await audit.record(
                self.session,
                actor,
                "update",
                "notification",
                item.id,
                {"read_at": [None, item.read_at.isoformat()]},
            )
        return item
