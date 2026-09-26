"""HealthOut contract (docs section 4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProvidersHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anthropic: bool
    openai: bool
    gemini: bool


class HealthOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    db: bool
    storage: bool
    providers: ProvidersHealth
