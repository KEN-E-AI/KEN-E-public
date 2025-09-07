"""Tests for OAuth state storage service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from src.kene_api.models.oauth_models import OAuthState
from src.kene_api.services.oauth_state_service import OAuthStateService


@pytest.fixture
def mock_firestore_client():
    """Create a mock Firestore client."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection
    mock_client.batch.return_value = MagicMock()
    return mock_client


@pytest.fixture
def oauth_state_service(mock_firestore_client):
    """Create an OAuthStateService instance with mock client."""
    return OAuthStateService(mock_firestore_client)


@pytest.mark.asyncio
async def test_create_state(oauth_state_service, mock_firestore_client):
    """Test creating a new OAuth state."""
    # Arrange
    state_token = "test-state-token"
    user_id = "test-user-id"
    account_id = "test-account-id"
    integration_type = "google_analytics"

    mock_doc_ref = MagicMock()
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.create_state(
        state_token=state_token,
        user_id=user_id,
        account_id=account_id,
        integration_type=integration_type,
        ttl_minutes=15,
    )

    # Assert
    assert isinstance(result, OAuthState)
    assert result.state_token == state_token
    assert result.user_id == user_id
    assert result.account_id == account_id
    assert result.integration_type == integration_type
    assert result.expires_at > result.created_at

    # Verify Firestore was called
    mock_firestore_client.collection.assert_called_with("oauth_states")
    mock_firestore_client.collection.return_value.document.assert_called_with(
        state_token
    )
    mock_doc_ref.set.assert_called_once()

    # Check the data that was stored
    stored_data = mock_doc_ref.set.call_args[0][0]
    assert stored_data["state_token"] == state_token
    assert stored_data["user_id"] == user_id
    assert stored_data["account_id"] == account_id


@pytest.mark.asyncio
async def test_get_state_valid(oauth_state_service, mock_firestore_client):
    """Test retrieving a valid OAuth state."""
    # Arrange
    state_token = "test-state-token"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "state_token": state_token,
        "user_id": "test-user-id",
        "account_id": "test-account-id",
        "created_at": now,
        "expires_at": expires_at,
        "integration_type": "google_analytics",
        "metadata": {},
    }

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.get_state(state_token)

    # Assert
    assert result is not None
    assert isinstance(result, OAuthState)
    assert result.state_token == state_token
    assert result.user_id == "test-user-id"
    assert result.account_id == "test-account-id"

    # Verify Firestore was called
    mock_firestore_client.collection.assert_called_with("oauth_states")
    mock_firestore_client.collection.return_value.document.assert_called_with(
        state_token
    )
    mock_doc_ref.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_state_not_found(oauth_state_service, mock_firestore_client):
    """Test retrieving a non-existent OAuth state."""
    # Arrange
    state_token = "non-existent-token"

    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.get_state(state_token)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_get_state_expired(oauth_state_service, mock_firestore_client):
    """Test retrieving an expired OAuth state."""
    # Arrange
    state_token = "expired-token"
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(minutes=1)  # Already expired

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "state_token": state_token,
        "user_id": "test-user-id",
        "account_id": "test-account-id",
        "created_at": now - timedelta(minutes=20),
        "expires_at": expires_at,
        "integration_type": "google_analytics",
        "metadata": {},
    }

    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value = mock_doc
    mock_doc_ref.delete = MagicMock()  # Mock delete method
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.get_state(state_token)

    # Assert
    assert result is None
    # Verify the expired state was deleted
    mock_doc_ref.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_state(oauth_state_service, mock_firestore_client):
    """Test deleting an OAuth state."""
    # Arrange
    state_token = "test-state-token"

    mock_doc_ref = MagicMock()
    mock_doc_ref.delete = MagicMock()
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.delete_state(state_token)

    # Assert
    assert result is True
    mock_firestore_client.collection.assert_called_with("oauth_states")
    mock_firestore_client.collection.return_value.document.assert_called_with(
        state_token
    )
    mock_doc_ref.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_state_error(oauth_state_service, mock_firestore_client):
    """Test error handling when deleting an OAuth state."""
    # Arrange
    state_token = "test-state-token"

    mock_doc_ref = MagicMock()
    mock_doc_ref.delete.side_effect = Exception("Delete failed")
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    result = await oauth_state_service.delete_state(state_token)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_cleanup_expired_states(oauth_state_service, mock_firestore_client):
    """Test cleaning up expired OAuth states."""
    # Arrange
    # Create mock expired documents
    mock_docs = []
    for _i in range(3):
        mock_doc = MagicMock()
        mock_doc.reference = MagicMock()
        mock_docs.append(mock_doc)

    mock_query = MagicMock()
    mock_query.stream.return_value = iter(mock_docs)
    mock_firestore_client.collection.return_value.where.return_value = mock_query

    mock_batch = MagicMock()
    mock_firestore_client.batch.return_value = mock_batch

    # Act
    count = await oauth_state_service.cleanup_expired_states()

    # Assert
    assert count == 3
    assert mock_batch.delete.call_count == 3
    mock_batch.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_expired_states_large_batch(
    oauth_state_service, mock_firestore_client
):
    """Test cleaning up a large batch of expired OAuth states."""
    # Arrange
    # Create 501 mock expired documents (to test batch size limit)
    mock_docs = []
    for _i in range(501):
        mock_doc = MagicMock()
        mock_doc.reference = MagicMock()
        mock_docs.append(mock_doc)

    mock_query = MagicMock()
    mock_query.stream.return_value = iter(mock_docs)
    mock_firestore_client.collection.return_value.where.return_value = mock_query

    mock_batch = MagicMock()
    mock_firestore_client.batch.return_value = mock_batch

    # Act
    count = await oauth_state_service.cleanup_expired_states()

    # Assert
    assert count == 501
    # Should have committed twice (500 + 1)
    assert mock_batch.commit.call_count == 2
    # New batch should have been created
    assert mock_firestore_client.batch.call_count == 2
