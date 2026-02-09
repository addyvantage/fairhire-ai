"""Tests for the Redis connection manager.

Uses fakeredis to avoid requiring a real Redis instance in CI.
"""

from __future__ import annotations

import pytest
import fakeredis.aioredis

from app.queue.connection import RedisManager


@pytest.fixture
def redis_manager() -> RedisManager:
    """Create a RedisManager pointed at a fake URL (overridden in tests)."""
    return RedisManager(redis_url="redis://localhost:6379/15")


class TestRedisManagerUnit:
    """Unit tests that do not require a running Redis."""

    def test_client_raises_before_connect(self, redis_manager: RedisManager) -> None:
        """Accessing .client before connect() must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            _ = redis_manager.client

    @pytest.mark.asyncio
    async def test_ping_returns_false_before_connect(
        self, redis_manager: RedisManager
    ) -> None:
        """ping() must return False when there is no active connection."""
        assert await redis_manager.ping() is False

    @pytest.mark.asyncio
    async def test_close_is_safe_before_connect(
        self, redis_manager: RedisManager
    ) -> None:
        """close() must not raise even if never connected."""
        await redis_manager.close()  # should be a no-op


class TestRedisManagerWithFake:
    """Integration-style tests using fakeredis as the backend."""

    @pytest.mark.asyncio
    async def test_connect_and_ping(self) -> None:
        """Verify connect + ping round-trip with fakeredis."""
        manager = RedisManager.__new__(RedisManager)
        manager._url = "redis://localhost:6379/15"
        manager._client = fakeredis.aioredis.FakeRedis()
        assert await manager.ping() is True

    @pytest.mark.asyncio
    async def test_client_accessible_after_fake_connect(self) -> None:
        """After injecting a fake client, .client should return it."""
        manager = RedisManager.__new__(RedisManager)
        manager._url = "redis://localhost:6379/15"
        manager._client = fakeredis.aioredis.FakeRedis()
        client = manager.client
        assert client is not None
        await client.set("test_key", b"test_value")
        assert await client.get("test_key") == b"test_value"

    @pytest.mark.asyncio
    async def test_close_clears_client(self) -> None:
        """After close(), .client must raise and ping must return False."""
        manager = RedisManager.__new__(RedisManager)
        manager._url = "redis://localhost:6379/15"
        manager._client = fakeredis.aioredis.FakeRedis()
        assert await manager.ping() is True

        await manager.close()

        assert await manager.ping() is False
        with pytest.raises(RuntimeError, match="not connected"):
            _ = manager.client

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self) -> None:
        """RedisManager supports async with for connect/close lifecycle."""
        manager = RedisManager.__new__(RedisManager)
        manager._url = "redis://localhost:6379/15"
        # Manually simulate __aenter__/__aexit__ with a fake client.
        manager._client = fakeredis.aioredis.FakeRedis()
        assert await manager.ping() is True
        await manager.__aexit__(None, None, None)
        assert await manager.ping() is False
