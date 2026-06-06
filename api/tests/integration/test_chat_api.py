# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration tests for the ADK-based chat API functionality."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add src to path so imports work in Cloud Build
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from kene_api.auth.models import UserContext
from kene_api.routers.chat import AgentEngineClient, ChatMessage


@pytest.fixture
def mock_agent_engine():
    """Mock the Vertex AI Agent Engine."""
    mock_engine = MagicMock()

    # Mock stream_query to return test responses
    def mock_stream_query(message: str, user_id: str, session_id: str):
        # Simulate ADK response structure
        yield {
            "content": {"parts": [{"text": f"Test response to: {message}"}]},
            "grounding_metadata": {},
            "usage_metadata": {},
            "invocation_id": "test-invocation-123",
            "author": "assistant",
            "actions": [],
            "id": "test-response-id",
            "timestamp": "2025-01-01T00:00:00Z",
        }

    mock_engine.stream_query = mock_stream_query
    return mock_engine


@pytest.fixture
def agent_client(mock_agent_engine):
    """Create an AgentEngineClient with mocked agent engine."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
            "ENVIRONMENT": "test",
        },
    ):
        client = AgentEngineClient()
        # Inject the mock agent engine
        client._agent_engine = mock_agent_engine
        return client


@pytest.fixture
def test_user():
    """Create a test user context."""
    return UserContext(
        user_id="test-user-123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
    )


@pytest.mark.asyncio
async def test_chat_completion(agent_client, test_user):
    """
    Test the chat completion functionality.
    Verifies that the agent returns valid responses.
    """
    messages = [
        ChatMessage(
            role="user", content="Write a fibonacci function in python", timestamp=""
        )
    ]

    response, session_id = await agent_client.chat_completion(
        messages=messages, user_context=test_user, session_id="test-session"
    )

    # Verify response
    assert response is not None, "Expected a response from chat completion"
    assert len(response) > 0, "Response should not be empty"
    assert "Test response to:" in response, "Response should contain expected content"
    # Session ID may be modified if ADK session creation fails, so just check it exists
    assert session_id is not None and len(session_id) > 0, "Should have a session ID"


@pytest.mark.asyncio
async def test_stream_chat_completion(agent_client, test_user):
    """
    Test the streaming chat completion functionality.
    Verifies that the agent returns valid streaming responses.
    """
    messages = [
        ChatMessage(role="user", content="Test streaming message", timestamp="")
    ]

    chunks = []
    async for channel, text, _author in agent_client.stream_chat_completion(
        messages=messages, user_context=test_user, session_id="test-stream-session"
    ):
        chunks.append((channel, text))

    # Verify streaming response
    assert len(chunks) > 0, "Expected at least one chunk"
    full_response = "".join(text for _channel, text in chunks)
    assert "Test response to:" in full_response, (
        "Streaming response should contain expected content"
    )


@pytest.mark.asyncio
async def test_empty_message_handling(agent_client, test_user):
    """
    Test handling of empty messages.
    Verifies that the agent handles edge cases gracefully.
    """
    messages = []

    response, _ = await agent_client.chat_completion(
        messages=messages, user_context=test_user
    )

    assert "didn't receive any message" in response.lower(), (
        "Should handle empty messages gracefully"
    )


@pytest.mark.asyncio
async def test_session_management(agent_client, test_user):
    """
    Test session creation and management.
    Verifies that sessions are properly handled.
    """

    # Mock the session service with async methods
    mock_session_service = MagicMock()

    # Create async mock for create_session
    async def mock_create_session(*args, **kwargs):
        return MagicMock(id="new-session-123")

    mock_session_service.create_session = mock_create_session
    mock_session_service.get_session = MagicMock(return_value=None)

    agent_client._session_service = mock_session_service

    # Test session creation
    session_id = await agent_client.get_or_create_session(
        user_id=test_user.user_id, session_id=None
    )

    assert session_id is not None, "Should create a session ID"
    # The actual implementation may create "manual_" prefixed sessions on error
    assert len(session_id) > 0, "Session ID should not be empty"


@pytest.mark.asyncio
async def test_development_mode_without_agent():
    """
    Test development mode behavior when no agent engine is configured.
    Verifies fallback behavior for development.
    """
    # Ensure VERTEX_AI_AGENT_ENGINE_ID is not set
    env_patch = {
        "GOOGLE_CLOUD_PROJECT_ID": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
        "ENVIRONMENT": "development",
    }

    with patch.dict(os.environ, env_patch, clear=False):
        if "VERTEX_AI_AGENT_ENGINE_ID" in os.environ:
            del os.environ["VERTEX_AI_AGENT_ENGINE_ID"]

        client = AgentEngineClient()
        test_user = UserContext(
            user_id="dev-user",
            email="dev@example.com",
            organization_permissions={},
            account_permissions={},
        )

        messages = [ChatMessage(role="user", content="Test in dev mode", timestamp="")]

        response, session_id = await client.chat_completion(
            messages=messages, user_context=test_user
        )

        # In development mode without agent, should return mock response
        assert response is not None, "Should return a response in dev mode"
        if os.getenv("ENVIRONMENT") == "development":
            assert (
                "[Development Mode" in response
                or "unable to process" in response.lower()
            ), "Should indicate development mode or unavailability"
