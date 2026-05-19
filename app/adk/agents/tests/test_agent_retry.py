"""Tests for agent retry utilities."""

import pytest
from pydantic import BaseModel, ValidationError

from ..utils.agent_retry import (
    RETRIABLE_EXCEPTIONS,
    retry_with_exponential_backoff,
)


class _DummyModel(BaseModel):
    x: int


class TestRetriableExceptions:
    """Verify which exceptions are retried."""

    def test_connection_error_is_retriable(self):
        assert ConnectionError in RETRIABLE_EXCEPTIONS

    def test_timeout_error_is_retriable(self):
        assert TimeoutError in RETRIABLE_EXCEPTIONS

    def test_os_error_is_retriable(self):
        assert OSError in RETRIABLE_EXCEPTIONS

    def test_validation_error_is_not_retriable(self):
        assert ValidationError not in RETRIABLE_EXCEPTIONS

    def test_value_error_is_not_retriable(self):
        assert ValueError not in RETRIABLE_EXCEPTIONS


class TestRetryWithExponentialBackoff:
    """Test the retry decorator behavior."""

    def test_connection_error_retried_up_to_max_attempts(self):
        call_count = 0

        @retry_with_exponential_backoff(
            max_attempts=3, initial_delay=0.01, jitter=False
        )
        def failing_fn():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("connection refused")

        with pytest.raises(ConnectionError, match="connection refused"):
            failing_fn()

        assert call_count == 3

    def test_validation_error_not_retried(self):
        call_count = 0

        @retry_with_exponential_backoff(max_attempts=3, initial_delay=0.01)
        def failing_fn():
            nonlocal call_count
            call_count += 1
            _DummyModel(x="not_an_int")  # type: ignore[arg-type]

        with pytest.raises(ValidationError):
            failing_fn()

        assert call_count == 1

    def test_value_error_not_retried(self):
        call_count = 0

        @retry_with_exponential_backoff(max_attempts=3, initial_delay=0.01)
        def failing_fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad value")

        with pytest.raises(ValueError, match="bad value"):
            failing_fn()

        assert call_count == 1

    def test_success_on_second_attempt(self):
        call_count = 0

        @retry_with_exponential_backoff(
            max_attempts=3, initial_delay=0.01, jitter=False
        )
        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temporary failure")
            return "success"

        result = flaky_fn()

        assert result == "success"
        assert call_count == 2

    def test_max_attempts_respected(self):
        call_count = 0

        @retry_with_exponential_backoff(
            max_attempts=2, initial_delay=0.01, jitter=False
        )
        def failing_fn():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timed out")

        with pytest.raises(TimeoutError, match="timed out"):
            failing_fn()

        assert call_count == 2

    def test_immediate_success_no_retry(self):
        call_count = 0

        @retry_with_exponential_backoff(max_attempts=3)
        def success_fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = success_fn()

        assert result == "ok"
        assert call_count == 1
