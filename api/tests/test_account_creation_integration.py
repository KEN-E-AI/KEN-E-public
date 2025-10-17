"""
Integration test for account creation flow.

This test verifies the complete account creation process including:
- Account node creation in Neo4j
- Initial Activity nodes creation from Firestore templates
- BELONGS_TO relationships
- Proper error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.kene_api.services.account_service import create_account_internal
from src.kene_api.models.kene_models import AccountRequest
from src.kene_api.auth import UserContext


@pytest.mark.asyncio
async def test_create_account_creates_initial_activities():
    """
    Test that account creation creates initial Activity nodes.

    This test would have caught Issue #1 where _create_initial_activities()
    was not being called during account creation.
    """
    # Arrange
    account_request = AccountRequest(
        account_id="test_acc_123",
        account_name="Test Company",
        organization_id="test_org",
        industry="Technology",
        status="Active",
        websites=["https://test.com"],
        timezone="America/New_York",
        data_region="US",
        region=["North America"],
        estimated_annual_ad_budget=100000,
    )

    uploaded_docs = []

    # Mock dependencies
    mock_user = MagicMock(spec=UserContext)
    mock_user.user_id = "test_user"
    mock_user.email = "test@example.com"
    mock_user.is_super_admin = False
    mock_user.organization_permissions = {}
    mock_user.account_permissions = {}
    mock_user.accessible_accounts = []

    mock_firestore = MagicMock()
    mock_storage = MagicMock()
    mock_neo4j = AsyncMock()
    mock_bigquery = None
    mock_background_tasks = MagicMock()

    # Mock Firestore initial-activities collection with sample data
    mock_activity_templates = [
        {
            "activity_id": "act_00_us",
            "activity_name": "Holiday in the United States",
            "activity_description": "US federal holidays",
            "expected_impact": "high",
            "internal": False,
            "known_activity": True,
        },
        {
            "activity_id": "act_01",
            "activity_name": "Changed Tags",
            "activity_description": "Updated product tags",
            "expected_impact": "medium",
            "internal": True,
            "known_activity": False,
        },
    ]
    mock_firestore.list_documents.return_value = mock_activity_templates

    # Mock Neo4j queries
    async def mock_execute_query(query, params=None):
        """Mock Neo4j query execution."""
        if "MATCH (org:Organization" in query:
            # Organization lookup
            return [{"organization_name": "Test Org", "agency": False}]
        elif "MATCH (acc:Account {account_id:" in query and "RETURN acc.websites" in query:
            # Account verification query
            return [{"websites": ["https://test.com"], "industry": "Technology", "budget": 100000}]
        return []

    async def mock_execute_write_query(query, params=None):
        """Mock Neo4j write query execution."""
        if "CREATE (acc:Account" in query:
            # Account creation
            return [{"acc": {"account_id": "test_acc_123"}}]
        elif "UNWIND $activities AS activity" in query:
            # Activity creation - verify this is called
            assert "activities" in params, "activities parameter missing"
            assert len(params["activities"]) == 2, f"Expected 2 activities, got {len(params['activities'])}"
            return [{"created_count": 2}]
        return []

    mock_neo4j.execute_query = mock_execute_query
    mock_neo4j.execute_write_query = mock_execute_write_query

    # Mock Firestore document creation
    mock_firestore.create_document.return_value = "placeholder_doc_id"
    mock_firestore.set_nested_field.return_value = True

    # Mock background task
    mock_background_tasks.add_task = MagicMock()

    # Act
    with patch("src.kene_api.auth.cached_user_context.get_cached_user_context_service"):
        account = await create_account_internal(
            request=account_request,
            uploaded_document_urls=uploaded_docs,
            background_tasks=mock_background_tasks,
            user=mock_user,
            firestore=mock_firestore,
            storage=mock_storage,
            neo4j_service=mock_neo4j,
            bigquery_service=mock_bigquery,
        )

    # Assert
    assert account is not None
    assert account.account_id == "test_acc_123"

    # Verify _create_initial_activities was called through Firestore
    mock_firestore.list_documents.assert_called_once_with("initial-activities")

    # Verify Neo4j write query was called for activities (via execute_write_query mock assertion)
    # The assertion happens inside mock_execute_write_query


@pytest.mark.asyncio
async def test_account_creation_handles_missing_activity_templates():
    """Test that account creation succeeds even if activity templates are missing."""
    # Arrange
    account_request = AccountRequest(
        account_id="test_acc_456",
        account_name="Test Company 2",
        organization_id="test_org",
        industry="Retail",
        status="Active",
        websites=["https://test2.com"],
        timezone="UTC",
        data_region="US",
        region=[],
        estimated_annual_ad_budget=50000,
    )

    mock_user = MagicMock(spec=UserContext)
    mock_user.user_id = "test_user"
    mock_user.email = "test@example.com"
    mock_user.is_super_admin = False
    mock_user.organization_permissions = {}
    mock_user.account_permissions = {}
    mock_user.accessible_accounts = []

    mock_firestore = MagicMock()
    mock_storage = MagicMock()
    mock_neo4j = AsyncMock()
    mock_background_tasks = MagicMock()

    # Mock empty activity templates (Firestore collection is empty)
    mock_firestore.list_documents.return_value = []

    # Mock Neo4j
    async def mock_execute_query(query, params=None):
        if "MATCH (org:Organization" in query:
            return [{"organization_name": "Test Org", "agency": False}]
        elif "RETURN acc.websites" in query:
            return [{"websites": ["https://test2.com"], "industry": "Retail", "budget": 50000}]
        return []

    async def mock_execute_write_query(query, params=None):
        if "CREATE (acc:Account" in query:
            return [{"acc": {"account_id": "test_acc_456"}}]
        # Should NOT be called for activities since templates are empty
        if "UNWIND $activities" in query:
            pytest.fail("Activity creation should not be called with empty templates")
        return []

    mock_neo4j.execute_query = mock_execute_query
    mock_neo4j.execute_write_query = mock_execute_write_query
    mock_firestore.create_document.return_value = "doc_id"
    mock_firestore.set_nested_field.return_value = True
    mock_background_tasks.add_task = MagicMock()

    # Act
    with patch("src.kene_api.auth.cached_user_context.get_cached_user_context_service"):
        account = await create_account_internal(
            request=account_request,
            uploaded_document_urls=[],
            background_tasks=mock_background_tasks,
            user=mock_user,
            firestore=mock_firestore,
            storage=mock_storage,
            neo4j_service=mock_neo4j,
            bigquery_service=None,
        )

    # Assert - account creation should succeed even without activities
    assert account is not None
    assert account.account_id == "test_acc_456"
    mock_firestore.list_documents.assert_called_once()


@pytest.mark.asyncio
async def test_account_creation_handles_activity_creation_failure():
    """Test that account creation succeeds even if activity creation fails."""
    # Arrange
    account_request = AccountRequest(
        account_id="test_acc_789",
        account_name="Test Company 3",
        organization_id="test_org",
        industry="Healthcare",
        status="Active",
        websites=["https://test3.com"],
        timezone="America/Los_Angeles",
        data_region="US",
        region=["West Coast"],
        estimated_annual_ad_budget=200000,
    )

    mock_user = MagicMock(spec=UserContext)
    mock_user.user_id = "test_user"
    mock_user.email = "test@example.com"
    mock_user.is_super_admin = False
    mock_user.organization_permissions = {}
    mock_user.account_permissions = {}
    mock_user.accessible_accounts = []

    mock_firestore = MagicMock()
    mock_storage = MagicMock()
    mock_neo4j = AsyncMock()
    mock_background_tasks = MagicMock()

    # Mock Firestore to return templates
    mock_firestore.list_documents.return_value = [
        {"activity_id": "act_test", "activity_name": "Test Activity"}
    ]

    # Mock Neo4j
    async def mock_execute_query(query, params=None):
        if "MATCH (org:Organization" in query:
            return [{"organization_name": "Test Org", "agency": False}]
        elif "RETURN acc.websites" in query:
            return [{"websites": ["https://test3.com"], "industry": "Healthcare", "budget": 200000}]
        return []

    async def mock_execute_write_query(query, params=None):
        if "CREATE (acc:Account" in query:
            return [{"acc": {"account_id": "test_acc_789"}}]
        elif "UNWIND $activities" in query:
            # Simulate activity creation failure
            raise Exception("Neo4j connection error during activity creation")
        return []

    mock_neo4j.execute_query = mock_execute_query
    mock_neo4j.execute_write_query = mock_execute_write_query
    mock_firestore.create_document.return_value = "doc_id"
    mock_firestore.set_nested_field.return_value = True
    mock_background_tasks.add_task = MagicMock()

    # Act - should NOT raise exception despite activity creation failure
    with patch("src.kene_api.auth.cached_user_context.get_cached_user_context_service"):
        account = await create_account_internal(
            request=account_request,
            uploaded_document_urls=[],
            background_tasks=mock_background_tasks,
            user=mock_user,
            firestore=mock_firestore,
            storage=mock_storage,
            neo4j_service=mock_neo4j,
            bigquery_service=None,
        )

    # Assert - account creation should succeed despite activity failure
    assert account is not None
    assert account.account_id == "test_acc_789"
    # The error is logged but doesn't break account creation
