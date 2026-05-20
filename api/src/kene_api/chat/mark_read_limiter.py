"""Per-session sliding-window rate limiter for POST /conversations/{id}/mark-read.

This is the BL-PRD-05 fallback limiter — an in-process deque per session_id.
It is per-pod (not per-fleet), which means horizontal autoscaling allows up to
N x 60 requests/min across N pods. Acceptable for v1 per CH-PRD-02 §3.

TODO(BL-PRD-05): replace with Firestore-backed sliding-window limiter once
the Billing rate-limit substrate ships, to enforce the cap per-fleet.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import HTTPException, status


def _now_utc() -> float:
    return datetime.now(timezone.utc).timestamp()


class MarkReadRateLimiter:
    """Sliding-window in-process rate limiter keyed by session_id.

    Args:
        max_requests: Maximum requests allowed within window_seconds.
        window_seconds: Width of the sliding window in seconds.
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}

    def check(
        self,
        session_id: str,
        now: Callable[[], float] | None = None,
    ) -> None:
        """Check rate limit for session_id.

        Args:
            session_id: The session to rate-limit.
            now: Optional callable returning the current timestamp as a float
                 (seconds since epoch). Defaults to utcnow. Injected for tests.

        Raises:
            HTTPException(429): When the per-session limit is exceeded.
        """
        current = (now or _now_utc)()
        cutoff = current - self.window_seconds

        bucket = self._buckets.get(session_id)
        if bucket is None:
            bucket = deque()
            self._buckets[session_id] = bucket

        # Prune timestamps outside the window.
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: {self.max_requests} mark-read "
                    f"requests per {self.window_seconds}s per session"
                ),
                headers={"Retry-After": str(self.window_seconds)},
            )

        bucket.append(current)


# Module-level singleton imported by the router.
mark_read_limiter = MarkReadRateLimiter(max_requests=60, window_seconds=60)
