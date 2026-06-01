"""Unit tests for CategoryUserRateLimiter (CH-35 Task 4).

References: CH-PRD-03 §5.4, §6 (rate limits), §7 AC-POST/DELETE 20/hour/user.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from src.kene_api.chat.category_user_limiter import CategoryUserRateLimiter


def _make_limiter(max_requests: int = 3, window_seconds: int = 3600) -> CategoryUserRateLimiter:
    return CategoryUserRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


class TestCategoryUserRateLimiter:
    def test_single_call_passes(self) -> None:
        limiter = _make_limiter()
        t = 0.0
        limiter.check("user_1", now=lambda: t)

    def test_calls_up_to_limit_all_pass(self) -> None:
        limiter = _make_limiter(max_requests=3)
        t = 0.0
        for _ in range(3):
            limiter.check("user_1", now=lambda: t)

    def test_exceeding_limit_raises_429(self) -> None:
        limiter = _make_limiter(max_requests=3)
        t = 0.0
        for _ in range(3):
            limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert exc_info.value.status_code == 429

    def test_429_has_retry_after_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "3600"

    def test_429_has_x_ratelimit_limit_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert "X-RateLimit-Limit" in exc_info.value.headers
        assert exc_info.value.headers["X-RateLimit-Limit"] == "1"

    def test_429_has_x_ratelimit_remaining_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert "X-RateLimit-Remaining" in exc_info.value.headers
        assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"

    def test_429_has_x_ratelimit_reset_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert "X-RateLimit-Reset" in exc_info.value.headers
        # reset = oldest_timestamp (0.0) + window_seconds (3600) = 3600
        assert exc_info.value.headers["X-RateLimit-Reset"] == "3600"

    def test_all_four_rate_limit_headers_present_on_429(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        headers = exc_info.value.headers
        assert headers is not None
        for h in ("Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            assert h in headers, f"Missing header: {h}"

    def test_clock_advance_past_window_resets_counter(self) -> None:
        limiter = _make_limiter(max_requests=2, window_seconds=3600)
        t = 0.0
        for _ in range(2):
            limiter.check("user_1", now=lambda: t)
        # Advance past the window
        t = 3601.0
        # Should not raise: old timestamps are pruned
        limiter.check("user_1", now=lambda: t)

    def test_distinct_user_ids_are_independent(self) -> None:
        limiter = _make_limiter(max_requests=1)
        t = 0.0
        limiter.check("user_A", now=lambda: t)
        # user_A is at limit, but user_B should still pass
        limiter.check("user_B", now=lambda: t)

    def test_default_now_is_callable(self) -> None:
        """Calling without injected now must not raise (uses real clock)."""
        limiter = _make_limiter()
        limiter.check("user_1")

    def test_twenty_requests_in_window_pass(self) -> None:
        """Default limit: 20 requests/3600s should all pass."""
        limiter = CategoryUserRateLimiter(max_requests=20, window_seconds=3600)
        t = 0.0
        for _ in range(20):
            limiter.check("user_1", now=lambda: t)

    def test_twenty_first_request_fails(self) -> None:
        """21st request in 3600s window should be rejected."""
        limiter = CategoryUserRateLimiter(max_requests=20, window_seconds=3600)
        t = 0.0
        for _ in range(20):
            limiter.check("user_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        assert exc_info.value.status_code == 429

    def test_retry_after_is_time_to_reset_not_full_window(self) -> None:
        """Retry-After must reflect seconds until the window resets, not window_seconds."""
        limiter = _make_limiter(max_requests=1, window_seconds=3600)
        t = 0.0
        limiter.check("user_1", now=lambda: t)
        # Advance halfway through the window; oldest slot resets at t=3600
        t = 1800.0
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user_1", now=lambda: t)
        # reset_at = int(0.0 + 3600) = 3600; Retry-After = 3600 - 1800 = 1800
        assert exc_info.value.headers["Retry-After"] == "1800"

    def test_max_buckets_eviction(self) -> None:
        """When max_buckets is exceeded, the oldest entry is evicted."""
        limiter = CategoryUserRateLimiter(
            max_requests=10, window_seconds=3600, max_buckets=3
        )
        t = 0.0
        for i in range(4):
            limiter.check(f"user_{i}", now=lambda: t)
        # Limiter should still work (oldest evicted)
        assert len(limiter._buckets) <= 3
