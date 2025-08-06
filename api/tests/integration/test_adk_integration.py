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

import os
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.kene_api.routers.chat import AgentEngineClient, ChatMessage
from src.kene_api.auth.models import UserContext


@pytest.fixture
def mock_vertexai():
    """Mock the Vertex AI initialization."""
    with patch('src.kene_api.routers.chat.vertexai') as mock:
        mock.init = MagicMock()
        yield mock


@pytest.fixture
def mock_agent_engines():
    """Mock the agent_engines module."""
    with patch('src.kene_api.routers.chat.agent_engines') as mock:
        # Create a mock agent engine
        mock_engine = MagicMock()
        mock_engine.name = "test-agent-engine"
        mock_engine.display_name = "Test Agent Engine"
        
        # Mock the get method to return our mock engine
        mock.get = MagicMock(return_value=mock_engine)
        
        yield mock


@pytest.fixture
def mock_session_service():
    """Mock the ADK Session Service."""
    with patch('src.kene_api.routers.chat.VertexAiSessionService') as mock_class:
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
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        client = AgentEngineClient()
        
        # Trigger lazy loading of agent engine
        engine = client.agent_engine
        
        # Verify initialization
        assert engine is not None, "Agent engine should be initialized"
        mock_vertexai.init.assert_called_once_with(
            project='test-project',
            location='us-central1'
        )
        mock_agent_engines.get.assert_called_once()


def test_session_service_initialization(mock_vertexai, mock_agent_engines, mock_session_service):
    """
    Test that the Session Service initializes correctly.
    """
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        client = AgentEngineClient()
        
        # Trigger lazy loading of session service
        service = client.session_service
        
        # Verify initialization
        assert service is not None, "Session service should be initialized"


@pytest.mark.asyncio
async def test_session_creation(mock_vertexai, mock_agent_engines, mock_session_service):
    """
    Test session creation functionality.
    """
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        client = AgentEngineClient()
        client._session_service = mock_session_service
        
        # Test session creation
        session_id = await client.get_or_create_session(
            user_id="test-user",
            session_id=None
        )
        
        assert session_id is not None, "Should create a session"
        # Verify session service was called
        mock_session_service.create_session.assert_called()


@pytest.mark.asyncio
async def test_conversation_listing(mock_vertexai, mock_agent_engines, mock_session_service):
    """
    Test listing conversations functionality.
    """
    # Mock session list response
    mock_sessions = [
        MagicMock(
            id="session-1",
            display_name="Test Conversation 1",
            create_time=MagicMock(timestamp=lambda: 1234567890),
            update_time=MagicMock(timestamp=lambda: 1234567890)
        ),
        MagicMock(
            id="session-2",
            display_name="Test Conversation 2",
            create_time=MagicMock(timestamp=lambda: 1234567891),
            update_time=MagicMock(timestamp=lambda: 1234567891)
        )
    ]
    mock_session_service.list_sessions.return_value = mock_sessions
    
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        client = AgentEngineClient()
        client._session_service = mock_session_service
        
        conversations = await client.get_conversations(user_id="test-user")
        
        assert len(conversations) == 2, "Should return two conversations"
        assert conversations[0]["session_id"] == "session-1"
        assert conversations[0]["conversation_name"] == "Test Conversation 1"
        assert conversations[1]["session_id"] == "session-2"


@pytest.mark.asyncio
async def test_conversation_history(mock_vertexai, mock_agent_engines, mock_session_service):
    """
    Test retrieving conversation history.
    """
    # Mock session with history
    mock_session = MagicMock()
    mock_session.session_chunks = [
        MagicMock(node_responses=[
            MagicMock(
                text="User message 1",
                metadata={"role": "user", "timestamp": "2025-01-01T00:00:00Z"}
            ),
            MagicMock(
                text="AI response 1",
                metadata={"role": "assistant", "timestamp": "2025-01-01T00:00:01Z"}
            )
        ])
    ]
    mock_session_service.get_session.return_value = mock_session
    
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        client = AgentEngineClient()
        client._session_service = mock_session_service
        
        history = await client.get_conversation_history(
            user_id="test-user",
            session_id="test-session"
        )
        
        assert len(history) == 2, "Should return two messages"
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "User message 1"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "AI response 1"


def test_missing_agent_engine_handling():
    """
    Test handling when no agent engine is configured.
    """
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1'
        # No VERTEX_AI_AGENT_ENGINE_ID set
    }):
        client = AgentEngineClient()
        
        # Agent engine should be None
        assert client.agent_engine is None, "Agent engine should be None when not configured"


@pytest.mark.asyncio
async def test_error_handling():
    """
    Test error handling in various scenarios.
    """
    with patch.dict(os.environ, {
        'GOOGLE_CLOUD_PROJECT_ID': 'test-project',
        'VERTEX_AI_LOCATION': 'us-central1',
        'VERTEX_AI_AGENT_ENGINE_ID': 'projects/test/locations/us-central1/reasoningEngines/test-id'
    }):
        # Test with agent engine that raises an error
        with patch('src.kene_api.routers.chat.agent_engines.get') as mock_get:
            mock_get.side_effect = Exception("Failed to connect to Agent Engine")
            
            client = AgentEngineClient()
            
            # Should handle the error gracefully
            engine = client.agent_engine
            assert engine is None, "Should return None when agent engine fails to initialize"


def test_response_parsing():
    """
    Test parsing of ADK response structure.
    """
    # Test the nested response structure parsing
    test_response = {
        'content': {
            'parts': [{'text': 'Test response text'}]
        },
        'grounding_metadata': {},
        'usage_metadata': {},
        'invocation_id': 'test-123',
        'author': 'assistant'
    }
    
    # Extract text from the nested structure
    content = test_response.get('content', {})
    parts = content.get('parts', [])
    text = parts[0].get('text', '') if parts else ''
    
    assert text == 'Test response text', "Should correctly parse nested response structure"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])