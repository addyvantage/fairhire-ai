from abc import ABC, abstractmethod

from app.schemas.analysis import ExplainableMetric


class ResumeParserInterface(ABC):
    @abstractmethod
    async def parse(self, filename: str, content: bytes) -> str:
        raise NotImplementedError


class SkillExtractorInterface(ABC):
    @abstractmethod
    async def extract(self, text: str) -> list[str]:
        raise NotImplementedError


class SemanticMatcherInterface(ABC):
    @abstractmethod
    async def score(self, resume_text: str, jd_text: str) -> ExplainableMetric:
        raise NotImplementedError


class ATSScorerInterface(ABC):
    @abstractmethod
    async def score(self, resume_text: str, jd_text: str) -> ExplainableMetric:
        raise NotImplementedError


class BiasDetectorInterface(ABC):
    @abstractmethod
    async def score(self, jd_text: str) -> ExplainableMetric:
        raise NotImplementedError
