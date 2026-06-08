"""Unit tests for chat conversation context formatting.

After the latency optimization, conversation history is no longer re-injected
into the message payload. The ADK session maintains its own conversation state,
so only the latest user message is sent to the Agent Engine.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from kene_api.auth.models import UserContext
from kene_api.routers.chat import AgentEngineClient, ChatMessage


class TestConversationContext:
    """Test that only the latest message is sent to Agent Engine (ADK handles history)."""

    @pytest.mark.asyncio
    async def test_single_message_sent_directly(self):
        """Single message is sent as-is to Agent Engine."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        mock_response = [{"content": {"parts": [{"text": "Response"}]}}]
        client._agent_engine.stream_query = MagicMock(return_value=iter(mock_response))

        messages = [ChatMessage(role="user", content="Hello, how are you?")]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",
            organization_permissions={},
        )

        result, session_id, _ = await client.chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        )

        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        assert call_args[1]["message"] == "Hello, how are you?"

    @pytest.mark.asyncio
    async def test_multiple_messages_sends_only_latest(self):
        """Multiple messages should send only the latest user message (ADK has history)."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        mock_response = [{"content": {"parts": [{"text": "I can help with that"}]}}]
        client._agent_engine.stream_query = MagicMock(return_value=iter(mock_response))

        messages = [
            ChatMessage(role="user", content="What is Python?"),
            ChatMessage(role="assistant", content="Python is a programming language."),
            ChatMessage(role="user", content="Can you give me an example?"),
        ]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",
            organization_permissions={},
        )

        result, session_id, _ = await client.chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        )

        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        formatted_message = call_args[1]["message"]

        # Only the latest message is sent — no re-injected history
        assert formatted_message == "Can you give me an example?"
        assert "Previous conversation:" not in formatted_message

    @pytest.mark.asyncio
    async def test_streaming_sends_only_latest(self):
        """Streaming endpoint also sends only the latest user message."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        def mock_stream():
            yield {"content": {"parts": [{"text": "Streaming "}]}}
            yield {"content": {"parts": [{"text": "response"}]}}

        client._agent_engine.stream_query = MagicMock(return_value=mock_stream())

        messages = [
            ChatMessage(role="user", content="Tell me about AI"),
            ChatMessage(
                role="assistant", content="AI stands for Artificial Intelligence."
            ),
            ChatMessage(role="user", content="What are its applications?"),
        ]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",
            organization_permissions={},
        )

        responses = []
        async for chunk in client.stream_chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        ):
            responses.append(chunk)

        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        formatted_message = call_args[1]["message"]

        # Only the latest message is sent
        assert formatted_message == "What are its applications?"
        assert "Previous conversation:" not in formatted_message
        assert len(responses) > 0
