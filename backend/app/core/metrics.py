"""Prometheus metrics for async analysis runtime safeguards."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

queue_depth_gauge = Gauge(
    "queue_depth",
    "Current depth of the analysis queue.",
)
jobs_created_total = Counter(
    "jobs_created_total",
    "Total number of analysis jobs created.",
)
jobs_cancelled_total = Counter(
    "jobs_cancelled_total",
    "Total number of analysis jobs cancelled.",
)
jobs_expired_total = Counter(
    "jobs_expired_total",
    "Total number of analysis jobs expired before completion.",
)
jobs_timed_out_total = Counter(
    "jobs_timed_out_total",
    "Total number of analysis jobs that timed out.",
)
jobs_retried_total = Counter(
    "jobs_retried_total",
    "Total number of analysis job retries scheduled.",
)
job_duration_seconds = Histogram(
    "job_duration_seconds",
    "End-to-end duration for analysis jobs.",
    buckets=(1, 2, 5, 10, 30, 60, 120, 300, 600, 900, 1800),
)


def set_queue_depth(depth: int) -> None:
    queue_depth_gauge.set(max(depth, 0))


def observe_job_duration(started_at: Optional[datetime], completed_at: Optional[datetime]) -> None:
    if started_at is None or completed_at is None:
        return
    start = _ensure_utc(started_at)
    end = _ensure_utc(completed_at)
    duration = (end - start).total_seconds()
    if duration >= 0:
        job_duration_seconds.observe(duration)


def refresh_queue_depth() -> None:
    """Best-effort queue depth refresh from Redis/RQ for scrape-time accuracy."""
    try:
        from app.workers.queue import get_queue_depth, get_redis_connection

        conn = get_redis_connection()
        depth = get_queue_depth(connection=conn)
        set_queue_depth(depth)
    except Exception:
        # Keep the last observed value if Redis is unavailable.
        pass


def render_metrics() -> bytes:
    refresh_queue_depth()
    return generate_latest()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "job_duration_seconds",
    "jobs_cancelled_total",
    "jobs_created_total",
    "jobs_expired_total",
    "jobs_retried_total",
    "jobs_timed_out_total",
    "observe_job_duration",
    "queue_depth_gauge",
    "render_metrics",
    "set_queue_depth",
]
