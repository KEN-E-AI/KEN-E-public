"""Unit tests for per-step status events (CH-71, Task 1).

Tests cover:
- _status_label_for_function_call returns None for function_response parts
- _status_label_for_function_call returns curated labels for known tools
- transfer_to_agent label uses agent_name arg when present
- transfer_to_agent label falls back to "Dispatching specialist…" without arg
- Unknown tools fall back to f"Running {tool_name}…"
- _STATUS_LABELS registry completeness for staging-incident tool names
- _format_sse "status" channel produces correct SSE frame
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.routers.chat import (
    _STATUS_LABELS,
    _format_sse,
    _status_label_for_function_call,
)

# Tool names observed in the 2026-06-10 staging incident (CH-71 AC-b).
STAGING_INCIDENT_TOOLS = [
    "create_visualization",
    "set_todo_list",
    "update_todo_list",
    "transfer_to_agent",
    "run_report_mt",
    "run_realtime_report_mt",
]


class TestStatusLabelForFunctionCall:
    def test_function_response_returns_none(self):
        part = {"function_response": {"name": "run_report_mt"}}
        assert _status_label_for_function_call(part) is None

    def test_non_function_part_returns_none(self):
        assert _status_label_for_function_call({"text": "hello"}) is None
        assert _status_label_for_function_call({}) is None
        assert _status_label_for_function_call({"function_call": "not_a_dict"}) is None

    def test_known_tools_have_curated_labels(self):
        for tool in ["create_visualization", "set_todo_list", "update_todo_list",
                     "run_report_mt", "run_realtime_report_mt"]:
            part = {"function_call": {"name": tool}}
            label = _status_label_for_function_call(part)
            assert label is not None and "Running " + tool not in label, (
                f"{tool} should have a curated label, got: {label}"
            )

    def test_transfer_to_agent_uses_agent_name(self):
        part = {"function_call": {"name": "transfer_to_agent", "args": {"agent_name": "google_analytics"}}}
        label = _status_label_for_function_call(part)
        assert label == "Dispatching google_analytics…"

    def test_transfer_to_agent_fallback_without_arg(self):
        part = {"function_call": {"name": "transfer_to_agent", "args": {}}}
        label = _status_label_for_function_call(part)
        assert label == "Dispatching specialist…"

    def test_transfer_to_agent_fallback_no_args_key(self):
        part = {"function_call": {"name": "transfer_to_agent"}}
        label = _status_label_for_function_call(part)
        assert label == "Dispatching specialist…"

    def test_transfer_to_agent_non_dict_args(self):
        part = {"function_call": {"name": "transfer_to_agent", "args": "not_a_dict"}}
        label = _status_label_for_function_call(part)
        assert label == "Dispatching specialist…"

    def test_unknown_tool_fallback(self):
        part = {"function_call": {"name": "some_unknown_tool_xyz"}}
        label = _status_label_for_function_call(part)
        assert label == "Running some_unknown_tool_xyz…"

    def test_staging_incident_tools_have_non_default_labels(self):
        """All tools observed in the 2026-06-10 staging incident must resolve to non-default labels."""
        for tool in STAGING_INCIDENT_TOOLS:
            part = {"function_call": {"name": tool}}
            if tool == "transfer_to_agent":
                part["function_call"]["args"] = {"agent_name": "ga"}
            label = _status_label_for_function_call(part)
            assert label is not None and f"Running {tool}" not in label, (
                f"Staging-incident tool '{tool}' fell back to default label: '{label}'"
            )


class TestFormatSseStatus:
    def test_status_channel_produces_event_frame(self):
        frame = _format_sse("status", "Creating visualization…", seq=0)
        assert frame.startswith("event: status\n")
        assert frame.endswith("\n\n")
        payload = json.loads(frame.split("data: ")[1].strip())
        assert payload["label"] == "Creating visualization…"
        assert payload["seq"] == 0
        assert "author" not in payload

    def test_status_channel_includes_author_when_not_model(self):
        frame = _format_sse("status", "Running GA report…", seq=3, author="ga_specialist")
        payload = json.loads(frame.split("data: ")[1].strip())
        assert payload["author"] == "ga_specialist"
        assert payload["seq"] == 3
        assert payload["label"] == "Running GA report…"

    def test_status_seq_increments_independently_from_reasoning(self):
        """Status seq counter is separate — this is a structural test that the format accepts seq."""
        f1 = _format_sse("status", "Running…", seq=0)
        f2 = _format_sse("status", "Running…", seq=1)
        p1 = json.loads(f1.split("data: ")[1].strip())
        p2 = json.loads(f2.split("data: ")[1].strip())
        assert p1["seq"] == 0
        assert p2["seq"] == 1


class TestStatusLabelsRegistry:
    def test_registry_has_all_staging_incident_tools_except_transfer(self):
        """Non-transfer staging-incident tools must be in _STATUS_LABELS."""
        tools_in_registry = [t for t in STAGING_INCIDENT_TOOLS if t != "transfer_to_agent"]
        for tool in tools_in_registry:
            assert tool in _STATUS_LABELS, f"'{tool}' missing from _STATUS_LABELS"
