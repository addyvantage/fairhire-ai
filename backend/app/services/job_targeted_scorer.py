"""Job-targeted resume scoring engine.

Fully synchronous — designed for RQ worker context. Produces decomposed,
explainable sub-scores for Resume × JobProfile matching.

Sub-scores and weights:
    skill_match_score     40%   Required/optional skill overlap
    experience_match_score 25%  Years of experience vs range
    role_alignment_score  15%   Cosine similarity (sentence-transformers)
    seniority_fit_score   10%   Detected seniority vs target
    quality_score          5%   Resume quality heuristics
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.skill_taxonomy import KNOWN_SKILLS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class JobProfileData:
    """Lightweight DTO passed from worker to scorer (no ORM dependency)."""

    title: str
    normalized_title: str
    seniority_level: str
    required_skills: list[str]
    optional_skills: list[str]
    responsibilities: list[str]
    years_experience_min: int | None
    years_experience_max: int | None


@dataclass
class JobMatchResult:
    """Complete output of the scoring engine."""

    overall_match_score: float = 0.0
    skill_match_score: float = 0.0
    experience_match_score: float = 0.0
    role_alignment_score: float = 0.0
    seniority_fit_score: float = 0.0
    quality_score: float = 0.0
    gaps: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    explanation_summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "overall_match_score": self.overall_match_score,
            "skill_match_score": self.skill_match_score,
            "experience_match_score": self.experience_match_score,
            "role_alignment_score": self.role_alignment_score,
            "seniority_fit_score": self.seniority_fit_score,
            "quality_score": self.quality_score,
            "gaps": self.gaps,
            "strengths": self.strengths,
            "explanation_summary": self.explanation_summary,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "skill_match": 0.40,
    "experience": 0.25,
    "role_alignment": 0.15,
    "seniority_fit": 0.10,
    "quality": 0.10,
}

# ---------------------------------------------------------------------------
# Seniority bands (mapped to approximate experience years)
# ---------------------------------------------------------------------------

_SENIORITY_BANDS: dict[str, tuple[int, int]] = {
    "intern": (0, 1),
    "junior": (0, 2),
    "mid": (2, 5),
    "senior": (5, 10),
    "lead": (7, 15),
    "principal": (10, 20),
    "staff": (10, 25),
}

# ---------------------------------------------------------------------------
# Year-range pattern for experience estimation
# ---------------------------------------------------------------------------

_YEAR_RANGE_PATTERN = re.compile(
    r"(\b(?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current|now)",
    re.IGNORECASE,
)

# Section detection patterns (reused from resume_analyzer)
_SECTION_PATTERNS: dict[str, list[str]] = {
    "education": ["education", "academic", "university", "degree", "bachelor", "master", "phd"],
    "experience": ["experience", "employment", "work history", "professional background"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "projects": ["projects", "portfolio", "personal projects", "open source"],
    "certifications": ["certifications", "certificates", "licenses", "credentials"],
    "summary": ["summary", "objective", "profile", "about me", "professional summary"],
}

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")


# ---------------------------------------------------------------------------
# Lazy-loaded sentence-transformers model (module-level singleton)
# ---------------------------------------------------------------------------

_st_model = None


def _get_sentence_model():
    """Lazy-load sentence-transformers model. Runs synchronously in worker."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model for scoring")
        except Exception:
            logger.warning(
                "sentence-transformers not available — role alignment will use fallback",
                exc_info=True,
            )
    return _st_model


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class JobTargetedScorer:
    """Synchronous Resume × JobProfile scorer for RQ worker context."""

    def score(self, resume_text: str, profile: JobProfileData) -> JobMatchResult:
        result = JobMatchResult()

        # Extract resume skills
        resume_skills = self._extract_resume_skills(resume_text)
        experience_years = self._estimate_experience_years(resume_text)

        # 1. Skill match (40%)
        result.skill_match_score = self._score_skill_match(
            resume_skills, profile.required_skills, profile.optional_skills
        )

        # 2. Experience match (25%)
        result.experience_match_score = self._score_experience(
            experience_years, profile.years_experience_min, profile.years_experience_max
        )

        # 3. Role alignment (15%) — cosine similarity of resume vs responsibilities
        responsibilities_text = ". ".join(profile.responsibilities) if profile.responsibilities else ""
        result.role_alignment_score = self._score_role_alignment(
            resume_text, responsibilities_text
        )

        # 4. Seniority fit (10%)
        result.seniority_fit_score = self._score_seniority_fit(
            experience_years, profile.seniority_level
        )

        # 5. Quality (10%)
        result.quality_score = self._score_quality(resume_text)

        # Weighted composite
        result.overall_match_score = round(
            result.skill_match_score * _WEIGHTS["skill_match"]
            + result.experience_match_score * _WEIGHTS["experience"]
            + result.role_alignment_score * _WEIGHTS["role_alignment"]
            + result.seniority_fit_score * _WEIGHTS["seniority_fit"]
            + result.quality_score * _WEIGHTS["quality"],
            1,
        )

        # Gaps and strengths
        required_set = {s.lower() for s in profile.required_skills}
        optional_set = {s.lower() for s in profile.optional_skills}
        resume_set = {s.lower() for s in resume_skills}

        matched_required = sorted(required_set & resume_set)
        missing_required = sorted(required_set - resume_set)
        matched_optional = sorted(optional_set & resume_set)

        result.gaps = []
        if missing_required:
            result.gaps.append(f"Missing required skills: {', '.join(missing_required)}")
        if profile.years_experience_min and experience_years < profile.years_experience_min:
            deficit = profile.years_experience_min - experience_years
            result.gaps.append(f"Experience shortfall: ~{deficit:.0f} years below minimum")

        result.strengths = []
        if matched_required:
            result.strengths.append(f"Matched required skills: {', '.join(matched_required)}")
        if matched_optional:
            result.strengths.append(f"Matched optional skills: {', '.join(matched_optional)}")
        if profile.years_experience_max and experience_years >= profile.years_experience_min or 0:
            result.strengths.append(f"Experience: {experience_years:.0f} years detected")

        # Explanation summary
        title_display = profile.title
        seniority_display = profile.seniority_level.capitalize() if profile.seniority_level else ""
        if seniority_display:
            title_display = f"{title_display} ({seniority_display})"

        total_required = len(profile.required_skills)
        matched_count = len(matched_required)
        gap_list = ", ".join(missing_required[:3]) if missing_required else ""
        gap_suffix = f" Key gaps: {gap_list}." if gap_list else ""

        result.explanation_summary = (
            f"{result.overall_match_score}% match for {title_display}. "
            f"Matched {matched_count}/{total_required} required skills.{gap_suffix}"
        )

        # Details dict
        result.details = {
            "resume_skills": resume_skills,
            "matched_required": matched_required,
            "matched_optional": matched_optional,
            "missing_required": missing_required,
            "extra_resume_skills": sorted(resume_set - required_set - optional_set),
            "experience_years_detected": experience_years,
            "cosine_similarity": result.role_alignment_score / 100.0,
        }

        return result

    # -------------------------------------------------------------------
    # Sub-scorers
    # -------------------------------------------------------------------

    @staticmethod
    def _extract_resume_skills(text: str) -> list[str]:
        text_lower = text.lower()
        tokens = {tok.lower() for tok in re.findall(r"[a-zA-Z0-9.+#/-]+", text)}
        found: set[str] = set()
        for skill in KNOWN_SKILLS:
            if " " in skill:
                if skill in text_lower:
                    found.add(skill)
            else:
                if skill in tokens:
                    found.add(skill)
        return sorted(found)

    @staticmethod
    def _estimate_experience_years(text: str) -> float:
        import datetime as dt

        matches = _YEAR_RANGE_PATTERN.findall(text)
        if not matches:
            return 0.0

        current_year = dt.datetime.now().year
        total = 0.0
        for start_str, end_str in matches:
            try:
                start_year = int(start_str)
                end_year = (
                    current_year
                    if end_str.lower() in ("present", "current", "now")
                    else int(end_str)
                )
                years = max(0, end_year - start_year)
                total += min(years, 30)
            except (ValueError, TypeError):
                continue
        return round(total, 1)

    @staticmethod
    def _score_skill_match(
        resume_skills: list[str],
        required: list[str],
        optional: list[str],
    ) -> float:
        resume_set = {s.lower() for s in resume_skills}
        required_lower = [s.lower() for s in required]
        optional_lower = [s.lower() for s in optional]

        total_required = len(required_lower)
        total_optional = len(optional_lower)

        if total_required == 0 and total_optional == 0:
            return 50.0  # no skills to compare against

        required_matched = sum(1 for s in required_lower if s in resume_set)
        optional_matched = sum(1 for s in optional_lower if s in resume_set)

        required_ratio = (required_matched / total_required) if total_required else 1.0
        optional_ratio = (optional_matched / total_optional) if total_optional else 0.0

        # Required contributes 80% of skill score, optional 20%
        raw = required_ratio * 80.0 + optional_ratio * 20.0
        return round(min(100.0, max(0.0, raw)), 1)

    @staticmethod
    def _score_experience(
        detected_years: float,
        exp_min: int | None,
        exp_max: int | None,
    ) -> float:
        if exp_min is None and exp_max is None:
            return 50.0  # no requirement specified

        lo = exp_min or 0
        hi = exp_max or (lo + 5)

        if lo <= detected_years <= hi:
            return 100.0

        if detected_years < lo:
            deficit = lo - detected_years
            # Lose 15 points per year under minimum
            return max(0.0, 100.0 - deficit * 15.0)

        # Over-qualified
        surplus = detected_years - hi
        # Lose 8 points per year over max (softer penalty)
        return max(0.0, 100.0 - surplus * 8.0)

    @staticmethod
    def _score_role_alignment(resume_text: str, responsibilities_text: str) -> float:
        if not responsibilities_text.strip():
            return 50.0

        model = _get_sentence_model()
        if model is None:
            # Fallback: keyword overlap ratio
            resume_tokens = set(resume_text.lower().split())
            resp_tokens = set(responsibilities_text.lower().split())
            if not resp_tokens:
                return 50.0
            overlap = len(resume_tokens & resp_tokens)
            ratio = overlap / len(resp_tokens)
            return round(min(100.0, ratio * 100.0), 1)

        # Sentence-transformer cosine similarity
        vectors = model.encode([resume_text[:2000], responsibilities_text[:2000]])
        a, b = vectors[0], vectors[1]
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = math.sqrt(sum(float(x) ** 2 for x in a))
        norm_b = math.sqrt(sum(float(x) ** 2 for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        cosine = dot / (norm_a * norm_b)
        clamped = max(0.0, min(1.0, cosine))
        return round(clamped * 100.0, 1)

    @staticmethod
    def _score_seniority_fit(detected_years: float, target_seniority: str) -> float:
        band = _SENIORITY_BANDS.get(target_seniority.lower(), (2, 5))
        lo, hi = band

        if lo <= detected_years <= hi:
            return 100.0

        if detected_years < lo:
            deficit = lo - detected_years
            return max(0.0, 100.0 - deficit * 20.0)

        surplus = detected_years - hi
        return max(0.0, 100.0 - surplus * 10.0)

    @staticmethod
    def _score_quality(text: str) -> float:
        """Resume quality heuristics — section coverage, contact info, length."""
        text_lower = text.lower()
        word_count = len(text.split())

        # Section detection
        sections_found = 0
        for keywords in _SECTION_PATTERNS.values():
            for kw in keywords:
                if kw in text_lower:
                    sections_found += 1
                    break

        # Contact info
        has_email = bool(_EMAIL_PATTERN.search(text))
        has_phone = bool(_PHONE_PATTERN.search(text))
        contact_score = 20.0 if (has_email or has_phone) else 0.0

        # Sections: 6 possible, each worth ~10 pts
        section_score = min(60.0, sections_found * 10.0)

        # Word count: 300+ is good
        if word_count >= 300:
            length_score = 20.0
        elif word_count >= 100:
            length_score = (word_count - 100) * (20.0 / 200)
        else:
            length_score = 0.0

        raw = contact_score + section_score + length_score
        return round(min(100.0, max(0.0, raw)), 1)
