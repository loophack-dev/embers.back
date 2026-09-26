"""Open WebSocket connections and serialized sending."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Connection:
    def __init__(self, websocket: WebSocket) -> None:
        self.id: UUID = uuid4()
        self._websocket = websocket
        self._lock = asyncio.Lock()

    async def send(self, message: dict[str, Any]) -> None:
        async with self._lock:
            await self._websocket.send_json(message)


class ConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[UUID, Connection] = {}

    def add(self, websocket: WebSocket) -> Connection:
        connection = Connection(websocket)
        self._connections[connection.id] = connection
        logger.info("websocket connected", extra={"connection_id": str(connection.id)})
        return connection

    def remove(self, connection: Connection) -> None:
        if self._connections.pop(connection.id, None) is not None:
            logger.info("websocket disconnected", extra={"connection_id": str(connection.id)})

    def all(self) -> list[Connection]:
        return list(self._connections.values())
