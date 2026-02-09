"""Resilience tests for async analysis infrastructure.

Covers failure scenarios:
- Redis unavailable during enqueue
- Queue enqueue failure (non-Redis)
- Job handler: analysis_id not found
- Job handler: resume/JD missing
- Job handler: orchestrator failure → status=failed + error persisted
- Worker heartbeat key behaviour
- Graceful degradation on RQ status sync failure
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.analysis import AnalysisRun
from app.services.async_analysis import enqueue_analysis, get_job_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_analysis(**overrides) -> AnalysisRun:
    defaults = {
        "id": 1,
        "user_id": 10,
        "resume_id": 100,
        "job_description_id": 200,
        "status": "pending",
        "job_id": "analysis-1",
        "overall_score": None,
        "result_payload": None,
        "error_message": None,
        "created_at": datetime.datetime.now(datetime.UTC),
    }
    defaults.update(overrides)
    analysis = AnalysisRun.__new__(AnalysisRun)
    for k, v in defaults.items():
        setattr(analysis, k, v)
    return analysis


# ---------------------------------------------------------------------------
# Redis unavailable scenarios
# ---------------------------------------------------------------------------


class TestRedisUnavailable:
    @pytest.mark.asyncio
    async def test_enqueue_marks_analysis_failed_when_redis_down(self) -> None:
        """When Redis is unreachable, the AnalysisRun should be marked failed."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_result(MagicMock()),
                _mock_scalar_result(MagicMock()),
            ]
        )
        added_objects: list = []
        db.add = lambda obj: added_objects.append(obj)
        commit_count = 0

        async def fake_commit():
            nonlocal commit_count
            commit_count += 1
            for obj in added_objects:
                if not hasattr(obj, "id") or obj.id is None:
                    obj.id = 1
                if not hasattr(obj, "created_at") or obj.created_at is None:
                    obj.created_at = datetime.datetime.now(datetime.UTC)

        db.commit = AsyncMock(side_effect=fake_commit)
        db.refresh = AsyncMock()

        with patch(
            "app.services.async_analysis.get_redis_connection",
            side_effect=RuntimeError("Connection refused"),
        ):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await enqueue_analysis(user_id=10, resume_id=100, job_description_id=200, db=db)
            assert exc_info.value.status_code == 503

        # The analysis should have been marked as failed
        assert len(added_objects) == 1
        assert added_objects[0].status == "failed"
        assert "Queue unavailable" in (added_objects[0].error_message or "")

    @pytest.mark.asyncio
    async def test_poll_gracefully_handles_rq_sync_failure(self) -> None:
        """If RQ fetch fails during polling, return the DB state without crashing."""
        analysis = _make_analysis(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(analysis))

        with patch(
            "app.services.async_analysis.fetch_job",
            side_effect=Exception("Redis down"),
        ):
            result = await get_job_status(user_id=10, job_id="analysis-1", db=db)
        # Should return the DB state, not crash
        assert result.status == "pending"


# ---------------------------------------------------------------------------
# Queue enqueue failure (non-Redis)
# ---------------------------------------------------------------------------


class TestQueueEnqueueFailure:
    @pytest.mark.asyncio
    async def test_enqueue_raises_503_on_rq_error(self) -> None:
        """If RQ queue.enqueue() raises, the API should return 503."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_result(MagicMock()),
                _mock_scalar_result(MagicMock()),
            ]
        )
        added_objects: list = []
        db.add = lambda obj: added_objects.append(obj)

        async def fake_commit():
            for obj in added_objects:
                if not hasattr(obj, "id") or obj.id is None:
                    obj.id = 1
                if not hasattr(obj, "created_at") or obj.created_at is None:
                    obj.created_at = datetime.datetime.now(datetime.UTC)

        db.commit = AsyncMock(side_effect=fake_commit)
        db.refresh = AsyncMock()

        with (
            patch("app.services.async_analysis.get_redis_connection") as mock_conn,
            patch("app.services.async_analysis.get_queue") as mock_queue,
        ):
            mock_queue.return_value.enqueue.side_effect = RuntimeError("Queue full")

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await enqueue_analysis(user_id=10, resume_id=100, job_description_id=200, db=db)
            assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Job handler failure scenarios
# ---------------------------------------------------------------------------


class TestJobHandlerResilience:
    @pytest.mark.asyncio
    async def test_mark_failed_persists_error(self) -> None:
        """_mark_failed should update analysis status and error_message."""
        from app.workers.job_handlers import _mark_failed

        analysis = _make_analysis(status="running")

        with patch("app.workers.job_handlers.SessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            mock_result = _mock_scalar_result(analysis)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()

            mock_session_cls.return_value = mock_session

            exc = ValueError("Orchestrator exploded")
            await _mark_failed(42, exc)

        assert analysis.status == "failed"
        assert "ValueError" in (analysis.error_message or "")

    @pytest.mark.asyncio
    async def test_mark_failed_handles_db_error_gracefully(self) -> None:
        """If _mark_failed itself fails (DB down), it should not raise."""
        from app.workers.job_handlers import _mark_failed

        with patch("app.workers.job_handlers.SessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            # Should not raise
            await _mark_failed(42, ValueError("original error"))

    @pytest.mark.asyncio
    async def test_execute_analysis_not_found(self) -> None:
        """_execute_analysis should raise ValueError if analysis_id doesn't exist."""
        from app.workers.job_handlers import _execute_analysis

        with patch("app.workers.job_handlers.SessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock(return_value=_mock_scalar_result(None))
            mock_session.commit = AsyncMock()
            mock_session_cls.return_value = mock_session

            with pytest.raises(ValueError, match="not found"):
                await _execute_analysis(9999)


# ---------------------------------------------------------------------------
# RQ status sync resilience
# ---------------------------------------------------------------------------


class TestRQStatusSync:
    @pytest.mark.asyncio
    async def test_sync_maps_rq_finished_to_completed(self) -> None:
        """RQ 'finished' status should map to 'completed'."""
        from app.services.async_analysis import _sync_rq_status

        analysis = _make_analysis(status="running", job_id="analysis-1")
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_job = MagicMock()
        mock_job.get_status.return_value = "finished"

        with patch("app.services.async_analysis.fetch_job", return_value=mock_job):
            result = await _sync_rq_status(analysis, db)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_sync_maps_rq_failed_to_failed(self) -> None:
        """RQ 'failed' status should map to 'failed'."""
        from app.services.async_analysis import _sync_rq_status

        analysis = _make_analysis(status="running", job_id="analysis-1")
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_job = MagicMock()
        mock_job.get_status.return_value = "failed"

        with patch("app.services.async_analysis.fetch_job", return_value=mock_job):
            result = await _sync_rq_status(analysis, db)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_sync_no_job_id_returns_unchanged(self) -> None:
        """If analysis has no job_id, sync should be a no-op."""
        from app.services.async_analysis import _sync_rq_status

        analysis = _make_analysis(status="pending", job_id=None)
        db = AsyncMock()

        result = await _sync_rq_status(analysis, db)
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_sync_rq_job_not_found_returns_unchanged(self) -> None:
        """If RQ job doesn't exist, return DB state unchanged."""
        from app.services.async_analysis import _sync_rq_status

        analysis = _make_analysis(status="pending", job_id="analysis-1")
        db = AsyncMock()

        with patch("app.services.async_analysis.fetch_job", return_value=None):
            result = await _sync_rq_status(analysis, db)
        assert result.status == "pending"


# ---------------------------------------------------------------------------
# Worker heartbeat key tests
# ---------------------------------------------------------------------------


class TestWorkerHeartbeat:
    def test_heartbeat_key_prefix(self) -> None:
        from app.workers.worker_runner import _HEARTBEAT_KEY_PREFIX

        assert _HEARTBEAT_KEY_PREFIX == "fairhire:worker:heartbeat"
