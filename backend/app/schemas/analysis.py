from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExplainableMetric(BaseModel):
    score: float = Field(ge=0, le=100)
    explanation: str
    contributing_factors: list[str]


# ---------------------------------------------------------------------------
# Legacy JD-based analysis (kept for backward compatibility)
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    resume_id: int
    job_description_id: int


class AnalysisResponse(BaseModel):
    analysis_id: int
    overall_score: float = Field(ge=0, le=100)
    semantic_match: ExplainableMetric
    ats_compatibility: ExplainableMetric
    bias_detection: ExplainableMetric
    extracted_resume_skills: list[str]
    extracted_jd_skills: list[str]
    created_at: datetime


class AsyncAnalysisResponse(BaseModel):
    """Returned by POST /analysis/async (HTTP 202)."""

    analysis_id: int
    job_id: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    """Returned by GET /analysis/jobs/{job_id}."""

    analysis_id: int
    job_id: Optional[str]
    status: str
    overall_score: Optional[float] = None
    result_payload: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Standalone resume analysis (new endpoints)
# ---------------------------------------------------------------------------

class ResumeAnalysisRequest(BaseModel):
    resume_id: int


class ResumeAnalysisQueued(BaseModel):
    """Returned by POST /analysis/run for standalone resume analysis."""

    analysis_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeAnalysisOut(BaseModel):
    """Full analysis result for GET /analysis/{id} and GET /analysis/by-resume/{resume_id}."""

    id: int
    resume_id: int
    status: str
    match_score: Optional[float] = None
    extracted_metadata: Optional[dict] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
