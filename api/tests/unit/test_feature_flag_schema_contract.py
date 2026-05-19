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

import pytest
from src.kene_api.models.feature_flag_models import FeatureFlag, FeatureFlagAuditEntry

_FIXTURES_DIR = (Path(__file__).parent.parent / "fixtures").resolve()
_SNAPSHOT_PATH = (_FIXTURES_DIR / "feature_flag_schema.snapshot.json").resolve()
_AUDIT_ENTRY_SNAPSHOT_PATH = (
    _FIXTURES_DIR / "feature_flag_audit_entry_schema.snapshot.json"
).resolve()


def _canonical(schema: dict[str, object]) -> str:
    # Trailing "\n" matches POSIX text-file convention and the print() newline
    # in the regeneration recipe above — both sides of the comparison must agree.
    return json.dumps(schema, sort_keys=True, indent=2) + "\n"


def _read_snapshot() -> str:
    assert _SNAPSHOT_PATH.is_relative_to(_FIXTURES_DIR), (
        f"Snapshot path escaped fixtures dir: {_SNAPSHOT_PATH}"
    )
    if not _SNAPSHOT_PATH.exists():
        pytest.fail(
            f"Snapshot fixture missing at {_SNAPSHOT_PATH}. "
            "Regenerate using the recipe in this module's docstring."
        )
    return _SNAPSHOT_PATH.read_text(encoding="utf-8")


class TestFeatureFlagSchemaContract:
    """AC-14: snapshot equality gate and drift-guard."""

    def test_feature_flag_schema_matches_snapshot(self) -> None:
        """FeatureFlag.model_json_schema() must match the committed snapshot byte-for-byte.

        If this test fails, the FeatureFlag Pydantic model has drifted from the
        committed snapshot.  Regenerate the snapshot using the recipe in this
        module's docstring, and update frontend/src/lib/featureFlags/types.ts
        in the same PR.
        """
        snapshot_text = _read_snapshot()
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

        snapshot_text = _read_snapshot()
        drift_schema = _canonical(_DriftFeatureFlag.model_json_schema())

        assert drift_schema != snapshot_text, (
            "Drift subclass schema should differ from the snapshot but did not. "
            "The contract gate may be broken."
        )


class TestFeatureFlagAuditEntrySchemaContract:
    """Snapshot contract for FeatureFlagAuditEntry (FF-PRD-02 §5.4).

    Guards against unintentional drift between the Python FeatureFlagAuditEntry
    model and the TypeScript mirror in frontend/src/lib/featureFlags/types.ts
    (owned by FF-PRD-02).  When FeatureFlagAuditEntry is intentionally changed,
    regenerate the snapshot in the same PR as the matching types.ts edit:

        cd api
        uv run python -c "
        from src.kene_api.models.feature_flag_models import FeatureFlagAuditEntry
        import json
        print(json.dumps(FeatureFlagAuditEntry.model_json_schema(), sort_keys=True, indent=2))
        " > tests/fixtures/feature_flag_audit_entry_schema.snapshot.json
    """

    def _read_audit_snapshot(self) -> str:
        assert _AUDIT_ENTRY_SNAPSHOT_PATH.is_relative_to(_FIXTURES_DIR), (
            f"Snapshot path escaped fixtures dir: {_AUDIT_ENTRY_SNAPSHOT_PATH}"
        )
        if not _AUDIT_ENTRY_SNAPSHOT_PATH.exists():
            pytest.fail(
                f"Snapshot fixture missing at {_AUDIT_ENTRY_SNAPSHOT_PATH}. "
                "Regenerate using the recipe in this class's docstring."
            )
        return _AUDIT_ENTRY_SNAPSHOT_PATH.read_text(encoding="utf-8")

    def test_audit_entry_schema_matches_snapshot(self) -> None:
        """FeatureFlagAuditEntry.model_json_schema() must match the committed snapshot."""
        snapshot_text = self._read_audit_snapshot()
        current = _canonical(FeatureFlagAuditEntry.model_json_schema())

        assert current == snapshot_text, (
            f"FeatureFlagAuditEntry schema has drifted from {_AUDIT_ENTRY_SNAPSHOT_PATH}. "
            "Regenerate the snapshot (see class docstring) and update "
            "frontend/src/lib/featureFlags/types.ts in the same PR."
        )

    def test_subclass_with_extra_field_does_not_match_snapshot(self) -> None:
        """A model with an extra field must NOT match the snapshot (gate is not trivial)."""

        class _DriftAuditEntry(FeatureFlagAuditEntry):
            extra_drift_field: str

        snapshot_text = self._read_audit_snapshot()
        drift_schema = _canonical(_DriftAuditEntry.model_json_schema())

        assert drift_schema != snapshot_text, (
            "Drift subclass schema should differ from the snapshot but did not. "
            "The contract gate may be broken."
        )
