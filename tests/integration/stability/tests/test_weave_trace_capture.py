"""Tests for the Weave trace capture context manager.

These tests don't require a live wandb backend — they drive the patched
``WeaveClient.finish_call`` directly with synthetic ``Call``-shaped
objects. The ``stub_finish_call`` fixture replaces the real
``WeaveClient.finish_call`` with a no-op **before** ``TraceCapture``
enters, so the capture's ``_original_finish`` reference is the stub
(and the patched wrapper's pass-through doesn't try to ship to wandb).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.integration.stability.weave_trace_capture import (
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


@pytest.fixture
def stub_finish_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``WeaveClient.finish_call`` with a no-op so tests don't hit wandb.

    Must run BEFORE ``TraceCapture.__enter__`` so the capture's
    ``_original_finish`` reference is the stub, not the real method.
    """
    from weave.trace.weave_client import WeaveClient

    monkeypatch.setattr(
        WeaveClient,
        "finish_call",
        lambda self, call, output=None, exception=None, *, op=None: None,
    )


def test_capture_records_finished_calls(stub_finish_call: None) -> None:
    from weave.trace.weave_client import WeaveClient

    with TraceCapture() as cap:
        WeaveClient.finish_call(None, _make_call(_COMPLIANT_ATTRS))
        WeaveClient.finish_call(
            None, _make_call({"agent_id": "x"}, op_name="other_op")
        )

    traces = cap.traces
    assert len(traces) == 2
    assert traces[0]["agent_id"] == "ken_e_chatbot"
    assert traces[0]["_weave_op_name"] == "test_op"
    assert traces[0]["_weave_call_id"] == "call_test_001"
    assert traces[1]["_weave_op_name"] == "other_op"


def test_capture_unpatches_on_exit(stub_finish_call: None) -> None:
    from weave.trace.weave_client import WeaveClient

    original = WeaveClient.finish_call
    with TraceCapture():
        assert WeaveClient.finish_call is not original
    assert WeaveClient.finish_call is original


def test_replay_through_compliance_flags_compliant_and_noncompliant(
    stub_finish_call: None,
) -> None:
    from weave.trace.weave_client import WeaveClient

    bad_attrs = {**_COMPLIANT_ATTRS, "agent_id": ""}  # missing/empty -> non-compliant
    with TraceCapture() as cap:
        WeaveClient.finish_call(None, _make_call(_COMPLIANT_ATTRS))
        WeaveClient.finish_call(None, _make_call(bad_attrs))

    results = replay_through_compliance(cap.traces)
    assert len(results) == 2
    assert results[0].is_compliant is True
    assert results[1].is_compliant is False
    assert any(issue.field == "agent_id" for issue in results[1].issues)


def test_capture_swallows_record_errors(stub_finish_call: None) -> None:
    """A pathological Call that explodes on attribute access must not break finish."""
    from weave.trace.weave_client import WeaveClient

    class Explosive:
        @property
        def attributes(self) -> Any:
            raise RuntimeError("boom")

        op_name = "x"
        trace_id = "y"
        id = "z"

    with TraceCapture() as cap:
        WeaveClient.finish_call(None, Explosive())  # must not raise

    assert len(cap.traces) == 0


def test_capture_calls_through_to_original(monkeypatch: pytest.MonkeyPatch) -> None:
    """The patched wrapper must still forward to the original finish_call."""
    from weave.trace.weave_client import WeaveClient

    seen: list[Any] = []
    monkeypatch.setattr(
        WeaveClient,
        "finish_call",
        lambda self, call, output=None, exception=None, *, op=None: seen.append(call),
    )

    with TraceCapture():
        synthetic = _make_call(_COMPLIANT_ATTRS)
        WeaveClient.finish_call(None, synthetic)

    assert len(seen) == 1
    assert seen[0] is synthetic
