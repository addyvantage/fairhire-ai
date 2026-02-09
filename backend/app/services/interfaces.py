from abc import ABC, abstractmethod
from enum import Enum

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


class ModelState(str, Enum):
    """Lifecycle states for ML model services (fail-closed semantics)."""

    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class EmbeddingServiceInterface(ABC):
    """Contract for text embedding services.

    Implementations MUST enforce fail-closed semantics: if the model is not
    in the READY state, ``encode`` and ``encode_batch`` MUST raise
    ``RuntimeError`` rather than returning degraded results.
    """

    @abstractmethod
    async def load_model(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def encode(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def state(self) -> ModelState:
        raise NotImplementedError

    @property
    def is_ready(self) -> bool:
        return self.state == ModelState.READY
