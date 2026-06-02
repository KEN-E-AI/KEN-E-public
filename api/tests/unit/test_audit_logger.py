"""Unit tests for audit logger."""

import json
from unittest import mock

import pytest
from src.kene_api.auth.audit_logger import AuditLogger, SecurityEventType


class TestAuditLogger:
    """Test audit logger functionality."""

    @pytest.fixture
    def audit_logger(self):
        """Create an audit logger instance for testing."""
        return AuditLogger()

    @pytest.mark.asyncio
    async def test_log_event_basic(self, audit_logger):
        """Test basic event logging."""
        with mock.patch.object(audit_logger, "_structured_logger") as mock_logger:
            with mock.patch(
                "src.kene_api.auth.audit_logger.get_firestore_service"
            ) as mock_firestore:
                # Mock Firestore
                mock_service = mock.Mock()
                mock_client = mock.Mock()
                mock_collection = mock.Mock()
                mock_doc_ref = mock.Mock()

                mock_firestore.return_value = mock_service
                mock_service.get_client.return_value = mock_client
                mock_client.collection.return_value = mock_collection
                mock_collection.document.return_value = mock_doc_ref

                # Log event
                await audit_logger.log_event(
                    event_type=SecurityEventType.LOGIN_SUCCESS,
                    user_id="test-user",
                    email="test@example.com",
                    ip_address="192.168.1.1",
                    user_agent="TestAgent/1.0",
                    details={"session_id": "abc123"},
                    severity="INFO",
                )

                # Verify structured logging
                mock_logger.log.assert_called_once()
                call_args = mock_logger.log.call_args
                assert call_args[0][0] == 20  # INFO level

                # Parse logged JSON
                logged_data = json.loads(call_args[0][1])
                assert logged_data["security_event"]["event_type"] == "login_success"
                assert logged_data["security_event"]["user_id"] == "test-user"
                assert logged_data["security_event"]["email"] == "test@example.com"
                assert logged_data["security_event"]["ip_address"] == "192.168.1.1"
                assert (
                    logged_data["security_event"]["details"]["session_id"] == "abc123"
                )

                # Verify Firestore storage
                mock_doc_ref.set.assert_called_once()
                stored_data = mock_doc_ref.set.call_args[0][0]
                assert stored_data["event_type"] == "login_success"
                assert stored_data["user_id"] == "test-user"

    @pytest.mark.asyncio
    async def test_log_login_success(self, audit_logger):
        """Test login success logging."""
        with mock.patch.object(audit_logger, "log_event") as mock_log_event:
            await audit_logger.log_login_success(
                user_id="user123",
                email="user@example.com",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            mock_log_event.assert_called_once_with(
                event_type=SecurityEventType.LOGIN_SUCCESS,
                user_id="user123",
                email="user@example.com",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
                severity="INFO",
            )

    @pytest.mark.asyncio
    async def test_log_login_failure(self, audit_logger):
        """Test login failure logging."""
        with mock.patch.object(audit_logger, "log_event") as mock_log_event:
            await audit_logger.log_login_failure(
                email="user@example.com",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
                reason="Invalid credentials",
            )

            mock_log_event.assert_called_once_with(
                event_type=SecurityEventType.LOGIN_FAILURE,
                email="user@example.com",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
                details={"reason": "Invalid credentials"},
                severity="WARNING",
            )

    @pytest.mark.asyncio
    async def test_log_access_denied(self, audit_logger):
        """Test access denied logging."""
        with mock.patch.object(audit_logger, "log_event") as mock_log_event:
            await audit_logger.log_access_denied(
                user_id="user123",
                resource_type="account",
                resource_id="acc_456",
                required_permission="admin",
                ip_address="10.0.0.1",
            )

            mock_log_event.assert_called_once_with(
                event_type=SecurityEventType.ACCESS_DENIED,
                user_id="user123",
                ip_address="10.0.0.1",
                details={
                    "resource_type": "account",
                    "resource_id": "acc_456",
                    "required_permission": "admin",
                },
                severity="WARNING",
            )

    @pytest.mark.asyncio
    async def test_log_rate_limit_exceeded(self, audit_logger):
        """Test rate limit exceeded logging."""
        with mock.patch.object(audit_logger, "log_event") as mock_log_event:
            await audit_logger.log_rate_limit_exceeded(
                ip_address="10.0.0.1",
                endpoint="/api/v1/login",
                user_id="user123",
            )

            mock_log_event.assert_called_once_with(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                user_id="user123",
                ip_address="10.0.0.1",
                details={"endpoint": "/api/v1/login"},
                severity="WARNING",
            )

    @pytest.mark.asyncio
    async def test_log_token_revoked(self, audit_logger):
        """Test token revocation logging."""
        with mock.patch.object(audit_logger, "log_event") as mock_log_event:
            await audit_logger.log_token_revoked(
                user_id="user123",
                token_id="token_abc",
                reason="Suspicious activity",
                revoked_by="admin@example.com",
            )

            mock_log_event.assert_called_once_with(
                event_type=SecurityEventType.TOKEN_REVOKED,
                user_id="user123",
                details={
                    "token_id": "token_abc",
                    "reason": "Suspicious activity",
                    "revoked_by": "admin@example.com",
                },
                severity="INFO",
            )

    @pytest.mark.asyncio
    async def test_firestore_failure_handling(self, audit_logger):
        """Test that logging continues even if Firestore fails."""
        with mock.patch.object(audit_logger, "_structured_logger") as mock_logger:
            with mock.patch(
                "src.kene_api.auth.audit_logger.get_firestore_service"
            ) as mock_firestore:
                # Mock Firestore failure
                mock_firestore.side_effect = Exception("Firestore connection failed")

                # Log event - should not raise exception
                await audit_logger.log_event(
                    event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                    user_id="test-user",
                    severity="CRITICAL",
                )

                # Verify structured logging still happened
                mock_logger.log.assert_called_once()

    @pytest.mark.asyncio
    async def test_firestore_failure_surfaces_event_context(self, audit_logger, caplog):
        """A Firestore write failure must log event_type/user_id/severity for SRE correlation.

        Without these fields the operator only sees a generic "failed to store"
        message and can't tell which audit event was lost. Defensive: ensures
        the Cloud Logging primary trail can be cross-referenced.
        """
        with mock.patch(
            "src.kene_api.auth.audit_logger.get_firestore_service",
            side_effect=Exception("Firestore connection failed"),
        ):
            with caplog.at_level("ERROR", logger="src.kene_api.auth.audit_logger"):
                await audit_logger.log_event(
                    event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                    user_id="test-user",
                    severity="CRITICAL",
                )

        error_records = [
            r
            for r in caplog.records
            if r.levelname == "ERROR" and "Failed to persist audit log" in r.message
        ]
        assert len(error_records) == 1, (
            "Expected one structured error record for the failed Firestore write"
        )
        record = error_records[0]
        assert getattr(record, "audit_event_type", None) == "suspicious_activity"
        assert getattr(record, "audit_user_id", None) == "test-user"
        assert getattr(record, "audit_severity", None) == "CRITICAL"
        assert getattr(record, "error_type", None) == "Exception"
