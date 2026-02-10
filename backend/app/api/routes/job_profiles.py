"""CRUD routes for job profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.job_profile import JobProfile
from app.models.user import User
from app.schemas.job_profile import (
    JobProfileCreate,
    JobProfileOut,
    JobProfileParseRequest,
    JobProfileUpdate,
    JobTargetPreview,
)
from app.services.jd_parser import JDParserService

router = APIRouter()


@router.post("/parse-preview", response_model=JobTargetPreview)
async def parse_job_profile_preview(
    payload: JobProfileParseRequest,
    _user: User = Depends(get_current_user),
) -> JobTargetPreview:
    """Parse raw JD text and return a structured preview before creation."""
    parser = JDParserService()
    parsed = parser.parse(payload.raw_description, title_hint=payload.title)
    return JobTargetPreview(
        role_title=parsed.role_title,
        normalized_title=parsed.normalized_title,
        role_archetype=parsed.role_archetype,
        seniority_level=parsed.seniority_level,
        years_experience_required=parsed.years_experience_required,
        company_context=parsed.company_context,
        role_summary=parsed.role_summary,
        constraints=parsed.constraints,
        requirements_hard=parsed.requirements_hard,
        requirements_soft=parsed.requirements_soft,
        education_requirements=parsed.education_requirements,
        certifications=parsed.certifications,
        hard_requirements=parsed.hard_requirements,
        soft_requirements=parsed.soft_requirements,
        responsibilities=parsed.responsibilities,
        tools_and_technologies=parsed.tools_and_technologies,
        domain_keywords=parsed.domain_keywords,
        soft_skills=parsed.soft_skills,
        ats_keywords=parsed.ats_keywords,
        responsibility_clusters=parsed.responsibility_clusters,
        weight_map=parsed.weight_map,
        required_skills=parsed.required_skills,
        optional_skills=parsed.optional_skills,
    )


@router.post("/", response_model=JobProfileOut, status_code=status.HTTP_201_CREATED)
async def create_job_profile(
    payload: JobProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileOut:
    """Create a new job profile.

    If ``raw_description`` is provided, the JD parser auto-fills
    structured fields (skills, seniority, experience range, responsibilities).
    Explicitly provided fields override parsed values.
    """
    parsed_data: dict = {}
    if payload.raw_description:
        parser = JDParserService()
        parsed = parser.parse(payload.raw_description, title_hint=payload.title)
        parsed_data = {
            "normalized_title": parsed.normalized_title,
            "seniority_level": parsed.seniority_level,
            "required_skills": parsed.required_skills,
            "optional_skills": parsed.optional_skills,
            "responsibilities": parsed.responsibilities,
            "years_experience_min": parsed.years_experience_min,
            "years_experience_max": parsed.years_experience_max,
        }

    profile = JobProfile(
        user_id=user.id,
        title=payload.title,
        normalized_title=parsed_data.get("normalized_title", payload.title.strip().lower()),
        seniority_level=payload.seniority_level or parsed_data.get("seniority_level"),
        required_skills=payload.required_skills or parsed_data.get("required_skills", []),
        optional_skills=payload.optional_skills or parsed_data.get("optional_skills", []),
        responsibilities=payload.responsibilities or parsed_data.get("responsibilities", []),
        years_experience_min=payload.years_experience_min or parsed_data.get("years_experience_min"),
        years_experience_max=payload.years_experience_max or parsed_data.get("years_experience_max"),
        source="user_pasted" if payload.raw_description else "user_created",
        raw_description=payload.raw_description,
        is_template=False,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Update user's last-used profile
    user.last_job_profile_id = profile.id
    await db.commit()

    return JobProfileOut.model_validate(profile)


@router.get("/", response_model=list[JobProfileOut])
async def list_job_profiles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[JobProfileOut]:
    """List user's profiles and system templates."""
    result = await db.execute(
        select(JobProfile)
        .where(
            (JobProfile.user_id == user.id) | (JobProfile.is_template.is_(True))
        )
        .order_by(JobProfile.is_template.desc(), JobProfile.created_at.desc())
    )
    profiles = result.scalars().all()
    return [JobProfileOut.model_validate(p) for p in profiles]


@router.get("/templates", response_model=list[JobProfileOut])
async def list_templates(
    db: AsyncSession = Depends(get_db_session),
) -> list[JobProfileOut]:
    """List system template profiles only."""
    result = await db.execute(
        select(JobProfile)
        .where(JobProfile.is_template.is_(True))
        .order_by(JobProfile.title)
    )
    profiles = result.scalars().all()
    return [JobProfileOut.model_validate(p) for p in profiles]


@router.get("/last-used", response_model=JobProfileOut | None)
async def get_last_used_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileOut | None:
    """Return the user's last-used job profile, or null."""
    if user.last_job_profile_id is None:
        return None
    result = await db.execute(
        select(JobProfile).where(JobProfile.id == user.last_job_profile_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    return JobProfileOut.model_validate(profile)


@router.get("/{profile_id}", response_model=JobProfileOut)
async def get_job_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileOut:
    """Get a single job profile by ID."""
    result = await db.execute(
        select(JobProfile).where(
            JobProfile.id == profile_id,
            (JobProfile.user_id == user.id) | (JobProfile.is_template.is_(True)),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Job profile not found")
    return JobProfileOut.model_validate(profile)


@router.put("/{profile_id}", response_model=JobProfileOut)
async def update_job_profile(
    profile_id: int,
    payload: JobProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> JobProfileOut:
    """Update a user-owned job profile."""
    result = await db.execute(
        select(JobProfile).where(
            JobProfile.id == profile_id,
            JobProfile.user_id == user.id,
            JobProfile.is_template.is_(False),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Job profile not found or not editable")

    update_data = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(profile, field_name, value)

    if "title" in update_data:
        profile.normalized_title = update_data["title"].strip().lower()

    await db.commit()
    await db.refresh(profile)
    return JobProfileOut.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_job_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete a user-owned job profile (templates cannot be deleted)."""
    result = await db.execute(
        select(JobProfile).where(
            JobProfile.id == profile_id,
            JobProfile.user_id == user.id,
            JobProfile.is_template.is_(False),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Job profile not found or not deletable")

    await db.delete(profile)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
