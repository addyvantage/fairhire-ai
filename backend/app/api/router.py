from fastapi import APIRouter

from app.api import analysis, auth, health, job_descriptions, resumes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(resumes.router)
api_router.include_router(job_descriptions.router)
api_router.include_router(analysis.router)
