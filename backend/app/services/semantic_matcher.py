import re

from app.schemas.analysis import ExplainableMetric
from app.services.interfaces import SemanticMatcherInterface


class SemanticMatcherService(SemanticMatcherInterface):
    async def score(self, resume_text: str, jd_text: str) -> ExplainableMetric:
        resume_tokens = self._tokens(resume_text)
        jd_tokens = self._tokens(jd_text)
        if not jd_tokens:
            return ExplainableMetric(
                score=0,
                explanation="Job description text is empty or not parseable.",
                contributing_factors=["No valid JD tokens found"],
            )

        overlap = resume_tokens & jd_tokens
        union = resume_tokens | jd_tokens
        jaccard = (len(overlap) / len(union)) * 100 if union else 0

        factors = [
            f"Overlapping keyword count: {len(overlap)}",
            f"JD keyword count: {len(jd_tokens)}",
            f"Resume keyword count: {len(resume_tokens)}",
        ]

        return ExplainableMetric(
            score=round(jaccard, 2),
            explanation="Semantic alignment estimated using keyword overlap (placeholder heuristic).",
            contributing_factors=factors,
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.lower() for token in re.findall(r"[a-zA-Z]{3,}", text)}
