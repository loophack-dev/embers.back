"""FastAPI dependencies resolved from `app.state`, set up in the app lifespan."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends, Request

from embers.config import Settings
from embers.db.agents_repository import PgAgentRepository
from embers.db.pool import Database
from embers.domain.agents import AgentService
from embers.domain.catalogs import ProviderCatalog
from embers.events.bus import EventBus


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_http(request: Request) -> httpx.AsyncClient:
    http: httpx.AsyncClient = request.app.state.http
    return http


def get_bus(request: Request) -> EventBus:
    bus: EventBus = request.app.state.bus
    return bus


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[Database, Depends(get_db)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]
EventBusDep = Annotated[EventBus, Depends(get_bus)]


def get_providers(request: Request) -> ProviderCatalog:
    providers: ProviderCatalog = request.app.state.providers
    return providers


ProvidersDep = Annotated[ProviderCatalog, Depends(get_providers)]


def get_agent_service(
    db: DatabaseDep, bus: EventBusDep, providers: ProvidersDep, settings: SettingsDep
) -> AgentService:
    return AgentService(
        PgAgentRepository(db), providers, bus, workspace_id=settings.default_workspace_id
    )


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
