"""GET /health: database, Storage and provider key status."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter

from embers.api.deps import DatabaseDep, HttpDep, SettingsDep
from embers.config import Settings
from embers.contracts.health import HealthOut, ProvidersHealth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

STORAGE_TIMEOUT_SECONDS = 2.0


async def _check_storage(http: httpx.AsyncClient, settings: Settings) -> bool:
    key = settings.supabase_service_role_key.get_secret_value()
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/bucket"
    try:
        response = await http.get(
            url,
            headers={"Authorization": f"Bearer {key}", "apikey": key},
            timeout=STORAGE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        logger.warning("storage health check failed", exc_info=True)
        return False
    return response.is_success


@router.get("/health", response_model=HealthOut)
async def health(db: DatabaseDep, http: HttpDep, settings: SettingsDep) -> HealthOut:
    db_ok, storage_ok = await asyncio.gather(db.ping(), _check_storage(http, settings))
    return HealthOut(
        status="ok" if db_ok else "degraded",
        db=db_ok,
        storage=storage_ok,
        providers=ProvidersHealth(
            anthropic=settings.has_provider_key("anthropic"),
            openai=settings.has_provider_key("openai"),
            gemini=settings.has_provider_key("gemini"),
        ),
    )
