from app.schemas.analysis import ExplainableMetric
from app.services.ats_scorer import ATSScorerService
from app.services.bias_detector import BiasDetectorService
from app.services.semantic_matcher import SemanticMatcherService
from app.services.skill_extractor import SkillExtractorService


class AnalysisOrchestrator:
    def __init__(self) -> None:
        self.skill_extractor = SkillExtractorService()
        self.semantic_matcher = SemanticMatcherService()
        self.ats_scorer = ATSScorerService()
        self.bias_detector = BiasDetectorService()

    async def analyze(self, resume_text: str, jd_text: str) -> dict:
        resume_skills = await self.skill_extractor.extract(resume_text)
        jd_skills = await self.skill_extractor.extract(jd_text)

        semantic_metric = await self.semantic_matcher.score(resume_text, jd_text)
        ats_metric = await self.ats_scorer.score(resume_text, jd_text)
        bias_metric = await self.bias_detector.score(jd_text)

        overall = self._weighted_score(semantic_metric, ats_metric, bias_metric)

        return {
            "overall_score": overall,
            "semantic_match": semantic_metric,
            "ats_compatibility": ats_metric,
            "bias_detection": bias_metric,
            "extracted_resume_skills": resume_skills,
            "extracted_jd_skills": jd_skills,
        }

    @staticmethod
    def _weighted_score(
        semantic_metric: ExplainableMetric,
        ats_metric: ExplainableMetric,
        bias_metric: ExplainableMetric,
    ) -> float:
        score = (semantic_metric.score * 0.5) + (ats_metric.score * 0.3) + (bias_metric.score * 0.2)
        return round(score, 2)
