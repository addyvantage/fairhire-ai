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


class JobProfileParseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    raw_description: str = Field(min_length=20)


class JobTargetPreview(BaseModel):
    role_title: str
    normalized_title: str
    seniority_level: str
    years_experience_required: dict[str, int | None]
    education_requirements: list[str]
    certifications: list[str]
    hard_requirements: list[str]
    soft_requirements: list[str]
    responsibilities: list[str]
    tools_and_technologies: list[str]
    domain_keywords: list[str]
    soft_skills: list[str]
    ats_keywords: list[str]
    responsibility_clusters: dict[str, list[str]]
    weight_map: dict[str, float]
    required_skills: list[str]
    optional_skills: list[str]
