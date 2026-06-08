"""E2E supervisor artifact-threading tests (AH-143 Task 7).

Verifies that a supervisor turn dispatching two task specialists each producing
a chart via create_visualization() surfaces both charts in ChatResponse.artifacts
and persists two ChatArtifactIndex rows.

These tests are marked ``@pytest.mark.llm`` because they assert artifact
threading through the AH-PRD-04 session-state pipeline; they require the
full pydantic Artifact model and the register_artifact wrapper, but can run
without a live Gemini model using deterministic mocks.

For the mandatory live-Gemini staging smoke (AH-PRD-05 merge blocker), a
separate staging run against the real Agent Engine is required. That smoke is
NOT part of this automated suite — see AH-PRD-05 §8 for the runbook.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pydantic.root_model  # noqa: F401  # force eager load (see test_supervisor_artifacts.py)
import pytest

from app.adk.tools.function_tools.testing import (
    make_register_artifact_mock,
    register_artifact_sys_modules_patch,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_SAMPLE_DATA = json.dumps([{"date": "2024-01-01", "sessions": 100}])
_SAMPLE_ENCODING = json.dumps(
    {"x": {"field": "date", "type": "temporal"}, "y": {"field": "sessions", "type": "quantitative"}}
)


def _make_tool_context(shared_state: dict[str, Any] | None = None, save_version: int = 0) -> MagicMock:
    """Build a minimal ToolContext mock."""
    ctx = MagicMock()
    ctx.save_artifact = AsyncMock(return_value=save_version)
    ctx.user_id = "user_e2e_test"
    ctx.session.id = "sess_e2e_test_001"
    state_dict: dict[str, Any] = shared_state if shared_state is not None else {}
    ctx.state = MagicMock()
    ctx.state.__setitem__ = lambda self, k, v: state_dict.__setitem__(k, v)
    ctx.state.__getitem__ = lambda self, k: state_dict[k]
    ctx.state.get = lambda k, d=None: state_dict.get(k, d)
    ctx.state.__contains__ = lambda self, k: k in state_dict
    invocation_ctx = MagicMock()
    invocation_ctx.app_name = "ken_e_chatbot"
    artifact_service = MagicMock()
    artifact_service.bucket_name = "ken-e-test-files-us"
    invocation_ctx.artifact_service = artifact_service
    ctx._invocation_context = invocation_ctx
    return ctx


async def _run_task_specialist(ctx: Any, title: str, chart_type: str = "bar") -> str:
    """Run a task-specialist simulation: call create_visualization once."""
    from app.adk.tools.function_tools.create_visualization import create_visualization

    return await create_visualization(
        chart_type=chart_type,
        title=title,
        data=_SAMPLE_DATA,
        encoding=_SAMPLE_ENCODING,
        tool_context=ctx,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.llm
class TestSupervisorArtifactsE2E:
    """E2E artifact-threading tests for the supervisor orchestration model."""

    def test_two_task_specialists_each_produce_one_artifact(self) -> None:
        """A supervisor turn with two task specialists surfaces two artifacts.

        Simulates the AH-PRD-05 sequential per-task delegation pattern:
          1. Coordinator resolves Task A; specialist runs → calls create_visualization().
          2. Coordinator resolves Task B; specialist runs → calls create_visualization().
          3. Turn completes; chat endpoint drains response_artifacts → ChatResponse.artifacts.

        Asserts:
          - response_artifacts contains 2 entries at turn end.
          - Both entries have the expected titles.
          - register_artifact was called twice (once per task).
        """
        mock_register = make_register_artifact_mock()
        shared_state: dict[str, Any] = {}

        with patch.dict(sys.modules, register_artifact_sys_modules_patch(mock_register)):
            ctx_a = _make_tool_context(shared_state=shared_state, save_version=0)
            ctx_b = _make_tool_context(shared_state=shared_state, save_version=1)

            asyncio.run(_run_task_specialist(ctx_a, title="GA Engagement Chart"))
            asyncio.run(_run_task_specialist(ctx_b, title="Meta Spend Chart"))

        # Both artifacts are in response_artifacts
        artifacts = shared_state.get("response_artifacts", [])
        assert len(artifacts) == 2
        titles = [a["metadata"]["title"] for a in artifacts]
        assert "GA Engagement Chart" in titles
        assert "Meta Spend Chart" in titles

        # register_artifact called once per specialist
        assert mock_register.await_count == 2

    def test_drain_produces_correct_chatresponse_shape(self) -> None:
        """Draining response_artifacts yields ChatResponse.artifacts with 2 entries.

        Uses the Artifact Pydantic model to validate the drained artifacts
        match the expected shape (type, spec, metadata).
        """
        from shared.artifact_models import Artifact

        mock_register = make_register_artifact_mock()
        shared_state: dict[str, Any] = {}

        with patch.dict(sys.modules, register_artifact_sys_modules_patch(mock_register)):
            ctx = _make_tool_context(shared_state=shared_state, save_version=0)
            asyncio.run(_run_task_specialist(ctx, title="Sessions Chart"))

            ctx2 = _make_tool_context(shared_state=shared_state, save_version=1)
            asyncio.run(_run_task_specialist(ctx2, title="Revenue Chart", chart_type="line"))

        # Simulate drain
        raw = shared_state.get("response_artifacts", [])
        assert len(raw) == 2

        for raw_artifact in raw:
            validated = Artifact.model_validate(raw_artifact)
            assert validated.type == "visualization"
            assert validated.spec is not None
            assert validated.metadata.chart_type_suggestion in ("bar", "line")

        # Drain + clear
        shared_state["response_artifacts"] = []
        assert shared_state["response_artifacts"] == []

    def test_register_artifact_created_by_tool_field(self) -> None:
        """register_artifact is called with created_by_tool='create_visualization'."""
        mock_register = make_register_artifact_mock()
        shared_state: dict[str, Any] = {}

        with patch.dict(sys.modules, register_artifact_sys_modules_patch(mock_register)):
            ctx = _make_tool_context(shared_state=shared_state)
            asyncio.run(_run_task_specialist(ctx, title="Provenance Test Chart"))

        args, kwargs = mock_register.call_args
        assert kwargs.get("created_by_tool") == "create_visualization"

    def test_artifact_content_is_valid_vegalite_json(self) -> None:
        """The content blob passed to register_artifact is valid Vega-Lite JSON."""
        mock_register = make_register_artifact_mock()
        shared_state: dict[str, Any] = {}

        with patch.dict(sys.modules, register_artifact_sys_modules_patch(mock_register)):
            ctx = _make_tool_context(shared_state=shared_state)
            asyncio.run(_run_task_specialist(ctx, title="Vega Lite Content Test"))

        args, kwargs = mock_register.call_args
        content = args[2] if len(args) > 2 else kwargs.get("content")
        assert content is not None

        raw_bytes = content.inline_data.data
        spec = json.loads(raw_bytes.decode("utf-8"))
        assert "$schema" in spec
        assert "vega-lite" in spec["$schema"]
        assert spec["title"] == "Vega Lite Content Test"
        assert content.inline_data.mime_type == "application/vnd.vegalite.v6+json"
