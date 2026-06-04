"""Tests for the RecordingWeaveClient test helper.

Coverage:
1. Synthetic tree shape: parent → 2 children → grandchild reconstructed correctly.
2. Unbalanced finish_call raises AssertionError.
3. tree_root() returns None when no calls were made.
"""

from __future__ import annotations

import pytest

from app.adk.tracking.tests._weave_recording import RecordingWeaveClient

# ---------------------------------------------------------------------------
# 1. Synthetic tree shape
# ---------------------------------------------------------------------------


def test_synthetic_tree_shape() -> None:
    """Build a parent → 2 children → grandchild tree and assert the
    reconstructed dict matches the expected shape."""
    client = RecordingWeaveClient()

    # root
    root_call = client.create_call("root_op", inputs={"x": 1})

    # child A (has a grandchild)
    child_a_call = client.create_call("child_a", inputs={"y": 2})
    grandchild_call = client.create_call("grandchild", inputs={"z": 3})

    # write to summary — mutable dict
    grandchild_call.summary["metric"] = 42
    client.finish_call(grandchild_call, output="grandchild_output")

    child_a_call.summary["status"] = "ok"
    client.finish_call(child_a_call, output="child_a_output")

    # child B (leaf)
    child_b_call = client.create_call("child_b", inputs={"w": 4})
    client.finish_call(child_b_call, output="child_b_output")

    root_call.summary["done"] = True
    client.finish_call(root_call, output="root_output")

    tree = client.tree_root()
    assert tree is not None

    # root
    assert tree["name"] == "root_op"
    assert tree["inputs"] == {"x": 1}
    assert tree["output"] == "root_output"
    assert tree["summary"] == {"done": True}
    assert len(tree["children"]) == 2

    # child A
    child_a = tree["children"][0]
    assert child_a["name"] == "child_a"
    assert child_a["inputs"] == {"y": 2}
    assert child_a["output"] == "child_a_output"
    assert child_a["summary"] == {"status": "ok"}
    assert len(child_a["children"]) == 1

    # grandchild
    grandchild = child_a["children"][0]
    assert grandchild["name"] == "grandchild"
    assert grandchild["inputs"] == {"z": 3}
    assert grandchild["output"] == "grandchild_output"
    assert grandchild["summary"] == {"metric": 42}
    assert grandchild["children"] == []

    # child B (leaf)
    child_b = tree["children"][1]
    assert child_b["name"] == "child_b"
    assert child_b["inputs"] == {"w": 4}
    assert child_b["output"] == "child_b_output"
    assert child_b["children"] == []


# ---------------------------------------------------------------------------
# 2. Unbalanced calls raise AssertionError
# ---------------------------------------------------------------------------


def test_unbalanced_calls_raises_on_excess_finish() -> None:
    """finish_call raises AssertionError when called with an empty stack."""
    client = RecordingWeaveClient()
    call = client.create_call("solo_op")
    client.finish_call(call)

    with pytest.raises(AssertionError, match="empty stack"):
        # Calling finish_call a second time with nothing left on the stack
        client.finish_call(call)


def test_unbalanced_calls_raises_on_unfinished() -> None:
    """tree_root() raises AssertionError when there are unfinished calls."""
    client = RecordingWeaveClient()
    client.create_call("open_op")
    # intentionally NOT calling finish_call

    with pytest.raises(AssertionError, match="unfinished call"):
        client.tree_root()


def test_unbalanced_calls_raises_on_mismatched_call() -> None:
    """finish_call raises AssertionError when the call object does not match
    the top of the stack."""
    client = RecordingWeaveClient()
    call_a = client.create_call("op_a")
    call_b = client.create_call("op_b")

    with pytest.raises(AssertionError, match="mismatch"):
        # finish outer before finishing inner — wrong order
        client.finish_call(call_a)

    # clean up to avoid side effects
    client.finish_call(call_b)


# ---------------------------------------------------------------------------
# 3. tree_root() returns None when no calls recorded
# ---------------------------------------------------------------------------


def test_tree_root_none_when_no_calls() -> None:
    """tree_root() returns None when create_call was never called."""
    client = RecordingWeaveClient()
    assert client.tree_root() is None
