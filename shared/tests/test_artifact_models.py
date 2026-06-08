"""Unit tests for shared.artifact_models (canonical location).

Also exercises the app.utils.artifact_models re-export shim.

Covers AH-130 ACs:
  AC-1  Model shape (literal sets, required/optional fields, default type).
  AC-2  JSON round-trip of the design-doc v6 example spec.
  AC-3  Pydantic ValidationError on unknown type / chart_type_suggestion.

No network, Firestore, or GCP credentials required.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from shared.artifact_models import (
    Artifact,
    ArtifactMetadata,
    ArtifactType,
    ChartType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_METADATA_KWARGS: dict[str, Any] = {
    "chart_type_suggestion": "line",
    "title": "Website Sessions",
    "data_source": "google_analytics",
}

_EXAMPLE_V6_SPEC: dict = {
    "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
    "title": "Website Sessions — Last 7 Days",
    "data": {
        "values": [
            {"date": "2026-03-11", "sessions": 1247},
            {"date": "2026-03-12", "sessions": 1389},
            {"date": "2026-03-13", "sessions": 1156},
            {"date": "2026-03-14", "sessions": 1423},
            {"date": "2026-03-15", "sessions": 982},
            {"date": "2026-03-16", "sessions": 874},
            {"date": "2026-03-17", "sessions": 1302},
        ]
    },
    "mark": "line",
    "encoding": {
        "x": {"field": "date", "type": "temporal", "title": "Date"},
        "y": {"field": "sessions", "type": "quantitative", "title": "Sessions"},
    },
}


# ---------------------------------------------------------------------------
# AC-1: Model shape
# ---------------------------------------------------------------------------


def test_model_shape() -> None:
    """Assert literal sets, required/optional fields, and Artifact.type default."""
    assert set(ChartType.__args__) == {"bar", "line", "area", "point", "arc"}  # type: ignore[attr-defined]
    assert set(ArtifactType.__args__) == {"visualization", "text", "table", "file"}  # type: ignore[attr-defined]

    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    assert meta.chart_type_suggestion == "line"
    assert meta.title == "Website Sessions"
    assert meta.data_source == "google_analytics"
    assert meta.description is None

    artifact = Artifact(spec=_EXAMPLE_V6_SPEC, metadata=meta)
    assert artifact.type == "visualization"
    # Pydantic v2 deep-copies dict values during validation; use == not `is`
    assert artifact.spec == _EXAMPLE_V6_SPEC
    assert artifact.metadata == meta

    artifact_text = Artifact(type="text", spec={}, metadata=meta)
    assert artifact_text.type == "text"


# ---------------------------------------------------------------------------
# AC-2: JSON round-trip of the design-doc v6 example spec
# ---------------------------------------------------------------------------


def test_vega_lite_v6_spec_roundtrip() -> None:
    """Artifact round-trips through model_dump_json / model_validate_json unchanged."""
    meta = ArtifactMetadata(
        chart_type_suggestion="line",
        title="Website Sessions — Last 7 Days",
        data_source="google_analytics",
        description="Daily session count from GA4",
    )
    original = Artifact(spec=_EXAMPLE_V6_SPEC, metadata=meta)

    json_str = original.model_dump_json()
    restored = Artifact.model_validate_json(json_str)

    assert restored == original
    assert restored.spec["$schema"] == "https://vega.github.io/schema/vega-lite/v6.json"
    assert len(restored.spec["data"]["values"]) == 7
    assert restored.spec["data"]["values"][0] == {
        "date": "2026-03-11",
        "sessions": 1247,
    }


# ---------------------------------------------------------------------------
# AC-3: Validation error on unknown type / chart_type_suggestion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "type": "bogus",
            "spec": {},
            "metadata": ArtifactMetadata(**_VALID_METADATA_KWARGS),
        },
        {
            "type": "visualization",
            "spec": {},
            "metadata": {
                "chart_type_suggestion": "scatter",
                "title": "x",
                "data_source": "ga",
            },
        },
        {
            "type": "",
            "spec": {},
            "metadata": ArtifactMetadata(**_VALID_METADATA_KWARGS),
        },
    ],
)
def test_unknown_type_rejected(kwargs: dict[str, Any]) -> None:
    """Constructing Artifact with an invalid literal value raises ValidationError."""
    with pytest.raises(ValidationError):
        Artifact(**kwargs)


def test_unknown_chart_type_suggestion_rejected() -> None:
    """ArtifactMetadata rejects chart_type_suggestion outside the Literal set."""
    with pytest.raises(ValidationError):
        ArtifactMetadata(chart_type_suggestion="scatter", title="x", data_source="ga")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Extra fields forbidden (defense-in-depth)
# ---------------------------------------------------------------------------


def test_extra_field_forbidden_on_metadata() -> None:
    with pytest.raises(ValidationError):
        ArtifactMetadata(
            **_VALID_METADATA_KWARGS,
            unexpected_field="should_not_be_allowed",  # type: ignore[call-arg]
        )


def test_extra_field_forbidden_on_artifact() -> None:
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError):
        Artifact(
            spec=_EXAMPLE_V6_SPEC,
            metadata=meta,
            unexpected_field="should_not_be_allowed",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Field constraints
# ---------------------------------------------------------------------------


def test_title_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        ArtifactMetadata(chart_type_suggestion="line", title="", data_source="ga")


def test_data_source_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        ArtifactMetadata(chart_type_suggestion="line", title="Chart", data_source="")


# ---------------------------------------------------------------------------
# Spec validator: security-sensitive keys
# ---------------------------------------------------------------------------


def test_spec_data_url_rejected() -> None:
    """spec.data.url triggers a cross-origin fetch from the Vega-Embed renderer."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError, match=r"data\.url is forbidden"):
        Artifact(
            spec={
                "$schema": "...",
                "data": {"url": "https://attacker.example/collect"},
                "mark": "point",
                "encoding": {},
            },
            metadata=meta,
        )


def test_spec_config_block_rejected() -> None:
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError, match="config is forbidden"):
        Artifact(
            spec={
                "config": {"background": "red"},
                "mark": "bar",
                "data": {"values": []},
                "encoding": {},
            },
            metadata=meta,
        )


@pytest.mark.parametrize("artifact_type", ["text", "table", "file"])
def test_non_visualization_spec_skips_vega_rules(artifact_type: str) -> None:
    """Vega-Lite spec bans (data.url / config) apply only to visualization artifacts.

    text/table/file artifacts carry non-Vega payloads where these keys may be
    legitimate, so the spec validator must not reject them.
    """
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    artifact = Artifact(
        type=artifact_type,  # type: ignore[arg-type]
        spec={"config": {"x": 1}, "data": {"url": "https://example.com/data.json"}},
        metadata=meta,
    )
    assert artifact.type == artifact_type


@pytest.mark.parametrize(
    "spec",
    [
        {"layer": [{"data": {"url": "https://evil.example/x"}, "mark": "line"}]},
        {"hconcat": [{"data": {"url": "https://evil.example/x"}, "mark": "bar"}]},
        {
            "data": {"values": []},
            "transform": [
                {
                    "lookup": "k",
                    "from": {"data": {"url": "https://evil.example/x"}, "key": "k"},
                }
            ],
            "mark": "line",
        },
    ],
)
def test_spec_nested_data_url_rejected(spec: dict[str, Any]) -> None:
    """data.url is rejected at any nesting level, not just the top of the spec."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError, match=r"data\.url is forbidden"):
        Artifact(spec=spec, metadata=meta)


def test_spec_nested_inline_data_accepted() -> None:
    """A nested spec whose data is inline (no url) passes the guard."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    artifact = Artifact(
        spec={
            "layer": [{"data": {"values": [{"a": 1}]}, "mark": "line", "encoding": {}}]
        },
        metadata=meta,
    )
    assert artifact.spec["layer"][0]["data"]["values"] == [{"a": 1}]


def test_spec_transform_rejected() -> None:
    """transform is forbidden: vega-runtime executes calculate/filter via new Function()."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError, match="transform is forbidden"):
        Artifact(
            spec={
                "$schema": "...",
                "data": {"values": [{"x": 1}]},
                "transform": [{"calculate": "datum.x * 2", "as": "x2"}],
                "mark": "bar",
                "encoding": {},
            },
            metadata=meta,
        )


@pytest.mark.parametrize(
    "spec",
    [
        {"layer": [{"transform": [{"filter": "datum.x > 0"}], "mark": "line"}]},
        {
            "hconcat": [
                {"transform": [{"calculate": "datum.y", "as": "z"}], "mark": "bar"}
            ]
        },
    ],
)
def test_spec_nested_transform_rejected(spec: dict[str, Any]) -> None:
    """transform is rejected at any nesting level."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    with pytest.raises(ValidationError, match="transform is forbidden"):
        Artifact(spec=spec, metadata=meta)


def test_spec_transform_allowed_for_non_visualization() -> None:
    """The transform ban applies only to visualization artifacts."""
    meta = ArtifactMetadata(**_VALID_METADATA_KWARGS)
    artifact = Artifact(
        type="text",
        spec={"transform": [{"calculate": "datum.x", "as": "x"}]},
        metadata=meta,
    )
    assert artifact.type == "text"


# ---------------------------------------------------------------------------
# Re-export shim: app.utils.artifact_models forwards to shared
# ---------------------------------------------------------------------------


def test_app_utils_shim_reexport() -> None:
    """app.utils.artifact_models re-exports the same class objects as shared."""
    from app.utils.artifact_models import (
        Artifact as ShimArtifact,
    )
    from app.utils.artifact_models import (
        ArtifactMetadata as ShimArtifactMetadata,
    )
    from app.utils.artifact_models import (
        ArtifactType as ShimArtifactType,
    )
    from app.utils.artifact_models import (
        ChartType as ShimChartType,
    )

    assert ShimArtifact is Artifact
    assert ShimArtifactMetadata is ArtifactMetadata
    assert ShimArtifactType is ArtifactType
    assert ShimChartType is ChartType
