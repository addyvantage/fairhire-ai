import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analysis import AnalysisResult
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.models.user import User
from app.schemas.analysis import AnalysisOut
from app.services.analysis_orchestrator import AnalysisOrchestrator

router = APIRouter()


@router.post("/run", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    resume_id: uuid.UUID,
    job_description_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisOut:
    resume_query = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = resume_query.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    jd_query = await db.execute(
        select(JobDescription).where(
            JobDescription.id == job_description_id,
            JobDescription.user_id == current_user.id,
        )
    )
    jd = jd_query.scalar_one_or_none()
    if jd is None:
        raise HTTPException(status_code=404, detail="Job description not found")

    orchestrator = AnalysisOrchestrator()
    result_payload = await orchestrator.analyze(resume.extracted_text, jd.text)

    analysis = AnalysisResult(
        resume_id=resume.id,
        job_description_id=jd.id,
        results_json={k: v.model_dump() for k, v in result_payload.items()},
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return AnalysisOut(
        id=analysis.id,
        resume_id=analysis.resume_id,
        job_description_id=analysis.job_description_id,
        skill_alignment=result_payload["skill_alignment"],
        semantic_match=result_payload["semantic_match"],
        ats_compatibility=result_payload["ats_compatibility"],
        bias_risk=result_payload["bias_risk"],
        created_at=analysis.created_at,
    )
