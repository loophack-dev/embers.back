"""Records every WebSocket message in `task_events` and delivers outgoing ones."""

from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from embers.contracts.ws import AskData, FinishData, ServerMessage
from embers.db.task_events_repository import PgTaskEventsRepository, StoredEvent
from embers.domain.ports import TaskRecord
from embers.realtime.connections import Connection, ConnectionRegistry

logger = logging.getLogger(__name__)

OutgoingType = Literal["ack", "error", "ask", "finish"]
RAW_CHARS = 2000


def _envelope(stored: StoredEvent) -> dict[str, Any]:
    """Rebuild the wire message from its row: `event_id` and `ts` are the row's id and date."""
    body = stored.data or {}
    message = ServerMessage(
        type=body["type"],
        event_id=stored.id,
        ts=stored.created_at,
        agent_id=stored.agent_id,
        task_id=stored.task_id,
        request_id=body.get("request_id"),
        data=body.get("data", {}),
    )
    return message.model_dump(mode="json")


class Outbox:
    def __init__(self, events: PgTaskEventsRepository, registry: ConnectionRegistry) -> None:
        self._events = events
        self._registry = registry

    async def record_incoming(
        self,
        *,
        type: str,
        request_id: str | None,
        agent_id: UUID | None,
        task_id: UUID | None,
        data: dict[str, Any],
    ) -> None:
        await self._events.insert(
            type=type,
            direction="in",
            agent_id=agent_id,
            task_id=task_id,
            data={"type": type, "request_id": request_id, "data": data},
        )
        logger.info(
            "ws message received",
            extra={
                "type": type,
                "request_id": request_id,
                "agent_id": str(agent_id) if agent_id else None,
                "task_id": str(task_id) if task_id else None,
            },
        )

    async def record_unreadable(self, raw: str) -> None:
        await self._events.insert(
            type="unknown",
            direction="in",
            agent_id=None,
            task_id=None,
            data={"raw": raw[:RAW_CHARS]},
        )
        logger.info("ws unreadable message received", extra={"length": len(raw)})

    async def send(
        self,
        connection: Connection,
        type: OutgoingType,
        *,
        request_id: str | None,
        agent_id: UUID | None,
        task_id: UUID | None,
        data: BaseModel | dict[str, Any],
    ) -> None:
        message = await self._store(type, request_id, agent_id, task_id, data)
        await connection.send(message)

    async def broadcast(
        self,
        type: OutgoingType,
        *,
        agent_id: UUID | None,
        task_id: UUID | None,
        data: BaseModel,
    ) -> None:
        message = await self._store(type, None, agent_id, task_id, data)
        for connection in self._registry.all():
            try:
                await connection.send(message)
            except Exception:
                logger.warning(
                    "dropping websocket after failed send",
                    extra={"connection_id": str(connection.id)},
                )
                self._registry.remove(connection)

    async def resend_pending_asks(self, connection: Connection) -> None:
        for stored in await self._events.pending_asks():
            await connection.send(_envelope(stored))

    async def _store(
        self,
        type: OutgoingType,
        request_id: str | None,
        agent_id: UUID | None,
        task_id: UUID | None,
        data: BaseModel | dict[str, Any],
    ) -> dict[str, Any]:
        payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
        stored = await self._events.insert(
            type=type,
            direction="out",
            agent_id=agent_id,
            task_id=task_id,
            data={"type": type, "request_id": request_id, "data": payload},
        )
        logger.info(
            "ws message sent",
            extra={
                "type": type,
                "event_id": stored.id,
                "request_id": request_id,
                "task_id": str(task_id) if task_id else None,
            },
        )
        return _envelope(stored)

    # --- TaskNotifier ---

    async def ask(self, task: TaskRecord, data: AskData) -> None:
        await self.broadcast("ask", agent_id=task.agent_id, task_id=task.id, data=data)

    async def finish(self, task: TaskRecord, data: FinishData) -> None:
        await self.broadcast("finish", agent_id=task.agent_id, task_id=task.id, data=data)
