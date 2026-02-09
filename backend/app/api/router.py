from fastapi import APIRouter

from app.api.routes import auth, analysis, job_descriptions, resumes, health

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(job_descriptions.router, prefix="/job-descriptions", tags=["job-descriptions"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(health.router, tags=["health"])
