"""RQ job handler functions.

These functions execute inside the RQ worker process (synchronous context).
They create their own DB sessions and run the async orchestrator via
``asyncio.run()``.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.resume_analyzer import analyze_resume

logger = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 2000


# ---------------------------------------------------------------------------
# Standalone resume analysis job (new)
# ---------------------------------------------------------------------------


def run_resume_analysis_job(analysis_id: int) -> dict:
    """Execute standalone resume analysis for the given AnalysisRun.

    Called by RQ in a worker process. Manages its own DB session lifecycle.
    Returns the result payload dict on success.
    """
    logger.info("Starting resume analysis job", extra={"analysis_id": analysis_id})
    try:
        result = asyncio.run(_execute_resume_analysis(analysis_id))
        logger.info("Resume analysis job completed", extra={"analysis_id": analysis_id})
        return result
    except Exception as exc:
        logger.error(
            "Resume analysis job failed",
            extra={"analysis_id": analysis_id, "error": str(exc)},
            exc_info=True,
        )
        asyncio.run(_mark_failed(analysis_id, exc))
        raise


async def _execute_resume_analysis(analysis_id: int) -> dict:
    """Core async execution for standalone resume analysis."""
    async with SessionLocal() as db:
        analysis = await _load_analysis(db, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        # Transition to processing
        analysis.status = "processing"
        analysis.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Load resume
        resume = await _load_entity(db, Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        # Run standalone analysis (synchronous, CPU-bound heuristics)
        output = analyze_resume(resume.parsed_text)

        # Persist results
        analysis.overall_score = output["match_score"]
        analysis.result_payload = output["extracted_metadata"]
        analysis.status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.error_message = None
        await db.commit()

        return output


# ---------------------------------------------------------------------------
# JD-based analysis job (existing, preserved)
# ---------------------------------------------------------------------------


def run_analysis_job(analysis_id: int) -> dict:
    """Execute a full analysis pipeline for the given AnalysisRun.

    Called by RQ in a worker process.  Manages its own DB session lifecycle.

    Returns the result payload dict on success.
    On failure, persists error state and re-raises so RQ can retry.
    """
    logger.info("Starting analysis job", extra={"analysis_id": analysis_id})
    try:
        result = asyncio.run(_execute_analysis(analysis_id))
        logger.info("Analysis job completed", extra={"analysis_id": analysis_id})
        return result
    except Exception as exc:
        logger.error(
            "Analysis job failed",
            extra={"analysis_id": analysis_id, "error": str(exc)},
            exc_info=True,
        )
        # Persist the failure state before re-raising for RQ retry.
        asyncio.run(_mark_failed(analysis_id, exc))
        raise


async def _execute_analysis(analysis_id: int) -> dict:
    """Core async analysis execution."""
    async with SessionLocal() as db:
        analysis = await _load_analysis(db, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        # Transition to running
        analysis.status = "running"
        await db.commit()

        # Load related entities
        resume = await _load_entity(db, Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        jd = await _load_entity(db, JobDescription, analysis.job_description_id)
        if jd is None:
            raise ValueError(f"JobDescription {analysis.job_description_id} not found")

        # Run the orchestrator
        orchestrator = AnalysisOrchestrator()
        output = await orchestrator.analyze(resume.parsed_text, jd.description_text)

        # Persist results
        analysis.overall_score = output["overall_score"]
        analysis.result_payload = {
            "semantic_match": output["semantic_match"].model_dump(),
            "ats_compatibility": output["ats_compatibility"].model_dump(),
            "bias_detection": output["bias_detection"].model_dump(),
            "extracted_resume_skills": output["extracted_resume_skills"],
            "extracted_jd_skills": output["extracted_jd_skills"],
        }
        analysis.status = "completed"
        analysis.error_message = None
        await db.commit()

        return analysis.result_payload


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _mark_failed(analysis_id: int, exc: Exception) -> None:
    """Persist failure state on the AnalysisRun."""
    try:
        async with SessionLocal() as db:
            analysis = await _load_analysis(db, analysis_id)
            if analysis is not None:
                analysis.status = "failed"
                analysis.completed_at = datetime.now(timezone.utc)
                error_text = traceback.format_exception_only(type(exc), exc)
                analysis.error_message = "".join(error_text)[:_MAX_ERROR_LENGTH]
                await db.commit()
    except Exception:
        logger.error(
            "Failed to mark analysis as failed",
            extra={"analysis_id": analysis_id},
            exc_info=True,
        )


async def _load_analysis(db: AsyncSession, analysis_id: int) -> AnalysisRun | None:
    result = await db.execute(
        select(AnalysisRun).where(AnalysisRun.id == analysis_id)
    )
    return result.scalar_one_or_none()


async def _load_entity(db: AsyncSession, model: type, entity_id: int):  # type: ignore[type-arg]
    result = await db.execute(select(model).where(model.id == entity_id))
    return result.scalar_one_or_none()
