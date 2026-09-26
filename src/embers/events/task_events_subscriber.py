"""Stores internal events (agent.*) in `task_events` with a null direction."""

from __future__ import annotations

from embers.db.task_events_repository import PgTaskEventsRepository
from embers.events.bus import Event


class TaskEventsSubscriber:
    def __init__(self, events: PgTaskEventsRepository) -> None:
        self._events = events

    async def __call__(self, event: Event) -> None:
        await self._events.insert(
            type=event.type,
            direction=None,
            agent_id=event.agent_id,
            task_id=event.task_id,
            data=event.data,
        )
