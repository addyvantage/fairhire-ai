from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import pytest

from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.job_profile import JobProfile
from app.models.resume import Resume
from app.services.async_analysis import enqueue_analysis
from app.workers.job_handlers import (
    TransientJobError,
    run_analysis_job,
    run_job_targeted_analysis_job,
    run_resume_analysis_job,
)


def _settings(**overrides):
    base = {
        "analysis_stale_after_minutes": 15,
        "max_input_chars": 10000,
        "max_queue_depth": 200,
        "job_ttl_seconds": 1800,
        "max_attempts": 3,
        "retry_backoff_base_seconds": 10,
        "job_hard_timeout_seconds": 300,
        "job_step_timeout_seconds": 120,
        "max_llm_calls_per_job": 5,
        "estimated_cost_per_call": 0.002,
        "studio_export_dir": "app/storage/exports",
        "open_weights_reasoner_model_path": "",
        "open_weights_reasoner_max_tokens": 320,
        "open_weights_reasoner_temperature": 0.1,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _mock_scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _analysis(**overrides):
    now = datetime.datetime.now(datetime.UTC)
    values = {
        "id": 1,
        "user_id": 10,
        "resume_id": 100,
        "job_description_id": 200,
        "job_profile_id": None,
        "status": "queued",
        "job_id": "analysis-1",
        "overall_score": None,
        "result_payload": None,
        "error_message": None,
        "last_error": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "expires_at": now + datetime.timedelta(minutes=30),
        "cancelled": False,
        "attempts": 0,
        "max_attempts": 3,
        "llm_calls_used": 0,
        "cost_estimate_usd": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _resume(**overrides):
    values = {
        "id": 100,
        "parsed_text": "python backend engineer",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _job_description(**overrides):
    values = {
        "id": 200,
        "description_text": "Build resilient APIs and async services",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _job_profile(**overrides):
    values = {
        "id": 300,
        "title": "Backend Engineer",
        "normalized_title": "backend engineer",
        "seniority_level": "mid",
        "required_skills": ["python"],
        "optional_skills": ["redis"],
        "responsibilities": ["build APIs"],
        "years_experience_min": 2,
        "years_experience_max": 5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeSession:
    def __init__(self, rows: dict[tuple[type, int], object]):
        self._rows = rows

    def get(self, model, row_id):
        return self._rows.get((model, row_id))

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def test_enqueue_backpressure_returns_429() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(_resume()),
            _mock_scalar_result(_job_description()),
        ]
    )
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch("app.services.async_analysis.get_settings", return_value=_settings(max_queue_depth=1)),
        patch("app.services.async_analysis.get_redis_connection", return_value=MagicMock()),
        patch("app.services.async_analysis.get_queue_depth", return_value=1),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                enqueue_analysis(user_id=10, resume_id=100, job_description_id=200, db=db)
            )

    assert exc_info.value.status_code == 429
    assert "capacity" in str(exc_info.value.detail).lower()
    db.add.assert_not_called()


def test_worker_cancelled_job_stops_immediately() -> None:
    analysis = _analysis(cancelled=True)
    session = _FakeSession({(AnalysisRun, 1): analysis})

    with (
        patch("app.workers.job_handlers.get_settings", return_value=_settings()),
        patch("app.workers.job_handlers.SyncSessionLocal", return_value=session),
    ):
        result = run_resume_analysis_job(1)

    assert result["status"] == "cancelled"
    assert analysis.status == "cancelled"


def test_worker_expired_job_stops_immediately() -> None:
    analysis = _analysis(expires_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1))
    session = _FakeSession({(AnalysisRun, 1): analysis})

    with (
        patch("app.workers.job_handlers.get_settings", return_value=_settings()),
        patch("app.workers.job_handlers.SyncSessionLocal", return_value=session),
    ):
        result = run_resume_analysis_job(1)

    assert result["status"] == "expired"
    assert analysis.status == "expired"


def test_transient_failure_marks_queued_and_increments_attempts() -> None:
    analysis = _analysis(status="queued", attempts=0, max_attempts=3)
    session = _FakeSession(
        {
            (AnalysisRun, 1): analysis,
            (Resume, 100): _resume(),
            (JobDescription, 200): _job_description(),
        }
    )

    class _BrokenOrchestrator:
        async def analyze(self, _resume_text: str, _jd_text: str):
            raise ConnectionError("temporary network failure")

    with (
        patch("app.workers.job_handlers.get_settings", return_value=_settings()),
        patch("app.workers.job_handlers.SyncSessionLocal", return_value=session),
        patch("app.services.analysis_orchestrator.AnalysisOrchestrator", _BrokenOrchestrator),
    ):
        with pytest.raises(TransientJobError):
            run_analysis_job(1)

    assert analysis.status == "queued"
    assert analysis.attempts == 1
    assert analysis.last_error is not None


def test_budget_cap_marks_job_budget_exceeded() -> None:
    analysis = _analysis(job_profile_id=300, llm_calls_used=0)
    session = _FakeSession(
        {
            (AnalysisRun, 1): analysis,
            (Resume, 100): _resume(),
            (JobProfile, 300): _job_profile(),
        }
    )

    class _BudgetConsumingScorer:
        def score(self, _resume_text: str, _profile_data):
            from app.services.llm_budget import consume_llm_call

            consume_llm_call()
            raise AssertionError("Budget guard should stop before returning a scorer result")

    with (
        patch("app.workers.job_handlers.get_settings", return_value=_settings(max_llm_calls_per_job=0)),
        patch("app.workers.job_handlers.SyncSessionLocal", return_value=session),
        patch("app.services.job_targeted_scorer.JobTargetedScorer", _BudgetConsumingScorer),
    ):
        result = run_job_targeted_analysis_job(1)

    assert result["status"] == "budget_exceeded"
    assert analysis.status == "budget_exceeded"


def test_retry_policy_uses_exponential_backoff() -> None:
    from app.services.async_analysis import _retry_policy

    policy = _retry_policy(_settings(max_attempts=4, retry_backoff_base_seconds=3))

    assert policy is not None
    assert policy.max == 3
    assert policy.intervals == [3, 6, 12]
