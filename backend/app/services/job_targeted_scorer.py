"""Evidence-first Resume × JobProfile scoring engine.

Design goals:
- deterministic and auditable scoring
- role-adaptive expectations
- strict entry-level handling (intern/apprentice/graduate/junior)
- evidence-based requirement matching (direct/equivalent/implied/semantic)
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.local_reasoner import LocalReasoner
from app.services.skill_taxonomy import (
    DOMAIN_KEYWORDS,
    KNOWN_SKILLS,
    canonicalize_skill,
    expand_skill_aliases,
    normalize_term,
)

logger = logging.getLogger(__name__)


@dataclass
class JobProfileData:
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
    overall_match_score: float = 0.0
    skill_match_score: float = 0.0
    experience_match_score: float = 0.0
    role_alignment_score: float = 0.0
    seniority_fit_score: float = 0.0
    quality_score: float = 0.0
    gaps: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    explanation_summary: str = ""
    recruiter_verdict: str = ""
    rejection_risks: list[str] = field(default_factory=list)
    fastest_fixes: list[str] = field(default_factory=list)
    matched_requirements: list[dict[str, Any]] = field(default_factory=list)
    missing_requirements: list[dict[str, Any]] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    rewrite_suggestions: list[dict[str, str]] = field(default_factory=list)
    ats_keyword_map: list[dict[str, Any]] = field(default_factory=list)
    resume_vs_jd_comparison: list[dict[str, Any]] = field(default_factory=list)
    dimension_scores: list[dict[str, Any]] = field(default_factory=list)
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
            "recruiter_verdict": self.recruiter_verdict,
            "rejection_risks": self.rejection_risks,
            "fastest_fixes": self.fastest_fixes,
            "matched_requirements": self.matched_requirements,
            "missing_requirements": self.missing_requirements,
            "missing_evidence": self.missing_evidence,
            "rewrite_suggestions": self.rewrite_suggestions,
            "ats_keyword_map": self.ats_keyword_map,
            "resume_vs_jd_comparison": self.resume_vs_jd_comparison,
            "dimension_scores": self.dimension_scores,
            "details": self.details,
        }


_SENIORITY_BANDS: dict[str, tuple[int, int]] = {
    "entry": (0, 2),
    "intern": (0, 1),
    "junior": (0, 2),
    "mid": (2, 5),
    "senior": (5, 10),
    "lead": (7, 15),
    "principal": (10, 20),
    "staff": (10, 25),
}

_ENTRY_TERMS_RE = re.compile(
    r"\b(intern|internship|trainee|apprentice|graduate|entry[\s-]?level|junior)\b",
    re.IGNORECASE,
)
_YEAR_RANGE_PATTERN = re.compile(
    r"(\b(?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current|now)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_IMPACT_PATTERN = re.compile(r"(\d+[%x]|[$€£]\s?\d+|\d+\s?(k|m|b)|\d+\+?)", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*•●◦▪]|\d+[.)]\s)")

_SECTION_PATTERNS: dict[str, list[str]] = {
    "summary": ["summary", "objective", "profile", "about"],
    "experience": ["experience", "employment", "work history"],
    "projects": ["projects", "portfolio", "case studies"],
    "skills": ["skills", "technical skills", "core competencies"],
    "education": ["education", "degree", "university"],
}

_LEADERSHIP_REQUIREMENTS = frozenset(
    {
        "leadership",
        "team leadership",
        "people management",
        "mentoring",
        "stakeholder management",
        "project management",
    }
)
_COMMUNICATION_REQUIREMENTS = frozenset(
    {"communication", "stakeholder management", "cross-functional collaboration"}
)

_ROLE_ARCHETYPE_PROFILES: dict[str, dict[str, Any]] = {
    "engineering": {
        "weights": {
            "skills_tools": 0.34,
            "responsibility_alignment": 0.28,
            "domain_familiarity": 0.08,
            "seniority_fit": 0.10,
            "experience_sufficiency": 0.12,
            "resume_quality": 0.08,
        },
        "communication_definition": "technical clarity, collaboration with product/design, and handoff quality",
        "evidence_keywords": {"systems", "api", "service", "architecture", "performance", "deployment"},
        "tool_penalty_factor": 1.0,
        "required_semantic_threshold": 0.43,
        "optional_semantic_threshold": 0.48,
    },
    "data_analytics": {
        "weights": {
            "skills_tools": 0.26,
            "responsibility_alignment": 0.30,
            "domain_familiarity": 0.14,
            "seniority_fit": 0.08,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.08,
        },
        "communication_definition": "clear insight storytelling, metric framing, and stakeholder readability",
        "evidence_keywords": {"dashboard", "reporting", "kpi", "analysis", "insights", "variance"},
        "tool_penalty_factor": 0.9,
        "required_semantic_threshold": 0.42,
        "optional_semantic_threshold": 0.47,
    },
    "finance_risk": {
        "weights": {
            "skills_tools": 0.22,
            "responsibility_alignment": 0.30,
            "domain_familiarity": 0.18,
            "seniority_fit": 0.08,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.08,
        },
        "communication_definition": "decision-grade reporting, variance explanation, and stakeholder trust",
        "evidence_keywords": {"forecast", "budget", "variance", "p&l", "controls", "risk"},
        "tool_penalty_factor": 0.85,
        "required_semantic_threshold": 0.41,
        "optional_semantic_threshold": 0.46,
    },
    "consulting_ops": {
        "weights": {
            "skills_tools": 0.17,
            "responsibility_alignment": 0.33,
            "domain_familiarity": 0.19,
            "seniority_fit": 0.08,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.09,
        },
        "communication_definition": "structured problem-solving, client/stakeholder communication, and recommendation clarity",
        "evidence_keywords": {"client", "stakeholder", "recommendation", "process", "operations", "strategy"},
        "tool_penalty_factor": 0.8,
        "required_semantic_threshold": 0.40,
        "optional_semantic_threshold": 0.45,
    },
    "product": {
        "weights": {
            "skills_tools": 0.20,
            "responsibility_alignment": 0.31,
            "domain_familiarity": 0.16,
            "seniority_fit": 0.09,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.10,
        },
        "communication_definition": "cross-functional alignment, prioritization rationale, and outcome ownership",
        "evidence_keywords": {"roadmap", "prioritization", "user research", "experiments", "stakeholder"},
        "tool_penalty_factor": 0.85,
        "required_semantic_threshold": 0.42,
        "optional_semantic_threshold": 0.47,
    },
    "general_business": {
        "weights": {
            "skills_tools": 0.23,
            "responsibility_alignment": 0.30,
            "domain_familiarity": 0.14,
            "seniority_fit": 0.09,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.10,
        },
        "communication_definition": "clear execution communication and stakeholder coordination",
        "evidence_keywords": {"coordination", "execution", "operations", "reporting"},
        "tool_penalty_factor": 0.85,
        "required_semantic_threshold": 0.42,
        "optional_semantic_threshold": 0.47,
    },
}

_IMPLIED_EVIDENCE_RULES: dict[str, list[set[str]]] = {
    "power bi": [{"dashboard"}, {"kpi", "report"}],
    "tableau": [{"dashboard"}, {"visualization"}, {"kpi", "report"}],
    "data visualization": [{"dashboard"}, {"visualization"}, {"kpi", "report"}],
    "sql": [{"query"}, {"join"}, {"dataset"}, {"report", "data"}],
    "stakeholder management": [{"stakeholder"}, {"cross-functional"}, {"partnered"}],
    "communication": [{"presented"}, {"reported"}, {"communicated"}, {"stakeholder"}],
    "risk analysis": [{"risk"}, {"controls"}, {"mitigation"}],
    "financial modeling": [{"forecast"}, {"budget"}, {"variance"}, {"model"}],
}

_st_model = None


def _get_sentence_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model for scoring")
        except Exception:
            logger.warning(
                "sentence-transformers unavailable; semantic fallback disabled",
                exc_info=True,
            )
    return _st_model


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


class JobTargetedScorer:
    """Synchronous scorer used in worker context."""

    def __init__(self) -> None:
        self.reasoner = LocalReasoner()

    def score(self, resume_text: str, profile: JobProfileData) -> JobMatchResult:
        result = JobMatchResult()
        resume_text_lower = resume_text.lower()
        evidence_units = self._extract_evidence_units(resume_text)
        resume_skills = self._extract_resume_skills(resume_text)
        experience_years = self._estimate_experience_years(resume_text)

        role_archetype = self._infer_role_archetype(profile)
        seniority = self._normalize_seniority(profile)
        expectations = self._build_expectation_profile(role_archetype, seniority)
        semantic_ctx = self._build_semantic_context(evidence_units)

        assessments = self._assess_requirements(
            profile=profile,
            seniority=seniority,
            role_archetype=role_archetype,
            expectations=expectations,
            resume_text_lower=resume_text_lower,
            evidence_units=evidence_units,
            semantic_ctx=semantic_ctx,
        )

        required_all = [entry for entry in assessments if entry["category"] == "required"]
        optional_all = [entry for entry in assessments if entry["category"] == "optional"]
        required_blocking = [entry for entry in required_all if entry["blocking"]]
        required_nonblocking = [entry for entry in required_all if not entry["blocking"]]

        result.skill_match_score = self._score_skill_coverage(
            required_blocking=required_blocking,
            optional_all=optional_all + required_nonblocking,
            tool_penalty_factor=expectations["tool_penalty_factor"],
        )
        result.experience_match_score = self._score_experience(
            detected_years=experience_years,
            exp_min=profile.years_experience_min,
            exp_max=profile.years_experience_max,
            seniority=seniority,
        )
        result.role_alignment_score, result.resume_vs_jd_comparison = self._score_responsibility_alignment(
            responsibilities=profile.responsibilities,
            evidence_units=evidence_units,
            semantic_ctx=semantic_ctx,
            expectations=expectations,
            role_archetype=role_archetype,
        )
        result.seniority_fit_score = self._score_seniority_fit(experience_years, seniority)
        result.quality_score = self._score_quality(resume_text, role_archetype)
        domain_score, domain_hits, domain_missing = self._score_domain_familiarity(
            profile=profile,
            resume_text_lower=resume_text_lower,
            role_archetype=role_archetype,
        )

        weights = expectations["weights"]
        result.dimension_scores = [
            {"key": "skills_tools", "label": "Skills / Tools Evidence", "score": result.skill_match_score, "weight": round(weights["skills_tools"] * 100, 1)},
            {"key": "responsibility_alignment", "label": "Responsibility Alignment", "score": result.role_alignment_score, "weight": round(weights["responsibility_alignment"] * 100, 1)},
            {"key": "domain_familiarity", "label": "Domain Familiarity", "score": domain_score, "weight": round(weights["domain_familiarity"] * 100, 1)},
            {"key": "seniority_fit", "label": "Seniority Fit", "score": result.seniority_fit_score, "weight": round(weights["seniority_fit"] * 100, 1)},
            {"key": "experience_sufficiency", "label": "Experience Sufficiency", "score": result.experience_match_score, "weight": round(weights["experience_sufficiency"] * 100, 1)},
            {"key": "resume_quality", "label": "Resume Clarity", "score": result.quality_score, "weight": round(weights["resume_quality"] * 100, 1)},
        ]

        result.overall_match_score = round(
            result.skill_match_score * weights["skills_tools"]
            + result.role_alignment_score * weights["responsibility_alignment"]
            + domain_score * weights["domain_familiarity"]
            + result.seniority_fit_score * weights["seniority_fit"]
            + result.experience_match_score * weights["experience_sufficiency"]
            + result.quality_score * weights["resume_quality"],
            1,
        )

        matched_required = [entry for entry in required_all if entry["matched"]]
        missing_required = [entry for entry in required_all if entry["blocking"] and not entry["matched"]]
        matched_optional = [entry for entry in optional_all if entry["matched"]]
        weak_evidence = [
            entry for entry in matched_required
            if entry["evidence"] and not any(_IMPACT_PATTERN.search(snippet) for snippet in entry["evidence"])
        ]

        result.matched_requirements = matched_required
        result.missing_requirements = missing_required
        result.missing_evidence = self._build_missing_evidence(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
        )
        result.rewrite_suggestions = self._build_rewrite_suggestions(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
            evidence_units=evidence_units,
            role_title=profile.title,
            role_archetype=role_archetype,
        )
        result.ats_keyword_map = self._build_ats_keyword_map(
            profile=profile,
            assessments=assessments,
            resume_text_lower=resume_text_lower,
            evidence_units=evidence_units,
            role_archetype=role_archetype,
        )

        result.strengths = self._build_strengths(
            matched_required=matched_required,
            matched_optional=matched_optional,
            domain_hits=domain_hits,
            experience_years=experience_years,
            role_alignment_score=result.role_alignment_score,
            role_archetype=role_archetype,
        )
        result.gaps = self._build_gaps(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
            domain_missing=domain_missing,
            experience_years=experience_years,
            profile=profile,
            seniority=seniority,
        )
        result.rejection_risks = self._build_rejection_risks(
            missing_required=missing_required,
            role_alignment_score=result.role_alignment_score,
            weak_evidence=weak_evidence,
            seniority=seniority,
        )
        result.fastest_fixes = self._build_fastest_fixes(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
            domain_missing=domain_missing,
            seniority=seniority,
        )

        result.explanation_summary = self._build_explanation_summary(
            overall=result.overall_match_score,
            profile_title=profile.title,
            matched_required=len([entry for entry in required_all if entry["matched"]]),
            total_required=len(required_all),
            missing_required=missing_required,
            role_alignment_score=result.role_alignment_score,
        )
        result.recruiter_verdict = self._build_recruiter_verdict(
            overall=result.overall_match_score,
            role_archetype=role_archetype,
            strengths=result.strengths,
            rejection_risks=result.rejection_risks,
        )

        self._apply_reasoner_enrichment(
            profile=profile,
            result=result,
            matched_required=matched_required,
            missing_required=missing_required,
        )

        required_names = {entry["requirement"] for entry in required_all}
        optional_names = {entry["requirement"] for entry in optional_all}
        resume_set = {skill.lower() for skill in resume_skills}
        evidence_map = {entry["requirement"]: entry["evidence"] for entry in assessments}

        result.details = {
            "resume_skills": resume_skills,
            "matched_required": sorted(entry["requirement"] for entry in matched_required),
            "matched_optional": sorted(entry["requirement"] for entry in matched_optional),
            "missing_required": sorted(entry["requirement"] for entry in missing_required),
            "extra_resume_skills": sorted(resume_set - {item.lower() for item in required_names | optional_names}),
            "experience_years_detected": experience_years,
            "cosine_similarity": round(result.role_alignment_score / 100.0, 4),
            "role_family": role_archetype,
            "role_archetype": role_archetype,
            "seniority_effective": seniority,
            "weights": weights,
            "domain_hits": domain_hits,
            "domain_missing": domain_missing,
            "communication_definition": expectations["communication_definition"],
            "evidence_map": evidence_map,
        }
        return result

    def _normalize_seniority(self, profile: JobProfileData) -> str:
        text = f"{profile.title} {profile.normalized_title} {profile.seniority_level}".lower()
        if _ENTRY_TERMS_RE.search(text):
            return "entry"
        level = normalize_term(profile.seniority_level or "mid")
        if level in _SENIORITY_BANDS:
            return level
        if level in {"intern", "junior"}:
            return "entry"
        return "mid"

    def _infer_role_archetype(self, profile: JobProfileData) -> str:
        source = f"{profile.title} {profile.normalized_title} {' '.join(profile.required_skills)} {' '.join(profile.responsibilities)}".lower()
        if any(term in source for term in ("engineer", "developer", "frontend", "backend", "devops", "sre", "ml")):
            return "engineering"
        if any(term in source for term in ("analytics", "analyst", "dashboard", "kpi", "reporting", "data")):
            return "data_analytics"
        if any(term in source for term in ("finance", "financial", "risk", "fp&a", "accounting", "valuation")):
            return "finance_risk"
        if any(term in source for term in ("consult", "operations", "process", "client")):
            return "consulting_ops"
        if any(term in source for term in ("product", "roadmap", "prioritization")):
            return "product"
        return "general_business"

    def _build_expectation_profile(self, role_archetype: str, seniority: str) -> dict[str, Any]:
        base = dict(_ROLE_ARCHETYPE_PROFILES.get(role_archetype, _ROLE_ARCHETYPE_PROFILES["general_business"]))
        base["weights"] = dict(base["weights"])
        if seniority == "entry":
            base["weights"]["skills_tools"] = max(0.15, base["weights"]["skills_tools"] - 0.06)
            base["weights"]["experience_sufficiency"] = max(0.08, base["weights"]["experience_sufficiency"] - 0.05)
            base["weights"]["resume_quality"] = min(0.16, base["weights"]["resume_quality"] + 0.04)
            base["weights"]["responsibility_alignment"] = min(0.36, base["weights"]["responsibility_alignment"] + 0.03)
            base["tool_penalty_factor"] = min(1.0, base["tool_penalty_factor"] * 0.65)
            base["required_semantic_threshold"] = max(0.35, base["required_semantic_threshold"] - 0.03)
            base["optional_semantic_threshold"] = max(0.39, base["optional_semantic_threshold"] - 0.03)
        total = sum(base["weights"].values()) or 1.0
        base["weights"] = {key: value / total for key, value in base["weights"].items()}
        return base

    @staticmethod
    def _extract_resume_skills(text: str) -> list[str]:
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
    def _extract_evidence_units(text: str) -> list[str]:
        chunks = re.split(r"[\n\r]+|(?<=[.!?])\s+", text)
        units: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            cleaned = _BULLET_RE.sub("", re.sub(r"\s+", " ", chunk).strip(" -•\t")).strip()
            if len(cleaned) < 20:
                continue
            normalized = normalize_term(cleaned)
            if normalized in seen:
                continue
            seen.add(normalized)
            units.append(cleaned)
        return units[:140]

    @staticmethod
    def _estimate_experience_years(text: str) -> float:
        matches = _YEAR_RANGE_PATTERN.findall(text)
        if not matches:
            return 0.0
        current_year = dt.datetime.now().year
        total = 0.0
        for start_str, end_str in matches:
            try:
                start_year = int(start_str)
                end_year = current_year if end_str.lower() in {"present", "current", "now"} else int(end_str)
                total += max(0, min(30, end_year - start_year))
            except (TypeError, ValueError):
                continue
        return round(total, 1)

    def _build_semantic_context(self, evidence_units: list[str]) -> dict[str, Any]:
        model = _get_sentence_model()
        if model is None or not evidence_units:
            return {"model": None, "unit_embeddings": []}
        try:
            embeddings = model.encode(evidence_units, normalize_embeddings=True)
            return {"model": model, "unit_embeddings": embeddings}
        except Exception:
            logger.warning("Failed to embed resume evidence units", exc_info=True)
            return {"model": None, "unit_embeddings": []}

    def _assess_requirements(
        self,
        *,
        profile: JobProfileData,
        seniority: str,
        role_archetype: str,
        expectations: dict[str, Any],
        resume_text_lower: str,
        evidence_units: list[str],
        semantic_ctx: dict[str, Any],
    ) -> list[dict[str, Any]]:
        assessments: list[dict[str, Any]] = []
        combined: list[tuple[str, str]] = []
        combined.extend(("required", item) for item in profile.required_skills)
        combined.extend(("optional", item) for item in profile.optional_skills)

        seen: set[tuple[str, str]] = set()
        for category, raw_requirement in combined:
            requirement = canonicalize_skill(raw_requirement)
            key = (category, requirement)
            if key in seen:
                continue
            seen.add(key)

            blocking = category == "required"
            if seniority == "entry" and requirement in _LEADERSHIP_REQUIREMENTS:
                blocking = False
                category = "optional"

            direct_evidence, lexical_type = self._find_direct_or_equivalent_evidence(
                requirement=requirement,
                resume_text_lower=resume_text_lower,
                evidence_units=evidence_units,
            )
            implied_evidence = []
            semantic_evidence = []
            semantic_score = 0.0
            evidence_type = lexical_type

            if not direct_evidence:
                implied_evidence = self._find_implied_evidence(
                    requirement=requirement,
                    evidence_units=evidence_units,
                    role_archetype=role_archetype,
                )
                if implied_evidence:
                    evidence_type = "implied"

            if not direct_evidence and not implied_evidence:
                semantic_evidence, semantic_score = self._find_semantic_evidence(
                    requirement=requirement,
                    evidence_units=evidence_units,
                    semantic_ctx=semantic_ctx,
                    threshold=expectations["required_semantic_threshold"] if category == "required" else expectations["optional_semantic_threshold"],
                )
                if semantic_evidence:
                    evidence_type = "semantic"

            if seniority == "entry" and requirement in _COMMUNICATION_REQUIREMENTS and not direct_evidence:
                baseline = self._find_implied_evidence(
                    requirement="communication",
                    evidence_units=evidence_units,
                    role_archetype=role_archetype,
                )
                if baseline:
                    implied_evidence = baseline
                    evidence_type = "entry-baseline"

            evidence = direct_evidence or implied_evidence or semantic_evidence
            matched = bool(evidence)
            confidence = self._confidence_for_evidence(
                evidence_type=evidence_type,
                semantic_score=semantic_score,
            )

            assessments.append(
                {
                    "requirement": requirement,
                    "category": category,
                    "blocking": blocking,
                    "matched": matched,
                    "confidence": confidence,
                    "evidence_type": evidence_type if matched else "none",
                    "evidence": evidence[:3],
                }
            )
        return assessments

    def _find_direct_or_equivalent_evidence(
        self,
        *,
        requirement: str,
        resume_text_lower: str,
        evidence_units: list[str],
    ) -> tuple[list[str], str]:
        aliases = expand_skill_aliases(requirement)
        direct_hits: list[str] = []
        equivalent_hits: list[str] = []

        for unit in evidence_units:
            unit_lower = unit.lower()
            if requirement in unit_lower:
                direct_hits.append(unit)
            elif any(alias in unit_lower for alias in aliases):
                equivalent_hits.append(unit)
            if len(direct_hits) >= 3:
                break
            if len(equivalent_hits) >= 3:
                break

        if direct_hits:
            return direct_hits[:3], "direct"
        if equivalent_hits:
            return equivalent_hits[:3], "equivalent"
        if requirement in resume_text_lower:
            return [requirement], "direct"
        return [], "none"

    def _find_implied_evidence(
        self,
        *,
        requirement: str,
        evidence_units: list[str],
        role_archetype: str,
    ) -> list[str]:
        canonical = canonicalize_skill(requirement)
        rules = list(_IMPLIED_EVIDENCE_RULES.get(canonical, []))

        if canonical in {"power bi", "tableau", "data visualization"} and role_archetype in {"data_analytics", "finance_risk"}:
            rules.extend([{"dashboard", "leadership"}, {"reporting", "kpi"}])
        if canonical == "stakeholder management" and role_archetype in {"consulting_ops", "product", "general_business"}:
            rules.extend([{"client", "recommendation"}, {"cross-functional", "alignment"}])

        matched: list[str] = []
        for unit in evidence_units:
            unit_lower = unit.lower()
            for keyword_set in rules:
                if all(keyword in unit_lower for keyword in keyword_set):
                    matched.append(unit)
                    break
                if len(keyword_set) == 1 and any(keyword in unit_lower for keyword in keyword_set):
                    matched.append(unit)
                    break
            if len(matched) >= 3:
                break
        return matched

    def _find_semantic_evidence(
        self,
        *,
        requirement: str,
        evidence_units: list[str],
        semantic_ctx: dict[str, Any],
        threshold: float,
    ) -> tuple[list[str], float]:
        model = semantic_ctx.get("model")
        unit_embeddings = semantic_ctx.get("unit_embeddings")
        if model is None or not evidence_units or len(unit_embeddings) == 0:
            return [], 0.0
        try:
            req_embedding = model.encode([requirement], normalize_embeddings=True)[0]
            scored: list[tuple[float, str]] = []
            for unit, vector in zip(evidence_units, unit_embeddings):
                score = float(sum(float(x) * float(y) for x, y in zip(req_embedding, vector)))
                scored.append((score, unit))
            scored.sort(key=lambda item: item[0], reverse=True)
            selected = [unit for score, unit in scored[:2] if score >= threshold]
            best = scored[0][0] if scored else 0.0
            return selected, best
        except Exception:
            logger.warning("Semantic evidence lookup failed", exc_info=True)
            return [], 0.0

    @staticmethod
    def _confidence_for_evidence(*, evidence_type: str, semantic_score: float) -> float:
        if evidence_type == "direct":
            return 100.0
        if evidence_type == "equivalent":
            return 90.0
        if evidence_type in {"implied", "entry-baseline"}:
            return 78.0
        if evidence_type == "semantic":
            return round(max(0.0, min(1.0, semantic_score)) * 100.0, 1)
        return 0.0

    @staticmethod
    def _score_skill_coverage(
        *,
        required_blocking: list[dict[str, Any]],
        optional_all: list[dict[str, Any]],
        tool_penalty_factor: float,
    ) -> float:
        required_total = len(required_blocking)
        optional_total = len(optional_all)

        required_ratio = (
            sum(1 for entry in required_blocking if entry["matched"]) / required_total
            if required_total
            else 1.0
        )
        optional_ratio = (
            sum(1 for entry in optional_all if entry["matched"]) / optional_total
            if optional_total
            else 0.0
        )
        required_weight = 82.0 * tool_penalty_factor
        optional_weight = 100.0 - required_weight
        raw = required_ratio * required_weight + optional_ratio * optional_weight
        return round(min(100.0, max(0.0, raw)), 1)

    def _score_responsibility_alignment(
        self,
        *,
        responsibilities: list[str],
        evidence_units: list[str],
        semantic_ctx: dict[str, Any],
        expectations: dict[str, Any],
        role_archetype: str,
    ) -> tuple[float, list[dict[str, Any]]]:
        if not responsibilities:
            return 55.0, []

        clusters = self._cluster_responsibilities(responsibilities)
        total_items = 0
        matched_items = 0
        comparison_rows: list[dict[str, Any]] = []

        for cluster_name, cluster_items in clusters.items():
            cluster_matched = 0
            for item in cluster_items:
                total_items += 1
                direct, _ = self._find_direct_or_equivalent_evidence(
                    requirement=item.lower(),
                    resume_text_lower=" ".join(unit.lower() for unit in evidence_units),
                    evidence_units=evidence_units,
                )
                implied = self._find_implied_evidence(
                    requirement=item,
                    evidence_units=evidence_units,
                    role_archetype=role_archetype,
                )
                semantic, semantic_score = self._find_semantic_evidence(
                    requirement=item,
                    evidence_units=evidence_units,
                    semantic_ctx=semantic_ctx,
                    threshold=max(0.36, expectations["required_semantic_threshold"] - 0.04),
                )
                if direct or implied or semantic or semantic_score >= max(0.36, expectations["required_semantic_threshold"] - 0.04):
                    cluster_matched += 1
                    matched_items += 1

            coverage = (cluster_matched / len(cluster_items) * 100.0) if cluster_items else 0.0
            comparison_rows.append(
                {
                    "cluster": cluster_name.replace("_", " ").title(),
                    "jd_items": len(cluster_items),
                    "matched_items": cluster_matched,
                    "coverage_score": round(coverage, 1),
                }
            )

        score = round((matched_items / total_items) * 100.0, 1) if total_items else 0.0
        return min(100.0, max(0.0, score)), comparison_rows

    @staticmethod
    def _cluster_responsibilities(responsibilities: list[str]) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {
            "delivery_execution": [],
            "analysis_reporting": [],
            "stakeholder_collaboration": [],
            "leadership_ownership": [],
        }
        for item in responsibilities:
            text = item.lower()
            if any(keyword in text for keyword in ("analy", "insight", "report", "forecast", "model")):
                clusters["analysis_reporting"].append(item)
            elif any(keyword in text for keyword in ("stakeholder", "cross-functional", "partner", "client")):
                clusters["stakeholder_collaboration"].append(item)
            elif any(keyword in text for keyword in ("lead", "mentor", "manage", "own", "drive")):
                clusters["leadership_ownership"].append(item)
            else:
                clusters["delivery_execution"].append(item)
        return {key: value for key, value in clusters.items() if value}

    @staticmethod
    def _score_domain_familiarity(
        *,
        profile: JobProfileData,
        resume_text_lower: str,
        role_archetype: str,
    ) -> tuple[float, list[str], list[str]]:
        role_text = f"{profile.title} {profile.normalized_title} {' '.join(profile.required_skills)} {' '.join(profile.responsibilities)}".lower()
        expected: set[str] = set()
        for domain_terms in DOMAIN_KEYWORDS.values():
            for term in domain_terms:
                if term in role_text:
                    expected.add(term)
        expected.update(_ROLE_ARCHETYPE_PROFILES[role_archetype]["evidence_keywords"])

        if not expected:
            return 60.0, [], []

        hits = sorted(term for term in expected if term in resume_text_lower)
        missing = sorted(expected - set(hits))
        ratio = len(hits) / len(expected)
        return round(min(100.0, ratio * 100.0), 1), hits, missing

    @staticmethod
    def _score_experience(
        *,
        detected_years: float,
        exp_min: int | None,
        exp_max: int | None,
        seniority: str,
    ) -> float:
        if exp_min is None and exp_max is None:
            return 70.0 if seniority == "entry" else 55.0

        lo = exp_min or 0
        hi = exp_max or (lo + (2 if seniority == "entry" else 5))

        if lo <= detected_years <= hi:
            return 100.0
        if detected_years < lo:
            penalty_per_year = 9.0 if seniority == "entry" else 14.0
            return max(0.0, round(100.0 - (lo - detected_years) * penalty_per_year, 1))
        return max(0.0, round(100.0 - (detected_years - hi) * 8.0, 1))

    @staticmethod
    def _score_seniority_fit(detected_years: float, target_seniority: str) -> float:
        band = _SENIORITY_BANDS.get(target_seniority, (2, 5))
        lo, hi = band
        if lo <= detected_years <= hi:
            return 100.0
        if detected_years < lo:
            return max(0.0, round(100.0 - (lo - detected_years) * 18.0, 1))
        return max(0.0, round(100.0 - (detected_years - hi) * 9.0, 1))

    @staticmethod
    def _score_quality(text: str, role_archetype: str) -> float:
        text_lower = text.lower()
        word_count = len(text.split())
        section_count = sum(1 for keywords in _SECTION_PATTERNS.values() if any(keyword in text_lower for keyword in keywords))

        contact = 0.0
        if _EMAIL_PATTERN.search(text):
            contact += 10.0
        if _PHONE_PATTERN.search(text):
            contact += 10.0

        section_score = min(50.0, section_count * 10.0)
        if word_count >= 320:
            length_score = 30.0
        elif word_count >= 160:
            length_score = 15.0 + (word_count - 160) * (15.0 / 160.0)
        elif word_count >= 80:
            length_score = (word_count - 80) * (15.0 / 80.0)
        else:
            length_score = 0.0

        impact_bonus = 10.0 if _IMPACT_PATTERN.search(text) else 0.0
        if role_archetype in {"finance_risk", "data_analytics"} and "kpi" in text_lower:
            impact_bonus += 3.0
        return round(min(100.0, section_score + contact + length_score + impact_bonus), 1)

    @staticmethod
    def _build_missing_evidence(
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
    ) -> list[str]:
        lines: list[str] = []
        for entry in missing_required[:4]:
            lines.append(f"No resume evidence supports “{entry['requirement']}”.")
        for entry in weak_evidence[:3]:
            lines.append(f"Evidence for “{entry['requirement']}” is present but not quantified.")
        return lines[:6]

    def _build_rewrite_suggestions(
        self,
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
        evidence_units: list[str],
        role_title: str,
        role_archetype: str,
    ) -> list[dict[str, str]]:
        suggestions: list[dict[str, str]] = []
        for entry in missing_required[:3]:
            requirement = entry["requirement"]
            grounding = self._pick_grounding_bullet(requirement, evidence_units, role_archetype)
            suggestions.append(
                {
                    "requirement": requirement,
                    "issue": "Missing explicit JD-aligned evidence",
                    "recommendation": (
                        f"Reframe an existing bullet to explicitly demonstrate {requirement} "
                        f"using this resume evidence: “{grounding}”."
                    ),
                    "example_bullet": (
                        f"Using {requirement}, delivered [project/process] for [stakeholder/team], "
                        f"improving [metric] by [X%] over [timeframe]."
                    ),
                }
            )
        for entry in weak_evidence[:2]:
            requirement = entry["requirement"]
            grounding = entry["evidence"][0] if entry["evidence"] else self._pick_grounding_bullet(requirement, evidence_units, role_archetype)
            suggestions.append(
                {
                    "requirement": requirement,
                    "issue": "Evidence exists but impact is not explicit",
                    "recommendation": (
                        f"Reframe this existing bullet for {role_title}: “{grounding}” "
                        "to include measurable scope and outcome."
                    ),
                    "example_bullet": (
                        f"{grounding} Result: [business outcome] improved by [X%] "
                        f"across [scope], tracked over [timeframe]."
                    ),
                }
            )
        return suggestions[:6]

    def _pick_grounding_bullet(self, requirement: str, evidence_units: list[str], role_archetype: str) -> str:
        requirement_aliases = expand_skill_aliases(requirement)
        archetype_terms = _ROLE_ARCHETYPE_PROFILES[role_archetype]["evidence_keywords"]

        scored: list[tuple[int, str]] = []
        for unit in evidence_units:
            unit_lower = unit.lower()
            score = 0
            if requirement in unit_lower:
                score += 4
            if any(alias in unit_lower for alias in requirement_aliases):
                score += 3
            if any(term in unit_lower for term in archetype_terms):
                score += 2
            if _IMPACT_PATTERN.search(unit):
                score += 2
            if score > 0:
                scored.append((score, unit))

        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            return scored[0][1]
        return "Existing project/experience bullet from your resume"

    def _build_ats_keyword_map(
        self,
        *,
        profile: JobProfileData,
        assessments: list[dict[str, Any]],
        resume_text_lower: str,
        evidence_units: list[str],
        role_archetype: str,
    ) -> list[dict[str, Any]]:
        assessed = {entry["requirement"]: entry for entry in assessments}
        keywords: list[str] = []
        keywords.extend(canonicalize_skill(skill) for skill in profile.required_skills)
        keywords.extend(canonicalize_skill(skill) for skill in profile.optional_skills[:10])
        keywords.extend(_ROLE_ARCHETYPE_PROFILES[role_archetype]["evidence_keywords"])

        unique: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            normalized = normalize_term(keyword)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)

        rows: list[dict[str, Any]] = []
        for keyword in unique[:24]:
            assessment = assessed.get(keyword)
            if assessment is not None:
                matched = assessment["matched"]
                evidence = assessment["evidence"][:1]
            else:
                evidence, _ = self._find_direct_or_equivalent_evidence(
                    requirement=keyword,
                    resume_text_lower=resume_text_lower,
                    evidence_units=evidence_units,
                )
                matched = bool(evidence)
                evidence = evidence[:1]

            rows.append(
                {
                    "keyword": keyword,
                    "status": "matched" if matched else "missing",
                    "location_hint": self._infer_keyword_location(keyword, resume_text_lower),
                    "evidence": evidence,
                }
            )
        return rows

    @staticmethod
    def _infer_keyword_location(keyword: str, resume_text_lower: str) -> str:
        idx = resume_text_lower.find(keyword)
        if idx < 0:
            return "not found"
        if idx < 450:
            return "summary"
        window = resume_text_lower[max(0, idx - 220): idx + 220]
        if "experience" in window or "employment" in window:
            return "experience"
        if "projects" in window:
            return "projects"
        if "skills" in window:
            return "skills"
        return "resume body"

    @staticmethod
    def _build_strengths(
        *,
        matched_required: list[dict[str, Any]],
        matched_optional: list[dict[str, Any]],
        domain_hits: list[str],
        experience_years: float,
        role_alignment_score: float,
        role_archetype: str,
    ) -> list[str]:
        strengths: list[str] = []
        if matched_required:
            strengths.append(
                f"Strong JD alignment evidence for: {', '.join(entry['requirement'] for entry in matched_required[:4])}."
            )
        if matched_optional:
            strengths.append(
                f"Additional optional fit shown for: {', '.join(entry['requirement'] for entry in matched_optional[:3])}."
            )
        if domain_hits:
            strengths.append(f"Domain familiarity signals detected: {', '.join(domain_hits[:4])}.")
        if experience_years > 0:
            strengths.append(f"Estimated experience depth is {experience_years:.1f} years.")
        if role_alignment_score >= 70:
            strengths.append("Responsibilities are well represented in current resume bullets.")
        if role_archetype == "consulting_ops" and any("stakeholder" in item["requirement"] for item in matched_required):
            strengths.append("Stakeholder-facing delivery evidence is visible.")
        return strengths[:6]

    @staticmethod
    def _build_gaps(
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
        domain_missing: list[str],
        experience_years: float,
        profile: JobProfileData,
        seniority: str,
    ) -> list[str]:
        gaps: list[str] = []
        if missing_required:
            gaps.append(
                f"Missing proof for required capabilities: {', '.join(entry['requirement'] for entry in missing_required[:4])}."
            )
        if weak_evidence:
            gaps.append(
                f"Evidence exists but is weakly framed for: {', '.join(entry['requirement'] for entry in weak_evidence[:3])}."
            )
        if domain_missing:
            gaps.append(f"Domain terminology underrepresented: {', '.join(domain_missing[:4])}.")
        if (
            seniority != "entry"
            and profile.years_experience_min is not None
            and experience_years < profile.years_experience_min
        ):
            gaps.append(
                f"Experience appears below target ({experience_years:.1f} yrs vs {profile.years_experience_min}+ yrs)."
            )
        return gaps[:6]

    @staticmethod
    def _build_rejection_risks(
        *,
        missing_required: list[dict[str, Any]],
        role_alignment_score: float,
        weak_evidence: list[dict[str, Any]],
        seniority: str,
    ) -> list[str]:
        risks: list[str] = []
        if missing_required:
            risks.append(
                f"Hard requirements without evidence: {', '.join(entry['requirement'] for entry in missing_required[:3])}."
            )
        if role_alignment_score < 60:
            risks.append("Resume bullets do not map clearly to JD responsibilities.")
        if weak_evidence and seniority != "entry":
            risks.append("Some matched skills are unconvincing due to missing measurable outcomes.")
        return risks[:4]

    @staticmethod
    def _build_fastest_fixes(
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
        domain_missing: list[str],
        seniority: str,
    ) -> list[str]:
        fixes: list[str] = []
        for entry in missing_required[:3]:
            fixes.append(
                f"Add one bullet with context + action + measurable outcome proving {entry['requirement']}."
            )
        for entry in weak_evidence[:2]:
            fixes.append(
                f"Strengthen {entry['requirement']} bullets with concrete impact metrics and timeframe."
            )
        if domain_missing:
            fixes.append(
                f"Use role-specific terminology in existing bullets ({', '.join(domain_missing[:3])})."
            )
        if seniority == "entry":
            fixes.append("Prioritize clear project evidence and learning outcomes over leadership claims.")
        if not fixes:
            fixes.append("Increase precision by linking each key JD requirement to one quantified resume bullet.")
        return fixes[:6]

    @staticmethod
    def _build_explanation_summary(
        *,
        overall: float,
        profile_title: str,
        matched_required: int,
        total_required: int,
        missing_required: list[dict[str, Any]],
        role_alignment_score: float,
    ) -> str:
        summary = (
            f"{overall}% match for {profile_title}. "
            f"Evidence supports {matched_required}/{max(total_required, 1)} required capabilities."
        )
        if missing_required:
            summary += (
                f" Highest-priority gap: {missing_required[0]['requirement']} lacks clear proof."
            )
        else:
            summary += " No blocking requirement gaps were detected."
        if role_alignment_score < 60:
            summary += " Responsibility coverage is currently uneven."
        else:
            summary += " Responsibility coverage is credible."
        if overall < 50:
            summary += (
                " This is not a rejection of your ability — it’s a mismatch in evidence framing."
            )
        return summary

    @staticmethod
    def _build_recruiter_verdict(
        *,
        overall: float,
        role_archetype: str,
        strengths: list[str],
        rejection_risks: list[str],
    ) -> str:
        if overall >= 82:
            tier = "Strong shortlist signal"
        elif overall >= 68:
            tier = "Possible shortlist with targeted edits"
        elif overall >= 50:
            tier = "Borderline fit; evidence framing needs improvement"
        else:
            tier = "Low-confidence match today"

        strength_line = strengths[0] if strengths else "Limited role-relevant signals identified."
        risk_line = rejection_risks[0] if rejection_risks else "No immediate rejection trigger identified."
        return f"{tier} ({role_archetype.replace('_', ' ')}). {strength_line} {risk_line}"

    def _apply_reasoner_enrichment(
        self,
        *,
        profile: JobProfileData,
        result: JobMatchResult,
        matched_required: list[dict[str, Any]],
        missing_required: list[dict[str, Any]],
    ) -> None:
        reasoned = self.reasoner.generate(
            {
                "role_title": profile.title,
                "overall_match_score": result.overall_match_score,
                "strengths": result.strengths[:4],
                "gaps": result.gaps[:4],
                "matched_required": [
                    {"requirement": entry["requirement"], "evidence": entry["evidence"][:2]}
                    for entry in matched_required[:6]
                ],
                "missing_required": [entry["requirement"] for entry in missing_required[:6]],
                "existing_rewrite_suggestions": result.rewrite_suggestions[:5],
            }
        )
        if not reasoned:
            return

        known_requirements = {entry["requirement"] for entry in matched_required + missing_required}

        recruiter_verdict = reasoned.get("recruiter_verdict")
        if isinstance(recruiter_verdict, str) and recruiter_verdict.strip():
            result.recruiter_verdict = recruiter_verdict.strip()

        explanation_summary = reasoned.get("explanation_summary")
        if isinstance(explanation_summary, str) and explanation_summary.strip():
            result.explanation_summary = explanation_summary.strip()

        rewrite_suggestions = reasoned.get("rewrite_suggestions")
        if isinstance(rewrite_suggestions, list):
            normalized: list[dict[str, str]] = []
            for entry in rewrite_suggestions:
                if not isinstance(entry, dict):
                    continue
                requirement = str(entry.get("requirement", "")).strip().lower()
                if requirement and requirement not in known_requirements:
                    continue
                example_bullet = str(entry.get("example_bullet", "")).strip()
                if not example_bullet:
                    continue
                normalized.append(
                    {
                        "requirement": requirement or "resume framing",
                        "issue": str(entry.get("issue", "Needs stronger evidence framing")).strip(),
                        "recommendation": str(entry.get("recommendation", "Reframe with clear evidence and measurable outcome.")).strip(),
                        "example_bullet": example_bullet,
                    }
                )
            if normalized:
                result.rewrite_suggestions = normalized[:6]
