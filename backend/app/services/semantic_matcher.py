"""Semantic matching via cosine similarity on embedding vectors.

Requires an initialised ``EmbeddingService`` (state == READY) and an
``EmbeddingCache`` instance.  The cache is checked before encoding so
repeated texts are essentially free.

Score is cosine similarity mapped to the 0–100 range.  Cosine similarity
naturally falls in [-1, 1]; we clamp to [0, 1] before scaling because
negative similarity between a resume and a job description is semantically
equivalent to "no match".
"""

from __future__ import annotations

import logging
import math

from app.schemas.analysis import ExplainableMetric
from app.services.embedding_cache import EmbeddingCache
from app.services.interfaces import EmbeddingServiceInterface, SemanticMatcherInterface

logger = logging.getLogger(__name__)


class SemanticMatcherService(SemanticMatcherInterface):
    """Cosine-similarity scorer backed by dense embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingServiceInterface,
        cache: EmbeddingCache,
    ) -> None:
        self._embedding = embedding_service
        self._cache = cache

    async def score(self, resume_text: str, jd_text: str) -> ExplainableMetric:
        if not jd_text or not jd_text.strip():
            return ExplainableMetric(
                score=0,
                explanation="Job description text is empty or not parseable.",
                contributing_factors=["No valid JD text provided"],
            )

        if not resume_text or not resume_text.strip():
            return ExplainableMetric(
                score=0,
                explanation="Resume text is empty or not parseable.",
                contributing_factors=["No valid resume text provided"],
            )

        resume_vec = await self._get_embedding(resume_text)
        jd_vec = await self._get_embedding(jd_text)

        cosine = self._cosine_similarity(resume_vec, jd_vec)
        # Clamp to [0, 1] — negative cosine means anti-correlated, treated as 0.
        clamped = max(0.0, min(1.0, cosine))
        score = round(clamped * 100, 2)

        factors = [
            f"Cosine similarity: {cosine:.4f}",
            f"Clamped similarity: {clamped:.4f}",
            f"Embedding dimension: {len(resume_vec)}",
        ]

        return ExplainableMetric(
            score=score,
            explanation="Semantic alignment computed via cosine similarity on dense embeddings.",
            contributing_factors=factors,
        )

    # -- Helpers --------------------------------------------------------------

    async def _get_embedding(self, text: str) -> list[float]:
        """Retrieve embedding from cache, or encode and cache it."""
        cached = await self._cache.get(text)
        if cached is not None:
            return cached
        vector = await self._embedding.encode(text)
        await self._cache.set(text, vector)
        return vector

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Returns 0.0 if either vector has zero magnitude.
        """
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
