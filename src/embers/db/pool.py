"""Asyncpg connection pool, tolerant to the database being unreachable at startup."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import asyncpg

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

PING_TIMEOUT_SECONDS = 2.0


async def _init_connection(connection: asyncpg.Connection) -> None:
    """Encode and decode jsonb columns as Python objects."""
    await connection.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


class Database:
    """Wraps an asyncpg pool with a lifecycle that never blocks app startup."""

    def __init__(self, dsn: str, *, min_size: int = 0, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def open(self) -> None:
        """Create the pool. With `min_size=0` this does not connect eagerly, so it
        succeeds even if the database is currently unreachable."""
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            init=_init_connection,
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.pool.PoolConnectionProxy]:
        if self._pool is None:
            raise RuntimeError("Database pool is not open; call open() first")
        async with self._pool.acquire() as connection:
            yield connection

    async def ping(self, timeout: float = PING_TIMEOUT_SECONDS) -> bool:
        """Return True if a `SELECT 1` completes within `timeout` seconds."""
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire(timeout=timeout) as connection:
                await connection.fetchval("SELECT 1")
            return True
        except (TimeoutError, OSError, asyncpg.PostgresError):
            logger.warning("database ping failed", exc_info=True)
            return False
