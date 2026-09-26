"""In-process event bus using the same envelope as the WebSocket contract.

Publishers stay decoupled from the transport: phase 2 will add a WebSocket
subscriber (and persistence into `task_events`) without touching publishers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Event(BaseModel):
    """The WebSocket contract envelope. `event_id` is always None in this phase
    because events are not persisted yet."""

    type: str
    event_id: int | None = None
    ts: datetime
    agent_id: UUID | None
    task_id: UUID | None
    data: dict[str, Any]


class Subscriber(Protocol):
    async def __call__(self, event: Event) -> None: ...


class EventBus:
    """Delivers published events to subscribers, in order, isolating failures."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    async def publish(self, event: Event) -> None:
        for subscriber in self._subscribers:
            try:
                await subscriber(event)
            except Exception:
                logger.exception(
                    "event subscriber failed",
                    extra={"event_type": event.type},
                )
