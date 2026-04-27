"""Tests for the Weave trace capture context manager.

These tests don't require a live wandb backend — they push synthetic
``Call``-shaped objects through the patched ``push_call`` to verify the
capture and validate-compliance flows.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests.integration.sprint6_harness.weave_trace_capture import (
    TraceCapture,
    replay_through_compliance,
)


def _make_call(attributes: dict[str, Any], **kw: Any) -> SimpleNamespace:
    """Synthesize a duck-typed weave Call for tests."""
    return SimpleNamespace(
        attributes=attributes,
        op_name=kw.get("op_name", "test_op"),
        trace_id=kw.get("trace_id", "trace_test_001"),
        id=kw.get("id", "call_test_001"),
    )


_COMPLIANT_ATTRS: dict[str, Any] = {
    "agent_id": "ken_e_chatbot",
    "agent_version": "v1.0.0",
    "account_id": "acc_harness_001",
    "session_id": "sess_harness_001",
    "user_id": "user_harness",
    "experiment_id": "baseline",
    "variant_name": "baseline",
    "environment": "development",
    "rollout_percentage": 100,
    "model_used": "gemini-2.5-pro",
    "temperature": 0.3,
    "max_output_tokens": 2500,
}


def test_capture_records_pushed_calls() -> None:
    from weave.trace.context import call_context

    with TraceCapture() as cap:
        call_context.push_call(_make_call(_COMPLIANT_ATTRS))
        call_context.push_call(_make_call({"agent_id": "x"}, op_name="other_op"))

    traces = cap.traces
    assert len(traces) == 2
    assert traces[0]["agent_id"] == "ken_e_chatbot"
    assert traces[0]["_weave_op_name"] == "test_op"
    assert traces[1]["_weave_op_name"] == "other_op"


def test_capture_unpatches_on_exit() -> None:
    from weave.trace.context import call_context

    original = call_context.push_call
    with TraceCapture():
        assert call_context.push_call is not original
    assert call_context.push_call is original


def test_replay_through_compliance_flags_compliant_and_noncompliant() -> None:
    bad_attrs = {**_COMPLIANT_ATTRS, "agent_id": ""}  # missing/empty -> non-compliant
    with TraceCapture() as cap:
        from weave.trace.context import call_context

        call_context.push_call(_make_call(_COMPLIANT_ATTRS))
        call_context.push_call(_make_call(bad_attrs))

    results = replay_through_compliance(cap.traces)
    assert len(results) == 2
    assert results[0].is_compliant is True
    assert results[1].is_compliant is False
    assert any(issue.field == "agent_id" for issue in results[1].issues)


def test_capture_swallows_record_errors() -> None:
    """A pathological Call that explodes on attribute access must not break push."""

    class Explosive:
        @property
        def attributes(self) -> Any:
            raise RuntimeError("boom")

        op_name = "x"
        trace_id = "y"
        id = "z"

    from weave.trace.context import call_context

    with TraceCapture() as cap:
        call_context.push_call(Explosive())  # must not raise

    # Either nothing recorded (preferred) or recorded with whatever survived.
    assert len(cap.traces) <= 1
