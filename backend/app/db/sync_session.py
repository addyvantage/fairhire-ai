"""Synchronous SQLAlchemy engine and session for use in RQ workers.

RQ is a synchronous job queue — workers must NOT use async DB sessions
(which require greenlet_spawn and cause ``MissingGreenlet`` errors).
This module provides a plain synchronous engine/session that strips the
``+asyncpg`` driver from the configured DATABASE_URL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _make_sync_url(async_url: str) -> str:
    """Convert an async database URL to a sync one.

    ``postgresql+asyncpg://...`` → ``postgresql+psycopg2://...``
    """
    return async_url.replace("+asyncpg", "+psycopg2")


_settings = get_settings()

sync_engine = create_engine(
    _make_sync_url(_settings.database_url),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)
