"""asyncpg implementation of AgentRepository. All SQL is parametrized."""

from __future__ import annotations

from typing import Any, NoReturn
from uuid import UUID

import asyncpg

from embers.db.pool import Database
from embers.domain.ports import (
    AgentChanges,
    AgentOpenTasks,
    AgentRecord,
    AppearanceTooLargeError,
    DuplicateAgentNameError,
    NewAgent,
)

_ACTIVE_NAME_INDEX = "agents_active_name_unique"
_APPEARANCE_SIZE_CHECK = "ui_settings_data_size"

_SELECT_AGENT = """
select a.id, a.name, a.model_config, a.identity, a.instructions, a.tools,
       a.status, a.version, a.created_at, a.updated_at, a.character_status,
       u.data as appearance
from public.agents a
left join public.ui_settings u
       on u.workspace_id = a.workspace_id
      and u.owner_type = 'agent'
      and u.owner_id = a.id
      and u.namespace = 'appearance'
"""

_UPSERT_APPEARANCE = """
insert into public.ui_settings (workspace_id, owner_type, owner_id, namespace, data)
values ($1, 'agent', $2, 'appearance', $3)
on conflict (workspace_id, owner_type, owner_id, namespace)
do update set data = excluded.data
"""


def _to_record(row: asyncpg.Record) -> AgentRecord:
    return AgentRecord(
        id=row["id"],
        name=row["name"],
        model_config=row["model_config"],
        identity=row["identity"],
        instructions=row["instructions"],
        tools=list(row["tools"]) if row["tools"] is not None else None,
        status=row["status"],
        version=row["version"],
        appearance=row["appearance"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        character_status=row["character_status"],
    )


class PgAgentRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, workspace_id: UUID, agent: NewAgent) -> AgentRecord:
        async with self._db.acquire() as conn, conn.transaction():
            try:
                agent_id = await conn.fetchval(
                    """
                    insert into public.agents
                        (workspace_id, name, model_config, identity, instructions, tools)
                    values ($1, $2, $3, $4, $5, $6)
                    returning id
                    """,
                    workspace_id,
                    agent.name,
                    agent.model_config,
                    agent.identity,
                    agent.instructions,
                    agent.tools,
                )
                if agent.appearance is not None:
                    await conn.execute(_UPSERT_APPEARANCE, workspace_id, agent_id, agent.appearance)
            except (asyncpg.UniqueViolationError, asyncpg.CheckViolationError) as exc:
                _raise_domain_error(exc)
            row = await conn.fetchrow(f"{_SELECT_AGENT} where a.id = $1", agent_id)
        assert row is not None
        return _to_record(row)

    async def get(self, workspace_id: UUID, agent_id: UUID) -> AgentRecord | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"{_SELECT_AGENT} where a.workspace_id = $1 and a.id = $2",
                workspace_id,
                agent_id,
            )
        return _to_record(row) if row is not None else None

    async def list_agents(self, workspace_id: UUID, *, include_archived: bool) -> list[AgentRecord]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                f"""{_SELECT_AGENT}
                where a.workspace_id = $1 and ($2 or a.status = 'active')
                order by a.created_at, a.id
                """,
                workspace_id,
                include_archived,
            )
        return [_to_record(row) for row in rows]

    async def update(
        self, workspace_id: UUID, agent_id: UUID, changes: AgentChanges
    ) -> AgentRecord:
        async with self._db.acquire() as conn, conn.transaction():
            try:
                await conn.execute(
                    """
                    update public.agents
                    set name = $3, model_config = $4, identity = $5,
                        instructions = $6, tools = $7, version = $8
                    where workspace_id = $1 and id = $2
                    """,
                    workspace_id,
                    agent_id,
                    changes.name,
                    changes.model_config,
                    changes.identity,
                    changes.instructions,
                    changes.tools,
                    changes.version,
                )
            except asyncpg.UniqueViolationError as exc:
                _raise_domain_error(exc)
            row = await conn.fetchrow(
                f"{_SELECT_AGENT} where a.workspace_id = $1 and a.id = $2", workspace_id, agent_id
            )
        assert row is not None
        return _to_record(row)

    async def archive(self, workspace_id: UUID, agent_id: UUID) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                update public.agents set status = 'archived'
                where workspace_id = $1 and id = $2 and status = 'active'
                """,
                workspace_id,
                agent_id,
            )

    async def open_tasks(
        self, workspace_id: UUID, agent_ids: list[UUID]
    ) -> dict[UUID, AgentOpenTasks]:
        async with self._db.acquire() as conn:
            return await _open_tasks(conn, workspace_id, agent_ids)

    async def save_appearance(
        self, workspace_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> AgentRecord:
        async with self._db.acquire() as conn, conn.transaction():
            try:
                await conn.execute(_UPSERT_APPEARANCE, workspace_id, agent_id, data)
            except asyncpg.CheckViolationError as exc:
                _raise_domain_error(exc)
            row = await conn.fetchrow(
                f"{_SELECT_AGENT} where a.workspace_id = $1 and a.id = $2", workspace_id, agent_id
            )
        assert row is not None
        return _to_record(row)


async def _open_tasks(
    conn: asyncpg.pool.PoolConnectionProxy, workspace_id: UUID, agent_ids: list[UUID]
) -> dict[UUID, AgentOpenTasks]:
    rows = await conn.fetch(
        """
        select agent_id, id, status
        from public.tasks
        where workspace_id = $1 and agent_id = any($2::uuid[])
          and status in ('queued', 'working', 'waiting_user')
        order by created_at, id
        """,
        workspace_id,
        agent_ids,
    )
    current: dict[UUID, UUID] = {}
    queued: dict[UUID, list[UUID]] = {}
    for row in rows:
        if row["status"] == "queued":
            queued.setdefault(row["agent_id"], []).append(row["id"])
        else:
            current[row["agent_id"]] = row["id"]
    return {
        agent_id: AgentOpenTasks(
            current_task_id=current.get(agent_id),
            queued_task_ids=tuple(queued.get(agent_id, [])),
        )
        for agent_id in agent_ids
    }


def _raise_domain_error(exc: asyncpg.PostgresError) -> NoReturn:
    constraint = getattr(exc, "constraint_name", None)
    if constraint == _ACTIVE_NAME_INDEX:
        raise DuplicateAgentNameError from exc
    if constraint == _APPEARANCE_SIZE_CHECK:
        raise AppearanceTooLargeError from exc
    raise exc
