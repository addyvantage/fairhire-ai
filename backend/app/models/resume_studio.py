from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeStudioProject(Base):
    __tablename__ = "resume_studio_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="builder")
    base_resume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ResumeStudioVersion(Base):
    __tablename__ = "resume_studio_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("resume_studio_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="base")
    job_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_profiles.id", ondelete="SET NULL"), nullable=True
    )
    jd_text_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    jd_structured_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    resume_structured_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resume_render_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_plain_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_snapshot_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    template_name: Mapped[str] = mapped_column(String(64), nullable=False, default="ats_classic")
    template_settings_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResumeStudioExport(Base):
    __tablename__ = "resume_studio_exports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("resume_studio_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
