from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401
from app.middleware.request_logging import RequestLoggingMiddleware
from app.queue.connection import RedisManager

logger = logging.getLogger(__name__)


_SCHEMA_MIGRATIONS = [
    # Make job_description_id nullable (idempotent via DO $$ block)
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'analysis_runs'
            AND column_name = 'job_description_id'
            AND is_nullable = 'NO'
        ) THEN
            ALTER TABLE analysis_runs ALTER COLUMN job_description_id DROP NOT NULL;
        END IF;
    END $$;
    """,
    # Add new timestamp columns
    "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ",
    "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    # Job-targeted analysis: add job_profile_id FK to analysis_runs
    "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS job_profile_id INTEGER REFERENCES job_profiles(id) ON DELETE SET NULL",
    # Remember last-used job profile per user
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_job_profile_id INTEGER REFERENCES job_profiles(id) ON DELETE SET NULL",
]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # --- Logging (must be first) ---
    setup_logging()
    logger.info("Starting FairHire-AI backend")

    # --- Database ---
    try:
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.studio_export_dir).mkdir(parents=True, exist_ok=True)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            # Apply incremental schema migrations (idempotent)
            for migration_sql in _SCHEMA_MIGRATIONS:
                await connection.execute(text(migration_sql))
        logger.info("Database tables verified")

        # Seed job profile templates (idempotent)
        from app.services.job_profile_templates import seed_templates

        await seed_templates(engine)
        logger.info("Job profile templates seeded")
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


def _normalize_allowed_origins(raw_origins: Iterable[str] | str | None) -> list[str]:
    if raw_origins is None:
        return []
    if isinstance(raw_origins, str):
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return [origin.strip() for origin in raw_origins if isinstance(origin, str) and origin.strip()]


allowed_origins = _normalize_allowed_origins(settings.allowed_origins)

# Middleware is applied in reverse registration order (last registered = outermost).
# CORSMiddleware must be outermost so preflight requests work before anything else.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://([A-Za-z0-9-]+\.)*vercel\.app(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
