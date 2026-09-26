"""GET /artifacts/{id}/download: redirect to a fresh signed URL."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import RedirectResponse

from embers.domain.artifacts import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{id}/download", status_code=status.HTTP_302_FOUND)
async def download_artifact(
    request: Request, artifact_id: Annotated[UUID, Path(alias="id")]
) -> RedirectResponse:
    service: ArtifactService = request.app.state.artifacts
    url = await service.download_url(artifact_id)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
