"""Optional local open-weights reasoning layer.

Uses llama.cpp if a model path is configured. If unavailable, returns None
so deterministic scoring output remains intact.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LocalReasoner:
    """Thin wrapper around a local llama.cpp model for concise reasoning."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._llm = None

    def is_enabled(self) -> bool:
        return bool(self.settings.open_weights_reasoner_model_path.strip())

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        if not self.is_enabled():
            return None
        try:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.settings.open_weights_reasoner_model_path,
                n_ctx=4096,
                n_threads=4,
                verbose=False,
            )
            return self._llm
        except Exception:
            logger.warning("Unable to initialize local reasoner model", exc_info=True)
            return None

    def generate(self, context: dict[str, Any]) -> dict[str, Any] | None:
        llm = self._get_llm()
        if llm is None:
            return None

        prompt = self._build_prompt(context)
        try:
            completion = llm.create_completion(
                prompt=prompt,
                max_tokens=self.settings.open_weights_reasoner_max_tokens,
                temperature=self.settings.open_weights_reasoner_temperature,
                stop=["</json>", "\n\n\n"],
            )
            text = completion.get("choices", [{}])[0].get("text", "").strip()
            if not text:
                return None
            json_text = self._extract_json(text)
            if json_text is None:
                return None
            payload = json.loads(json_text)
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception:
            logger.warning("Local reasoner generation failed", exc_info=True)
            return None

    @staticmethod
    def _extract_json(text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        return text[start:end + 1]

    @staticmethod
    def _build_prompt(context: dict[str, Any]) -> str:
        schema = (
            '{'
            '"recruiter_verdict":"string (1-2 sentences)",'
            '"explanation_summary":"string (2 sentences max)",'
            '"rewrite_suggestions":[{"requirement":"string","issue":"string","recommendation":"string","example_bullet":"string"}]'
            '}'
        )
        return (
            "You are a strict recruiting analyst. Use only provided evidence. "
            "Do not invent skills or outcomes. Keep concise. Output JSON only.\n"
            f"JSON schema: {schema}\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}\n"
            "Return JSON now:\n"
        )
