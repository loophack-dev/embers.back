"""Persistence port for agents. The domain depends on this Protocol; `db/` implements it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from embers.contracts.ws import ArtifactOut, AskData, FinishData


@dataclass(frozen=True)
class AgentRecord:
    """An agent row as stored, nulls included (see the phase 1 null rule)."""

    id: UUID
    name: str
    model_config: dict[str, Any]
    identity: dict[str, Any]
    instructions: str | None
    tools: list[str] | None
    status: str
    version: int
    appearance: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    character_status: str = "idle"


@dataclass(frozen=True)
class NewAgent:
    name: str
    model_config: dict[str, Any]
    identity: dict[str, Any]
    instructions: str | None
    tools: list[str] | None
    appearance: dict[str, Any] | None


@dataclass(frozen=True)
class AgentChanges:
    """Full set of editable columns after applying a partial update."""

    name: str
    model_config: dict[str, Any]
    identity: dict[str, Any]
    instructions: str | None
    tools: list[str] | None
    version: int


@dataclass(frozen=True)
class AgentOpenTasks:
    """Open tasks of an agent: the current one (working or waiting_user) and the queue."""

    current_task_id: UUID | None = None
    queued_task_ids: tuple[UUID, ...] = ()


class DuplicateAgentNameError(Exception):
    """Another active agent in the workspace already has this name."""


class AppearanceTooLargeError(Exception):
    """The stored appearance exceeds the database size limit."""


class AgentRepository(Protocol):
    async def create(self, workspace_id: UUID, agent: NewAgent) -> AgentRecord: ...

    async def get(self, workspace_id: UUID, agent_id: UUID) -> AgentRecord | None: ...

    async def list_agents(
        self, workspace_id: UUID, *, include_archived: bool
    ) -> list[AgentRecord]: ...

    async def update(
        self, workspace_id: UUID, agent_id: UUID, changes: AgentChanges
    ) -> AgentRecord: ...

    async def archive(self, workspace_id: UUID, agent_id: UUID) -> None: ...

    async def save_appearance(
        self, workspace_id: UUID, agent_id: UUID, data: dict[str, Any]
    ) -> AgentRecord: ...

    async def open_tasks(
        self, workspace_id: UUID, agent_ids: list[UUID]
    ) -> dict[UUID, AgentOpenTasks]: ...


# --- Tasks (phase 2) ---


@dataclass(frozen=True)
class TaskRecord:
    id: UUID
    agent_id: UUID
    instruction: str
    status: str
    expected_output: str | None
    agent_snapshot: dict[str, Any]
    result_text: str | None
    error: dict[str, Any] | None
    usage: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class QuestionRecord:
    id: UUID
    task_id: UUID
    question: str
    options: list[str] | None
    status: str
    interrupt_id: str | None


@dataclass(frozen=True)
class AcceptedAnswer:
    task: TaskRecord
    question: QuestionRecord


class QuestionNotFoundError(Exception):
    """The task or the question does not exist, or the question belongs to another task."""


class QuestionNotPendingError(Exception):
    """The question is not pending or the task is not waiting for the user."""


class TaskRepository(Protocol):
    async def create(
        self,
        workspace_id: UUID,
        *,
        agent_id: UUID,
        instruction: str,
        expected_output: str | None,
        agent_snapshot: dict[str, Any],
        status: str,
    ) -> TaskRecord: ...

    async def get(self, workspace_id: UUID, task_id: UUID) -> TaskRecord | None: ...

    async def mark_working(self, task_id: UUID) -> TaskRecord: ...

    async def ask(
        self,
        task_id: UUID,
        *,
        question: str,
        options: list[str] | None,
        interrupt_id: str | None,
        usage: dict[str, Any],
    ) -> QuestionRecord: ...

    async def accept_answer(
        self, workspace_id: UUID, *, task_id: UUID, question_id: UUID, answer: str
    ) -> AcceptedAnswer: ...

    async def finish(
        self,
        task_id: UUID,
        *,
        status: str,
        result_text: str | None,
        error: dict[str, Any] | None,
        usage: dict[str, Any],
    ) -> TaskRecord: ...

    async def expire_question(self, question_id: UUID) -> bool:
        """Mark a pending question as expired. False if it was no longer pending."""
        ...

    async def fail_open_tasks(self, workspace_id: UUID, error: dict[str, Any]) -> int: ...


class TaskNotifier(Protocol):
    """Delivers task messages to the front end (implemented by the realtime gateway)."""

    async def ask(self, task: TaskRecord, data: AskData) -> None: ...

    async def finish(self, task: TaskRecord, data: FinishData) -> None: ...


# --- Artifacts (phase 2) ---


@dataclass(frozen=True)
class ArtifactRecord:
    id: UUID
    task_id: UUID
    agent_id: UUID
    type: str
    status: str
    title: str | None
    mime: str | None
    storage_path: str | None
    size_bytes: int | None
    created_at: datetime


class ArtifactRepository(Protocol):
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
    ) -> ArtifactRecord: ...

    async def mark_ready(
        self, artifact_id: UUID, *, storage_path: str, size_bytes: int
    ) -> None: ...

    async def mark_failed(self, artifact_id: UUID, error: dict[str, Any]) -> None: ...

    async def get(self, workspace_id: UUID, artifact_id: UUID) -> ArtifactRecord | None: ...

    async def ready_for_task(self, task_id: UUID) -> list[ArtifactRecord]: ...


class FileStorage(Protocol):
    async def upload(self, path: str, content: bytes, mime: str) -> None: ...

    async def signed_url(self, path: str, *, expires_in_s: int, download_name: str) -> str: ...


class TaskArtifacts(Protocol):
    """Ready files of a task, with fresh signed URLs (used to build `finish`)."""

    async def ready_for_task(self, task_id: UUID) -> list[ArtifactOut]: ...
