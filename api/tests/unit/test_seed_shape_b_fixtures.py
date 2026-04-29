"""Unit tests for api/scripts/seed_shape_b_fixtures.py.

These tests cover pure-logic surface (seed constants, path helpers, project guard,
argparse defaults) without requiring a live Firestore connection.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to path so we can import the script as a module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from seed_shape_b_fixtures import (
    PARENT_ACCOUNT_SEED,
    SKILLS_SEED,
    SKILLS_VERSIONS_SEEDS,
    STRATEGY_AUDIT_SEEDS,
    STRATEGY_DOCS_SEED,
    STRATEGY_DOCS_VERSIONS_SEEDS,
    build_seed_paths,
    is_dev_project,
    main,
    parse_args,
)

# ---------------------------------------------------------------------------
# Seed constant structural tests
# ---------------------------------------------------------------------------


class TestSeedConstants:
    def test_strategy_docs_versions_has_two_entries(self):
        assert len(STRATEGY_DOCS_VERSIONS_SEEDS) >= 2

    def test_strategy_audit_has_two_entries(self):
        assert len(STRATEGY_AUDIT_SEEDS) >= 2

    def test_skills_versions_has_two_entries(self):
        assert len(SKILLS_VERSIONS_SEEDS) >= 2

    def test_strategy_doc_seed_parses_as_strategy_document(self):
        """Seed dict round-trips through StrategyDocument without validation error."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        from kene_api.models.strategy_models import StrategyDocument

        payload = {**STRATEGY_DOCS_SEED, "account_id": "test_acc_fixture"}
        doc = StrategyDocument(**payload)
        assert doc.doc_type == "business_strategy"
        assert doc.account_id == "test_acc_fixture"

    def test_strategy_doc_version_seeds_parse_as_strategy_document(self):
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        from kene_api.models.strategy_models import StrategyDocument

        for seed in STRATEGY_DOCS_VERSIONS_SEEDS:
            payload = {**seed, "account_id": "test_acc_fixture"}
            doc = StrategyDocument(**payload)
            assert doc.doc_type == "business_strategy"

    def test_strategy_audit_seeds_parse_as_strategy_audit_entry(self):
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        from kene_api.models.strategy_models import StrategyAuditEntry

        for seed in STRATEGY_AUDIT_SEEDS:
            entry = StrategyAuditEntry(**seed)
            assert entry.user_id == "user_seed_fixture"

    def test_timestamps_are_deterministic_datetime_literals(self):
        """All timestamps in seed constants are fixed datetimes, not datetime.now()."""
        expected_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert STRATEGY_DOCS_SEED["created_at"] == expected_ts
        assert STRATEGY_AUDIT_SEEDS[0]["timestamp"] == expected_ts
        assert SKILLS_SEED["created_at"] == expected_ts
        assert PARENT_ACCOUNT_SEED["created_at"] == expected_ts

    def test_parent_account_seed_has_organization_id(self):
        assert "organization_id" in PARENT_ACCOUNT_SEED


# ---------------------------------------------------------------------------
# is_dev_project guard tests
# ---------------------------------------------------------------------------


class TestIsDevProject:
    def test_ken_e_dev_is_dev(self):
        assert is_dev_project("ken-e-dev") is True

    def test_foo_dev_is_dev(self):
        assert is_dev_project("foo-dev") is True

    def test_ken_e_staging_is_not_dev(self):
        assert is_dev_project("ken-e-staging") is False

    def test_ken_e_prod_is_not_dev(self):
        assert is_dev_project("ken-e-prod") is False

    def test_dev_bucket_is_not_dev(self):
        # 'dev' prefix, not '-dev' suffix
        assert is_dev_project("dev-bucket") is False

    def test_empty_string_is_not_dev(self):
        assert is_dev_project("") is False

    def test_just_dev_is_dev(self):
        # Edge case: a project named exactly "dev" — ends with "-dev"? No. "-dev" != "dev"
        # "dev".endswith("-dev") → False. Correct — we require the *hyphenated* suffix.
        assert is_dev_project("dev") is False

    def test_hyphen_dev_is_dev(self):
        # Minimal valid dev project name
        assert is_dev_project("-dev") is True


# ---------------------------------------------------------------------------
# build_seed_paths tests
# ---------------------------------------------------------------------------


class TestBuildSeedPaths:
    def test_all_paths_start_with_account_prefix(self):
        """Every collection path must begin with accounts/{account_id}/
        (except the parent account doc itself whose collection is 'accounts').
        """
        account_id = "acc_X"
        paths = build_seed_paths(account_id)
        for collection, _doc_id, _data in paths:
            assert collection == "accounts" or collection.startswith(
                f"accounts/{account_id}/"
            ), f"Unexpected collection path: {collection!r}"

    def test_default_account_id_is_not_hardcoded_in_paths(self):
        """Using a custom account_id flows through to all paths (no test_acc_fixture leak)."""
        account_id = "custom_acc_xyz"
        paths = build_seed_paths(account_id)
        for collection, _doc_id, _data in paths:
            if collection != "accounts":
                assert "test_acc_fixture" not in collection, (
                    f"Literal 'test_acc_fixture' leaked into path for custom account_id: {collection!r}"
                )

    def test_expected_paths_are_present(self):
        account_id = "test_acc_fixture"
        paths = build_seed_paths(account_id)
        collections = [c for c, _, _ in paths]
        base = f"accounts/{account_id}"

        assert "accounts" in collections
        assert f"{base}/strategy_docs" in collections
        assert f"{base}/strategy_docs/business_strategy/versions" in collections
        assert f"{base}/strategy_audit" in collections
        assert f"{base}/skills" in collections
        assert f"{base}/skills/skill_seed_outreach_v1/versions" in collections

    def test_strategy_audit_count(self):
        paths = build_seed_paths("test_acc")
        audit_paths = [
            (c, d) for c, d, _ in paths if "strategy_audit" in c and "versions" not in c
        ]
        assert len(audit_paths) >= 2

    def test_strategy_docs_version_count(self):
        paths = build_seed_paths("test_acc")
        version_paths = [
            (c, d)
            for c, d, _ in paths
            if "strategy_docs/business_strategy/versions" in c
        ]
        assert len(version_paths) >= 2

    def test_skills_version_count(self):
        paths = build_seed_paths("test_acc")
        version_paths = [
            (c, d) for c, d, _ in paths if "skill_seed_outreach_v1/versions" in c
        ]
        assert len(version_paths) >= 2

    def test_account_id_resolved_in_strategy_doc_payload(self):
        """The PLACEHOLDER value in STRATEGY_DOCS_SEED must be replaced with account_id."""
        account_id = "resolved_acc"
        paths = build_seed_paths(account_id)
        for collection, doc_id, data in paths:
            if doc_id == "business_strategy" and "strategy_docs" in collection:
                assert data["account_id"] == account_id
                assert data["account_id"] != "PLACEHOLDER"


# ---------------------------------------------------------------------------
# parse_args tests
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_default_account_id(self):
        args = parse_args([])
        assert args.account_id == "test_acc_fixture"

    def test_default_not_dev_flag(self):
        args = parse_args([])
        assert args.yes_i_know_its_not_dev is False

    def test_custom_account_id(self):
        args = parse_args(["--account-id", "my_custom_acc"])
        assert args.account_id == "my_custom_acc"

    def test_override_flag_set(self):
        args = parse_args(["--yes-i-know-its-not-dev"])
        assert args.yes_i_know_its_not_dev is True


# ---------------------------------------------------------------------------
# main() integration (no Firestore)
# ---------------------------------------------------------------------------


class TestMainGuard:
    def test_main_rejects_non_dev_project(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        result = main([])
        assert result == 1

    def test_main_rejects_prod_project(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-prod")
        result = main([])
        assert result == 1

    def test_main_proceeds_with_override_flag(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        mock_service = MagicMock()
        mock_service.health_check.return_value = True
        mock_service.create_document.return_value = "doc_id"

        with patch(
            "seed_shape_b_fixtures.get_firestore_service", return_value=mock_service
        ):
            result = main(["--yes-i-know-its-not-dev"])

        assert result == 0

    def test_main_succeeds_on_dev_project(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        mock_service = MagicMock()
        mock_service.health_check.return_value = True
        mock_service.create_document.return_value = "doc_id"

        with patch(
            "seed_shape_b_fixtures.get_firestore_service", return_value=mock_service
        ):
            result = main([])

        assert result == 0

    def test_main_fails_when_health_check_fails(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        mock_service = MagicMock()
        mock_service.health_check.return_value = False

        with patch(
            "seed_shape_b_fixtures.get_firestore_service", return_value=mock_service
        ):
            result = main([])

        assert result == 1

    def test_main_fails_on_create_document_error(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        mock_service = MagicMock()
        mock_service.health_check.return_value = True
        mock_service.create_document.side_effect = RuntimeError("Firestore error")

        with patch(
            "seed_shape_b_fixtures.get_firestore_service", return_value=mock_service
        ):
            result = main([])

        assert result == 1
