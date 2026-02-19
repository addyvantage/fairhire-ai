from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    job_description_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=True
    )
    job_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_profiles.id", ondelete="SET NULL"), nullable=True
    )
    overall_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=3, server_default="3")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_calls_used: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    cost_estimate_usd: Mapped[float] = mapped_column(nullable=False, default=0.0, server_default="0")
