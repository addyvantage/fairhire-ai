"""Deterministic job description parser.

This parser is designed for messy real-world JDs and enforces:
- explicit structural segmentation
- strict seniority overrides for entry/apprentice roles
- role-adaptive weighting metadata
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
    role_archetype: str = "general_business"
    seniority_level: str = "mid"
    years_experience_required: dict[str, int | None] = field(
        default_factory=lambda: {"min": None, "max": None}
    )
    education_requirements: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)

    company_context: list[str] = field(default_factory=list)
    role_summary: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    requirements_hard: list[str] = field(default_factory=list)
    requirements_soft: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

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
    years_experience_min: int | None = None
    years_experience_max: int | None = None


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
    "business analyst": "business analyst",
    "financial analyst": "financial analyst",
    "risk analyst": "risk analyst",
    "operations analyst": "operations analyst",
    "consulting analyst": "consulting analyst",
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

_ENTRY_OVERRIDE_RE = re.compile(
    r"\b(intern|internship|trainee|apprentice|graduate|entry[\s-]?level|junior)\b",
    re.IGNORECASE,
)

_SENIORITY_STRICT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(principal|staff|distinguished)\b", re.IGNORECASE), "principal"),
    (re.compile(r"\b(lead|team lead|tech lead)\b", re.IGNORECASE), "lead"),
    (re.compile(r"\b(senior|sr\.?)\b", re.IGNORECASE), "senior"),
    (re.compile(r"\b(mid[\s-]?level|intermediate|associate)\b", re.IGNORECASE), "mid"),
]

_EXP_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[-–—to]+\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)
_EXP_MIN_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)
_EXP_AT_LEAST_RE = re.compile(
    r"(?:at\s+least|minimum|min)\s*(\d{1,2})\s*(?:years?|yrs?)",
    re.IGNORECASE,
)

_REQUIRED_MARKERS = re.compile(
    r"(?:required|must[\s-]?have|minimum qualifications?|mandatory|essential)",
    re.IGNORECASE,
)
_OPTIONAL_MARKERS = re.compile(
    r"(?:preferred|nice[\s-]?to[\s-]?have|bonus|plus|desirable|optional)",
    re.IGNORECASE,
)
_RESPONSIBILITY_MARKERS = re.compile(
    r"(?:responsibilit|what you'?ll do|you will|day-to-day|key duties)",
    re.IGNORECASE,
)
_SUMMARY_MARKERS = re.compile(
    r"(?:about the role|role overview|position summary|summary)",
    re.IGNORECASE,
)
_COMPANY_MARKERS = re.compile(
    r"(?:about us|about company|our values|culture|benefits|perks|equal opportunity|eeo|diversity|mission)",
    re.IGNORECASE,
)
_CONSTRAINT_MARKERS = re.compile(
    r"(?:degree|location|hybrid|remote|onsite|contract|full[- ]?time|part[- ]?time|visa|authorized|work permit|years?|yrs?)",
    re.IGNORECASE,
)

_BULLET_RE = re.compile(r"^\s*(?:[-*•●◦▪]|\d+[.)]\s)")
_ACTION_VERBS = (
    "build",
    "develop",
    "design",
    "analyze",
    "support",
    "implement",
    "own",
    "manage",
    "collaborate",
    "deliver",
    "optimize",
    "execute",
    "report",
    "monitor",
    "improve",
)
_KNOWN_SECTION_HEADINGS = frozenset(
    {
        "about us",
        "about the role",
        "role overview",
        "job summary",
        "summary",
        "responsibilities",
        "key responsibilities",
        "what you'll do",
        "minimum qualifications",
        "required qualifications",
        "requirements",
        "must have",
        "preferred qualifications",
        "nice to have",
        "benefits",
        "location",
        "contract",
    }
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = normalize_term(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(item.strip())
    return output


class JDParserService:
    """Parse raw job description text into structured fields."""

    def parse(self, raw_text: str, title_hint: str = "") -> ParsedJobDescription:
        result = ParsedJobDescription()
        result.role_title = title_hint.strip() or self._extract_title(raw_text)
        result.normalized_title = self._normalize_title(result.role_title)

        segments = self._segment_jd(raw_text)
        result.company_context = segments["company_context"]
        result.role_summary = segments["role_summary"]
        result.responsibilities = segments["responsibilities"] or self._extract_responsibilities(raw_text)
        result.requirements_hard = segments["requirements_hard"]
        result.requirements_soft = segments["requirements_soft"]
        result.constraints = segments["constraints"]

        result.hard_requirements = result.requirements_hard
        result.soft_requirements = result.requirements_soft

        seniority_source = " ".join(
            [result.role_title, *result.role_summary, *result.requirements_hard, *result.constraints]
        )
        result.seniority_level = self._extract_seniority(
            raw_text=seniority_source,
            full_text=raw_text,
            title=result.role_title,
        )
        result.role_archetype = self._infer_role_archetype(
            title=result.role_title,
            summary=result.role_summary,
            requirements=result.requirements_hard + result.requirements_soft,
        )

        required, optional = self._extract_skills_from_segments(
            hard_requirements=result.requirements_hard,
            soft_requirements=result.requirements_soft,
            responsibilities=result.responsibilities,
        )
        result.required_skills = required
        result.optional_skills = optional

        exp_min, exp_max = self._extract_experience_years(
            "\n".join([*result.constraints, *result.requirements_hard, *result.requirements_soft, raw_text])
        )
        result.years_experience_min = exp_min
        result.years_experience_max = exp_max
        result.years_experience_required = {"min": exp_min, "max": exp_max}

        result.education_requirements = self._extract_education(
            "\n".join([*result.constraints, *result.requirements_hard, *result.requirements_soft])
        )
        result.certifications = self._extract_certifications(
            "\n".join([*result.constraints, *result.requirements_hard, *result.requirements_soft])
        )
        result.domain_keywords = self._extract_domain_keywords(
            text="\n".join([*result.role_summary, *result.requirements_hard, *result.responsibilities]),
            title=result.role_title,
        )
        result.soft_skills = self._extract_soft_skills(
            "\n".join([*result.requirements_hard, *result.requirements_soft, *result.responsibilities])
        )

        result.tools_and_technologies = _dedupe(
            sorted(
                {
                    *result.required_skills,
                    *result.optional_skills,
                    *self._extract_tools_from_text(
                        "\n".join([*result.requirements_hard, *result.requirements_soft, *result.responsibilities])
                    ),
                }
            )
        )
        result.ats_keywords = self._extract_ats_keywords(result)
        result.responsibility_clusters = self._cluster_responsibilities(result.responsibilities)
        result.weight_map = self._infer_weight_map(
            role_archetype=result.role_archetype,
            seniority=result.seniority_level,
            hard_requirement_count=len(result.requirements_hard),
            responsibility_count=len(result.responsibilities),
        )
        return result

    @staticmethod
    def _extract_title(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return "Target role"
        first = lines[0]
        return first[:120]

    @staticmethod
    def _normalize_title(title: str) -> str:
        lower = title.strip().lower()
        stripped = re.sub(
            r"^(senior|sr\.?|junior|jr\.?|lead|principal|staff|intern|apprentice|graduate)\s+",
            "",
            lower,
        )
        return _TITLE_VARIANTS.get(stripped, stripped)

    def _segment_jd(self, raw_text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {
            "company_context": [],
            "role_summary": [],
            "responsibilities": [],
            "requirements_hard": [],
            "requirements_soft": [],
            "constraints": [],
        }
        current_section = "role_summary"
        lines = raw_text.splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            line_no_bullet = _BULLET_RE.sub("", line).strip()
            if len(line_no_bullet) < 3:
                continue
            line_lower = line_no_bullet.lower()

            if self._is_heading_line(line_no_bullet, raw_line):
                if _COMPANY_MARKERS.search(line_lower):
                    current_section = "company_context"
                elif _RESPONSIBILITY_MARKERS.search(line_lower):
                    current_section = "responsibilities"
                elif _REQUIRED_MARKERS.search(line_lower):
                    current_section = "requirements_hard"
                elif _OPTIONAL_MARKERS.search(line_lower):
                    current_section = "requirements_soft"
                elif _SUMMARY_MARKERS.search(line_lower):
                    current_section = "role_summary"
                elif _CONSTRAINT_MARKERS.search(line_lower):
                    current_section = "constraints"
                continue

            if self._is_company_context_line(line_lower):
                sections["company_context"].append(line_no_bullet)
                continue

            if self._is_constraint_line(line_lower):
                sections["constraints"].append(line_no_bullet)

            if _REQUIRED_MARKERS.search(line_lower):
                sections["requirements_hard"].append(line_no_bullet)
                current_section = "requirements_hard"
                continue
            if _OPTIONAL_MARKERS.search(line_lower):
                sections["requirements_soft"].append(line_no_bullet)
                current_section = "requirements_soft"
                continue

            if current_section in {"requirements_hard", "requirements_soft"}:
                sections[current_section].append(line_no_bullet)
                continue

            if current_section == "company_context":
                sections["company_context"].append(line_no_bullet)
                continue

            if self._looks_like_responsibility_line(line_no_bullet, raw_line):
                sections["responsibilities"].append(line_no_bullet)
                continue

            if current_section == "responsibilities":
                sections["responsibilities"].append(line_no_bullet)
                continue

            if len(sections["role_summary"]) < 8:
                sections["role_summary"].append(line_no_bullet)
            else:
                sections["company_context"].append(line_no_bullet)

        for key in sections:
            sections[key] = _dedupe(sections[key])

        return sections

    @staticmethod
    def _is_heading_line(line_no_bullet: str, raw_line: str) -> bool:
        stripped = raw_line.strip()
        lower = line_no_bullet.lower().strip()
        if not lower:
            return False
        if stripped.endswith(":"):
            return True
        if lower in _KNOWN_SECTION_HEADINGS:
            return True
        if len(line_no_bullet) <= 40 and line_no_bullet.isupper():
            return True
        return False

    @staticmethod
    def _is_company_context_line(line_lower: str) -> bool:
        if _COMPANY_MARKERS.search(line_lower):
            return True
        fluff_markers = (
            "benefits",
            "compensation",
            "equal opportunity",
            "our culture",
            "our mission",
            "our team",
            "we are committed",
        )
        return any(marker in line_lower for marker in fluff_markers)

    @staticmethod
    def _is_constraint_line(line_lower: str) -> bool:
        if _CONSTRAINT_MARKERS.search(line_lower):
            return True
        return bool(_EXP_RANGE_RE.search(line_lower) or _EXP_MIN_RE.search(line_lower) or _EXP_AT_LEAST_RE.search(line_lower))

    @staticmethod
    def _looks_like_responsibility_line(cleaned_line: str, raw_line: str) -> bool:
        if _BULLET_RE.match(raw_line):
            return True
        lower = cleaned_line.lower()
        return any(lower.startswith(verb + " ") for verb in _ACTION_VERBS)

    @staticmethod
    def _extract_seniority(*, raw_text: str, full_text: str, title: str) -> str:
        joined = f"{title} {full_text}"
        if _ENTRY_OVERRIDE_RE.search(joined):
            return "entry"

        title_lower = title.lower()
        for pattern, level in _SENIORITY_STRICT_PATTERNS:
            if pattern.search(title_lower):
                return level

        scannable = raw_text.lower()[:1600]
        for pattern, level in _SENIORITY_STRICT_PATTERNS:
            if pattern.search(scannable):
                return level

        return "mid"

    @staticmethod
    def _infer_role_archetype(
        *,
        title: str,
        summary: list[str],
        requirements: list[str],
    ) -> str:
        source = f"{title} {' '.join(summary)} {' '.join(requirements)}".lower()
        if any(term in source for term in ("engineer", "developer", "devops", "sre", "ml", "frontend", "backend")):
            return "engineering"
        if any(term in source for term in ("data analyst", "analytics", "business intelligence", "reporting", "dashboard")):
            return "data_analytics"
        if any(term in source for term in ("finance", "financial", "risk", "fp&a", "accounting", "valuation")):
            return "finance_risk"
        if any(term in source for term in ("consult", "operations", "process improvement", "client engagement")):
            return "consulting_ops"
        if any(term in source for term in ("product manager", "product strategy", "roadmap")):
            return "product"
        return "general_business"

    def _extract_skills_from_segments(
        self,
        *,
        hard_requirements: list[str],
        soft_requirements: list[str],
        responsibilities: list[str],
    ) -> tuple[list[str], list[str]]:
        hard_text = "\n".join([*hard_requirements, *responsibilities])
        soft_text = "\n".join(soft_requirements)

        required = self._extract_skills_from_text(hard_text)
        optional = self._extract_skills_from_text(soft_text)

        required_set = set(required)
        optional_clean = [item for item in optional if item not in required_set]
        return required, optional_clean

    @staticmethod
    def _extract_skills_from_text(text: str) -> list[str]:
        text_lower = text.lower()
        tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9.+#/-]+", text)}
        found: set[str] = set()
        for skill in KNOWN_SKILLS:
            canonical = canonicalize_skill(skill)
            aliases = expand_skill_aliases(canonical)
            if any(alias in tokens for alias in aliases if " " not in alias):
                found.add(canonical)
                continue
            if any(alias in text_lower for alias in aliases if " " in alias):
                found.add(canonical)
        return sorted(found)

    @staticmethod
    def _extract_experience_years(text: str) -> tuple[int | None, int | None]:
        range_match = _EXP_RANGE_RE.search(text)
        if range_match:
            lo = int(range_match.group(1))
            hi = int(range_match.group(2))
            return min(lo, hi), max(lo, hi)

        min_match = _EXP_MIN_RE.search(text)
        if min_match:
            val = int(min_match.group(1))
            return val, val + 2

        at_least_match = _EXP_AT_LEAST_RE.search(text)
        if at_least_match:
            val = int(at_least_match.group(1))
            return val, val + 2

        return None, None

    @staticmethod
    def _extract_responsibilities(text: str) -> list[str]:
        lines = text.splitlines()
        responsibilities: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            cleaned = _BULLET_RE.sub("", stripped).strip()
            if len(cleaned) < 10:
                continue
            lower = cleaned.lower()
            if any(lower.startswith(verb + " ") for verb in _ACTION_VERBS) or _BULLET_RE.match(stripped):
                responsibilities.append(cleaned)
        return _dedupe(responsibilities)[:30]

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
    def _extract_tools_from_text(text: str) -> list[str]:
        return JDParserService._extract_skills_from_text(text)

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
            keywords.update(expand_skill_aliases(canonical))

        for phrase in [*parsed.requirements_hard, *parsed.requirements_soft]:
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+/.-]{2,}", phrase.lower()):
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
            elif any(keyword in text for keyword in ("stakeholder", "cross-functional", "client", "partner", "collaborate")):
                clusters["collaboration_stakeholders"].append(item)
            elif any(keyword in text for keyword in ("lead", "mentor", "manage", "own", "drive")):
                clusters["leadership_ownership"].append(item)
            else:
                clusters["delivery_execution"].append(item)
        return {key: value for key, value in clusters.items() if value}

    @staticmethod
    def _infer_weight_map(
        *,
        role_archetype: str,
        seniority: str,
        hard_requirement_count: int,
        responsibility_count: int,
    ) -> dict[str, float]:
        weight_profiles: dict[str, dict[str, float]] = {
            "engineering": {
                "skills_tools": 0.34,
                "responsibility_alignment": 0.28,
                "domain_familiarity": 0.08,
                "seniority_fit": 0.10,
                "experience_sufficiency": 0.12,
                "resume_quality": 0.08,
            },
            "data_analytics": {
                "skills_tools": 0.26,
                "responsibility_alignment": 0.30,
                "domain_familiarity": 0.14,
                "seniority_fit": 0.08,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.08,
            },
            "finance_risk": {
                "skills_tools": 0.22,
                "responsibility_alignment": 0.30,
                "domain_familiarity": 0.18,
                "seniority_fit": 0.08,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.08,
            },
            "consulting_ops": {
                "skills_tools": 0.16,
                "responsibility_alignment": 0.33,
                "domain_familiarity": 0.19,
                "seniority_fit": 0.08,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.10,
            },
            "product": {
                "skills_tools": 0.20,
                "responsibility_alignment": 0.31,
                "domain_familiarity": 0.16,
                "seniority_fit": 0.09,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.10,
            },
            "general_business": {
                "skills_tools": 0.22,
                "responsibility_alignment": 0.30,
                "domain_familiarity": 0.14,
                "seniority_fit": 0.09,
                "experience_sufficiency": 0.15,
                "resume_quality": 0.10,
            },
        }
        base = dict(weight_profiles.get(role_archetype, weight_profiles["general_business"]))

        if seniority == "entry":
            base["skills_tools"] = max(0.15, base["skills_tools"] - 0.06)
            base["responsibility_alignment"] = min(0.36, base["responsibility_alignment"] + 0.02)
            base["experience_sufficiency"] = max(0.10, base["experience_sufficiency"] - 0.04)
            base["resume_quality"] = min(0.14, base["resume_quality"] + 0.03)

        if hard_requirement_count >= 12:
            base["skills_tools"] = min(0.38, base["skills_tools"] + 0.03)
            base["resume_quality"] = max(0.06, base["resume_quality"] - 0.01)
        if responsibility_count >= 12:
            base["responsibility_alignment"] = min(0.38, base["responsibility_alignment"] + 0.02)
            base["domain_familiarity"] = max(0.08, base["domain_familiarity"] - 0.01)

        total = sum(base.values()) or 1.0
        return {key: round(value / total, 3) for key, value in base.items()}
