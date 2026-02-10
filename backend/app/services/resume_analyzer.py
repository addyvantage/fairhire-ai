"""Standalone resume analysis service.

Performs heuristic analysis on a resume without requiring a job description:
- Keyword / skill extraction (expanded skill set)
- Section detection (education, experience, skills, projects, certifications)
- Experience years estimation
- Contact info detection
- Heuristic quality scoring (60-95 range)
"""

from __future__ import annotations

import re
from typing import Any


# Expanded skill set for standalone extraction
_KNOWN_SKILLS: set[str] = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    # Web frameworks
    "react", "angular", "vue", "next.js", "nuxt", "django", "flask",
    "fastapi", "express", "spring", "rails", "laravel",
    # Data / ML
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "spark",
    "hadoop", "kafka", "airflow", "mlflow", "jupyter",
    "nlp", "ml", "deep learning", "machine learning", "data science",
    # Databases
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "sqlite", "oracle",
    # Cloud & DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "jenkins", "github actions", "gitlab ci", "ci/cd", "ansible",
    # Tools & Platforms
    "git", "linux", "jira", "figma", "tableau", "power bi",
    "rest", "graphql", "grpc", "microservices",
    # Soft skills / domains
    "agile", "scrum", "leadership", "project management",
}

# Section heading patterns (case-insensitive)
_SECTION_PATTERNS: dict[str, list[str]] = {
    "education": ["education", "academic", "university", "degree", "bachelor", "master", "phd"],
    "experience": ["experience", "employment", "work history", "professional background"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "projects": ["projects", "portfolio", "personal projects", "open source"],
    "certifications": ["certifications", "certificates", "licenses", "credentials"],
    "summary": ["summary", "objective", "profile", "about me", "professional summary"],
}

# Patterns for estimating years of experience
_YEAR_RANGE_PATTERN = re.compile(
    r"(\b(?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current|now)",
    re.IGNORECASE,
)

# Contact info patterns
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)


def analyze_resume(text: str) -> dict[str, Any]:
    """Run full standalone analysis on resume text.

    Returns a dict with:
        match_score: float (60-95 heuristic score)
        extracted_metadata: dict with skills, sections, experience, etc.
    """
    skills = _extract_skills(text)
    sections = _detect_sections(text)
    experience_years = _estimate_experience_years(text)
    contact_info = _detect_contact_info(text)
    word_count = len(text.split())

    score = _compute_score(
        skills=skills,
        sections=sections,
        experience_years=experience_years,
        has_contact=bool(contact_info),
        word_count=word_count,
    )

    metadata: dict[str, Any] = {
        "skills": skills,
        "skill_count": len(skills),
        "sections_detected": sections,
        "section_count": len(sections),
        "experience_years": experience_years,
        "contact_info": contact_info,
        "word_count": word_count,
    }

    return {
        "match_score": score,
        "extracted_metadata": metadata,
    }


def _extract_skills(text: str) -> list[str]:
    """Extract known skills from resume text."""
    text_lower = text.lower()
    # Tokenize for single-word skills
    tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9.+#/-]+", text)}
    found: set[str] = set()

    for skill in _KNOWN_SKILLS:
        if " " in skill:
            # Multi-word skills: substring match
            if skill in text_lower:
                found.add(skill)
        else:
            # Single-word skills: token match
            if skill in tokens:
                found.add(skill)

    return sorted(found)


def _detect_sections(text: str) -> list[str]:
    """Detect which standard resume sections are present."""
    text_lower = text.lower()
    detected: list[str] = []

    for section_name, keywords in _SECTION_PATTERNS.items():
        for keyword in keywords:
            if keyword in text_lower:
                detected.append(section_name)
                break

    return sorted(detected)


def _estimate_experience_years(text: str) -> float:
    """Estimate total years of experience from date ranges."""
    matches = _YEAR_RANGE_PATTERN.findall(text)
    if not matches:
        return 0.0

    import datetime as dt

    current_year = dt.datetime.now().year
    total_years = 0.0

    for start_str, end_str in matches:
        try:
            start_year = int(start_str)
            if end_str.lower() in ("present", "current", "now"):
                end_year = current_year
            else:
                end_year = int(end_str)

            years = max(0, end_year - start_year)
            # Cap individual ranges at 30 years (sanity check)
            total_years += min(years, 30)
        except (ValueError, TypeError):
            continue

    return round(total_years, 1)


def _detect_contact_info(text: str) -> dict[str, bool]:
    """Detect presence of contact information (not the values themselves)."""
    return {
        "has_email": bool(_EMAIL_PATTERN.search(text)),
        "has_phone": bool(_PHONE_PATTERN.search(text)),
        "has_linkedin": bool(_LINKEDIN_PATTERN.search(text)),
    }


def _compute_score(
    skills: list[str],
    sections: list[str],
    experience_years: float,
    has_contact: bool,
    word_count: int,
) -> float:
    """Compute a heuristic quality score in the 60-95 range.

    Scoring breakdown:
    - Skills breadth (0-25 points)
    - Section completeness (0-25 points)
    - Experience depth (0-20 points)
    - Content length (0-15 points)
    - Contact info (0-10 points)

    Base score: 60. Max additional: 35 points → range [60, 95].
    """
    # Skills: more skills → higher score, diminishing returns
    skill_count = len(skills)
    if skill_count >= 10:
        skill_score = 25.0
    elif skill_count >= 5:
        skill_score = 15.0 + (skill_count - 5) * 2.0
    elif skill_count >= 1:
        skill_score = skill_count * 3.0
    else:
        skill_score = 0.0

    # Sections: reward completeness
    expected_sections = {"education", "experience", "skills"}
    bonus_sections = {"projects", "certifications", "summary"}
    present_expected = len(expected_sections & set(sections))
    present_bonus = len(bonus_sections & set(sections))
    section_score = (present_expected / len(expected_sections)) * 18.0 + min(present_bonus * 2.33, 7.0)

    # Experience: more years → higher score, capped
    if experience_years >= 10:
        exp_score = 20.0
    elif experience_years >= 5:
        exp_score = 12.0 + (experience_years - 5) * 1.6
    elif experience_years >= 1:
        exp_score = experience_years * 2.4
    else:
        exp_score = 0.0

    # Content length: reasonable length is good, too short is bad
    if word_count >= 300:
        length_score = 15.0
    elif word_count >= 150:
        length_score = 8.0 + (word_count - 150) * (7.0 / 150)
    elif word_count >= 50:
        length_score = (word_count - 50) * (8.0 / 100)
    else:
        length_score = 0.0

    # Contact info
    contact_score = 10.0 if has_contact else 0.0

    raw = 60.0 + (skill_score + section_score + exp_score + length_score + contact_score) * (35.0 / 95.0)

    return round(min(max(raw, 60.0), 95.0), 1)
