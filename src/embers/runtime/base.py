"""Agent runtime interface. Nothing outside `runtime/` depends on a concrete engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class RunRequest:
    task_id: UUID
    agent_id: UUID
    agent_snapshot: dict[str, Any]
    instruction: str
    expected_output: str | None


@dataclass(frozen=True)
class Completed:
    """The agent finished. `usage` is the consumption of this step only."""

    text: str | None
    usage: Usage


@dataclass(frozen=True)
class Interrupted:
    """The agent paused to ask the person. Resume with `AgentRuntime.resume`."""

    interrupt_id: str
    question: str
    options: list[str] | None
    usage: Usage


RunOutcome = Completed | Interrupted


class AgentRuntime(Protocol):
    async def start(self, request: RunRequest) -> RunOutcome: ...

    async def resume(self, task_id: UUID, interrupt_id: str, answer: str) -> RunOutcome: ...

    def discard(self, task_id: UUID) -> None:
        """Release the in-memory agent instance of a finished task."""
        ...


class ModelProviderError(Exception):
    """The model provider returned an error. The message never includes response bodies or keys."""
