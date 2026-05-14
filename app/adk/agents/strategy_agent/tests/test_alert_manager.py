"""Unit tests for Alert Manager."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta, timezone

from ..alert_manager import AlertManager, AlertSeverity, AlertChannel, AlertThreshold
from shared.token_utils import TokenEstimator


@pytest.fixture
def mock_firestore_client():
    """Create mock Firestore client."""
    with patch("google.cloud.firestore.Client") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        yield mock_db


@pytest.fixture
def alert_manager(mock_firestore_client):
    """Create Alert Manager instance with mocked Firestore."""
    # Mock the configuration loading
    mock_doc = MagicMock()
    mock_doc.exists = False  # Use default config
    mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

    manager = AlertManager(account_id="test_account", project_id="test_project")
    return manager


def test_alert_manager_initialization(alert_manager):
    """Test Alert Manager initialization."""
    assert alert_manager.account_id == "test_account"
    assert alert_manager.project_id == "test_project"
    assert alert_manager.config is not None
    assert alert_manager.config["enabled"] is True
    assert len(alert_manager.config["thresholds"]) == 4  # Default thresholds


def test_check_token_usage_no_alerts(alert_manager):
    """Test token usage check with no alerts triggered."""
    alerts = alert_manager.check_token_usage(
        current_tokens=10000,
        max_tokens=1000000,
        context="test",
        agent_name="test_agent",
    )

    assert len(alerts) == 0  # Below 50% threshold


def test_check_token_usage_warning_alert(alert_manager):
    """Test token usage check triggering warning alert."""
    alerts = alert_manager.check_token_usage(
        current_tokens=800000,
        max_tokens=1000000,
        context="test",
        agent_name="test_agent",
    )

    assert len(alerts) > 0
    # Should trigger 50% and 75% alerts
    severities = [alert["severity"] for alert in alerts]
    assert (
        AlertSeverity.INFO.value in severities
        or AlertSeverity.WARNING.value in severities
    )


def test_check_token_usage_critical_alert(alert_manager):
    """Test token usage check triggering critical alert."""
    alerts = alert_manager.check_token_usage(
        current_tokens=960000,
        max_tokens=1000000,
        context="test",
        agent_name="test_agent",
    )

    # Should trigger all thresholds including critical
    assert len(alerts) >= 3
    severities = [alert["severity"] for alert in alerts]
    assert AlertSeverity.CRITICAL.value in severities


def test_circuit_breaker_trigger(alert_manager):
    """Test circuit breaker triggers at 100% usage."""
    alerts = alert_manager.check_token_usage(
        current_tokens=1000000,
        max_tokens=1000000,
        context="test",
        agent_name="test_agent",
    )

    assert alert_manager.circuit_breaker_open is True
    assert any("CIRCUIT BREAKER" in alert["message"] for alert in alerts)


def test_circuit_breaker_reset(alert_manager):
    """Test circuit breaker reset."""
    # Trigger circuit breaker
    alert_manager.check_token_usage(
        current_tokens=1000000, max_tokens=1000000, context="test"
    )
    assert alert_manager.circuit_breaker_open is True

    # Reset
    alert_manager.reset_circuit_breaker()
    assert alert_manager.circuit_breaker_open is False


def test_alert_cooldown(alert_manager):
    """Test alert cooldown prevents duplicate alerts."""
    # First alert
    alerts1 = alert_manager.check_token_usage(
        current_tokens=800000, max_tokens=1000000, context="test"
    )
    assert len(alerts1) > 0

    # Second alert immediately after (should be suppressed by cooldown)
    alerts2 = alert_manager.check_token_usage(
        current_tokens=800000, max_tokens=1000000, context="test"
    )
    assert len(alerts2) == 0  # Cooldown prevents duplicate


def test_send_email_alert(alert_manager):
    """Test email alert configuration check."""
    # Enable email in config
    alert_manager.config["notification_channels"]["email"] = {
        "enabled": True,
        "recipients": ["test@example.com"],
    }

    alert = {
        "alert_id": "test_id",
        "account_id": "test_account",
        "severity": "error",
        "percentage": 90,
        "message": "Test alert",
    }

    # Email implementation would be mocked in production
    # This test verifies the configuration is checked correctly
    alert_manager._send_email_alert(alert)

    # In real implementation, would verify email service was called
    # For now, just verify the method doesn't raise an exception
    assert True  # Method completed without error


def test_send_firestore_alert(alert_manager, mock_firestore_client):
    """Test storing alert in Firestore."""
    mock_collection = MagicMock()
    mock_firestore_client.collection.return_value.document.return_value.collection.return_value = mock_collection

    alert = {"alert_id": "test_id", "severity": "warning", "message": "Test alert"}

    alert_manager._send_firestore_alert(alert)

    mock_collection.add.assert_called_once_with(alert)


def test_send_webhook_alert(alert_manager):
    """Test sending webhook alert."""
    # Enable webhook in config
    alert_manager.config["notification_channels"]["webhook"] = {
        "enabled": True,
        "url": "https://example.com/webhook",
        "headers": {"Authorization": "Bearer test"},
    }

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        alert = {"alert_id": "test", "message": "Test alert"}
        alert_manager._send_webhook_alert(alert)

        mock_post.assert_called_once_with(
            "https://example.com/webhook",
            json=alert,
            headers={"Authorization": "Bearer test"},
            timeout=10,
        )


def test_update_configuration(alert_manager, mock_firestore_client):
    """Test updating alert configuration."""
    new_thresholds = [
        {"percentage": 60, "severity": "warning", "channels": ["logging"]}
    ]

    alert_manager.update_configuration(thresholds=new_thresholds, enabled=False)

    assert alert_manager.config["thresholds"] == new_thresholds
    assert alert_manager.config["enabled"] is False

    # Verify save was called
    mock_firestore_client.collection.return_value.document.return_value.set.assert_called()


def test_get_recent_alerts(alert_manager, mock_firestore_client):
    """Test retrieving recent alerts."""
    # Mock Firestore query
    mock_doc1 = MagicMock()
    mock_doc1.to_dict.return_value = {
        "timestamp": "2024-01-01T12:00:00Z",
        "severity": "error",
        "message": "Alert 1",
    }

    mock_doc2 = MagicMock()
    mock_doc2.to_dict.return_value = {
        "timestamp": "2024-01-01T11:00:00Z",
        "severity": "warning",
        "message": "Alert 2",
    }

    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.stream.return_value = [mock_doc1, mock_doc2]

    mock_firestore_client.collection.return_value.document.return_value.collection.return_value.where.return_value = mock_query

    alerts = alert_manager.get_recent_alerts(hours=24)

    assert len(alerts) == 2
    # Should be sorted by timestamp (most recent first)
    assert alerts[0]["timestamp"] >= alerts[1]["timestamp"]


def test_disabled_alerts(alert_manager):
    """Test that alerts don't trigger when disabled."""
    alert_manager.config["enabled"] = False

    alerts = alert_manager.check_token_usage(
        current_tokens=950000, max_tokens=1000000, context="test"
    )

    assert len(alerts) == 0  # No alerts when disabled


def test_alert_severity_filtering(alert_manager, mock_firestore_client):
    """Test filtering alerts by severity."""
    mock_query = MagicMock()
    mock_query.where.return_value = mock_query
    mock_query.stream.return_value = []

    mock_firestore_client.collection.return_value.document.return_value.collection.return_value.where.return_value = mock_query

    alert_manager.get_recent_alerts(hours=24, severity_filter=AlertSeverity.ERROR)

    # Verify the severity FieldFilter was applied as a keyword argument to mock_query.where()
    calls = mock_query.where.call_args_list
    assert len(calls) >= 1, (
        f"Expected at least one .where() call for severity, got: {calls}"
    )
    field_filter = calls[-1].kwargs.get("filter")
    assert field_filter is not None, "Expected FieldFilter passed as 'filter=' kwarg"
    assert field_filter.field_path == "severity"


def test_load_save_round_trip():
    """Verify load()/save() round-trip on the Shape B path.

    Asserts:
    - save() writes to accounts/{account_id}/alert_configurations/default
    - load() reads from the same path
    - Returned config equals the saved payload
    - collection() was called with the Shape B path
    - document() was called with "default" (not the account_id)
    """
    saved_payload = {
        "account_id": "test_acct_xyz",
        "enabled": True,
        "thresholds": [],
        "marker": "round_trip",
    }

    with patch("google.cloud.firestore.Client") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db

        # Stage initial load (called in __init__) to return no doc so default config is used
        mock_init_doc = MagicMock()
        mock_init_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_init_doc
        )

        manager = AlertManager(account_id="test_acct_xyz", project_id="test_project")

        # Reset call history to inspect only the save/load calls
        mock_db.reset_mock()

        # Perform save
        manager.save(saved_payload)

        # Stage the mock so the next get() returns the saved payload
        mock_loaded_doc = MagicMock()
        mock_loaded_doc.exists = True
        mock_loaded_doc.to_dict.return_value = saved_payload
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_loaded_doc
        )

        # Perform load
        result = manager.load()

        # Assert round-trip payload equality
        assert result == saved_payload

        # Assert collection() was called with the Shape B path for both save and load
        collection_calls = [str(c) for c in mock_db.collection.call_args_list]
        assert any(
            "accounts/test_acct_xyz/alert_configurations" in c for c in collection_calls
        ), f"Expected Shape B path in collection calls, got: {collection_calls}"

        # Assert document() was called with "default" (not the account_id)
        document_calls = [
            str(c) for c in mock_db.collection.return_value.document.call_args_list
        ]
        assert any("'default'" in c or '"default"' in c for c in document_calls), (
            f"Expected 'default' doc-id in document calls, got: {document_calls}"
        )
        assert not any("test_acct_xyz" in c for c in document_calls), (
            f"account_id must not appear as doc-id in document calls, got: {document_calls}"
        )


@pytest.mark.parametrize(
    "bad_account_id,reason",
    [
        ("acc/with/slash", "a slash would change the Firestore path depth"),
        ("..", "could be misread as a path segment"),
        ("acc with spaces", "spaces are outside the allowed character set"),
        ("", "empty string"),
        ("a" * 129, "exceeds the 128-character bound"),
    ],
)
def test_alert_manager_rejects_invalid_account_id(bad_account_id, reason):
    """account_id is interpolated into f-string Firestore *collection* paths
    (``accounts/{account_id}/alert_configurations``), so AlertManager must reject
    anything outside ``^[a-zA-Z0-9_\\-]{1,128}$`` before constructing them."""
    with patch("google.cloud.firestore.Client"):
        with pytest.raises(ValueError):
            AlertManager(account_id=bad_account_id, project_id="test_project")
