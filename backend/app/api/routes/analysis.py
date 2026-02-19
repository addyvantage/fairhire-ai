from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.analysis import AnalysisRun
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AsyncAnalysisResponse,
    JobCancelResponse,
    JobStatusResponse,
    ResumeAnalysisOut,
    ResumeAnalysisQueued,
    ResumeAnalysisRequest,
)
from app.schemas.job_profile import TargetedAnalysisRequest
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.async_analysis import (
    cancel_analysis_job,
    enqueue_analysis,
    enqueue_job_targeted_analysis,
    enqueue_resume_analysis,
    get_analysis_by_id,
    get_analysis_history_for_resume,
    get_job_status,
    get_latest_analysis_for_resume,
)

router = APIRouter()


def _analysis_to_out(analysis: AnalysisRun) -> ResumeAnalysisOut:
    """Map AnalysisRun to ResumeAnalysisOut response schema."""
    payload = analysis.result_payload

    # Job-targeted analyses store the full JobMatchResult in result_payload.
    # Standalone analyses store extracted_metadata dict instead.
    is_targeted = analysis.job_profile_id is not None
    job_match_result = payload if is_targeted and payload else None
    extracted_metadata = payload if not is_targeted and payload else None

    return ResumeAnalysisOut(
        id=analysis.id,
        resume_id=analysis.resume_id,
        job_profile_id=analysis.job_profile_id,
        status=analysis.status,
        match_score=analysis.overall_score,
        extracted_metadata=extracted_metadata,
        job_match_result=job_match_result,
        error_message=analysis.error_message,
        last_error=analysis.last_error,
        cancelled=analysis.cancelled,
        expires_at=analysis.expires_at,
        attempts=analysis.attempts,
        max_attempts=analysis.max_attempts,
        llm_calls_used=analysis.llm_calls_used,
        cost_estimate_usd=analysis.cost_estimate_usd,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        created_at=analysis.created_at,
    )


# ---------------------------------------------------------------------------
# POST endpoints (no ordering concern with GET /{analysis_id})
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=ResumeAnalysisQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_resume_analysis(
    payload: ResumeAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeAnalysisQueued:
    """Trigger standalone resume analysis.

    Creates an AnalysisRun (status=queued) and enqueues a worker job.
    Returns the analysis_id for polling.
    """
    analysis = await enqueue_resume_analysis(
        user_id=user.id,
        resume_id=payload.resume_id,
        db=db,
    )
    return ResumeAnalysisQueued(
        analysis_id=analysis.id,
        status=analysis.status,
        created_at=analysis.created_at,
        expires_at=analysis.expires_at,
        attempts=analysis.attempts,
        max_attempts=analysis.max_attempts,
    )


@router.post(
    "/run-targeted",
    response_model=ResumeAnalysisQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_targeted_analysis(
    payload: TargetedAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeAnalysisQueued:
    """Trigger job-targeted resume analysis (Resume × JobProfile).

    Creates an AnalysisRun (status=queued) and enqueues the targeted scoring job.
    Also updates the user's last_job_profile_id for convenience.
    """
    analysis = await enqueue_job_targeted_analysis(
        user_id=user.id,
        resume_id=payload.resume_id,
        job_profile_id=payload.job_profile_id,
        db=db,
    )
    return ResumeAnalysisQueued(
        analysis_id=analysis.id,
        status=analysis.status,
        created_at=analysis.created_at,
        expires_at=analysis.expires_at,
        attempts=analysis.attempts,
        max_attempts=analysis.max_attempts,
    )


@router.post("/sync", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    payload: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
    """Synchronous JD-based analysis (legacy)."""
    resume_result = await db.execute(
        select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == user.id)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    jd_result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == payload.job_description_id, JobDescription.user_id == user.id
        )
    )
    job_description = jd_result.scalar_one_or_none()
    if not job_description:
        raise HTTPException(status_code=404, detail="Job description not found")

    orchestrator = AnalysisOrchestrator()
    output = await orchestrator.analyze(resume.parsed_text, job_description.description_text)

    analysis = AnalysisRun(
        user_id=user.id,
        resume_id=resume.id,
        job_description_id=job_description.id,
        overall_score=output["overall_score"],
        result_payload={
            "semantic_match": output["semantic_match"].model_dump(),
            "ats_compatibility": output["ats_compatibility"].model_dump(),
            "bias_detection": output["bias_detection"].model_dump(),
            "extracted_resume_skills": output["extracted_resume_skills"],
            "extracted_jd_skills": output["extracted_jd_skills"],
        },
        status="completed",
    )

    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return AnalysisResponse(
        analysis_id=analysis.id,
        overall_score=analysis.overall_score,
        semantic_match=output["semantic_match"],
        ats_compatibility=output["ats_compatibility"],
        bias_detection=output["bias_detection"],
        extracted_resume_skills=output["extracted_resume_skills"],
        extracted_jd_skills=output["extracted_jd_skills"],
        created_at=analysis.created_at,
    )


@router.post("/async", response_model=AsyncAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_async_analysis(
    payload: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AsyncAnalysisResponse:
    """Submit a JD-based analysis for asynchronous background processing."""
    analysis = await enqueue_analysis(
        user_id=user.id,
        resume_id=payload.resume_id,
        job_description_id=payload.job_description_id,
        db=db,
    )
    return AsyncAnalysisResponse(
        analysis_id=analysis.id,
        job_id=analysis.job_id,
        status=analysis.status,
        created_at=analysis.created_at,
        expires_at=analysis.expires_at,
        attempts=analysis.attempts,
        max_attempts=analysis.max_attempts,
    )


# ---------------------------------------------------------------------------
# GET endpoints — specific paths BEFORE parameterized catch-all
# ---------------------------------------------------------------------------


@router.get("/by-resume/{resume_id}", response_model=ResumeAnalysisOut)
async def get_analysis_by_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeAnalysisOut:
    """Get the latest standalone analysis for a resume."""
    analysis = await get_latest_analysis_for_resume(
        user_id=user.id,
        resume_id=resume_id,
        db=db,
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis found for this resume")
    return _analysis_to_out(analysis)


@router.get("/by-resume/{resume_id}/history", response_model=list[ResumeAnalysisOut])
async def get_analysis_history(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ResumeAnalysisOut]:
    analyses = await get_analysis_history_for_resume(
        user_id=user.id,
        resume_id=resume_id,
        db=db,
    )
    return [_analysis_to_out(analysis) for analysis in analyses]


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def poll_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobStatusResponse:
    """Poll the status of an async analysis job."""
    analysis = await get_job_status(
        user_id=user.id,
        job_id=job_id,
        db=db,
    )
    return JobStatusResponse(
        analysis_id=analysis.id,
        job_id=analysis.job_id,
        status=analysis.status,
        overall_score=analysis.overall_score,
        result_payload=analysis.result_payload,
        error_message=analysis.error_message,
        last_error=analysis.last_error,
        created_at=analysis.created_at,
        expires_at=analysis.expires_at,
        cancelled=analysis.cancelled,
        attempts=analysis.attempts,
        max_attempts=analysis.max_attempts,
        llm_calls_used=analysis.llm_calls_used,
        cost_estimate_usd=analysis.cost_estimate_usd,
    )


@router.post("/jobs/{analysis_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobCancelResponse:
    analysis = await cancel_analysis_job(
        user_id=user.id,
        analysis_id=analysis_id,
        db=db,
    )
    return JobCancelResponse(
        analysis_id=analysis.id,
        status=analysis.status,
        cancelled=analysis.cancelled,
        completed_at=analysis.completed_at,
    )


@router.get("/{analysis_id}", response_model=ResumeAnalysisOut)
async def get_analysis(
    analysis_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeAnalysisOut:
    """Get analysis by ID with full results."""
    analysis = await get_analysis_by_id(
        user_id=user.id,
        analysis_id=analysis_id,
        db=db,
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_to_out(analysis)
