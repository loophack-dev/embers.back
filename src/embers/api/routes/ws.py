"""WebSocket gateway `/ws`: delegate and answer in; ack, error, ask and finish out."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from embers.contracts.errors import ErrorBody, ErrorCode
from embers.contracts.ws import AnswerData, ClientMessage, DelegateData
from embers.domain.tasks import TaskService, preview
from embers.errors import ApiError
from embers.realtime.connections import Connection, ConnectionRegistry
from embers.realtime.outbox import Outbox

logger = logging.getLogger(__name__)

router = APIRouter()

KNOWN_TYPES = ("delegate", "answer")


def _validation_details(exc: ValidationError) -> dict[str, Any]:
    fields = [
        {
            "field": ".".join(str(part) for part in error["loc"]) or "data",
            "reason": str(error["msg"]).removeprefix("Value error, "),
        }
        for error in exc.errors()
    ]
    return {"fields": fields}


class _Gateway:
    def __init__(self, websocket: WebSocket, connection: Connection) -> None:
        state = websocket.app.state
        self.outbox: Outbox = state.outbox
        self.tasks: TaskService = state.task_service
        self.connection = connection

    async def handle(self, raw: str) -> None:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            await self.outbox.record_unreadable(raw)
            await self._error(None, ErrorCode.UNKNOWN_COMMAND, "Message is not valid JSON.")
            return
        if not isinstance(parsed, dict):
            await self.outbox.record_unreadable(raw)
            await self._error(None, ErrorCode.UNKNOWN_COMMAND, "Message must be a JSON object.")
            return

        type_ = parsed.get("type")
        request_id = parsed.get("request_id") if isinstance(parsed.get("request_id"), str) else None
        raw_data = parsed.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}

        if type_ not in KNOWN_TYPES:
            await self._record_in(str(type_ or "unknown"), request_id, data)
            await self._error(
                request_id, ErrorCode.UNKNOWN_COMMAND, f"Unknown message type: {type_}."
            )
            return

        try:
            message = ClientMessage.model_validate(parsed)
            if message.type == "delegate":
                await self._delegate(message.request_id, DelegateData.model_validate(message.data))
            else:
                await self._answer(message.request_id, AnswerData.model_validate(message.data))
        except ValidationError as exc:
            await self._record_in(str(type_), request_id, data)
            await self._error(
                request_id,
                ErrorCode.VALIDATION_ERROR,
                "The message did not pass validation.",
                _validation_details(exc),
            )
        except ApiError as exc:
            await self._record_in(str(type_), request_id, data)
            await self._error(request_id, exc.code, exc.message, exc.details)

    async def _delegate(self, request_id: str, data: DelegateData) -> None:
        task = await self.tasks.create_task(data)
        await self.outbox.record_incoming(
            type="delegate",
            request_id=request_id,
            agent_id=task.agent_id,
            task_id=task.id,
            data=data.model_dump(mode="json"),
        )
        logger.info(
            "task delegated",
            extra={"task_id": str(task.id), "instruction": preview(data.instruction)},
        )
        await self.outbox.send(
            self.connection,
            "ack",
            request_id=request_id,
            agent_id=task.agent_id,
            task_id=task.id,
            data=self.tasks.ack_for(task),
        )
        self.tasks.start(task)

    async def _answer(self, request_id: str, data: AnswerData) -> None:
        task, interrupt_id = await self.tasks.accept_answer(data)
        await self.outbox.record_incoming(
            type="answer",
            request_id=request_id,
            agent_id=task.agent_id,
            task_id=task.id,
            data=data.model_dump(mode="json"),
        )
        await self.outbox.send(
            self.connection,
            "ack",
            request_id=request_id,
            agent_id=task.agent_id,
            task_id=task.id,
            data=self.tasks.ack_for(task),
        )
        self.tasks.resume(task, interrupt_id, data.answer)

    async def _record_in(self, type_: str, request_id: str | None, data: dict[str, Any]) -> None:
        await self.outbox.record_incoming(
            type=type_, request_id=request_id, agent_id=None, task_id=None, data=data
        )

    async def _error(
        self,
        request_id: str | None,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self.outbox.send(
            self.connection,
            "error",
            request_id=request_id,
            agent_id=None,
            task_id=None,
            data=ErrorBody(code=code, message=message, details=details),
        )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    registry: ConnectionRegistry = websocket.app.state.connections
    connection = registry.add(websocket)
    gateway = _Gateway(websocket, connection)
    try:
        await gateway.outbox.resend_pending_asks(connection)
        while True:
            raw = await websocket.receive_text()
            try:
                await gateway.handle(raw)
            except Exception:
                logger.exception("unexpected error handling websocket message")
                await gateway.outbox.send(
                    connection,
                    "error",
                    request_id=None,
                    agent_id=None,
                    task_id=None,
                    data=ErrorBody(
                        code=ErrorCode.INTERNAL_ERROR, message="An unexpected error occurred."
                    ),
                )
    except WebSocketDisconnect:
        pass
    finally:
        registry.remove(connection)
