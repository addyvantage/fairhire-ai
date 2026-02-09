"""Tests for the request logging middleware.

These tests verify:
- Every response gets an X-Request-ID header
- Client-supplied X-Request-ID is preserved
- Structured log entries are emitted for each request
- User ID is extracted from JWT for log enrichment
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware, _extract_user_id


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with only the logging middleware."""
    test_app = FastAPI()
    test_app.add_middleware(RequestLoggingMiddleware)

    @test_app.get("/ok")
    async def ok() -> dict:
        return {"status": "ok"}

    @test_app.get("/error")
    async def error() -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "boom"})

    @test_app.get("/not-found")
    async def not_found() -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "nope"})

    @test_app.get("/unhandled")
    async def unhandled(request: Request) -> dict:
        raise RuntimeError("unexpected failure")

    return test_app


# ---------------------------------------------------------------------------
# X-Request-ID tests
# ---------------------------------------------------------------------------


def test_response_contains_request_id() -> None:
    """Every response must include an X-Request-ID header."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/ok")
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert len(request_id) > 0


def test_client_supplied_request_id_is_preserved() -> None:
    """If the client sends X-Request-ID, the middleware must echo it back."""
    app = _make_app()
    custom_id = "my-trace-abc-123"
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/ok", headers={"X-Request-ID": custom_id})
    assert response.headers.get("X-Request-ID") == custom_id


def test_generated_request_id_is_uuid_format() -> None:
    """Auto-generated request IDs should be valid UUID4 strings."""
    import uuid

    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/ok")
    request_id = response.headers["X-Request-ID"]
    parsed = uuid.UUID(request_id)
    assert parsed.version == 4


# ---------------------------------------------------------------------------
# Logging output tests
# ---------------------------------------------------------------------------


def test_request_finished_is_logged(caplog: object) -> None:
    """The middleware must emit a 'request_finished' log entry."""
    setup_logging()
    app = _make_app()
    import logging

    with caplog_at_level(caplog, logging.DEBUG):  # type: ignore[arg-type]
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/ok")

    # structlog sends through stdlib so caplog captures it.
    messages = [r.message for r in caplog.records]  # type: ignore[attr-defined]
    assert any("request_finished" in m for m in messages)


def test_500_response_logs_at_error_level(caplog: object) -> None:
    """5xx responses should be logged at ERROR level."""
    setup_logging()
    app = _make_app()
    import logging

    with caplog_at_level(caplog, logging.DEBUG):  # type: ignore[arg-type]
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/error")

    error_records = [
        r for r in caplog.records if r.levelno >= logging.ERROR  # type: ignore[attr-defined]
    ]
    assert len(error_records) > 0


def test_404_response_logs_at_warning_level(caplog: object) -> None:
    """4xx responses should be logged at WARNING level."""
    setup_logging()
    app = _make_app()
    import logging

    with caplog_at_level(caplog, logging.DEBUG):  # type: ignore[arg-type]
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/not-found")

    warning_records = [
        r for r in caplog.records if r.levelno == logging.WARNING  # type: ignore[attr-defined]
    ]
    assert len(warning_records) > 0


# ---------------------------------------------------------------------------
# JWT user_id extraction (unit tests)
# ---------------------------------------------------------------------------


def test_extract_user_id_returns_none_without_header() -> None:
    assert _extract_user_id(None) is None


def test_extract_user_id_returns_none_for_non_bearer() -> None:
    assert _extract_user_id("Basic abc123") is None


def test_extract_user_id_returns_none_for_garbage_token() -> None:
    assert _extract_user_id("Bearer not.a.jwt") is None


def test_extract_user_id_returns_sub_from_valid_jwt() -> None:
    from app.core.security import TokenService

    token = TokenService.create_access_token(subject="42")
    result = _extract_user_id(f"Bearer {token}")
    assert result == "42"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import contextmanager
import logging as _logging


@contextmanager
def caplog_at_level(caplog: object, level: int):  # type: ignore[type-arg]
    """Temporarily enable caplog propagation at the given level."""
    caplog.set_level(level)  # type: ignore[attr-defined]
    root = _logging.getLogger()
    old_level = root.level
    root.setLevel(level)
    try:
        yield
    finally:
        root.setLevel(old_level)
