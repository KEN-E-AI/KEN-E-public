"""Unit tests for OAuth metrics module."""

import pytest


def test_oauth_metrics_can_be_imported():
    """Test that oauth_metrics module can be imported without errors.

    This test addresses the issue where pytest's test collection imports modules
    causing Prometheus metric registration errors.
    """
    # Import the module normally
    from src.kene_api.metrics import oauth_metrics

    # Verify metrics are created
    assert oauth_metrics.oauth_auth_attempts is not None
    assert oauth_metrics.oauth_auth_success is not None
    assert oauth_metrics.encryption_operation_duration is not None


def test_metrics_prevents_duplicate_registration():
    """Test that the helper functions prevent duplicate registration."""
    from src.kene_api.metrics.oauth_metrics import _get_or_create_counter

    # Get a metric
    counter1 = _get_or_create_counter(
        'test_counter_unique_name_xyz',
        'Test counter',
        ['label1']
    )

    # Get the same metric again
    counter2 = _get_or_create_counter(
        'test_counter_unique_name_xyz',
        'Test counter',
        ['label1']
    )

    # Should return the exact same object from Prometheus registry
    assert counter1 is counter2


def test_all_oauth_metrics_are_defined():
    """Test that all expected OAuth metrics are defined."""
    from src.kene_api.metrics import oauth_metrics

    # Authentication metrics
    assert hasattr(oauth_metrics, 'oauth_auth_attempts')
    assert hasattr(oauth_metrics, 'oauth_auth_success')
    assert hasattr(oauth_metrics, 'oauth_callback_errors')
    assert hasattr(oauth_metrics, 'token_refresh_success')
    assert hasattr(oauth_metrics, 'token_refresh_failures')

    # Performance metrics
    assert hasattr(oauth_metrics, 'oauth_flow_duration')
    assert hasattr(oauth_metrics, 'encryption_operation_duration')

    # State metrics
    assert hasattr(oauth_metrics, 'active_oauth_sessions')
    assert hasattr(oauth_metrics, 'oauth_state_transitions')

    # Token expiration metrics
    assert hasattr(oauth_metrics, 'tokens_expiring_soon')
    assert hasattr(oauth_metrics, 'expired_tokens')
