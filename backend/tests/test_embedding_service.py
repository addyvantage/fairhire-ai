"""Tests for EmbeddingService lifecycle and encoding.

Uses a mock SentenceTransformer to avoid downloading a real model in CI.
A separate integration-style test at the bottom verifies real model behaviour
when ``FAIRHIRE_TEST_REAL_MODEL=1`` is set (skipped by default).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embedding_service import EmbeddingService
from app.services.interfaces import ModelState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_DIM = 384


def _make_fake_st_class() -> MagicMock:
    """Build a mock that behaves like a SentenceTransformer instance."""
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = _FAKE_DIM
    mock_model.encode.side_effect = lambda texts, **kw: np.random.rand(len(texts), _FAKE_DIM).astype(np.float32)
    return mock_model


# ---------------------------------------------------------------------------
# Lifecycle state tests
# ---------------------------------------------------------------------------


class TestEmbeddingServiceLifecycle:
    def test_initial_state_is_uninitialized(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        assert svc.state == ModelState.UNINITIALIZED
        assert svc.is_ready is False

    @pytest.mark.asyncio
    async def test_load_model_transitions_to_ready(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with patch.object(svc, "_load_sync", return_value=_make_fake_st_class()):
            await svc.load_model()
        assert svc.state == ModelState.READY
        assert svc.is_ready is True
        assert svc.dimension == _FAKE_DIM

    @pytest.mark.asyncio
    async def test_load_model_transitions_to_failed_on_error(self) -> None:
        svc = EmbeddingService(model_name="nonexistent-model")
        with patch.object(svc, "_load_sync", side_effect=OSError("download failed")):
            with pytest.raises(RuntimeError, match="failed to load"):
                await svc.load_model()
        assert svc.state == ModelState.FAILED
        assert svc.is_ready is False

    @pytest.mark.asyncio
    async def test_double_load_when_ready_is_noop(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        fake = _make_fake_st_class()
        with patch.object(svc, "_load_sync", return_value=fake):
            await svc.load_model()
            await svc.load_model()  # should not raise or re-load
        assert svc.state == ModelState.READY


# ---------------------------------------------------------------------------
# Fail-closed tests
# ---------------------------------------------------------------------------


class TestEmbeddingServiceFailClosed:
    @pytest.mark.asyncio
    async def test_encode_raises_when_uninitialized(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with pytest.raises(RuntimeError, match="not ready"):
            await svc.encode("hello")

    @pytest.mark.asyncio
    async def test_encode_batch_raises_when_uninitialized(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with pytest.raises(RuntimeError, match="not ready"):
            await svc.encode_batch(["hello"])

    @pytest.mark.asyncio
    async def test_encode_raises_when_failed(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with patch.object(svc, "_load_sync", side_effect=OSError("boom")):
            with pytest.raises(RuntimeError):
                await svc.load_model()
        assert svc.state == ModelState.FAILED
        with pytest.raises(RuntimeError, match="not ready"):
            await svc.encode("hello")

    @pytest.mark.asyncio
    async def test_dimension_raises_when_not_ready(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with pytest.raises(RuntimeError, match="not ready"):
            _ = svc.dimension


# ---------------------------------------------------------------------------
# Encoding tests (mock model)
# ---------------------------------------------------------------------------


class TestEmbeddingServiceEncoding:
    @pytest.mark.asyncio
    async def test_encode_returns_float_list(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with patch.object(svc, "_load_sync", return_value=_make_fake_st_class()):
            await svc.load_model()
        result = await svc.encode("test text")
        assert isinstance(result, list)
        assert len(result) == _FAKE_DIM
        assert all(isinstance(v, float) for v in result)

    @pytest.mark.asyncio
    async def test_encode_batch_returns_list_of_float_lists(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with patch.object(svc, "_load_sync", return_value=_make_fake_st_class()):
            await svc.load_model()
        texts = ["one", "two", "three"]
        result = await svc.encode_batch(texts)
        assert isinstance(result, list)
        assert len(result) == 3
        for vec in result:
            assert len(vec) == _FAKE_DIM

    @pytest.mark.asyncio
    async def test_encode_batch_empty_input(self) -> None:
        svc = EmbeddingService(model_name="mock-model")
        with patch.object(svc, "_load_sync", return_value=_make_fake_st_class()):
            await svc.load_model()
        result = await svc.encode_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_model_name_property(self) -> None:
        svc = EmbeddingService(model_name="test-model-v2")
        assert svc.model_name == "test-model-v2"


# ---------------------------------------------------------------------------
# Integration test (real model — skipped unless opted in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("FAIRHIRE_TEST_REAL_MODEL") != "1",
    reason="Set FAIRHIRE_TEST_REAL_MODEL=1 to run real model tests",
)
class TestEmbeddingServiceRealModel:
    @pytest.mark.asyncio
    async def test_real_model_load_and_encode(self) -> None:
        svc = EmbeddingService()  # uses default model from config
        await svc.load_model()
        assert svc.state == ModelState.READY
        assert svc.dimension > 0

        vec = await svc.encode("Software engineer with Python experience")
        assert len(vec) == svc.dimension
        assert all(isinstance(v, float) for v in vec)
