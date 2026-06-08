"""Unit tests for _function_event_invokes helper and _VISUALIZATION_TOOL_NAME constant.

AH-157: verifies the detection helper used to gate per-turn artifact extraction.

References:
  - AH-PRD-04 §4.3 (session-state slot)
  - AH-157 Implementation Plan Task 1
  - app/adk/tools/function_tools/create_visualization.py (tool registration name)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import (
    _VISUALIZATION_TOOL_NAME,
    _function_event_invokes,
)

# ---------------------------------------------------------------------------
# 1 — Constant validation
# ---------------------------------------------------------------------------


def test_visualization_tool_name_matches_registration():
    """_VISUALIZATION_TOOL_NAME must equal the string passed to register_function_tool().

    The canonical registration site is create_visualization.py. This test is the
    value-level sync check described in the AH-157 risk table: if the tool is ever
    renamed, this test fails and forces a coordinated update of chat.py.
    """
    assert _VISUALIZATION_TOOL_NAME == "create_visualization"


# ---------------------------------------------------------------------------
# 2 — _function_event_invokes truth table
# ---------------------------------------------------------------------------


def test_function_call_matching_tool_returns_true():
    part = {"function_call": {"name": "create_visualization", "args": {}}}
    assert _function_event_invokes(part, "create_visualization") is True


def test_function_response_matching_tool_returns_true():
    part = {"function_response": {"name": "create_visualization", "response": {}}}
    assert _function_event_invokes(part, "create_visualization") is True


def test_function_call_other_tool_returns_false():
    part = {"function_call": {"name": "list_accounts", "args": {}}}
    assert _function_event_invokes(part, "create_visualization") is False


def test_function_response_other_tool_returns_false():
    part = {"function_response": {"name": "search_kb", "response": {}}}
    assert _function_event_invokes(part, "create_visualization") is False


def test_text_part_returns_false():
    part = {"text": "Hello, world!"}
    assert _function_event_invokes(part, "create_visualization") is False


def test_empty_dict_returns_false():
    assert _function_event_invokes({}, "create_visualization") is False


def test_non_dict_returns_false():
    assert _function_event_invokes("not a dict", "create_visualization") is False  # type: ignore[arg-type]
    assert _function_event_invokes(None, "create_visualization") is False  # type: ignore[arg-type]
    assert _function_event_invokes(42, "create_visualization") is False  # type: ignore[arg-type]


def test_function_call_missing_name_returns_false():
    part = {"function_call": {"args": {}}}  # no "name" key
    assert _function_event_invokes(part, "create_visualization") is False


def test_function_call_name_none_returns_false():
    part = {"function_call": {"name": None}}
    assert _function_event_invokes(part, "create_visualization") is False


def test_both_function_call_and_response_prefers_call():
    """When both function_call and function_response keys are present (unusual but valid),
    a match on either returns True.
    """
    part = {
        "function_call": {"name": "create_visualization"},
        "function_response": {"name": "other_tool"},
    }
    assert _function_event_invokes(part, "create_visualization") is True


def test_function_call_name_wrong_case_returns_false():
    """Tool name matching is case-sensitive (registration name is lowercase)."""
    part = {"function_call": {"name": "Create_Visualization"}}
    assert _function_event_invokes(part, "create_visualization") is False
