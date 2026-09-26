"""Builds the agent runtime selected by AGENT_RUNTIME."""

from __future__ import annotations

from embers.config import Settings
from embers.domain.artifacts import ArtifactService
from embers.runtime.base import AgentRuntime
from embers.runtime.fake import FakeRuntime


def build_runtime(settings: Settings, artifacts: ArtifactService) -> AgentRuntime:
    if settings.agent_runtime == "fake":
        return FakeRuntime(settings.fake_runtime_delay_s, artifacts)
    if settings.agent_runtime == "strands":
        # Imported lazily so the fake runtime does not load the provider SDKs.
        from embers.runtime.strands_runtime import StrandsRuntime

        return StrandsRuntime(settings, artifacts)
    raise ValueError(f"Unsupported AGENT_RUNTIME: {settings.agent_runtime}")
