"""Rule-based job description parser.

Extracts structured data from raw JD text:
- Seniority level
- Required vs optional skills
- Experience years range
- Responsibilities
- Normalized title
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.skill_taxonomy import KNOWN_SKILLS


@dataclass
class ParsedJobDescription:
    normalized_title: str = ""
    seniority_level: str = "mid"
    required_skills: list[str] = field(default_factory=list)
    optional_skills: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    years_experience_min: int | None = None
    years_experience_max: int | None = None


# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------

_TITLE_VARIANTS: dict[str, str] = {
    "frontend developer": "frontend engineer",
    "front-end developer": "frontend engineer",
    "front-end engineer": "frontend engineer",
    "front end developer": "frontend engineer",
    "front end engineer": "frontend engineer",
    "ui developer": "frontend engineer",
    "ui engineer": "frontend engineer",
    "backend developer": "backend engineer",
    "back-end developer": "backend engineer",
    "back-end engineer": "backend engineer",
    "back end developer": "backend engineer",
    "back end engineer": "backend engineer",
    "server-side developer": "backend engineer",
    "full stack developer": "full-stack developer",
    "full-stack engineer": "full-stack developer",
    "fullstack developer": "full-stack developer",
    "fullstack engineer": "full-stack developer",
    "software developer": "software engineer",
    "swe": "software engineer",
    "sde": "software engineer",
    "data analyst": "data analyst",
    "business analyst": "data analyst",
    "data engineer": "data engineer",
    "ml engineer": "ml engineer",
    "machine learning engineer": "ml engineer",
    "ai engineer": "ml engineer",
    "devops engineer": "devops engineer",
    "site reliability engineer": "devops engineer",
    "sre": "devops engineer",
    "platform engineer": "devops engineer",
    "product manager": "product manager",
    "pm": "product manager",
    "ux designer": "ux designer",
    "ui/ux designer": "ux designer",
    "product designer": "ux designer",
}

# ---------------------------------------------------------------------------
# Seniority keywords
# ---------------------------------------------------------------------------

_SENIORITY_MAP: dict[str, str] = {
    "intern": "intern",
    "internship": "intern",
    "junior": "junior",
    "entry level": "junior",
    "entry-level": "junior",
    "associate": "junior",
    "mid": "mid",
    "mid-level": "mid",
    "mid level": "mid",
    "intermediate": "mid",
    "senior": "senior",
    "sr.": "senior",
    "sr ": "senior",
    "lead": "lead",
    "tech lead": "lead",
    "team lead": "lead",
    "principal": "principal",
    "staff": "staff",
    "architect": "staff",
    "distinguished": "staff",
    "director": "staff",
    "vp": "staff",
}

# ---------------------------------------------------------------------------
# Experience years patterns
# ---------------------------------------------------------------------------

_EXP_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[-–—to]+\s*(\d{1,2})\s*(?:\+)?\s*years?",
    re.IGNORECASE,
)
_EXP_MIN_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*years?\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)
_EXP_AT_LEAST_RE = re.compile(
    r"(?:at\s+least|minimum|min)\s*(\d{1,2})\s*years?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Section detection for required vs optional skills
# ---------------------------------------------------------------------------

_REQUIRED_MARKERS = re.compile(
    r"(?:required|must[\s-]have|minimum|essential|need|mandatory)",
    re.IGNORECASE,
)
_OPTIONAL_MARKERS = re.compile(
    r"(?:nice[\s-]to[\s-]have|preferred|bonus|desirable|plus|optional|ideally)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bullet extraction
# ---------------------------------------------------------------------------

_BULLET_RE = re.compile(r"^\s*(?:[-*•●◦▪]|\d+[.)]\s)", re.MULTILINE)


class JDParserService:
    """Parse raw job description text into structured fields."""

    def parse(self, raw_text: str, title_hint: str = "") -> ParsedJobDescription:
        result = ParsedJobDescription()
        result.normalized_title = self._normalize_title(title_hint)
        result.seniority_level = self._extract_seniority(raw_text, title_hint)

        required, optional = self._extract_skills(raw_text)
        result.required_skills = required
        result.optional_skills = optional

        exp_min, exp_max = self._extract_experience_years(raw_text)
        result.years_experience_min = exp_min
        result.years_experience_max = exp_max

        result.responsibilities = self._extract_responsibilities(raw_text)
        return result

    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_title(title: str) -> str:
        lower = title.strip().lower()
        # Strip seniority prefixes for canonical lookup
        stripped = re.sub(
            r"^(senior|sr\.?|junior|jr\.?|lead|principal|staff|intern)\s+",
            "",
            lower,
        )
        return _TITLE_VARIANTS.get(stripped, stripped)

    @staticmethod
    def _extract_seniority(text: str, title: str) -> str:
        combined = f"{title} {text}".lower()
        # Check title first (more reliable)
        for keyword, level in _SENIORITY_MAP.items():
            if keyword in title.lower():
                return level
        # Fall back to body text (first 500 chars more likely to have it)
        snippet = combined[:500]
        for keyword, level in _SENIORITY_MAP.items():
            if keyword in snippet:
                return level
        return "mid"  # default

    @staticmethod
    def _extract_skills(text: str) -> tuple[list[str], list[str]]:
        """Split skills into required and optional based on context.

        Strategy: split text at optional-marker headings. Skills found
        before the first optional marker are 'required'; skills after
        are 'optional'. If no markers found, all skills go to required.
        """
        text_lower = text.lower()
        tokens = {tok.lower() for tok in re.findall(r"[a-zA-Z0-9.+#/-]+", text)}

        def _find_skills_in(segment: str, segment_tokens: set[str]) -> list[str]:
            seg_lower = segment.lower()
            found: set[str] = set()
            for skill in KNOWN_SKILLS:
                if " " in skill:
                    if skill in seg_lower:
                        found.add(skill)
                else:
                    if skill in segment_tokens:
                        found.add(skill)
            return sorted(found)

        # Try to find an optional section boundary
        optional_match = _OPTIONAL_MARKERS.search(text)
        if optional_match:
            boundary = optional_match.start()
            required_section = text[:boundary]
            optional_section = text[boundary:]

            req_tokens = {
                tok.lower()
                for tok in re.findall(r"[a-zA-Z0-9.+#/-]+", required_section)
            }
            opt_tokens = {
                tok.lower()
                for tok in re.findall(r"[a-zA-Z0-9.+#/-]+", optional_section)
            }

            required = _find_skills_in(required_section, req_tokens)
            optional_raw = _find_skills_in(optional_section, opt_tokens)
            # Remove any skills already in required from optional
            required_set = set(required)
            optional = [s for s in optional_raw if s not in required_set]
            return required, optional

        # No optional boundary — all skills are required
        all_skills = _find_skills_in(text_lower, tokens)
        return all_skills, []

    @staticmethod
    def _extract_experience_years(text: str) -> tuple[int | None, int | None]:
        # Try range first: "3-5 years"
        range_match = _EXP_RANGE_RE.search(text)
        if range_match:
            lo = int(range_match.group(1))
            hi = int(range_match.group(2))
            return (min(lo, hi), max(lo, hi))

        # Try "X+ years of experience"
        min_match = _EXP_MIN_RE.search(text)
        if min_match:
            val = int(min_match.group(1))
            return (val, val + 3)  # heuristic: X+ ≈ X to X+3

        # Try "at least X years"
        at_least_match = _EXP_AT_LEAST_RE.search(text)
        if at_least_match:
            val = int(at_least_match.group(1))
            return (val, val + 3)

        return (None, None)

    @staticmethod
    def _extract_responsibilities(text: str) -> list[str]:
        """Extract bullet-point items as responsibilities."""
        lines = text.split("\n")
        responsibilities: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _BULLET_RE.match(stripped):
                # Remove the bullet prefix
                cleaned = _BULLET_RE.sub("", stripped).strip()
                if len(cleaned) > 10:  # skip very short fragments
                    responsibilities.append(cleaned)

        # Limit to a reasonable number
        return responsibilities[:20]
