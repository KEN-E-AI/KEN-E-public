"""Unit tests for chat ADK callbacks.

Covers Critical 4 (token-extract error handling), Critical 5 (real ADK Event
API attribute names), root-only guard, and session-id guard.

CH-PRD-01 §5.1, §7 AC-6, AC-19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from app.adk.agents.chat_callbacks import (
    _build_turn_delta,
    _extract_session_id,
    _gather_turn_events,
    attach_chat_side_table_callbacks,
    chat_after_agent_callback,
    chat_before_agent_callback,
)

# ---------------------------------------------------------------------------
# attach_chat_side_table_callbacks — root-agent wiring (CH-PRD-01 §5.1)
# ---------------------------------------------------------------------------


class TestAttachChatSideTableCallbacks:
    def test_appends_to_existing_callback_lists(self) -> None:
        """Factory-built agents carry list callbacks (weave/skill) — append to them."""

        def _weave_before(_ctx: Any) -> None: ...
        def _weave_after(_ctx: Any) -> None: ...

        agent = SimpleNamespace(
            before_agent_callback=[_weave_before],
            after_agent_callback=[_weave_after],
        )

        attach_chat_side_table_callbacks(agent)

        assert agent.before_agent_callback == [
            _weave_before,
            chat_before_agent_callback,
        ]
        assert agent.after_agent_callback == [_weave_after, chat_after_agent_callback]

    def test_promotes_single_callable_to_list(self) -> None:
        def _single(_ctx: Any) -> None: ...

        agent = SimpleNamespace(
            before_agent_callback=_single,
            after_agent_callback=_single,
        )

        attach_chat_side_table_callbacks(agent)

        assert agent.before_agent_callback == [_single, chat_before_agent_callback]
        assert agent.after_agent_callback == [_single, chat_after_agent_callback]

    def test_creates_list_when_none(self) -> None:
        agent = SimpleNamespace(
            before_agent_callback=None,
            after_agent_callback=None,
        )

        attach_chat_side_table_callbacks(agent)

        assert agent.before_agent_callback == [chat_before_agent_callback]
        assert agent.after_agent_callback == [chat_after_agent_callback]


# ---------------------------------------------------------------------------
# ADK Event stub helpers
# ---------------------------------------------------------------------------


@dataclass
class _MockPart:
    text: str | None = None
    # ADK reasoning/thinking summaries arrive as Part(text=..., thought=True);
    # default False so plain-text fixtures are treated as answer text.
    thought: bool = False


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
        event_id: str | None = None,
        node_info: object = None,
        isolation_scope: str | None = None,
    ) -> None:
        self.invocation_id = invocation_id
        self.author = author
        self._fn_calls = fn_calls or []
        self._is_final = is_final
        self.content = (
            _MockContent(parts=[_MockPart(text=t) for t in (parts or [])])
            if parts
            else None
        )
        self.usage_metadata = usage
        if event_id is not None:
            self.id = event_id
        if node_info is not None:
            self.node_info = node_info
        if isolation_scope is not None:
            self.isolation_scope = isolation_scope

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
        assert delta.input_tokens_increment == 0
        assert delta.output_tokens_increment == 0
        assert delta.tool_call_count == 0
        assert delta.message_count == 0
        assert delta.last_message_preview == ""

    def test_tool_call_count_uses_get_function_calls(self) -> None:
        """Critical 5: tool_call_count must use get_function_calls(), not event.type."""
        fn_call = MagicMock()
        events = [
            _MockEvent(fn_calls=[fn_call, fn_call]),
            _MockEvent(fn_calls=[fn_call]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.tool_call_count == 3

    def test_tool_call_zero_when_no_function_calls(self) -> None:
        events = [_MockEvent()]
        delta = _build_turn_delta(events, self._now())
        assert delta.tool_call_count == 0

    def test_final_text_uses_is_final_response_and_content_parts(self) -> None:
        """Critical 5: last_message_preview must use is_final_response() + content.parts."""
        events = [
            _MockEvent(is_final=False, parts=["ignored"]),
            _MockEvent(is_final=True, parts=["hello ", "world"]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.last_message_preview == "hello world"

    def test_final_text_excludes_thought_parts(self) -> None:
        """Reasoning (thought=True) parts must not leak into last_message_preview.

        ADK attaches the thinking summary as a thought part that precedes the
        answer in the final-response content; without filtering, the preview
        (final_text[:160]) would show the agent's reasoning instead of its reply.
        """
        event = _MockEvent(is_final=True)
        event.content = _MockContent(
            parts=[
                _MockPart(
                    text="Let me reason about the request first...", thought=True
                ),
                _MockPart(text="Here is your answer", thought=False),
            ]
        )
        delta = _build_turn_delta([event], self._now())
        assert delta.last_message_preview == "Here is your answer"

    def test_final_text_truncated_at_160(self) -> None:
        long_text = "x" * 200
        events = [_MockEvent(is_final=True, parts=[long_text])]
        delta = _build_turn_delta(events, self._now())
        assert len(delta.last_message_preview) == 160

    def test_final_text_empty_when_no_final_event(self) -> None:
        events = [_MockEvent(is_final=False, parts=["not final"])]
        delta = _build_turn_delta(events, self._now())
        assert delta.last_message_preview == ""

    def test_message_count_author_check(self) -> None:
        """Legacy author check: user and model count; non-legacy author without
        usage_metadata does NOT count (the "no usage_metadata → excluded" path).
        For the full multi-author contract see TestBuildTurnDeltaMultiAuthorMessageCount."""
        events = [
            _MockEvent(author="user"),
            _MockEvent(author="model"),
            _MockEvent(author="other_agent"),  # no usage_metadata → excluded
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.message_count == 2

    def test_token_extraction_errors_do_not_raise(self) -> None:
        """Critical 4: token extraction failures must not propagate."""
        bad_event = _MockEvent()
        bad_event.usage_metadata = object()  # will fail inside extract_billable_tokens

        with patch(
            "app.adk.agents.chat_callbacks._extract_billable_tokens",
            side_effect=RuntimeError("boom"),
        ):
            delta = _build_turn_delta([bad_event], self._now())

        assert delta.input_tokens_increment == 0

    def test_token_extraction_accumulates_counts(self) -> None:
        usage = _MockUsage(prompt_token_count=100, candidates_token_count=50)
        events = [_MockEvent(usage=usage), _MockEvent(usage=usage)]
        delta = _build_turn_delta(events, self._now())
        # input = prompt - cached = 100 - 0 = 100, output = 50 each → total 200 input, 100 output
        assert delta.input_tokens_increment == 200
        assert delta.output_tokens_increment == 100

    def test_datetime_fields_are_typed_datetimes(self) -> None:
        now = self._now()
        delta = _build_turn_delta([], now)
        for attr in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            val = getattr(delta, attr)
            assert isinstance(val, datetime), f"{attr} should be a datetime"
            assert val == now, f"{attr} should match the input datetime"

    def test_wire_dict_emits_isoformat_sentinels(self) -> None:
        now = self._now()
        wire = _build_turn_delta([], now).to_wire_dict()
        for key in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            assert set(wire[key].keys()) == {"_isoformat"}, (
                f"{key} missing _isoformat sentinel"
            )
            assert datetime.fromisoformat(wire[key]["_isoformat"]) == now


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
    _invocation_context: _MockInvocationContext = field(
        default_factory=_MockInvocationContext
    )
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
    inv_ctx = _MockInvocationContext(
        agent=agent, session=session, invocation_id=invocation_id
    )
    state = _MockState(_data={"account_id": account_id})
    return _MockCallbackContext(_invocation_context=inv_ctx, state=state)


class TestRootOnlyGuard:
    def test_before_callback_skips_sub_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=_MockAgent())
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            result = chat_before_agent_callback(ctx)
        assert result is None
        mock_post.assert_not_called()

    def test_after_callback_skips_sub_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=_MockAgent())
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            result = chat_after_agent_callback(ctx)
        assert result is None
        mock_post.assert_not_called()

    def test_before_callback_fires_for_root_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=None)
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            result = chat_before_agent_callback(ctx)
        assert result is None
        mock_post.assert_called_once()

    def test_after_callback_fires_for_root_agent(self) -> None:
        ctx = _make_callback_context(parent_agent=None)
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            result = chat_after_agent_callback(ctx)
        assert result is None
        mock_post.assert_called_once()


class TestPendingSessionGuard:
    def test_before_callback_skips_pending_session(self) -> None:
        ctx = _make_callback_context(session_id="pending_abc123")
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            chat_before_agent_callback(ctx)
        mock_post.assert_not_called()

    def test_after_callback_skips_pending_session(self) -> None:
        ctx = _make_callback_context(session_id="pending_abc123")
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
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

        with (
            patch(
                "app.adk.agents.chat_callbacks._post_side_table_update",
                side_effect=lambda **kw: posted.append(kw),
            ),
            patch("app.adk.agents.chat_callbacks.datetime", mock_dt),
        ):
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


# ---------------------------------------------------------------------------
# Multi-task / fan-out aggregation (AH-PRD-14 §7 AC-2 — merge blocker)
# ---------------------------------------------------------------------------


class TestBuildTurnDeltaMultiTaskAggregation:
    """AC-2: aggregate token / tool-call / message counts equal the sum of
    per-specialist baselines under a multi-specialist supervisor turn."""

    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_two_specialist_tokens_equal_sum_of_baselines(self) -> None:
        """CH-10 parity fixture per specialist: prompt=1250, cached=200, candidates=380
        → input=1050, output=380.  Two specialists → 2100/760/0 aggregate."""
        events = [
            _MockEvent(
                author="specialist_a",
                usage=_MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200),
            ),
            _MockEvent(
                author="specialist_b",
                usage=_MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200),
            ),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.input_tokens_increment == 2100
        assert delta.output_tokens_increment == 760

    def test_fan_out_group_tool_call_count_equals_sum(self) -> None:
        fn_call = MagicMock()
        events = [
            _MockEvent(author="specialist_a", fn_calls=[fn_call]),
            _MockEvent(author="specialist_b", fn_calls=[fn_call]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.tool_call_count == 2

    def test_aggregate_all_three_counters_equal_sum_of_baselines(self) -> None:
        """AC-2 merge-blocker: tokens + tool_calls + messages equal the sum of
        per-specialist baselines for a two-specialist fan-out turn."""
        fn_call = MagicMock()
        events = [
            # specialist_a: 1 LLM response + 1 tool call
            _MockEvent(
                author="specialist_a",
                usage=_MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200),
            ),
            _MockEvent(author="specialist_a", fn_calls=[fn_call]),
            # specialist_b: 1 LLM response + 1 tool call
            _MockEvent(
                author="specialist_b",
                usage=_MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200),
            ),
            _MockEvent(author="specialist_b", fn_calls=[fn_call]),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.input_tokens_increment == 2100   # sum of per-specialist input tokens
        assert delta.output_tokens_increment == 760   # sum of per-specialist output tokens
        assert delta.tool_call_count == 2              # sum of per-specialist tool calls
        assert delta.message_count == 2                # sum of per-specialist LLM responses


# ---------------------------------------------------------------------------
# ADK 2.0 field tolerance (AH-PRD-14 §2)
# ---------------------------------------------------------------------------


class TestBuildTurnDeltaADK20FieldTolerance:
    """Regression guards: events carrying ADK 2.0 fields (node_info,
    isolation_scope) must not be dropped by future filtering code.

    ``_build_turn_delta`` does not read these fields today, so they pass
    through via duck-typing. These tests lock in the invariant that adding
    those attributes to an event never causes the event to be skipped or its
    counters zeroed — guarding against a future regression that accidentally
    gates processing on the absence of ADK 2.0 fields."""

    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_event_with_node_info_tokens_counted(self) -> None:
        from types import SimpleNamespace as _NS

        node_info = _NS(path="coordinator@1/task_specialist@2", output_for=[])
        event = _MockEvent(
            author="task_specialist",
            usage=_MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200),
            node_info=node_info,
        )
        delta = _build_turn_delta([event], self._now())
        assert delta.input_tokens_increment == 1050
        assert delta.output_tokens_increment == 380

    def test_event_with_isolation_scope_tokens_counted(self) -> None:
        event = _MockEvent(
            author="coordinator",
            usage=_MockUsage(prompt_token_count=500, candidates_token_count=200),
            isolation_scope="fc_abc",
        )
        delta = _build_turn_delta([event], self._now())
        assert delta.input_tokens_increment == 500
        assert delta.output_tokens_increment == 200

    def test_event_with_both_adk2_fields_not_dropped(self) -> None:
        from types import SimpleNamespace as _NS

        node_info = _NS(path="coordinator@1", output_for=["task_1"])
        event = _MockEvent(
            author="coordinator",
            usage=_MockUsage(prompt_token_count=800, candidates_token_count=300),
            node_info=node_info,
            isolation_scope="fc_xyz",
        )
        delta = _build_turn_delta([event], self._now())
        assert delta.input_tokens_increment == 800
        assert delta.output_tokens_increment == 300

    def test_llm_event_with_node_info_increments_message_count(self) -> None:
        from types import SimpleNamespace as _NS

        node_info = _NS(path="task_specialist@1", output_for=[])
        event = _MockEvent(
            author="task_specialist",
            usage=_MockUsage(prompt_token_count=400, candidates_token_count=150),
            node_info=node_info,
        )
        delta = _build_turn_delta([event], self._now())
        assert delta.message_count == 1


# ---------------------------------------------------------------------------
# Defensive event-identity deduplication (AH-PRD-14 §2 / Decision 1)
# ---------------------------------------------------------------------------


class TestBuildTurnDeltaEventIdentityDedupe:
    """Events with the same id must only fold into counters once."""

    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_duplicate_event_id_not_double_counted_tokens(self) -> None:
        usage = _MockUsage(prompt_token_count=1250, candidates_token_count=380, cached_content_token_count=200)
        event = _MockEvent(usage=usage, event_id="evt-1")
        delta = _build_turn_delta([event, event], self._now())
        assert delta.input_tokens_increment == 1050
        assert delta.output_tokens_increment == 380

    def test_duplicate_event_id_not_double_counted_message(self) -> None:
        event = _MockEvent(author="model", event_id="evt-model-1")
        delta = _build_turn_delta([event, event], self._now())
        assert delta.message_count == 1

    def test_different_event_ids_both_counted(self) -> None:
        usage = _MockUsage(prompt_token_count=500, candidates_token_count=100)
        ev1 = _MockEvent(usage=usage, event_id="evt-a")
        ev2 = _MockEvent(usage=usage, event_id="evt-b")
        delta = _build_turn_delta([ev1, ev2], self._now())
        assert delta.input_tokens_increment == 1000
        assert delta.output_tokens_increment == 200

    def test_event_without_id_falls_through_dedupe(self) -> None:
        """Events with no id attribute bypass dedupe and are counted normally."""
        usage = _MockUsage(prompt_token_count=300, candidates_token_count=100)
        event = _MockEvent(usage=usage)  # no event_id
        delta = _build_turn_delta([event, event], self._now())
        # No id → no dedupe → both folds counted (preserves current behaviour)
        assert delta.input_tokens_increment == 600
        assert delta.output_tokens_increment == 200

    def test_duplicate_event_does_not_overwrite_final_text(self) -> None:
        """A replayed event is skipped before final-text extraction runs."""
        event = _MockEvent(author="model", is_final=True, parts=["hello"], event_id="evt-final-1")
        delta = _build_turn_delta([event, event], self._now())
        assert delta.last_message_preview == "hello"


# ---------------------------------------------------------------------------
# Multi-author message count (AH-PRD-14 §7 AC-2 / Decision 2)
# ---------------------------------------------------------------------------


class TestBuildTurnDeltaMultiAuthorMessageCount:
    """Non-user, non-model authors carrying usage_metadata contribute +1 to
    message_count.  Tool-call events and events without usage_metadata from
    the same authors do not."""

    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _usage(self) -> _MockUsage:
        return _MockUsage(prompt_token_count=100, candidates_token_count=50)

    def test_coordinator_with_usage_metadata_increments(self) -> None:
        delta = _build_turn_delta([_MockEvent(author="coordinator", usage=self._usage())], self._now())
        assert delta.message_count == 1

    def test_specialist_a_with_usage_metadata_increments(self) -> None:
        delta = _build_turn_delta([_MockEvent(author="specialist_a", usage=self._usage())], self._now())
        assert delta.message_count == 1

    def test_specialist_b_with_usage_metadata_increments(self) -> None:
        delta = _build_turn_delta([_MockEvent(author="specialist_b", usage=self._usage())], self._now())
        assert delta.message_count == 1

    def test_task_specialist_with_usage_metadata_increments(self) -> None:
        delta = _build_turn_delta([_MockEvent(author="task_specialist", usage=self._usage())], self._now())
        assert delta.message_count == 1

    def test_all_four_supervisor_authors_each_increment_once(self) -> None:
        """Four distinct supervisor-authored LLM responses contribute 4 to message_count."""
        events = [
            _MockEvent(author="coordinator", usage=self._usage()),
            _MockEvent(author="specialist_a", usage=self._usage()),
            _MockEvent(author="specialist_b", usage=self._usage()),
            _MockEvent(author="task_specialist", usage=self._usage()),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.message_count == 4

    def test_tool_call_from_supervisor_author_does_not_increment_message_count(self) -> None:
        """get_function_calls() returning non-empty excludes the event from message_count
        but still increments tool_call_count."""
        fn_call = MagicMock()
        events = [
            _MockEvent(author="coordinator", fn_calls=[fn_call], usage=self._usage()),
            _MockEvent(author="specialist_a", fn_calls=[fn_call], usage=self._usage()),
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.message_count == 0
        assert delta.tool_call_count == 2

    def test_supervisor_author_without_usage_metadata_does_not_increment(self) -> None:
        """Non-user, non-model authors without usage_metadata do not count."""
        events = [
            _MockEvent(author="coordinator"),   # no usage
            _MockEvent(author="specialist_a"),  # no usage
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.message_count == 0

    def test_legacy_user_model_authors_still_increment_without_usage_metadata(self) -> None:
        """Preserves legacy behaviour: user and model count without needing usage_metadata."""
        events = [
            _MockEvent(author="user"),   # no usage
            _MockEvent(author="model"),  # no usage
        ]
        delta = _build_turn_delta(events, self._now())
        assert delta.message_count == 2


# ---------------------------------------------------------------------------
# AH-PRD-15 re-plan: isolated AgentTool leaf billing capture
# ---------------------------------------------------------------------------


class TestAgentToolBillingIntegration:
    """The leaf's usage_metadata (dropped by AgentTool.run_async, #3984) is parked
    in the per-turn sink and folded into the after-callback's billed delta."""

    def _now(self) -> datetime:
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_build_turn_delta_folds_extra_tokens(self) -> None:
        from shared.token_accounting import BillableTokenCounts

        # No events at all, but an isolated leaf captured tokens out-of-band.
        delta = _build_turn_delta(
            [], self._now(), extra=BillableTokenCounts(input=300, output=80, reasoning=5)
        )
        assert delta.input_tokens_increment == 300
        assert delta.output_tokens_increment == 80
        assert delta.reasoning_tokens_increment == 5
        # current_context_tokens accumulates the same turn total.
        assert delta.current_context_tokens == 385

    def test_extra_adds_to_event_tokens_no_double_count(self) -> None:
        from shared.token_accounting import BillableTokenCounts

        # The root/specialist model events ARE in session.events (counted here);
        # the leaf tokens are NOT (extra) — the two sources are additive, distinct.
        events = [_MockEvent(author="model", usage=_MockUsage(prompt_token_count=100, candidates_token_count=20))]
        delta = _build_turn_delta(
            events, self._now(), extra=BillableTokenCounts(input=300, output=80)
        )
        assert delta.input_tokens_increment == 400  # 100 (event) + 300 (leaf)
        assert delta.output_tokens_increment == 100  # 20 (event) + 80 (leaf)

    def test_after_callback_bills_captured_leaf_tokens(self) -> None:
        from app.adk.agents.agent_tool_billing import (
            capture_agent_tool_usage,
            reset_for_tests,
            set_outer_turn_id,
        )

        reset_for_tests()
        # Simulate the turn: before-callback bound the turn id; the isolated leaf's
        # after_model_callback parked its usage. The root session.events do NOT
        # contain the leaf events (AgentTool drops them — #3984).
        set_outer_turn_id("inv-1")
        leaf_response = SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=300,
                candidates_token_count=80,
                thoughts_token_count=0,
                cached_content_token_count=0,
            )
        )
        capture_agent_tool_usage(None, leaf_response)

        ctx = _make_callback_context(parent_agent=None, invocation_id="inv-1")
        with patch(
            "app.adk.agents.chat_callbacks._post_side_table_update"
        ) as mock_post:
            chat_after_agent_callback(ctx)

        mock_post.assert_called_once()
        posted_delta = mock_post.call_args.kwargs["delta"]
        # Wire format sentinel-encodes increments.
        assert posted_delta["input_tokens_total"] == {"_increment": 300}
        assert posted_delta["output_tokens_total"] == {"_increment": 80}
        reset_for_tests()

    def test_after_callback_drains_one_shot(self) -> None:
        from app.adk.agents.agent_tool_billing import (
            capture_agent_tool_usage,
            reset_for_tests,
            set_outer_turn_id,
        )

        reset_for_tests()
        set_outer_turn_id("inv-1")
        capture_agent_tool_usage(
            None,
            SimpleNamespace(
                usage_metadata=SimpleNamespace(
                    prompt_token_count=50,
                    candidates_token_count=5,
                    thoughts_token_count=0,
                    cached_content_token_count=0,
                )
            ),
        )
        ctx = _make_callback_context(parent_agent=None, invocation_id="inv-1")
        with patch("app.adk.agents.chat_callbacks._post_side_table_update") as mock_post:
            chat_after_agent_callback(ctx)  # drains
            chat_after_agent_callback(ctx)  # second flush sees an empty sink

        first = mock_post.call_args_list[0].kwargs["delta"]
        second = mock_post.call_args_list[1].kwargs["delta"]
        assert first["input_tokens_total"] == {"_increment": 50}
        assert second["input_tokens_total"] == {"_increment": 0}
        reset_for_tests()

    def test_before_callback_binds_turn_id_for_capture(self) -> None:
        from app.adk.agents.agent_tool_billing import (
            capture_agent_tool_usage,
            drain_turn_billing,
            reset_for_tests,
        )

        reset_for_tests()
        ctx = _make_callback_context(parent_agent=None, invocation_id="inv-xyz")
        with patch("app.adk.agents.chat_callbacks._post_side_table_update"):
            chat_before_agent_callback(ctx)
        # After before-callback bound the id, a leaf capture lands under it.
        capture_agent_tool_usage(
            None,
            SimpleNamespace(
                usage_metadata=SimpleNamespace(
                    prompt_token_count=12,
                    candidates_token_count=3,
                    thoughts_token_count=0,
                    cached_content_token_count=0,
                )
            ),
        )
        drained = drain_turn_billing("inv-xyz")
        assert (drained.input, drained.output) == (12, 3)
        reset_for_tests()
