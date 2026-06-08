"""Shared Pydantic v2 models for Vega-Lite chart artifacts.

AH-PRD-04 §4.1 / §5.1 — importable from both the ADK agent tool layer
(app/adk/) and the FastAPI API serializer (api/src/kene_api/).

Exports: Artifact, ArtifactMetadata, ChartType, ArtifactType.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

ChartType = Literal["bar", "line", "area", "point", "arc"]
ArtifactType = Literal["visualization", "text", "table", "file"]

__all__ = ["Artifact", "ArtifactMetadata", "ArtifactType", "ChartType"]

_MAX_SPEC_BYTES = (
    524_288  # 512 KB — prevents memory exhaustion from degenerate LLM specs
)


def _spec_has_data_url(node: Any) -> bool:
    """True if any ``data`` object anywhere in the spec carries a ``url`` key.

    Vega-Lite allows ``data`` at the unit/layer level and inside
    concat/hconcat/vconcat/facet compositions and ``transform.lookup.from`` —
    every such ``url`` triggers a cross-origin fetch from the Vega-Embed
    renderer, so the guard must walk the whole spec, not just its top level.
    The walk is bounded by the 512 KB size cap enforced before it runs.
    """
    if isinstance(node, dict):
        data = node.get("data")
        if isinstance(data, dict) and "url" in data:
            return True
        return any(_spec_has_data_url(value) for value in node.values())
    if isinstance(node, list):
        return any(_spec_has_data_url(item) for item in node)
    return False


def _spec_has_transform(node: Any) -> bool:
    """True if any ``transform`` key exists anywhere in the spec.

    Vega-Lite ``transform.calculate`` and ``transform.filter`` accept
    expression strings compiled by vega-runtime via ``new Function()``,
    allowing arbitrary JavaScript execution in the user's browser.  The
    ``ast: true`` option on the frontend's VegaEmbed call switches to the
    pure-interpreter path, but a defence-in-depth ban at the model boundary
    is the primary control.  Walk the full spec so nested layer/concat/facet
    compositions are covered; the walk is bounded by the 512 KB size cap.
    """
    if isinstance(node, dict):
        if "transform" in node:
            return True
        return any(_spec_has_transform(value) for value in node.values())
    if isinstance(node, list):
        return any(_spec_has_transform(item) for item in node)
    return False


class ArtifactMetadata(BaseModel):
    """Metadata envelope for a Vega-Lite chart artifact."""

    model_config = ConfigDict(extra="forbid")

    chart_type_suggestion: ChartType
    title: str = Field(min_length=1, max_length=200)
    data_source: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class Artifact(BaseModel):
    """Typed wrapper for a Vega-Lite v6 specification plus metadata.

    spec authoring rules (v6 $schema, inline data.values, no config block,
    no hardcoded mark colors) are enforced by create_visualization() (AH-131).
    This model additionally blocks the data.url and config keys because they
    are security-relevant: data.url causes Vega-Embed to issue a cross-origin
    fetch from the user's browser, and config overrides the app theme.

    The config ban enforces PRD §4.1 ("do not emit a config block") at the
    model boundary for chart artifacts; PRD §4.4 transform #1 still merges any
    spec.config defensively at the renderer for legacy/hand-authored specs.
    These Vega-Lite rules apply only to type=="visualization" — the other
    artifact types (text/table/file) carry non-Vega payloads where data.url
    and config may be legitimate, so they are validated elsewhere. The data.url
    ban walks the whole spec (nested layer/concat/facet/lookup), since Vega-Lite
    permits data at any of those levels; config is top-level only in Vega-Lite,
    so the config check is not recursive.

    An empty spec ({}) is accepted at the model layer — spec content invariants
    (non-empty data, v6 $schema, mark/encoding present) are AH-131's concern.
    """

    model_config = ConfigDict(extra="forbid")

    type: ArtifactType = "visualization"
    spec: dict[str, Any]
    metadata: ArtifactMetadata

    @field_validator("spec")
    @classmethod
    def _validate_spec(cls, v: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        # Vega-Lite security rules apply only to chart specs. text/table/file
        # artifacts carry non-Vega payloads where these keys may be legitimate.
        # `type` is declared before `spec`, so it is already in info.data here;
        # an invalid `type` literal leaves it absent and skips these rules while
        # still surfacing its own validation error.
        if info.data.get("type") != "visualization":
            return v
        if len(json.dumps(v).encode("utf-8")) > _MAX_SPEC_BYTES:
            raise ValueError(
                f"spec exceeds maximum size of {_MAX_SPEC_BYTES // 1024} KB"
            )
        if _spec_has_data_url(v):
            raise ValueError(
                "spec.data.url is forbidden; use spec.data.values (inline array) only"
            )
        if "config" in v:
            raise ValueError(
                "spec.config is forbidden; theme is applied by the frontend"
            )
        if _spec_has_transform(v):
            raise ValueError(
                "spec.transform is forbidden; data must be pre-aggregated inline "
                "via spec.data.values"
            )
        return v
