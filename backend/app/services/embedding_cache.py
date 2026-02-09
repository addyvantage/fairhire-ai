"""Two-tier embedding cache: L1 in-memory LRU + L2 Redis.

Cache key format: ``emb:v1:{sha256_hex}``

The ``v1`` version prefix allows safe model upgrades — bump the version and
old (incompatible) vectors will never be served.  L1 provides sub-millisecond
hits for hot texts; L2 provides shared, persistent storage across processes.

Resilience: if Redis is unreachable, L2 operations silently degrade to misses
(reads) or no-ops (writes).  L1 continues to work independently.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError as RedisConnectionError, RedisError

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_CACHE_VERSION = "v1"
_KEY_PREFIX = f"emb:{_CACHE_VERSION}"


class EmbeddingCache:
    """L1 (memory) + L2 (Redis) embedding vector cache."""

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        l1_max_size: int = 1000,
        l2_ttl_seconds: int = 86400,
    ) -> None:
        self._redis = redis_client
        self._l1_max_size = l1_max_size
        self._l2_ttl = l2_ttl_seconds
        # OrderedDict used as an LRU: most-recently-used items move to end.
        self._l1: OrderedDict[str, list[float]] = OrderedDict()

    # -- Public API -----------------------------------------------------------

    async def get(self, text: str) -> list[float] | None:
        """Look up an embedding vector for *text*.

        Check order: L1 → L2.  On L2 hit the vector is promoted into L1.
        Returns ``None`` on cache miss.
        """
        key = self._cache_key(text)

        # L1
        vector = self._l1_get(key)
        if vector is not None:
            return vector

        # L2
        vector = await self._l2_get(key)
        if vector is not None:
            self._l1_put(key, vector)
            return vector

        return None

    async def set(self, text: str, vector: list[float]) -> None:
        """Store an embedding vector for *text* in both cache tiers."""
        key = self._cache_key(text)
        self._l1_put(key, vector)
        await self._l2_put(key, vector)

    async def invalidate(self, text: str) -> None:
        """Remove a cached vector from both tiers."""
        key = self._cache_key(text)
        self._l1.pop(key, None)
        await self._l2_delete(key)

    @property
    def l1_size(self) -> int:
        """Current number of entries in the L1 cache."""
        return len(self._l1)

    # -- L1 (in-memory LRU) --------------------------------------------------

    def _l1_get(self, key: str) -> list[float] | None:
        if key in self._l1:
            self._l1.move_to_end(key)
            return self._l1[key]
        return None

    def _l1_put(self, key: str, vector: list[float]) -> None:
        if key in self._l1:
            self._l1.move_to_end(key)
            self._l1[key] = vector
        else:
            if len(self._l1) >= self._l1_max_size:
                self._l1.popitem(last=False)  # evict oldest
            self._l1[key] = vector

    # -- L2 (Redis) -----------------------------------------------------------

    async def _l2_get(self, key: str) -> list[float] | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisConnectionError, RedisError, OSError) as exc:
            logger.warning("Embedding cache L2 read failed", extra={"key": key, "error": str(exc)})
            return None
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Embedding cache L2 deserialization failed", extra={"key": key, "error": str(exc)})
            return None

    async def _l2_put(self, key: str, vector: list[float]) -> None:
        if self._redis is None:
            return
        try:
            raw = json.dumps(vector)
            await self._redis.set(key, raw, ex=self._l2_ttl)
        except (RedisConnectionError, RedisError, OSError) as exc:
            logger.warning("Embedding cache L2 write failed", extra={"key": key, "error": str(exc)})

    async def _l2_delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except (RedisConnectionError, RedisError, OSError) as exc:
            logger.warning("Embedding cache L2 delete failed", extra={"key": key, "error": str(exc)})

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _cache_key(text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{_KEY_PREFIX}:{digest}"
