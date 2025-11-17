"""Unit tests for chat conversation context formatting."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from kene_api.auth.models import UserContext
from kene_api.routers.chat import AgentEngineClient, ChatMessage


class TestConversationContext:
    """Test conversation context formatting in chat messages."""

    @pytest.mark.asyncio
    async def test_single_message_no_context(self):
        """Test that single messages are sent without context."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        # Mock session service
        client._session_service.get_or_create_session = AsyncMock(
            return_value="test-session-id"
        )

        # Mock agent engine stream_query
        mock_response = [{"content": {"parts": [{"text": "Response"}]}}]
        client._agent_engine.stream_query = MagicMock(return_value=iter(mock_response))

        # Single message
        messages = [ChatMessage(role="user", content="Hello, how are you?")]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",            permissions={},
            organization_permissions={},
        )

        # Call the method
        result, session_id = await client.chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        )

        # Verify the message sent to agent engine doesn't include context
        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        assert call_args[1]["message"] == "Hello, how are you?"
        assert "Previous conversation:" not in call_args[1]["message"]

    @pytest.mark.asyncio
    async def test_multiple_messages_includes_context(self):
        """Test that multiple messages include conversation context."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        # Mock session service
        client._session_service.get_or_create_session = AsyncMock(
            return_value="test-session-id"
        )

        # Mock agent engine stream_query
        mock_response = [{"content": {"parts": [{"text": "I can help with that"}]}}]
        client._agent_engine.stream_query = MagicMock(return_value=iter(mock_response))

        # Multiple messages simulating a conversation
        messages = [
            ChatMessage(role="user", content="What is Python?"),
            ChatMessage(role="assistant", content="Python is a programming language."),
            ChatMessage(role="user", content="Can you give me an example?"),
        ]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",            permissions={},
            organization_permissions={},
        )

        # Call the method
        result, session_id = await client.chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        )

        # Verify the formatted message includes context
        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        formatted_message = call_args[1]["message"]

        assert "Previous conversation:" in formatted_message
        assert "User: What is Python?" in formatted_message
        assert "Assistant: Python is a programming language." in formatted_message
        assert "Current message: Can you give me an example?" in formatted_message

    @pytest.mark.asyncio
    async def test_streaming_includes_context(self):
        """Test that streaming endpoint also includes conversation context."""
        client = AgentEngineClient()
        client._agent_engine = MagicMock()
        client._session_service = AsyncMock()

        # Mock session service
        client._session_service.get_or_create_session = AsyncMock(
            return_value="test-session-id"
        )

        # Mock agent engine stream_query for streaming
        def mock_stream():
            yield {"content": {"parts": [{"text": "Streaming "}]}}
            yield {"content": {"parts": [{"text": "response"}]}}

        client._agent_engine.stream_query = MagicMock(return_value=mock_stream())

        # Multiple messages
        messages = [
            ChatMessage(role="user", content="Tell me about AI"),
            ChatMessage(
                role="assistant", content="AI stands for Artificial Intelligence."
            ),
            ChatMessage(role="user", content="What are its applications?"),
        ]

        user_context = UserContext(
            user_id="test-user",
            email="test@example.com",            permissions={},
            organization_permissions={},
        )

        # Collect streaming responses
        responses = []
        async for chunk in client.stream_chat_completion(
            messages=messages, user_context=user_context, session_id="test-session"
        ):
            responses.append(chunk)

        # Verify context was included
        client._agent_engine.stream_query.assert_called_once()
        call_args = client._agent_engine.stream_query.call_args
        formatted_message = call_args[1]["message"]

        assert "Previous conversation:" in formatted_message
        assert "User: Tell me about AI" in formatted_message
        assert "Assistant: AI stands for Artificial Intelligence." in formatted_message
        assert "Current message: What are its applications?" in formatted_message

        # Verify we got streaming responses
        assert len(responses) > 0

    def test_context_formatting_preserves_message_order(self):
        """Test that conversation context preserves the correct message order."""
        messages = [
            ChatMessage(role="user", content="First question"),
            ChatMessage(role="assistant", content="First answer"),
            ChatMessage(role="user", content="Second question"),
            ChatMessage(role="assistant", content="Second answer"),
            ChatMessage(role="user", content="Third question"),
        ]

        # Extract conversation context (all but last message)
        conversation_context = []
        for msg in messages[:-1]:
            role_label = "User" if msg.role == "user" else "Assistant"
            conversation_context.append(f"{role_label}: {msg.content}")

        context_str = "\n".join(conversation_context)
        formatted_input = f"Previous conversation:\n{context_str}\n\nCurrent message: {messages[-1].content}"

        # Verify order is preserved
        lines = formatted_input.split("\n")
        assert lines[1] == "User: First question"
        assert lines[2] == "Assistant: First answer"
        assert lines[3] == "User: Second question"
        assert lines[4] == "Assistant: Second answer"
        assert "Current message: Third question" in formatted_input
