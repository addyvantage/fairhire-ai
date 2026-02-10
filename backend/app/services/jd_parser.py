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

from app.services.skill_taxonomy import (
    DOMAIN_KEYWORDS,
    KNOWN_SKILLS,
    SOFT_SKILL_KEYWORDS,
    canonicalize_skill,
    expand_skill_aliases,
    normalize_term,
)


@dataclass
class ParsedJobDescription:
    role_title: str = ""
    normalized_title: str = ""
    seniority_level: str = "mid"
    years_experience_required: dict[str, int | None] = field(
        default_factory=lambda: {"min": None, "max": None}
    )
    education_requirements: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    hard_requirements: list[str] = field(default_factory=list)
    soft_requirements: list[str] = field(default_factory=list)
    tools_and_technologies: list[str] = field(default_factory=list)
    domain_keywords: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    ats_keywords: list[str] = field(default_factory=list)
    responsibility_clusters: dict[str, list[str]] = field(default_factory=dict)
    weight_map: dict[str, float] = field(default_factory=dict)
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
        result.role_title = title_hint.strip() or self._extract_title(raw_text)
        result.normalized_title = self._normalize_title(result.role_title)
        result.seniority_level = self._extract_seniority(raw_text, result.role_title)

        required, optional = self._extract_skills(raw_text)
        result.required_skills = required
        result.optional_skills = optional

        exp_min, exp_max = self._extract_experience_years(raw_text)
        result.years_experience_min = exp_min
        result.years_experience_max = exp_max
        result.years_experience_required = {"min": exp_min, "max": exp_max}

        result.responsibilities = self._extract_responsibilities(raw_text)
        result.hard_requirements, result.soft_requirements = self._extract_requirements(raw_text)
        result.education_requirements = self._extract_education(raw_text)
        result.certifications = self._extract_certifications(raw_text)
        result.domain_keywords = self._extract_domain_keywords(raw_text, result.role_title)
        result.soft_skills = self._extract_soft_skills(raw_text)

        result.tools_and_technologies = sorted(
            {
                *result.required_skills,
                *result.optional_skills,
                *self._extract_tools_from_requirements(result.hard_requirements, result.soft_requirements),
            }
        )
        result.ats_keywords = self._extract_ats_keywords(result)
        result.responsibility_clusters = self._cluster_responsibilities(result.responsibilities)
        result.weight_map = self._infer_weight_map(
            normalized_title=result.normalized_title,
            domain_keywords=result.domain_keywords,
            hard_requirements=result.hard_requirements,
            responsibilities=result.responsibilities,
        )
        return result

    # -------------------------------------------------------------------

    @staticmethod
    def _extract_title(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Target role"
        return lines[0][:120]

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
                        found.add(canonicalize_skill(skill))
                else:
                    if skill in segment_tokens:
                        found.add(canonicalize_skill(skill))
            for canonical, aliases in (
                (key, expand_skill_aliases(key)) for key in KNOWN_SKILLS
            ):
                if canonical in found:
                    continue
                if any(alias in seg_lower for alias in aliases if " " in alias):
                    found.add(canonical)
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

    @staticmethod
    def _extract_requirements(text: str) -> tuple[list[str], list[str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hard: list[str] = []
        soft: list[str] = []

        for line in lines:
            normalized = re.sub(r"^\s*(?:[-*•●◦▪]|\d+[.)]\s)", "", line).strip()
            if len(normalized) < 8:
                continue
            line_lower = normalized.lower()
            if _OPTIONAL_MARKERS.search(line_lower):
                soft.append(normalized)
                continue
            if _REQUIRED_MARKERS.search(line_lower):
                hard.append(normalized)
                continue

            if any(marker in line_lower for marker in ("responsible for", "you will", "you'll", "ability to")):
                hard.append(normalized)
            elif any(marker in line_lower for marker in ("preferred", "nice to have", "plus", "exposure to")):
                soft.append(normalized)

        return hard[:20], soft[:20]

    @staticmethod
    def _extract_education(text: str) -> list[str]:
        education_patterns = [
            r"(bachelor'?s degree[^.\n]*)",
            r"(master'?s degree[^.\n]*)",
            r"(mba[^.\n]*)",
            r"(phd[^.\n]*)",
            r"(degree in [^.\n]*)",
        ]
        found: set[str] = set()
        for pattern in education_patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                found.add(match.strip(" ."))
        return sorted(found)

    @staticmethod
    def _extract_certifications(text: str) -> list[str]:
        certification_patterns = [
            r"(cfa(?: level [123])?)",
            r"(cpa)",
            r"(pmp)",
            r"(six sigma[^,\n.]*)",
            r"(aws certified[^,\n.]*)",
            r"(certification[s]?:?[^.\n]*)",
        ]
        found: set[str] = set()
        for pattern in certification_patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                found.add(match.strip(" ."))
        return sorted(found)

    @staticmethod
    def _extract_domain_keywords(text: str, title: str) -> list[str]:
        source = f"{text} {title}".lower()
        keywords: set[str] = set()
        for domain_terms in DOMAIN_KEYWORDS.values():
            for term in domain_terms:
                if term in source:
                    keywords.add(term)
        return sorted(keywords)

    @staticmethod
    def _extract_soft_skills(text: str) -> list[str]:
        source = text.lower()
        extracted: set[str] = set()
        for skill in SOFT_SKILL_KEYWORDS:
            if skill in source:
                extracted.add(skill)
        return sorted(extracted)

    @staticmethod
    def _extract_tools_from_requirements(hard: list[str], soft: list[str]) -> list[str]:
        combined = " ".join([*hard, *soft]).lower()
        tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9.+#/-]+", combined)}
        extracted: set[str] = set()
        for skill in KNOWN_SKILLS:
            if " " in skill and skill in combined:
                extracted.add(skill)
            elif skill in tokens:
                extracted.add(skill)
        return sorted(extracted)

    @staticmethod
    def _extract_ats_keywords(parsed: ParsedJobDescription) -> list[str]:
        keywords: set[str] = set()

        for term in [
            *parsed.required_skills,
            *parsed.optional_skills,
            *parsed.soft_skills,
            *parsed.domain_keywords,
        ]:
            canonical = canonicalize_skill(term)
            keywords.add(canonical)
            for alias in expand_skill_aliases(canonical):
                keywords.add(alias)

        for requirement in [*parsed.hard_requirements, *parsed.soft_requirements]:
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+/.-]{2,}", requirement.lower()):
                normalized = normalize_term(token)
                if normalized in KNOWN_SKILLS or normalized in parsed.domain_keywords:
                    keywords.add(normalized)

        return sorted(keywords)

    @staticmethod
    def _cluster_responsibilities(responsibilities: list[str]) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {
            "delivery_execution": [],
            "analysis_decisioning": [],
            "collaboration_stakeholders": [],
            "leadership_ownership": [],
        }
        for item in responsibilities:
            text = item.lower()
            if any(keyword in text for keyword in ("build", "develop", "execute", "deliver", "implement")):
                clusters["delivery_execution"].append(item)
            elif any(keyword in text for keyword in ("analyze", "model", "report", "insight", "measure")):
                clusters["analysis_decisioning"].append(item)
            elif any(keyword in text for keyword in ("stakeholder", "cross-functional", "client", "partner")):
                clusters["collaboration_stakeholders"].append(item)
            elif any(keyword in text for keyword in ("lead", "own", "mentor", "drive", "manage")):
                clusters["leadership_ownership"].append(item)
            else:
                clusters["delivery_execution"].append(item)
        return {key: value for key, value in clusters.items() if value}

    @staticmethod
    def _infer_weight_map(
        *,
        normalized_title: str,
        domain_keywords: list[str],
        hard_requirements: list[str],
        responsibilities: list[str],
    ) -> dict[str, float]:
        role_source = f"{normalized_title} {' '.join(domain_keywords)}".lower()
        base = {
            "skills_tools": 0.35,
            "responsibility_alignment": 0.25,
            "experience": 0.15,
            "domain_familiarity": 0.15,
            "communication_quality": 0.10,
        }

        if any(term in role_source for term in ("engineer", "developer", "ml", "devops")):
            base["skills_tools"] = 0.42
            base["responsibility_alignment"] = 0.23
            base["experience"] = 0.15
            base["domain_familiarity"] = 0.10
            base["communication_quality"] = 0.10
        elif any(term in role_source for term in ("finance", "financial", "risk", "analyst")):
            base["skills_tools"] = 0.30
            base["responsibility_alignment"] = 0.30
            base["experience"] = 0.18
            base["domain_familiarity"] = 0.15
            base["communication_quality"] = 0.07
        elif any(term in role_source for term in ("consulting", "consultant")):
            base["skills_tools"] = 0.24
            base["responsibility_alignment"] = 0.32
            base["experience"] = 0.16
            base["domain_familiarity"] = 0.16
            base["communication_quality"] = 0.12

        if len(hard_requirements) >= 10:
            base["skills_tools"] = min(0.5, base["skills_tools"] + 0.03)
            base["communication_quality"] = max(0.06, base["communication_quality"] - 0.01)
        if len(responsibilities) >= 10:
            base["responsibility_alignment"] = min(0.36, base["responsibility_alignment"] + 0.02)
            base["domain_familiarity"] = max(0.1, base["domain_familiarity"] - 0.01)

        total = sum(base.values()) or 1.0
        return {key: round(value / total, 3) for key, value in base.items()}
