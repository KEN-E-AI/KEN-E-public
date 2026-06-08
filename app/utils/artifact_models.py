"""Re-export shim: canonical definitions live in shared.artifact_models.

Import from shared.artifact_models directly; this module exists only as
a compatibility alias so code paths that were originally pointed here
(e.g. early ADK tool drafts) continue to resolve without change.
"""

from shared.artifact_models import (
    Artifact,
    ArtifactMetadata,
    ArtifactType,
    ChartType,
)

__all__ = ["Artifact", "ArtifactMetadata", "ArtifactType", "ChartType"]
