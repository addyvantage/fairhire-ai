#!/usr/bin/env python3
"""FairHire-AI stack healthcheck.

Verifies that all services started by ``make dev`` are reachable and
functioning.  Exit code 0 = healthy, 1 = one or more checks failed.

Usage:
    python scripts/healthcheck.py
    make health
"""

from __future__ import annotations

import socket
import sys
import time
import urllib.request
import urllib.error


CHECKS: list[dict] = [
    {
        "name": "PostgreSQL",
        "host": "localhost",
        "port": 5432,
    },
    {
        "name": "Redis",
        "host": "localhost",
        "port": 6379,
    },
    {
        "name": "Backend API",
        "url": "http://localhost:8000/docs",
        "expected_status": 200,
    },
    {
        "name": "Frontend",
        "url": "http://localhost:3000",
        "expected_status": 200,
    },
    {
        "name": "Prometheus",
        "url": "http://localhost:9090/-/healthy",
        "expected_status": 200,
    },
    {
        "name": "Grafana",
        "url": "http://localhost:3001/api/health",
        "expected_status": 200,
    },
]


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """Return True if a TCP connection can be established."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def check_http(url: str, expected_status: int = 200, timeout: float = 5.0) -> bool:
    """Return True if the URL responds with the expected HTTP status."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == expected_status
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


def run_checks(max_retries: int = 12, interval: float = 5.0) -> bool:
    """Run all checks with retries.  Returns True if all pass."""
    pending = list(CHECKS)
    passed: list[str] = []
    failed: list[str] = []

    for attempt in range(1, max_retries + 1):
        still_pending = []
        for check in pending:
            name = check["name"]
            ok = False
            if "url" in check:
                ok = check_http(check["url"], check.get("expected_status", 200))
            elif "host" in check and "port" in check:
                ok = check_tcp(check["host"], check["port"])

            if ok:
                passed.append(name)
                print(f"  [OK]   {name}")
            else:
                still_pending.append(check)

        pending = still_pending
        if not pending:
            break

        if attempt < max_retries:
            remaining = [c["name"] for c in pending]
            print(f"  ... waiting for: {', '.join(remaining)} (attempt {attempt}/{max_retries})")
            time.sleep(interval)

    for check in pending:
        failed.append(check["name"])
        print(f"  [FAIL] {check['name']}")

    return len(failed) == 0


def main() -> None:
    print("=" * 50)
    print("FairHire-AI Stack Healthcheck")
    print("=" * 50)
    print()

    healthy = run_checks()

    print()
    if healthy:
        print("All services are healthy.")
        sys.exit(0)
    else:
        print("One or more services failed healthcheck.")
        sys.exit(1)


if __name__ == "__main__":
    main()
