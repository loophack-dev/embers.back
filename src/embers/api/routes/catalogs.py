"""GET /providers and GET /tools."""

from __future__ import annotations

from fastapi import APIRouter

from embers.api.deps import ProvidersDep, SettingsDep
from embers.contracts.catalogs import ProviderModelOut, ProviderOut, ToolOut
from embers.contracts.common import ItemsOut
from embers.domain.catalogs import TOOL_CATALOG

router = APIRouter(tags=["catalogs"])


@router.get("/providers", response_model=ItemsOut[ProviderOut])
async def list_providers(providers: ProvidersDep, settings: SettingsDep) -> ItemsOut[ProviderOut]:
    return ItemsOut[ProviderOut](
        items=[
            ProviderOut(
                provider=entry.provider,
                available=settings.has_provider_key(entry.provider),
                models=[ProviderModelOut(id=m.id, label=m.label) for m in entry.models],
            )
            for entry in providers.entries
        ]
    )


@router.get("/tools", response_model=ItemsOut[ToolOut])
async def list_tools() -> ItemsOut[ToolOut]:
    return ItemsOut[ToolOut](
        items=[
            ToolOut(id=tool.id, description=tool.description, artifact_type=tool.artifact_type)
            for tool in TOOL_CATALOG
        ]
    )
