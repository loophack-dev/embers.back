"""Shared enums and wrappers from the official contract (docs sections 1 and 4)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Provider(StrEnum):
    """Model providers. `bedrock` is intentionally excluded (approved deviation)."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


class AgentRecordStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CharacterStatus(StrEnum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"


class ArtifactType(StrEnum):
    DOCX = "docx"
    PPTX = "pptx"
    MD = "md"


class ItemsOut[T](BaseModel):
    """Every list response has the shape `{ "items": [...] }`."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
