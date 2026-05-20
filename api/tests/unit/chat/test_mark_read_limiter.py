"""Unit tests for MarkReadRateLimiter (CH-PRD-02 §5.2 Task 2)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.kene_api.chat.mark_read_limiter import MarkReadRateLimiter


def _make_limiter(max_requests: int = 3, window_seconds: int = 60) -> MarkReadRateLimiter:
    return MarkReadRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


class TestMarkReadRateLimiter:
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

    def test_429_response_has_retry_after_header(self) -> None:
        limiter = _make_limiter(max_requests=1, window_seconds=60)
        t = 0.0
        limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers

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
        limiter = MarkReadRateLimiter(max_requests=60, window_seconds=60)
        t = 0.0
        for _ in range(60):
            limiter.check("sess_1", now=lambda: t)

    def test_sixty_first_request_fails(self) -> None:
        """61st request in 60s window should be rejected."""
        limiter = MarkReadRateLimiter(max_requests=60, window_seconds=60)
        t = 0.0
        for _ in range(60):
            limiter.check("sess_1", now=lambda: t)
        with pytest.raises(HTTPException) as exc_info:
            limiter.check("sess_1", now=lambda: t)
        assert exc_info.value.status_code == 429
