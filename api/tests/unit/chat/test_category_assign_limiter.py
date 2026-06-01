"""Unit tests for CategoryAssignRateLimiter (CH-35 Task 4).

References: CH-PRD-03 §5.4, §6 (rate limits), §7 AC-PUT 60/minute/session.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from src.kene_api.chat.category_assign_limiter import CategoryAssignRateLimiter


def _make_limiter(max_requests: int = 3, window_seconds: int = 60) -> CategoryAssignRateLimiter:
    return CategoryAssignRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


class TestCategoryAssignRateLimiter:
    def test_single_call_passes(self) -> None:
        limiter = _make_limiter()
        t = 0.0
        limiter.check("sess_1", now=lambda: t)

    def test_calls_up_to_limit_all_pass(self) -> None:
        limiter = _make_limiter(max_requests=3)
        t = 0.0
        for _ in range(3):
            limiter.check("sess_1", now=lambda: t)

    def test_exceeding_limit_raises_429(self) -> None:
        limiter = _make_limiter(max_requests=3)
        t = 0.0
        for _ in range(3):
            limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert exc_info.value.status_code == 429

    def test_429_has_retry_after_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "60"

    def test_429_has_x_ratelimit_limit_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert "X-RateLimit-Limit" in exc_info.value.headers
        assert exc_info.value.headers["X-RateLimit-Limit"] == "1"

    def test_429_has_x_ratelimit_remaining_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert "X-RateLimit-Remaining" in exc_info.value.headers
        assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"

    def test_429_has_x_ratelimit_reset_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert "X-RateLimit-Reset" in exc_info.value.headers
        # reset = oldest_timestamp (0.0) + window_seconds (60) = 60
        assert exc_info.value.headers["X-RateLimit-Reset"] == "60"

    def test_all_four_rate_limit_headers_present_on_429(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        headers = exc_info.value.headers
        assert headers is not None
        for h in ("Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            assert h in headers, f"Missing header: {h}"

    def test_clock_advance_past_window_resets_counter(self) -> None:
        limiter = _make_limiter(max_requests=2, window_seconds=60)
        t = 0.0
        for _ in range(2):
            limiter.check("sess_1", now=lambda: t)
        # Advance past the window
        t = 61.0
        # Should not raise: old timestamps are pruned
        limiter.check("sess_1", now=lambda: t)

    def test_distinct_session_ids_are_independent(self) -> None:
        limiter = _make_limiter(max_requests=1)
        t = 0.0
        limiter.check("sess_A", now=lambda: t)
        # sess_A is at limit, but sess_B should still pass
        limiter.check("sess_B", now=lambda: t)

    def test_default_now_is_callable(self) -> None:
        """Calling without injected now must not raise (uses real clock)."""
        limiter = _make_limiter()
        limiter.check("sess_1")

    def test_sixty_requests_in_window_pass(self) -> None:
        """Default limit: 60 requests/60s should all pass."""
        limiter = CategoryAssignRateLimiter(max_requests=60, window_seconds=60)
        t = 0.0
        for _ in range(60):
            limiter.check("sess_1", now=lambda: t)

    def test_sixty_first_request_fails(self) -> None:
        """61st request in 60s window should be rejected."""
        limiter = CategoryAssignRateLimiter(max_requests=60, window_seconds=60)
        t = 0.0
        for _ in range(60):
            limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert exc_info.value.status_code == 429

    def test_retry_after_is_time_to_reset_not_full_window(self) -> None:
        """Retry-After must reflect seconds until the window resets, not window_seconds."""
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        # Advance halfway through the window; oldest slot resets at t=60
        t = 30.0
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        # reset_at = int(0.0 + 60) = 60; Retry-After = 60 - 30 = 30
        assert exc_info.value.headers["Retry-After"] == "30"

    def test_max_buckets_eviction(self) -> None:
        """When max_buckets is exceeded, the oldest entry is evicted."""
        limiter = CategoryAssignRateLimiter(
            max_requests=10, window_seconds=60, max_buckets=3
        )
        t = 0.0
        for i in range(4):
            limiter.check(f"sess_{i}", now=lambda: t)
        # Limiter should still work (oldest evicted)
        assert len(limiter._buckets) <= 3
