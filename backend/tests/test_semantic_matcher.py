"""Tests for the embedding-based SemanticMatcherService.

All tests use a fake EmbeddingService that returns deterministic vectors,
so no real model download is required.
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock

import pytest

from app.schemas.analysis import ExplainableMetric
from app.services.embedding_cache import EmbeddingCache
from app.services.interfaces import EmbeddingServiceInterface, ModelState
from app.services.semantic_matcher import SemanticMatcherService

# ---------------------------------------------------------------------------
# Fake embedding service
# ---------------------------------------------------------------------------


class FakeEmbeddingService(EmbeddingServiceInterface):
    """Deterministic embedding service for testing.

    Returns a fixed vector per text, or a configurable mapping.
    """

    def __init__(self, vectors: dict[str, list[float]] | None = None, dim: int = 4) -> None:
        self._vectors = vectors or {}
        self._dim = dim
        self._state = ModelState.READY

    async def load_model(self) -> None:
        self._state = ModelState.READY

    async def encode(self, text: str) -> list[float]:
        if text in self._vectors:
            return self._vectors[text]
        # Default: hash-based deterministic vector
        import hashlib

        h = hashlib.md5(text.encode()).hexdigest()
        return [int(h[i : i + 2], 16) / 255.0 for i in range(0, self._dim * 2, 2)]

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.encode(t) for t in texts]

    @property
    def state(self) -> ModelState:
        return self._state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache() -> EmbeddingCache:
    """L1-only cache (no Redis)."""
    return EmbeddingCache(redis_client=None, l1_max_size=100)


@pytest.fixture
def embedding_svc() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def matcher(embedding_svc: FakeEmbeddingService, cache: EmbeddingCache) -> SemanticMatcherService:
    return SemanticMatcherService(embedding_service=embedding_svc, cache=cache)


# ---------------------------------------------------------------------------
# Cosine similarity unit tests (static method)
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        result = SemanticMatcherService._cosine_similarity(v, v)
        assert math.isclose(result, 1.0, rel_tol=1e-9)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = SemanticMatcherService._cosine_similarity(a, b)
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        result = SemanticMatcherService._cosine_similarity(a, b)
        assert math.isclose(result, -1.0, rel_tol=1e-9)

    def test_zero_vector_returns_zero(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert SemanticMatcherService._cosine_similarity(a, b) == 0.0
        assert SemanticMatcherService._cosine_similarity(b, a) == 0.0

    def test_both_zero_vectors(self) -> None:
        a = [0.0, 0.0]
        assert SemanticMatcherService._cosine_similarity(a, a) == 0.0

    def test_known_angle(self) -> None:
        """45-degree angle → cos(45°) ≈ 0.7071."""
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        result = SemanticMatcherService._cosine_similarity(a, b)
        assert math.isclose(result, math.cos(math.pi / 4), rel_tol=1e-6)

    def test_negative_values(self) -> None:
        a = [-1.0, -2.0, -3.0]
        b = [-1.0, -2.0, -3.0]
        result = SemanticMatcherService._cosine_similarity(a, b)
        assert math.isclose(result, 1.0, rel_tol=1e-9)

    def test_single_dimension(self) -> None:
        assert math.isclose(
            SemanticMatcherService._cosine_similarity([5.0], [3.0]), 1.0, rel_tol=1e-9
        )
        assert math.isclose(
            SemanticMatcherService._cosine_similarity([5.0], [-3.0]), -1.0, rel_tol=1e-9
        )


# ---------------------------------------------------------------------------
# Score output tests
# ---------------------------------------------------------------------------


class TestSemanticMatcherScore:
    @pytest.mark.asyncio
    async def test_identical_text_scores_100(self, cache: EmbeddingCache) -> None:
        """Same text → same vector → cosine=1 → score=100."""
        svc = FakeEmbeddingService()
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)
        result = await matcher.score("python developer", "python developer")
        assert isinstance(result, ExplainableMetric)
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_score_is_in_0_100_range(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("data scientist with ML experience", "looking for a chef")
        assert 0 <= result.score <= 100

    @pytest.mark.asyncio
    async def test_score_contains_explanation(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("engineer", "developer")
        assert "cosine similarity" in result.explanation.lower()

    @pytest.mark.asyncio
    async def test_score_contains_contributing_factors(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("resume text here", "job description here")
        assert len(result.contributing_factors) >= 1
        assert any("Cosine similarity" in f for f in result.contributing_factors)
        assert any("Embedding dimension" in f for f in result.contributing_factors)

    @pytest.mark.asyncio
    async def test_negative_cosine_clamped_to_zero(self, cache: EmbeddingCache) -> None:
        """Anti-correlated vectors should produce score=0, not negative."""
        svc = FakeEmbeddingService(
            vectors={
                "text_a": [1.0, 0.0, 0.0, 0.0],
                "text_b": [-1.0, 0.0, 0.0, 0.0],
            }
        )
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)
        result = await matcher.score("text_a", "text_b")
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_orthogonal_vectors_score_zero(self, cache: EmbeddingCache) -> None:
        svc = FakeEmbeddingService(
            vectors={
                "resume": [1.0, 0.0, 0.0, 0.0],
                "jd": [0.0, 1.0, 0.0, 0.0],
            }
        )
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)
        result = await matcher.score("resume", "jd")
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_partial_similarity_produces_intermediate_score(self, cache: EmbeddingCache) -> None:
        """Two vectors at a known angle should produce a predictable score."""
        svc = FakeEmbeddingService(
            vectors={
                "resume": [1.0, 0.0],
                "jd": [1.0, 1.0],
            },
            dim=2,
        )
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)
        result = await matcher.score("resume", "jd")
        expected = round(math.cos(math.pi / 4) * 100, 2)
        assert math.isclose(result.score, expected, rel_tol=1e-4)


# ---------------------------------------------------------------------------
# Edge case / empty input tests
# ---------------------------------------------------------------------------


class TestSemanticMatcherEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_jd_returns_zero(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("some resume", "")
        assert result.score == 0
        assert "empty" in result.explanation.lower()

    @pytest.mark.asyncio
    async def test_whitespace_jd_returns_zero(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("some resume", "   \n\t  ")
        assert result.score == 0

    @pytest.mark.asyncio
    async def test_empty_resume_returns_zero(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("", "some job description")
        assert result.score == 0
        assert "empty" in result.explanation.lower()

    @pytest.mark.asyncio
    async def test_whitespace_resume_returns_zero(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("  \t\n  ", "some job description")
        assert result.score == 0

    @pytest.mark.asyncio
    async def test_both_empty_returns_zero(self, matcher: SemanticMatcherService) -> None:
        result = await matcher.score("", "")
        assert result.score == 0


# ---------------------------------------------------------------------------
# Cache integration tests
# ---------------------------------------------------------------------------


class TestSemanticMatcherCaching:
    @pytest.mark.asyncio
    async def test_cache_is_populated_after_score(self, cache: EmbeddingCache) -> None:
        """Scoring should populate the cache for both texts."""
        svc = FakeEmbeddingService()
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)
        await matcher.score("resume text", "jd text")
        # Both texts should now be cached
        assert await cache.get("resume text") is not None
        assert await cache.get("jd text") is not None

    @pytest.mark.asyncio
    async def test_cache_hit_avoids_encode(self, cache: EmbeddingCache) -> None:
        """If the cache already has the vector, encode should not be called."""
        svc = FakeEmbeddingService()
        matcher = SemanticMatcherService(embedding_service=svc, cache=cache)

        # Prime the cache
        await cache.set("resume", [1.0, 0.0, 0.0, 0.0])
        await cache.set("jd", [0.0, 1.0, 0.0, 0.0])

        # Wrap encode to track calls
        original_encode = svc.encode
        call_count = 0

        async def counting_encode(text: str) -> list[float]:
            nonlocal call_count
            call_count += 1
            return await original_encode(text)

        svc.encode = counting_encode  # type: ignore[assignment]

        await matcher.score("resume", "jd")
        assert call_count == 0, "encode should not have been called when cache hits"
