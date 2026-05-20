"""Unit tests: chat_callbacks._build_turn_delta and callback wiring.

Verifies that chat_after_agent_callback (and chat_before_agent_callback) build
the correct wire-format delta from ADK events (CH-PRD-01 §7 AC-6, AC-19).

These tests exercise the full callback-to-delta path with _post_side_table_update
mocked — no network and no Firestore emulator required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.adk.agents.chat_callbacks import (
    _build_turn_delta,
    chat_after_agent_callback,
    chat_before_agent_callback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    prompt: int = 0,
    candidates: int = 0,
    thoughts: int = 0,
    cached: int = 0,
    author: str | None = None,
    invocation_id: str = "inv_001",
    is_tool_call: bool = False,
    final_text: str | None = None,
) -> Any:
    """Build a minimal ADK-event-like namespace using the real ADK Event API."""
    fn_calls = [SimpleNamespace(name="fake_tool")] if is_tool_call else []

    def get_function_calls() -> list[Any]:
        return fn_calls

    _final_text = final_text

    def is_final_response() -> bool:
        return _final_text is not None

    content = None
    if final_text is not None:
        content = SimpleNamespace(parts=[SimpleNamespace(text=final_text)])

    return SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt,
            candidates_token_count=candidates,
            thoughts_token_count=thoughts,
            cached_content_token_count=cached,
        ) if (prompt or candidates or thoughts or cached) else None,
        author=author,
        get_function_calls=get_function_calls,
        is_final_response=is_final_response,
        content=content,
        invocation_id=invocation_id,
    )


def _make_callback_ctx(
    session_id: str = "sess_001",
    invocation_id: str = "inv_001",
    account_id: str = "acc_001",
    parent_agent: Any | None = None,
    events: list[Any] | None = None,
) -> Any:
    """Build a minimal CallbackContext-like namespace for callback tests."""
    session = SimpleNamespace(
        id=session_id,
        events=events if events is not None else [],
    )
    inv_ctx = SimpleNamespace(
        agent=SimpleNamespace(parent_agent=parent_agent),
        session=session,
        invocation_id=invocation_id,
    )
    state: dict[str, Any] = {}
    if account_id:
        state["account_id"] = account_id
    return SimpleNamespace(_invocation_context=inv_ctx, state=state)


# ---------------------------------------------------------------------------
# Tests: _build_turn_delta (pure function)
# ---------------------------------------------------------------------------


class TestBuildTurnDelta:
    def test_empty_events_produces_zero_increments(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        delta = _build_turn_delta([], now)
        assert delta.input_tokens_increment == 0
        assert delta.output_tokens_increment == 0
        assert delta.reasoning_tokens_increment == 0
        assert delta.current_context_tokens == 0
        assert delta.tool_call_count == 0
        assert delta.message_count == 0
        assert delta.last_message_preview == ""

    def test_token_events_are_summed(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(prompt=100, candidates=50, cached=20),   # input=80, output=50
            _make_event(prompt=200, candidates=80, thoughts=30, cached=0),  # input=200, output=80, reasoning=30
        ]
        delta = _build_turn_delta(events, now)
        assert delta.input_tokens_increment == 280    # 80 + 200
        assert delta.output_tokens_increment == 130   # 50 + 80
        assert delta.reasoning_tokens_increment == 30
        assert delta.current_context_tokens == 440    # 280 + 130 + 30

    def test_cached_tokens_excluded_from_input(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # prompt=1250, cached=200 => input=1050 (canonical fixture from token_accounting parity test)
        events = [_make_event(prompt=1250, candidates=380, thoughts=0, cached=200)]
        delta = _build_turn_delta(events, now)
        assert delta.input_tokens_increment == 1050
        assert delta.output_tokens_increment == 380
        assert delta.reasoning_tokens_increment == 0
        assert delta.current_context_tokens == 1430

    def test_tool_call_count_incremented(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(is_tool_call=True),
            _make_event(is_tool_call=True),
        ]
        delta = _build_turn_delta(events, now)
        assert delta.tool_call_count == 2

    def test_non_tool_call_events_not_counted(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(),
            _make_event(),
            _make_event(is_tool_call=True),
        ]
        delta = _build_turn_delta(events, now)
        assert delta.tool_call_count == 1

    def test_message_count_only_user_and_model(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(author="user"),
            _make_event(author="model"),
            _make_event(author="root"),    # not counted
            _make_event(author="system"),  # not counted
            _make_event(author=None),      # not counted
        ]
        delta = _build_turn_delta(events, now)
        assert delta.message_count == 2

    def test_final_text_preview_truncated_at_160(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        long_text = "x" * 200
        events = [_make_event(final_text=long_text)]
        delta = _build_turn_delta(events, now)
        assert delta.last_message_preview == "x" * 160

    def test_final_text_short_not_padded(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [_make_event(final_text="hello")]
        delta = _build_turn_delta(events, now)
        assert delta.last_message_preview == "hello"

    def test_last_final_text_wins(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(final_text="first"),
            _make_event(final_text="last"),
        ]
        delta = _build_turn_delta(events, now)
        assert delta.last_message_preview == "last"

    def test_non_final_text_events_ignored_for_preview(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(),
            _make_event(final_text="kept"),
        ]
        delta = _build_turn_delta(events, now)
        assert delta.last_message_preview == "kept"

    def test_datetime_fields_are_typed_datetimes(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        delta = _build_turn_delta([], now)
        for attr in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            val = getattr(delta, attr)
            assert isinstance(val, datetime), f"{attr} should be a datetime"
            assert val == now, f"{attr} should match the input datetime"

    def test_wire_round_trip_reproduces_sentinel_format(self) -> None:
        """to_wire_dict() reproduces the legacy sentinel format byte-for-byte."""
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [_make_event(prompt=280, candidates=130, thoughts=30, cached=0)]
        wire = _build_turn_delta(events, now).to_wire_dict()
        now_sentinel = {"_isoformat": now.isoformat()}
        assert wire == {
            "last_agent_stopped_at": now_sentinel,
            "updated_at": now_sentinel,
            "last_agent_message_at": now_sentinel,
            "input_tokens_total": {"_increment": 280},
            "output_tokens_total": {"_increment": 130},
            "reasoning_tokens_total": {"_increment": 30},
            "tool_call_count": {"_increment": 0},
            "message_count": {"_increment": 0},
            "current_context_tokens": {"_increment": 440},
            "last_message_preview": "",
        }

    def test_events_without_usage_metadata_are_skipped_for_tokens(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Events with no usage_metadata (None) should not blow up and should
        # contribute 0 tokens.
        events = [
            _make_event(is_tool_call=True),   # no usage_metadata set
            _make_event(author="user"),        # no usage_metadata set
        ]
        delta = _build_turn_delta(events, now)
        assert delta.input_tokens_increment == 0
        assert delta.output_tokens_increment == 0
        assert delta.tool_call_count == 1
        assert delta.message_count == 1

    def test_mixed_events_compound_correctly(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events = [
            _make_event(prompt=100, candidates=50, cached=10, author="user"),
            _make_event(is_tool_call=True),
            _make_event(prompt=200, candidates=80, thoughts=20, cached=0, author="model"),
            _make_event(final_text="final answer"),
        ]
        delta = _build_turn_delta(events, now)
        # input = (100-10) + (200-0) = 90 + 200 = 290
        assert delta.input_tokens_increment == 290
        # output = 50 + 80 = 130
        assert delta.output_tokens_increment == 130
        # reasoning = 20
        assert delta.reasoning_tokens_increment == 20
        # context = 290 + 130 + 20 = 440
        assert delta.current_context_tokens == 440
        assert delta.tool_call_count == 1
        assert delta.message_count == 2
        assert delta.last_message_preview == "final answer"


# ---------------------------------------------------------------------------
# Tests: chat_after_agent_callback (integration — mocks _post_side_table_update)
# ---------------------------------------------------------------------------


class TestChatAfterAgentCallbackIntegration:
    """Verify chat_after_agent_callback calls _post_side_table_update correctly."""

    def test_callback_posts_delta_for_root_agent(self) -> None:
        """Root agent: _post_side_table_update is called with a non-empty delta."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_001",
                invocation_id="inv_001",
                account_id="acc_001",
                parent_agent=None,
            )
            result = chat_after_agent_callback(ctx)

        assert result is None
        assert len(posted) == 1
        call = posted[0]
        assert call["session_id"] == "sess_001"
        assert call["account_id"] == "acc_001"
        assert "turn:inv_001" in call["idempotency_key"]
        assert "last_agent_stopped_at" in call["delta"]
        assert "updated_at" in call["delta"]
        assert "last_agent_message_at" in call["delta"]
        assert "input_tokens_total" in call["delta"]
        assert "output_tokens_total" in call["delta"]
        assert "tool_call_count" in call["delta"]
        assert "message_count" in call["delta"]
        assert "current_context_tokens" in call["delta"]
        assert "last_message_preview" in call["delta"]

    def test_callback_skips_for_specialist(self) -> None:
        """Specialist (parent_agent set): no update is posted (AC-19)."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            parent = SimpleNamespace()
            ctx = _make_callback_ctx(
                session_id="sess_002",
                invocation_id="inv_002",
                account_id="acc_001",
                parent_agent=parent,
            )
            result = chat_after_agent_callback(ctx)

        assert result is None
        assert posted == []

    def test_callback_skips_when_no_account_id(self) -> None:
        """Missing account_id: no update posted (guard against state not ready)."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_003",
                invocation_id="inv_003",
                account_id="",   # empty — triggers the guard
                parent_agent=None,
            )
            result = chat_after_agent_callback(ctx)

        assert result is None
        assert posted == []

    def test_callback_skips_for_pending_session(self) -> None:
        """Session IDs that start with 'pending_' are skipped."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="pending_not_ready",
                invocation_id="inv_004",
                account_id="acc_001",
                parent_agent=None,
            )
            result = chat_after_agent_callback(ctx)

        assert result is None
        assert posted == []

    def test_callback_returns_none_on_post_exception(self) -> None:
        """Even if _post_side_table_update raises, callback returns None (non-blocking)."""
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=RuntimeError("network failure"),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_005",
                invocation_id="inv_005",
                account_id="acc_001",
                parent_agent=None,
            )
            result = chat_after_agent_callback(ctx)

        assert result is None

    def test_callback_passes_turn_events_to_delta(self) -> None:
        """Events matching the invocation_id are included in the delta."""
        posted: list[dict] = []

        inv_id = "inv_006"
        turn_events = [
            _make_event(prompt=500, candidates=200, cached=0, invocation_id=inv_id),
            _make_event(author="model", invocation_id=inv_id),
            # event from a different invocation — must not be included
            _make_event(prompt=9999, candidates=9999, invocation_id="other_inv"),
        ]

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_006",
                invocation_id=inv_id,
                account_id="acc_001",
                parent_agent=None,
                events=turn_events,
            )
            chat_after_agent_callback(ctx)

        assert len(posted) == 1
        delta = posted[0]["delta"]
        # Only events matching inv_006 are counted: 500 input, 200 output
        assert delta["input_tokens_total"] == {"_increment": 500}
        assert delta["output_tokens_total"] == {"_increment": 200}
        assert delta["message_count"] == {"_increment": 1}  # only author="model" event

    def test_idempotency_key_contains_session_and_invocation(self) -> None:
        """Idempotency key format: '{session_id}:turn:{invocation_id}'.

        The shared per-turn key — the /completions finally block flushes
        partial counts under the same key on a cancelled stream (AC-8).
        """
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_idem",
                invocation_id="inv_idem",
                account_id="acc_001",
                parent_agent=None,
            )
            chat_after_agent_callback(ctx)

        assert posted[0]["idempotency_key"] == "sess_idem:turn:inv_idem"


# ---------------------------------------------------------------------------
# Tests: chat_before_agent_callback (mirrors after-callback guards)
# ---------------------------------------------------------------------------


class TestChatBeforeAgentCallback:
    """Verify chat_before_agent_callback stamps last_agent_started_at. Root-only."""

    def test_before_callback_posts_started_at_for_root_agent(self) -> None:
        """Root agent: _post_side_table_update is called with last_agent_started_at."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_b01",
                invocation_id="inv_b01",
                account_id="acc_001",
                parent_agent=None,
            )
            result = chat_before_agent_callback(ctx)

        assert result is None
        assert len(posted) == 1
        call = posted[0]
        assert call["session_id"] == "sess_b01"
        assert call["account_id"] == "acc_001"
        assert "before-agent:inv_b01" in call["idempotency_key"]
        # Delta must contain the two timestamp fields, nothing else
        assert "last_agent_started_at" in call["delta"]
        assert "updated_at" in call["delta"]

    def test_before_callback_stamps_are_iso_strings(self) -> None:
        """Timestamps in the before-callback delta are valid ISO-8601 strings."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_b02",
                invocation_id="inv_b02",
                account_id="acc_001",
                parent_agent=None,
            )
            chat_before_agent_callback(ctx)

        delta = posted[0]["delta"]
        for key in ("last_agent_started_at", "updated_at"):
            sentinel = delta[key]
            assert isinstance(sentinel, dict) and "_isoformat" in sentinel, (
                f"{key} should use _isoformat sentinel"
            )
            # Parsing must succeed (raises ValueError on bad format)
            datetime.fromisoformat(sentinel["_isoformat"])

    def test_before_callback_skips_for_specialist(self) -> None:
        """Specialist agent (parent_agent set): no update posted (AC-19)."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            parent = SimpleNamespace()
            ctx = _make_callback_ctx(
                session_id="sess_b03",
                invocation_id="inv_b03",
                account_id="acc_001",
                parent_agent=parent,
            )
            result = chat_before_agent_callback(ctx)

        assert result is None
        assert posted == []

    def test_before_callback_skips_when_no_account_id(self) -> None:
        """Missing account_id: no update posted."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_b04",
                invocation_id="inv_b04",
                account_id="",
                parent_agent=None,
            )
            chat_before_agent_callback(ctx)

        assert posted == []

    def test_before_callback_skips_for_pending_session(self) -> None:
        """Pending session IDs are skipped."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="pending_123",
                invocation_id="inv_b05",
                account_id="acc_001",
                parent_agent=None,
            )
            chat_before_agent_callback(ctx)

        assert posted == []

    def test_before_callback_idempotency_key_format(self) -> None:
        """Idempotency key format: '{session_id}:before-agent:{invocation_id}'."""
        posted: list[dict] = []

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_idem2",
                invocation_id="inv_idem2",
                account_id="acc_001",
                parent_agent=None,
            )
            chat_before_agent_callback(ctx)

        assert posted[0]["idempotency_key"] == "sess_idem2:before-agent:inv_idem2"

    def test_before_callback_returns_none_on_post_exception(self) -> None:
        """Even if _post_side_table_update raises, callback returns None (non-blocking)."""
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=RuntimeError("network failure"),
        ):
            ctx = _make_callback_ctx(
                session_id="sess_b06",
                invocation_id="inv_b06",
                account_id="acc_001",
                parent_agent=None,
            )
            result = chat_before_agent_callback(ctx)

        assert result is None
