from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.job_description import JobDescription
from app.models.user import User
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut

router = APIRouter()


@router.post("", response_model=JobDescriptionOut, status_code=status.HTTP_201_CREATED)
async def create_job_description(
    payload: JobDescriptionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobDescription:
    jd = JobDescription(
        user_id=user.id,
        title=payload.title,
        company=payload.company,
        description_text=payload.description_text,
    )
    db.add(jd)
    await db.commit()
    await db.refresh(jd)
    return jd


@router.get("", response_model=list[JobDescriptionOut])
async def list_job_descriptions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> list[JobDescription]:
    result = await db.execute(
        select(JobDescription).where(JobDescription.user_id == user.id).order_by(JobDescription.id.desc())
    )
    return list(result.scalars().all())
