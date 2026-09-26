"""Contract models for REST and WebSocket error bodies (docs section 6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    AGENT_ARCHIVED = "agent_archived"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN_TOOL = "unknown_tool"
    TASK_NOT_CANCELABLE = "task_not_cancelable"
    QUESTION_NOT_PENDING = "question_not_pending"
    UNKNOWN_COMMAND = "unknown_command"
    MODEL_ERROR = "model_error"
    TIMEOUT = "timeout"
    ARTIFACT_ERROR = "artifact_error"
    INTERNAL_ERROR = "internal_error"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
