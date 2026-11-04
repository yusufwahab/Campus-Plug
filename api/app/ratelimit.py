import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.config import get_settings

# In-process sliding window. On a single Render instance this is sufficient; with several
# instances move the buckets into the database (documented in docs/RUNBOOK.md).
_buckets: dict[str, deque[float]] = defaultdict(deque)


def reset_limits() -> None:
    _buckets.clear()


def rate_limit(name: str, limit: int, per_seconds: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        bucket = _buckets[f"{name}:{ip}"]
        now = time.monotonic()
        while bucket and bucket[0] <= now - per_seconds:
            bucket.popleft()
        if len(bucket) >= limit * get_settings().rate_limit_multiplier:
            raise HTTPException(429, "Too many requests. Please wait a moment and try again.")
        bucket.append(now)

    return dependency
