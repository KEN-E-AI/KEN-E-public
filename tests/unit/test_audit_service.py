"""
Unit tests for audit logging service.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from api.src.kene_api.auth.models import UserContext
from api.src.kene_api.models.strategy_models import StrategyAuditEntry
from api.src.kene_api.services.audit_service import (
    cleanup_old_audit_logs,
    get_document_history,
    get_recent_actions,
    log_strategy_action,
)


class TestAuditService:
    """Test audit logging service functionality."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user context."""
        return UserContext(
            user_id="test_user_001",
            email="test@example.com",
            accessible_accounts=["account_001"],
            permissions={},
            organization_permissions={"org_001": "admin"},
            account_permissions={},
        )

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers.get.return_value = "Mozilla/5.0 Test Browser"
        return request

    @pytest.fixture
    def mock_firestore(self):
        """Create a mock Firestore client."""
        with patch("api.src.kene_api.services.audit_service.db") as mock_db:
            yield mock_db

    @pytest.mark.asyncio
    async def test_log_strategy_action_create(
        self, mock_user, mock_request, mock_firestore
    ):
        """Test logging a document creation action."""
        # Mock Firestore document reference
        mock_doc_ref = MagicMock()
        mock_firestore.document.return_value = mock_doc_ref

        # Log action
        audit_id = await log_strategy_action(
            account_id="account_001",
            doc_type="business_strategy",
            action="created",
            user=mock_user,
            request=mock_request,
            doc_id="doc_001",
            version=1,
        )

        # Verify audit ID was returned
        assert audit_id != ""

        # Verify Firestore was called
        mock_firestore.document.assert_called_once()
        mock_doc_ref.set.assert_called_once()

        # Verify the audit entry data
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["action"] == "created"
        assert call_args["user_id"] == "test_user_001"
        assert call_args["user_email"] == "test@example.com"
        assert call_args["doc_type"] == "business_strategy"
        assert call_args["doc_id"] == "doc_001"
        assert call_args["version"] == 1
        assert call_args["ip_address"] == "192.168.1.1"
        assert call_args["user_agent"] == "Mozilla/5.0 Test Browser"

    @pytest.mark.asyncio
    async def test_log_strategy_action_update_with_changes(
        self, mock_user, mock_request, mock_firestore
    ):
        """Test logging an update action with changes."""
        mock_doc_ref = MagicMock()
        mock_firestore.document.return_value = mock_doc_ref

        changes = {"before": {"title": "Old Title"}, "after": {"title": "New Title"}}

        audit_id = await log_strategy_action(
            account_id="account_001",
            doc_type="competitive_strategy",
            action="updated",
            user=mock_user,
            request=mock_request,
            doc_id="doc_002",
            version=2,
            changes=changes,
            fields_modified=["title"],
        )

        # Verify the changes were logged
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["action"] == "updated"
        assert call_args["changes"] == changes
        assert call_args["fields_modified"] == ["title"]
        assert call_args["version"] == 2

    @pytest.mark.asyncio
    async def test_log_strategy_action_no_request(self, mock_user, mock_firestore):
        """Test logging without request object (e.g., from background job)."""
        mock_doc_ref = MagicMock()
        mock_firestore.document.return_value = mock_doc_ref

        audit_id = await log_strategy_action(
            account_id="account_001",
            doc_type="brand_strategy",
            action="viewed",
            user=mock_user,
            request=None,
        )

        # Verify it works without request
        assert audit_id != ""

        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["ip_address"] is None
        assert call_args["user_agent"] is None

    @pytest.mark.asyncio
    async def test_log_strategy_action_with_session(self, mock_user, mock_firestore):
        """Test logging with chat session ID."""
        mock_doc_ref = MagicMock()
        mock_firestore.document.return_value = mock_doc_ref

        session_id = "chat_session_123"

        audit_id = await log_strategy_action(
            account_id="account_001",
            doc_type="marketing_strategy",
            action="created",
            user=mock_user,
            session_id=session_id,
        )

        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_get_recent_actions(self, mock_firestore):
        """Test retrieving recent actions."""
        # Mock Firestore query
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_firestore.collection.return_value = mock_collection
        mock_collection.order_by.return_value = mock_query
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query

        # Mock query results
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = {
            "action": "created",
            "user_id": "user_001",
            "user_email": "test@example.com",
            "timestamp": datetime.utcnow(),
            "doc_type": "business_strategy",
            "version": 1,
        }
        mock_query.stream.return_value = [mock_doc1]

        # Get recent actions
        entries = await get_recent_actions(
            account_id="account_001", user_id="user_001", limit=5
        )

        # Verify results
        assert len(entries) == 1
        assert entries[0].action == "created"
        assert entries[0].user_id == "user_001"

        # Verify query construction
        mock_collection.order_by.assert_called_once_with(
            "timestamp", direction="DESCENDING"
        )
        mock_query.limit.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_document_history(self, mock_firestore):
        """Test retrieving document history."""
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_firestore.collection.return_value = mock_collection
        mock_collection.where.return_value = mock_query
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query

        # Mock multiple history entries
        entries_data = [
            {
                "action": "created",
                "user_id": "user_001",
                "user_email": "creator@example.com",
                "timestamp": datetime.utcnow() - timedelta(days=2),
                "doc_type": "business_strategy",
                "doc_id": "doc_001",
                "version": 1,
            },
            {
                "action": "updated",
                "user_id": "user_002",
                "user_email": "editor@example.com",
                "timestamp": datetime.utcnow() - timedelta(days=1),
                "doc_type": "business_strategy",
                "doc_id": "doc_001",
                "version": 2,
            },
        ]

        mock_docs = []
        for data in entries_data:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = data
            mock_docs.append(mock_doc)

        mock_query.stream.return_value = mock_docs

        # Get document history
        entries = await get_document_history(
            account_id="account_001", doc_type="business_strategy", doc_id="doc_001"
        )

        # Verify results
        assert len(entries) == 2
        assert entries[0].action == "created"
        assert entries[0].version == 1
        assert entries[1].action == "updated"
        assert entries[1].version == 2

    @pytest.mark.asyncio
    async def test_cleanup_old_audit_logs(self, mock_firestore):
        """Test cleanup of old audit logs."""
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_batch = MagicMock()

        mock_firestore.collection.return_value = mock_collection
        mock_firestore.batch.return_value = mock_batch
        mock_collection.where.return_value = mock_query

        # Mock old documents to delete
        old_docs = []
        for i in range(5):
            mock_doc = MagicMock()
            mock_doc.reference = f"doc_ref_{i}"
            old_docs.append(mock_doc)

        mock_query.stream.return_value = old_docs

        # Run cleanup
        deleted_count = await cleanup_old_audit_logs(
            account_id="account_001", days_to_keep=30
        )

        # Verify results
        assert deleted_count == 5

        # Verify batch operations
        assert mock_batch.delete.call_count == 5
        mock_batch.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_audit_logs_large_batch(self, mock_firestore):
        """Test cleanup with large number of documents (batch splitting)."""
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_batch = MagicMock()

        mock_firestore.collection.return_value = mock_collection
        mock_firestore.batch.return_value = mock_batch
        mock_collection.where.return_value = mock_query

        # Mock 501 documents (should trigger batch split)
        old_docs = []
        for i in range(501):
            mock_doc = MagicMock()
            mock_doc.reference = f"doc_ref_{i}"
            old_docs.append(mock_doc)

        mock_query.stream.return_value = old_docs

        # Run cleanup
        deleted_count = await cleanup_old_audit_logs(
            account_id="account_001", days_to_keep=30
        )

        # Verify results
        assert deleted_count == 501

        # Verify batch was committed twice (500 + 1)
        assert mock_batch.commit.call_count == 2

    def test_audit_entry_model_validation(self):
        """Test StrategyAuditEntry model validation."""
        # Valid entry
        entry = StrategyAuditEntry(
            action="created",
            user_id="user_001",
            user_email="test@example.com",
            doc_type="business_strategy",
            version=1,
        )

        assert entry.action == "created"
        assert entry.user_id == "user_001"
        assert entry.version == 1

        # Test invalid action
        with pytest.raises(ValueError):
            StrategyAuditEntry(
                action="invalid_action",  # Invalid action
                user_id="user_001",
                user_email="test@example.com",
                doc_type="business_strategy",
                version=1,
            )
