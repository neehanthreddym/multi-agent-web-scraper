"""The dispatcher touches its heartbeat after each successful database scan."""

import time
from pathlib import Path


heartbeat = Path("/tmp/catalog-dispatcher-heartbeat")
if not heartbeat.exists() or time.time() - heartbeat.stat().st_mtime > 30:
    raise SystemExit(1)
