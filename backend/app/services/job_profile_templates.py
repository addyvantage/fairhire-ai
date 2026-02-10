"""System job profile templates seeded at startup.

These provide pre-configured job profiles for common roles so users
can start analyzing resumes immediately without creating a profile.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.job_profile import JobProfile

logger = logging.getLogger(__name__)

TEMPLATES: list[dict] = [
    {
        "title": "Frontend Engineer",
        "normalized_title": "frontend engineer",
        "seniority_level": "mid",
        "required_skills": [
            "javascript", "typescript", "react", "html", "css",
            "git", "responsive design", "rest apis",
        ],
        "optional_skills": [
            "next.js", "vue", "angular", "graphql", "webpack",
            "tailwind css", "testing", "ci/cd",
        ],
        "responsibilities": [
            "Build and maintain user-facing web applications",
            "Collaborate with designers to implement UI/UX specifications",
            "Write clean, tested, and well-documented code",
            "Optimize applications for speed and scalability",
            "Participate in code reviews and architectural discussions",
        ],
        "years_experience_min": 2,
        "years_experience_max": 5,
    },
    {
        "title": "Backend Engineer",
        "normalized_title": "backend engineer",
        "seniority_level": "mid",
        "required_skills": [
            "python", "sql", "rest apis", "git", "postgresql",
            "docker", "linux", "testing",
        ],
        "optional_skills": [
            "fastapi", "django", "flask", "redis", "rabbitmq",
            "kubernetes", "aws", "ci/cd",
        ],
        "responsibilities": [
            "Design, build, and maintain server-side applications and APIs",
            "Write efficient database queries and manage data models",
            "Implement authentication, authorization, and security practices",
            "Monitor and optimize application performance",
            "Collaborate with frontend and infrastructure teams",
        ],
        "years_experience_min": 2,
        "years_experience_max": 5,
    },
    {
        "title": "Full-Stack Developer",
        "normalized_title": "full-stack developer",
        "seniority_level": "mid",
        "required_skills": [
            "javascript", "typescript", "python", "react", "sql",
            "rest apis", "git", "html", "css",
        ],
        "optional_skills": [
            "node.js", "next.js", "docker", "postgresql", "mongodb",
            "aws", "graphql", "redis",
        ],
        "responsibilities": [
            "Develop features across the full application stack",
            "Build responsive frontends and robust backend services",
            "Design and implement database schemas",
            "Deploy and maintain applications in cloud environments",
            "Participate in system design and architecture decisions",
        ],
        "years_experience_min": 3,
        "years_experience_max": 6,
    },
    {
        "title": "Data Analyst",
        "normalized_title": "data analyst",
        "seniority_level": "mid",
        "required_skills": [
            "sql", "python", "excel", "data visualization",
            "statistics", "pandas", "communication",
        ],
        "optional_skills": [
            "tableau", "power bi", "r", "jupyter", "dbt",
            "airflow", "bigquery", "a/b testing",
        ],
        "responsibilities": [
            "Analyze large datasets to extract actionable insights",
            "Build dashboards and reports for stakeholders",
            "Define and track key performance metrics",
            "Collaborate with product and engineering teams on data needs",
            "Maintain data quality and documentation standards",
        ],
        "years_experience_min": 1,
        "years_experience_max": 4,
    },
    {
        "title": "Product Manager",
        "normalized_title": "product manager",
        "seniority_level": "mid",
        "required_skills": [
            "product strategy", "roadmap planning", "user research",
            "data analysis", "communication", "stakeholder management",
            "agile",
        ],
        "optional_skills": [
            "sql", "jira", "figma", "a/b testing", "okrs",
            "market research", "technical writing",
        ],
        "responsibilities": [
            "Define product vision, strategy, and roadmap",
            "Gather and prioritize user requirements",
            "Work closely with engineering and design teams",
            "Analyze product metrics and drive data-informed decisions",
            "Communicate product plans to stakeholders and leadership",
        ],
        "years_experience_min": 3,
        "years_experience_max": 7,
    },
    {
        "title": "DevOps Engineer",
        "normalized_title": "devops engineer",
        "seniority_level": "mid",
        "required_skills": [
            "linux", "docker", "ci/cd", "aws", "terraform",
            "git", "monitoring", "scripting",
        ],
        "optional_skills": [
            "kubernetes", "ansible", "jenkins", "github actions",
            "prometheus", "grafana", "python", "go",
        ],
        "responsibilities": [
            "Design and maintain CI/CD pipelines",
            "Manage cloud infrastructure and deployment automation",
            "Monitor system health and respond to incidents",
            "Implement security best practices across infrastructure",
            "Collaborate with development teams to improve reliability",
        ],
        "years_experience_min": 2,
        "years_experience_max": 5,
    },
    {
        "title": "ML Engineer",
        "normalized_title": "ml engineer",
        "seniority_level": "mid",
        "required_skills": [
            "python", "machine learning", "deep learning",
            "pytorch", "sql", "statistics", "git",
        ],
        "optional_skills": [
            "tensorflow", "mlflow", "docker", "aws", "spark",
            "nlp", "computer vision", "kubernetes",
        ],
        "responsibilities": [
            "Design, train, and deploy machine learning models",
            "Build and maintain ML pipelines and infrastructure",
            "Evaluate model performance and iterate on improvements",
            "Collaborate with data scientists and product teams",
            "Monitor models in production and handle drift detection",
        ],
        "years_experience_min": 2,
        "years_experience_max": 5,
    },
    {
        "title": "UX Designer",
        "normalized_title": "ux designer",
        "seniority_level": "mid",
        "required_skills": [
            "figma", "user research", "wireframing", "prototyping",
            "usability testing", "design systems", "communication",
        ],
        "optional_skills": [
            "sketch", "adobe xd", "html", "css", "accessibility",
            "motion design", "analytics", "information architecture",
        ],
        "responsibilities": [
            "Conduct user research and usability testing",
            "Create wireframes, prototypes, and high-fidelity designs",
            "Maintain and evolve design system components",
            "Collaborate with product managers and engineers",
            "Advocate for user needs and accessibility standards",
        ],
        "years_experience_min": 2,
        "years_experience_max": 5,
    },
]


async def seed_templates(async_engine: AsyncEngine) -> None:
    """Insert system template job profiles if they don't already exist.

    Idempotent — skips any template whose title already exists with
    ``is_template=True``.
    """
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        # Fetch existing template titles in one query
        result = await session.execute(
            select(JobProfile.title).where(JobProfile.is_template.is_(True))
        )
        existing_titles: set[str] = {row[0] for row in result.all()}

        inserted = 0
        for tpl in TEMPLATES:
            if tpl["title"] in existing_titles:
                continue
            profile = JobProfile(
                user_id=None,
                title=tpl["title"],
                normalized_title=tpl["normalized_title"],
                seniority_level=tpl["seniority_level"],
                required_skills=tpl["required_skills"],
                optional_skills=tpl["optional_skills"],
                responsibilities=tpl["responsibilities"],
                years_experience_min=tpl["years_experience_min"],
                years_experience_max=tpl["years_experience_max"],
                source="template",
                raw_description=None,
                is_template=True,
            )
            session.add(profile)
            inserted += 1

        if inserted:
            await session.commit()
            logger.info("Seeded %d job profile templates", inserted)
        else:
            logger.debug("All job profile templates already exist")
