"""Async analysis service: enqueue jobs and poll status.

Bridges the FastAPI async world with the RQ synchronous queue.
All database operations are async via SQLAlchemy.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from rq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.metrics import jobs_cancelled_total, jobs_created_total, set_queue_depth
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.job_profile import JobProfile
from app.models.resume import Resume
from app.models.user import User
from app.workers.job_handlers import (
    run_analysis_job,
    run_job_targeted_analysis_job,
    run_resume_analysis_job,
)
from app.workers.queue import fetch_job, get_queue, get_queue_depth, get_redis_connection

logger = logging.getLogger(__name__)


IN_PROGRESS_STATUSES = ("pending", "queued", "running", "processing")
TERMINAL_STATUSES = (
    "completed",
    "failed",
    "cancelled",
    "expired",
    "timeout",
    "budget_exceeded",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _last_activity_at(analysis: AnalysisRun) -> datetime:
    """Best-effort activity timestamp for stale-lock detection."""
    timestamp = analysis.started_at or analysis.created_at or _utc_now()
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp


def _analysis_ttl_expiry(settings) -> datetime:
    return _utc_now() + timedelta(seconds=max(1, settings.job_ttl_seconds))


def _retry_policy(settings) -> Retry | None:
    retries = max(0, settings.max_attempts - 1)
    if retries == 0:
        return None

    base = max(1, settings.retry_backoff_base_seconds)
    intervals = [base * (2**idx) for idx in range(retries)]
    return Retry(max=retries, interval=intervals)


def _enforce_max_input_chars(
    settings,
    *,
    resume_text: str | None,
    jd_text: str | None = None,
) -> None:
    max_chars = max(1, settings.max_input_chars)
    if resume_text and len(resume_text) > max_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Resume text exceeds MAX_INPUT_CHARS={max_chars}. "
                "Please shorten the resume before analysis."
            ),
        )
    if jd_text and len(jd_text) > max_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Job description exceeds MAX_INPUT_CHARS={max_chars}. "
                "Please shorten the job description before analysis."
            ),
        )


def _enforce_queue_backpressure(settings) -> None:
    try:
        conn = get_redis_connection()
        depth = get_queue_depth(connection=conn)
        set_queue_depth(depth)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Analysis queue is currently unavailable. Please try again later.",
        ) from exc

    if depth >= settings.max_queue_depth:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Analysis queue is at capacity ({depth}/{settings.max_queue_depth}). "
                "Please retry in 30-60 seconds."
            ),
        )


async def _reset_stale_inflight(
    db: AsyncSession,
    analyses: list[AnalysisRun],
    *,
    stale_after_minutes: int,
    stale_reason: str,
) -> list[AnalysisRun]:
    """Mark stale in-flight analyses as failed and return remaining active rows."""
    cutoff = _utc_now() - timedelta(minutes=stale_after_minutes)
    stale_ids: list[int] = []
    active: list[AnalysisRun] = []

    for analysis in analyses:
        if _last_activity_at(analysis) < cutoff:
            analysis.status = "failed"
            analysis.error_message = stale_reason
            analysis.last_error = stale_reason
            analysis.completed_at = _utc_now()
            stale_ids.append(analysis.id)
        else:
            active.append(analysis)

    if stale_ids:
        await db.commit()
        logger.warning(
            "Reset stale in-flight analyses",
            extra={
                "analysis_ids": stale_ids,
                "stale_after_minutes": stale_after_minutes,
            },
        )

    return active


async def _mark_analysis_enqueue_failed(
    db: AsyncSession,
    analysis_id: int,
    error_message: str,
) -> None:
    """Persist FAILED state if enqueueing fails after DB row creation."""
    await db.rollback()
    analysis = await db.get(AnalysisRun, analysis_id)
    if analysis is None:
        return
    analysis.status = "failed"
    analysis.last_error = error_message
    analysis.error_message = error_message
    analysis.completed_at = _utc_now()
    await db.commit()


def _new_analysis_run(
    *,
    settings,
    user_id: int,
    resume_id: int,
    status: str,
    job_description_id: int | None = None,
    job_profile_id: int | None = None,
) -> AnalysisRun:
    return AnalysisRun(
        user_id=user_id,
        resume_id=resume_id,
        job_description_id=job_description_id,
        job_profile_id=job_profile_id,
        status=status,
        expires_at=_analysis_ttl_expiry(settings),
        cancelled=False,
        attempts=0,
        max_attempts=settings.max_attempts,
        llm_calls_used=0,
        cost_estimate_usd=0.0,
    )


def _job_timeout_seconds(settings) -> int:
    return max(1, settings.job_hard_timeout_seconds)


def _increment_jobs_created() -> None:
    jobs_created_total.inc()


# ---------------------------------------------------------------------------
# Standalone resume analysis (new)
# ---------------------------------------------------------------------------


async def enqueue_resume_analysis(
    user_id: int,
    resume_id: int,
    db: AsyncSession,
) -> AnalysisRun:
    """Validate ownership, create a queued AnalysisRun, and enqueue an RQ job.

    No job_description_id required. Uses the standalone resume analyzer.
    """
    settings = get_settings()

    # Validate ownership
    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    _enforce_max_input_chars(settings, resume_text=resume.parsed_text)
    _enforce_queue_backpressure(settings)

    # Check for existing in-flight analysis
    existing = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.resume_id == resume_id,
            AnalysisRun.user_id == user_id,
            AnalysisRun.job_description_id.is_(None),
            AnalysisRun.status.in_(IN_PROGRESS_STATUSES),
        )
    )
    inflight = list(existing.scalars().all())
    active_inflight = await _reset_stale_inflight(
        db,
        inflight,
        stale_after_minutes=settings.analysis_stale_after_minutes,
        stale_reason="stale lock reset",
    )
    if active_inflight:
        raise HTTPException(
            status_code=409,
            detail="An analysis is already in progress for this resume",
        )

    # Create queued AnalysisRun (no job_description_id)
    analysis = _new_analysis_run(
        settings=settings,
        user_id=user_id,
        resume_id=resume_id,
        status="queued",
    )
    db.add(analysis)
    await db.flush()
    analysis_id = int(analysis.id)
    await db.commit()
    _increment_jobs_created()

    if analysis.created_at is None:
        await db.refresh(analysis, attribute_names=["created_at"])
    logger.info(
        "Queued resume analysis record created",
        extra={"analysis_id": analysis_id, "status": analysis.status},
    )

    # Enqueue RQ job
    try:
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        rq_job = queue.enqueue(
            run_resume_analysis_job,
            analysis_id,
            job_id=f"resume-analysis-{analysis_id}",
            retry=_retry_policy(settings),
            job_timeout=_job_timeout_seconds(settings),
        )
        analysis.job_id = rq_job.id
        await db.commit()
        logger.info(
            "Resume analysis job enqueued",
            extra={"analysis_id": analysis_id, "job_id": rq_job.id},
        )
    except Exception as exc:
        await _mark_analysis_enqueue_failed(
            db,
            analysis_id=analysis_id,
            error_message=f"Failed to enqueue resume analysis: {exc}",
        )
        if isinstance(exc, RuntimeError):
            raise HTTPException(
                status_code=503,
                detail="Analysis queue is currently unavailable. Please try again later.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Failed to enqueue analysis job. Please try again.",
        ) from exc

    return analysis


# ---------------------------------------------------------------------------
# Job-targeted analysis (Resume × JobProfile)
# ---------------------------------------------------------------------------


async def enqueue_job_targeted_analysis(
    user_id: int,
    resume_id: int,
    job_profile_id: int,
    db: AsyncSession,
) -> AnalysisRun:
    """Validate ownership, create a queued AnalysisRun with job_profile_id, and enqueue."""
    settings = get_settings()

    # Validate resume ownership
    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    _enforce_max_input_chars(settings, resume_text=resume.parsed_text)
    _enforce_queue_backpressure(settings)

    # Validate job profile access (user-owned or template)
    profile_result = await db.execute(
        select(JobProfile).where(
            JobProfile.id == job_profile_id,
            (JobProfile.user_id == user_id) | (JobProfile.is_template.is_(True)),
        )
    )
    if profile_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job profile not found")

    # Check for in-flight targeted analysis with same resume + profile
    existing = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.resume_id == resume_id,
            AnalysisRun.user_id == user_id,
            AnalysisRun.job_profile_id == job_profile_id,
            AnalysisRun.status.in_(IN_PROGRESS_STATUSES),
        )
    )
    inflight = list(existing.scalars().all())
    active_inflight = await _reset_stale_inflight(
        db,
        inflight,
        stale_after_minutes=settings.analysis_stale_after_minutes,
        stale_reason="stale lock reset",
    )
    if active_inflight:
        raise HTTPException(
            status_code=409,
            detail="A targeted analysis is already in progress for this resume and profile",
        )

    # Create queued AnalysisRun
    analysis = _new_analysis_run(
        settings=settings,
        user_id=user_id,
        resume_id=resume_id,
        job_profile_id=job_profile_id,
        status="queued",
    )
    db.add(analysis)
    await db.flush()
    analysis_id = int(analysis.id)

    # Update user's last-used profile
    user_result = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_result.scalar_one_or_none()
    if user_obj is not None:
        user_obj.last_job_profile_id = job_profile_id
    await db.commit()
    _increment_jobs_created()

    if analysis.created_at is None:
        await db.refresh(analysis, attribute_names=["created_at"])
    logger.info(
        "Queued targeted analysis record created",
        extra={
            "analysis_id": analysis_id,
            "status": analysis.status,
            "job_profile_id": job_profile_id,
        },
    )

    # Enqueue RQ job
    try:
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        rq_job = queue.enqueue(
            run_job_targeted_analysis_job,
            analysis_id,
            job_id=f"targeted-analysis-{analysis_id}",
            retry=_retry_policy(settings),
            job_timeout=_job_timeout_seconds(settings),
        )
        analysis.job_id = rq_job.id
        await db.commit()
        logger.info(
            "Job-targeted analysis enqueued",
            extra={
                "analysis_id": analysis_id,
                "job_id": rq_job.id,
                "job_profile_id": job_profile_id,
            },
        )
    except Exception as exc:
        await _mark_analysis_enqueue_failed(
            db,
            analysis_id=analysis_id,
            error_message=f"Failed to enqueue targeted analysis: {exc}",
        )
        if isinstance(exc, RuntimeError):
            raise HTTPException(
                status_code=503,
                detail="Analysis queue is currently unavailable. Please try again later.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Failed to enqueue targeted analysis. Please try again.",
        ) from exc

    return analysis


# ---------------------------------------------------------------------------
# JD-based analysis (existing, preserved)
# ---------------------------------------------------------------------------


async def enqueue_analysis(
    user_id: int,
    resume_id: int,
    job_description_id: int,
    db: AsyncSession,
) -> AnalysisRun:
    """Validate ownership, create a pending AnalysisRun, and enqueue an RQ job."""
    settings = get_settings()

    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    jd_result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == job_description_id, JobDescription.user_id == user_id
        )
    )
    job_description = jd_result.scalar_one_or_none()
    if job_description is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    _enforce_max_input_chars(
        settings,
        resume_text=resume.parsed_text,
        jd_text=job_description.description_text,
    )
    _enforce_queue_backpressure(settings)

    analysis = _new_analysis_run(
        settings=settings,
        user_id=user_id,
        resume_id=resume_id,
        job_description_id=job_description_id,
        status="pending",
    )
    db.add(analysis)
    await db.flush()
    analysis_id = int(analysis.id)
    await db.commit()
    _increment_jobs_created()

    if analysis.created_at is None:
        await db.refresh(analysis, attribute_names=["created_at"])
    logger.info(
        "Queued JD-based analysis record created",
        extra={"analysis_id": analysis_id, "status": analysis.status},
    )

    try:
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        rq_job = queue.enqueue(
            run_analysis_job,
            analysis_id,
            job_id=f"analysis-{analysis_id}",
            retry=_retry_policy(settings),
            job_timeout=_job_timeout_seconds(settings),
        )
        analysis.job_id = rq_job.id
        await db.commit()
        logger.info(
            "Analysis job enqueued",
            extra={"analysis_id": analysis_id, "job_id": rq_job.id},
        )
    except Exception as exc:
        await _mark_analysis_enqueue_failed(
            db,
            analysis_id=analysis_id,
            error_message=f"Failed to enqueue JD analysis: {exc}",
        )
        if isinstance(exc, RuntimeError):
            raise HTTPException(
                status_code=503,
                detail="Analysis queue is currently unavailable. Please try again later.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Failed to enqueue analysis job. Please try again.",
        ) from exc

    return analysis


async def cancel_analysis_job(
    *,
    user_id: int,
    analysis_id: int,
    db: AsyncSession,
) -> AnalysisRun:
    """Cancel an analysis job (idempotent)."""
    result = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.id == analysis_id,
            AnalysisRun.user_id == user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    prior_status = analysis.status
    analysis.cancelled = True

    if analysis.status not in TERMINAL_STATUSES:
        analysis.status = "cancelled"
        analysis.completed_at = analysis.completed_at or _utc_now()
        analysis.last_error = "Cancelled by user request"
        analysis.error_message = "Cancelled by user request"

    if prior_status != "cancelled" and analysis.status == "cancelled":
        jobs_cancelled_total.inc()

    await db.commit()
    await db.refresh(analysis)
    return analysis


# ---------------------------------------------------------------------------
# Status polling & retrieval
# ---------------------------------------------------------------------------


async def get_job_status(
    user_id: int,
    job_id: str,
    db: AsyncSession,
) -> AnalysisRun:
    """Retrieve an AnalysisRun by job_id with access control."""
    result = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.job_id == job_id,
            AnalysisRun.user_id == user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    if analysis.status in IN_PROGRESS_STATUSES:
        analysis = await _sync_rq_status(analysis, db)

    return analysis


async def get_analysis_by_id(
    user_id: int,
    analysis_id: int,
    db: AsyncSession,
) -> AnalysisRun | None:
    """Retrieve an AnalysisRun by ID with access control."""
    result = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.id == analysis_id,
            AnalysisRun.user_id == user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        return None

    if analysis.status in IN_PROGRESS_STATUSES:
        analysis = await _sync_rq_status(analysis, db)

    return analysis


async def get_latest_analysis_for_resume(
    user_id: int,
    resume_id: int,
    db: AsyncSession,
) -> AnalysisRun | None:
    """Get the latest standalone analysis for a resume."""
    result = await db.execute(
        select(AnalysisRun)
        .where(
            AnalysisRun.resume_id == resume_id,
            AnalysisRun.user_id == user_id,
            AnalysisRun.job_description_id.is_(None),
        )
        .order_by(AnalysisRun.id.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        return None

    if analysis.status in IN_PROGRESS_STATUSES:
        analysis = await _sync_rq_status(analysis, db)

    return analysis


async def get_analysis_history_for_resume(
    user_id: int,
    resume_id: int,
    db: AsyncSession,
    *,
    limit: int = 10,
) -> list[AnalysisRun]:
    """Get recent targeted analysis runs for a resume."""
    result = await db.execute(
        select(AnalysisRun)
        .where(
            AnalysisRun.resume_id == resume_id,
            AnalysisRun.user_id == user_id,
            AnalysisRun.job_description_id.is_(None),
            AnalysisRun.job_profile_id.is_not(None),
        )
        .order_by(AnalysisRun.id.desc())
        .limit(limit)
    )
    analyses = list(result.scalars().all())
    synced: list[AnalysisRun] = []
    for analysis in analyses:
        if analysis.status in IN_PROGRESS_STATUSES:
            analysis = await _sync_rq_status(analysis, db)
        synced.append(analysis)
    return synced


async def _sync_rq_status(analysis: AnalysisRun, db: AsyncSession) -> AnalysisRun:
    """Update AnalysisRun status from the live RQ job state."""
    if not analysis.job_id:
        return analysis

    try:
        rq_job = fetch_job(analysis.job_id)
    except Exception:
        return analysis

    if rq_job is None:
        return analysis

    rq_status = rq_job.get_status()

    status_map = {
        "queued": "queued",
        "started": "processing",
        "finished": "completed",
        "failed": "failed",
        "stopped": "failed",
        "canceled": "cancelled",
        "cancelled": "cancelled",
    }

    new_status = status_map.get(str(rq_status), analysis.status)

    if new_status != analysis.status:
        prior_status = analysis.status
        analysis.status = new_status
        if new_status in TERMINAL_STATUSES and analysis.completed_at is None:
            analysis.completed_at = _utc_now()
        if new_status == "failed" and not analysis.error_message:
            analysis.error_message = "Job failed in worker"
        if new_status == "cancelled" and prior_status != "cancelled":
            jobs_cancelled_total.inc()
        await db.commit()
        await db.refresh(analysis)

    return analysis
