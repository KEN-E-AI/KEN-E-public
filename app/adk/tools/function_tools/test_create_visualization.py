"""Unit tests for app.adk.tools.function_tools.create_visualization (AH-131).

Covers PRD §7 AC-1 through AC-3 and the factory-wiring verification:

  AC-1  Builds a valid Vega-Lite v6 spec, appends to response_artifacts
        (two calls → length 2, never overwrites).
  AC-2  Returns a confirmation string containing title, chart_type, data-point count.
  AC-3  Returns a clear ERROR string on invalid JSON; spec has no config block and no
        hardcoded mark.color; emitted Artifact passes model validation.
  Wiring  hierarchy.py side-effect import causes create_visualization to appear in
          resolve_default_global_tools() output (verifies AH-PRD-06 PR-C wiring).
"""

from __future__ import annotations

import json
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.adk.tools.registry.function_tool_registry import (
    restore_function_tool_registry,
    snapshot_function_tool_registry,
)

# ---------------------------------------------------------------------------
# Registry isolation — prevent leakage across suites
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None, None, None]:
    """Snapshot the registry, ensure create_visualization is registered, then restore.

    Importing the module fires the module-bottom registration side effect.
    Restoring the snapshot on teardown — rather than clearing — prevents this
    suite from stranding an empty registry in adjacent suites (the process-global
    singleton failure mode documented in function_tool_registry.py).
    """
    import app.adk.tools.function_tools.create_visualization  # noqa: F401

    snapshot = snapshot_function_tool_registry()
    yield
    restore_function_tool_registry(snapshot)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_ctx(initial_state: dict[str, Any] | None = None) -> SimpleNamespace:
    """Return a minimal ToolContext stand-in with a ``.state`` dict."""
    return SimpleNamespace(state=dict(initial_state or {}))


def _get_tool() -> Any:
    from app.adk.tools.function_tools.create_visualization import create_visualization

    return create_visualization


_SAMPLE_DATA = json.dumps([{"date": "2024-01-01", "sessions": 100}])
_SAMPLE_ENCODING = json.dumps(
    {"x": {"field": "date", "type": "temporal"}, "y": {"field": "sessions", "type": "quantitative"}}
)


# ---------------------------------------------------------------------------
# TestSpecAuthoring — AC-1, AC-3 (spec structure rules)
# ---------------------------------------------------------------------------


class TestSpecAuthoring:
    def test_happy_path_spec_shape(self) -> None:
        """Valid inputs produce a Vega-Lite v6 spec with the expected structure."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="line",
            title="Sessions Over Time",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )

        assert result.startswith("Visualization created:")
        artifacts = ctx.state["response_artifacts"]
        assert len(artifacts) == 1
        artifact = artifacts[0]

        spec = artifact["spec"]
        assert spec["$schema"] == "https://vega.github.io/schema/vega-lite/v6.json"
        assert spec["title"] == "Sessions Over Time"
        assert spec["data"]["values"] == json.loads(_SAMPLE_DATA)
        assert spec["mark"] == "line"
        assert spec["encoding"] == json.loads(_SAMPLE_ENCODING)

    def test_no_config_block_in_spec(self) -> None:
        """Spec must not contain a config block (PRD §4.1, Artifact validator)."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="bar",
            title="Test",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        spec = ctx.state["response_artifacts"][0]["spec"]
        assert "config" not in spec

    def test_mark_is_bare_string_no_color(self) -> None:
        """mark must be a bare string (not an object), so no mark.color can exist."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="bar",
            title="Test",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        spec = ctx.state["response_artifacts"][0]["spec"]
        mark = spec["mark"]
        # mark is a bare string (not an object), so mark.color cannot exist.
        assert isinstance(mark, str)

    def test_chart_type_suggestion_stored_in_metadata(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="area",
            title="Area Chart",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        metadata = ctx.state["response_artifacts"][0]["metadata"]
        assert metadata["chart_type_suggestion"] == "area"

    def test_invalid_chart_type_raises_and_returns_error(self) -> None:
        """Pydantic rejects an invalid chart_type via ArtifactMetadata validation.

        Note: Python does not enforce Literal type hints at call time, so
        "scatter" passes the function signature and is only rejected when
        Artifact(...) runs Pydantic validation on chart_type_suggestion.
        """
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="scatter",  # not in ChartType literal — intentional for error-path test
            title="Bad Chart",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert result.startswith("ERROR:")
        # State must be unchanged — no artifact written on validation failure.
        assert "response_artifacts" not in ctx.state


# ---------------------------------------------------------------------------
# TestAppendSemantics — AC-1 (append-not-overwrite)
# ---------------------------------------------------------------------------


class TestAppendSemantics:
    def test_two_calls_accumulate_to_length_two(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="line",
            title="Chart A",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        create_visualization(
            chart_type="bar",
            title="Chart B",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert len(ctx.state["response_artifacts"]) == 2

    def test_existing_artifacts_preserved(self) -> None:
        """A pre-existing artifact in the list is not overwritten."""
        create_visualization = _get_tool()
        other_artifact = {"type": "text", "spec": {}, "metadata": {}}
        ctx = _fake_ctx({"response_artifacts": [other_artifact]})
        create_visualization(
            chart_type="line",
            title="New Chart",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        artifacts = ctx.state["response_artifacts"]
        assert len(artifacts) == 2
        assert artifacts[0] is other_artifact

    def test_first_call_initializes_list(self) -> None:
        """response_artifacts is created on first call even if the key is absent."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        assert "response_artifacts" not in ctx.state
        create_visualization(
            chart_type="arc",
            title="Pie Chart",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert "response_artifacts" in ctx.state
        assert len(ctx.state["response_artifacts"]) == 1


# ---------------------------------------------------------------------------
# TestConfirmationString — AC-2
# ---------------------------------------------------------------------------


class TestConfirmationString:
    def test_contains_title_chart_type_and_count(self) -> None:
        create_visualization = _get_tool()
        data = json.dumps([{"x": 1}, {"x": 2}, {"x": 3}])
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="bar",
            title="My Bar Chart",
            data=data,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert "My Bar Chart" in result
        assert "bar" in result
        assert "3" in result  # data-point count

    def test_confirmation_format(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="line",
            title="Trend",
            data=json.dumps([{"t": 1}]),
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert result == "Visualization created: Trend (line chart, 1 data point)"

    def test_confirmation_plural(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="bar",
            title="Multi",
            data=json.dumps([{"t": 1}, {"t": 2}]),
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert result == "Visualization created: Multi (bar chart, 2 data points)"


# ---------------------------------------------------------------------------
# TestInvalidJsonGraceful — AC-3 (error handling)
# ---------------------------------------------------------------------------


class TestInvalidJsonGraceful:
    def test_invalid_data_returns_error_string(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="line",
            title="Bad",
            data="not-json",
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert result.startswith("ERROR:")
        assert "response_artifacts" not in ctx.state

    def test_invalid_encoding_returns_error_string(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="bar",
            title="Bad",
            data=_SAMPLE_DATA,
            encoding='["unclosed',
            tool_context=ctx,
        )
        assert result.startswith("ERROR:")
        assert "response_artifacts" not in ctx.state

    def test_no_exception_escapes_on_bad_data(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        # Must not raise — any exception here would be a bug.
        result = create_visualization(
            chart_type="line",
            title="T",
            data="{bad",
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert isinstance(result, str)

    def test_no_exception_escapes_on_bad_encoding(self) -> None:
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="line",
            title="T",
            data=_SAMPLE_DATA,
            encoding="{bad",
            tool_context=ctx,
        )
        assert isinstance(result, str)

    def test_data_non_array_returns_error(self) -> None:
        """data must be a JSON array; bare objects are rejected."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="bar",
            title="T",
            data='{"key": "value"}',  # JSON object, not array
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        assert result.startswith("ERROR:")
        assert "response_artifacts" not in ctx.state

    def test_encoding_non_object_returns_error(self) -> None:
        """encoding must be a JSON object; arrays are rejected."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        result = create_visualization(
            chart_type="bar",
            title="T",
            data=_SAMPLE_DATA,
            encoding='["not", "an", "object"]',
            tool_context=ctx,
        )
        assert result.startswith("ERROR:")
        assert "response_artifacts" not in ctx.state


# ---------------------------------------------------------------------------
# TestNoToolContext
# ---------------------------------------------------------------------------


class TestNoToolContext:
    def test_none_context_returns_confirmation_without_raising(self) -> None:
        create_visualization = _get_tool()
        result = create_visualization(
            chart_type="line",
            title="Headless Chart",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=None,
        )
        assert "Headless Chart" in result
        assert result.startswith("Visualization created:")

    def test_none_context_with_empty_data_array_succeeds(self) -> None:
        """Empty data array is valid — returns confirmation with 0 data points."""
        create_visualization = _get_tool()
        result = create_visualization(
            chart_type="bar",
            title="T",
            data="[]",
            encoding=_SAMPLE_ENCODING,
            tool_context=None,
        )
        assert isinstance(result, str)
        assert result.startswith("Visualization created:")


# ---------------------------------------------------------------------------
# TestArtifactModelValidation — AC-1/AC-3 (round-trip + Pydantic validators)
# ---------------------------------------------------------------------------


class TestArtifactModelValidation:
    def test_emitted_dict_round_trips_through_artifact_model_validate(self) -> None:
        """The dict stored in response_artifacts must pass Artifact.model_validate."""
        from shared.artifact_models import Artifact

        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="point",
            title="Scatter",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        artifact_dict = ctx.state["response_artifacts"][0]
        # Should not raise — confirms no forbidden keys leaked into the dict.
        validated = Artifact.model_validate(artifact_dict)
        assert validated.metadata.chart_type_suggestion == "point"

    def test_dict_is_json_serializable(self) -> None:
        """Session state must be JSON-serializable for ADK persistence."""
        create_visualization = _get_tool()
        ctx = _fake_ctx()
        create_visualization(
            chart_type="line",
            title="JSON Test",
            data=_SAMPLE_DATA,
            encoding=_SAMPLE_ENCODING,
            tool_context=ctx,
        )
        artifact_dict = ctx.state["response_artifacts"][0]
        # Must not raise.
        serialized = json.dumps(artifact_dict)
        assert "visualization" in serialized

    def test_spec_config_block_rejected_by_artifact_model(self) -> None:
        """If a config block somehow entered the spec, Artifact validation catches it."""
        from shared.artifact_models import Artifact

        bad_spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "title": "Bad",
            "data": {"values": [{"x": 1}]},
            "mark": "bar",
            "encoding": {},
            "config": {"font": "Comic Sans"},  # forbidden
        }
        with pytest.raises(ValidationError):
            Artifact(
                type="visualization",
                spec=bad_spec,
                metadata={  # type: ignore[arg-type]
                    "chart_type_suggestion": "bar",
                    "title": "Bad",
                    "data_source": "agent",
                },
            )


# ---------------------------------------------------------------------------
# TestFactoryWiring — AH-PRD-06 PR-C wiring verification
# ---------------------------------------------------------------------------


class TestFactoryWiring:
    def test_create_visualization_present_in_default_global_tools(self) -> None:
        """hierarchy.py side-effect import causes create_visualization to appear
        in the resolver output, confirming the AH-PRD-06 PR-C wiring is intact."""
        import app.adk.agents.agent_factory.hierarchy  # noqa: F401 — triggers side-effect
        from app.adk.tools.registry.function_tool_registry import (
            resolve_default_global_tools,
        )
        from app.adk.tools.registry.tool_registry import get_default_registry

        tools = resolve_default_global_tools(get_default_registry())
        tool_names = [t.name for t in tools]
        assert "create_visualization" in tool_names

    def test_create_visualization_directly_registered(self) -> None:
        """get_function_tool('create_visualization') returns a non-None entry."""
        from app.adk.tools.registry.function_tool_registry import get_function_tool

        tool = get_function_tool("create_visualization")
        assert tool is not None
        assert tool.name == "create_visualization"
