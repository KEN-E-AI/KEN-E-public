"""Retry utilities for robust Firestore operations.

This module provides decorators and utilities for implementing retry logic
with exponential backoff for Firestore operations.
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

from google.api_core import exceptions as google_exceptions
from google.cloud import firestore

logger = logging.getLogger(__name__)


# Exceptions that should trigger a retry
RETRIABLE_EXCEPTIONS = (
    google_exceptions.Aborted,
    google_exceptions.DeadlineExceeded,
    google_exceptions.InternalServerError,
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
    google_exceptions.Unknown,
    ConnectionError,
    TimeoutError,
)

# Exceptions that should NOT trigger a retry (client errors)
NON_RETRIABLE_EXCEPTIONS = (
    google_exceptions.InvalidArgument,
    google_exceptions.NotFound,
    google_exceptions.AlreadyExists,
    google_exceptions.PermissionDenied,
    google_exceptions.Unauthenticated,
    google_exceptions.FailedPrecondition,
    google_exceptions.OutOfRange,
    google_exceptions.DataLoss,
    google_exceptions.Cancelled,
)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retriable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
        on_retry: Optional[Callable[[Exception, int], None]] = None
    ):
        """Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retriable_exceptions: Tuple of exceptions to retry on
            on_retry: Optional callback called on each retry with (exception, attempt_number)
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retriable_exceptions = retriable_exceptions or RETRIABLE_EXCEPTIONS
        self.on_retry = on_retry
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = min(
            self.initial_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            delay *= (0.5 + random.random())
        
        return delay


# Default configurations for different operation types
DEFAULT_CONFIG = RetryConfig()
READ_CONFIG = RetryConfig(max_attempts=5, initial_delay=0.5)
WRITE_CONFIG = RetryConfig(max_attempts=3, initial_delay=1.0)
BATCH_CONFIG = RetryConfig(max_attempts=3, initial_delay=2.0, max_delay=120.0)


def with_firestore_retry(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
) -> Callable:
    """Decorator to add retry logic to Firestore operations.
    
    Args:
        config: Retry configuration (uses DEFAULT_CONFIG if None)
        operation_name: Optional name for logging
        
    Returns:
        Decorated function with retry logic
        
    Example:
        ```python
        @with_firestore_retry(config=WRITE_CONFIG, operation_name="save_metrics")
        def save_metrics(self, metrics):
            self.db.collection("metrics").add(metrics)
        ```
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            op_name = operation_name or func.__name__
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    # Attempt the operation
                    result = func(*args, **kwargs)
                    
                    # Success - log if this was a retry
                    if attempt > 1:
                        logger.info(
                            f"[RETRY] {op_name} succeeded on attempt {attempt}/{config.max_attempts}"
                        )
                    
                    return result
                    
                except config.retriable_exceptions as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"[RETRY] {op_name} failed after {config.max_attempts} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    # Log retry attempt
                    logger.warning(
                        f"[RETRY] {op_name} failed on attempt {attempt}/{config.max_attempts} "
                        f"with {type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    
                    # Call retry callback if provided
                    if config.on_retry:
                        config.on_retry(e, attempt)
                    
                    # Wait before retrying
                    time.sleep(delay)
                    
                except NON_RETRIABLE_EXCEPTIONS as e:
                    # Don't retry client errors
                    logger.error(
                        f"[RETRY] {op_name} failed with non-retriable error: {type(e).__name__}: {e}"
                    )
                    raise
                    
                except Exception as e:
                    # Unexpected error - log and raise
                    logger.error(
                        f"[RETRY] {op_name} failed with unexpected error: {type(e).__name__}: {e}"
                    )
                    raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def with_read_retry(operation_name: Optional[str] = None) -> Callable:
    """Decorator specifically for read operations with optimized retry config.
    
    Args:
        operation_name: Optional name for logging
        
    Returns:
        Decorated function with read-optimized retry logic
    """
    return with_firestore_retry(config=READ_CONFIG, operation_name=operation_name)


def with_write_retry(operation_name: Optional[str] = None) -> Callable:
    """Decorator specifically for write operations with optimized retry config.
    
    Args:
        operation_name: Optional name for logging
        
    Returns:
        Decorated function with write-optimized retry logic
    """
    return with_firestore_retry(config=WRITE_CONFIG, operation_name=operation_name)


def with_batch_retry(operation_name: Optional[str] = None) -> Callable:
    """Decorator specifically for batch operations with optimized retry config.
    
    Args:
        operation_name: Optional name for logging
        
    Returns:
        Decorated function with batch-optimized retry logic
    """
    return with_firestore_retry(config=BATCH_CONFIG, operation_name=operation_name)


class RetryableTransaction:
    """Context manager for retryable Firestore transactions.
    
    Example:
        ```python
        with RetryableTransaction(db, config=WRITE_CONFIG) as transaction:
            doc_ref = db.collection("users").document("user123")
            user_data = doc_ref.get(transaction=transaction).to_dict()
            user_data["login_count"] += 1
            transaction.update(doc_ref, user_data)
        ```
    """
    
    def __init__(
        self,
        db: firestore.Client,
        config: Optional[RetryConfig] = None,
        operation_name: str = "transaction"
    ):
        """Initialize retryable transaction.
        
        Args:
            db: Firestore client
            config: Retry configuration
            operation_name: Name for logging
        """
        self.db = db
        self.config = config or DEFAULT_CONFIG
        self.operation_name = operation_name
        self.transaction = None
    
    def __enter__(self) -> firestore.Transaction:
        """Enter transaction context."""
        self.transaction = self.db.transaction()
        return self.transaction
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context with retry logic."""
        if exc_type is None:
            # No exception - commit transaction with retry
            self._commit_with_retry()
        else:
            # Exception occurred - determine if we should retry
            if isinstance(exc_val, self.config.retriable_exceptions):
                logger.warning(
                    f"[RETRY] Transaction {self.operation_name} failed with retriable error: {exc_val}"
                )
                # Return False to propagate exception for outer retry logic
                return False
            else:
                # Non-retriable error
                logger.error(
                    f"[RETRY] Transaction {self.operation_name} failed with non-retriable error: {exc_val}"
                )
                return False
    
    def _commit_with_retry(self):
        """Commit transaction with retry logic."""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.transaction.commit()
                
                if attempt > 1:
                    logger.info(
                        f"[RETRY] Transaction {self.operation_name} committed on attempt {attempt}"
                    )
                return
                
            except self.config.retriable_exceptions as e:
                last_exception = e
                
                if attempt >= self.config.max_attempts:
                    logger.error(
                        f"[RETRY] Transaction {self.operation_name} commit failed after "
                        f"{self.config.max_attempts} attempts: {e}"
                    )
                    raise
                
                delay = self.config.calculate_delay(attempt)
                logger.warning(
                    f"[RETRY] Transaction {self.operation_name} commit failed on attempt "
                    f"{attempt}/{self.config.max_attempts}. Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
        
        if last_exception:
            raise last_exception


def retry_on_conflict(
    func: Callable,
    max_attempts: int = 3,
    operation_name: Optional[str] = None
) -> Any:
    """Execute a function with retry on Firestore conflict errors.
    
    Useful for operations that may conflict due to concurrent updates.
    
    Args:
        func: Function to execute
        max_attempts: Maximum retry attempts
        operation_name: Optional name for logging
        
    Returns:
        Function result
        
    Example:
        ```python
        def increment_counter(doc_ref):
            doc = doc_ref.get()
            doc_ref.update({"count": doc.get("count") + 1})
        
        retry_on_conflict(lambda: increment_counter(doc_ref))
        ```
    """
    op_name = operation_name or getattr(func, "__name__", "operation")
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=0.1,  # Quick retry for conflicts
        retriable_exceptions=(google_exceptions.Aborted, google_exceptions.FailedPrecondition)
    )
    
    wrapped = with_firestore_retry(config=config, operation_name=op_name)(func)
    return wrapped()