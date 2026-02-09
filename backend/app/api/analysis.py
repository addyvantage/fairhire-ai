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
    JobStatusResponse,
)
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.async_analysis import enqueue_analysis, get_job_status

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Existing synchronous endpoint (backward compatible)
# ---------------------------------------------------------------------------


@router.post("/run", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    payload: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AnalysisResponse:
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


# ---------------------------------------------------------------------------
# Async endpoints (new)
# ---------------------------------------------------------------------------


@router.post("/async", response_model=AsyncAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_async_analysis(
    payload: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AsyncAnalysisResponse:
    """Submit an analysis for asynchronous background processing.

    Returns HTTP 202 with the job tracking information.
    Poll ``GET /analysis/jobs/{job_id}`` for status and results.
    """
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
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def poll_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobStatusResponse:
    """Poll the status of an async analysis job.

    Returns the current status, and the full result payload once completed.
    """
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
        created_at=analysis.created_at,
    )
