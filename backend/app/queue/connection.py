from __future__ import annotations

import logging
from typing import Self

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Manages a shared async Redis connection with health checking.

    Usage:
        manager = RedisManager()
        await manager.connect()
        client = manager.client  # redis.asyncio.Redis instance
        await manager.close()
    """

    def __init__(self, redis_url: str | None = None) -> None:
        settings = get_settings()
        self._url = redis_url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Create the Redis connection pool and verify connectivity."""
        self._client = aioredis.from_url(
            self._url,
            decode_responses=False,
            max_connections=20,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        try:
            await self._client.ping()
            logger.info("Redis connection established", extra={"redis_url": self._url})
        except (RedisConnectionError, RedisError) as exc:
            logger.error(
                "Redis connection failed on startup",
                extra={"redis_url": self._url, "error": str(exc)},
            )
            raise

    @property
    def client(self) -> aioredis.Redis:
        """Return the active Redis client. Raises if not connected."""
        if self._client is None:
            raise RuntimeError("RedisManager is not connected. Call connect() first.")
        return self._client

    async def ping(self) -> bool:
        """Non-throwing health check. Returns True if Redis is reachable."""
        if self._client is None:
            return False
        try:
            return bool(await self._client.ping())
        except (RedisConnectionError, RedisError, OSError):
            return False

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis connection closed")

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
