"""Tests for EmbeddingCache (L1 in-memory + L2 Redis).

Uses fakeredis for L2 tests so no real Redis instance is needed.
"""

from __future__ import annotations

import pytest
import fakeredis.aioredis

from app.services.embedding_cache import EmbeddingCache, _KEY_PREFIX

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_VEC = [0.1, 0.2, 0.3, 0.4, 0.5]
_SAMPLE_TEXT = "python engineer with fastapi experience"


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def cache_l1_only() -> EmbeddingCache:
    """Cache with no Redis backend (L1 only)."""
    return EmbeddingCache(redis_client=None, l1_max_size=5)


@pytest.fixture
def cache_with_redis(fake_redis: fakeredis.aioredis.FakeRedis) -> EmbeddingCache:
    """Cache with both L1 and L2 (fakeredis)."""
    return EmbeddingCache(redis_client=fake_redis, l1_max_size=5, l2_ttl_seconds=3600)


# ---------------------------------------------------------------------------
# L1-only tests
# ---------------------------------------------------------------------------


class TestEmbeddingCacheL1Only:
    @pytest.mark.asyncio
    async def test_miss_returns_none(self, cache_l1_only: EmbeddingCache) -> None:
        assert await cache_l1_only.get("unknown text") is None

    @pytest.mark.asyncio
    async def test_set_then_get(self, cache_l1_only: EmbeddingCache) -> None:
        await cache_l1_only.set(_SAMPLE_TEXT, _SAMPLE_VEC)
        result = await cache_l1_only.get(_SAMPLE_TEXT)
        assert result == _SAMPLE_VEC

    @pytest.mark.asyncio
    async def test_l1_size_tracks_entries(self, cache_l1_only: EmbeddingCache) -> None:
        assert cache_l1_only.l1_size == 0
        await cache_l1_only.set("a", [1.0])
        assert cache_l1_only.l1_size == 1
        await cache_l1_only.set("b", [2.0])
        assert cache_l1_only.l1_size == 2

    @pytest.mark.asyncio
    async def test_l1_evicts_oldest_when_full(self, cache_l1_only: EmbeddingCache) -> None:
        """L1 max_size=5; inserting 6 items should evict the first."""
        for i in range(6):
            await cache_l1_only.set(f"text_{i}", [float(i)])
        assert cache_l1_only.l1_size == 5
        # text_0 was evicted
        assert await cache_l1_only.get("text_0") is None
        # text_5 is present
        assert await cache_l1_only.get("text_5") == [5.0]

    @pytest.mark.asyncio
    async def test_l1_lru_access_prevents_eviction(self, cache_l1_only: EmbeddingCache) -> None:
        """Accessing an entry moves it to end, preventing eviction."""
        for i in range(5):
            await cache_l1_only.set(f"text_{i}", [float(i)])
        # Access text_0 to make it recently used
        await cache_l1_only.get("text_0")
        # Insert one more — text_1 should be evicted (oldest untouched)
        await cache_l1_only.set("text_5", [5.0])
        assert await cache_l1_only.get("text_0") == [0.0]
        assert await cache_l1_only.get("text_1") is None

    @pytest.mark.asyncio
    async def test_invalidate_removes_from_l1(self, cache_l1_only: EmbeddingCache) -> None:
        await cache_l1_only.set(_SAMPLE_TEXT, _SAMPLE_VEC)
        assert await cache_l1_only.get(_SAMPLE_TEXT) == _SAMPLE_VEC
        await cache_l1_only.invalidate(_SAMPLE_TEXT)
        assert await cache_l1_only.get(_SAMPLE_TEXT) is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, cache_l1_only: EmbeddingCache) -> None:
        await cache_l1_only.set("text", [1.0])
        await cache_l1_only.set("text", [2.0])
        assert await cache_l1_only.get("text") == [2.0]
        assert cache_l1_only.l1_size == 1


# ---------------------------------------------------------------------------
# L1 + L2 (fakeredis) tests
# ---------------------------------------------------------------------------


class TestEmbeddingCacheWithRedis:
    @pytest.mark.asyncio
    async def test_set_writes_to_both_tiers(
        self, cache_with_redis: EmbeddingCache, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        await cache_with_redis.set(_SAMPLE_TEXT, _SAMPLE_VEC)
        # L1
        assert cache_with_redis.l1_size == 1
        # L2 — verify key exists in Redis
        key = EmbeddingCache._cache_key(_SAMPLE_TEXT)
        raw = await fake_redis.get(key)
        assert raw is not None

    @pytest.mark.asyncio
    async def test_l2_hit_promotes_to_l1(
        self, cache_with_redis: EmbeddingCache, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        """If L1 misses but L2 hits, the vector is promoted into L1."""
        import json

        key = EmbeddingCache._cache_key(_SAMPLE_TEXT)
        # Write directly to Redis (bypassing L1)
        await fake_redis.set(key, json.dumps(_SAMPLE_VEC))

        assert cache_with_redis.l1_size == 0
        result = await cache_with_redis.get(_SAMPLE_TEXT)
        assert result == _SAMPLE_VEC
        assert cache_with_redis.l1_size == 1  # promoted

    @pytest.mark.asyncio
    async def test_invalidate_removes_from_both_tiers(
        self, cache_with_redis: EmbeddingCache, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        await cache_with_redis.set(_SAMPLE_TEXT, _SAMPLE_VEC)
        key = EmbeddingCache._cache_key(_SAMPLE_TEXT)
        assert await fake_redis.get(key) is not None

        await cache_with_redis.invalidate(_SAMPLE_TEXT)
        assert cache_with_redis.l1_size == 0
        assert await fake_redis.get(key) is None

    @pytest.mark.asyncio
    async def test_l2_ttl_is_set(
        self, cache_with_redis: EmbeddingCache, fake_redis: fakeredis.aioredis.FakeRedis
    ) -> None:
        await cache_with_redis.set(_SAMPLE_TEXT, _SAMPLE_VEC)
        key = EmbeddingCache._cache_key(_SAMPLE_TEXT)
        ttl = await fake_redis.ttl(key)
        assert ttl > 0
        assert ttl <= 3600

    @pytest.mark.asyncio
    async def test_complete_miss_returns_none(self, cache_with_redis: EmbeddingCache) -> None:
        assert await cache_with_redis.get("never stored") is None


# ---------------------------------------------------------------------------
# Redis failure resilience tests
# ---------------------------------------------------------------------------


class TestEmbeddingCacheRedisResilience:
    @pytest.mark.asyncio
    async def test_l2_read_failure_degrades_to_miss(self) -> None:
        """If Redis raises on GET, cache should return None (not crash)."""
        broken_redis = fakeredis.aioredis.FakeRedis()
        await broken_redis.aclose()  # close it to force errors
        cache = EmbeddingCache(redis_client=broken_redis, l1_max_size=5)
        # Should not raise — degrades gracefully
        result = await cache.get("some text")
        assert result is None

    @pytest.mark.asyncio
    async def test_l2_write_failure_does_not_crash(self) -> None:
        """If Redis raises on SET, cache should silently skip L2."""
        broken_redis = fakeredis.aioredis.FakeRedis()
        await broken_redis.aclose()
        cache = EmbeddingCache(redis_client=broken_redis, l1_max_size=5)
        # Should not raise — L1 still works
        await cache.set("some text", [1.0, 2.0])
        assert cache.l1_size == 1

    @pytest.mark.asyncio
    async def test_l1_works_independently_when_redis_down(self) -> None:
        """Full round-trip via L1 when Redis is broken."""
        broken_redis = fakeredis.aioredis.FakeRedis()
        await broken_redis.aclose()
        cache = EmbeddingCache(redis_client=broken_redis, l1_max_size=5)
        await cache.set("text", [0.5, 0.6])
        result = await cache.get("text")
        assert result == [0.5, 0.6]


# ---------------------------------------------------------------------------
# Cache key tests
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_key_has_version_prefix(self) -> None:
        key = EmbeddingCache._cache_key("hello")
        assert key.startswith(f"{_KEY_PREFIX}:")

    def test_same_text_produces_same_key(self) -> None:
        assert EmbeddingCache._cache_key("abc") == EmbeddingCache._cache_key("abc")

    def test_different_text_produces_different_key(self) -> None:
        assert EmbeddingCache._cache_key("abc") != EmbeddingCache._cache_key("xyz")

    def test_key_is_deterministic_sha256(self) -> None:
        import hashlib

        text = "test input"
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        key = EmbeddingCache._cache_key(text)
        assert key == f"{_KEY_PREFIX}:{expected_hash}"
