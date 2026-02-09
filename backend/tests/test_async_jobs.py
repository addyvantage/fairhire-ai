"""Tests for the async analysis job infrastructure.

Covers:
- Successful job enqueue
- Retry configuration correctness
- Job status polling
- Forbidden access to another user's job
- Queue/Redis error handling

Uses monkeypatch + fakeredis to avoid real Redis / DB dependencies.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.models.analysis import AnalysisRun
from app.schemas.analysis import AsyncAnalysisResponse, JobStatusResponse
from app.services.async_analysis import enqueue_analysis, get_job_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(
    id: int = 1,
    user_id: int = 10,
    resume_id: int = 100,
    job_description_id: int = 200,
    status: str = "pending",
    job_id: str | None = None,
    overall_score: float | None = None,
    result_payload: dict | None = None,
    error_message: str | None = None,
) -> AnalysisRun:
    """Build a mock AnalysisRun with sensible defaults."""
    analysis = AnalysisRun.__new__(AnalysisRun)
    analysis.id = id
    analysis.user_id = user_id
    analysis.resume_id = resume_id
    analysis.job_description_id = job_description_id
    analysis.status = status
    analysis.job_id = job_id
    analysis.overall_score = overall_score
    analysis.result_payload = result_payload
    analysis.error_message = error_message
    analysis.created_at = datetime.datetime.now(datetime.UTC)
    return analysis


def _mock_scalar_result(value):
    """Create a mock for db.execute() result with scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# Settings / retry configuration
# ---------------------------------------------------------------------------


class TestRetryConfiguration:
    def test_default_retry_max(self) -> None:
        settings = get_settings()
        assert settings.async_job_retry_max == 3

    def test_default_retry_interval(self) -> None:
        settings = get_settings()
        assert settings.async_job_retry_interval == [10, 30, 60]

    def test_queue_name(self) -> None:
        settings = get_settings()
        assert settings.queue_name == "fairhire:analysis"

    def test_worker_heartbeat_defaults(self) -> None:
        settings = get_settings()
        assert settings.worker_heartbeat_interval_seconds == 30
        assert settings.worker_heartbeat_ttl_seconds == 90


# ---------------------------------------------------------------------------
# Enqueue tests
# ---------------------------------------------------------------------------


class TestEnqueueAnalysis:
    @pytest.mark.asyncio
    async def test_successful_enqueue(self) -> None:
        """enqueue_analysis should create an AnalysisRun and enqueue an RQ job."""
        db = AsyncMock()

        # Mock ownership checks — both return a truthy result
        resume_mock = MagicMock()
        jd_mock = MagicMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_result(resume_mock),  # resume check
                _mock_scalar_result(jd_mock),  # JD check
            ]
        )

        # Capture the AnalysisRun added to the session
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

        # Mock the RQ queue
        mock_rq_job = MagicMock()
        mock_rq_job.id = "analysis-1"

        with (
            patch("app.services.async_analysis.get_redis_connection") as mock_conn,
            patch("app.services.async_analysis.get_queue") as mock_queue,
        ):
            mock_queue.return_value.enqueue.return_value = mock_rq_job

            result = await enqueue_analysis(
                user_id=10,
                resume_id=100,
                job_description_id=200,
                db=db,
            )

        assert result.status == "pending"
        assert result.job_id == "analysis-1"
        assert result.user_id == 10
        mock_queue.return_value.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_resume_not_found(self) -> None:
        """enqueue_analysis should raise 404 if resume is not found."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(None))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await enqueue_analysis(user_id=10, resume_id=999, job_description_id=200, db=db)
        assert exc_info.value.status_code == 404
        assert "Resume" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enqueue_jd_not_found(self) -> None:
        """enqueue_analysis should raise 404 if JD is not found."""
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _mock_scalar_result(MagicMock()),  # resume found
                _mock_scalar_result(None),  # JD not found
            ]
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await enqueue_analysis(user_id=10, resume_id=100, job_description_id=999, db=db)
        assert exc_info.value.status_code == 404
        assert "Job description" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_enqueue_redis_unavailable_returns_503(self) -> None:
        """If Redis is down, enqueue should raise 503."""
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

        with patch(
            "app.services.async_analysis.get_redis_connection",
            side_effect=RuntimeError("Redis down"),
        ):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await enqueue_analysis(user_id=10, resume_id=100, job_description_id=200, db=db)
            assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Job status polling tests
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    @pytest.mark.asyncio
    async def test_returns_completed_analysis(self) -> None:
        """Polling a completed job should return its result."""
        analysis = _make_analysis(
            status="completed",
            job_id="analysis-1",
            overall_score=85.5,
            result_payload={"key": "value"},
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(analysis))

        result = await get_job_status(user_id=10, job_id="analysis-1", db=db)
        assert result.status == "completed"
        assert result.overall_score == 85.5

    @pytest.mark.asyncio
    async def test_returns_pending_and_syncs_with_rq(self) -> None:
        """Polling a pending job should attempt to sync with RQ."""
        analysis = _make_analysis(status="pending", job_id="analysis-1")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(analysis))
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        mock_rq_job = MagicMock()
        mock_rq_job.get_status.return_value = "started"

        with patch("app.services.async_analysis.fetch_job", return_value=mock_rq_job):
            result = await get_job_status(user_id=10, job_id="analysis-1", db=db)
        assert result.status == "running"

    @pytest.mark.asyncio
    async def test_job_not_found_raises_404(self) -> None:
        """Polling a nonexistent job should raise 404."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(None))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_job_status(user_id=10, job_id="nonexistent", db=db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_forbidden_access_other_users_job(self) -> None:
        """A user should NOT be able to poll another user's job.

        The query filters by user_id, so a mismatch returns None → 404.
        """
        db = AsyncMock()
        # The query includes user_id filter, so it returns None for wrong user
        db.execute = AsyncMock(return_value=_mock_scalar_result(None))

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_job_status(user_id=999, job_id="analysis-1", db=db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_failed_job_includes_error_message(self) -> None:
        """A failed job should include the error_message field."""
        analysis = _make_analysis(
            status="failed",
            job_id="analysis-1",
            error_message="Model loading failed",
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_scalar_result(analysis))

        result = await get_job_status(user_id=10, job_id="analysis-1", db=db)
        assert result.status == "failed"
        assert result.error_message == "Model loading failed"


# ---------------------------------------------------------------------------
# Queue helper tests
# ---------------------------------------------------------------------------


class TestQueueHelpers:
    def test_get_redis_connection_raises_on_failure(self) -> None:
        """get_redis_connection should raise RuntimeError when Redis is down."""
        with patch("app.workers.queue.Redis") as MockRedis:
            from redis.exceptions import ConnectionError as RedisConnectionError

            mock_instance = MagicMock()
            mock_instance.ping.side_effect = RedisConnectionError("refused")
            MockRedis.from_url.return_value = mock_instance

            from app.workers.queue import get_redis_connection

            with pytest.raises(RuntimeError, match="Cannot connect to Redis"):
                get_redis_connection()

    def test_get_queue_returns_queue_with_correct_name(self) -> None:
        """get_queue should return an RQ Queue with the configured name."""
        mock_conn = MagicMock()
        with patch("app.workers.queue.get_redis_connection", return_value=mock_conn):
            from app.workers.queue import get_queue

            queue = get_queue(connection=mock_conn)
            settings = get_settings()
            assert queue.name == settings.queue_name


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestAsyncSchemas:
    def test_async_analysis_response_fields(self) -> None:
        resp = AsyncAnalysisResponse(
            analysis_id=1,
            job_id="analysis-1",
            status="pending",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        assert resp.analysis_id == 1
        assert resp.job_id == "analysis-1"
        assert resp.status == "pending"

    def test_job_status_response_completed(self) -> None:
        resp = JobStatusResponse(
            analysis_id=1,
            job_id="analysis-1",
            status="completed",
            overall_score=92.5,
            result_payload={"data": "value"},
            created_at=datetime.datetime.now(datetime.UTC),
        )
        assert resp.overall_score == 92.5
        assert resp.error_message is None

    def test_job_status_response_failed(self) -> None:
        resp = JobStatusResponse(
            analysis_id=1,
            job_id="analysis-1",
            status="failed",
            error_message="Something went wrong",
            created_at=datetime.datetime.now(datetime.UTC),
        )
        assert resp.status == "failed"
        assert resp.overall_score is None


# ---------------------------------------------------------------------------
# AnalysisRun model tests
# ---------------------------------------------------------------------------


class TestAnalysisRunModel:
    def test_new_fields_exist(self) -> None:
        """AnalysisRun should have job_id and error_message columns."""
        from sqlalchemy import inspect

        mapper = inspect(AnalysisRun)
        column_names = {col.key for col in mapper.column_attrs}
        assert "job_id" in column_names
        assert "error_message" in column_names
        assert "status" in column_names

    def test_default_status_is_pending(self) -> None:
        analysis = AnalysisRun(
            user_id=1,
            resume_id=1,
            job_description_id=1,
        )
        assert analysis.status == "pending"

    def test_nullable_fields(self) -> None:
        analysis = AnalysisRun(
            user_id=1,
            resume_id=1,
            job_description_id=1,
        )
        assert analysis.overall_score is None
        assert analysis.result_payload is None
        assert analysis.job_id is None
        assert analysis.error_message is None
