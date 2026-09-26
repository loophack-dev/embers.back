"""ProviderOut, ProviderModelOut and ToolOut contracts (docs section 4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from embers.contracts.common import ArtifactType, Provider


class ProviderModelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class ProviderOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Provider
    available: bool
    models: list[ProviderModelOut]


class ToolOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    artifact_type: ArtifactType | None
