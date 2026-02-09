from app.schemas.analysis import ExplainableMetric
from app.services.interfaces import ATSScorerInterface


class ATSScorerService(ATSScorerInterface):
    async def score(self, resume_text: str, jd_text: str) -> ExplainableMetric:
        sections = ["experience", "skills", "education"]
        resume_lower = resume_text.lower()
        present_sections = [section for section in sections if section in resume_lower]

        jd_keywords = {kw for kw in jd_text.lower().split() if len(kw) > 4}
        resume_keywords = {kw for kw in resume_text.lower().split() if len(kw) > 4}
        keyword_coverage = (
            len(jd_keywords & resume_keywords) / len(jd_keywords) if jd_keywords else 0
        )

        section_score = len(present_sections) / len(sections)
        total_score = ((section_score * 0.4) + (keyword_coverage * 0.6)) * 100

        return ExplainableMetric(
            score=round(total_score, 2),
            explanation="ATS compatibility based on section completeness and keyword coverage.",
            contributing_factors=[
                f"Detected sections: {', '.join(present_sections) if present_sections else 'none'}",
                f"Keyword coverage: {round(keyword_coverage * 100, 2)}%",
            ],
        )
