"""kene_api.models re-exports the shared Artifact models (AH-130 / AH-PRD-04 §5.1).

Gates the production import path ``from kene_api.models import Artifact`` that
AH-132 (``ChatResponse.artifacts``) depends on. Lives under ``api/tests`` so it
runs in the ``api-unit-tests`` CI step where ``kene_api`` is importable; the
``shared/`` package tests deliberately do not import ``kene_api``.

No network, Firestore, or GCP credentials required.
"""

from __future__ import annotations

from kene_api.models import Artifact, ArtifactMetadata, ArtifactType, ChartType

from shared.artifact_models import Artifact as SharedArtifact
from shared.artifact_models import ArtifactMetadata as SharedArtifactMetadata
from shared.artifact_models import ArtifactType as SharedArtifactType
from shared.artifact_models import ChartType as SharedChartType


def test_kene_api_reexports_shared_artifact_models() -> None:
    """kene_api.models exposes the *same* objects as shared.artifact_models."""
    assert Artifact is SharedArtifact
    assert ArtifactMetadata is SharedArtifactMetadata
    assert ArtifactType is SharedArtifactType
    assert ChartType is SharedChartType
