"""asyncpg access to `task_events`: every WebSocket message and internal event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from embers.db.pool import Database


@dataclass(frozen=True)
class StoredEvent:
    id: int
    created_at: datetime
    type: str
    agent_id: UUID | None
    task_id: UUID | None
    data: dict[str, Any] | None


class PgTaskEventsRepository:
    def __init__(self, db: Database, workspace_id: UUID) -> None:
        self._db = db
        self._workspace_id = workspace_id

    async def insert(
        self,
        *,
        type: str,
        direction: str | None,
        agent_id: UUID | None,
        task_id: UUID | None,
        data: dict[str, Any] | None,
    ) -> StoredEvent:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into public.task_events
                    (workspace_id, type, direction, agent_id, task_id, data)
                values ($1, $2, $3, $4, $5, $6)
                returning id, created_at
                """,
                self._workspace_id,
                type,
                direction,
                agent_id,
                task_id,
                data,
            )
        assert row is not None
        return StoredEvent(row["id"], row["created_at"], type, agent_id, task_id, data)

    async def pending_asks(self) -> list[StoredEvent]:
        """Original `ask` messages whose question is still pending, oldest first."""
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                select e.id, e.created_at, e.type, e.agent_id, e.task_id, e.data
                from public.task_events e
                join public.task_questions q
                  on q.id = (e.data -> 'data' ->> 'question_id')::uuid
                where e.workspace_id = $1
                  and e.type = 'ask' and e.direction = 'out' and q.status = 'pending'
                order by e.id
                """,
                self._workspace_id,
            )
        return [
            StoredEvent(r["id"], r["created_at"], r["type"], r["agent_id"], r["task_id"], r["data"])
            for r in rows
        ]
