"""RQ worker entry point with heartbeat.

Run as: ``python -m app.workers.worker_runner``

The worker:
1. Connects to Redis.
2. Registers a periodic heartbeat key (``fairhire:worker:heartbeat:<pid>``).
3. Listens on the configured analysis queue.
4. Shuts down gracefully on SIGINT / SIGTERM.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time

from redis import Redis
from rq import Worker

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.queue import get_queue, get_redis_connection

logger = logging.getLogger(__name__)

_HEARTBEAT_KEY_PREFIX = "fairhire:worker:heartbeat"
_shutdown_requested = threading.Event()


def _heartbeat_loop(conn: Redis, interval: int, ttl: int) -> None:
    """Background thread that writes a heartbeat key periodically."""
    pid = os.getpid()
    key = f"{_HEARTBEAT_KEY_PREFIX}:{pid}"
    logger.info("Heartbeat thread started", extra={"key": key, "interval": interval, "ttl": ttl})
    while not _shutdown_requested.is_set():
        try:
            conn.set(key, str(time.time()), ex=ttl)
        except Exception:
            logger.warning("Heartbeat write failed", exc_info=True)
        _shutdown_requested.wait(timeout=interval)
    # Clean up heartbeat key on shutdown.
    try:
        conn.delete(key)
    except Exception:
        pass
    logger.info("Heartbeat thread stopped")


def _signal_handler(signum: int, frame: object) -> None:
    logger.info("Shutdown signal received", extra={"signal": signum})
    _shutdown_requested.set()


def main() -> None:
    setup_logging()
    settings = get_settings()

    logger.info("Starting FairHire-AI worker")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    conn = get_redis_connection()
    queue = get_queue(connection=conn)

    # Start heartbeat in a daemon thread.
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(conn, settings.worker_heartbeat_interval_seconds, settings.worker_heartbeat_ttl_seconds),
        daemon=True,
        name="worker-heartbeat",
    )
    heartbeat_thread.start()

    worker = Worker([queue], connection=conn, name=f"fairhire-worker-{os.getpid()}")
    logger.info("Worker listening", extra={"queue": settings.queue_name, "pid": os.getpid()})

    try:
        worker.work(with_scheduler=False)
    except SystemExit:
        pass
    finally:
        _shutdown_requested.set()
        heartbeat_thread.join(timeout=5)
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
