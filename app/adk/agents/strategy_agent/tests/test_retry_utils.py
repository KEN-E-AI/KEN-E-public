"""Unit tests for retry utilities."""

import time
from unittest.mock import MagicMock, Mock

import pytest
from google.api_core import exceptions as google_exceptions

from ..retry_utils import (
    RETRIABLE_EXCEPTIONS,
    RetryableTransaction,
    RetryConfig,
    retry_on_conflict,
    with_batch_retry,
    with_firestore_retry,
    with_read_retry,
    with_write_retry,
)


class TestRetryConfig:
    """Test RetryConfig functionality."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.retriable_exceptions == RETRIABLE_EXCEPTIONS

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_calculate_delay_exponential(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(1) == 1.0  # 1 * 2^0
        assert config.calculate_delay(2) == 2.0  # 1 * 2^1
        assert config.calculate_delay(3) == 4.0  # 1 * 2^2
        assert config.calculate_delay(4) == 8.0  # 1 * 2^3

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(
            initial_delay=10.0, max_delay=20.0, exponential_base=3.0, jitter=False
        )

        # Should be capped at 20.0
        assert config.calculate_delay(3) == 20.0  # Would be 90.0 without cap

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(initial_delay=1.0, jitter=True)

        # With jitter, delay should be between 0.5x and 1.5x base delay
        delay = config.calculate_delay(1)
        assert 0.5 <= delay <= 1.5


class TestFirestoreRetryDecorator:
    """Test the Firestore retry decorator."""

    def test_successful_operation_no_retry(self):
        """Test successful operation doesn't retry."""
        mock_func = Mock(return_value="success")

        @with_firestore_retry()
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retriable_exception_retries(self):
        """Test retriable exception triggers retry."""
        mock_func = Mock(
            side_effect=[
                google_exceptions.ServiceUnavailable("Service down"),
                "success",
            ]
        )

        @with_firestore_retry(config=RetryConfig(initial_delay=0.01))
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_non_retriable_exception_no_retry(self):
        """Test non-retriable exception doesn't retry."""
        mock_func = Mock(side_effect=google_exceptions.InvalidArgument("Bad request"))

        @with_firestore_retry()
        def operation():
            return mock_func()

        with pytest.raises(google_exceptions.InvalidArgument):
            operation()

        assert mock_func.call_count == 1

    def test_max_attempts_exceeded(self):
        """Test exception raised after max attempts."""
        mock_func = Mock(
            side_effect=google_exceptions.ServiceUnavailable("Service down")
        )

        @with_firestore_retry(config=RetryConfig(max_attempts=3, initial_delay=0.01))
        def operation():
            return mock_func()

        with pytest.raises(google_exceptions.ServiceUnavailable):
            operation()

        assert mock_func.call_count == 3

    def test_retry_callback(self):
        """Test retry callback is called."""
        callback = Mock()
        mock_func = Mock(
            side_effect=[google_exceptions.ServiceUnavailable("Error"), "success"]
        )

        @with_firestore_retry(config=RetryConfig(initial_delay=0.01, on_retry=callback))
        def operation():
            return mock_func()

        result = operation()

        assert result == "success"
        assert callback.call_count == 1

        # Check callback was called with exception and attempt number
        call_args = callback.call_args[0]
        assert isinstance(call_args[0], google_exceptions.ServiceUnavailable)
        assert call_args[1] == 1  # First retry attempt

    def test_operation_name_in_logs(self, caplog):
        """Test operation name appears in logs."""
        import logging

        caplog.set_level(logging.INFO)

        mock_func = Mock(
            side_effect=[google_exceptions.ServiceUnavailable("Error"), "success"]
        )

        @with_firestore_retry(
            config=RetryConfig(initial_delay=0.01), operation_name="test_operation"
        )
        def operation():
            return mock_func()

        result = operation()

        assert "test_operation" in caplog.text
        # Check that retry message was logged
        assert (
            "test_operation failed on attempt 1" in caplog.text
            or "test_operation succeeded on attempt 2" in caplog.text
        )


class TestSpecializedRetryDecorators:
    """Test specialized retry decorators."""

    def test_read_retry_config(self):
        """Test read retry uses optimized config."""
        mock_func = Mock(
            side_effect=[google_exceptions.ServiceUnavailable("Error"), "success"]
        )

        @with_read_retry()
        def read_operation():
            return mock_func()

        result = read_operation()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_write_retry_config(self):
        """Test write retry uses optimized config."""
        mock_func = Mock(
            side_effect=[google_exceptions.ServiceUnavailable("Error"), "success"]
        )

        @with_write_retry()
        def write_operation():
            return mock_func()

        result = write_operation()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_batch_retry_config(self):
        """Test batch retry uses optimized config."""
        mock_func = Mock(
            side_effect=[google_exceptions.ServiceUnavailable("Error"), "success"]
        )

        @with_batch_retry()
        def batch_operation():
            return mock_func()

        result = batch_operation()

        assert result == "success"
        assert mock_func.call_count == 2


class TestRetryableTransaction:
    """Test RetryableTransaction context manager."""

    def test_successful_transaction(self):
        """Test successful transaction commits."""
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        with RetryableTransaction(mock_db) as transaction:
            assert transaction == mock_transaction

        mock_transaction.commit.assert_called_once()

    def test_transaction_with_exception_rollback(self):
        """Test transaction with exception doesn't commit."""
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        with pytest.raises(ValueError):
            with RetryableTransaction(mock_db) as transaction:
                raise ValueError("Test error")

        mock_transaction.commit.assert_not_called()

    def test_transaction_commit_retry(self):
        """Test transaction commit retries on failure."""
        mock_db = MagicMock()
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        # Fail once, then succeed
        mock_transaction.commit.side_effect = [
            google_exceptions.ServiceUnavailable("Error"),
            None,
        ]

        with RetryableTransaction(
            mock_db, config=RetryConfig(initial_delay=0.01)
        ) as transaction:
            pass

        assert mock_transaction.commit.call_count == 2


class TestRetryOnConflict:
    """Test retry_on_conflict function."""

    def test_retry_on_conflict_success(self):
        """Test retry on conflict succeeds after retry."""
        counter = {"value": 0}

        def conflicting_operation():
            counter["value"] += 1
            if counter["value"] == 1:
                raise google_exceptions.Aborted("Conflict")
            return "success"

        result = retry_on_conflict(conflicting_operation, max_attempts=3)

        assert result == "success"
        assert counter["value"] == 2

    def test_retry_on_conflict_max_attempts(self):
        """Test retry on conflict respects max attempts."""

        def always_conflicts():
            raise google_exceptions.Aborted("Conflict")

        with pytest.raises(google_exceptions.Aborted):
            retry_on_conflict(always_conflicts, max_attempts=2)


class TestIntegrationWithFirestore:
    """Integration tests with actual Firestore operations."""

    @pytest.mark.skip(reason="Integration tests require Firestore setup")
    def test_real_firestore_retry(self):
        """Test retry with real Firestore operations."""
        # This would test against actual Firestore
        # Skipped by default to avoid external dependencies
        pass


class TestExponentialBackoffTiming:
    """Test timing of exponential backoff."""

    def test_retry_timing(self):
        """Test that retries respect delay timing."""
        mock_func = Mock(
            side_effect=[
                google_exceptions.ServiceUnavailable("Error"),
                google_exceptions.ServiceUnavailable("Error"),
                "success",
            ]
        )

        @with_firestore_retry(
            config=RetryConfig(initial_delay=0.1, exponential_base=2.0, jitter=False)
        )
        def operation():
            return mock_func()

        start_time = time.time()
        result = operation()
        elapsed = time.time() - start_time

        assert result == "success"
        assert mock_func.call_count == 3

        # Should have delays of 0.1 + 0.2 = 0.3 seconds minimum
        assert elapsed >= 0.3
        # But not too long (with some margin for execution time)
        assert elapsed < 0.5
