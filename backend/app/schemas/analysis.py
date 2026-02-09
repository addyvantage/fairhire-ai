from datetime import datetime

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
