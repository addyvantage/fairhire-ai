"""RQ job handler functions.

These functions execute inside the RQ worker process (synchronous context).
They use a synchronous SQLAlchemy session to avoid async/sync boundary issues.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
import traceback

from rq import get_current_job

from app.core.config import get_settings
from app.core.metrics import (
    jobs_cancelled_total,
    jobs_expired_total,
    jobs_retried_total,
    jobs_timed_out_total,
    observe_job_duration,
)
from app.db.sync_session import SyncSessionLocal
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.resume_studio import ResumeStudioExport, ResumeStudioVersion
from app.services.llm_budget import (
    BudgetExceededError,
    LLMCallTracker,
    activate_llm_call_tracker,
)
from app.services.resume_analyzer import analyze_resume

logger = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 2000
_TERMINAL_ANALYSIS_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "expired",
    "timeout",
    "budget_exceeded",
}
_TRANSIENT_HINTS = (
    "timeout",
    "temporarily unavailable",
    "connection",
    "rate limit",
    "429",
    "502",
    "503",
    "504",
)


class TransientJobError(RuntimeError):
    """Raised to signal RQ should retry the job."""


class JobTimeoutError(RuntimeError):
    """Raised when job deadlines are exceeded."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_id() -> str | None:
    current = get_current_job()
    return current.id if current is not None else None


def _estimate_cost(llm_calls_used: int, estimated_cost_per_call: float) -> float:
    return round(max(0, llm_calls_used) * max(0.0, estimated_cost_per_call), 6)


def _normalized_ts(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_expired(analysis: AnalysisRun, *, now: datetime) -> bool:
    expires_at = _normalized_ts(analysis.expires_at)
    return expires_at is not None and now > expires_at


def _remaining_seconds(deadline_monotonic: float) -> float:
    return deadline_monotonic - time.monotonic()


def _disable_rq_retries() -> None:
    job = get_current_job()
    if job is None:
        return
    try:
        job.retries_left = 0
        job.save()
    except Exception:
        logger.warning("Unable to disable retries for current RQ job", exc_info=True)


def _set_analysis_status(
    db,
    analysis: AnalysisRun,
    *,
    status: str,
    error_message: str | None,
    settings,
) -> None:
    prior_status = analysis.status
    analysis.status = status
    analysis.completed_at = _utc_now() if status in _TERMINAL_ANALYSIS_STATUSES else None

    if error_message:
        clipped = error_message[:_MAX_ERROR_LENGTH]
        analysis.last_error = clipped
        analysis.error_message = clipped
    elif status == "completed":
        analysis.last_error = None
        analysis.error_message = None

    analysis.cost_estimate_usd = _estimate_cost(
        llm_calls_used=analysis.llm_calls_used,
        estimated_cost_per_call=settings.estimated_cost_per_call,
    )
    db.commit()

    if status in _TERMINAL_ANALYSIS_STATUSES:
        observe_job_duration(analysis.started_at or analysis.created_at, analysis.completed_at)

    if status == "cancelled" and prior_status != "cancelled":
        jobs_cancelled_total.inc()
    elif status == "expired" and prior_status != "expired":
        jobs_expired_total.inc()
    elif status == "timeout" and prior_status != "timeout":
        jobs_timed_out_total.inc()


def _start_attempt(db, analysis: AnalysisRun, *, settings) -> None:
    analysis.attempts = int(analysis.attempts or 0) + 1
    analysis.max_attempts = max(1, int(analysis.max_attempts or settings.max_attempts))
    analysis.status = "processing"
    if analysis.started_at is None:
        analysis.started_at = _utc_now()
    analysis.last_error = None
    analysis.error_message = None
    analysis.cost_estimate_usd = _estimate_cost(
        llm_calls_used=analysis.llm_calls_used,
        estimated_cost_per_call=settings.estimated_cost_per_call,
    )
    db.commit()


def _check_execution_guards(
    db,
    analysis: AnalysisRun,
    *,
    settings,
    deadline_monotonic: float,
    phase: str,
) -> bool:
    """Return True if the job should stop due to cancellation/expiry/timeout/budget."""
    db.refresh(analysis)

    if analysis.cancelled:
        _set_analysis_status(
            db,
            analysis,
            status="cancelled",
            error_message=f"Job cancelled ({phase}).",
            settings=settings,
        )
        return True

    now = _utc_now()
    if _is_expired(analysis, now=now):
        _set_analysis_status(
            db,
            analysis,
            status="expired",
            error_message=f"Job expired before completion ({phase}).",
            settings=settings,
        )
        return True

    if _remaining_seconds(deadline_monotonic) <= 0:
        _set_analysis_status(
            db,
            analysis,
            status="timeout",
            error_message=f"Job exceeded hard timeout ({phase}).",
            settings=settings,
        )
        return True

    if analysis.llm_calls_used > settings.max_llm_calls_per_job:
        _set_analysis_status(
            db,
            analysis,
            status="budget_exceeded",
            error_message=(
                f"LLM call budget exceeded ({analysis.llm_calls_used}/"
                f"{settings.max_llm_calls_per_job})."
            ),
            settings=settings,
        )
        return True

    return False


def _enforce_input_limit_or_raise(
    *,
    settings,
    resume_text: str,
    jd_text: str | None = None,
) -> None:
    max_chars = max(1, settings.max_input_chars)
    if len(resume_text) > max_chars:
        raise BudgetExceededError(
            f"Resume text length {len(resume_text)} exceeds MAX_INPUT_CHARS={max_chars}."
        )
    if jd_text is not None and len(jd_text) > max_chars:
        raise BudgetExceededError(
            f"Job description length {len(jd_text)} exceeds MAX_INPUT_CHARS={max_chars}."
        )


def _is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    message = str(exc).lower()
    return any(hint in message for hint in _TRANSIENT_HINTS)


def _handle_analysis_exception(
    db,
    analysis: AnalysisRun,
    exc: Exception,
    *,
    settings,
    job_id: str | None,
) -> None:
    message = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    clipped = message[:_MAX_ERROR_LENGTH]
    analysis.last_error = clipped
    analysis.error_message = clipped
    analysis.cost_estimate_usd = _estimate_cost(
        llm_calls_used=analysis.llm_calls_used,
        estimated_cost_per_call=settings.estimated_cost_per_call,
    )

    should_retry = _is_transient_error(exc) and analysis.attempts < analysis.max_attempts
    if should_retry:
        analysis.status = "queued"
        analysis.completed_at = None
        db.commit()
        jobs_retried_total.inc()
        logger.warning(
            "Analysis job attempt failed; retry scheduled",
            extra={
                "analysis_id": analysis.id,
                "job_id": job_id,
                "status": analysis.status,
                "attempts": analysis.attempts,
                "max_attempts": analysis.max_attempts,
                "last_error": clipped,
            },
        )
        raise TransientJobError(clipped) from exc

    _disable_rq_retries()
    _set_analysis_status(
        db,
        analysis,
        status="failed",
        error_message=clipped,
        settings=settings,
    )


def _mark_budget_exceeded(
    db,
    analysis: AnalysisRun,
    *,
    message: str,
    settings,
) -> None:
    _disable_rq_retries()
    _set_analysis_status(
        db,
        analysis,
        status="budget_exceeded",
        error_message=message,
        settings=settings,
    )


def _mark_timeout(
    db,
    analysis: AnalysisRun,
    *,
    message: str,
    settings,
) -> None:
    _disable_rq_retries()
    _set_analysis_status(
        db,
        analysis,
        status="timeout",
        error_message=message,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Standalone resume analysis job
# ---------------------------------------------------------------------------


def run_resume_analysis_job(analysis_id: int) -> dict:
    """Execute standalone resume analysis for the given AnalysisRun."""
    settings = get_settings()
    job_id = _job_id()
    deadline_monotonic = time.monotonic() + max(1, settings.job_hard_timeout_seconds)

    logger.info(
        "Starting resume analysis job",
        extra={"analysis_id": analysis_id, "job_id": job_id, "status": "starting"},
    )
    db = SyncSessionLocal()
    analysis: AnalysisRun | None = None

    try:
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="pre-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        _start_attempt(db, analysis, settings=settings)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="after-attempt-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        resume = db.get(Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        _enforce_input_limit_or_raise(settings=settings, resume_text=resume.parsed_text)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="before-analysis",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        output = analyze_resume(resume.parsed_text)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="post-analysis",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        analysis.overall_score = output["match_score"]
        analysis.result_payload = output["extracted_metadata"]
        _set_analysis_status(
            db,
            analysis,
            status="completed",
            error_message=None,
            settings=settings,
        )

        logger.info(
            "Resume analysis job completed",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return output

    except BudgetExceededError as exc:
        if analysis is None:
            raise
        _mark_budget_exceeded(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Resume analysis budget exceeded",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except JobTimeoutError as exc:
        if analysis is None:
            raise
        _mark_timeout(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Resume analysis timed out",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except Exception as exc:
        logger.error(
            "Resume analysis job failed",
            extra={"analysis_id": analysis_id, "job_id": job_id},
            exc_info=True,
        )
        if analysis is not None:
            _handle_analysis_exception(db, analysis, exc, settings=settings, job_id=job_id)
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Job-targeted resume analysis
# ---------------------------------------------------------------------------


def run_job_targeted_analysis_job(analysis_id: int) -> dict:
    """Execute job-targeted analysis for Resume × JobProfile."""
    from app.models.job_profile import JobProfile
    from app.services.job_targeted_scorer import JobProfileData, JobTargetedScorer

    settings = get_settings()
    job_id = _job_id()
    deadline_monotonic = time.monotonic() + max(1, settings.job_hard_timeout_seconds)

    logger.info(
        "Starting job-targeted analysis",
        extra={"analysis_id": analysis_id, "job_id": job_id, "status": "starting"},
    )
    db = SyncSessionLocal()
    analysis: AnalysisRun | None = None

    try:
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="pre-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        _start_attempt(db, analysis, settings=settings)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="after-attempt-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        resume = db.get(Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        profile_orm = db.get(JobProfile, analysis.job_profile_id)
        if profile_orm is None:
            raise ValueError(f"JobProfile {analysis.job_profile_id} not found")

        _enforce_input_limit_or_raise(settings=settings, resume_text=resume.parsed_text)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="before-scoring",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        profile_data = JobProfileData(
            title=profile_orm.title,
            normalized_title=profile_orm.normalized_title or "",
            seniority_level=profile_orm.seniority_level or "mid",
            required_skills=profile_orm.required_skills or [],
            optional_skills=profile_orm.optional_skills or [],
            responsibilities=profile_orm.responsibilities or [],
            years_experience_min=profile_orm.years_experience_min,
            years_experience_max=profile_orm.years_experience_max,
        )

        def _on_llm_call(used: int) -> None:
            analysis.llm_calls_used = used
            analysis.cost_estimate_usd = _estimate_cost(
                llm_calls_used=analysis.llm_calls_used,
                estimated_cost_per_call=settings.estimated_cost_per_call,
            )
            db.commit()

        tracker = LLMCallTracker(
            max_calls=settings.max_llm_calls_per_job,
            initial_used=int(analysis.llm_calls_used or 0),
            on_call=_on_llm_call,
        )

        scorer = JobTargetedScorer()
        with activate_llm_call_tracker(tracker):
            result = scorer.score(resume.parsed_text, profile_data)

        analysis.llm_calls_used = tracker.used
        analysis.cost_estimate_usd = _estimate_cost(
            llm_calls_used=analysis.llm_calls_used,
            estimated_cost_per_call=settings.estimated_cost_per_call,
        )

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="post-scoring",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        analysis.overall_score = result.overall_match_score
        analysis.result_payload = result.model_dump()
        _set_analysis_status(
            db,
            analysis,
            status="completed",
            error_message=None,
            settings=settings,
        )

        logger.info(
            "Job-targeted analysis completed",
            extra={
                "analysis_id": analysis_id,
                "job_id": job_id,
                "status": analysis.status,
                "score": result.overall_match_score,
            },
        )
        return result.model_dump()

    except BudgetExceededError as exc:
        if analysis is None:
            raise
        _mark_budget_exceeded(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Job-targeted analysis budget exceeded",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except JobTimeoutError as exc:
        if analysis is None:
            raise
        _mark_timeout(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Job-targeted analysis timed out",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except Exception as exc:
        logger.error(
            "Job-targeted analysis failed",
            extra={"analysis_id": analysis_id, "job_id": job_id},
            exc_info=True,
        )
        if analysis is not None:
            _handle_analysis_exception(db, analysis, exc, settings=settings, job_id=job_id)
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# JD-based analysis job
# ---------------------------------------------------------------------------


def run_analysis_job(analysis_id: int) -> dict:
    """Execute a full JD-based analysis pipeline for the given AnalysisRun."""
    from app.services.analysis_orchestrator import AnalysisOrchestrator

    settings = get_settings()
    job_id = _job_id()
    deadline_monotonic = time.monotonic() + max(1, settings.job_hard_timeout_seconds)

    logger.info(
        "Starting analysis job",
        extra={"analysis_id": analysis_id, "job_id": job_id, "status": "starting"},
    )
    db = SyncSessionLocal()
    analysis: AnalysisRun | None = None

    try:
        analysis = db.get(AnalysisRun, analysis_id)
        if analysis is None:
            raise ValueError(f"AnalysisRun {analysis_id} not found")

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="pre-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        _start_attempt(db, analysis, settings=settings)

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="after-attempt-start",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        resume = db.get(Resume, analysis.resume_id)
        if resume is None:
            raise ValueError(f"Resume {analysis.resume_id} not found")

        jd = db.get(JobDescription, analysis.job_description_id)
        if jd is None:
            raise ValueError(f"JobDescription {analysis.job_description_id} not found")

        _enforce_input_limit_or_raise(
            settings=settings,
            resume_text=resume.parsed_text,
            jd_text=jd.description_text,
        )

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="before-orchestration",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        remaining = _remaining_seconds(deadline_monotonic)
        if remaining <= 0:
            raise JobTimeoutError("Job exceeded hard timeout before orchestrator call.")

        step_timeout = min(max(1, settings.job_step_timeout_seconds), max(1, int(remaining)))
        orchestrator = AnalysisOrchestrator()
        try:
            output = asyncio.run(
                asyncio.wait_for(
                    orchestrator.analyze(resume.parsed_text, jd.description_text),
                    timeout=step_timeout,
                )
            )
        except TimeoutError as exc:
            raise JobTimeoutError(
                f"Orchestrator step exceeded timeout ({step_timeout}s)."
            ) from exc

        if _check_execution_guards(
            db,
            analysis,
            settings=settings,
            deadline_monotonic=deadline_monotonic,
            phase="post-orchestration",
        ):
            return {"analysis_id": analysis_id, "status": analysis.status}

        analysis.overall_score = output["overall_score"]
        analysis.result_payload = {
            "semantic_match": output["semantic_match"].model_dump(),
            "ats_compatibility": output["ats_compatibility"].model_dump(),
            "bias_detection": output["bias_detection"].model_dump(),
            "extracted_resume_skills": output["extracted_resume_skills"],
            "extracted_jd_skills": output["extracted_jd_skills"],
        }
        _set_analysis_status(
            db,
            analysis,
            status="completed",
            error_message=None,
            settings=settings,
        )

        logger.info(
            "Analysis job completed",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return analysis.result_payload

    except BudgetExceededError as exc:
        if analysis is None:
            raise
        _mark_budget_exceeded(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Analysis job budget exceeded",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except JobTimeoutError as exc:
        if analysis is None:
            raise
        _mark_timeout(db, analysis, message=str(exc), settings=settings)
        logger.warning(
            "Analysis job timed out",
            extra={"analysis_id": analysis_id, "job_id": job_id, "status": analysis.status},
        )
        return {"analysis_id": analysis_id, "status": analysis.status}

    except Exception as exc:
        logger.error(
            "Analysis job failed",
            extra={"analysis_id": analysis_id, "job_id": job_id},
            exc_info=True,
        )
        if analysis is not None:
            _handle_analysis_exception(db, analysis, exc, settings=settings, job_id=job_id)
        raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Resume Studio export jobs
# ---------------------------------------------------------------------------


def run_resume_studio_export_job(export_id: int) -> dict:
    """Generate Resume Studio exports (PDF or DOCX) in worker context."""
    from app.services.resume_studio import ResumeStudioService

    logger.info("Starting Resume Studio export", extra={"export_id": export_id})
    db = SyncSessionLocal()
    try:
        export = db.get(ResumeStudioExport, export_id)
        if export is None:
            raise ValueError(f"ResumeStudioExport {export_id} not found")
        version = db.get(ResumeStudioVersion, export.version_id)
        if version is None:
            raise ValueError(f"ResumeStudioVersion {export.version_id} not found")

        export.status = "processing"
        export.error_message = None
        db.commit()

        service = ResumeStudioService()
        settings = get_settings()
        output_dir = Path(settings.studio_export_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        extension = export.format.lower()
        file_name = f"studio_project_{version.project_id}_v{version.id}_export_{export.id}.{extension}"
        output_path = output_dir / file_name

        structured_resume = version.resume_structured_json or {}
        if extension == "pdf":
            service.export_pdf(structured_resume=structured_resume, output_path=str(output_path))
        elif extension == "docx":
            service.export_docx(structured_resume=structured_resume, output_path=str(output_path))
        else:
            raise ValueError(f"Unsupported export format: {export.format}")

        export.status = "completed"
        export.completed_at = _utc_now()
        export.file_path = str(output_path.resolve())
        export.error_message = None
        db.commit()
        logger.info(
            "Resume Studio export completed",
            extra={"export_id": export_id, "file_path": export.file_path},
        )
        return {"export_id": export_id, "status": export.status, "file_path": export.file_path}
    except Exception as exc:
        logger.error(
            "Resume Studio export failed",
            extra={"export_id": export_id, "error": str(exc)},
            exc_info=True,
        )
        _mark_studio_export_failed_sync(db, export_id=export_id, exc=exc)
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mark_studio_export_failed_sync(db, export_id: int, exc: Exception) -> None:
    try:
        db.rollback()
        export = db.get(ResumeStudioExport, export_id)
        if export is not None:
            export.status = "failed"
            export.completed_at = _utc_now()
            error_text = traceback.format_exception_only(type(exc), exc)
            export.error_message = "".join(error_text)[:_MAX_ERROR_LENGTH]
            db.commit()
    except Exception:
        logger.error(
            "Failed to mark studio export as failed",
            extra={"export_id": export_id},
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
