"""Agent use cases and business rules for phase 1."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from embers.contracts.agents import (
    AgentCreate,
    AgentIdentity,
    AgentIdentityOut,
    AgentOut,
    AgentUpdate,
    AppearanceUpdate,
    ModelConfig,
    ModelConfigOut,
    ModelParamsOut,
)
from embers.contracts.common import AgentRecordStatus, CharacterStatus
from embers.contracts.errors import ErrorCode
from embers.domain.catalogs import DEFAULT_TOOL_IDS, TOOL_IDS, ProviderCatalog
from embers.domain.ports import (
    AgentChanges,
    AgentOpenTasks,
    AgentRecord,
    AgentRepository,
    AppearanceTooLargeError,
    DuplicateAgentNameError,
    NewAgent,
)
from embers.errors import ApiError
from embers.events.bus import Event, EventBus

MAX_APPEARANCE_BYTES = 64 * 1024


def validation_error(field: str, reason: str) -> ApiError:
    return ApiError(
        ErrorCode.VALIDATION_ERROR,
        "The request did not pass validation.",
        status_code=422,
        details={"fields": [{"field": field, "reason": reason}]},
    )


def to_agent_out(record: AgentRecord, open_tasks: AgentOpenTasks | None = None) -> AgentOut:
    """Convert a stored agent to the contract shape, applying the null rule.

    `character_status` comes from the database (kept by a trigger on tasks); `open_tasks`
    provides the current and queued task ids.
    """
    tasks = open_tasks or AgentOpenTasks()
    params: dict[str, Any] | None = record.model_config.get("params") or None
    return AgentOut(
        id=record.id,
        name=record.name,
        model_cfg=ModelConfigOut(
            provider=record.model_config["provider"],
            model_id=record.model_config["model_id"],
            params=ModelParamsOut(
                temperature=params.get("temperature"),
                max_tokens=params.get("max_tokens"),
                top_p=params.get("top_p"),
            )
            if params is not None
            else None,
        ),
        identity=AgentIdentityOut(
            role=record.identity["role"],
            persona=record.identity.get("persona"),
            tone=record.identity.get("tone"),
        ),
        instructions=record.instructions or "",
        tools=record.tools or [],
        status=AgentRecordStatus(record.status),
        version=record.version,
        appearance=record.appearance or {},
        character_status=CharacterStatus(record.character_status),
        current_task_id=tasks.current_task_id,
        queued_task_ids=list(tasks.queued_task_ids),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _store_model_config(model_config: ModelConfig) -> dict[str, Any]:
    stored = model_config.model_dump(mode="json", exclude_none=True)
    if not stored.get("params"):
        stored.pop("params", None)
    return stored


def _store_identity(identity: AgentIdentity) -> dict[str, Any]:
    return identity.model_dump(mode="json", exclude_none=True)


def _store_instructions(instructions: str | None) -> str | None:
    return instructions or None


def _dedupe(tools: list[str]) -> list[str]:
    return list(dict.fromkeys(tools))


def _appearance_size(data: dict[str, Any]) -> int:
    # Default separators match Postgres' jsonb text output, so the DB check agrees.
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        providers: ProviderCatalog,
        bus: EventBus,
        workspace_id: UUID,
    ) -> None:
        self._repo = repository
        self._providers = providers
        self._bus = bus
        self._workspace_id = workspace_id

    async def create(self, body: AgentCreate) -> AgentOut:
        self._check_model(body.model_cfg)
        tools = _dedupe(body.tools) if "tools" in body.model_fields_set else list(DEFAULT_TOOL_IDS)
        self._check_tools(tools)
        if body.appearance is not None:
            self._check_appearance_size(body.appearance, "appearance")

        new_agent = NewAgent(
            name=body.name,
            model_config=_store_model_config(body.model_cfg),
            identity=_store_identity(body.identity),
            instructions=_store_instructions(body.instructions),
            tools=tools,
            appearance=body.appearance,
        )
        try:
            record = await self._repo.create(self._workspace_id, new_agent)
        except DuplicateAgentNameError:
            raise self._duplicate_name(body.name) from None
        except AppearanceTooLargeError:
            raise validation_error("appearance", "Appearance exceeds 64 KB.") from None

        agent = to_agent_out(record)
        await self._publish("agent.created", agent.id, {"agent": _dump(agent)})
        return agent

    async def list_agents(self, *, include_archived: bool) -> list[AgentOut]:
        records = await self._repo.list_agents(
            self._workspace_id, include_archived=include_archived
        )
        open_tasks = await self._repo.open_tasks(self._workspace_id, [r.id for r in records])
        return [to_agent_out(record, open_tasks.get(record.id)) for record in records]

    async def get(self, agent_id: UUID) -> AgentOut:
        return await self._out(await self._get_record(agent_id))

    async def update(self, agent_id: UUID, body: AgentUpdate) -> AgentOut:
        record = await self._get_record(agent_id)
        self._ensure_active(record)
        sent = body.model_fields_set

        name = body.name if "name" in sent and body.name is not None else record.name
        model_config = record.model_config
        if "model_cfg" in sent and body.model_cfg is not None:
            self._check_model(body.model_cfg)
            model_config = _store_model_config(body.model_cfg)
        identity = record.identity
        if "identity" in sent and body.identity is not None:
            identity = _store_identity(body.identity)
        instructions = record.instructions
        if "instructions" in sent:
            instructions = _store_instructions(body.instructions)
        tools = record.tools
        if "tools" in sent:
            tools = _dedupe(body.tools) if body.tools is not None else None
            self._check_tools(tools or [])

        before = await self._out(record)
        candidate = to_agent_out(
            AgentRecord(
                id=record.id,
                name=name,
                model_config=model_config,
                identity=identity,
                instructions=instructions,
                tools=tools,
                status=record.status,
                version=record.version,
                appearance=record.appearance,
                created_at=record.created_at,
                updated_at=record.updated_at,
                character_status=record.character_status,
            )
        )
        versioned_change = (
            candidate.model_cfg != before.model_cfg
            or candidate.identity != before.identity
            or candidate.instructions != before.instructions
            or candidate.tools != before.tools
        )
        if not versioned_change and candidate.name == before.name:
            return before

        changes = AgentChanges(
            name=name,
            model_config=model_config,
            identity=identity,
            instructions=instructions,
            tools=tools,
            version=record.version + 1 if versioned_change else record.version,
        )
        try:
            updated = await self._repo.update(self._workspace_id, agent_id, changes)
        except DuplicateAgentNameError:
            raise self._duplicate_name(name) from None

        agent = await self._out(updated)
        await self._publish("agent.updated", agent.id, {"agent": _dump(agent)})
        return agent

    async def set_appearance(self, agent_id: UUID, body: AppearanceUpdate) -> AgentOut:
        record = await self._get_record(agent_id)
        self._ensure_active(record)
        self._check_appearance_size(body.data, "data")
        try:
            updated = await self._repo.save_appearance(self._workspace_id, agent_id, body.data)
        except AppearanceTooLargeError:
            raise validation_error("data", "Appearance exceeds 64 KB.") from None

        agent = await self._out(updated)
        await self._publish("agent.updated", agent.id, {"agent": _dump(agent)})
        return agent

    async def archive(self, agent_id: UUID) -> None:
        record = await self._get_record(agent_id)
        if record.status == AgentRecordStatus.ARCHIVED:
            return
        await self._repo.archive(self._workspace_id, agent_id)
        await self._publish("agent.archived", agent_id, {"agent_id": str(agent_id)})

    async def _out(self, record: AgentRecord) -> AgentOut:
        open_tasks = await self._repo.open_tasks(self._workspace_id, [record.id])
        return to_agent_out(record, open_tasks.get(record.id))

    # --- rules ---

    async def _get_record(self, agent_id: UUID) -> AgentRecord:
        record = await self._repo.get(self._workspace_id, agent_id)
        if record is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Agent not found.", status_code=404)
        return record

    @staticmethod
    def _ensure_active(record: AgentRecord) -> None:
        if record.status == AgentRecordStatus.ARCHIVED:
            raise ApiError(
                ErrorCode.AGENT_ARCHIVED,
                "The agent is archived and cannot be edited.",
                status_code=409,
            )

    def _check_model(self, model_config: ModelConfig) -> None:
        if not self._providers.has_model(model_config.provider, model_config.model_id):
            raise validation_error(
                "model_config.model_id",
                f"Model '{model_config.model_id}' is not in the catalog of provider "
                f"'{model_config.provider}'.",
            )

    @staticmethod
    def _check_tools(tools: list[str]) -> None:
        unknown = [tool for tool in tools if tool not in TOOL_IDS]
        if unknown:
            raise ApiError(
                ErrorCode.UNKNOWN_TOOL,
                "One or more tools do not exist.",
                status_code=422,
                details={
                    "fields": [{"field": "tools", "reason": f"Unknown tools: {', '.join(unknown)}"}]
                },
            )

    @staticmethod
    def _check_appearance_size(data: dict[str, Any], field: str) -> None:
        if _appearance_size(data) > MAX_APPEARANCE_BYTES:
            raise validation_error(field, "Appearance exceeds 64 KB.")

    @staticmethod
    def _duplicate_name(name: str) -> ApiError:
        return validation_error("name", f"An active agent named '{name}' already exists.")

    async def _publish(self, event_type: str, agent_id: UUID, data: dict[str, Any]) -> None:
        await self._bus.publish(
            Event(
                type=event_type,
                ts=datetime.now(UTC),
                agent_id=agent_id,
                task_id=None,
                data=data,
            )
        )


def _dump(agent: AgentOut) -> dict[str, Any]:
    return agent.model_dump(mode="json", by_alias=True)
