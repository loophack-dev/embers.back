"""asyncpg implementation of TaskRepository. All SQL is parametrized."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from embers.db.pool import Database
from embers.domain.ports import (
    AcceptedAnswer,
    QuestionNotFoundError,
    QuestionNotPendingError,
    QuestionRecord,
    TaskRecord,
)

_TASK_COLUMNS = """
id, agent_id, instruction, status, expected_output, agent_snapshot, result_text,
error, usage, created_at, started_at, finished_at
"""

_QUESTION_COLUMNS = "id, task_id, question, options, status, interrupt_id"


def _to_task(row: asyncpg.Record) -> TaskRecord:
    return TaskRecord(
        id=row["id"],
        agent_id=row["agent_id"],
        instruction=row["instruction"],
        status=row["status"],
        expected_output=row["expected_output"],
        agent_snapshot=row["agent_snapshot"],
        result_text=row["result_text"],
        error=row["error"],
        usage=row["usage"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _to_question(row: asyncpg.Record) -> QuestionRecord:
    return QuestionRecord(
        id=row["id"],
        task_id=row["task_id"],
        question=row["question"],
        options=row["options"],
        status=row["status"],
        interrupt_id=row["interrupt_id"],
    )


class PgTaskRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID,
        instruction: str,
        expected_output: str | None,
        agent_snapshot: dict[str, Any],
        status: str,
    ) -> TaskRecord:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                insert into public.tasks
                    (workspace_id, agent_id, instruction, expected_output, agent_snapshot, status)
                values ($1, $2, $3, $4, $5, $6)
                returning {_TASK_COLUMNS}
                """,
                workspace_id,
                agent_id,
                instruction,
                expected_output,
                agent_snapshot,
                status,
            )
        assert row is not None
        return _to_task(row)

    async def get(self, workspace_id: UUID, task_id: UUID) -> TaskRecord | None:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"select {_TASK_COLUMNS} from public.tasks where workspace_id = $1 and id = $2",
                workspace_id,
                task_id,
            )
        return _to_task(row) if row is not None else None

    async def mark_working(self, task_id: UUID) -> TaskRecord:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                update public.tasks
                set status = 'working', started_at = coalesce(started_at, now())
                where id = $1
                returning {_TASK_COLUMNS}
                """,
                task_id,
            )
        assert row is not None
        return _to_task(row)

    async def ask(
        self,
        task_id: UUID,
        *,
        question: str,
        options: list[str] | None,
        interrupt_id: str | None,
        usage: dict[str, Any],
    ) -> QuestionRecord:
        async with self._db.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                f"""
                insert into public.task_questions (task_id, question, options, interrupt_id)
                values ($1, $2, $3, $4)
                returning {_QUESTION_COLUMNS}
                """,
                task_id,
                question,
                options,
                interrupt_id,
            )
            await conn.execute(
                "update public.tasks set status = 'waiting_user', usage = $2 where id = $1",
                task_id,
                usage,
            )
        assert row is not None
        return _to_question(row)

    async def accept_answer(
        self, workspace_id: UUID, *, task_id: UUID, question_id: UUID, answer: str
    ) -> AcceptedAnswer:
        async with self._db.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                select q.task_id, q.status as question_status, t.status as task_status
                from public.task_questions q
                join public.tasks t on t.id = q.task_id
                where q.id = $1 and t.workspace_id = $2
                for update of q, t
                """,
                question_id,
                workspace_id,
            )
            if row is None or row["task_id"] != task_id:
                raise QuestionNotFoundError
            if row["question_status"] != "pending" or row["task_status"] != "waiting_user":
                raise QuestionNotPendingError
            question_row = await conn.fetchrow(
                f"""
                update public.task_questions
                set status = 'answered', answer = $2, answered_at = now()
                where id = $1
                returning {_QUESTION_COLUMNS}
                """,
                question_id,
                answer,
            )
            task_row = await conn.fetchrow(
                f"""
                update public.tasks set status = 'working'
                where id = $1
                returning {_TASK_COLUMNS}
                """,
                task_id,
            )
        assert question_row is not None and task_row is not None
        return AcceptedAnswer(task=_to_task(task_row), question=_to_question(question_row))

    async def finish(
        self,
        task_id: UUID,
        *,
        status: str,
        result_text: str | None,
        error: dict[str, Any] | None,
        usage: dict[str, Any],
    ) -> TaskRecord:
        async with self._db.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                update public.task_questions set status = 'expired'
                where task_id = $1 and status = 'pending'
                """,
                task_id,
            )
            row = await conn.fetchrow(
                f"""
                update public.tasks
                set status = $2, result_text = $3, error = $4, usage = $5, finished_at = now()
                where id = $1
                returning {_TASK_COLUMNS}
                """,
                task_id,
                status,
                result_text,
                error,
                usage,
            )
        assert row is not None
        return _to_task(row)

    async def expire_question(self, question_id: UUID) -> bool:
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                update public.task_questions set status = 'expired'
                where id = $1 and status = 'pending'
                returning id
                """,
                question_id,
            )
        return row is not None

    async def fail_open_tasks(self, workspace_id: UUID, error: dict[str, Any]) -> int:
        async with self._db.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                update public.task_questions q set status = 'expired'
                from public.tasks t
                where q.task_id = t.id and t.workspace_id = $1 and q.status = 'pending'
                """,
                workspace_id,
            )
            result = await conn.execute(
                """
                update public.tasks
                set status = 'failed', error = $2, finished_at = now()
                where workspace_id = $1 and status in ('queued', 'working', 'waiting_user')
                """,
                workspace_id,
                error,
            )
        return int(result.split()[-1])
