"""Unit tests for chart re-attachment in get_conversation_history.

Charts are streamed inline during a live turn but live only in client state, so
a reload (or the session-status toggle that remounts the chat) must resurface
them from the persisted Vega-Lite specs. These tests cover the pure
turn-association helper and the end-to-end enrichment with all GCS / Firestore
interactions mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.chat.artifacts import VEGALITE_MIME
from src.kene_api.models.chat import ChatArtifactIndex
from src.kene_api.routers import chat as chat_module
from src.kene_api.routers.chat import (
    AgentEngineClient,
    _attach_artifacts_to_events,
)


# ── Pure association helper ──────────────────────────────────────────────────


class TestAttachArtifactsToEvents:
    def test_anchors_to_nearest_assistant_event(self) -> None:
        events = [
            {"role": "user", "timestamp": 100.0},
            {"role": "model", "timestamp": 105.0},  # turn 1 answer
            {"role": "user", "timestamp": 200.0},
            {"role": "model", "timestamp": 205.0},  # turn 2 answer
        ]
        # Chart created during turn 2 (just before its assistant text event).
        _attach_artifacts_to_events(events, [(204.0, {"type": "visualization"})])
        assert events[3]["artifacts"] == [{"type": "visualization"}]
        assert "artifacts" not in events[1]

    def test_user_events_are_never_anchors(self) -> None:
        events = [
            {"role": "user", "timestamp": 204.0},  # closest, but a user turn
            {"role": "model", "timestamp": 205.0},
        ]
        _attach_artifacts_to_events(events, [(204.0, {"type": "visualization"})])
        assert events[1]["artifacts"] == [{"type": "visualization"}]
        assert "artifacts" not in events[0]

    def test_multiple_charts_same_turn_accumulate(self) -> None:
        events = [{"role": "model", "timestamp": 105.0}]
        _attach_artifacts_to_events(events, [(104.0, {"a": 1}), (104.5, {"a": 2})])
        assert events[0]["artifacts"] == [{"a": 1}, {"a": 2}]

    def test_no_assistant_events_drops_artifacts(self) -> None:
        events = [{"role": "user", "timestamp": 100.0}]
        _attach_artifacts_to_events(events, [(100.0, {"type": "visualization"})])
        assert "artifacts" not in events[0]


# ── End-to-end enrichment in get_conversation_history ────────────────────────

_SPEC = {
    "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
    "title": "Sessions over time",
    "data": {"values": [{"x": 1, "y": 2}]},
    "mark": "line",
    "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
}


def _viz_row(created_at: datetime) -> ChatArtifactIndex:
    return ChatArtifactIndex(
        artifact_id="a" * 32,
        session_id="s1",
        filename="viz_sessions.json",
        mime_type=VEGALITE_MIME,
        size_bytes=100,
        version=0,
        gcs_path="gs://ken-e-dev-files-us/ken_e_chatbot/u1/s1/viz_sessions.json/0",
        created_by_tool="create_visualization",
        created_at=created_at,
    )


def _event(role: str, text: str, ts: float) -> SimpleNamespace:
    return SimpleNamespace(
        content=SimpleNamespace(role=role, parts=[SimpleNamespace(text=text)]),
        author="ken_e" if role == "model" else "user",
        timestamp=ts,
    )


def _client(events: list[SimpleNamespace]) -> AgentEngineClient:
    client = AgentEngineClient()
    client._session_service = AsyncMock()
    client._session_service.get_session = AsyncMock(
        return_value=SimpleNamespace(events=events)
    )
    return client


@pytest.fixture(autouse=True)
def _no_redis():
    fake = MagicMock()
    fake.is_available.return_value = False
    with patch.object(chat_module, "get_redis_service", return_value=fake):
        yield


def _patch_side_table(account_id: str | None = "acc_1") -> Any:
    svc = MagicMock()
    svc.find_session_for_user.return_value = (
        None if account_id is None else SimpleNamespace(account_id=account_id)
    )
    return patch.object(
        chat_module, "get_chat_side_table_service", return_value=svc
    )


class TestHistoryChartReattachment:
    @pytest.mark.asyncio
    async def test_persisted_chart_is_reattached_to_its_turn(self) -> None:
        created = datetime(2024, 1, 1, 12, 0, 4, tzinfo=timezone.utc)
        client = _client(
            [
                _event("user", "show me sessions", created.timestamp() - 4),
                _event("model", "Here you go", created.timestamp() + 1),
            ]
        )
        with (
            _patch_side_table(),
            patch.object(
                chat_module, "list_artifacts", return_value=[_viz_row(created)]
            ),
            patch.object(
                chat_module, "fetch_visualization_spec", return_value=_SPEC
            ),
        ):
            result = await client.get_conversation_history("u1", "s1")

        charts = result["events"][1]["artifacts"]
        assert charts == [
            {
                "type": "visualization",
                "spec": _SPEC,
                "metadata": {
                    "chart_type_suggestion": "line",
                    "title": "Sessions over time",
                    "data_source": "agent",
                    "description": None,
                },
            }
        ]

    @pytest.mark.asyncio
    async def test_no_viz_artifacts_leaves_events_untouched(self) -> None:
        client = _client([_event("model", "no charts here", 105.0)])
        with (
            _patch_side_table(),
            patch.object(chat_module, "list_artifacts", return_value=[]),
        ):
            result = await client.get_conversation_history("u1", "s1")
        assert "artifacts" not in result["events"][0]

    @pytest.mark.asyncio
    async def test_unresolvable_session_is_best_effort_noop(self) -> None:
        client = _client([_event("model", "answer", 105.0)])
        with _patch_side_table(account_id=None):
            result = await client.get_conversation_history("u1", "s1")
        assert "artifacts" not in result["events"][0]

    @pytest.mark.asyncio
    async def test_gcs_spec_fetch_failure_drops_only_that_chart(self) -> None:
        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        client = _client([_event("model", "answer", created.timestamp() + 1)])
        with (
            _patch_side_table(),
            patch.object(
                chat_module, "list_artifacts", return_value=[_viz_row(created)]
            ),
            patch.object(
                chat_module, "fetch_visualization_spec", return_value=None
            ),
        ):
            result = await client.get_conversation_history("u1", "s1")
        assert "artifacts" not in result["events"][0]
