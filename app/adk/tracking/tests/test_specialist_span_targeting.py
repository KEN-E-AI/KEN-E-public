"""Regression tests: AH-35 specialist attributes land on the specialist's OWN
Weave span, not the root span.

The original bug (PR #842) appended the AH-35 ``after_agent_callback`` AFTER
``weave_after_agent_callback``. ADK runs after-callbacks in list order, and
``weave_after_agent_callback`` finishes and pops the agent's span — so by the
time the AH-35 callback ran, ``weave.get_current_call()`` resolved to the
PARENT (root) span and the six attributes were written there instead of on the
specialist's span.

These tests drive the REAL ``set_specialist_span_attrs`` + the REAL
``weave_after_agent_callback`` in the production order (AH-35 write first, span
finish second) against a ``RecordingWeaveClient`` and assert the attributes
land on the specialist child span and NOT on the root.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adk.agents.utils.review_pipeline_tracing import set_specialist_span_attrs
from app.adk.tracking import callbacks as cb
from app.adk.tracking.tests._weave_recording import recording_weave_client

_PREFIX = "google_analytics_specialist_review"


def _drive_after(ctx: Any) -> None:
    """Run weave_after_agent_callback against the recording client.

    ``_weave_call_context.pop_call`` is a no-op here — the RecordingWeaveClient's
    ``finish_call`` already pops its own stack.
    """
    with (
        patch.object(cb, "_weave_call_context", MagicMock()),
    ):
        cb.weave_after_agent_callback(callback_context=ctx)


def test_attrs_land_on_specialist_span_not_root_in_production_order() -> None:
    """With the production order [ah35-write, weave_after], the six attributes
    land on the specialist span; the root span carries none of them."""
    with recording_weave_client() as client:
        if client is None:
            pytest.skip("weave package not installed — cannot record spans")

        # Model weave_before having created the root then the specialist span.
        root_call = client.create_call("ken_e")
        spec_call = client.create_call("google_analytics_specialist")

        # Seed the per-agent span stack exactly as the two weave_before calls
        # would (root at the bottom, specialist on top).
        cb._weave_agent_span_stack.set([(root_call, None), (spec_call, None)])

        ctx = MagicMock()
        ctx.state = {}  # weave_after reads temp:_last_model_output → absent

        with patch.object(cb, "_weave_get_client", return_value=client):
            # 1) AH-35 write — runs while the specialist span is still current
            #    (this is what the AH-35 callback does, inserted BEFORE
            #    weave_after).
            set_specialist_span_attrs(
                specialist_name="google_analytics_specialist",
                criteria="Cite 3 sources.",
                final_state={f"{_PREFIX}_feedback": ""},
                prefix=_PREFIX,
                total_iterations=0,
                cache_hit=False,
                agent_kind="loop_pipeline",
            )
            # 2) weave_after finishes + pops the specialist span, then the root.
            _drive_after(ctx)
            _drive_after(ctx)

    tree = client.tree_root()
    assert tree is not None
    assert tree["name"] == "ken_e"

    spec_node = tree["children"][0]
    assert spec_node["name"] == "google_analytics_specialist"
    assert spec_node["summary"] == {
        "specialist_name": "google_analytics_specialist",
        "agent_kind": "loop_pipeline",
        "cache_hit": False,
        "exit_reason": "approved",
        "total_iterations": 0,
        "output_key_prefix": _PREFIX,
    }

    # The root span must NOT carry any specialist attributes — that was the bug.
    assert "specialist_name" not in tree["summary"]
    assert "exit_reason" not in tree["summary"]


def test_root_span_finishes_when_specialist_runs() -> None:
    """The root span is finished (not orphaned) after a nested specialist span:
    the per-agent stack pops each frame independently."""
    with recording_weave_client() as client:
        if client is None:
            pytest.skip("weave package not installed — cannot record spans")

        root_call = client.create_call("ken_e")
        spec_call = client.create_call("google_analytics_specialist")
        cb._weave_agent_span_stack.set([(root_call, None), (spec_call, None)])

        ctx = MagicMock()
        ctx.state = {}
        with patch.object(cb, "_weave_get_client", return_value=client):
            _drive_after(ctx)  # specialist
            _drive_after(ctx)  # root

        # Both frames popped — nothing left dangling.
        assert (cb._weave_agent_span_stack.get() or []) == []

    # tree_root() asserts no unfinished calls remain (raises otherwise).
    tree = client.tree_root()
    assert tree["name"] == "ken_e"
    assert tree["output"] == {"status": "completed"}
    assert tree["children"][0]["output"] == {"status": "completed"}
