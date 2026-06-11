"""Unit tests for the streaming-completion side-table flush (CH-PRD-01 §7 AC-8).

Covers `_flush_stream_turn` (the finally-block flush logic) and drives the real
`_stream_completion_sse` async generator to genuine mid-stream cancellation via
`aclose()` — proving a cancelled stream still records `last_agent_stopped_at`
and its partial token counts.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore_v1.transforms import Increment
from src.kene_api.chat.accumulator import SessionTurnAccumulator
from src.kene_api.routers import chat as chat_module


def _stream_chunk(invocation_id: str, prompt: int, candidates: int) -> dict[str, Any]:
    """Build a JSON-shaped Agent Engine stream_query chunk."""
    return {
        "invocation_id": invocation_id,
        "usage_metadata": {
            "prompt_token_count": prompt,
            "candidates_token_count": candidates,
            "thoughts_token_count": 0,
            "cached_content_token_count": 0,
        },
        "content": {"parts": [{"text": "chunk"}]},
    }


def _make_fake_stream(chunks: list[Any]):
    """Return a stand-in for AgentEngineClient.stream_chat_completion.

    Mirrors the real generator: feeds each raw chunk to the accumulator before
    yielding a ``(channel, text, author)`` fragment on the "text" channel.
    """

    async def _fake_stream(
        *, accumulator: SessionTurnAccumulator | None = None, **_kwargs: Any
    ):
        for chunk in chunks:
            if accumulator is not None:
                accumulator.add_stream_chunk(chunk)
            yield ("text", "chunk-text", "model")

    return _fake_stream


# ---------------------------------------------------------------------------
# _flush_stream_turn
# ---------------------------------------------------------------------------


class TestFlushStreamTurn:
    @pytest.mark.asyncio
    async def test_failed_turn_with_invocation_id_flushes_partial_counts(self) -> None:
        """A cancelled turn flushes partial token counts under the shared key."""
        accumulator = SessionTurnAccumulator()
        accumulator.add_stream_chunk(_stream_chunk("inv-9", prompt=500, candidates=120))

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            await chat_module._flush_stream_turn(
                session_id="sess-9",
                account_id="acc-9",
                accumulator=accumulator,
                turn_failed=True,
                turn_uuid="turn-uuid-9",
            )

        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args.kwargs
        assert kwargs["idempotency_key"] == "sess-9:turn:inv-9"
        delta = kwargs["delta"]
        assert "last_agent_stopped_at" in delta
        assert delta["input_tokens_total"].value == 500
        assert delta["output_tokens_total"].value == 120
        assert delta["current_context_tokens"].value == 620

    @pytest.mark.asyncio
    async def test_clean_turn_writes_stop_stamp_only(self) -> None:
        """A clean turn writes only the stop-stamp under the distinct api-finally key."""
        accumulator = SessionTurnAccumulator()
        accumulator.add_stream_chunk(
            _stream_chunk("inv-clean", prompt=999, candidates=999)
        )

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            await chat_module._flush_stream_turn(
                session_id="sess-clean",
                account_id="acc-clean",
                accumulator=accumulator,
                turn_failed=False,
                turn_uuid="turn-uuid-clean",
            )

        kwargs = mock_apply.call_args.kwargs
        assert kwargs["idempotency_key"] == "sess-clean:api-finally:turn-uuid-clean"
        # Clean path ignores the accumulator — stop-stamp only, no token counters.
        assert set(kwargs["delta"].keys()) == {"last_agent_stopped_at", "updated_at"}

    @pytest.mark.asyncio
    async def test_failed_turn_without_invocation_id_falls_back_to_stop_stamp(
        self,
    ) -> None:
        """A failure before any chunk arrived has no invocation id — stop-stamp only."""
        accumulator = SessionTurnAccumulator()  # no chunks → invocation_id is None

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            await chat_module._flush_stream_turn(
                session_id="sess-noinv",
                account_id="acc-noinv",
                accumulator=accumulator,
                turn_failed=True,
                turn_uuid="turn-uuid-noinv",
            )

        kwargs = mock_apply.call_args.kwargs
        assert kwargs["idempotency_key"] == "sess-noinv:api-finally:turn-uuid-noinv"
        assert set(kwargs["delta"].keys()) == {"last_agent_stopped_at", "updated_at"}

    @pytest.mark.asyncio
    async def test_pending_session_is_skipped(self) -> None:
        mock_apply = MagicMock()
        with patch.object(chat_module, "apply_side_table_update", mock_apply):
            await chat_module._flush_stream_turn(
                session_id="pending_abc",
                account_id="acc-1",
                accumulator=SessionTurnAccumulator(),
                turn_failed=True,
                turn_uuid="t",
            )
        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_account_id_is_skipped(self) -> None:
        mock_apply = MagicMock()
        with patch.object(chat_module, "apply_side_table_update", mock_apply):
            await chat_module._flush_stream_turn(
                session_id="sess-1",
                account_id="",
                accumulator=SessionTurnAccumulator(),
                turn_failed=True,
                turn_uuid="t",
            )
        mock_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_side_table_failure_never_raises(self) -> None:
        """A side-table error must not surface to the SSE client."""
        mock_apply = MagicMock(side_effect=RuntimeError("firestore down"))
        with (
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            # Must not raise.
            await chat_module._flush_stream_turn(
                session_id="sess-err",
                account_id="acc-err",
                accumulator=SessionTurnAccumulator(),
                turn_failed=False,
                turn_uuid="t",
            )


# ---------------------------------------------------------------------------
# _stream_completion_sse — genuine mid-stream cancellation
# ---------------------------------------------------------------------------


class TestStreamCompletionCancellation:
    @pytest.mark.asyncio
    async def test_cancellation_mid_stream_flushes_partial_token_counts(self) -> None:
        """Consume two chunks, cancel via aclose() — partial counts must persist (AC-8)."""
        chunks = [
            _stream_chunk("inv-cancel", prompt=500, candidates=120),
            _stream_chunk("inv-cancel", prompt=0, candidates=80),
            # Never consumed — its tokens must NOT appear in the flushed delta.
            _stream_chunk("inv-cancel", prompt=9999, candidates=9999),
        ]
        mock_apply = MagicMock(return_value={"status": "applied"})

        with (
            patch.object(
                chat_module.agent_client,
                "stream_chat_completion",
                _make_fake_stream(chunks),
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-cancel",
                conversation_name=None,
                account_id="acc-cancel",
                turn_uuid="turn-uuid-1",
            )
            # CH-71: every stream leads with an initial keep-alive ping.
            assert await gen.__anext__() == ": ping 0\n\n"
            assert await gen.__anext__() == "data: chunk-text\n\n"
            assert await gen.__anext__() == "data: chunk-text\n\n"
            # Client disconnects mid-stream.
            await gen.aclose()

        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args.kwargs
        # AC-8: partial counts flushed under the shared per-turn key.
        assert kwargs["idempotency_key"] == "sess-cancel:turn:inv-cancel"
        delta = kwargs["delta"]
        assert "last_agent_stopped_at" in delta
        # Only the first two chunks were consumed: input=500, output=120+80=200.
        assert delta["input_tokens_total"].value == 500
        assert delta["output_tokens_total"].value == 200
        assert delta["current_context_tokens"].value == 700
        # The unconsumed third chunk's 9999 tokens must not be counted.
        assert isinstance(delta["input_tokens_total"], Increment)

    @pytest.mark.asyncio
    async def test_clean_completion_writes_stop_stamp_only(self) -> None:
        """A fully-consumed stream takes the clean path — after_agent_callback owns counters."""
        chunks = [_stream_chunk("inv-clean", prompt=300, candidates=90)]
        mock_apply = MagicMock(return_value={"status": "applied"})

        with (
            patch.object(
                chat_module.agent_client,
                "stream_chat_completion",
                _make_fake_stream(chunks),
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-done",
                conversation_name=None,
                account_id="acc-done",
                turn_uuid="turn-uuid-2",
            )
            collected = [item async for item in gen]

        assert collected[-1] == "data: [DONE]\n\n"
        kwargs = mock_apply.call_args.kwargs
        assert kwargs["idempotency_key"] == "sess-done:api-finally:turn-uuid-2"
        assert set(kwargs["delta"].keys()) == {"last_agent_stopped_at", "updated_at"}

    @pytest.mark.asyncio
    async def test_agent_failure_mid_stream_flushes_partial_counts(self) -> None:
        """An agent-side exception is a failed turn — error frame emitted, partial counts flushed."""

        async def _failing_stream(
            *, accumulator: SessionTurnAccumulator | None = None, **_kwargs: Any
        ):
            if accumulator is not None:
                accumulator.add_stream_chunk(
                    _stream_chunk("inv-fail", prompt=200, candidates=50)
                )
            yield ("text", "chunk-text", "model")
            raise RuntimeError("agent exploded")

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(
                chat_module.agent_client, "stream_chat_completion", _failing_stream
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-fail",
                conversation_name=None,
                account_id="acc-fail",
                turn_uuid="turn-uuid-3",
            )
            collected = [item async for item in gen]

        # CH-79: exception is caught — no raise escapes the generator.
        # Error frame + [DONE] are emitted after the partial text.
        assert any("event: error\n" in frame for frame in collected)
        assert collected[-1] == "data: [DONE]\n\n"
        kwargs = mock_apply.call_args.kwargs
        assert kwargs["idempotency_key"] == "sess-fail:turn:inv-fail"
        assert kwargs["delta"]["input_tokens_total"].value == 200
        assert kwargs["delta"]["output_tokens_total"].value == 50


# ---------------------------------------------------------------------------
# _stream_completion_sse — terminal error frame (CH-79)
# ---------------------------------------------------------------------------


class TestStreamCompletionTerminalError:
    """Tests for the ``except Exception:`` arm added in CH-79.

    Verifies that a genuine server-side exception (not CancelledError /
    GeneratorExit) causes the generator to:
    - emit ``event: error\\n...`` followed by ``data: [DONE]\\n\\n``
    - NOT raise out of the generator
    - flush the side-table with ``turn_failed=True``
    - NOT leak internal exception details to the SSE client
    """

    @pytest.mark.asyncio
    async def test_empty_bubble_hard_failure_emits_error_and_done(self) -> None:
        """Stream raises before any yielded chunk — error frame + DONE emitted, no raise."""

        async def _raising_stream(*, accumulator: Any = None, **_kwargs: Any):
            if False:
                yield  # make it a valid async generator
            raise RuntimeError("hard failure")

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(
                chat_module.agent_client, "stream_chat_completion", _raising_stream
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-hard",
                conversation_name=None,
                account_id="acc-hard",
                turn_uuid="turn-uuid-hard",
            )
            # Consuming fully must NOT raise.
            collected = [item async for item in gen]

        # Initial ping + error frame + DONE — no text chunk because none was yielded.
        assert any("event: error\n" in frame for frame in collected)
        assert collected[-1] == "data: [DONE]\n\n"
        # Flush happened with turn_failed=True — last_agent_stopped_at is present.
        mock_apply.assert_called_once()
        delta = mock_apply.call_args.kwargs["delta"]
        assert "last_agent_stopped_at" in delta

    @pytest.mark.asyncio
    async def test_post_answer_benign_failure_emits_error_after_text(self) -> None:
        """Stream yields one text chunk then raises — frames arrive in expected order."""

        async def _partial_then_fail(
            *, accumulator: SessionTurnAccumulator | None = None, **_kwargs: Any
        ):
            if accumulator is not None:
                accumulator.add_stream_chunk(
                    _stream_chunk("inv-ptf", prompt=100, candidates=50)
                )
            yield ("text", "chunk-text", "model")
            raise RuntimeError("post-answer failure")

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(
                chat_module.agent_client,
                "stream_chat_completion",
                _partial_then_fail,
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-ptf",
                conversation_name=None,
                account_id="acc-ptf",
                turn_uuid="turn-uuid-ptf",
            )
            collected = [item async for item in gen]

        # Order: ping, text chunk, error frame, DONE.
        assert collected[0] == ": ping 0\n\n"
        assert collected[1] == "data: chunk-text\n\n"
        last_text_idx = max(i for i, f in enumerate(collected) if "data: chunk-text" in f)
        error_frame_idx = next(
            i for i, f in enumerate(collected) if "event: error\n" in f
        )
        assert error_frame_idx == last_text_idx + 1
        assert collected[-1] == "data: [DONE]\n\n"
        # Side-table flushed with turn_failed=True.
        mock_apply.assert_called_once()
        assert mock_apply.call_args.kwargs["delta"]["input_tokens_total"].value == 100

    @pytest.mark.asyncio
    async def test_cancelled_error_unchanged_no_error_frame(self) -> None:
        """CancelledError path still raises; no ``event: error`` frame is emitted."""
        chunks = [_stream_chunk("inv-cancel2", prompt=10, candidates=5)]
        mock_apply = MagicMock(return_value={"status": "applied"})

        with (
            patch.object(
                chat_module.agent_client,
                "stream_chat_completion",
                _make_fake_stream(chunks),
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-ce",
                conversation_name=None,
                account_id="acc-ce",
                turn_uuid="turn-uuid-ce",
            )
            # Consume the ping and the first text frame, then cancel.
            assert await gen.__anext__() == ": ping 0\n\n"
            assert await gen.__anext__() == "data: chunk-text\n\n"
            await gen.aclose()

        # None of the frames yielded before close should contain an error event.
        # (aclose() triggers GeneratorExit — the cancellation arm, not the error arm.)
        mock_apply.assert_called_once()
        delta = mock_apply.call_args.kwargs["delta"]
        # turn_failed=True is set by the cancellation arm, but no error frame is emitted.
        assert "last_agent_stopped_at" in delta

    @pytest.mark.asyncio
    async def test_generator_exit_unchanged_no_error_frame(self) -> None:
        """GeneratorExit (aclose) does not emit an error frame."""
        chunks = [
            _stream_chunk("inv-ge", prompt=20, candidates=10),
            _stream_chunk("inv-ge", prompt=0, candidates=5),
        ]
        mock_apply = MagicMock(return_value={"status": "applied"})
        collected_before_close: list[str] = []

        with (
            patch.object(
                chat_module.agent_client,
                "stream_chat_completion",
                _make_fake_stream(chunks),
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-ge",
                conversation_name=None,
                account_id="acc-ge",
                turn_uuid="turn-uuid-ge",
            )
            collected_before_close.append(await gen.__anext__())  # ping
            collected_before_close.append(await gen.__anext__())  # first text
            await gen.aclose()

        assert not any("event: error\n" in f for f in collected_before_close)

    @pytest.mark.asyncio
    async def test_error_frame_does_not_leak_exception_repr(self) -> None:
        """The SSE error frame contains only the sanitised message, not exception details."""

        async def _leaky_stream(*, accumulator: Any = None, **_kwargs: Any):
            if False:
                yield
            raise RuntimeError("secret internal details here")

        mock_apply = MagicMock(return_value={"status": "applied"})
        with (
            patch.object(
                chat_module.agent_client, "stream_chat_completion", _leaky_stream
            ),
            patch.object(chat_module, "apply_side_table_update", mock_apply),
            patch.object(chat_module, "_get_firestore_client", lambda: MagicMock()),
        ):
            gen = chat_module._stream_completion_sse(
                messages=[],
                user_context=MagicMock(),
                session_id="sess-leak",
                conversation_name=None,
                account_id="acc-leak",
                turn_uuid="turn-uuid-leak",
            )
            collected = [item async for item in gen]

        # Find the error frame.
        error_frame = next(f for f in collected if "event: error\n" in f)
        # Extract the data: line and parse it.
        data_line = next(
            line for line in error_frame.splitlines() if line.startswith("data:")
        )
        parsed = json.loads(data_line[len("data:"):].strip())
        assert parsed["message"] == "An unexpected error occurred. Please try again."
        # The raw exception text must NOT appear anywhere in the SSE output.
        full_output = "".join(collected)
        assert "secret internal details here" not in full_output
