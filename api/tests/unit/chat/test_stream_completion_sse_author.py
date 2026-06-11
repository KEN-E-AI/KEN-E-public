"""Unit tests for author sidecar SSE frames emitted by _stream_completion_sse.

Verifies the SSE wire format for fan-out turns:
- Single-author ("model") turns produce zero "event: author" sidecar frames
  (backward-compat golden-file).
- Multi-author turns emit "event: author\ndata: <name>\n\n" sidecars before
  the first text frame from each new specialist.
- Reasoning frames include the "author" key in their JSON payload when the
  author differs from "model"; omit it when author is "model".
- Session frames are unaffected by author logic.

References: AH-124 SSE author-tagging for fan-out turns.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import ChatMessage, _stream_completion_sse, agent_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_context(user_id: str = "user_1") -> MagicMock:
    ctx = MagicMock()
    ctx.user_id = user_id
    return ctx


async def _collect_sse(gen: AsyncGenerator[str, None]) -> str:
    """Concatenate all SSE frames into a single string."""
    return "".join([frame async for frame in gen])


def _fake_stream(
    *tuples: tuple[str, str, str],
) -> AsyncGenerator[tuple[str, str, str], None]:
    """Return an async generator that yields the given 3-tuples."""

    async def _gen(*args: object, **kwargs: object) -> AsyncGenerator[tuple[str, str, str], None]:
        for t in tuples:
            yield t

    return _gen()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStreamCompletionSseAuthor:
    async def _run_sse(
        self,
        *tuples: tuple[str, str, str],
    ) -> str:
        """Patch agent_client.stream_chat_completion and collect SSE output."""

        async def _mock_stream(*args: object, **kwargs: object) -> AsyncGenerator[tuple[str, str, str], None]:
            for t in tuples:
                yield t

        with patch.object(
            agent_client,
            "stream_chat_completion",
            new=_mock_stream,
        ):
            with patch(
                "kene_api.routers.chat._flush_stream_turn",
                new=AsyncMock(),
            ):
                with patch(
                    "kene_api.routers.chat._maybe_set_temp_title",
                    new=AsyncMock(),
                ):
                    return await _collect_sse(
                        _stream_completion_sse(
                            messages=[ChatMessage(role="user", content="hi")],
                            user_context=_make_user_context(),
                            session_id="sess_test",
                            conversation_name=None,
                            account_id="acct_1",
                            turn_uuid="test-uuid",
                        )
                    )

    async def test_single_author_turn_no_sidecar(self) -> None:
        """A stream where author is always "model" produces no event: author frames.

        Golden-file: aside from CH-71's initial keep-alive ping, single-author
        SSE bytes are unchanged — no event: author sidecar frames.
        """
        output = await self._run_sse(("text", "hello world", "model"))
        assert output == ": ping 0\n\ndata: hello world\n\ndata: [DONE]\n\n", (
            f"Unexpected SSE output: {output!r}"
        )

    async def test_two_author_turn_emits_sidecars(self) -> None:
        """A stream with two alternating specialists emits author sidecar frames."""
        output = await self._run_sse(
            ("text", "a1", "specialist_a"),
            ("text", "b1", "specialist_b"),
            ("text", "a2", "specialist_a"),
        )

        # The first text frame from specialist_a must be preceded by its sidecar.
        assert "event: author\ndata: specialist_a\n\n" in output
        # When specialist_b takes over, its sidecar must appear.
        assert "event: author\ndata: specialist_b\n\n" in output

        # Verify ordering: specialist_a sidecar → a1 text → specialist_b sidecar → b1 text
        pos_sidecar_a = output.index("event: author\ndata: specialist_a\n\n")
        pos_text_a1 = output.index("data: a1\n\n")
        pos_sidecar_b = output.index("event: author\ndata: specialist_b\n\n")
        pos_text_b1 = output.index("data: b1\n\n")

        assert pos_sidecar_a < pos_text_a1, "specialist_a sidecar must precede a1 text"
        assert pos_text_a1 < pos_sidecar_b, "a1 text must precede specialist_b sidecar"
        assert pos_sidecar_b < pos_text_b1, "specialist_b sidecar must precede b1 text"

        # specialist_a appears a second time (a2) — no new sidecar since author
        # already changed back from specialist_b to specialist_a.
        # Count occurrences of specialist_a sidecar: exactly once before a1, then
        # again before a2 (because _current_author is specialist_b at that point).
        sidecar_a_count = output.count("event: author\ndata: specialist_a\n\n")
        assert sidecar_a_count == 2, (
            f"Expected 2 specialist_a sidecars (one per switch), got {sidecar_a_count}"
        )

    async def test_reasoning_gets_author_in_json(self) -> None:
        """A reasoning frame from a non-model specialist includes "author" in its JSON."""
        output = await self._run_sse(("reasoning", "thinking", "specialist_a"))

        assert "event: reasoning\n" in output
        data_line = output.split("data: ", 1)[1].split("\n\n")[0]
        payload = json.loads(data_line)
        assert payload == {"text": "thinking", "seq": 0, "author": "specialist_a"}, (
            f"Unexpected reasoning payload: {payload}"
        )

    async def test_reasoning_default_author_no_author_key(self) -> None:
        """A reasoning frame from "model" must NOT include an "author" key in its JSON."""
        output = await self._run_sse(("reasoning", "thinking", "model"))

        assert "event: reasoning\n" in output
        data_line = output.split("data: ", 1)[1].split("\n\n")[0]
        payload = json.loads(data_line)
        assert payload == {"text": "thinking", "seq": 0}, (
            f"Expected no 'author' key for model reasoning, got: {payload}"
        )
        assert "author" not in payload

    async def test_session_frame_unaffected(self) -> None:
        """A session tuple produces the standard event: session frame, unaffected by author."""
        output = await self._run_sse(("session", "sess_123", "model"))

        assert "event: session\n" in output
        data_line = output.split("event: session\ndata: ", 1)[1].split("\n\n")[0]
        payload = json.loads(data_line)
        assert payload == {"session_id": "sess_123"}, (
            f"Unexpected session payload: {payload}"
        )
        # No author sidecar for session events.
        assert "event: author" not in output

    async def test_author_name_with_newlines_is_stripped(self) -> None:
        """An author name containing newlines must NOT produce multiple SSE lines.

        Guards against SSE frame injection: 'name\\nevent: session\\ndata: ...'
        would otherwise be parsed as two separate events by the client.
        """
        injected = "malicious\nevent: session\ndata: {\"session_id\": \"evil\"}"
        output = await self._run_sse(("text", "hello", injected))

        # The sidecar frame must be a single data line with no embedded newlines.
        assert "event: author\n" in output
        # Locate the sidecar and verify the data field has no embedded \n or \r.
        sidecar_start = output.index("event: author\n")
        sidecar_end = output.index("\n\n", sidecar_start)
        sidecar_frame = output[sidecar_start:sidecar_end]
        lines = sidecar_frame.split("\n")
        # Expected: ["event: author", "data: malicious event: session data: ..."]
        assert len(lines) == 2, (
            f"Author sidecar must have exactly 2 lines, got {len(lines)}: {sidecar_frame!r}"
        )
        # The injected content must not appear as a separate event.
        assert "event: session" not in output[sidecar_end:]
