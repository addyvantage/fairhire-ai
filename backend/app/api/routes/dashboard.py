from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.analysis import AnalysisRun
from app.models.resume import Resume
from app.models.user import User
from app.schemas.dashboard import DashboardStatsOut

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsOut)
async def get_dashboard_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DashboardStatsOut:
    resume_count = await db.scalar(
        select(func.count()).select_from(Resume).where(Resume.user_id == user.id)
    )

    analysis_count = await db.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .where(AnalysisRun.user_id == user.id, AnalysisRun.status == "completed")
    )

    avg_score_result = await db.scalar(
        select(func.avg(AnalysisRun.overall_score)).where(
            AnalysisRun.user_id == user.id,
            AnalysisRun.status == "completed",
            AnalysisRun.overall_score.is_not(None),
        )
    )

    return DashboardStatsOut(
        total_resumes=resume_count or 0,
        analyses_run=analysis_count or 0,
        avg_match_score=round(avg_score_result or 0, 1),
    )
