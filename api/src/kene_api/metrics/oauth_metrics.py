"""
OAuth metrics collection using Prometheus client.

This module provides comprehensive metrics tracking for OAuth integration health,
including authentication attempts, token refreshes, and performance monitoring.
"""

import time
from functools import wraps
from typing import Any, Callable, Optional

from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Authentication Metrics
oauth_auth_attempts = Counter(
    'oauth_auth_attempts_total',
    'Total OAuth authorization attempts',
    ['integration_type']
)

oauth_auth_success = Counter(
    'oauth_auth_success_total',
    'Successful OAuth authorizations',
    ['integration_type']
)

oauth_callback_errors = Counter(
    'oauth_callback_errors_total',
    'OAuth callback errors',
    ['integration_type', 'error_type']
)

token_refresh_success = Counter(
    'token_refresh_success_total',
    'Successful token refreshes',
    ['integration_type']
)

token_refresh_failures = Counter(
    'token_refresh_failures_total',
    'Failed token refreshes',
    ['integration_type', 'error_reason']
)

# Performance Metrics
oauth_flow_duration = Histogram(
    'oauth_flow_duration_seconds',
    'Time to complete OAuth flow',
    ['integration_type'],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0)
)

encryption_operation_duration = Histogram(
    'encryption_duration_seconds',
    'Time to encrypt/decrypt credentials',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0)
)

# State Metrics
active_oauth_sessions = Gauge(
    'active_oauth_sessions',
    'Number of active OAuth sessions',
    ['integration_type']
)

oauth_state_transitions = Counter(
    'oauth_state_transitions_total',
    'OAuth state transitions',
    ['integration_type', 'from_state', 'to_state']
)

# Token Expiration Metrics
tokens_expiring_soon = Gauge(
    'tokens_expiring_soon',
    'Number of tokens expiring within 1 hour',
    ['integration_type']
)

expired_tokens = Counter(
    'expired_tokens_total',
    'Total number of expired tokens detected',
    ['integration_type']
)


def track_oauth_attempt(integration_type: str) -> None:
    """Track an OAuth authorization attempt."""
    oauth_auth_attempts.labels(integration_type=integration_type).inc()


def track_oauth_success(integration_type: str) -> None:
    """Track a successful OAuth authorization."""
    oauth_auth_success.labels(integration_type=integration_type).inc()


def track_oauth_callback_error(integration_type: str, error_type: str) -> None:
    """Track an OAuth callback error."""
    oauth_callback_errors.labels(
        integration_type=integration_type,
        error_type=error_type
    ).inc()


def track_token_refresh_success(integration_type: str) -> None:
    """Track a successful token refresh."""
    token_refresh_success.labels(integration_type=integration_type).inc()


def track_token_refresh_failure(integration_type: str, error_reason: str) -> None:
    """Track a failed token refresh."""
    token_refresh_failures.labels(
        integration_type=integration_type,
        error_reason=error_reason
    ).inc()


def track_state_transition(
    integration_type: str,
    from_state: str,
    to_state: str
) -> None:
    """Track an OAuth state transition."""
    oauth_state_transitions.labels(
        integration_type=integration_type,
        from_state=from_state,
        to_state=to_state
    ).inc()


def update_active_sessions(integration_type: str, count: int) -> None:
    """Update the count of active OAuth sessions."""
    active_oauth_sessions.labels(integration_type=integration_type).set(count)


def update_expiring_tokens(integration_type: str, count: int) -> None:
    """Update the count of tokens expiring soon."""
    tokens_expiring_soon.labels(integration_type=integration_type).set(count)


def track_expired_token(integration_type: str) -> None:
    """Track detection of an expired token."""
    expired_tokens.labels(integration_type=integration_type).inc()


def measure_oauth_flow(integration_type: str) -> Callable:
    """
    Decorator to measure OAuth flow duration.
    
    Usage:
        @measure_oauth_flow("google_analytics")
        async def authorize_google_analytics(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                oauth_flow_duration.labels(
                    integration_type=integration_type
                ).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                oauth_flow_duration.labels(
                    integration_type=integration_type
                ).observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def measure_encryption_operation(operation: str) -> Callable:
    """
    Decorator to measure encryption/decryption operation duration.
    
    Usage:
        @measure_encryption_operation("encrypt")
        def encrypt_credentials(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                encryption_operation_duration.labels(
                    operation=operation
                ).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                encryption_operation_duration.labels(
                    operation=operation
                ).observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def get_metrics() -> bytes:
    """
    Generate metrics in Prometheus format.
    
    Returns:
        Prometheus formatted metrics as bytes.
    """
    return generate_latest()


class OAuthMetricsCollector:
    """
    Context manager for tracking OAuth flow metrics.
    
    Usage:
        async with OAuthMetricsCollector("google_analytics") as collector:
            # OAuth flow logic
            collector.track_success()
    """
    
    def __init__(self, integration_type: str):
        self.integration_type = integration_type
        self.start_time: Optional[float] = None
        self.success = False
        self.error_type: Optional[str] = None
    
    def __enter__(self):
        self.start_time = time.time()
        track_oauth_attempt(self.integration_type)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            oauth_flow_duration.labels(
                integration_type=self.integration_type
            ).observe(duration)
        
        if self.success:
            track_oauth_success(self.integration_type)
        elif exc_type:
            error_type = self.error_type or exc_type.__name__
            track_oauth_callback_error(self.integration_type, error_type)
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)
    
    def track_success(self):
        """Mark the OAuth flow as successful."""
        self.success = True
    
    def track_error(self, error_type: str):
        """Track a specific error type."""
        self.error_type = error_type
        self.success = False


# Alert thresholds (for reference in monitoring setup)
ALERT_THRESHOLDS = {
    "oauth_success_rate_threshold": 0.95,  # Alert if success rate < 95%
    "token_refresh_failure_rate_threshold": 0.10,  # Alert if failure rate > 10%
    "encryption_operation_p99_threshold": 0.1,  # Alert if p99 > 100ms
    "oauth_flow_p99_threshold": 30.0,  # Alert if p99 > 30s
    "tokens_expiring_soon_threshold": 100,  # Alert if > 100 tokens expiring
}