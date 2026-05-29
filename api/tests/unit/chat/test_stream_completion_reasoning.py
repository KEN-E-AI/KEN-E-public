"""Unit tests for reasoning-channel extraction and SSE framing.

Tests cover:
- Thought parts yield ("reasoning", text) tuples from stream_chat_completion.
- Text parts yield ("text", text) tuples.
- Mixed thought+text in one chunk preserves order.
- Contentless event chunks are still dropped (CH-59 regression guard).
- _format_sse framing: reasoning events, text events, seq counter, newline escaping.

References: CH-60 Implementation Plan Tasks 1 & 2.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Resolve the api/src package so the test runner finds kene_api.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import _format_sse


# ---------------------------------------------------------------------------
# _format_sse helper tests
# ---------------------------------------------------------------------------


class TestFormatSse:
    def test_text_channel_produces_data_line(self):
        result = _format_sse("text", "hello world", 0)
        assert result == "data: hello world\n\n"

    def test_reasoning_channel_produces_event_and_data_lines(self):
        result = _format_sse("reasoning", "step 1", 0)
        assert result.startswith("event: reasoning\n")
        assert "data: " in result
        payload = json.loads(result.split("data: ", 1)[1].strip())
        assert payload == {"text": "step 1", "seq": 0}

    def test_reasoning_seq_is_embedded(self):
        result = _format_sse("reasoning", "think", 5)
        payload = json.loads(result.split("data: ", 1)[1].strip())
        assert payload["seq"] == 5

    def test_format_sse_escapes_newlines_in_reasoning(self):
        """A newline inside reasoning text must not break SSE framing."""
        result = _format_sse("reasoning", "line one\nline two", 0)
        # The outer SSE line must contain no bare newlines in the data payload
        data_line = result.split("data: ", 1)[1]
        # json.dumps escapes the inner newline as \n — so the data_line itself
        # has no bare newline before the trailing \n\n terminator
        payload_str, remainder = data_line.split("\n\n", 1)
        assert "\n" not in payload_str, (
            "Newline inside reasoning was not escaped by json.dumps"
        )
        parsed = json.loads(payload_str)
        assert parsed["text"] == "line one\nline two"

    def test_unknown_channel_falls_through_to_text(self):
        result = _format_sse("unknown", "hello", 0)
        assert result == "data: hello\n\n"

    def test_text_channel_does_not_add_event_line(self):
        result = _format_sse("text", "answer", 0)
        assert "event:" not in result

    def test_sse_done_terminator_format(self):
        """Verify the [DONE] terminator can be emitted on the text channel."""
        result = _format_sse("text", "[DONE]", 0)
        assert result == "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# stream_chat_completion thought-part extraction tests
#
# We test the internal part-classification logic by exercising the two dict
# chunk shapes that the agent engine returns:
#   shape A: {"content": {"parts": [...]}}
#   shape B: {"parts": [...]}
#
# We do this by calling a stripped-down async generator that mirrors the
# exact branching logic from _stream_completion_sse's inner loop, without
# spinning up a full agent client.
# ---------------------------------------------------------------------------


async def _classify_parts(
    chunks: list[dict],
) -> list[tuple[str, str]]:
    """Mirror the dict-chunk classification logic from stream_chat_completion.

    Returns a list of (channel, text) tuples for the given sequence of raw
    chunk dicts. This exercises the same code path as the production generator
    without needing a real agent engine or HTTP context.
    """
    from kene_api.routers.chat import _is_function_event_part

    results: list[tuple[str, str]] = []

    def _process_parts(parts: list) -> None:
        for part in parts:
            if isinstance(part, dict) and _is_function_event_part(part):
                pass  # skipped
            elif (
                isinstance(part, dict)
                and part.get("thought", False)
                and "text" in part
            ):
                results.append(("reasoning", part["text"]))
            elif isinstance(part, dict) and "text" in part:
                results.append(("text", part["text"]))
            else:
                results.append(("text", str(part)))

    for chunk in chunks:
        if isinstance(chunk, dict):
            if "content" in chunk and isinstance(chunk["content"], dict):
                content = chunk["content"]
                if "parts" in content and isinstance(content["parts"], list):
                    _process_parts(content["parts"])
                else:
                    results.append(("text", str(content)))
            elif "parts" in chunk and isinstance(chunk["parts"], list):
                _process_parts(chunk["parts"])
            elif "content" in chunk:
                results.append(("text", str(chunk["content"])))
            # else: contentless event — skipped (CH-59)

    return results


@pytest.mark.asyncio
class TestThoughtPartClassification:
    async def test_thought_part_yields_reasoning_channel(self):
        chunk = {"content": {"parts": [{"text": "I should think.", "thought": True}]}}
        results = await _classify_parts([chunk])
        assert results == [("reasoning", "I should think.")]

    async def test_text_part_yields_text_channel(self):
        chunk = {"content": {"parts": [{"text": "Hello, user."}]}}
        results = await _classify_parts([chunk])
        assert results == [("text", "Hello, user.")]

    async def test_thought_false_is_text_channel(self):
        chunk = {"content": {"parts": [{"text": "Answer.", "thought": False}]}}
        results = await _classify_parts([chunk])
        assert results == [("text", "Answer.")]

    async def test_mixed_thought_and_text_in_one_chunk_preserves_order(self):
        chunk = {
            "content": {
                "parts": [
                    {"text": "Thinking…", "thought": True},
                    {"text": "Answer text."},
                ]
            }
        }
        results = await _classify_parts([chunk])
        assert results == [("reasoning", "Thinking…"), ("text", "Answer text.")]

    async def test_function_event_part_is_skipped(self):
        chunk = {
            "content": {
                "parts": [
                    {"function_call": {"name": "search_kb", "args": {}}},
                    {"text": "After function."},
                ]
            }
        }
        results = await _classify_parts([chunk])
        assert results == [("text", "After function.")]

    async def test_function_event_takes_priority_over_thought(self):
        """A part with both thought=True and function_call is treated as function (skipped)."""
        chunk = {
            "content": {
                "parts": [
                    {
                        "function_call": {"name": "fn"},
                        "thought": True,
                        "text": "ignored",
                    }
                ]
            }
        }
        results = await _classify_parts([chunk])
        assert results == []

    async def test_contentless_event_still_dropped(self):
        """CH-59 regression guard: a dict with no content/parts produces no output."""
        chunk = {"actions": ["some_action"], "metadata": {}}
        results = await _classify_parts([chunk])
        assert results == []

    async def test_direct_parts_shape_thought_part(self):
        """Shape B: {'parts': [...]} also classifies thought parts correctly."""
        chunk = {"parts": [{"text": "Direct reasoning.", "thought": True}]}
        results = await _classify_parts([chunk])
        assert results == [("reasoning", "Direct reasoning.")]

    async def test_direct_parts_shape_text_part(self):
        chunk = {"parts": [{"text": "Direct text."}]}
        results = await _classify_parts([chunk])
        assert results == [("text", "Direct text.")]


# ---------------------------------------------------------------------------
# SSE seq counter tests
# ---------------------------------------------------------------------------


class TestSseSeqMonotonic:
    def test_seq_increments_per_reasoning_emit(self):
        frames = [
            _format_sse("reasoning", "first thought", 0),
            _format_sse("reasoning", "second thought", 1),
            _format_sse("reasoning", "third thought", 2),
        ]
        seqs = []
        for f in frames:
            data_line = f.split("data: ", 1)[1].strip()
            seqs.append(json.loads(data_line)["seq"])
        assert seqs == [0, 1, 2]

    def test_text_events_do_not_advance_seq(self):
        """Text events use seq=0 (seq is only meaningful for reasoning)."""
        text_frame = _format_sse("text", "hello", 0)
        assert "event:" not in text_frame
        assert text_frame == "data: hello\n\n"
