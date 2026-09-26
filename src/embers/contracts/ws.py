"""WebSocket contracts (docs section 5): envelopes and message data."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from embers.contracts.common import ArtifactType
from embers.contracts.errors import ErrorCode


class TaskStatus(StrEnum):
    QUEUED = "queued"
    WORKING = "working"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ArtifactStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


# --- Client -> server ---


class ClientMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delegate", "answer"]
    request_id: Annotated[str, Field(min_length=1, max_length=64)]
    data: dict[str, Any]


class DelegateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    instruction: Annotated[str, Field(min_length=1, max_length=4000)]
    expected_output: ArtifactType | None = None


class AnswerData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    question_id: UUID
    answer: Annotated[str, Field(min_length=1, max_length=2000)]


# --- Server -> client ---


class ServerMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["ack", "error", "ask", "finish"]
    event_id: int
    ts: datetime
    agent_id: UUID | None
    task_id: UUID | None
    request_id: str | None
    data: dict[str, Any]


class AckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    status: Literal[TaskStatus.WORKING, TaskStatus.QUEUED]


class AskData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    question: Annotated[str, Field(min_length=1, max_length=1000)]
    options: Annotated[list[str], Field(max_length=6)] | None


class TaskError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    retryable: bool = False


class TaskUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_id: str | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    task_id: UUID
    agent_id: UUID
    title: str
    type: ArtifactType
    mime: str
    status: ArtifactStatus
    size_bytes: int | None
    download_url: str | None
    url_expires_at: datetime | None
    created_at: datetime


class FinishData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[TaskStatus.COMPLETED, TaskStatus.FAILED]
    result_text: str | None
    artifacts: list[ArtifactOut]
    error: TaskError | None
    usage: TaskUsage
