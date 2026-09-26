"""asyncpg implementation of ArtifactRepository. All SQL is parametrized."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from embers.db.pool import Database
from embers.domain.ports import ArtifactRecord

_COLUMNS = """
id, task_id, agent_id, type, status, title, mime, storage_path, size_bytes, created_at,
url, url_expires_at
"""


def _to_record(row: asyncpg.Record) -> ArtifactRecord:
    return ArtifactRecord(
        id=row["id"],
        task_id=row["task_id"],
        agent_id=row["agent_id"],
        type=row["type"],
        status=row["status"],
        title=row["title"],
        mime=row["mime"],
        storage_path=row["storage_path"],
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
        url=row["url"],
        url_expires_at=row["url_expires_at"],
    )


class PgArtifactRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_generating(
        self,
        workspace_id: UUID,
        *,
        task_id: UUID,
        agent_id: UUID,
        type: str,
        title: str,
        mime: str,
        source_spec: dict[str, Any],
    ) -> ArtifactRecord:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                insert into public.artifacts
                    (workspace_id, task_id, agent_id, type, title, mime, source_spec)
                values ($1, $2, $3, $4, $5, $6, $7)
                returning {_COLUMNS}
                """,
                workspace_id,
                task_id,
                agent_id,
                type,
                title,
                mime,
                source_spec,
            )
        assert row is not None
        return _to_record(row)

    async def mark_ready(
        self,
        artifact_id: UUID,
        *,
        storage_path: str,
        size_bytes: int,
        url: str,
        url_expires_at: datetime,
    ) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                update public.artifacts
                set status = 'ready', storage_path = $2, size_bytes = $3,
                    url = $4, url_expires_at = $5
                where id = $1
                """,
                artifact_id,
                storage_path,
                size_bytes,
                url,
                url_expires_at,
            )

    async def update_url(self, artifact_id: UUID, *, url: str, url_expires_at: datetime) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                "update public.artifacts set url = $2, url_expires_at = $3 where id = $1",
                artifact_id,
                url,
                url_expires_at,
            )

    async def mark_failed(self, artifact_id: UUID, error: dict[str, Any]) -> None:
        async with self._db.acquire() as conn:
            await conn.execute(
                "update public.artifacts set status = 'failed', error = $2 where id = $1",
                artifact_id,
                error,
            )

    async def get(self, workspace_id: UUID, artifact_id: UUID) -> ArtifactRecord | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"select {_COLUMNS} from public.artifacts where workspace_id = $1 and id = $2",
                workspace_id,
                artifact_id,
            )
        return _to_record(row) if row is not None else None

    async def ready_for_task(self, task_id: UUID) -> list[ArtifactRecord]:
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                select {_COLUMNS} from public.artifacts
                where task_id = $1 and status = 'ready'
                order by created_at, id
                """,
                task_id,
            )
        return [_to_record(row) for row in rows]
