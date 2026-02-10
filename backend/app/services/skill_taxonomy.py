"""Shared skill taxonomy used by both resume analysis and JD parsing.

Single source of truth for known skills and their categories.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Categorised skill sets
# ---------------------------------------------------------------------------

SKILL_CATEGORIES: dict[str, set[str]] = {
    "languages": {
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
        "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    },
    "frameworks": {
        "react", "angular", "vue", "next.js", "nuxt", "django", "flask",
        "fastapi", "express", "spring", "rails", "laravel", "node.js",
        "svelte", "ember", ".net",
    },
    "data_ml": {
        "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "spark",
        "hadoop", "kafka", "airflow", "mlflow", "jupyter",
        "nlp", "ml", "deep learning", "machine learning", "data science",
        "computer vision", "a/b testing", "statistics", "dbt",
    },
    "databases": {
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "dynamodb", "cassandra", "sqlite", "oracle", "bigquery",
    },
    "cloud_devops": {
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "jenkins", "github actions", "gitlab ci", "ci/cd", "ansible",
        "prometheus", "grafana", "monitoring", "linux",
    },
    "tools": {
        "git", "jira", "figma", "tableau", "power bi",
        "rest apis", "graphql", "grpc", "microservices",
        "webpack", "tailwind css", "responsive design",
        "sketch", "adobe xd",
    },
    "soft_skills": {
        "agile", "scrum", "leadership", "project management",
        "communication", "stakeholder management", "product strategy",
        "roadmap planning", "user research", "design systems",
        "wireframing", "prototyping", "usability testing",
        "information architecture", "motion design", "accessibility",
        "technical writing", "testing", "okrs", "market research",
    },
}

# Flat set of all known skills (for fast lookup)
KNOWN_SKILLS: frozenset[str] = frozenset(
    skill for category in SKILL_CATEGORIES.values() for skill in category
)


SKILL_SYNONYMS: dict[str, set[str]] = {
    "sql": {"structured query language", "mysql", "postgres", "postgresql", "t-sql"},
    "python": {"python3", "py"},
    "javascript": {"js", "ecmascript"},
    "typescript": {"ts"},
    "react": {"reactjs", "react.js"},
    "next.js": {"nextjs", "next js"},
    "node.js": {"node", "nodejs", "node js"},
    "rest apis": {"rest api", "api integration", "http apis"},
    "ci/cd": {"continuous integration", "continuous delivery", "continuous deployment", "cicd"},
    "stakeholder management": {
        "cross functional collaboration",
        "cross-functional collaboration",
        "executive communication",
        "partner management",
    },
    "data visualization": {"dashboarding", "dashboards", "visual analytics"},
    "machine learning": {"ml", "predictive modeling", "model development"},
    "a/b testing": {"ab testing", "split testing", "experimentation"},
    "power bi": {"powerbi"},
    "tableau": {"tableau desktop"},
    "excel": {"microsoft excel", "advanced excel"},
}

DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "engineering": {
        "software",
        "engineer",
        "api",
        "microservices",
        "frontend",
        "backend",
        "platform",
        "devops",
    },
    "data": {
        "analytics",
        "analyst",
        "data",
        "reporting",
        "dashboard",
        "etl",
        "warehouse",
        "kpi",
    },
    "finance": {
        "financial",
        "fp&a",
        "forecast",
        "budget",
        "variance",
        "p&l",
        "valuation",
        "reconciliation",
    },
    "consulting": {
        "client",
        "case",
        "strategy",
        "stakeholder",
        "presentation",
        "recommendation",
        "problem-solving",
    },
    "operations": {
        "operations",
        "process",
        "sop",
        "logistics",
        "supply chain",
        "efficiency",
        "throughput",
    },
}

SOFT_SKILL_KEYWORDS: frozenset[str] = frozenset(
    {
        "communication",
        "leadership",
        "stakeholder management",
        "collaboration",
        "problem solving",
        "project management",
        "analytical thinking",
        "attention to detail",
        "ownership",
        "adaptability",
        "critical thinking",
    }
)


def normalize_term(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def expand_skill_aliases(skill: str) -> set[str]:
    canonical = normalize_term(skill)
    aliases = set(SKILL_SYNONYMS.get(canonical, set()))
    aliases.add(canonical)
    return {normalize_term(alias) for alias in aliases if alias.strip()}


def canonicalize_skill(skill: str) -> str:
    candidate = normalize_term(skill)
    if candidate in KNOWN_SKILLS:
        return candidate

    for canonical, aliases in SKILL_SYNONYMS.items():
        if candidate == canonical:
            return canonical
        if candidate in {normalize_term(alias) for alias in aliases}:
            return canonical

    return candidate
