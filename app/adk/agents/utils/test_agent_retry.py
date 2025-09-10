"""
Tests for agent retry utilities.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from .agent_retry import (
    FAST_RETRY_CONFIG,
    ROBUST_RETRY_CONFIG,
    AgentRetryConfig,
    invoke_agent_with_retry,
    retry_with_exponential_backoff,
)


class TestRetryWithExponentialBackoff:
    """Test the retry decorator."""

    def test_successful_on_first_attempt(self):
        """Test that successful calls don't retry."""
        mock_func = MagicMock(return_value="success")

        @retry_with_exponential_backoff(max_attempts=3)
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_connection_error(self):
        """Test retry on ConnectionError."""
        mock_func = MagicMock(
            side_effect=[ConnectionError("Connection failed"), "success"]
        )

        @retry_with_exponential_backoff(max_attempts=3, initial_delay=0.1, jitter=False)
        def test_func():
            return mock_func()

        start = time.time()
        result = test_func()
        elapsed = time.time() - start

        assert result == "success"
        assert mock_func.call_count == 2
        # Should have delayed ~0.1 seconds
        assert 0.05 < elapsed < 0.2

    def test_retry_on_validation_error(self):
        """Test retry on Pydantic ValidationError."""
        mock_func = MagicMock(
            side_effect=[
                ValidationError.from_exception_data("test", []),
                ValidationError.from_exception_data("test", []),
                "success",
            ]
        )

        @retry_with_exponential_backoff(
            max_attempts=3, initial_delay=0.05, jitter=False
        )
        def test_func():
            return mock_func()

        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_attempts_exceeded(self):
        """Test that it gives up after max attempts."""
        mock_func = MagicMock(side_effect=TimeoutError("Timeout"))

        @retry_with_exponential_backoff(
            max_attempts=2, initial_delay=0.01, jitter=False
        )
        def test_func():
            return mock_func()

        with pytest.raises(TimeoutError):
            test_func()

        assert mock_func.call_count == 2

    def test_non_retriable_exception(self):
        """Test that non-retriable exceptions aren't retried."""
        mock_func = MagicMock(side_effect=KeyError("Not found"))

        @retry_with_exponential_backoff(max_attempts=3)
        def test_func():
            return mock_func()

        with pytest.raises(KeyError):
            test_func()

        # Should not retry on KeyError
        assert mock_func.call_count == 1

    def test_exponential_backoff_calculation(self):
        """Test that delays increase exponentially."""
        delays = []

        def capture_delay(original_sleep):
            def wrapped(delay):
                delays.append(delay)
                # Don't actually sleep in tests
                return None

            return wrapped

        mock_func = MagicMock(
            side_effect=[
                ConnectionError("Fail 1"),
                ConnectionError("Fail 2"),
                ConnectionError("Fail 3"),
                "success",
            ]
        )

        with patch("time.sleep", side_effect=capture_delay(time.sleep)):

            @retry_with_exponential_backoff(
                max_attempts=4,
                initial_delay=1.0,
                exponential_base=2.0,
                jitter=False,
            )
            def test_func():
                return mock_func()

            result = test_func()

        assert result == "success"
        assert len(delays) == 3
        # Should be 1, 2, 4 seconds (exponential with base 2)
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    def test_max_delay_limit(self):
        """Test that delays are capped at max_delay."""
        delays = []

        def capture_delay(original_sleep):
            def wrapped(delay):
                delays.append(delay)
                return None

            return wrapped

        mock_func = MagicMock(
            side_effect=[
                ConnectionError("Fail 1"),
                ConnectionError("Fail 2"),
                "success",
            ]
        )

        with patch("time.sleep", side_effect=capture_delay(time.sleep)):

            @retry_with_exponential_backoff(
                max_attempts=3,
                initial_delay=10.0,
                max_delay=15.0,
                exponential_base=2.0,
                jitter=False,
            )
            def test_func():
                return mock_func()

            result = test_func()

        assert result == "success"
        assert len(delays) == 2
        assert delays[0] == 10.0
        # Should be capped at max_delay of 15
        assert delays[1] == 15.0  # Would be 20 without cap

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays."""
        delays = []

        def capture_delay(original_sleep):
            def wrapped(delay):
                delays.append(delay)
                return None

            return wrapped

        mock_func = MagicMock(side_effect=[ConnectionError("Fail"), "success"])

        with patch("time.sleep", side_effect=capture_delay(time.sleep)):

            @retry_with_exponential_backoff(
                max_attempts=2,
                initial_delay=1.0,
                jitter=True,
            )
            def test_func():
                return mock_func()

            result = test_func()

        assert result == "success"
        assert len(delays) == 1
        # With jitter, delay should be between 0.5 and 1.5
        assert 0.5 <= delays[0] <= 1.5


class TestInvokeAgentWithRetry:
    """Test the invoke_agent_with_retry function."""

    @patch("agents.utils.supervisor_utils.invoke_agent_sync")
    def test_successful_invocation(self, mock_invoke):
        """Test successful agent invocation."""
        mock_agent = MagicMock()
        mock_invoke.return_value = "Agent response"

        result = invoke_agent_with_retry(mock_agent, "test query", max_attempts=3)

        assert result == "Agent response"
        mock_invoke.assert_called_once_with(mock_agent, "test query", None, None)

    @patch("agents.utils.supervisor_utils.invoke_agent_sync")
    @patch("time.sleep")
    def test_retry_on_failure(self, mock_sleep, mock_invoke):
        """Test retry on agent invocation failure."""
        mock_agent = MagicMock()
        mock_invoke.side_effect = [
            ConnectionError("Connection failed"),
            "Agent response",
        ]

        result = invoke_agent_with_retry(mock_agent, "test query", max_attempts=3)

        assert result == "Agent response"
        assert mock_invoke.call_count == 2
        mock_sleep.assert_called_once()

    @patch("agents.utils.supervisor_utils.invoke_agent_sync")
    def test_passes_optional_parameters(self, mock_invoke):
        """Test that optional parameters are passed through."""
        mock_agent = MagicMock()
        mock_invoke.return_value = "Agent response"

        result = invoke_agent_with_retry(
            mock_agent,
            "test query",
            user_id="user123",
            session_id="session456",
            max_attempts=2,
        )

        assert result == "Agent response"
        mock_invoke.assert_called_once_with(
            mock_agent, "test query", "user123", "session456"
        )


class TestAgentRetryConfig:
    """Test the AgentRetryConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AgentRetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.retry_on_validation_error is True
        assert config.retry_on_timeout is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AgentRetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=10.0,
            exponential_base=3.0,
            jitter=False,
            retry_on_validation_error=False,
            retry_on_timeout=False,
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
        assert config.retry_on_validation_error is False
        assert config.retry_on_timeout is False

    def test_get_decorator(self):
        """Test that get_decorator returns a configured decorator."""
        config = AgentRetryConfig(max_attempts=2, initial_delay=0.01)
        decorator = config.get_decorator()

        mock_func = MagicMock(side_effect=[ConnectionError("Fail"), "success"])

        @decorator
        def test_func():
            return mock_func()

        with patch("time.sleep"):  # Don't actually sleep in tests
            result = test_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_predefined_configs(self):
        """Test predefined configuration constants."""
        # Fast config for quick retries
        assert FAST_RETRY_CONFIG.max_attempts == 2
        assert FAST_RETRY_CONFIG.initial_delay == 0.5
        assert FAST_RETRY_CONFIG.max_delay == 5.0

        # Robust config for critical operations
        assert ROBUST_RETRY_CONFIG.max_attempts == 5
        assert ROBUST_RETRY_CONFIG.initial_delay == 2.0
        assert ROBUST_RETRY_CONFIG.max_delay == 60.0
