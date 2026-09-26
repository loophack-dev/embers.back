"""Subscriber that writes every published event to the log."""

from __future__ import annotations

import logging
from typing import Any

from embers.events.bus import Event


class LogSubscriber:
    """Logs the full event envelope as JSON, redacting long agent instructions."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("embers.events")

    async def __call__(self, event: Event) -> None:
        payload = event.model_dump(mode="json")
        _redact_agent_instructions(payload.get("data"))
        self._logger.info("event", extra={"event": payload})


def _redact_agent_instructions(data: Any) -> None:
    if not isinstance(data, dict):
        return
    agent = data.get("agent")
    if not isinstance(agent, dict):
        return
    instructions = agent.get("instructions")
    if isinstance(instructions, str):
        agent["instructions"] = f"[redacted len={len(instructions)}]"
