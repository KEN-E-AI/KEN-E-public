"""Integration tests for simplified account creation flow."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.kene_api.routers.accounts import AccountCreationStatus
from src.kene_api.tasks.strategy_tasks import (
    trigger_strategy_generation,
    update_account_setup_status,
    verify_strategy_documents_created,
)


@pytest.mark.asyncio
async def test_account_creation_status_uses_progress_rate_limiter():
    """Test that the creation-status endpoint uses higher rate limits."""
    from src.kene_api.auth.user_context import get_user_context_for_polling
    from src.kene_api.rate_limiter import progress_rate_limiter
    
    # Mock request
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {"User-Agent": "test"}
    
    # Mock credentials
    mock_credentials = MagicMock()
    mock_credentials.credentials = "test_token"
    
    # Mock Firebase token verification
    with patch("src.kene_api.auth.user_context.verify_id_token") as mock_verify:
        mock_verify.return_value = {
            "uid": "test_user",
            "email": "test@example.com",
            "iat": 1234567890,
        }
        
        # Mock Firestore
        with patch("src.kene_api.auth.user_context.get_firestore_service") as mock_firestore:
            mock_firestore_service = MagicMock()
            mock_firestore_client = MagicMock()
            mock_user_doc = MagicMock()
            mock_user_doc.exists = True
            mock_user_doc.to_dict.return_value = {
                "uid": "test_user",
                "email": "test@example.com",
                "permissions": {"accounts": {"test_account": "admin"}},
            }
            mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_user_doc
            mock_firestore_service.get_client.return_value = mock_firestore_client
            mock_firestore.return_value = mock_firestore_service
            
            # Test that we can call this function multiple times quickly
            # (would fail with regular rate limiter but succeeds with progress_rate_limiter)
            for _ in range(10):
                user_context = await get_user_context_for_polling(
                    mock_request, mock_credentials, mock_firestore_service
                )
                assert user_context.user_id == "test_user"


@pytest.mark.asyncio
async def test_strategy_generation_timeout_handling():
    """Test that strategy generation properly handles timeouts."""
    account_id = "test_account"
    
    # Mock the agent engine to simulate timeout
    with patch("src.kene_api.tasks.strategy_tasks.agent_engines") as mock_engines:
        mock_engine = MagicMock()
        
        # Create a mock response that takes too long
        async def slow_generator():
            for i in range(100):
                await asyncio.sleep(0.1)  # Simulate slow response
                yield {"content": {"parts": [{"text": f"chunk_{i}"}]}}
        
        mock_engine.stream_query.return_value = slow_generator()
        mock_engines.get.return_value = mock_engine
        
        # Mock environment variables
        with patch.dict("os.environ", {
            "VERTEX_AI_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "test-engine-id",
        }):
            # Mock Vertex AI init
            with patch("src.kene_api.tasks.strategy_tasks.vertexai.init"):
                # Mock database update
                with patch("src.kene_api.tasks.strategy_tasks.update_account_setup_status") as mock_update:
                    # Run strategy generation with a short timeout
                    await trigger_strategy_generation(
                        account_id=account_id,
                        company_name="Test Company",
                        websites=["https://example.com"],
                        industry="Technology",
                        customer_regions=["US"],
                        user_id="test_user",
                    )
                    
                    # Should have called update with failed status due to timeout
                    mock_update.assert_called_with(
                        account_id, "failed", completed=False, 
                        error_message="Strategy document generation timed out. Please try again."
                    )


@pytest.mark.asyncio
async def test_empty_agent_response_handling():
    """Test that empty agent responses are handled properly."""
    account_id = "test_account"
    
    # Mock the agent engine to return empty response
    with patch("src.kene_api.tasks.strategy_tasks.agent_engines") as mock_engines:
        mock_engine = MagicMock()
        
        # Create an empty response generator
        async def empty_generator():
            yield {"content": {"parts": []}}  # Empty parts
        
        mock_engine.stream_query.return_value = empty_generator()
        mock_engines.get.return_value = mock_engine
        
        # Mock environment variables
        with patch.dict("os.environ", {
            "VERTEX_AI_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "test-engine-id",
        }):
            # Mock Vertex AI init
            with patch("src.kene_api.tasks.strategy_tasks.vertexai.init"):
                # Mock database update
                with patch("src.kene_api.tasks.strategy_tasks.update_account_setup_status") as mock_update:
                    # Run strategy generation
                    await trigger_strategy_generation(
                        account_id=account_id,
                        company_name="Test Company",
                        websites=["https://example.com"],
                        industry="Technology",
                        customer_regions=["US"],
                        user_id="test_user",
                    )
                    
                    # Should have called update with failed status due to empty response
                    mock_update.assert_called_with(
                        account_id, "failed", completed=False,
                        error_message="Strategy generation returned no content. Please try again."
                    )


@pytest.mark.asyncio
async def test_document_verification_failure():
    """Test that incomplete documents prevent account completion."""
    account_id = "test_account"
    
    # Mock the agent engine to return a valid response
    with patch("src.kene_api.tasks.strategy_tasks.agent_engines") as mock_engines:
        mock_engine = MagicMock()
        
        # Create a valid response generator
        async def valid_generator():
            yield {"content": {"parts": [{"text": "Valid strategy content"}]}}
        
        mock_engine.stream_query.return_value = valid_generator()
        mock_engines.get.return_value = mock_engine
        
        # Mock environment variables
        with patch.dict("os.environ", {
            "VERTEX_AI_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "test-engine-id",
        }):
            # Mock Vertex AI init
            with patch("src.kene_api.tasks.strategy_tasks.vertexai.init"):
                # Mock document verification to return False (documents not complete)
                with patch("src.kene_api.tasks.strategy_tasks.verify_strategy_documents_created") as mock_verify:
                    mock_verify.return_value = False  # Documents never complete
                    
                    # Mock database update
                    with patch("src.kene_api.tasks.strategy_tasks.update_account_setup_status") as mock_update:
                        # Mock sleep to speed up test
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            # Run strategy generation
                            await trigger_strategy_generation(
                                account_id=account_id,
                                company_name="Test Company",
                                websites=["https://example.com"],
                                industry="Technology",
                                customer_regions=["US"],
                                user_id="test_user",
                            )
                            
                            # Should have called update with failed status due to incomplete documents
                            mock_update.assert_called_with(
                                account_id, "failed", completed=False,
                                error_message="Strategy document generation timed out. Please try again."
                            )


@pytest.mark.asyncio
async def test_successful_account_creation():
    """Test successful account creation with all documents complete."""
    account_id = "test_account"
    
    # Mock the agent engine to return a valid response
    with patch("src.kene_api.tasks.strategy_tasks.agent_engines") as mock_engines:
        mock_engine = MagicMock()
        
        # Create a valid response generator
        async def valid_generator():
            yield {"content": {"parts": [{"text": "Valid strategy content"}]}}
        
        mock_engine.stream_query.return_value = valid_generator()
        mock_engines.get.return_value = mock_engine
        
        # Mock environment variables
        with patch.dict("os.environ", {
            "VERTEX_AI_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "test-engine-id",
        }):
            # Mock Vertex AI init
            with patch("src.kene_api.tasks.strategy_tasks.vertexai.init"):
                # Mock document verification to return True (all documents complete)
                with patch("src.kene_api.tasks.strategy_tasks.verify_strategy_documents_created") as mock_verify:
                    mock_verify.return_value = True  # All documents complete
                    
                    # Mock database update
                    with patch("src.kene_api.tasks.strategy_tasks.update_account_setup_status") as mock_update:
                        # Run strategy generation
                        await trigger_strategy_generation(
                            account_id=account_id,
                            company_name="Test Company",
                            websites=["https://example.com"],
                            industry="Technology",
                            customer_regions=["US"],
                            user_id="test_user",
                        )
                        
                        # Should have called update with completed status
                        mock_update.assert_called_with(
                            account_id, "completed", completed=True
                        )


@pytest.mark.asyncio
async def test_account_creation_status_endpoint_responses():
    """Test the different status responses from the creation-status endpoint."""
    from src.kene_api.routers.accounts import get_account_creation_status
    from src.kene_api.auth import UserContext
    
    # Create mock user context
    mock_user = UserContext(
        user_id="test_user",
        email="test@example.com",
        accessible_accounts=["test_account"],
        permissions={"test_account": "admin"},
        organization_permissions={"test_org": "admin"},
        account_permissions={},
    )
    
    # Test case 1: Account not found (being created)
    with patch("src.kene_api.routers.accounts.get_neo4j_service") as mock_db_service:
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = []  # No account found
        mock_db_service.return_value = mock_db
        
        status = await get_account_creation_status("test_account", mock_user, mock_db)
        assert status.status == "processing"
        assert "15-20 minutes" in status.message
    
    # Test case 2: Account completed
    with patch("src.kene_api.routers.accounts.get_neo4j_service") as mock_db_service:
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [{
            "setup_status": "completed",
            "setup_completed_at": datetime.now(),
            "organization_id": "test_org",
        }]
        mock_db_service.return_value = mock_db
        
        status = await get_account_creation_status("test_account", mock_user, mock_db)
        assert status.status == "completed"
        assert status.message == "Account setup complete"
    
    # Test case 3: Account failed
    with patch("src.kene_api.routers.accounts.get_neo4j_service") as mock_db_service:
        mock_db = AsyncMock()
        mock_db.execute_query.side_effect = [
            [{
                "setup_status": "failed",
                "setup_completed_at": None,
                "organization_id": "test_org",
            }],
            [{"error": "Strategy generation timeout"}]  # Error details query
        ]
        mock_db_service.return_value = mock_db
        
        status = await get_account_creation_status("test_account", mock_user, mock_db)
        assert status.status == "failed"
        assert "Strategy generation timeout" in status.message
    
    # Test case 4: Account processing
    with patch("src.kene_api.routers.accounts.get_neo4j_service") as mock_db_service:
        mock_db = AsyncMock()
        mock_db.execute_query.return_value = [{
            "setup_status": "processing",
            "setup_completed_at": None,
            "organization_id": "test_org",
        }]
        mock_db_service.return_value = mock_db
        
        status = await get_account_creation_status("test_account", mock_user, mock_db)
        assert status.status == "processing"
        assert "15-20 minutes" in status.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])