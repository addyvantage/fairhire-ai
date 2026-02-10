"""Shared skill taxonomy used by both resume analysis and JD parsing.

Single source of truth for known skills and their categories.
"""

from __future__ import annotations

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
