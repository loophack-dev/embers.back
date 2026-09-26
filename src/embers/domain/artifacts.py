"""Artifact use cases: validate, generate, upload, mark ready/failed and sign URLs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError

from embers.artifacts.generators import MIME_TYPES, build_docx, build_markdown, build_pptx
from embers.artifacts.specs import ArtifactSpec, DocumentSpec, MarkdownSpec, PresentationSpec
from embers.contracts.common import ArtifactType
from embers.contracts.errors import ErrorCode
from embers.contracts.ws import ArtifactOut, ArtifactStatus
from embers.domain.ports import ArtifactRecord, ArtifactRepository, FileStorage
from embers.errors import ApiError

logger = logging.getLogger(__name__)

ArtifactKind = Literal["docx", "pptx", "md"]

_SPECS: dict[ArtifactKind, type[ArtifactSpec]] = {
    "docx": DocumentSpec,
    "pptx": PresentationSpec,
    "md": MarkdownSpec,
}


def _validation_message(exc: ValidationError) -> str:
    problems = [
        f"{'.'.join(str(part) for part in error['loc']) or 'input'}: {error['msg']}"
        for error in exc.errors()
    ]
    return "Error: invalid input, nothing was created. " + "; ".join(problems)


class ArtifactService:
    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        storage: FileStorage,
        workspace_id: UUID,
        signed_url_ttl_s: int,
        pptx_template_path: Path | None,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._workspace_id = workspace_id
        self._ttl_s = signed_url_ttl_s
        self._template = pptx_template_path

    async def create(
        self, kind: ArtifactKind, *, task_id: UUID, agent_id: UUID, raw: dict[str, Any]
    ) -> str:
        """Create a file for a task. Returns the message for the model (success or error)."""
        try:
            spec: ArtifactSpec = _SPECS[kind].model_validate(raw)
        except ValidationError as exc:
            return _validation_message(exc)

        title = spec.title
        record = await self._repo.create_generating(
            self._workspace_id,
            task_id=task_id,
            agent_id=agent_id,
            type=kind,
            title=title,
            mime=MIME_TYPES[kind],
            source_spec=spec.model_dump(mode="json"),
        )
        try:
            content = await asyncio.to_thread(self._builder(kind, spec))
            path = f"{self._workspace_id}/{task_id}/{record.id}.{kind}"
            await self._storage.upload(path, content, MIME_TYPES[kind])
            await self._repo.mark_ready(record.id, storage_path=path, size_bytes=len(content))
        except Exception as exc:
            logger.exception(
                "artifact generation failed", extra={"artifact_id": str(record.id), "type": kind}
            )
            await self._repo.mark_failed(
                record.id, {"code": "artifact_error", "message": type(exc).__name__}
            )
            return f"Error: the {kind} file could not be generated ({type(exc).__name__})."
        logger.info(
            "artifact ready",
            extra={"artifact_id": str(record.id), "type": kind, "task_id": str(task_id)},
        )
        return f"Created {kind} '{title}' (id {record.id})."

    def _builder(self, kind: ArtifactKind, spec: ArtifactSpec) -> Callable[[], bytes]:
        if isinstance(spec, DocumentSpec):
            return lambda: build_docx(spec)
        if isinstance(spec, PresentationSpec):
            return lambda: build_pptx(spec, self._template)
        if isinstance(spec, MarkdownSpec):
            return lambda: build_markdown(spec)
        raise ValueError(f"Unsupported artifact kind: {kind}")

    async def ready_for_task(self, task_id: UUID) -> list[ArtifactOut]:
        return [await self._to_out(record) for record in await self._repo.ready_for_task(task_id)]

    async def download_url(self, artifact_id: UUID) -> str:
        record = await self._repo.get(self._workspace_id, artifact_id)
        if record is None or record.status != ArtifactStatus.READY or not record.storage_path:
            raise ApiError(ErrorCode.NOT_FOUND, "Artifact not found.", status_code=404)
        return await self._sign(record)

    async def _sign(self, record: ArtifactRecord) -> str:
        assert record.storage_path is not None
        return await self._storage.signed_url(
            record.storage_path,
            expires_in_s=self._ttl_s,
            download_name=f"{record.title or record.id}.{record.type}",
        )

    async def _to_out(self, record: ArtifactRecord) -> ArtifactOut:
        signed_at = datetime.now(UTC)
        url = await self._sign(record)
        return ArtifactOut(
            id=record.id,
            task_id=record.task_id,
            agent_id=record.agent_id,
            title=record.title or "",
            type=ArtifactType(record.type),
            mime=record.mime or MIME_TYPES[record.type],
            status=ArtifactStatus(record.status),
            size_bytes=record.size_bytes,
            download_url=url,
            url_expires_at=signed_at + timedelta(seconds=self._ttl_s),
            created_at=record.created_at,
        )
