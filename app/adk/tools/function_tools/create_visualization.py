"""SDK function tool for creating Vega-Lite v6 chart artifacts.

AH-PRD-04 §4 / AH-131 — implements the ``create_visualization`` callable
described in data-visualization.md §4.1-4.2 and AC-1/2/3 of AH-131.

The tool appends a JSON-serializable artifact dict to
``tool_context.state["response_artifacts"]`` so multiple calls in one turn
accumulate (never overwrite). The upstream chat endpoint pops and clears that
key after the agent run (AH-132); the artifact Pydantic model is defined in
``shared.artifact_models`` (AH-130).

AH-143 adds ``register_artifact`` persistence so each chart is also written to
GCS + a ``ChatArtifactIndex`` Firestore row. Persistence is best-effort: any
failure is caught and logged, and the function still returns the success
confirmation string (the in-memory append to ``response_artifacts`` already
succeeded and the chat response must not lose the chart over a transient).

Module-bottom ``register_function_tool`` fires at import time so the registry
is populated before ``specialist_runtime.resolve_default_global_tools`` runs
in the agent factory. The side-effect import lives in
``app/adk/agents/agent_factory/hierarchy.py`` alongside the other
default-global tools (todo_list_tools, google_search, numerical_analyst).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
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
_VEGALITE_MIME: str = "application/vnd.vegalite.v6+json"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, max_len: int = 48) -> str:
    """Convert a title to a safe filename slug (lowercase, underscores, trimmed)."""
    slug = _SLUG_RE.sub("_", text.lower()).strip("_")
    return slug[:max_len] if slug else "chart"


def _iso8601_compact() -> str:
    """Return a compact UTC timestamp suitable for filenames: ``20240101T120000``."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


async def create_visualization(
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
    frontend-side), wraps the result in an ``Artifact``, appends the artifact's
    dict representation to ``tool_context.state["response_artifacts"]``, and
    persists the spec via ``register_artifact`` (GCS + Firestore index).

    Persistence is best-effort: ``RuntimeError`` (missing account_id) and
    transient ``ServiceUnavailable`` / ``DeadlineExceeded`` errors are caught,
    logged, and swallowed so the chart still reaches ``ChatResponse.artifacts``
    even when persistence is temporarily unavailable.

    Args:
        chart_type: Vega-Lite mark type. Use ``"point"`` for scatter plots.
        title: Human-readable chart title (shown above the chart).
        data: JSON string of data values — must be an array of objects.
        encoding: JSON string of a Vega-Lite encoding specification.
        description: Optional human-readable description of what the chart shows.
        tool_context: ADK ToolContext. When ``None`` (e.g. in unit tests not
            backed by an ADK runtime) the function still builds and validates the
            artifact and returns the confirmation string, but skips both the
            session-state append and the ``register_artifact`` persistence call.

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

    n = len(parsed_data)
    unit = "data point" if n == 1 else "data points"
    confirmation = f"Visualization created: {title} ({chart_type} chart, {n} {unit})"

    if tool_context is not None:
        existing: list[dict[str, Any]] = tool_context.state.get(
            _RESPONSE_ARTIFACTS_KEY, []
        )
        # Idempotent within a turn: if this exact chart was already emitted this
        # turn, skip both the response_artifacts append AND the register_artifact
        # persistence below. A review LoopAgent (wrap_task_in_review, AH-142)
        # re-runs the worker across iterations; without this guard an unchanged
        # chart re-emitted on a later iteration would be shown twice and persisted
        # twice (AH-143 x AH-142). artifact_dict carries no timestamp/id, so
        # value-equality is a reliable within-turn content identity. A genuinely
        # *revised* chart differs in content and is NOT deduped here — both surface
        # and persist (accepted residual; full fix tracked in CH-69).
        if artifact_dict in existing:
            return confirmation
        existing.append(artifact_dict)
        tool_context.state[_RESPONSE_ARTIFACTS_KEY] = existing

        # Persist to GCS + Firestore via the canonical register_artifact wrapper
        # (app/CLAUDE.md universal contract: every tool that saves an artifact
        # MUST call register_artifact). Deferred import: kene_api is not
        # available in the app-adk-tests CI venv but IS present in the Agent
        # Engine runtime where the tool actually runs.
        #
        # Import block is separated from the call block so ImportError (missing
        # kene_api package) is distinct from runtime errors on the actual call.
        _register_artifact = None
        _deadline_exc: tuple[type[Exception], ...] = ()
        try:
            from google.api_core.exceptions import (  # type: ignore[import]
                DeadlineExceeded,
                ServiceUnavailable,
            )
            from google.genai.types import Blob, Part
            from kene_api.chat.artifacts import (  # type: ignore[import]
                register_artifact as _register_artifact,
            )

            _deadline_exc = (ServiceUnavailable, DeadlineExceeded)
        except ImportError:
            # kene_api not available (unit-test or deploy-time venv); skip.
            pass

        if _register_artifact is not None:
            filename = f"viz_{_slugify(title)}_{_iso8601_compact()}.json"
            content = Part(
                inline_data=Blob(
                    data=json.dumps(spec).encode("utf-8"),
                    mime_type=_VEGALITE_MIME,
                )
            )
            try:
                await _register_artifact(
                    tool_context, filename, content, created_by_tool="create_visualization"
                )
            except RuntimeError as exc:
                logger.warning(
                    "create_visualization: register_artifact skipped (missing context): %s",
                    exc,
                )
            except ValueError as exc:
                logger.error(
                    "create_visualization: register_artifact contract violation: %s",
                    exc,
                )
            except _deadline_exc as exc:  # type: ignore[misc]
                logger.warning(
                    "create_visualization: register_artifact failed after retries: %s",
                    exc,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "create_visualization: register_artifact raised unexpectedly: %s",
                    exc,
                )

    return confirmation


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_function_tool("create_visualization", create_visualization)
