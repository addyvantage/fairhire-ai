from fastapi import APIRouter

from app.api import analysis, health, job_descriptions, resumes
from app.api.routes import auth

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(resumes.router)
api_router.include_router(job_descriptions.router)
api_router.include_router(analysis.router)
