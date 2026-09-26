"""Application factory and ASGI entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from embers.api.errors import register_exception_handlers
from embers.api.routes import agents, artifacts, catalogs, health, ws
from embers.config import Settings, get_settings
from embers.db.agents_repository import PgAgentRepository
from embers.db.artifacts_repository import PgArtifactRepository
from embers.db.pool import Database
from embers.db.task_events_repository import PgTaskEventsRepository
from embers.db.tasks_repository import PgTaskRepository
from embers.domain.artifacts import ArtifactService
from embers.domain.catalogs import ProviderCatalog
from embers.domain.tasks import TaskLimits, TaskService, TaskSupervisor
from embers.events.bus import EventBus
from embers.events.log_subscriber import LogSubscriber
from embers.events.task_events_subscriber import TaskEventsSubscriber
from embers.logging import configure_logging
from embers.realtime.connections import ConnectionRegistry
from embers.realtime.outbox import Outbox
from embers.runtime.factory import build_runtime
from embers.storage.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings.database_url)
        await db.open()
        workspace_id = settings.default_workspace_id
        events = PgTaskEventsRepository(db, workspace_id)
        bus = EventBus()
        bus.subscribe(LogSubscriber())
        bus.subscribe(TaskEventsSubscriber(events))
        connections = ConnectionRegistry()
        outbox = Outbox(events, connections)
        http = httpx.AsyncClient()
        artifact_service = ArtifactService(
            repository=PgArtifactRepository(db),
            storage=SupabaseStorage(
                http,
                base_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key.get_secret_value(),
                bucket=settings.artifacts_bucket,
            ),
            workspace_id=workspace_id,
            signed_url_ttl_s=settings.signed_url_ttl_s,
            stored_url_ttl_s=settings.artifact_url_ttl_s,
            pptx_template_path=settings.pptx_template_path,
        )
        runtime = build_runtime(settings, artifact_service)
        supervisor = TaskSupervisor()
        task_service = TaskService(
            tasks=PgTaskRepository(db),
            agents=PgAgentRepository(db),
            runtime=runtime,
            notifier=outbox,
            supervisor=supervisor,
            workspace_id=workspace_id,
            # The fake runtime never calls a provider, so it does not need API keys.
            provider_available=(
                (lambda _provider: True)
                if settings.agent_runtime == "fake"
                else settings.has_provider_key
            ),
            limits=TaskLimits(
                task_timeout_s=settings.task_timeout_s, ask_timeout_s=settings.ask_timeout_s
            ),
            artifacts=artifact_service,
        )
        app.state.artifacts = artifact_service
        app.state.connections = connections
        app.state.outbox = outbox
        app.state.task_service = task_service
        try:
            recovered = await task_service.recover()
            if recovered:
                logger.warning(
                    "failed tasks left open by a previous run", extra={"count": recovered}
                )
        except Exception:
            logger.exception("could not recover open tasks; database unavailable?")
        app.state.settings = settings
        app.state.providers = ProviderCatalog.from_yaml(settings.providers_file)
        app.state.db = db
        app.state.bus = bus
        app.state.http = http
        logger.info(
            "application started",
            extra={
                "default_workspace_id": str(settings.default_workspace_id),
                "cors_origins": settings.cors_origins,
                "agent_runtime": settings.agent_runtime,
            },
        )
        try:
            yield
        finally:
            await supervisor.shutdown()
            await app.state.http.aclose()
            await db.close()
            logger.info("application stopped")

    app = FastAPI(title="Embers", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(catalogs.router)
    app.include_router(agents.router)
    app.include_router(ws.router)
    app.include_router(artifacts.router)
    return app
