"""Unit tests for migrate_shape_d_split.py pure-logic helpers.

No Firestore dependency.  All helpers are exercised with plain dicts.

Covers:
- extract_account_payload: empty account_settings/funnels, None values, no mutation of input
- is_already_migrated: various hit/miss combinations
- approx_bytes: non-zero for non-empty dicts, zero-ish for empty
- CLI: --env mismatch exits 2, missing --env exits 2, missing GOOGLE_CLOUD_PROJECT_ID exits 2
- org-level fields are never touched (only accounts.* is consumed)
"""

from __future__ import annotations

import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_shape_d_split as m  # noqa: E402

# ---------------------------------------------------------------------------
# Fixed timestamp for deterministic tests
# ---------------------------------------------------------------------------
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
_ISO_NOW = _NOW.isoformat()


# ===========================================================================
# extract_account_payload
# ===========================================================================


class TestExtractAccountPayload:
    def test_full_payload(self) -> None:
        nested = {
            "account_settings": {"overview_kpis": {"income_kpi": "m_123"}},
            "funnels": {"organization": {"1": {"name": "Awareness"}}},
        }
        result = m.extract_account_payload(nested, "org_abc", _NOW)
        assert result == {
            "organization_id": "org_abc",
            "account_settings": {"overview_kpis": {"income_kpi": "m_123"}},
            "funnels": {"organization": {"1": {"name": "Awareness"}}},
            "shape_d_migrated_at": _ISO_NOW,
            "updated_at": _ISO_NOW,
        }

    def test_missing_account_settings_defaults_to_empty_dict(self) -> None:
        nested: dict[str, Any] = {"funnels": {"organization": {}}}
        result = m.extract_account_payload(nested, "org_abc", _NOW)
        assert result["account_settings"] == {}

    def test_missing_funnels_defaults_to_empty_dict(self) -> None:
        nested: dict[str, Any] = {"account_settings": {"kpi": "x"}}
        result = m.extract_account_payload(nested, "org_abc", _NOW)
        assert result["funnels"] == {}

    def test_none_account_settings_defaults_to_empty_dict(self) -> None:
        nested: dict[str, Any] = {"account_settings": None, "funnels": {}}
        result = m.extract_account_payload(nested, "org_abc", _NOW)
        assert result["account_settings"] == {}

    def test_none_funnels_defaults_to_empty_dict(self) -> None:
        nested: dict[str, Any] = {"account_settings": {}, "funnels": None}
        result = m.extract_account_payload(nested, "org_abc", _NOW)
        assert result["funnels"] == {}

    def test_empty_nested_dict(self) -> None:
        result = m.extract_account_payload({}, "org_abc", _NOW)
        assert result["account_settings"] == {}
        assert result["funnels"] == {}
        assert result["organization_id"] == "org_abc"

    def test_does_not_mutate_input(self) -> None:
        nested = {
            "account_settings": {"kpi": "m_123"},
            "funnels": {"organization": {"1": {}}},
        }
        original_settings_id = id(nested["account_settings"])
        m.extract_account_payload(nested, "org_abc", _NOW)
        # Input dict reference unchanged
        assert id(nested["account_settings"]) == original_settings_id
        assert nested == {
            "account_settings": {"kpi": "m_123"},
            "funnels": {"organization": {"1": {}}},
        }

    def test_organization_id_back_ref_set(self) -> None:
        result = m.extract_account_payload({}, "org_xyz", _NOW)
        assert result["organization_id"] == "org_xyz"

    def test_shape_d_migrated_at_matches_iso_now(self) -> None:
        result = m.extract_account_payload({}, "org_abc", _NOW)
        assert result["shape_d_migrated_at"] == _ISO_NOW
        assert result["updated_at"] == _ISO_NOW


# ===========================================================================
# is_already_migrated
# ===========================================================================


class TestIsAlreadyMigrated:
    def _source(self) -> dict[str, Any]:
        return {
            "account_settings": {"kpi": "m_123"},
            "funnels": {"organization": {"1": {"name": "Awareness"}}},
        }

    def test_returns_true_when_all_fields_match(self) -> None:
        src = self._source()
        dest = {
            "organization_id": "org_abc",
            "account_settings": {"kpi": "m_123"},
            "funnels": {"organization": {"1": {"name": "Awareness"}}},
            "shape_d_migrated_at": "2026-05-10T00:00:00+00:00",
        }
        assert m.is_already_migrated(dest, src, "org_abc") is True

    def test_returns_false_when_dest_is_none(self) -> None:
        assert m.is_already_migrated(None, self._source(), "org_abc") is False

    def test_returns_false_when_org_id_differs(self) -> None:
        src = self._source()
        dest = {
            "organization_id": "org_other",
            "account_settings": src["account_settings"],
            "funnels": src["funnels"],
        }
        assert m.is_already_migrated(dest, src, "org_abc") is False

    def test_returns_false_when_funnels_differ(self) -> None:
        src = self._source()
        dest = {
            "organization_id": "org_abc",
            "account_settings": {"kpi": "m_123"},
            "funnels": {"organization": {"1": {"name": "DIFFERENT"}}},
        }
        assert m.is_already_migrated(dest, src, "org_abc") is False

    def test_returns_false_when_account_settings_differ(self) -> None:
        src = self._source()
        dest = {
            "organization_id": "org_abc",
            "account_settings": {"kpi": "DIFFERENT"},
            "funnels": src["funnels"],
        }
        assert m.is_already_migrated(dest, src, "org_abc") is False

    def test_returns_true_when_both_empty(self) -> None:
        src: dict[str, Any] = {}
        dest = {"organization_id": "org_abc"}
        assert m.is_already_migrated(dest, src, "org_abc") is True

    def test_empty_dest_settings_matches_empty_source_settings(self) -> None:
        src: dict[str, Any] = {"account_settings": {}, "funnels": {}}
        dest = {"organization_id": "org_abc", "account_settings": {}, "funnels": {}}
        assert m.is_already_migrated(dest, src, "org_abc") is True

    def test_none_source_settings_normalised_to_empty(self) -> None:
        src: dict[str, Any] = {"account_settings": None, "funnels": None}
        dest = {"organization_id": "org_abc", "account_settings": {}, "funnels": {}}
        assert m.is_already_migrated(dest, src, "org_abc") is True

    def test_none_dest_settings_normalised_to_empty(self) -> None:
        src: dict[str, Any] = {"account_settings": {}, "funnels": {}}
        dest = {"organization_id": "org_abc", "account_settings": None, "funnels": None}
        assert m.is_already_migrated(dest, src, "org_abc") is True


# ===========================================================================
# approx_bytes
# ===========================================================================


class TestApproxBytes:
    def test_non_zero_for_non_empty(self) -> None:
        assert m.approx_bytes({"key": "value"}) > 0

    def test_empty_dict_is_small(self) -> None:
        assert m.approx_bytes({}) <= 4  # JSON: {} = 2 bytes

    def test_larger_dict_has_more_bytes(self) -> None:
        small = {"a": "b"}
        large = {"a": "b" * 1000}
        assert m.approx_bytes(large) > m.approx_bytes(small)


# ===========================================================================
# CLI argument validation
# ===========================================================================


class TestCLIValidation:
    def _run_main(self, argv: list[str], env_vars: dict[str, str] | None = None) -> int:
        """Run main() with overridden sys.argv and environment variables."""
        env: dict[str, str] = {}
        if env_vars is not None:
            env.update(env_vars)
        with (
            patch.object(sys, "argv", ["migrate_shape_d_split", *argv]),
            patch.dict("os.environ", env, clear=False),
            redirect_stdout(StringIO()),
            redirect_stderr(StringIO()),
        ):
            try:
                return m.main()
            except SystemExit as exc:
                return int(exc.code) if exc.code is not None else 0

    def test_missing_env_flag_exits_2(self) -> None:
        code = self._run_main([], env_vars={"GOOGLE_CLOUD_PROJECT_ID": "ken-e-dev"})
        assert code == 2

    def test_missing_google_cloud_project_id_exits_2(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            code = self._run_main(
                ["--env=dev"],
                env_vars={},
            )
        assert code == 2

    def test_env_mismatch_exits_2(self) -> None:
        # --env=production but project id is ken-e-dev → mismatch
        code = self._run_main(
            ["--env=production"],
            env_vars={"GOOGLE_CLOUD_PROJECT_ID": "ken-e-dev"},
        )
        assert code == 2

    def test_dev_env_matches_ken_e_dev(self) -> None:
        # With a properly-matched env, env validation passes (no SystemExit(2)).
        # We test _validate_env_flag directly — the equivalent unit-level assertion.
        # (CLI-level smoke tested in TestValidateEnvFlag; this is belt-and-braces.)
        try:
            m._validate_env_flag("dev", "ken-e-dev")
        except SystemExit as exc:
            pytest.fail(f"_validate_env_flag raised SystemExit({exc.code}) for valid dev env")


# ===========================================================================
# _validate_env_flag (unit tested directly)
# ===========================================================================


class TestValidateEnvFlag:
    def test_matching_dev(self) -> None:
        # Should not raise
        m._validate_env_flag("dev", "ken-e-dev")

    def test_matching_staging(self) -> None:
        m._validate_env_flag("staging", "ken-e-staging")

    def test_matching_production(self) -> None:
        m._validate_env_flag("production", "ken-e-production")

    def test_mismatch_dev_vs_staging(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            m._validate_env_flag("staging", "ken-e-dev")
        assert exc_info.value.code == m.EXIT_USAGE_ERROR

    def test_mismatch_production_vs_dev(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            m._validate_env_flag("production", "ken-e-dev")
        assert exc_info.value.code == m.EXIT_USAGE_ERROR


# ===========================================================================
# Org-level fields invariant
# ===========================================================================


class TestOrgLevelFieldsUntouched:
    """Verify that run_migration never reads org-level fields into any write payload."""

    def _make_fake_client(
        self,
        org_data: dict[str, Any],
        existing_accounts: dict[str, dict[str, Any]] | None = None,
    ) -> Any:
        """Build a minimal fake Firestore client with org + optional account docs."""

        class _Snap:
            def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
                self.id = doc_id
                self._data = data
                self.exists = True

            def to_dict(self) -> dict[str, Any]:
                return dict(self._data)

        class _DocRef:
            def __init__(self, path: str, store: dict[str, Any]) -> None:
                self._path = path
                self._store = store
                self._written: list[tuple[dict[str, Any], bool]] = []

            @property
            def id(self) -> str:
                return self._path.rsplit("/", 1)[-1]

            def get(self) -> _Snap:
                data = self._store.get(self._path)
                if data is None:
                    s = _Snap(self.id, {})
                    s.exists = False
                    return s
                return _Snap(self.id, data)

            def set(self, data: dict[str, Any], merge: bool = False) -> None:
                assert merge is True, "set() called with merge=False — merge=True required for safe idempotent writes"
                self._written.append((data, merge))
                self._store[self._path] = data

        class _ColRef:
            def __init__(self, name: str, store: dict[str, Any], rows: list[Any]) -> None:
                self._name = name
                self._store = store
                self._rows = rows

            def stream(self) -> list[Any]:
                return self._rows

            def document(self, doc_id: str) -> _DocRef:
                return _DocRef(f"{self._name}/{doc_id}", self._store)

        written_payloads: list[dict[str, Any]] = []
        store: dict[str, Any] = {}
        if existing_accounts:
            for acc_id, data in existing_accounts.items():
                store[f"accounts/{acc_id}"] = data

        class _Client:
            def __init__(self) -> None:
                self._written = written_payloads
                self._store = store

            def collection(self, name: str) -> Any:
                if name == "organizations":
                    org_snap = _Snap("org_test", org_data)
                    col = _ColRef("organizations", store, [org_snap])
                    return col
                # accounts collection
                col = _ColRef(name, store, [])
                return col

        return _Client()

    def test_org_level_fields_never_in_payload(self) -> None:
        """account_settings and funnels come from accounts.*; name/agency are never touched."""
        org_data = {
            "name": "Acme Corp",
            "agency": "Acme Agency",
            "created_at": "2026-01-01T00:00:00+00:00",
            "accounts": {
                "acc_alpha": {
                    "account_settings": {"kpi": "m_1"},
                    "funnels": {"org": {"1": {}}},
                }
            },
        }
        client = self._make_fake_client(org_data)
        summary = m.run_migration(client, dry_run=False)

        # One account copied
        assert summary.copied == 1
        assert summary.errors == 0

        # The written payload must not contain org-level fields
        written_doc = client._store.get("accounts/acc_alpha")
        assert written_doc is not None
        assert "name" not in written_doc
        assert "agency" not in written_doc
        assert "created_at" not in written_doc
        assert written_doc["organization_id"] == "org_test"
        assert written_doc["account_settings"] == {"kpi": "m_1"}
        assert written_doc["funnels"] == {"org": {"1": {}}}

    def test_dry_run_writes_nothing(self) -> None:
        org_data = {
            "name": "Dry Org",
            "accounts": {"acc_dry": {"account_settings": {}, "funnels": {}}},
        }
        client = self._make_fake_client(org_data)
        m.run_migration(client, dry_run=True)
        # Dry-run: accounts collection should have no writes from the migration
        assert "accounts/acc_dry" not in client._store

    def test_idempotency_skips_already_migrated(self) -> None:
        settings = {"kpi": "m_1"}
        funnels = {"org": {"1": {}}}
        org_data = {
            "accounts": {
                "acc_idem": {
                    "account_settings": settings,
                    "funnels": funnels,
                }
            }
        }
        existing = {
            "acc_idem": {
                "organization_id": "org_test",
                "account_settings": settings,
                "funnels": funnels,
                "shape_d_migrated_at": "2026-01-01T00:00:00+00:00",
            }
        }
        client = self._make_fake_client(org_data, existing_accounts=existing)
        summary = m.run_migration(client, dry_run=False)
        assert summary.skipped == 1
        assert summary.copied == 0

    def test_empty_settings_but_populated_funnels_is_copied(self) -> None:
        """is_empty must be False when account_settings={} but funnels has data."""
        org_data = {
            "accounts": {
                "acc_funnel_only": {
                    "account_settings": {},
                    "funnels": {"organization": {"1": {"name": "Awareness"}}},
                }
            }
        }
        client = self._make_fake_client(org_data)
        summary = m.run_migration(client, dry_run=False)
        assert summary.copied == 1
        assert summary.empty == 0
        written_doc = client._store.get("accounts/acc_funnel_only")
        assert written_doc is not None
        assert written_doc["funnels"] == {"organization": {"1": {"name": "Awareness"}}}
        assert written_doc["account_settings"] == {}

    def test_invalid_account_id_with_slash_is_skipped(self) -> None:
        """account_id containing '/' is rejected before reaching Firestore."""
        org_data = {
            "accounts": {
                "valid_acc": {"account_settings": {"kpi": "m_1"}, "funnels": {}},
                "invalid/acc": {"account_settings": {"kpi": "m_2"}, "funnels": {}},
            }
        }
        client = self._make_fake_client(org_data)
        summary = m.run_migration(client, dry_run=False)
        assert summary.copied == 1
        assert "accounts/valid_acc" in client._store
        assert "accounts/invalid/acc" not in client._store


# ===========================================================================
# TestDeleteFieldPass
# ===========================================================================


class TestDeleteFieldPass:
    """Unit tests for run_delete_field_pass() — the --confirm-delete-field step.

    Uses a fake Firestore client that records update() calls so we can assert
    DELETE_FIELD is (or is not) issued without touching a real database.
    """

    # Sentinel to stand in for google.cloud.firestore_v1.DELETE_FIELD in tests.
    # run_delete_field_pass imports DELETE_FIELD inside the function body, so we
    # patch it in the google.cloud.firestore_v1 module namespace.
    _DELETE_FIELD_SENTINEL = object()

    def _make_fake_client(
        self,
        orgs: dict[str, dict[str, Any]],
        existing_accounts: dict[str, dict[str, Any]] | None = None,
    ) -> Any:
        """Build a fake Firestore client for delete-pass tests.

        Parameters
        ----------
        orgs:
            ``{org_id: org_doc_data}`` — each entry becomes an organizations/ snapshot.
            The org_doc_data should include an ``accounts`` map if the org has accounts.
        existing_accounts:
            ``{account_id: account_doc_data}`` — pre-populated accounts/ docs.
        """

        class _Snap:
            def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
                self.id = doc_id
                self._data = data
                self.exists = bool(data) or data == {}

            def to_dict(self) -> dict[str, Any]:
                return dict(self._data)

        class _DocRef:
            def __init__(self, path: str, store: dict[str, Any], updates: list[Any]) -> None:
                self._path = path
                self._store = store
                self._updates = updates  # shared list of (path, field_mask) tuples

            @property
            def id(self) -> str:
                return self._path.rsplit("/", 1)[-1]

            def get(self) -> _Snap:
                data = self._store.get(self._path)
                if data is None:
                    s = _Snap(self.id, {})
                    s.exists = False
                    return s
                return _Snap(self.id, data)

            def update(self, field_mask: dict[str, Any]) -> None:
                self._updates.append((self._path, field_mask))
                # Simulate the DELETE_FIELD by removing the key from the store
                for key in list(field_mask.keys()):
                    doc = self._store.get(self._path, {})
                    doc.pop(key, None)
                    self._store[self._path] = doc

        class _ColRef:
            def __init__(
                self,
                name: str,
                store: dict[str, Any],
                rows: list[Any],
                updates: list[Any],
            ) -> None:
                self._name = name
                self._store = store
                self._rows = rows
                self._updates = updates

            def stream(self) -> list[Any]:
                return self._rows

            def document(self, doc_id: str) -> _DocRef:
                return _DocRef(f"{self._name}/{doc_id}", self._store, self._updates)

        store: dict[str, Any] = {}
        updates: list[Any] = []  # records (path, field_mask) for each update() call

        # Seed account docs
        if existing_accounts:
            for acc_id, data in existing_accounts.items():
                store[f"accounts/{acc_id}"] = data

        # Seed org docs
        for org_id, org_data in orgs.items():
            store[f"organizations/{org_id}"] = org_data

        org_snaps = [_Snap(org_id, data) for org_id, data in orgs.items()]

        class _Client:
            def __init__(self) -> None:
                self._store = store
                self._updates = updates

            def collection(self, name: str) -> Any:
                if name == "organizations":
                    return _ColRef(name, store, org_snaps, updates)
                return _ColRef(name, store, [], updates)

        return _Client()

    def _fully_migrated_account(self, org_id: str) -> dict[str, Any]:
        return {
            "organization_id": org_id,
            "account_settings": {"kpi": "m_1"},
            "funnels": {"organization": {"1": {"name": "Awareness"}}},
            "shape_d_migrated_at": "2026-05-11T12:00:00+00:00",
        }

    def test_gate_pass_records_deleted_and_issues_update(self) -> None:
        """Fully-migrated org → action=deleted, update() called with DELETE_FIELD."""
        settings = {"kpi": "m_1"}
        funnels = {"organization": {"1": {"name": "Awareness"}}}
        org_data = {
            "name": "Acme",
            "accounts": {
                "acc_a": {"account_settings": settings, "funnels": funnels},
                "acc_b": {"account_settings": {}, "funnels": {"org": {}}},
            },
        }
        existing = {
            "acc_a": {"organization_id": "org_1", "account_settings": settings, "funnels": funnels},
            "acc_b": {"organization_id": "org_1", "account_settings": {}, "funnels": {"org": {}}},
        }
        client = self._make_fake_client({"org_1": org_data}, existing_accounts=existing)

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=False)

        assert summary.orgs_field_deleted == 1
        assert summary.orgs_already_clean == 0
        assert summary.orgs_skipped_unmigrated == 0

        # Exactly one update() call on the org doc with "accounts" key
        assert len(client._updates) == 1
        path, field_mask = client._updates[0]
        assert path == "organizations/org_1"
        assert "accounts" in field_mask
        assert field_mask["accounts"] is self._DELETE_FIELD_SENTINEL

    def test_gate_block_missing_account_doc(self) -> None:
        """Org with a missing accounts/ doc → skipped_unmigrated, update() NOT called."""
        settings = {"kpi": "m_1"}
        funnels = {}
        org_data = {
            "accounts": {
                "acc_present": {"account_settings": settings, "funnels": funnels},
                "acc_missing": {"account_settings": {"kpi": "m_2"}, "funnels": {}},
            },
        }
        # Only acc_present is migrated; acc_missing has no destination doc
        existing = {
            "acc_present": {
                "organization_id": "org_1",
                "account_settings": settings,
                "funnels": funnels,
            },
        }
        client = self._make_fake_client({"org_1": org_data}, existing_accounts=existing)

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=False)

        assert summary.orgs_skipped_unmigrated == 1
        assert summary.orgs_field_deleted == 0
        assert len(client._updates) == 0

    def test_gate_block_content_mismatch(self) -> None:
        """Dest doc exists but funnels differ from source → skipped_unmigrated."""
        settings = {"kpi": "m_1"}
        funnels_source = {"organization": {"1": {"name": "Awareness"}}}
        funnels_dest = {"organization": {"1": {"name": "DIFFERENT"}}}
        org_data = {
            "accounts": {
                "acc_mismatch": {"account_settings": settings, "funnels": funnels_source},
            },
        }
        existing = {
            "acc_mismatch": {
                "organization_id": "org_1",
                "account_settings": settings,
                "funnels": funnels_dest,  # different!
            },
        }
        client = self._make_fake_client({"org_1": org_data}, existing_accounts=existing)

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=False)

        assert summary.orgs_skipped_unmigrated == 1
        assert summary.orgs_field_deleted == 0
        assert len(client._updates) == 0

    def test_idempotency_already_clean(self) -> None:
        """Org doc with no accounts field → already_clean, update() NOT called."""
        org_data = {"name": "Clean Org"}  # no "accounts" key
        client = self._make_fake_client({"org_clean": org_data})

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=False)

        assert summary.orgs_already_clean == 1
        assert summary.orgs_field_deleted == 0
        assert len(client._updates) == 0

    def test_dry_run_does_not_issue_update(self) -> None:
        """--dry-run: verified org records would_delete but update() is NOT called."""
        settings = {"kpi": "m_1"}
        funnels = {}
        org_data = {
            "accounts": {"acc_a": {"account_settings": settings, "funnels": funnels}},
        }
        existing = {
            "acc_a": {
                "organization_id": "org_dry",
                "account_settings": settings,
                "funnels": funnels,
            },
        }
        client = self._make_fake_client({"org_dry": org_data}, existing_accounts=existing)

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=True)

        # would_delete counted as orgs_field_deleted in the summary for simplicity
        assert summary.orgs_field_deleted == 1
        assert len(client._updates) == 0  # no real writes

    def test_mixed_batch_three_orgs(self) -> None:
        """Three orgs: one deleted, one skipped_unmigrated, one already_clean."""
        settings = {"kpi": "m_1"}
        funnels = {}

        org_full = {
            "accounts": {"acc_full": {"account_settings": settings, "funnels": funnels}},
        }
        org_partial = {
            "accounts": {
                "acc_present": {"account_settings": settings, "funnels": funnels},
                "acc_absent": {"account_settings": {"kpi": "m_2"}, "funnels": {}},
            },
        }
        org_empty = {"name": "Empty Org"}  # no accounts field

        existing = {
            "acc_full": {"organization_id": "org_full", "account_settings": settings, "funnels": funnels},
            "acc_present": {"organization_id": "org_partial", "account_settings": settings, "funnels": funnels},
            # acc_absent intentionally missing
        }
        client = self._make_fake_client(
            {"org_full": org_full, "org_partial": org_partial, "org_empty": org_empty},
            existing_accounts=existing,
        )

        with patch("google.cloud.firestore_v1.DELETE_FIELD", self._DELETE_FIELD_SENTINEL):
            summary = m.run_delete_field_pass(client, dry_run=False)

        assert summary.orgs_field_deleted == 1
        assert summary.orgs_skipped_unmigrated == 1
        assert summary.orgs_already_clean == 1
        assert summary.total_orgs == 3

        # Only the full org should have had update() called
        assert len(client._updates) == 1
        path, _ = client._updates[0]
        assert path == "organizations/org_full"
