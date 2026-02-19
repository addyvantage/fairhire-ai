"""Context-aware budget guards for LLM calls inside worker jobs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar


class BudgetExceededError(RuntimeError):
    """Raised when an LLM call would exceed the configured per-job budget."""


class LLMCallTracker:
    def __init__(
        self,
        *,
        max_calls: int,
        initial_used: int = 0,
        on_call: Callable[[int], None] | None = None,
    ) -> None:
        self.max_calls = max(0, max_calls)
        self.used = max(0, initial_used)
        self._on_call = on_call

    def consume(self) -> int:
        if self.used >= self.max_calls:
            raise BudgetExceededError(
                f"LLM call budget exceeded ({self.used}/{self.max_calls})"
            )
        self.used += 1
        if self._on_call is not None:
            self._on_call(self.used)
        return self.used


_tracker_var: ContextVar[LLMCallTracker | None] = ContextVar("llm_call_tracker", default=None)


@contextmanager
def activate_llm_call_tracker(tracker: LLMCallTracker):
    token = _tracker_var.set(tracker)
    try:
        yield
    finally:
        _tracker_var.reset(token)


def consume_llm_call() -> int | None:
    tracker = _tracker_var.get()
    if tracker is None:
        return None
    return tracker.consume()
