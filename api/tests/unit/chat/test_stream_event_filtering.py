"""Regression tests for CH-59: contentless ADK control events must never be
streamed to the chat client as text.

The root agent emits a content-free *state-delta* event at the start of every
turn — ADK flushes a ``before_agent_callback`` state write as an ``Event``
carrying ``actions.state_delta`` but no ``content``/``parts`` (base_agent.py
:482). Agent Engine serialises that to a dict-shaped ``stream_query`` chunk.
Both chat response handlers must skip such events; previously they fell through
to ``str(chunk)`` and dumped the raw event dict into the reply (CH-59).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.auth.models import UserContext
from src.kene_api.routers import chat as chat_module
from src.kene_api.routers.chat import AgentEngineClient, ChatMessage

# A contentless state-delta event, shaped exactly like the chunk Agent Engine's
# stream_query serialises from the root agent's before_agent_callback state
# write (the JSON blob reported in CH-59): no `content`, no `parts`.
STATE_DELTA_EVENT: dict[str, Any] = {
    "invocation_id": "e-48c1f20e-d079-40e9-aed5-e0a280d6496e",
    "author": "ken_e",
    "actions": {
        "state_delta": {
            "active_skill_id": None,
            "_available_specialists": [
                {
                    "name": "brand_guardian",
                    "description": "Ensures brand consistency across all communications",
                    "agent_id": "brand_guardian",
                },
            ],
        },
        "artifact_delta": {},
        "requested_auth_configs": {},
        "requested_tool_confirmations": {},
    },
    "id": "f6b2bac0-1b63-4e70-9d80-51b7c43f9289",
    "timestamp": 1780054954.1730509,
}

TEXT_EVENT: dict[str, Any] = {
    "content": {"parts": [{"text": "Here's how to start a business."}]}
}

_ANSWER = "Here's how to start a business."


def _make_client(stream_chunks: list[Any]) -> AgentEngineClient:
    client = AgentEngineClient()
    client._agent_engine = MagicMock()
    client._session_service = AsyncMock()
    client._agent_engine.stream_query = MagicMock(return_value=iter(stream_chunks))
    return client


def _user_context() -> UserContext:
    return UserContext(
        user_id="test-user",
        email="test@example.com",
        organization_permissions={},
    )


@pytest.fixture(autouse=True)
def _no_redis():
    """Keep the session lookup hermetic — no Redis dependency."""
    fake = MagicMock()
    fake.is_available.return_value = False
    with patch.object(chat_module, "get_redis_service", return_value=fake):
        yield


class TestStreamingSkipsContentlessEvents:
    @pytest.mark.asyncio
    async def test_state_delta_event_is_not_streamed(self) -> None:
        """A state-delta-only event must contribute nothing to the SSE stream."""
        client = _make_client([STATE_DELTA_EVENT, TEXT_EVENT])

        responses = [
            chunk
            async for chunk in client.stream_chat_completion(
                messages=[
                    ChatMessage(role="user", content="How do I start a business?")
                ],
                user_context=_user_context(),
                session_id="test-session-ch59",
            )
        ]

        # Only the real answer reaches the client; the event dict (whose keys
        # would otherwise appear verbatim) is dropped entirely.
        assert "".join(text for _channel, text, _author in responses) == _ANSWER


class TestNonStreamingSkipsContentlessEvents:
    @pytest.mark.asyncio
    async def test_state_delta_event_is_not_in_response(self) -> None:
        """The non-streaming path must not append the raw event dict either."""
        client = _make_client([STATE_DELTA_EVENT, TEXT_EVENT])

        result, _session_id, _visualization_seen = await client.chat_completion(
            messages=[ChatMessage(role="user", content="How do I start a business?")],
            user_context=_user_context(),
            session_id="test-session-ch59-ns",
        )

        assert result == _ANSWER
