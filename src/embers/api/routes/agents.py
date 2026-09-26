"""Agent CRUD endpoints. Business rules live in `domain.agents.AgentService`."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Response, status

from embers.api.deps import AgentServiceDep
from embers.contracts.agents import AgentCreate, AgentOut, AgentUpdate, AppearanceUpdate
from embers.contracts.common import ItemsOut

router = APIRouter(prefix="/agents", tags=["agents"])

AgentId = Annotated[UUID, Path(alias="id")]


@router.get("", response_model=ItemsOut[AgentOut])
async def list_agents(
    service: AgentServiceDep, include_archived: bool = False
) -> ItemsOut[AgentOut]:
    return ItemsOut[AgentOut](items=await service.list_agents(include_archived=include_archived))


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, service: AgentServiceDep) -> AgentOut:
    return await service.create(body)


@router.get("/{id}", response_model=AgentOut)
async def get_agent(agent_id: AgentId, service: AgentServiceDep) -> AgentOut:
    return await service.get(agent_id)


@router.patch("/{id}", response_model=AgentOut)
async def update_agent(agent_id: AgentId, body: AgentUpdate, service: AgentServiceDep) -> AgentOut:
    return await service.update(agent_id, body)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_agent(agent_id: AgentId, service: AgentServiceDep) -> Response:
    await service.archive(agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{id}/appearance", response_model=AgentOut)
async def set_appearance(
    agent_id: AgentId, body: AppearanceUpdate, service: AgentServiceDep
) -> AgentOut:
    return await service.set_appearance(agent_id, body)
