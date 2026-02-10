"""Async analysis service: enqueue jobs and poll status.

Bridges the FastAPI async world with the RQ synchronous queue.
All database operations are async via SQLAlchemy.
"""

from __future__ import annotations

import logging

from rq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.core.config import get_settings
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.workers.job_handlers import run_analysis_job, run_resume_analysis_job
from app.workers.queue import fetch_job, get_queue, get_redis_connection

logger = logging.getLogger(__name__)


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
    # Validate ownership
    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    if resume_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Check for existing in-flight analysis
    existing = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.resume_id == resume_id,
            AnalysisRun.user_id == user_id,
            AnalysisRun.job_description_id.is_(None),
            AnalysisRun.status.in_(["queued", "processing"]),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="An analysis is already in progress for this resume",
        )

    # Create queued AnalysisRun (no job_description_id)
    analysis = AnalysisRun(
        user_id=user_id,
        resume_id=resume_id,
        status="queued",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    # Enqueue RQ job
    settings = get_settings()
    try:
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        rq_job = queue.enqueue(
            run_resume_analysis_job,
            analysis.id,
            job_id=f"resume-analysis-{analysis.id}",
            retry=Retry(
                max=settings.async_job_retry_max,
                interval=settings.async_job_retry_interval,
            ),
            job_timeout="5m",
        )
        analysis.job_id = rq_job.id
        await db.commit()
        await db.refresh(analysis)
        logger.info(
            "Resume analysis job enqueued",
            extra={"analysis_id": analysis.id, "job_id": rq_job.id},
        )
    except RuntimeError as exc:
        analysis.status = "failed"
        analysis.error_message = f"Queue unavailable: {exc}"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Analysis queue is currently unavailable. Please try again later.",
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
    resume_result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    if resume_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    jd_result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == job_description_id, JobDescription.user_id == user_id
        )
    )
    if jd_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    analysis = AnalysisRun(
        user_id=user_id,
        resume_id=resume_id,
        job_description_id=job_description_id,
        status="pending",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    settings = get_settings()
    try:
        conn = get_redis_connection()
        queue = get_queue(connection=conn)
        rq_job = queue.enqueue(
            run_analysis_job,
            analysis.id,
            job_id=f"analysis-{analysis.id}",
            retry=Retry(
                max=settings.async_job_retry_max,
                interval=settings.async_job_retry_interval,
            ),
            job_timeout="5m",
        )
        analysis.job_id = rq_job.id
        await db.commit()
        await db.refresh(analysis)
        logger.info(
            "Analysis job enqueued",
            extra={"analysis_id": analysis.id, "job_id": rq_job.id},
        )
    except RuntimeError as exc:
        analysis.status = "failed"
        analysis.error_message = f"Queue unavailable: {exc}"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Analysis queue is currently unavailable. Please try again later.",
        ) from exc

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

    if analysis.status in ("pending", "queued", "running", "processing"):
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

    if analysis.status in ("queued", "processing"):
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

    if analysis.status in ("queued", "processing"):
        analysis = await _sync_rq_status(analysis, db)

    return analysis


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
        "canceled": "failed",
    }

    new_status = status_map.get(str(rq_status), analysis.status)

    if new_status != analysis.status:
        analysis.status = new_status
        if new_status == "failed" and not analysis.error_message:
            analysis.error_message = "Job failed in worker"
        await db.commit()
        await db.refresh(analysis)

    return analysis
