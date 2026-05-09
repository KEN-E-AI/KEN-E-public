"""JSON-schema snapshot contract test for the FeatureFlag Pydantic model.

Guards against unintentional drift between the Python ``FeatureFlag`` model
(``api/src/kene_api/models/feature_flag_models.py``) and the TypeScript mirror
in ``frontend/src/lib/featureFlags/types.ts`` (owned by FF-PRD-02).

When the ``FeatureFlag`` model is intentionally changed, regenerate the snapshot
in the same PR as the matching ``types.ts`` edit:

    cd api
    uv run python -c "
    from src.kene_api.models.feature_flag_models import FeatureFlag
    import json
    print(json.dumps(FeatureFlag.model_json_schema(), sort_keys=True, indent=2))
    " > tests/fixtures/feature_flag_schema.snapshot.json

Spec: docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md §5.4, §7.14
"""

from __future__ import annotations

import json
from pathlib import Path

from src.kene_api.models.feature_flag_models import FeatureFlag

_SNAPSHOT_PATH = (
    Path(__file__).parent.parent / "fixtures" / "feature_flag_schema.snapshot.json"
)


def _canonical(schema: dict[str, object]) -> str:
    return json.dumps(schema, sort_keys=True, indent=2) + "\n"


class TestFeatureFlagSchemaContract:
    """AC-14: snapshot equality gate and drift-guard."""

    def test_feature_flag_schema_matches_snapshot(self) -> None:
        """FeatureFlag.model_json_schema() must match the committed snapshot byte-for-byte.

        If this test fails, the FeatureFlag Pydantic model has drifted from the
        committed snapshot.  Regenerate the snapshot using the recipe in this
        module's docstring, and update frontend/src/lib/featureFlags/types.ts
        in the same PR.
        """
        snapshot_text = _SNAPSHOT_PATH.read_text(encoding="utf-8")
        current = _canonical(FeatureFlag.model_json_schema())

        assert current == snapshot_text, (
            f"FeatureFlag schema has drifted from {_SNAPSHOT_PATH}. "
            "Regenerate the snapshot (see module docstring) and update "
            "frontend/src/lib/featureFlags/types.ts in the same PR."
        )

    def test_subclass_with_extra_field_does_not_match_snapshot(self) -> None:
        """A model with an extra field must NOT match the snapshot.

        This proves the equality gate in test_feature_flag_schema_matches_snapshot
        would actually catch real drift — the test does not pass trivially.
        """

        class _DriftFeatureFlag(FeatureFlag):
            extra_drift_field: str

        snapshot_text = _SNAPSHOT_PATH.read_text(encoding="utf-8")
        drift_schema = _canonical(_DriftFeatureFlag.model_json_schema())

        assert drift_schema != snapshot_text, (
            "Drift subclass schema should differ from the snapshot but did not. "
            "The contract gate may be broken."
        )
