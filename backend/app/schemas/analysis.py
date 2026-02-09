from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExplainableMetric(BaseModel):
    score: float = Field(ge=0, le=100)
    explanation: str
    contributing_factors: list[str]


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
