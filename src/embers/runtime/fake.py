"""Fake runtime (AGENT_RUNTIME=fake): fixed answers, no model calls."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from embers.domain.artifacts import ArtifactKind, ArtifactService
from embers.runtime.base import Completed, Interrupted, RunOutcome, RunRequest, Usage

QUESTION_TRIGGER = "pregunta"
FAKE_QUESTION = "¿Qué detalle quieres que tenga en cuenta?"
FAKE_OPTIONS = ["Formal", "Informal"]
FAKE_RESULT = "Tarea completada por el runtime falso."
FAKE_TITLE = "Entregable de prueba"
_KINDS: dict[str, ArtifactKind] = {"docx": "docx", "pptx": "pptx", "md": "md"}


def _minimal_spec(kind: str, instruction: str) -> dict[str, object]:
    if kind == "docx":
        return {
            "title": FAKE_TITLE,
            "sections": [{"heading": "Instrucción", "paragraphs": [instruction]}],
        }
    if kind == "pptx":
        return {
            "title": FAKE_TITLE,
            "slides": [{"title": "Instrucción", "bullets": [instruction[:4000]]}],
        }
    return {"title": FAKE_TITLE, "content": instruction}


class FakeRuntime:
    def __init__(self, delay_s: float, artifacts: ArtifactService) -> None:
        self._delay_s = delay_s
        self._artifacts = artifacts
        self._waiting: dict[UUID, RunRequest] = {}

    async def start(self, request: RunRequest) -> RunOutcome:
        await asyncio.sleep(self._delay_s)
        if QUESTION_TRIGGER in request.instruction.lower():
            self._waiting[request.task_id] = request
            return Interrupted(str(uuid4()), FAKE_QUESTION, list(FAKE_OPTIONS), Usage())
        await self._deliver_file(request)
        return Completed(FAKE_RESULT, Usage())

    async def resume(self, task_id: UUID, interrupt_id: str, answer: str) -> RunOutcome:
        request = self._waiting.pop(task_id, None)
        await asyncio.sleep(self._delay_s)
        if request is not None:
            await self._deliver_file(request)
        return Completed(f"{FAKE_RESULT} Respuesta recibida: {answer}", Usage())

    async def _deliver_file(self, request: RunRequest) -> None:
        """Plan B for the demo: produce the requested file type with the real file tools."""
        kind = _KINDS.get(request.expected_output or "")
        if kind is None:
            return
        await self._artifacts.create(
            kind,
            task_id=request.task_id,
            agent_id=request.agent_id,
            raw=_minimal_spec(kind, request.instruction),
        )

    def discard(self, task_id: UUID) -> None:
        self._waiting.pop(task_id, None)
