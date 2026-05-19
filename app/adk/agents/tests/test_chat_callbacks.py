"""Unit tests for chat ADK callbacks.

Covers Critical 4 (token-extract error handling), Critical 5 (real ADK Event
API attribute names), root-only guard, and session-id guard.

CH-PRD-01 §5.1, §7 AC-6, AC-19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.adk.agents.chat_callbacks import (
    _build_turn_delta,
    _extract_session_id,
    _gather_turn_events,
    chat_after_agent_callback,
    chat_before_agent_callback,
)

# ---------------------------------------------------------------------------
# ADK Event stub helpers
# ---------------------------------------------------------------------------


@dataclass
class _MockPart:
    text: str | None = None


@dataclass
class _MockContent:
    parts: list[_MockPart] = field(default_factory=list)


@dataclass
class _MockUsage:
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    thoughts_token_count: int = 0
    cached_content_token_count: int = 0


class _MockEvent:
    """Minimal ADK Event stub using the real API surface."""

    def __init__(
        self,
        *,
        invocation_id: str = "inv-1",
        author: str = "model",
        fn_calls: list[Any] | None = None,
        is_final: bool = False,
        parts: list[str] | None = None,
        usage: _MockUsage | None = None,
    ) -> None:
        self.invocation_id = invocation_id
        self.author = author
        self._fn_calls = fn_calls or []
        self._is_final = is_final
        self.content = _MockContent(parts=[_MockPart(text=t) for t in (parts or [])]) if parts else None
        self.usage_metadata = usage

    def get_function_calls(self) -> list[Any]:
        return self._fn_calls

    def is_final_response(self) -> bool:
        return self._is_final


# ---------------------------------------------------------------------------
# _build_turn_delta
# ---------------------------------------------------------------------------


class TestBuildTurnDelta:
    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_empty_events(self) -> None:
        delta = _build_turn_delta([], self._now())
        assert delta["input_tokens_total"] == {"_increment": 0}
        assert delta["output_tokens_total"] == {"_increment": 0}
        assert delta["tool_call_count"] == {"_increment": 0}
        assert delta["message_count"] == {"_increment": 0}
        assert delta["last_message_preview"] == ""

    def test_tool_call_count_uses_get_function_calls(self) -> None:
        """Critical 5: tool_call_count must use get_function_calls(), not event.type."""
        fn_call = MagicMock()
        events = [
            _MockEvent(fn_calls=[fn_call, fn_call]),
            _MockEvent(fn_calls=[fn_call]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta["tool_call_count"] == {"_increment": 3}

    def test_tool_call_zero_when_no_function_calls(self) -> None:
        events = [_MockEvent()]
        delta = _build_turn_delta(events, self._now())
        assert delta["tool_call_count"] == {"_increment": 0}

    def test_final_text_uses_is_final_response_and_content_parts(self) -> None:
        """Critical 5: last_message_preview must use is_final_response() + content.parts."""
        events = [
            _MockEvent(is_final=False, parts=["ignored"]),
            _MockEvent(is_final=True, parts=["hello ", "world"]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta["last_message_preview"] == "hello world"

    def test_final_text_truncated_at_160(self) -> None:
        long_text = "x" * 200
        events = [_MockEvent(is_final=True, parts=[long_text])]
        delta = _build_turn_delta(events, self._now())
        assert len(delta["last_message_preview"]) == 160

    def test_final_text_empty_when_no_final_event(self) -> None:
        events = [_MockEvent(is_final=False, parts=["not final"])]
        delta = _build_turn_delta(events, self._now())
        assert delta["last_message_preview"] == ""

    def test_message_count_author_check(self) -> None:
        events = [
            _MockEvent(author="user"),
            _MockEvent(author="model"),
            _MockEvent(author="other_agent"),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta["message_count"] == {"_increment": 2}

    def test_token_extraction_errors_do_not_raise(self) -> None:
        """Critical 4: token extraction failures must not propagate."""
        bad_event = _MockEvent()
        bad_event.usage_metadata = object()  # will fail inside extract_billable_tokens

        with patch(
            "app.adk.agents.chat_callbacks._extract_billable_tokens",
            side_effect=RuntimeError("boom"),
        ):
            delta = _build_turn_delta([bad_event], self._now())

        assert delta["input_tokens_total"] == {"_increment": 0}

    def test_token_extraction_accumulates_counts(self) -> None:

        usage = _MockUsage(prompt_token_count=100, candidates_token_count=50)
        events = [_MockEvent(usage=usage), _MockEvent(usage=usage)]
        delta = _build_turn_delta(events, self._now())
        # input = prompt - cached = 100 - 0 = 100, output = 50 each → total 200 input, 100 output
        assert delta["input_tokens_total"] == {"_increment": 200}
        assert delta["output_tokens_total"] == {"_increment": 100}

    def test_datetime_fields_are_isoformat_sentinels(self) -> None:
        delta = _build_turn_delta([], self._now())
        for field_name in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            assert "_isoformat" in delta[field_name], f"{field_name} missing _isoformat sentinel"


# ---------------------------------------------------------------------------
# Root-only guard
# ---------------------------------------------------------------------------


@dataclass
class _MockAgent:
    parent_agent: Any = None


@dataclass
class _MockSession:
    id: str = "sess-001"
    events: list[Any] = field(default_factory=list)


@dataclass
class _MockInvocationContext:
    agent: _MockAgent = field(default_factory=_MockAgent)
    session: _MockSession = field(default_factory=_MockSession)
    invocation_id: str = "inv-1"


@dataclass
class _MockState:
    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


@dataclass
class _MockCallbackContext:
    _invocation_context: _MockInvocationContext = field(default_factory=_MockInvocationContext)
    state: _MockState = field(default_factory=_MockState)


def _make_callback_context(
    *,
    parent_agent: Any = None,
    session_id: str = "sess-001",
    account_id: str = "acc-001",
    invocation_id: str = "inv-1",
) -> _MockCallbackContext:
    agent = _MockAgent(parent_agent=parent_agent)
    session = _MockSession(id=session_id)
    inv_ctx = _MockInvocationContext(agent=agent, session=session, invocation_id=invocation_id)
    state = _MockState(_data={"account_id": account_id})
    return _MockCallbackContext(_invocation_context=inv_ctx, state=state)


class TestRootOnlyGuard:
    def test_before_callback_skips_sub_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=_MockAgent())
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            result = chat_before_agent_callback(ctx)
        assert result is None
        mock_post.assert_not_called()

    def test_after_callback_skips_sub_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=_MockAgent())
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            result = chat_after_agent_callback(ctx)
        assert result is None
        mock_post.assert_not_called()

    def test_before_callback_fires_for_root_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=None)
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            result = chat_before_agent_callback(ctx)
        assert result is None
        mock_post.assert_called_once()

    def test_after_callback_fires_for_root_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=None)
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            result = chat_after_agent_callback(ctx)
        assert result is None
        mock_post.assert_called_once()


class TestPendingSessionGuard:
    def test_before_callback_skips_pending_session(self) -> None:
        ctx = _make_callback_context(session_id="pending_abc123")
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            chat_before_agent_callback(ctx)
        mock_post.assert_not_called()

    def test_after_callback_skips_pending_session(self) -> None:
        ctx = _make_callback_context(session_id="pending_abc123")
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            chat_after_agent_callback(ctx)
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestExtractSessionId:
    def test_returns_session_id(self) -> None:
        session = _MockSession(id="sess-xyz")
        inv_ctx = _MockInvocationContext(session=session)
        assert _extract_session_id(inv_ctx) == "sess-xyz"

    def test_returns_empty_string_when_no_session(self) -> None:
        inv_ctx = _MockInvocationContext(session=None)  # type: ignore[arg-type]
        assert _extract_session_id(inv_ctx) == ""


class TestGatherTurnEvents:
    def test_filters_by_invocation_id(self) -> None:
        e1 = _MockEvent(invocation_id="inv-A")
        e2 = _MockEvent(invocation_id="inv-B")
        e3 = _MockEvent(invocation_id="inv-A")
        session = _MockSession(events=[e1, e2, e3])
        inv_ctx = _MockInvocationContext(session=session)
        result = _gather_turn_events(inv_ctx, "inv-A")
        assert result == [e1, e3]

    def test_returns_empty_when_invocation_id_none(self) -> None:
        session = _MockSession(events=[_MockEvent()])
        inv_ctx = _MockInvocationContext(session=session)
        assert _gather_turn_events(inv_ctx, None) == []


# ---------------------------------------------------------------------------
# AC-19: nested-specialist callback sequence
# ---------------------------------------------------------------------------


class TestNestedSpecialistSequence:
    """Simulate a turn that dispatches a sub-agent and assert the root-only
    guard keeps the side-table per-turn (CH-PRD-01 §7 AC-19).

    ADK fires the agent callbacks once per agent dispatch, so a turn that
    dispatches one specialist produces the sequence:

        root.before -> specialist.before -> specialist.after -> root.after

    Without the ``parent_agent`` guard the two specialist firings would post
    their own deltas — overwriting ``last_agent_started_at`` mid-turn and
    flushing an incomplete accumulator — which corrupts the ``is_agent_running``
    derivation. This test drives the full four-call sequence and asserts the
    PRD AC-19 sub-assertions (a)-(d).
    """

    _T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # root.before stamp
    _T1 = datetime(2026, 1, 1, 12, 0, 9, tzinfo=timezone.utc)  # root.after stamp

    def test_only_root_callbacks_post_one_delta_each(self) -> None:
        root = _make_callback_context(
            parent_agent=None,
            session_id="sess-seq",
            account_id="acc-seq",
            invocation_id="inv-seq",
        )
        specialist = _make_callback_context(
            parent_agent=_MockAgent(),
            session_id="sess-seq",
            account_id="acc-seq",
            invocation_id="inv-seq",
        )

        posted: list[dict[str, Any]] = []

        mock_dt = MagicMock()
        # Two stamps are consumed on the correct path (root.before, root.after);
        # the extra entries let a broken guard fail on the assertions below
        # rather than on a StopIteration inside the callback.
        mock_dt.now.side_effect = [self._T0, self._T1, self._T1, self._T1]

        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update",
            side_effect=lambda **kw: posted.append(kw),
        ), patch("app.adk.agents.chat_callbacks.datetime", mock_dt):
            assert chat_before_agent_callback(root) is None
            assert len(posted) == 1, "root before-callback must post exactly once"

            # AC-19 (d): the guard returns early on the specialist invocations.
            assert chat_before_agent_callback(specialist) is None
            assert len(posted) == 1, "specialist before-callback must not post"

            assert chat_after_agent_callback(specialist) is None
            assert len(posted) == 1, "specialist after-callback must not post"

            assert chat_after_agent_callback(root) is None

        # AC-19 (c): exactly one flush per root callback — two for the turn,
        # not the four that an unguarded wiring would produce.
        assert len(posted) == 2

        before_post, after_post = posted

        # AC-19 (a): last_agent_started_at carries the root before-callback's
        # timestamp, never overwritten by specialist.before.
        assert before_post["idempotency_key"] == "sess-seq:before-agent:inv-seq"
        assert before_post["delta"]["last_agent_started_at"] == {
            "_isoformat": self._T0.isoformat()
        }
        assert "last_agent_stopped_at" not in before_post["delta"]

        # AC-19 (b): last_agent_stopped_at carries the root after-callback's
        # timestamp, never stamped early by specialist.after.
        assert after_post["idempotency_key"] == "sess-seq:turn:inv-seq"
        assert after_post["delta"]["last_agent_stopped_at"] == {
            "_isoformat": self._T1.isoformat()
        }
        # The after-post carries the full per-turn delta, not just a stamp.
        assert "input_tokens_total" in after_post["delta"]
        assert "message_count" in after_post["delta"]
