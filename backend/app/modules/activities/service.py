from datetime import UTC, datetime
from typing import Any

from app.core.rbac import Actor
from app.modules.activities.models import Activity
from app.modules.activities.refs import load_parent
from app.modules.activities.schemas import ActivityCreate, ActivityUpdate
from app.modules.base import CrudService


class ActivityService(CrudService[Activity, ActivityCreate, ActivityUpdate]):
    model = Activity
    resource = "activities"
    entity_type = "activity"

    async def prepare_create(self, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
        parent = await load_parent(
            self.session, actor, payload["entity_type"], payload["entity_id"]
        )
        payload["owner_id"] = parent.owner_id
        payload["team_id"] = parent.team_id
        payload["created_by_kind"] = actor.kind.value
        payload.setdefault("occurred_at", datetime.now(UTC))
        return payload

    async def authorize_update(self, actor: Actor, obj: Activity, payload: dict[str, Any]) -> None:
        for field in ("type", "occurred_at"):
            if field in payload and payload[field] is None:
                payload.pop(field)
