"""Embedding service wrapping sentence-transformers with fail-closed lifecycle.

State machine:
    UNINITIALIZED ──load_model()──▶ LOADING ──success──▶ READY
                                        │
                                        └──failure──▶ FAILED

Once in FAILED, the service stays failed.  Callers must check ``is_ready``
or handle ``RuntimeError`` from ``encode`` / ``encode_batch``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.services.interfaces import EmbeddingServiceInterface, ModelState

logger = logging.getLogger(__name__)


class EmbeddingService(EmbeddingServiceInterface):
    """Production embedding service backed by sentence-transformers.

    The model is loaded in a thread-pool executor so the event loop is never
    blocked.  All public methods enforce fail-closed semantics.
    """

    def __init__(self, model_name: str | None = None) -> None:
        settings = get_settings()
        self._model_name = model_name or settings.embedding_model_name
        self._model: Any = None  # SentenceTransformer instance (lazy)
        self._state = ModelState.UNINITIALIZED
        self._dimension: int = 0

    # -- Lifecycle ------------------------------------------------------------

    async def load_model(self) -> None:
        """Load the sentence-transformers model in a background thread.

        Transitions: UNINITIALIZED → LOADING → READY | FAILED.
        Calling ``load_model`` when already READY is a safe no-op.
        """
        if self._state == ModelState.READY:
            return
        if self._state == ModelState.LOADING:
            logger.warning("load_model() called while already loading — ignoring")
            return

        self._state = ModelState.LOADING
        logger.info("Loading embedding model", extra={"model": self._model_name})

        loop = asyncio.get_running_loop()
        try:
            self._model = await loop.run_in_executor(None, self._load_sync)
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._state = ModelState.READY
            logger.info(
                "Embedding model ready",
                extra={"model": self._model_name, "dimension": self._dimension},
            )
        except Exception as exc:
            self._state = ModelState.FAILED
            logger.error(
                "Embedding model failed to load",
                extra={"model": self._model_name, "error": str(exc)},
                exc_info=True,
            )
            raise RuntimeError(
                f"Embedding model '{self._model_name}' failed to load: {exc}"
            ) from exc

    def _load_sync(self) -> Any:
        """Synchronous model load — runs inside ``run_in_executor``."""
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self._model_name)

    # -- Encoding -------------------------------------------------------------

    async def encode(self, text: str) -> list[float]:
        """Encode a single text string into a dense vector.

        Raises ``RuntimeError`` if the model is not in READY state.
        """
        self._assert_ready()
        loop = asyncio.get_running_loop()
        vector = await loop.run_in_executor(None, self._encode_sync, [text])
        return vector[0].tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts into dense vectors.

        Raises ``RuntimeError`` if the model is not in READY state.
        """
        if not texts:
            return []
        self._assert_ready()
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, self._encode_sync, texts)
        return [v.tolist() for v in vectors]

    def _encode_sync(self, texts: list[str]) -> Any:
        """Synchronous encoding — runs inside ``run_in_executor``."""
        return self._model.encode(texts, show_progress_bar=False)

    # -- State ----------------------------------------------------------------

    @property
    def state(self) -> ModelState:
        return self._state

    @property
    def dimension(self) -> int:
        """Embedding vector dimension. Only valid when state is READY."""
        self._assert_ready()
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _assert_ready(self) -> None:
        if self._state != ModelState.READY:
            raise RuntimeError(
                f"EmbeddingService is not ready (state={self._state.value}). "
                f"Cannot process requests."
            )
