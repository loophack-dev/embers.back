"""Agent contracts: AgentCreate, AgentUpdate, AgentOut and AppearanceUpdate (docs section 4).

`model_config` is reserved by Pydantic, so the field is declared as `model_cfg`
with the JSON alias `model_config`. FastAPI serializes responses by alias.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from embers.contracts.common import AgentRecordStatus, CharacterStatus, Provider

AgentName = Annotated[str, Field(min_length=1, max_length=60)]
Instructions = Annotated[str, Field(max_length=8000)]


# --- Value objects (input) ---


class ModelParams(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    max_tokens: Annotated[int, Field(ge=256, le=64000)] | None = None
    top_p: Annotated[float, Field(gt=0, le=1)] | None = None


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    provider: Provider
    model_id: Annotated[str, Field(min_length=1, max_length=120)]
    params: ModelParams | None = None


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    role: Annotated[str, Field(min_length=1, max_length=80)]
    persona: Annotated[str, Field(max_length=600)] | None = None
    tone: Annotated[str, Field(max_length=120)] | None = None


# --- Requests ---


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    name: AgentName
    model_cfg: ModelConfig = Field(alias="model_config")
    identity: AgentIdentity
    instructions: Instructions = ""
    # When omitted, the service assigns the demo tools; see `model_fields_set`.
    tools: list[str] = Field(default_factory=list)
    appearance: dict[str, Any] | None = None


class AgentUpdate(BaseModel):
    """Partial update: only fields present in `model_fields_set` change."""

    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    name: AgentName | None = None
    model_cfg: ModelConfig | None = Field(default=None, alias="model_config")
    identity: AgentIdentity | None = None
    instructions: Instructions | None = None
    tools: list[str] | None = None

    @field_validator("name", "model_cfg", "identity", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        # Only runs for fields actually sent; defaults are not validated.
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class AppearanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    data: dict[str, Any]


# --- Responses ---


class ModelParamsOut(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    temperature: float | None
    max_tokens: int | None
    top_p: float | None


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    provider: Provider
    model_id: str
    params: ModelParamsOut | None


class AgentIdentityOut(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    role: str
    persona: str | None
    tone: str | None


class AgentOut(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True)

    id: UUID
    name: str
    model_cfg: ModelConfigOut = Field(alias="model_config")
    identity: AgentIdentityOut
    instructions: str
    tools: list[str]
    status: AgentRecordStatus
    version: int
    appearance: dict[str, Any]
    character_status: CharacterStatus
    current_task_id: UUID | None
    queued_task_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
