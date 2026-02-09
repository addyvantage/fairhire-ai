from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job_description import JobDescription
from app.models.user import User
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut

router = APIRouter()


@router.post("", response_model=JobDescriptionOut, status_code=status.HTTP_201_CREATED)
async def create_job_description(
    payload: JobDescriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDescription:
    job_description = JobDescription(
        user_id=current_user.id,
        title=payload.title,
        company=payload.company,
        text=payload.text,
    )
    db.add(job_description)
    await db.commit()
    await db.refresh(job_description)
    return job_description


@router.get("", response_model=list[JobDescriptionOut])
async def list_job_descriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobDescription]:
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        .order_by(JobDescription.created_at.desc())
    )
    return list(result.scalars().all())
