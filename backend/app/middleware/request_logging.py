"""ASGI middleware that logs every HTTP request with structured context.

Adds a unique ``X-Request-ID`` header to both the request context (for
downstream correlation) and the response.  Logs method, path, status code,
duration, and — when available — the authenticated user id extracted from
the JWT ``Authorization`` header (best-effort, never blocks the request).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _extract_user_id(authorization: str | None) -> str | None:
    """Best-effort extraction of user id from a Bearer JWT.

    Returns ``None`` on any failure — this is purely for logging enrichment
    and must never raise or block the request pipeline.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except (JWTError, ValueError, KeyError):
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request/response with structured context."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        user_id = _extract_user_id(request.headers.get("Authorization"))
        client_ip = request.client.host if request.client else "unknown"

        # Bind context vars so any downstream log call includes them.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            **({"user_id": user_id} if user_id else {}),
        )

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_error",
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code

        log_kw: dict[str, Any] = {
            "status_code": status_code,
            "duration_ms": duration_ms,
        }

        if status_code >= 500:
            logger.error("request_finished", **log_kw)
        elif status_code >= 400:
            logger.warning("request_finished", **log_kw)
        else:
            logger.info("request_finished", **log_kw)

        response.headers["X-Request-ID"] = request_id
        return response
