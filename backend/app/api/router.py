from fastapi import APIRouter

from app.api.routes import (
    analysis,
    auth,
    dashboard,
    health,
    job_descriptions,
    job_profiles,
    resume_studio,
    resumes,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(job_descriptions.router, prefix="/job-descriptions", tags=["job-descriptions"])
api_router.include_router(job_profiles.router, prefix="/job-profiles", tags=["job-profiles"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(resume_studio.router, prefix="/studio", tags=["resume-studio"])
api_router.include_router(health.router, tags=["health"])
