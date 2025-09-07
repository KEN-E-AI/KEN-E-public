"""
Retry utilities for agent invocations with exponential backoff.
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, TypeVar, Union

from pydantic import ValidationError

logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar("T")

# Common exceptions that should trigger a retry
RETRIABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    ValidationError,  # Pydantic validation errors
    ValueError,  # JSON parsing errors
)


def retry_with_exponential_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that adds retry logic with exponential backoff to a function.

    Args:
        max_attempts: Maximum number of retry attempts (including initial attempt)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to prevent thundering herd

    Returns:
        Decorated function with retry logic

    Example:
        ```python
        @retry_with_exponential_backoff(max_attempts=3)
        def invoke_agent(agent, query):
            return agent.invoke(query)
        ```
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    # Attempt the operation
                    result = func(*args, **kwargs)

                    # Success - log if this was a retry
                    if attempt > 1:
                        logger.info(
                            f"[RETRY] {func.__name__} succeeded on attempt {attempt}/{max_attempts}"
                        )

                    return result

                except RETRIABLE_EXCEPTIONS as e:
                    last_exception = e

                    # Check if we should retry
                    if attempt >= max_attempts:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** (attempt - 1)), max_delay
                    )

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        f"[RETRY] {func.__name__} failed on attempt {attempt}/{max_attempts} "
                        f"with {type(e).__name__}: {str(e)[:100]}. Retrying in {delay:.1f}s..."
                    )

                    # Wait before retrying
                    time.sleep(delay)

                except Exception as e:
                    # Non-retriable error - log and raise immediately
                    logger.error(
                        f"[RETRY] {func.__name__} failed with non-retriable error: "
                        f"{type(e).__name__}: {e}"
                    )
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def invoke_agent_with_retry(
    agent: Any,
    query: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    max_attempts: int = 3,
) -> str:
    """
    Invoke an agent with automatic retry on failure.

    This is a convenience function that wraps invoke_agent_sync with retry logic.

    Args:
        agent: The agent to invoke
        query: The query to send to the agent
        user_id: Optional user ID for context
        session_id: Optional session ID for context
        max_attempts: Maximum number of retry attempts

    Returns:
        The agent's response

    Raises:
        Exception: If all retry attempts fail
    """
    from .supervisor_utils import invoke_agent_sync

    @retry_with_exponential_backoff(max_attempts=max_attempts)
    def _invoke() -> str:
        return invoke_agent_sync(agent, query, user_id, session_id)

    return _invoke()


class AgentRetryConfig:
    """Configuration for agent retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_validation_error: bool = True,
        retry_on_timeout: bool = True,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retry_on_validation_error: Whether to retry on Pydantic validation errors
            retry_on_timeout: Whether to retry on timeout errors
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_validation_error = retry_on_validation_error
        self.retry_on_timeout = retry_on_timeout

    def get_decorator(self) -> Callable:
        """Get a configured retry decorator."""
        return retry_with_exponential_backoff(
            max_attempts=self.max_attempts,
            initial_delay=self.initial_delay,
            max_delay=self.max_delay,
            exponential_base=self.exponential_base,
            jitter=self.jitter,
        )


# Default configurations for different agent types
DEFAULT_RETRY_CONFIG = AgentRetryConfig()
FAST_RETRY_CONFIG = AgentRetryConfig(max_attempts=2, initial_delay=0.5, max_delay=5.0)
ROBUST_RETRY_CONFIG = AgentRetryConfig(
    max_attempts=5, initial_delay=2.0, max_delay=60.0
)
