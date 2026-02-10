"""RQ job handler functions.

These functions execute inside the RQ worker process (synchronous context).
They use a **synchronous** SQLAlchemy session — NOT the async one used by
the FastAPI server — to avoid the ``MissingGreenlet`` error that occurs when
mixing asyncio + SQLAlchemy async inside RQ's sync worker loop.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

from app.db.sync_session import SyncSessionLocal
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.services.resume_analyzer import analyze_resume

logger = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 2000


# ---------------------------------------------------------------------------
# Standalone resume analysis job (new)
# ---------------------------------------------------------------------------


def run_resume_analysis_job(analysis_id: int) -> dict:
    """Execute standalone resume analysis for the given AnalysisRun.

    Called by RQ in a worker process. Fully synchronous — no asyncio, no
    async DB sessions. Returns the result payload dict on success.
    """
    logger.info("Starting resume analysis job", extra={"analysis_id": analysis_id})
    db = SyncSessionLocal()
    try:
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        # Transition to processing
        analysis.status = "processing"
        analysis.started_at = datetime.now(timezone.utc)
        db.commit()

        # Load resume
        resume = db.get(Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        # Run standalone analysis (CPU-bound heuristics)
        output = analyze_resume(resume.parsed_text)

        # Persist results
        analysis.overall_score = output["match_score"]
        analysis.result_payload = output["extracted_metadata"]
        analysis.status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.error_message = None
        db.commit()

        logger.info("Resume analysis job completed", extra={"analysis_id": analysis_id})
        return output

    except Exception as exc:
        logger.error(
            "Resume analysis job failed",
            extra={"analysis_id": analysis_id, "error": str(exc)},
            exc_info=True,
        )
        _mark_failed_sync(db, analysis_id, exc)
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# JD-based analysis job (existing, also converted to sync DB)
# ---------------------------------------------------------------------------


def run_analysis_job(analysis_id: int) -> dict:
    """Execute a full JD-based analysis pipeline for the given AnalysisRun.

    Called by RQ in a worker process. Uses sync DB for entity loading;
    the AnalysisOrchestrator is still async internally (run via asyncio.run).
    """
    logger.info("Starting analysis job", extra={"analysis_id": analysis_id})
    db = SyncSessionLocal()
    try:
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        # Transition to processing
        analysis.status = "processing"
        analysis.started_at = datetime.now(timezone.utc)
        db.commit()

        # Load related entities
        resume = db.get(Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        jd = db.get(JobDescription, analysis.job_description_id)
        if jd is None:
            raise ValueError(f"JobDescription {analysis.job_description_id} not found")

        # The orchestrator is async (uses embeddings), so run it in a
        # fresh event loop. This is safe because it does NOT touch
        # SQLAlchemy — it only returns plain dicts/pydantic models.
        import asyncio
        from app.services.analysis_orchestrator import AnalysisOrchestrator

        orchestrator = AnalysisOrchestrator()
        output = asyncio.run(
            orchestrator.analyze(resume.parsed_text, jd.description_text)
        )

        # Persist results (sync DB)
        analysis.overall_score = output["overall_score"]
        analysis.result_payload = {
            "semantic_match": output["semantic_match"].model_dump(),
            "ats_compatibility": output["ats_compatibility"].model_dump(),
            "bias_detection": output["bias_detection"].model_dump(),
            "extracted_resume_skills": output["extracted_resume_skills"],
            "extracted_jd_skills": output["extracted_jd_skills"],
        }
        analysis.status = "completed"
        analysis.completed_at = datetime.now(timezone.utc)
        analysis.error_message = None
        db.commit()

        logger.info("Analysis job completed", extra={"analysis_id": analysis_id})
        return analysis.result_payload

    except Exception as exc:
        logger.error(
            "Analysis job failed",
            extra={"analysis_id": analysis_id, "error": str(exc)},
            exc_info=True,
        )
        _mark_failed_sync(db, analysis_id, exc)
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mark_failed_sync(db, analysis_id: int, exc: Exception) -> None:
    """Persist failure state on the AnalysisRun using the existing session."""
    try:
        # Roll back any partial transaction first
        db.rollback()
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is not None:
            analysis.status = "failed"
            analysis.completed_at = datetime.now(timezone.utc)
            error_text = traceback.format_exception_only(type(exc), exc)
            analysis.error_message = "".join(error_text)[:_MAX_ERROR_LENGTH]
            db.commit()
    except Exception:
        logger.error(
            "Failed to mark analysis as failed",
            extra={"analysis_id": analysis_id},
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
