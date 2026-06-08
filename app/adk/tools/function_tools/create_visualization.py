"""SDK function tool for creating Vega-Lite v6 chart artifacts.

AH-PRD-04 §4 / AH-131 — implements the ``create_visualization`` callable
described in data-visualization.md §4.1-4.2 and AC-1/2/3 of AH-131.

The tool appends a JSON-serializable artifact dict to
``tool_context.state["response_artifacts"]`` so multiple calls in one turn
accumulate (never overwrite). The upstream chat endpoint pops and clears that
key after the agent run (AH-132); the artifact Pydantic model is defined in
``shared.artifact_models`` (AH-130).

Module-bottom ``register_function_tool`` fires at import time so the registry
is populated before ``specialist_runtime.resolve_default_global_tools`` runs
in the agent factory. The side-effect import lives in
``app/adk/agents/agent_factory/hierarchy.py`` alongside the other
default-global tools (todo_list_tools, google_search, numerical_analyst).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.adk.tools.registry.function_tool_registry import register_function_tool
from shared.artifact_models import (
    Artifact,
    ArtifactMetadata,
    ChartType,
)
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

_RESPONSE_ARTIFACTS_KEY: str = "response_artifacts"


def create_visualization(
    chart_type: ChartType,
    title: str,
    data: str,
    encoding: str,
    description: str = "",
    tool_context: Any = None,
) -> str:
    """Create a Vega-Lite v6 visualization artifact from structured data.

    Parses the ``data`` and ``encoding`` JSON strings, builds a Vega-Lite v6
    spec (no ``config`` block, no hardcoded ``mark.color`` — theme is applied
    frontend-side), wraps the result in an ``Artifact``, and appends the
    artifact's dict representation to
    ``tool_context.state["response_artifacts"]``.

    Args:
        chart_type: Vega-Lite mark type. Use ``"point"`` for scatter plots.
        title: Human-readable chart title (shown above the chart).
        data: JSON string of data values — must be an array of objects.
        encoding: JSON string of a Vega-Lite encoding specification.
        description: Optional human-readable description of what the chart shows.
        tool_context: ADK ToolContext. When ``None`` (e.g. in unit tests not
            backed by an ADK runtime) the function still builds and validates the
            artifact and returns the confirmation string, but skips the session-
            state append.

    Returns:
        On success: confirmation string of the form
        ``"Visualization created: <title> (<chart_type> chart, <n> data points)"``.
        On error: string prefixed with ``"ERROR: "``; no exception escapes.
    """
    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as exc:
        logger.warning("create_visualization: invalid JSON in data arg: %s", exc)
        return f"ERROR: invalid JSON in data argument: {exc}"

    try:
        parsed_encoding = json.loads(encoding)
    except json.JSONDecodeError as exc:
        logger.warning("create_visualization: invalid JSON in encoding arg: %s", exc)
        return f"ERROR: invalid JSON in encoding argument: {exc}"

    if not isinstance(parsed_data, list):
        return "ERROR: data argument must be a JSON array of objects"
    if not isinstance(parsed_encoding, dict):
        return "ERROR: encoding argument must be a JSON object"

    # Plain spec: bare mark string (no {type: ...} object), no config block, no
    # hardcoded mark.color. The data.url and config bans are enforced again by the
    # Artifact validator below, providing defence-in-depth.
    spec: dict[str, Any] = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "title": title,
        "data": {"values": parsed_data},
        "mark": chart_type,
        "encoding": parsed_encoding,
    }

    try:
        artifact = Artifact(
            type="visualization",
            spec=spec,
            metadata=ArtifactMetadata(
                chart_type_suggestion=chart_type,
                title=title,
                data_source="agent",
                description=description or None,
            ),
        )
    except ValidationError as exc:
        logger.warning(
            "create_visualization: artifact validation failed (%d error(s)): %s",
            exc.error_count(),
            exc,
        )
        return "ERROR: visualization spec failed internal validation; check chart_type, title length, and data shape"

    artifact_dict = artifact.model_dump()

    if tool_context is not None:
        existing: list[dict[str, Any]] = tool_context.state.get(
            _RESPONSE_ARTIFACTS_KEY, []
        )
        existing.append(artifact_dict)
        tool_context.state[_RESPONSE_ARTIFACTS_KEY] = existing

    n = len(parsed_data)
    unit = "data point" if n == 1 else "data points"
    return f"Visualization created: {title} ({chart_type} chart, {n} {unit})"


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_function_tool("create_visualization", create_visualization)
