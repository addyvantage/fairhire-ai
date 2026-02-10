from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ResumeHeaderLink(BaseModel):
    label: str
    url: str


class ResumeHeader(BaseModel):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[ResumeHeaderLink] = Field(default_factory=list)


class ResumeSkillCategory(BaseModel):
    name: str
    items: list[str] = Field(default_factory=list)


class ResumeSkills(BaseModel):
    categories: list[ResumeSkillCategory] = Field(default_factory=list)


class ResumeExperienceItem(BaseModel):
    company: str = ""
    role: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)


class ResumeExperience(BaseModel):
    items: list[ResumeExperienceItem] = Field(default_factory=list)


class ResumeProjectItem(BaseModel):
    name: str = ""
    link: str = ""
    bullets: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)


class ResumeProjects(BaseModel):
    items: list[ResumeProjectItem] = Field(default_factory=list)


class ResumeEducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    start: str = ""
    end: str = ""
    notes: list[str] = Field(default_factory=list)


class ResumeEducation(BaseModel):
    items: list[ResumeEducationItem] = Field(default_factory=list)


class StructuredResume(BaseModel):
    header: ResumeHeader = Field(default_factory=ResumeHeader)
    summary: str = ""
    skills: ResumeSkills = Field(default_factory=ResumeSkills)
    experience: ResumeExperience = Field(default_factory=ResumeExperience)
    projects: ResumeProjects = Field(default_factory=ResumeProjects)
    education: ResumeEducation = Field(default_factory=ResumeEducation)
    certifications: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    evidence_map: dict[str, list[str]] = Field(default_factory=dict)


class StudioProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_type: Literal["builder", "import_pdf", "import_docx", "import_text"] = "builder"
    base_resume_id: Optional[int] = None


class StudioProjectOut(BaseModel):
    id: int
    user_id: int
    title: str
    source_type: str
    base_resume_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    latest_version_id: Optional[int] = None
    latest_version_kind: Optional[str] = None
    latest_version_created_at: Optional[datetime] = None
    tailored_tags: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StudioVersionCreate(BaseModel):
    source_version_id: Optional[int] = None
    kind: Literal["base", "tailored"] = "base"
    job_profile_id: Optional[int] = None
    template_name: Optional[str] = None
    template_settings: Optional[dict[str, Any]] = None


class StudioVersionUpdate(BaseModel):
    resume_structured_json: StructuredResume
    template_name: Optional[str] = None
    template_settings: Optional[dict[str, Any]] = None


class StudioTailorRequest(BaseModel):
    jd_text: str = Field(min_length=50)
    strict_mode: bool = True
    job_profile_id: Optional[int] = None
    template_name: Optional[str] = None
    template_settings: Optional[dict[str, Any]] = None


class StudioVersionOut(BaseModel):
    id: int
    project_id: int
    kind: str
    job_profile_id: Optional[int] = None
    jd_text_hash: Optional[str] = None
    jd_structured_json: Optional[dict[str, Any]] = None
    resume_structured_json: dict[str, Any]
    resume_render_html: Optional[str] = None
    resume_plain_text: Optional[str] = None
    score_snapshot_json: Optional[dict[str, Any]] = None
    template_name: str
    template_settings_json: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudioProjectDetailOut(BaseModel):
    project: StudioProjectOut
    versions: list[StudioVersionOut] = Field(default_factory=list)


class StudioImportResponse(BaseModel):
    project: StudioProjectOut
    version: StudioVersionOut


class StudioExportOut(BaseModel):
    id: int
    version_id: int
    format: str
    status: str
    job_id: Optional[str] = None
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
