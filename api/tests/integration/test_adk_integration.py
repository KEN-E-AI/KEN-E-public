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

"""Integration tests for ADK (Agent Development Kit) functionality."""

import logging
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add src to path so imports work in Cloud Build
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from kene_api.routers.chat import AgentEngineClient


@pytest.fixture
def mock_vertexai():
    """Mock the Vertex AI initialization and Client."""
    with patch("kene_api.routers.chat.vertexai") as mock:
        # Mock vertexai.init
        mock.init = MagicMock()

        # Create a mock Client instance
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_engine.name = "test-agent-engine"
        mock_engine.display_name = "Test Agent Engine"

        # Set up client.agent_engines.get(name=...) to return mock engine
        mock_client.agent_engines.get = MagicMock(return_value=mock_engine)

        # Mock vertexai.Client() to return our mock client
        mock.Client = MagicMock(return_value=mock_client)

        yield mock


@pytest.fixture
def mock_agent_engines():
    """Mock the agent_engines module (legacy - kept for backward compatibility).

    NOTE: agent_engines import was removed from chat.py in session state refactor.
    This fixture is now a no-op but kept for backward compatibility with existing tests.
    """
    # No-op fixture - agent_engines no longer used in chat.py
    yield None


@pytest.fixture
def mock_session_service():
    """Mock the ADK Session Service."""
    with patch("kene_api.routers.chat.VertexAiSessionService") as mock_class:
        mock_service = MagicMock()

        # Mock session operations
        mock_service.create_session = MagicMock(
            return_value=MagicMock(id="test-session-123")
        )
        mock_service.get_session = MagicMock(return_value=None)
        mock_service.list_sessions = MagicMock(return_value=[])

        mock_class.return_value = mock_service
        yield mock_service


def test_agent_engine_initialization(mock_vertexai, mock_agent_engines):
    """
    Test that the Agent Engine initializes correctly.
    """
    with (
        patch.dict(
            os.environ,
            {
                "GOOGLE_CLOUD_PROJECT_ID": "test-project",
                "VERTEX_AI_LOCATION": "us-central1",
                "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
            },
        ),
        patch("shared.secrets.get_env_or_secret") as mock_get_env,
    ):
        # Mock get_env_or_secret to return the test engine ID
        def side_effect(key):
            if key == "KEN_E_ENGINE_ID":
                return None  # Fallback to VERTEX_AI_AGENT_ENGINE_ID
            elif key == "VERTEX_AI_AGENT_ENGINE_ID":
                return "projects/test/locations/us-central1/reasoningEngines/test-id"
            return None

        mock_get_env.side_effect = side_effect

        client = AgentEngineClient()

        # Trigger lazy loading of agent engine
        engine = client.agent_engine

        # Verify initialization
        assert engine is not None, "Agent engine should be initialized"
        mock_vertexai.init.assert_called_once_with(
            project="test-project", location="us-central1"
        )

        # Verify Client was created with correct parameters
        mock_vertexai.Client.assert_called_once_with(
            project="test-project", location="us-central1"
        )

        # Verify client.agent_engines.get() was called with the full resource name
        mock_client = mock_vertexai.Client.return_value
        mock_client.agent_engines.get.assert_called_once_with(
            name="projects/test/locations/us-central1/reasoningEngines/test-id"
        )


def test_session_service_initialization(
    mock_vertexai, mock_agent_engines, mock_session_service
):
    """
    Test that the Session Service initializes correctly.
    """
    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
        },
    ):
        client = AgentEngineClient()

        # Trigger lazy loading of session service
        service = client.session_service

        # Verify initialization
        assert service is not None, "Session service should be initialized"


@pytest.mark.asyncio
async def test_session_creation(
    mock_vertexai, mock_agent_engines, mock_session_service
):
    """
    Test session creation functionality.
    """
    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
        },
    ):
        client = AgentEngineClient()
        client._session_service = mock_session_service

        # Test session creation
        session_id = await client.get_or_create_session(
            user_id="test-user", session_id=None
        )

        assert session_id is not None, "Should create a session"
        # Verify session service was called
        mock_session_service.create_session.assert_called()


@pytest.mark.asyncio
async def test_conversation_listing(
    mock_vertexai, mock_agent_engines, mock_session_service
):
    """
    Test listing conversations functionality.
    """
    # Mock session list response with async function
    now = datetime.now(timezone.utc)
    mock_sessions = [
        MagicMock(
            id="session-1",
            display_name="Test Conversation 1",
            create_time=now,
            update_time=now,
        ),
        MagicMock(
            id="session-2",
            display_name="Test Conversation 2",
            create_time=now,
            update_time=now,
        ),
    ]

    # Create async mock for list_sessions
    async def mock_list_sessions(*args, **kwargs):
        return mock_sessions

    mock_session_service.list_sessions = mock_list_sessions

    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
        },
    ):
        client = AgentEngineClient()
        client._session_service = mock_session_service

        conversations = await client.get_user_conversations(user_id="test-user")

        assert len(conversations) == 2, "Should return two conversations"
        assert conversations[0].session_id == "session-1"
        assert (
            conversations[0].conversation_name == "Chat ession-1"
        )  # Default format is "Chat {session_id[-8:]}"
        assert conversations[1].session_id == "session-2"
        assert conversations[1].conversation_name == "Chat ession-2"


@pytest.mark.asyncio
async def test_conversation_history(
    mock_vertexai, mock_agent_engines, mock_session_service
):
    """
    Test retrieving conversation history.
    """
    # Mock session with history in ADK format
    mock_session = MagicMock()
    mock_session.events = [
        MagicMock(
            content=MagicMock(role="user", parts=[MagicMock(text="User message 1")]),
            timestamp="2025-01-01T00:00:00Z",
        ),
        MagicMock(
            content=MagicMock(
                role="assistant", parts=[MagicMock(text="AI response 1")]
            ),
            timestamp="2025-01-01T00:00:01Z",
        ),
    ]

    # Create async mock for get_session
    async def mock_get_session(*args, **kwargs):
        return mock_session

    mock_session_service.get_session = mock_get_session

    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
        },
    ):
        client = AgentEngineClient()
        client._session_service = mock_session_service

        history = await client.get_conversation_history(
            user_id="test-user", session_id="test-session"
        )

        assert history is not None, "Should return history"
        assert history["session_id"] == "test-session"
        assert len(history["events"]) == 2, "Should return two events"
        assert history["events"][0]["role"] == "user"
        assert history["events"][0]["content"]["parts"][0]["text"] == "User message 1"
        assert history["events"][1]["role"] == "assistant"
        assert history["events"][1]["content"]["parts"][0]["text"] == "AI response 1"


def test_missing_agent_engine_handling():
    """
    Test handling when no agent engine is configured.
    """
    # Mock get_env_or_secret to return None for engine IDs
    with patch("shared.secrets.get_env_or_secret") as mock_get_secret:
        mock_get_secret.return_value = None

        env_patch = {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
        }

        # Clear engine ID environment variables
        with patch.dict(os.environ, env_patch, clear=False):
            for key in ["VERTEX_AI_AGENT_ENGINE_ID", "KEN_E_ENGINE_ID"]:
                if key in os.environ:
                    del os.environ[key]

            client = AgentEngineClient()

            # Agent engine should be None
            assert client.agent_engine is None, (
                "Agent engine should be None when not configured"
            )


@pytest.mark.asyncio
async def test_error_handling():
    """
    Test error handling in various scenarios.
    """
    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "us-central1",
            "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/test-id",
        },
    ):
        # Test with agent engine that raises an error
        # NOTE: agent_engines import removed in session state refactor
        # Now using vertexai.Client().agent_engines.get() pattern
        with patch("vertexai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.agent_engines.get.side_effect = Exception(
                "Failed to connect to Agent Engine"
            )
            mock_client_class.return_value = mock_client

            client = AgentEngineClient()

            # The code raises an HTTPException when agent engine fails to initialize
            # This is the expected behavior for production
            import pytest
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                engine = client.agent_engine

            assert exc_info.value.status_code == 503, (
                "Should raise 503 Service Unavailable"
            )
            assert "Agent Engine is currently unavailable" in str(exc_info.value.detail)


def test_response_parsing():
    """
    Test parsing of ADK response structure.
    """
    # Test the nested response structure parsing
    test_response = {
        "content": {"parts": [{"text": "Test response text"}]},
        "grounding_metadata": {},
        "usage_metadata": {},
        "invocation_id": "test-123",
        "author": "assistant",
    }

    # Extract text from the nested structure
    content = test_response.get("content", {})
    parts = content.get("parts", [])
    text = parts[0].get("text", "") if parts else ""

    assert text == "Test response text", (
        "Should correctly parse nested response structure"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])
