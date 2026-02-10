"""Job-targeted resume scoring engine.

Synchronous scorer used by the RQ worker. Produces explainable,
evidence-backed matching outputs for Resume × JobProfile.
"""

from __future__ import annotations

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
    "intern": (0, 1),
    "junior": (0, 2),
    "mid": (2, 5),
    "senior": (5, 10),
    "lead": (7, 15),
    "principal": (10, 20),
    "staff": (10, 25),
}

_YEAR_RANGE_PATTERN = re.compile(
    r"(\b(?:19|20)\d{2})\s*[-–—to]+\s*((?:19|20)\d{2}|present|current|now)",
    re.IGNORECASE,
)

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_IMPACT_PATTERN = re.compile(r"(\d+[%x]|[$€£]\s?\d+|\d+\s?(k|m|b)|\d+\+?)", re.IGNORECASE)

_SECTION_PATTERNS: dict[str, list[str]] = {
    "summary": ["summary", "objective", "profile"],
    "experience": ["experience", "employment", "work history"],
    "projects": ["projects", "portfolio"],
    "skills": ["skills", "technical skills", "core competencies"],
    "education": ["education", "degree", "university"],
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
                "sentence-transformers not available — semantic matching will use lexical fallback",
                exc_info=True,
            )
    return _st_model


class JobTargetedScorer:
    """Synchronous Resume × JobProfile scorer for RQ worker context."""

    def __init__(self) -> None:
        self.reasoner = LocalReasoner()

    def score(self, resume_text: str, profile: JobProfileData) -> JobMatchResult:
        result = JobMatchResult()

        resume_text_lower = resume_text.lower()
        evidence_units = self._extract_evidence_units(resume_text)
        resume_skills = self._extract_resume_skills(resume_text)
        experience_years = self._estimate_experience_years(resume_text)
        role_family = self._infer_role_family(profile)
        weights = self._weight_map_for_role(role_family)

        semantic_ctx = self._build_semantic_context(evidence_units)
        requirement_assessments = self._assess_requirements(
            profile=profile,
            resume_text_lower=resume_text_lower,
            evidence_units=evidence_units,
            semantic_ctx=semantic_ctx,
        )

        required_assessments = [entry for entry in requirement_assessments if entry["category"] == "required"]
        optional_assessments = [entry for entry in requirement_assessments if entry["category"] == "optional"]

        result.skill_match_score = self._score_skill_coverage(required_assessments, optional_assessments)
        result.experience_match_score = self._score_experience(
            experience_years, profile.years_experience_min, profile.years_experience_max
        )
        responsibility_score, responsibility_comparison = self._score_responsibility_alignment(
            responsibilities=profile.responsibilities,
            evidence_units=evidence_units,
            semantic_ctx=semantic_ctx,
        )
        result.role_alignment_score = responsibility_score
        result.seniority_fit_score = self._score_seniority_fit(experience_years, profile.seniority_level)
        result.quality_score = self._score_quality(resume_text)
        domain_score, domain_hits, domain_missing = self._score_domain_familiarity(
            profile=profile,
            resume_text_lower=resume_text_lower,
        )

        result.dimension_scores = [
            {
                "key": "skills_tools",
                "label": "Skills & Tools",
                "score": result.skill_match_score,
                "weight": round(weights["skills_tools"] * 100, 1),
            },
            {
                "key": "responsibility_alignment",
                "label": "Responsibility Alignment",
                "score": result.role_alignment_score,
                "weight": round(weights["responsibility_alignment"] * 100, 1),
            },
            {
                "key": "domain_familiarity",
                "label": "Domain Familiarity",
                "score": domain_score,
                "weight": round(weights["domain_familiarity"] * 100, 1),
            },
            {
                "key": "seniority_fit",
                "label": "Seniority Fit",
                "score": result.seniority_fit_score,
                "weight": round(weights["seniority_fit"] * 100, 1),
            },
            {
                "key": "experience_sufficiency",
                "label": "Experience Sufficiency",
                "score": result.experience_match_score,
                "weight": round(weights["experience_sufficiency"] * 100, 1),
            },
            {
                "key": "resume_quality",
                "label": "Resume Quality",
                "score": result.quality_score,
                "weight": round(weights["resume_quality"] * 100, 1),
            },
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

        matched_required = [
            entry for entry in required_assessments if entry["matched"]
        ]
        missing_required = [
            entry for entry in required_assessments if not entry["matched"]
        ]
        matched_optional = [
            entry for entry in optional_assessments if entry["matched"]
        ]
        weak_evidence = [
            entry
            for entry in matched_required
            if entry["evidence"] and not any(_IMPACT_PATTERN.search(snippet) for snippet in entry["evidence"])
        ]

        result.matched_requirements = matched_required
        result.missing_requirements = missing_required
        result.resume_vs_jd_comparison = responsibility_comparison
        result.missing_evidence = [
            f"No quantified evidence for {entry['requirement']}."
            for entry in weak_evidence[:5]
        ]
        result.rewrite_suggestions = self._build_rewrite_suggestions(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
            role_title=profile.title,
        )
        result.ats_keyword_map = self._build_ats_keyword_map(
            profile=profile,
            requirement_assessments=requirement_assessments,
            resume_text_lower=resume_text_lower,
            evidence_units=evidence_units,
        )

        result.strengths = self._build_strengths(
            matched_required=matched_required,
            matched_optional=matched_optional,
            experience_years=experience_years,
            role_alignment=result.role_alignment_score,
            domain_hits=domain_hits,
        )
        result.gaps = self._build_gaps(
            missing_required=missing_required,
            profile=profile,
            experience_years=experience_years,
            domain_missing=domain_missing,
        )
        result.rejection_risks = self._build_rejection_risks(
            missing_required=missing_required,
            role_alignment_score=result.role_alignment_score,
            weak_evidence=weak_evidence,
        )
        result.fastest_fixes = self._build_fastest_fixes(
            missing_required=missing_required,
            weak_evidence=weak_evidence,
            domain_missing=domain_missing,
        )

        result.explanation_summary = self._build_explanation_summary(
            profile=profile,
            overall=result.overall_match_score,
            matched_required=len(matched_required),
            total_required=len(required_assessments),
            role_alignment_score=result.role_alignment_score,
            missing_required=missing_required,
        )
        result.recruiter_verdict = self._build_recruiter_verdict(
            overall=result.overall_match_score,
            strengths=result.strengths,
            rejection_risks=result.rejection_risks,
        )

        self._apply_reasoner_enrichment(
            profile=profile,
            result=result,
            matched_required=matched_required,
            missing_required=missing_required,
        )

        required_set = {entry["requirement"].lower() for entry in required_assessments}
        optional_set = {entry["requirement"].lower() for entry in optional_assessments}
        resume_set = {skill.lower() for skill in resume_skills}
        evidence_map = {
            entry["requirement"]: entry["evidence"] for entry in requirement_assessments
        }

        result.details = {
            "resume_skills": resume_skills,
            "matched_required": sorted(entry["requirement"] for entry in matched_required),
            "matched_optional": sorted(entry["requirement"] for entry in matched_optional),
            "missing_required": sorted(entry["requirement"] for entry in missing_required),
            "extra_resume_skills": sorted(resume_set - required_set - optional_set),
            "experience_years_detected": experience_years,
            "cosine_similarity": round(result.role_alignment_score / 100.0, 4),
            "role_family": role_family,
            "weights": weights,
            "domain_hits": domain_hits,
            "domain_missing": domain_missing,
            "evidence_map": evidence_map,
        }

        return result

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
                    {
                        "requirement": entry["requirement"],
                        "evidence": entry["evidence"][:2],
                    }
                    for entry in matched_required[:6]
                ],
                "missing_required": [
                    entry["requirement"] for entry in missing_required[:6]
                ],
                "existing_rewrite_suggestions": result.rewrite_suggestions[:5],
            }
        )
        if not reasoned:
            return

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
                requirement = str(entry.get("requirement", "")).strip()
                issue = str(entry.get("issue", "")).strip()
                recommendation = str(entry.get("recommendation", "")).strip()
                example_bullet = str(entry.get("example_bullet", "")).strip()
                if not requirement or not example_bullet:
                    continue
                normalized.append(
                    {
                        "requirement": requirement,
                        "issue": issue or "Needs stronger evidence",
                        "recommendation": recommendation or "Rewrite with measurable impact.",
                        "example_bullet": example_bullet,
                    }
                )
            if normalized:
                result.rewrite_suggestions = normalized[:5]

    @staticmethod
    def _extract_resume_skills(text: str) -> list[str]:
        text_lower = text.lower()
        tokens = {token.lower() for token in re.findall(r"[a-zA-Z0-9.+#/-]+", text)}
        found: set[str] = set()

        for skill in KNOWN_SKILLS:
            aliases = expand_skill_aliases(skill)
            if any(alias in tokens for alias in aliases if " " not in alias):
                found.add(canonicalize_skill(skill))
                continue
            if any(alias in text_lower for alias in aliases if " " in alias):
                found.add(canonicalize_skill(skill))

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
    def _extract_evidence_units(text: str) -> list[str]:
        chunks = re.split(r"[\n\r]+|(?<=[.!?])\s+", text)
        units: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            cleaned = re.sub(r"\s+", " ", chunk).strip(" -•\t")
            if len(cleaned) < 25:
                continue
            normalized = cleaned.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            units.append(cleaned)
        return units[:120]

    @staticmethod
    def _infer_role_family(profile: JobProfileData) -> str:
        role_text = f"{profile.title} {profile.normalized_title}".lower()
        if any(term in role_text for term in ("frontend", "backend", "engineer", "developer", "ml", "devops")):
            return "engineering"
        if any(term in role_text for term in ("finance", "financial", "risk", "accounting")):
            return "finance"
        if "consult" in role_text:
            return "consulting"
        if any(term in role_text for term in ("operations", "business analyst")):
            return "operations"
        if "analyst" in role_text:
            return "analytics"
        return "general"

    @staticmethod
    def _weight_map_for_role(role_family: str) -> dict[str, float]:
        if role_family == "engineering":
            return {
                "skills_tools": 0.34,
                "responsibility_alignment": 0.26,
                "domain_familiarity": 0.08,
                "seniority_fit": 0.10,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.08,
            }
        if role_family == "finance":
            return {
                "skills_tools": 0.22,
                "responsibility_alignment": 0.30,
                "domain_familiarity": 0.16,
                "seniority_fit": 0.08,
                "experience_sufficiency": 0.16,
                "resume_quality": 0.08,
            }
        if role_family == "consulting":
            return {
                "skills_tools": 0.16,
                "responsibility_alignment": 0.32,
                "domain_familiarity": 0.18,
                "seniority_fit": 0.10,
                "experience_sufficiency": 0.14,
                "resume_quality": 0.10,
            }
        if role_family in {"operations", "analytics"}:
            return {
                "skills_tools": 0.24,
                "responsibility_alignment": 0.30,
                "domain_familiarity": 0.14,
                "seniority_fit": 0.08,
                "experience_sufficiency": 0.16,
                "resume_quality": 0.08,
            }
        return {
            "skills_tools": 0.28,
            "responsibility_alignment": 0.28,
            "domain_familiarity": 0.12,
            "seniority_fit": 0.10,
            "experience_sufficiency": 0.14,
            "resume_quality": 0.08,
        }

    def _build_semantic_context(self, evidence_units: list[str]) -> dict[str, Any]:
        model = _get_sentence_model()
        if model is None or not evidence_units:
            return {"model": None, "unit_embeddings": []}
        try:
            embeddings = model.encode(evidence_units, normalize_embeddings=True)
            return {"model": model, "unit_embeddings": embeddings}
        except Exception:
            logger.warning("Failed to encode evidence units for semantic matching", exc_info=True)
            return {"model": None, "unit_embeddings": []}

    def _assess_requirements(
        self,
        *,
        profile: JobProfileData,
        resume_text_lower: str,
        evidence_units: list[str],
        semantic_ctx: dict[str, Any],
    ) -> list[dict[str, Any]]:
        assessments: list[dict[str, Any]] = []
        combined = [("required", item) for item in profile.required_skills] + [
            ("optional", item) for item in profile.optional_skills
        ]

        for category, raw_requirement in combined:
            requirement = canonicalize_skill(raw_requirement)
            lexical_evidence = self._find_lexical_evidence(
                requirement=requirement,
                resume_text_lower=resume_text_lower,
                evidence_units=evidence_units,
            )
            semantic_evidence: list[str] = []
            semantic_score = 0.0

            if not lexical_evidence:
                semantic_evidence, semantic_score = self._find_semantic_evidence(
                    requirement=requirement,
                    evidence_units=evidence_units,
                    semantic_ctx=semantic_ctx,
                    threshold=0.46 if category == "required" else 0.50,
                )

            evidence = lexical_evidence or semantic_evidence
            confidence = (
                100.0
                if lexical_evidence
                else round(max(0.0, semantic_score) * 100, 1)
            )
            assessments.append(
                {
                    "requirement": requirement,
                    "category": category,
                    "matched": bool(evidence),
                    "confidence": confidence,
                    "evidence": evidence[:3],
                }
            )

        return assessments

    def _find_lexical_evidence(
        self,
        *,
        requirement: str,
        resume_text_lower: str,
        evidence_units: list[str],
    ) -> list[str]:
        aliases = expand_skill_aliases(requirement)
        normalized_units = [(unit, unit.lower()) for unit in evidence_units]
        found: list[str] = []

        for unit, unit_lower in normalized_units:
            if any(alias in unit_lower for alias in aliases):
                found.append(unit)
                if len(found) >= 3:
                    break

        if found:
            return found

        if requirement in resume_text_lower:
            return [requirement]
        return []

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
        if model is None or len(evidence_units) == 0 or len(unit_embeddings) == 0:
            return [], 0.0

        try:
            requirement_embedding = model.encode([requirement], normalize_embeddings=True)[0]
            scored: list[tuple[float, str]] = []
            for unit, vector in zip(evidence_units, unit_embeddings):
                score = float(sum(float(x) * float(y) for x, y in zip(requirement_embedding, vector)))
                scored.append((score, unit))

            scored.sort(key=lambda item: item[0], reverse=True)
            selected = [unit for score, unit in scored[:2] if score >= threshold]
            best = scored[0][0] if scored else 0.0
            return selected, best
        except Exception:
            logger.warning("Semantic requirement matching failed", exc_info=True)
            return [], 0.0

    @staticmethod
    def _score_skill_coverage(
        required_assessments: list[dict[str, Any]],
        optional_assessments: list[dict[str, Any]],
    ) -> float:
        required_total = len(required_assessments)
        optional_total = len(optional_assessments)

        required_ratio = (
            sum(1 for entry in required_assessments if entry["matched"]) / required_total
            if required_total
            else 1.0
        )
        optional_ratio = (
            sum(1 for entry in optional_assessments if entry["matched"]) / optional_total
            if optional_total
            else 0.0
        )
        raw = required_ratio * 82.0 + optional_ratio * 18.0
        return round(min(100.0, max(0.0, raw)), 1)

    def _score_responsibility_alignment(
        self,
        *,
        responsibilities: list[str],
        evidence_units: list[str],
        semantic_ctx: dict[str, Any],
    ) -> tuple[float, list[dict[str, Any]]]:
        if not responsibilities:
            return 55.0, []

        matched = 0
        comparison_rows: list[dict[str, Any]] = []
        clusters = self._cluster_responsibilities(responsibilities)

        for cluster_name, cluster_items in clusters.items():
            cluster_matched = 0
            for item in cluster_items:
                lexical = self._find_lexical_evidence(
                    requirement=item.lower(),
                    resume_text_lower=" ".join(unit.lower() for unit in evidence_units),
                    evidence_units=evidence_units,
                )
                semantic, best = self._find_semantic_evidence(
                    requirement=item,
                    evidence_units=evidence_units,
                    semantic_ctx=semantic_ctx,
                    threshold=0.38,
                )
                if lexical or semantic or best >= 0.38:
                    cluster_matched += 1
                    matched += 1

            coverage = (cluster_matched / len(cluster_items)) * 100 if cluster_items else 0.0
            comparison_rows.append(
                {
                    "cluster": cluster_name.replace("_", " ").title(),
                    "jd_items": len(cluster_items),
                    "matched_items": cluster_matched,
                    "coverage_score": round(coverage, 1),
                }
            )

        total = len(responsibilities)
        coverage_ratio = matched / total if total else 0.0
        score = round(min(100.0, coverage_ratio * 100.0), 1)
        return score, comparison_rows

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
            elif any(keyword in text for keyword in ("lead", "own", "drive", "mentor", "manage")):
                clusters["leadership_ownership"].append(item)
            else:
                clusters["delivery_execution"].append(item)

        return {key: value for key, value in clusters.items() if value}

    @staticmethod
    def _score_domain_familiarity(
        *,
        profile: JobProfileData,
        resume_text_lower: str,
    ) -> tuple[float, list[str], list[str]]:
        role_text = f"{profile.title} {profile.normalized_title} {' '.join(profile.required_skills)} {' '.join(profile.responsibilities)}".lower()
        expected: set[str] = set()
        for terms in DOMAIN_KEYWORDS.values():
            for term in terms:
                if term in role_text:
                    expected.add(term)

        if not expected:
            return 60.0, [], []

        hits = sorted(term for term in expected if term in resume_text_lower)
        missing = sorted(expected - set(hits))
        ratio = len(hits) / len(expected)
        return round(min(100.0, ratio * 100), 1), hits, missing

    @staticmethod
    def _score_experience(
        detected_years: float,
        exp_min: int | None,
        exp_max: int | None,
    ) -> float:
        if exp_min is None and exp_max is None:
            return 55.0

        lo = exp_min or 0
        hi = exp_max or (lo + 5)

        if lo <= detected_years <= hi:
            return 100.0

        if detected_years < lo:
            deficit = lo - detected_years
            return max(0.0, round(100.0 - deficit * 14.0, 1))

        surplus = detected_years - hi
        return max(0.0, round(100.0 - surplus * 8.0, 1))

    @staticmethod
    def _score_seniority_fit(detected_years: float, target_seniority: str) -> float:
        band = _SENIORITY_BANDS.get(target_seniority.lower(), (2, 5))
        lo, hi = band
        if lo <= detected_years <= hi:
            return 100.0
        if detected_years < lo:
            return max(0.0, round(100.0 - (lo - detected_years) * 20.0, 1))
        return max(0.0, round(100.0 - (detected_years - hi) * 10.0, 1))

    @staticmethod
    def _score_quality(text: str) -> float:
        text_lower = text.lower()
        word_count = len(text.split())
        section_count = 0
        for keywords in _SECTION_PATTERNS.values():
            if any(keyword in text_lower for keyword in keywords):
                section_count += 1

        contact = 0.0
        if _EMAIL_PATTERN.search(text):
            contact += 10.0
        if _PHONE_PATTERN.search(text):
            contact += 10.0

        section_score = min(50.0, section_count * 10.0)
        length_score = 0.0
        if word_count >= 350:
            length_score = 30.0
        elif word_count >= 160:
            length_score = 15.0 + (word_count - 160) * (15.0 / 190.0)
        elif word_count >= 80:
            length_score = (word_count - 80) * (15.0 / 80.0)

        return round(min(100.0, section_score + contact + length_score), 1)

    @staticmethod
    def _build_strengths(
        *,
        matched_required: list[dict[str, Any]],
        matched_optional: list[dict[str, Any]],
        experience_years: float,
        role_alignment: float,
        domain_hits: list[str],
    ) -> list[str]:
        strengths: list[str] = []
        if matched_required:
            top = ", ".join(entry["requirement"] for entry in matched_required[:4])
            strengths.append(f"Evidence found for required capabilities: {top}.")
        if matched_optional:
            optional = ", ".join(entry["requirement"] for entry in matched_optional[:3])
            strengths.append(f"Additional alignment on preferred skills: {optional}.")
        if experience_years > 0:
            strengths.append(f"Estimated experience depth: {experience_years:.1f} years.")
        if role_alignment >= 70:
            strengths.append("Responsibility alignment is strong across core JD themes.")
        if domain_hits:
            strengths.append(f"Domain language overlap detected: {', '.join(domain_hits[:4])}.")
        return strengths[:5]

    @staticmethod
    def _build_gaps(
        *,
        missing_required: list[dict[str, Any]],
        profile: JobProfileData,
        experience_years: float,
        domain_missing: list[str],
    ) -> list[str]:
        gaps: list[str] = []
        if missing_required:
            missing_names = ", ".join(entry["requirement"] for entry in missing_required[:4])
            gaps.append(f"Missing required evidence for: {missing_names}.")
        if profile.years_experience_min and experience_years < profile.years_experience_min:
            gaps.append(
                f"Experience appears below target ({experience_years:.1f} yrs vs {profile.years_experience_min}+ yrs)."
            )
        if domain_missing:
            gaps.append(f"Domain keywords not evidenced: {', '.join(domain_missing[:4])}.")
        return gaps[:5]

    @staticmethod
    def _build_rejection_risks(
        *,
        missing_required: list[dict[str, Any]],
        role_alignment_score: float,
        weak_evidence: list[dict[str, Any]],
    ) -> list[str]:
        risks: list[str] = []
        if missing_required:
            risks.append(
                f"Core requirements lack direct evidence ({', '.join(entry['requirement'] for entry in missing_required[:3])})."
            )
        if role_alignment_score < 60:
            risks.append("Resume bullets do not consistently map to the job's core responsibilities.")
        if weak_evidence:
            risks.append("Matched skills are present but impact metrics are often missing.")
        return risks[:4]

    @staticmethod
    def _build_fastest_fixes(
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
        domain_missing: list[str],
    ) -> list[str]:
        fixes: list[str] = []
        for entry in missing_required[:3]:
            fixes.append(
                f"Add one bullet proving {entry['requirement']} with a measurable outcome."
            )
        for entry in weak_evidence[:2]:
            fixes.append(
                f"Rewrite {entry['requirement']} evidence to include scope, metric, and result."
            )
        if domain_missing:
            fixes.append(
                f"Use domain terminology naturally in experience bullets ({', '.join(domain_missing[:3])})."
            )
        return fixes[:5]

    @staticmethod
    def _build_rewrite_suggestions(
        *,
        missing_required: list[dict[str, Any]],
        weak_evidence: list[dict[str, Any]],
        role_title: str,
    ) -> list[dict[str, str]]:
        suggestions: list[dict[str, str]] = []
        for entry in missing_required[:3]:
            requirement = entry["requirement"]
            suggestions.append(
                {
                    "requirement": requirement,
                    "issue": "No direct evidence found",
                    "recommendation": f"Add a bullet demonstrating how you used {requirement} in a real project.",
                    "example_bullet": f"Used {requirement} to deliver [project/result] that improved [metric] by [X%] for {role_title} outcomes.",
                }
            )
        for entry in weak_evidence[:2]:
            requirement = entry["requirement"]
            current = entry["evidence"][0] if entry["evidence"] else "Current bullet lacks measurable impact."
            suggestions.append(
                {
                    "requirement": requirement,
                    "issue": "Evidence exists but lacks quantifiable impact",
                    "recommendation": "Add baseline, action, and measurable result in one line.",
                    "example_bullet": f"{current} Result: improved [target metric] by [X%] within [time period].",
                }
            )
        return suggestions[:5]

    def _build_ats_keyword_map(
        self,
        *,
        profile: JobProfileData,
        requirement_assessments: list[dict[str, Any]],
        resume_text_lower: str,
        evidence_units: list[str],
    ) -> list[dict[str, Any]]:
        assessed = {entry["requirement"]: entry for entry in requirement_assessments}
        keywords: list[str] = []
        keywords.extend(canonicalize_skill(skill) for skill in profile.required_skills)
        keywords.extend(canonicalize_skill(skill) for skill in profile.optional_skills[:10])

        role_text = f"{profile.title} {profile.normalized_title}".lower()
        for terms in DOMAIN_KEYWORDS.values():
            keywords.extend(term for term in terms if term in role_text)

        unique_keywords = []
        seen: set[str] = set()
        for keyword in keywords:
            normalized = normalize_term(keyword)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_keywords.append(normalized)

        ats_map: list[dict[str, Any]] = []
        for keyword in unique_keywords[:20]:
            assessment = assessed.get(keyword)
            if assessment is not None:
                matched = assessment["matched"]
                evidence = assessment["evidence"]
            else:
                evidence = self._find_lexical_evidence(
                    requirement=keyword,
                    resume_text_lower=resume_text_lower,
                    evidence_units=evidence_units,
                )
                matched = bool(evidence)

            ats_map.append(
                {
                    "keyword": keyword,
                    "status": "matched" if matched else "missing",
                    "location_hint": self._infer_keyword_location(keyword, resume_text_lower),
                    "evidence": evidence[:1],
                }
            )
        return ats_map

    @staticmethod
    def _infer_keyword_location(keyword: str, resume_text_lower: str) -> str:
        index = resume_text_lower.find(keyword)
        if index < 0:
            return "not found"
        if index < 450:
            return "summary"
        window = resume_text_lower[max(0, index - 180): index + 180]
        if "experience" in window or "employment" in window:
            return "experience"
        if "projects" in window:
            return "projects"
        if "skills" in window:
            return "skills"
        return "resume body"

    @staticmethod
    def _build_explanation_summary(
        *,
        profile: JobProfileData,
        overall: float,
        matched_required: int,
        total_required: int,
        role_alignment_score: float,
        missing_required: list[dict[str, Any]],
    ) -> str:
        headline = (
            f"{overall}% match for {profile.title}. "
            f"Evidence supports {matched_required}/{max(1, total_required)} required capabilities."
        )
        if missing_required:
            biggest_gap = missing_required[0]["requirement"]
            gap_line = f" Biggest gap: missing direct evidence for {biggest_gap}."
        else:
            gap_line = " No hard blockers detected in required capabilities."

        alignment_line = (
            " Responsibility alignment is strong."
            if role_alignment_score >= 70
            else " Responsibility alignment needs clearer bullet-level proof."
        )
        return f"{headline}{gap_line}{alignment_line}"

    @staticmethod
    def _build_recruiter_verdict(
        *,
        overall: float,
        strengths: list[str],
        rejection_risks: list[str],
    ) -> str:
        if overall >= 82:
            status = "Strong shortlist candidate"
        elif overall >= 68:
            status = "Borderline shortlist candidate"
        else:
            status = "Low-confidence shortlist candidate"

        strength_line = strengths[0] if strengths else "Limited strong signals were detected."
        risk_line = rejection_risks[0] if rejection_risks else "No immediate rejection triggers were detected."
        return f"{status}. {strength_line} {risk_line}"
