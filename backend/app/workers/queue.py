"""RQ queue infrastructure backed by Redis.

Provides synchronous Redis connection and RQ Queue for job enqueueing.
The worker process and the API server both use these helpers.

If Redis is unavailable, ``get_redis_connection`` raises ``RuntimeError``
immediately (fail-closed).
"""

from __future__ import annotations

import logging

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError
from rq import Queue
from rq.job import Job
from rq.registry import FailedJobRegistry

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_redis_connection() -> Redis:
    """Create a synchronous Redis connection for RQ.

    RQ requires a synchronous ``redis.Redis`` client (not ``redis.asyncio``).
    Raises ``RuntimeError`` if the connection cannot be established.
    """
    settings = get_settings()
    try:
        conn = Redis.from_url(
            settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=30,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=15,
        )
        conn.ping()
        return conn
    except (RedisConnectionError, RedisError, OSError) as exc:
        raise RuntimeError(
            f"Cannot connect to Redis at {settings.redis_url}: {exc}"
        ) from exc


def get_queue(connection: Redis | None = None) -> Queue:
    """Return the analysis RQ Queue.

    If *connection* is not provided, a new synchronous connection is created.
    """
    settings = get_settings()
    conn = connection or get_redis_connection()
    return Queue(name=settings.queue_name, connection=conn)


def get_queue_depth(connection: Redis | None = None) -> int:
    """Return the number of jobs currently in the analysis queue."""
    queue = get_queue(connection=connection)
    return queue.count


def get_failed_registry(connection: Redis | None = None) -> FailedJobRegistry:
    """Return the failed job registry for the analysis queue."""
    queue = get_queue(connection=connection)
    return FailedJobRegistry(queue=queue)


def fetch_job(job_id: str, connection: Redis | None = None) -> Job | None:
    """Fetch an RQ Job by ID. Returns None if the job does not exist."""
    settings = get_settings()
    conn = connection or get_redis_connection()
    try:
        return Job.fetch(job_id, connection=conn)
    except Exception:
        return None
