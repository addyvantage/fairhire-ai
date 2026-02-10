from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobProfile(Base):
    __tablename__ = "job_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seniority_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    required_skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    optional_skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    responsibilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    years_experience_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    years_experience_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="user_created"
    )
    raw_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
