from app.schemas.analysis import ExplainableMetric
from app.services.interfaces import BiasDetectorInterface


class BiasDetectorService(BiasDetectorInterface):
    _flagged_terms = {
        "young": "Age-coded wording",
        "aggressive": "Potentially exclusionary tone",
        "digital native": "Age-coded wording",
        "rockstar": "Gender-coded or non-inclusive term",
        "ninja": "Gender-coded or non-inclusive term",
        "he/she": "Binary gender phrasing",
    }

    async def score(self, jd_text: str) -> ExplainableMetric:
        jd_lower = jd_text.lower()
        findings = []
        for term, reason in self._flagged_terms.items():
            if term in jd_lower:
                findings.append(f"'{term}' flagged: {reason}")

        penalty = min(len(findings) * 15, 90)
        score = max(100 - penalty, 0)

        explanation = (
            "Bias risk is lower when fewer exclusionary terms are detected."
            if findings
            else "No high-risk bias keywords detected by rule-based scan."
        )

        return ExplainableMetric(
            score=round(score, 2),
            explanation=explanation,
            contributing_factors=findings or ["No flagged terms found"],
        )
