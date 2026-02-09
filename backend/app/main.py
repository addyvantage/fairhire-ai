from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
from app.middleware.request_logging import RequestLoggingMiddleware
from app.queue.connection import RedisManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # --- Logging (must be first) ---
    setup_logging()
    logger.info("Starting FairHire-AI backend")

    # --- Database ---
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified")
    except Exception:
        logger.warning("Database unavailable at startup — skipping table creation")

    # --- Redis (async client for cache / general use) ---
    redis_manager = RedisManager()
    try:
        await redis_manager.connect()
        application.state.redis = redis_manager
        logger.info("Redis async client connected")
    except Exception:
        logger.warning("Redis unavailable at startup — continuing without Redis")
        application.state.redis = redis_manager  # store anyway; callers check .ping()

    # --- Redis connectivity check for RQ (sync client) ---
    try:
        from app.workers.queue import get_redis_connection

        sync_conn = get_redis_connection()
        sync_conn.close()
        logger.info("Redis sync client (RQ) connectivity verified")
    except Exception:
        logger.warning(
            "Redis sync client unavailable — async analysis queue will not function "
            "until Redis is restored"
        )

    yield

    # --- Shutdown ---
    logger.info("Shutting down FairHire-AI backend")
    await redis_manager.close()


settings = get_settings()
app = FastAPI(title=settings.project_name, lifespan=lifespan)

# Middleware is applied in reverse registration order (last registered = outermost).
# CORSMiddleware must be outermost so preflight requests work before anything else.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
