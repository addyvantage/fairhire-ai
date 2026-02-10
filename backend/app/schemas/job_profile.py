"""Pydantic schemas for job profile endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobProfileCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    raw_description: Optional[str] = None
    seniority_level: Optional[str] = None
    required_skills: Optional[list[str]] = None
    optional_skills: Optional[list[str]] = None
    responsibilities: Optional[list[str]] = None
    years_experience_min: Optional[int] = None
    years_experience_max: Optional[int] = None


class JobProfileUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    raw_description: Optional[str] = None
    seniority_level: Optional[str] = None
    required_skills: Optional[list[str]] = None
    optional_skills: Optional[list[str]] = None
    responsibilities: Optional[list[str]] = None
    years_experience_min: Optional[int] = None
    years_experience_max: Optional[int] = None


class JobProfileOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    normalized_title: Optional[str] = None
    seniority_level: Optional[str] = None
    required_skills: Optional[list[str]] = None
    optional_skills: Optional[list[str]] = None
    responsibilities: Optional[list[str]] = None
    years_experience_min: Optional[int] = None
    years_experience_max: Optional[int] = None
    source: str
    raw_description: Optional[str] = None
    is_template: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TargetedAnalysisRequest(BaseModel):
    resume_id: int
    job_profile_id: int
