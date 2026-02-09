import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

# Ensure a Redis URL is set for tests (connection will be mocked/faked as needed).
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
# Use console logging in tests for readability.
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
