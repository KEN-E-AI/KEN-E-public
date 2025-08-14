"""Test notification service with empty account lists."""

import pytest
from unittest.mock import Mock, MagicMock
from google.cloud import firestore

from src.kene_api.services.notification_service_v2 import NotificationService
from src.kene_api.models.kene_models import NotificationCategory


@pytest.mark.asyncio
async def test_get_user_notifications_with_empty_account_list():
    """Test that get_user_notifications returns empty list when user has no accessible accounts."""
    # Create mock Firestore client
    mock_db = Mock(spec=firestore.Client)
    
    # Create service
    service = NotificationService(mock_db)
    
    # Call with empty account list
    result = await service.get_user_notifications(
        user_id="test_user",
        account_ids=[],  # Empty list
        include_archived=False
    )
    
    # Should return empty list without querying Firestore
    assert result == []
    mock_db.collection.assert_not_called()


@pytest.mark.asyncio
async def test_get_unread_count_with_empty_account_list():
    """Test that get_unread_count returns 0 when user has no accessible accounts."""
    # Create mock Firestore client
    mock_db = Mock(spec=firestore.Client)
    
    # Create service
    service = NotificationService(mock_db)
    
    # Call with empty account list
    result = await service.get_unread_count(
        user_id="test_user",
        account_ids=[]  # Empty list
    )
    
    # Should return 0 without querying Firestore
    assert result == 0
    mock_db.collection.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_notifications_with_accounts():
    """Test that get_user_notifications queries Firestore when accounts exist."""
    # Create mock Firestore client
    mock_db = Mock(spec=firestore.Client)
    mock_collection = Mock()
    mock_query = Mock()
    mock_stream = Mock(return_value=[])
    
    mock_db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_query.stream.return_value = mock_stream
    
    # Create service
    service = NotificationService(mock_db)
    
    # Call with non-empty account list
    result = await service.get_user_notifications(
        user_id="test_user",
        account_ids=["account1", "account2"],
        include_archived=False
    )
    
    # Should query Firestore
    mock_db.collection.assert_called_once_with("notifications")
    mock_collection.where.assert_called_once_with("account_id", "in", ["account1", "account2"])