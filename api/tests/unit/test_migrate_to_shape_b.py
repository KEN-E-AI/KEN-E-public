"""Unit tests for migrate_to_shape_b.py CLI scaffolding (DM-1 / DM-2), runner (DM-3),
--confirm-delete orchestration (DM-5), and --dry-run (DM-6).

Covers:
- MigrateConfig validation (empty old_prefix / new_subcollection, special-case flags)
- --list exit code 0 with empty RESOURCES (subprocess, real CLI)
- --list rendering with a non-empty RESOURCES (monkeypatch + main() invocation)
- Missing GOOGLE_CLOUD_PROJECT_ID → exit code 2
- --resource=unknown exits with code 2 and a clear "unknown resource" message (DM-2)
- Runner: copy_resource, verify_resource, migrate_resource via FakeFirestoreClient
- CLI wiring: --resource and --all dispatch
- delete_source_collections: per-account deletion, has_versions, source_is_single_collection,
  custom extractor, is_field_migration, empty registry, per-account counts (DM-5)
- CLI orchestration: --confirm-delete --yes, prompt-accept, prompt-decline, verify-fail
  short-circuit, --yes without --confirm-delete rejection (DM-5)
- dry_run_resource: source-walk, no writes, summary block, mutual exclusion (DM-6)
"""

import io
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — add api/scripts/ so the package is importable without install.
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_to_shape_b as cli_module  # noqa: E402
from _migrate_shape_b.config import MigrateConfig  # noqa: E402
from _migrate_shape_b.resources import RESOURCES  # noqa: E402
from _migrate_shape_b.runner import (  # noqa: E402
    AccountDeleteResult,
    CopyResult,
    DeleteResult,
    VerifyResult,
    _is_valid_account_id,
    copy_resource,
    delete_source_collections,
    dry_run_resource,
    migrate_resource,
    verify_resource,
)

# ---------------------------------------------------------------------------
# FakeFirestoreClient — in-memory Firestore substitute for unit tests.
# ---------------------------------------------------------------------------


class _FakeDocSnapshot:
    """Minimal document snapshot."""

    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data
        self.exists = True

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeDocRef:
    """Minimal document reference that tracks writes."""

    def __init__(self, client: "FakeFirestoreClient", path: str) -> None:
        self._client = client
        self._path = path  # e.g. "accounts/acc_A/strategy_docs/swot"

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]

    @property
    def path(self) -> str:
        return self._path

    @property
    def reference(self) -> "_FakeDocRef":
        return self

    def get(self) -> _FakeDocSnapshot:
        data = self._client._store.get(self._path, None)
        if data is None:
            snap = _FakeDocSnapshot(self.id, {})
            snap.exists = False
            return snap
        return _FakeDocSnapshot(self.id, data)

    def collection(self, name: str) -> "_FakeCollectionRef":
        return _FakeCollectionRef(self._client, f"{self._path}/{name}")

    def delete(self) -> None:
        self._client._store.pop(self._path, None)


class _FakeAggResult:
    def __init__(self, value: int) -> None:
        self.value = value


class _FakeCountQuery:
    def __init__(self, client: "FakeFirestoreClient", col_path: str) -> None:
        self._client = client
        self._col_path = col_path

    def get(self) -> list[list[_FakeAggResult]]:
        prefix = self._col_path + "/"
        count = sum(
            1
            for k in self._client._store
            if k.startswith(prefix) and k.count("/") == self._col_path.count("/") + 1
        )
        return [[_FakeAggResult(count)]]


class _FakeCollectionRef:
    """Minimal collection reference."""

    def __init__(self, client: "FakeFirestoreClient", path: str) -> None:
        self._client = client
        self._path = path  # e.g. "strategy_docs_acc_A"

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]

    def stream(self) -> list[_FakeDocSnapshot]:
        """Return snapshots for docs directly under this collection."""
        prefix = self._path + "/"
        docs = []
        seen: set[str] = set()
        for full_path, data in self._client._store.items():
            if not full_path.startswith(prefix):
                continue
            rel = full_path[len(prefix) :]
            parts = rel.split("/")
            if len(parts) == 1:  # direct child doc
                doc_id = parts[0]
                if doc_id not in seen:
                    seen.add(doc_id)
                    snap = _FakeDocSnapshot(doc_id, data)
                    # Attach a reference so runner can recurse into subcollections
                    snap.reference = _FakeDocRef(self._client, full_path)
                    docs.append(snap)
        return docs

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._client, f"{self._path}/{doc_id}")

    def count(self) -> _FakeCountQuery:
        return _FakeCountQuery(self._client, self._path)

    def list_documents(self) -> list[_FakeDocRef]:
        """Return document refs for all direct children."""
        prefix = self._path + "/"
        seen: set[str] = set()
        refs = []
        for full_path in self._client._store:
            if not full_path.startswith(prefix):
                continue
            rel = full_path[len(prefix) :]
            doc_id = rel.split("/")[0]
            if doc_id not in seen:
                seen.add(doc_id)
                refs.append(_FakeDocRef(self._client, f"{self._path}/{doc_id}"))
        return refs


class _FakeBatch:
    """Minimal write-batch that applies writes and deletes to the client store on commit."""

    def __init__(self, client: "FakeFirestoreClient") -> None:
        self._client = client
        self._set_ops: list[tuple[str, dict[str, Any]]] = []
        self._delete_ops: list[str] = []

    def set(self, doc_ref: _FakeDocRef, data: dict[str, Any]) -> None:
        self._set_ops.append((doc_ref._path, data))

    def delete(self, doc_ref: _FakeDocRef) -> None:
        self._delete_ops.append(doc_ref._path)

    def commit(self) -> None:
        for path, data in self._set_ops:
            self._client._store[path] = data
        for path in self._delete_ops:
            self._client._store.pop(path, None)
        self._set_ops.clear()
        self._delete_ops.clear()


class FakeFirestoreClient:
    """Minimal in-memory Firestore client for runner unit tests.

    Stores data in a flat dict keyed by full Firestore path.
    E.g. ``"strategy_docs_acc_A/swot"`` → ``{"field": "value"}``
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    # --- Seeding helpers ---

    def seed(self, path: str, data: dict[str, Any]) -> None:
        """Write a document at *path* (e.g. ``"strategy_docs_acc_A/swot"``)."""
        self._store[path] = data

    # --- SDK interface the runner uses ---

    def collections(self) -> list[_FakeCollectionRef]:
        """Return top-level collection references (distinct level-1 path segments)."""
        seen: set[str] = set()
        refs = []
        for path in self._store:
            col_name = path.split("/")[0]
            if col_name not in seen:
                seen.add(col_name)
                refs.append(_FakeCollectionRef(self, col_name))
        return refs

    def collection(self, path: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self, path)

    def document(self, path: str) -> _FakeDocRef:
        return _FakeDocRef(self, path)

    def batch(self) -> _FakeBatch:
        return _FakeBatch(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cli(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the CLI in a subprocess with an explicit environment.

    ``env`` replaces the child's entire environment (no ambient vars inherited).
    Callers that need the real OS environment should pass ``{**os.environ, ...}``.
    Tests that verify missing-env-var behaviour must pass a sparse dict (or ``{}``)
    to strip ``GOOGLE_CLOUD_PROJECT_ID`` from the child's scope.
    """
    script = str(SCRIPTS_DIR / "migrate_to_shape_b.py")
    return subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# TestMigrateConfig
# ---------------------------------------------------------------------------


class TestMigrateConfig:
    """MigrateConfig dataclass validation."""

    def test_valid_config_standard(self) -> None:
        cfg = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        assert cfg.old_prefix == "strategy_docs_"
        assert cfg.new_subcollection == "strategy_docs"
        assert cfg.has_versions is False
        assert cfg.account_id_extractor is None
        assert cfg.source_is_single_collection is False
        assert cfg.destination_doc_id is None
        assert cfg.is_field_migration is False

    def test_empty_old_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="old_prefix"):
            MigrateConfig(old_prefix="", new_subcollection="strategy_docs")

    def test_empty_new_subcollection_raises(self) -> None:
        with pytest.raises(ValueError, match="new_subcollection"):
            MigrateConfig(old_prefix="strategy_docs_", new_subcollection="")

    def test_empty_new_subcollection_raises_regardless_of_flags(self) -> None:
        with pytest.raises(ValueError, match="new_subcollection"):
            MigrateConfig(
                old_prefix="",
                new_subcollection="",
                source_is_single_collection=True,
            )

    def test_empty_old_prefix_allowed_when_source_is_single_collection(self) -> None:
        cfg = MigrateConfig(
            old_prefix="",
            new_subcollection="monitoring_topics",
            source_is_single_collection=True,
            destination_doc_id="default",
        )
        assert cfg.old_prefix == ""
        assert cfg.source_is_single_collection is True
        assert cfg.destination_doc_id == "default"

    def test_empty_old_prefix_allowed_when_is_field_migration(self) -> None:
        cfg = MigrateConfig(
            old_prefix="",
            new_subcollection="members_migration",
            is_field_migration=True,
        )
        assert cfg.is_field_migration is True

    def test_has_versions_flag(self) -> None:
        cfg = MigrateConfig(
            old_prefix="strategy_docs_",
            new_subcollection="strategy_docs",
            has_versions=True,
        )
        assert cfg.has_versions is True

    def test_frozen_config_is_immutable(self) -> None:
        cfg = MigrateConfig(old_prefix="x_", new_subcollection="x")
        with pytest.raises(
            AttributeError
        ):  # FrozenInstanceError (subclass of AttributeError)
            cfg.old_prefix = "changed"  # type: ignore[misc]

    def test_account_id_extractor_accepted(self) -> None:
        def extractor(name: str) -> str:
            return name.removeprefix("performance_profiles_acc_")

        cfg = MigrateConfig(
            old_prefix="performance_profiles_",
            new_subcollection="performance_profiles",
            account_id_extractor=extractor,
        )
        assert cfg.account_id_extractor is not None
        assert cfg.account_id_extractor("performance_profiles_acc_abc_xyz") == "abc_xyz"


# ---------------------------------------------------------------------------
# TestListCommand
# ---------------------------------------------------------------------------


class TestListCommand:
    """--list subcommand behaviour."""

    def test_list_exits_zero_and_shows_registered_resources(self) -> None:
        """AC-1 (updated DM-12 + DM-30): --list exits 0 and lists the registered resources."""
        result = run_cli("--list", env={"GOOGLE_CLOUD_PROJECT_ID": "test-project-id"})
        assert result.returncode == 0
        # Strategy suite (DM-12)
        assert "strategy_processing_state" in result.stdout
        assert "strategy_docs" in result.stdout
        assert "strategy_audit" in result.stdout
        # Analytics suite (DM-30)
        assert "agent_analytics" in result.stdout
        assert "cost_aggregations" in result.stdout
        assert "performance_profiles" in result.stdout

    def test_list_empty_registry_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC-1: --list with empty RESOURCES (in-process monkeypatched) exits 0 and prints the empty-state message."""
        monkeypatch.setattr(cli_module, "RESOURCES", {})
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project-id")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cli_module.cmd_list()

        assert exit_code == 0
        assert "(no resources registered)" in buf.getvalue()

    def test_list_non_empty_registry_sorted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--list with a populated RESOURCES prints sorted resource → path lines."""
        fake_resources = {
            "strategy_docs": MigrateConfig(
                old_prefix="strategy_docs_", new_subcollection="strategy_docs"
            ),
            "agent_analytics": MigrateConfig(
                old_prefix="agent_analytics_", new_subcollection="agent_analytics"
            ),
        }
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project-id")

        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cli_module.cmd_list()

        output = buf.getvalue()
        assert exit_code == 0
        lines = [line for line in output.splitlines() if line.strip()]
        assert lines[0].startswith("agent_analytics"), f"Expected sorted; got: {lines}"
        assert lines[1].startswith("strategy_docs"), f"Expected sorted; got: {lines}"
        assert "accounts/{account_id}/agent_analytics" in lines[0]
        assert "accounts/{account_id}/strategy_docs" in lines[1]

    def test_list_missing_project_id_exits_two(self) -> None:
        """Missing GOOGLE_CLOUD_PROJECT_ID → exit code 2."""
        result = run_cli("--list", env={})
        assert result.returncode == 2
        assert "GOOGLE_CLOUD_PROJECT_ID" in result.stderr

    def test_list_logs_project_and_database_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Startup logging includes project_id and database_id."""
        result = run_cli(
            "--list",
            env={
                "GOOGLE_CLOUD_PROJECT_ID": "my-project",
                "FIRESTORE_DATABASE_ID": "my-db",
            },
        )
        assert result.returncode == 0
        # Startup line goes to stderr
        assert "my-project" in result.stderr
        assert "my-db" in result.stderr

    def test_list_default_database_id(self) -> None:
        """When FIRESTORE_DATABASE_ID is absent, database_id defaults to '(default)'."""
        result = run_cli(
            "--list",
            env={"GOOGLE_CLOUD_PROJECT_ID": "my-project"},
        )
        assert result.returncode == 0
        assert "(default)" in result.stderr


# ---------------------------------------------------------------------------
# TestUnknownResource
# ---------------------------------------------------------------------------


class TestUnknownResource:
    """--resource=<name> validation against the RESOURCES registry (DM-2 / AC-2)."""

    def test_unknown_resource_empty_registry_exits_two(self) -> None:
        """AC-2: --resource=unknown with empty RESOURCES exits 2 and prints the error."""
        result = run_cli(
            "--resource=unknown",
            env={"GOOGLE_CLOUD_PROJECT_ID": "test-project-id"},
        )
        assert result.returncode == 2
        assert result.stdout == ""
        assert "unknown resource:" in result.stderr
        assert "'unknown'" in result.stderr
        assert "--list" in result.stderr

    def test_unknown_resource_non_empty_registry_exits_two(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Registry presence does not change the unknown-name verdict.

        Even when RESOURCES has entries, an unrecognised name must still exit 2
        with the AC-2 message (regression-guard against accidentally short-circuiting
        on registry emptiness).
        """
        fake_resources = {
            "strategy_docs": MigrateConfig(
                old_prefix="strategy_docs_", new_subcollection="strategy_docs"
            ),
        }
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project-id")

        buf = io.StringIO()
        with redirect_stderr(buf):
            exit_code = cli_module.cmd_resource(
                "missing_name",
                "test-project-id",
                "(default)",
                dry_run=False,
                confirm_delete=False,
            )

        stderr_output = buf.getvalue()
        assert exit_code == 2
        assert "unknown resource:" in stderr_output
        assert "'missing_name'" in stderr_output
        assert "--list" in stderr_output

    def test_known_resource_returns_runner_stub_not_unknown_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recognised name returns the DM-3 runner stub — not the unknown-resource message.

        This proves cmd_resource correctly distinguishes "name not in registry"
        from "name in registry but runner not yet implemented".
        """
        fake_resources = {
            "strategy_docs": MigrateConfig(
                old_prefix="strategy_docs_", new_subcollection="strategy_docs"
            ),
        }
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project-id")

        buf = io.StringIO()
        with redirect_stderr(buf):
            cli_module.cmd_resource(
                "strategy_docs",
                "test-project-id",
                "(default)",
                dry_run=False,
                confirm_delete=False,
            )

        stderr_output = buf.getvalue()
        # A recognised resource must NOT produce the "unknown resource" error —
        # proving cmd_resource distinguishes the two failure modes. The runner
        # may exit 0 (emulator present, no source docs → VERIFIED) or non-zero
        # (live-Firestore connect error); the exit code is not part of the
        # contract we're verifying here. The absence of the unknown-resource
        # message is sufficient.
        assert "unknown resource:" not in stderr_output


# ---------------------------------------------------------------------------
# TestRunner — copy_resource / verify_resource / migrate_resource
# ---------------------------------------------------------------------------


class TestRunner:
    """Runner functions tested against FakeFirestoreClient (no emulator needed)."""

    # ------------------------------------------------------------------
    # copy_resource — default extractor (prefix-strip)
    # ------------------------------------------------------------------

    def test_copy_default_extractor(self) -> None:
        """copy_resource copies docs from strategy_docs_acc_A to accounts/acc_A/strategy_docs."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        client.seed("strategy_docs_acc_A/pestle", {"title": "PESTLE"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        result = copy_resource(client, "strategy_docs", config)

        assert isinstance(result, CopyResult)
        assert result.source_collections_found == 1
        assert result.total_docs == 2
        assert client._store.get("accounts/acc_A/strategy_docs/swot") == {
            "title": "SWOT"
        }
        assert client._store.get("accounts/acc_A/strategy_docs/pestle") == {
            "title": "PESTLE"
        }
        # Source untouched
        assert "strategy_docs_acc_A/swot" in client._store

    def test_copy_multiple_accounts(self) -> None:
        """copy_resource handles multiple source collections (multiple accounts)."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_B/doc2", {"x": 2})
        client.seed("example_acc_C/doc3", {"x": 3})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = copy_resource(client, "example", config)

        assert result.source_collections_found == 3
        assert result.total_docs == 3
        assert client._store.get("accounts/acc_A/example/doc1") == {"x": 1}
        assert client._store.get("accounts/acc_B/example/doc2") == {"x": 2}
        assert client._store.get("accounts/acc_C/example/doc3") == {"x": 3}

    # ------------------------------------------------------------------
    # copy_resource — custom extractor (acc_ variant)
    # ------------------------------------------------------------------

    def test_copy_custom_extractor_for_acc_variant(self) -> None:
        """Custom extractor maps performance_profiles_acc_abc_xyz → account_id=abc_xyz."""

        def _extractor(name: str) -> str:
            if name.startswith("performance_profiles_acc_"):
                return name.removeprefix("performance_profiles_acc_")
            return name.removeprefix("performance_profiles_")

        client = FakeFirestoreClient()
        client.seed("performance_profiles_acc_abc_xyz/prof1", {"score": 0.9})

        config = MigrateConfig(
            old_prefix="performance_profiles_",
            new_subcollection="performance_profiles",
            account_id_extractor=_extractor,
        )
        result = copy_resource(client, "performance_profiles", config)

        assert result.total_docs == 1
        assert client._store.get("accounts/abc_xyz/performance_profiles/prof1") == {
            "score": 0.9
        }

    # ------------------------------------------------------------------
    # copy_resource — has_versions=True
    # ------------------------------------------------------------------

    def test_copy_with_versions_subcollection(self) -> None:
        """has_versions=True copies /versions/{n} sub-docs to destination."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        client.seed("strategy_docs_acc_A/swot/versions/1", {"v": 1})
        client.seed("strategy_docs_acc_A/swot/versions/2", {"v": 2})

        config = MigrateConfig(
            old_prefix="strategy_docs_",
            new_subcollection="strategy_docs",
            has_versions=True,
        )
        copy_resource(client, "strategy_docs", config)

        assert client._store.get("accounts/acc_A/strategy_docs/swot") == {
            "title": "SWOT"
        }
        assert client._store.get("accounts/acc_A/strategy_docs/swot/versions/1") == {
            "v": 1
        }
        assert client._store.get("accounts/acc_A/strategy_docs/swot/versions/2") == {
            "v": 2
        }

    # ------------------------------------------------------------------
    # copy_resource — idempotency (skip-already-migrated, AC-4)
    # ------------------------------------------------------------------

    def test_skip_already_migrated_main_doc(self) -> None:
        """copy_resource skips a main doc already at the destination; docs_written == 0."""
        client = FakeFirestoreClient()
        # Source doc
        client.seed("example_acc_A/doc1", {"v": 1})
        # Pre-seed the destination — simulates a prior successful run
        client.seed("accounts/acc_A/example/doc1", {"v": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = copy_resource(client, "example", config)

        # No new docs written — the destination already had doc1
        assert result.total_docs == 0
        # Destination doc is still intact (not overwritten)
        assert client._store.get("accounts/acc_A/example/doc1") == {"v": 1}

    def test_skip_already_migrated_partial_versions(self) -> None:
        """Main doc already at destination; only missing versions are written (partial resume)."""
        client = FakeFirestoreClient()
        # Source: main doc + 2 versions
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        client.seed("strategy_docs_acc_A/swot/versions/1", {"v": 1})
        client.seed("strategy_docs_acc_A/swot/versions/2", {"v": 2})
        # Destination: main doc already written; version 1 already there; version 2 missing
        client.seed("accounts/acc_A/strategy_docs/swot", {"title": "SWOT"})
        client.seed("accounts/acc_A/strategy_docs/swot/versions/1", {"v": 1})

        config = MigrateConfig(
            old_prefix="strategy_docs_",
            new_subcollection="strategy_docs",
            has_versions=True,
        )
        result = copy_resource(client, "strategy_docs", config)

        # Only version 2 was newly written; main doc and version 1 were skipped
        assert result.total_docs == 1
        # All three destination docs are present and correct
        assert client._store.get("accounts/acc_A/strategy_docs/swot") == {
            "title": "SWOT"
        }
        assert client._store.get("accounts/acc_A/strategy_docs/swot/versions/1") == {
            "v": 1
        }
        assert client._store.get("accounts/acc_A/strategy_docs/swot/versions/2") == {
            "v": 2
        }

    # ------------------------------------------------------------------
    # copy_resource — source_is_single_collection + destination_doc_id
    # ------------------------------------------------------------------

    def test_copy_source_is_single_collection_with_destination_doc_id(self) -> None:
        """DM-PRD-04 use-case: monitoring_topics/{account_id} → accounts/{id}/monitoring_topics/default."""
        client = FakeFirestoreClient()
        client.seed("monitoring_topics/acc_X", {"topic": "seo"})
        client.seed("monitoring_topics/acc_Y", {"topic": "ppc"})

        config = MigrateConfig(
            old_prefix="",
            new_subcollection="monitoring_topics",
            source_is_single_collection=True,
            destination_doc_id="default",
        )
        result = copy_resource(client, "monitoring_topics", config)

        assert result.source_collections_found == 2
        assert client._store.get("accounts/acc_X/monitoring_topics/default") == {
            "topic": "seo"
        }
        assert client._store.get("accounts/acc_Y/monitoring_topics/default") == {
            "topic": "ppc"
        }

    # ------------------------------------------------------------------
    # copy_resource — is_field_migration raises NotImplementedError
    # ------------------------------------------------------------------

    def test_is_field_migration_raises_not_implemented(self) -> None:
        """is_field_migration=True raises NotImplementedError with DM-PRD-07 pointer."""
        client = FakeFirestoreClient()
        config = MigrateConfig(
            old_prefix="",
            new_subcollection="members_migration",
            is_field_migration=True,
        )
        with pytest.raises(NotImplementedError, match="DM-PRD-07"):
            copy_resource(client, "members_migration", config)

    def test_verify_is_field_migration_raises_not_implemented(self) -> None:
        """verify_resource also raises NotImplementedError for is_field_migration=True."""
        client = FakeFirestoreClient()
        config = MigrateConfig(
            old_prefix="",
            new_subcollection="members_migration",
            is_field_migration=True,
        )
        with pytest.raises(NotImplementedError, match="DM-PRD-07"):
            verify_resource(client, "members_migration", config)

    # ------------------------------------------------------------------
    # verify_resource — count matching and mismatches
    # ------------------------------------------------------------------

    def test_verify_returns_verified_when_counts_match(self) -> None:
        """verify_resource returns VERIFIED when source and destination counts match."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("accounts/acc_A/example/doc1", {"x": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = verify_resource(client, "example", config)

        assert isinstance(result, VerifyResult)
        assert result.verified is True
        assert result.total_source == 1
        assert result.total_destination == 1

    def test_verify_returns_failed_on_count_mismatch(self) -> None:
        """verify_resource returns FAILED when destination count != source count."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_A/doc2", {"x": 2})
        # Only one doc migrated to destination (simulate partial copy)
        client.seed("accounts/acc_A/example/doc1", {"x": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = verify_resource(client, "example", config)

        assert result.verified is False
        assert len(result.mismatches) == 1
        assert result.mismatches[0].account_id == "acc_A"
        assert result.mismatches[0].source_count == 2
        assert result.mismatches[0].destination_count == 1

    def test_verify_per_account_diff_on_mismatch(self) -> None:
        """verify_resource lists each mismatching account with source/destination delta."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})  # source=1
        client.seed("example_acc_B/doc1", {"x": 1})  # source=1
        client.seed("example_acc_B/doc2", {"x": 2})  # source=2
        # Destination: acc_A correct (1), acc_B missing one
        client.seed("accounts/acc_A/example/doc1", {"x": 1})
        client.seed("accounts/acc_B/example/doc1", {"x": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = verify_resource(client, "example", config)

        assert result.verified is False
        mismatch_ids = {m.account_id for m in result.mismatches}
        assert "acc_B" in mismatch_ids
        assert "acc_A" not in mismatch_ids

    # ------------------------------------------------------------------
    # migrate_resource — summary block format
    # ------------------------------------------------------------------

    def test_migrate_resource_prints_summary_block(self) -> None:
        """migrate_resource stdout matches the PRD §4 format exactly."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_B/doc1", {"x": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = migrate_resource(client, "example", config)

        output = buf.getvalue()
        lines = output.splitlines()
        assert exit_code == 0, f"Expected exit 0, got {exit_code}. Output:\n{output}"

        assert any(ln.startswith("Resource:") and "example" in ln for ln in lines), (
            lines
        )
        assert any("Source collections found:" in ln for ln in lines), lines
        assert any("Source doc count:" in ln for ln in lines), lines
        assert any(
            "Destination path:" in ln and "accounts/{id}/example" in ln for ln in lines
        ), lines
        assert any("Destination doc count:" in ln for ln in lines), lines
        assert any("Status:" in ln and "VERIFIED" in ln for ln in lines), lines
        assert any("Next step:" in ln and "confirm-delete" in ln for ln in lines), lines

    def test_migrate_resource_returns_one_on_mismatch(self) -> None:
        """migrate_resource returns exit code 1 when verification fails."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_A/doc2", {"x": 2})
        # Pre-seed an orphan doc in destination; after copy, dest has 3 docs
        # (doc1 + doc2 from copy, orphan pre-existing) while source has 2 → mismatch.
        client.seed("accounts/acc_A/example/orphan", {"x": 99})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = migrate_resource(client, "example", config)

        output = buf.getvalue()
        assert exit_code == 1
        assert "FAILED" in output

    # ------------------------------------------------------------------
    # CLI wiring — --resource and --all dispatch
    # ------------------------------------------------------------------

    def test_resource_flag_invokes_runner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<name> calls migrate_resource with the registered config."""
        fake_config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        fake_resources = {"example": fake_config}
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)

        calls: list[tuple[str, object]] = []

        def fake_migrate(client: object, name: str, config: object) -> int:
            calls.append((name, config))
            return 0

        monkeypatch.setattr(cli_module, "migrate_resource", fake_migrate)

        # Patch firestore.Client so no real connection is made
        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            exit_code = cli_module.cmd_resource(
                "example", "test-proj", "(default)", dry_run=False, confirm_delete=False
            )

        assert exit_code == 0
        assert len(calls) == 1
        assert calls[0][0] == "example"
        assert calls[0][1] is fake_config

    def test_resource_flag_unknown_exits_two(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<unknown> exits with code 2."""
        monkeypatch.setattr(cli_module, "RESOURCES", {})
        exit_code = cli_module.cmd_resource(
            "nonexistent", "proj", "(default)", dry_run=False, confirm_delete=False
        )
        assert exit_code == 2

    def test_all_flag_iterates_alphabetically_and_stops_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all iterates sorted(RESOURCES) and stops at the first non-zero code."""
        cfg_a = MigrateConfig(old_prefix="aaa_", new_subcollection="aaa")
        cfg_b = MigrateConfig(old_prefix="bbb_", new_subcollection="bbb")
        cfg_c = MigrateConfig(old_prefix="ccc_", new_subcollection="ccc")
        fake_resources = {"bbb": cfg_b, "aaa": cfg_a, "ccc": cfg_c}
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)

        called: list[str] = []

        def fake_migrate(client: object, name: str, config: object) -> int:
            called.append(name)
            return 1 if name == "bbb" else 0  # bbb (second alphabetically) fails

        monkeypatch.setattr(cli_module, "migrate_resource", fake_migrate)

        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            exit_code = cli_module.cmd_all(
                "test-proj", "(default)", dry_run=False, confirm_delete=False
            )

        assert exit_code == 1
        assert called == ["aaa", "bbb"]  # ccc never reached

    def test_all_flag_with_empty_registry_exits_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all with an empty RESOURCES exits 0 without error."""
        monkeypatch.setattr(cli_module, "RESOURCES", {})
        exit_code = cli_module.cmd_all(
            "test-proj", "(default)", dry_run=False, confirm_delete=False
        )
        assert exit_code == 0

    def test_resource_dry_run_invokes_runner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<name> --dry-run calls dry_run_resource and returns its exit code."""
        fake_config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        monkeypatch.setattr(
            cli_module,
            "RESOURCES",
            {"example": fake_config},
        )

        calls: list[tuple[str, object]] = []

        def fake_dry_run(client: object, name: str, config: object) -> int:
            calls.append((name, config))
            return 0

        monkeypatch.setattr(cli_module, "dry_run_resource", fake_dry_run)

        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            exit_code = cli_module.cmd_resource(
                "example", "proj", "(default)", dry_run=True, confirm_delete=False
            )

        assert exit_code == 0
        assert len(calls) == 1
        assert calls[0][0] == "example"
        assert calls[0][1] is fake_config

    def test_resource_confirm_delete_with_assume_yes_invokes_deletion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<name> --confirm-delete --yes calls delete_source_collections on verified copy."""
        fake_config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        fake_resources = {"example": fake_config}
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)

        migrate_calls: list[str] = []
        delete_calls: list[str] = []

        def fake_migrate(client: object, name: str, config: object) -> int:
            migrate_calls.append(name)
            return 0

        fake_delete_result = MagicMock()
        fake_delete_result.source_collections_deleted = 1
        fake_delete_result.total_docs = 3

        def fake_delete(client: object, name: str, config: object) -> object:
            delete_calls.append(name)
            return fake_delete_result

        monkeypatch.setattr(cli_module, "migrate_resource", fake_migrate)
        monkeypatch.setattr(cli_module, "delete_source_collections", fake_delete)

        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            exit_code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=True,
            )

        assert exit_code == 0
        assert migrate_calls == ["example"]
        assert delete_calls == ["example"]


# ---------------------------------------------------------------------------
# TestDeleteSource — delete_source_collections unit tests (DM-5)
# ---------------------------------------------------------------------------


class TestDeleteSource:
    """delete_source_collections tested against FakeFirestoreClient (no emulator)."""

    # ------------------------------------------------------------------
    # Default extractor — standard prefix-based case
    # ------------------------------------------------------------------

    def test_delete_default_extractor_removes_source_leaves_destination(self) -> None:
        """Default extractor: source docs deleted; accounts/{id}/example/* untouched."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_B/doc1", {"x": 2})
        # Destination already populated (as if copy+verify passed)
        client.seed("accounts/acc_A/example/doc1", {"x": 1})
        client.seed("accounts/acc_B/example/doc1", {"x": 2})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = delete_source_collections(client, "example", config)

        assert isinstance(result, DeleteResult)
        assert result.source_collections_deleted == 2
        assert result.total_docs == 2

        # Source gone
        assert "example_acc_A/doc1" not in client._store
        assert "example_acc_B/doc1" not in client._store
        # Destination untouched
        assert client._store.get("accounts/acc_A/example/doc1") == {"x": 1}
        assert client._store.get("accounts/acc_B/example/doc1") == {"x": 2}

    # ------------------------------------------------------------------
    # has_versions=True — version sub-docs deleted before parent
    # ------------------------------------------------------------------

    def test_delete_has_versions_removes_versions_and_parent(self) -> None:
        """has_versions=True: version sub-docs and parent doc all deleted."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        client.seed("strategy_docs_acc_A/swot/versions/1", {"v": 1})
        client.seed("strategy_docs_acc_A/swot/versions/2", {"v": 2})
        # Destination present
        client.seed("accounts/acc_A/strategy_docs/swot", {"title": "SWOT"})
        client.seed("accounts/acc_A/strategy_docs/swot/versions/1", {"v": 1})
        client.seed("accounts/acc_A/strategy_docs/swot/versions/2", {"v": 2})

        config = MigrateConfig(
            old_prefix="strategy_docs_",
            new_subcollection="strategy_docs",
            has_versions=True,
        )
        result = delete_source_collections(client, "strategy_docs", config)

        # 2 version docs + 1 parent = 3 deletions
        assert result.total_docs == 3
        assert "strategy_docs_acc_A/swot" not in client._store
        assert "strategy_docs_acc_A/swot/versions/1" not in client._store
        assert "strategy_docs_acc_A/swot/versions/2" not in client._store
        # Destination untouched
        assert "accounts/acc_A/strategy_docs/swot" in client._store

    # ------------------------------------------------------------------
    # source_is_single_collection=True + destination_doc_id="default"
    # ------------------------------------------------------------------

    def test_delete_source_is_single_collection(self) -> None:
        """DM-PRD-04: monitoring_topics/{account_id} docs deleted; accounts/* untouched."""
        client = FakeFirestoreClient()
        client.seed("monitoring_topics/acc_X", {"topic": "seo"})
        client.seed("monitoring_topics/acc_Y", {"topic": "ppc"})
        # Destination present
        client.seed("accounts/acc_X/monitoring_topics/default", {"topic": "seo"})
        client.seed("accounts/acc_Y/monitoring_topics/default", {"topic": "ppc"})

        config = MigrateConfig(
            old_prefix="",
            new_subcollection="monitoring_topics",
            source_is_single_collection=True,
            destination_doc_id="default",
        )
        result = delete_source_collections(client, "monitoring_topics", config)

        assert result.source_collections_deleted == 2
        assert result.total_docs == 2
        # Source docs deleted
        assert "monitoring_topics/acc_X" not in client._store
        assert "monitoring_topics/acc_Y" not in client._store
        # Destination untouched
        assert "accounts/acc_X/monitoring_topics/default" in client._store
        assert "accounts/acc_Y/monitoring_topics/default" in client._store

    # ------------------------------------------------------------------
    # Custom account_id_extractor
    # ------------------------------------------------------------------

    def test_delete_custom_extractor(self) -> None:
        """Custom extractor: source deleted, destination untouched."""

        def _extractor(name: str) -> str:
            return name.removeprefix("performance_profiles_acc_")

        client = FakeFirestoreClient()
        client.seed("performance_profiles_acc_abc_xyz/prof1", {"score": 0.9})
        client.seed("accounts/abc_xyz/performance_profiles/prof1", {"score": 0.9})

        config = MigrateConfig(
            old_prefix="performance_profiles_",
            new_subcollection="performance_profiles",
            account_id_extractor=_extractor,
        )
        result = delete_source_collections(client, "performance_profiles", config)

        assert result.total_docs == 1
        assert "performance_profiles_acc_abc_xyz/prof1" not in client._store
        assert "accounts/abc_xyz/performance_profiles/prof1" in client._store

    # ------------------------------------------------------------------
    # is_field_migration=True raises NotImplementedError
    # ------------------------------------------------------------------

    def test_is_field_migration_raises_not_implemented(self) -> None:
        """is_field_migration=True raises NotImplementedError with DM-PRD-07 pointer."""
        client = FakeFirestoreClient()
        config = MigrateConfig(
            old_prefix="",
            new_subcollection="members_migration",
            is_field_migration=True,
        )
        with pytest.raises(NotImplementedError, match="DM-PRD-07"):
            delete_source_collections(client, "members_migration", config)

    # ------------------------------------------------------------------
    # Empty / no matching collections
    # ------------------------------------------------------------------

    def test_delete_empty_registry_returns_zero_counts(self) -> None:
        """No matching source collections → DeleteResult with total_docs=0."""
        client = FakeFirestoreClient()
        # Seed only unrelated collections
        client.seed("unrelated_col/doc1", {"x": 1})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = delete_source_collections(client, "example", config)

        assert result.total_docs == 0
        assert result.source_collections_deleted == 0

    # ------------------------------------------------------------------
    # Per-account count accuracy
    # ------------------------------------------------------------------

    def test_delete_per_account_counts_sum_correctly(self) -> None:
        """3-account seed with 2/5/1 docs — DeleteResult sums to total_docs=8."""
        client = FakeFirestoreClient()
        for i in range(2):
            client.seed(f"example_acc_A/doc{i}", {"n": i})
        for i in range(5):
            client.seed(f"example_acc_B/doc{i}", {"n": i})
        for i in range(1):
            client.seed(f"example_acc_C/doc{i}", {"n": i})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")
        result = delete_source_collections(client, "example", config)

        assert result.source_collections_deleted == 3
        assert result.total_docs == 8
        counts_by_account = {a.account_id: a.docs_deleted for a in result.accounts}
        assert counts_by_account["acc_A"] == 2
        assert counts_by_account["acc_B"] == 5
        assert counts_by_account["acc_C"] == 1


# ---------------------------------------------------------------------------
# TestConfirmDeleteOrchestration — CLI --confirm-delete wiring (DM-5)
# ---------------------------------------------------------------------------


class TestConfirmDeleteOrchestration:
    """CLI orchestration: --confirm-delete, prompt, --yes, verify-fail short-circuit."""

    def _make_resources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_resources = {
            "example": MigrateConfig(old_prefix="example_", new_subcollection="example")
        }
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)

    def _patch_firestore(self) -> "MagicMock":
        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        return mock_fs

    # ------------------------------------------------------------------
    # cmd_resource happy paths
    # ------------------------------------------------------------------

    def test_cmd_resource_confirm_delete_assume_yes_deletes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--confirm-delete --yes: migrate then delete, exit 0."""
        self._make_resources(monkeypatch)
        migrate_calls: list[str] = []
        delete_calls: list[str] = []

        monkeypatch.setattr(
            cli_module,
            "migrate_resource",
            lambda c, n, cfg: (migrate_calls.append(n), 0)[1],
        )

        fake_result = MagicMock(source_collections_deleted=1, total_docs=3)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_calls.append(n), fake_result)[1],
        )

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=True,
            )

        assert code == 0
        assert migrate_calls == ["example"]
        assert delete_calls == ["example"]

    def test_cmd_resource_prompt_yes_deletes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--confirm-delete with prompt answered 'YES': migration and deletion run."""
        self._make_resources(monkeypatch)
        delete_calls: list[str] = []

        monkeypatch.setattr(cli_module, "migrate_resource", lambda c, n, cfg: 0)
        fake_result = MagicMock(source_collections_deleted=1, total_docs=2)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_calls.append(n), fake_result)[1],
        )
        monkeypatch.setattr("builtins.input", lambda: "YES")

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=False,
            )

        assert code == 0
        assert delete_calls == ["example"]

    def test_cmd_resource_prompt_lowercase_yes_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prompt answered 'yes' (lowercase): deletion skipped, exit 0."""
        self._make_resources(monkeypatch)
        delete_calls: list[str] = []

        monkeypatch.setattr(cli_module, "migrate_resource", lambda c, n, cfg: 0)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_calls.append(n), None)[1],
        )
        monkeypatch.setattr("builtins.input", lambda: "yes")

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=False,
            )

        assert code == 0
        assert delete_calls == []  # deletion skipped

    def test_cmd_resource_prompt_empty_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prompt answered '' (empty): deletion skipped, exit 0."""
        self._make_resources(monkeypatch)
        delete_calls: list[str] = []

        monkeypatch.setattr(cli_module, "migrate_resource", lambda c, n, cfg: 0)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_calls.append(n), None)[1],
        )
        monkeypatch.setattr("builtins.input", lambda: "")

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=False,
            )

        assert code == 0
        assert delete_calls == []

    def test_cmd_resource_verify_fail_skips_deletion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When migrate_resource returns 1 (verify fail), delete is never called."""
        self._make_resources(monkeypatch)
        delete_calls: list[str] = []

        monkeypatch.setattr(cli_module, "migrate_resource", lambda c, n, cfg: 1)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_calls.append(n), None)[1],
        )

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_resource(
                "example",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=True,
            )

        assert code == 1
        assert delete_calls == []

    def test_cmd_resource_unknown_with_confirm_delete_exits_two(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown resource with --confirm-delete exits 2 immediately."""
        monkeypatch.setattr(cli_module, "RESOURCES", {})
        code = cli_module.cmd_resource(
            "nonexistent",
            "proj",
            "(default)",
            dry_run=False,
            confirm_delete=True,
            assume_yes=True,
        )
        assert code == 2

    # ------------------------------------------------------------------
    # cmd_all with --confirm-delete
    # ------------------------------------------------------------------

    def test_cmd_all_confirm_delete_assume_yes_all_resources(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all --confirm-delete --yes: migrates and deletes all three resources."""
        cfg_a = MigrateConfig(old_prefix="aaa_", new_subcollection="aaa")
        cfg_b = MigrateConfig(old_prefix="bbb_", new_subcollection="bbb")
        cfg_c = MigrateConfig(old_prefix="ccc_", new_subcollection="ccc")
        monkeypatch.setattr(
            cli_module, "RESOURCES", {"bbb": cfg_b, "aaa": cfg_a, "ccc": cfg_c}
        )

        migrate_order: list[str] = []
        delete_order: list[str] = []

        monkeypatch.setattr(
            cli_module,
            "migrate_resource",
            lambda c, n, cfg: (migrate_order.append(n), 0)[1],
        )
        fake_result = MagicMock(source_collections_deleted=1, total_docs=1)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_order.append(n), fake_result)[1],
        )

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_all(
                "proj", "(default)", dry_run=False, confirm_delete=True, assume_yes=True
            )

        assert code == 0
        assert migrate_order == ["aaa", "bbb", "ccc"]
        assert delete_order == ["aaa", "bbb", "ccc"]

    def test_cmd_all_confirm_delete_stops_on_middle_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all --confirm-delete: stops when second resource's migrate returns 1."""
        cfg_a = MigrateConfig(old_prefix="aaa_", new_subcollection="aaa")
        cfg_b = MigrateConfig(old_prefix="bbb_", new_subcollection="bbb")
        cfg_c = MigrateConfig(old_prefix="ccc_", new_subcollection="ccc")
        monkeypatch.setattr(
            cli_module, "RESOURCES", {"bbb": cfg_b, "aaa": cfg_a, "ccc": cfg_c}
        )

        migrate_order: list[str] = []
        delete_order: list[str] = []

        def fake_migrate(c: object, n: str, cfg: object) -> int:
            migrate_order.append(n)
            return 1 if n == "bbb" else 0

        monkeypatch.setattr(cli_module, "migrate_resource", fake_migrate)
        fake_result = MagicMock(source_collections_deleted=1, total_docs=1)
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: (delete_order.append(n), fake_result)[1],
        )

        with patch.dict(
            "sys.modules", {"google.cloud.firestore": self._patch_firestore()}
        ):
            code = cli_module.cmd_all(
                "proj", "(default)", dry_run=False, confirm_delete=True, assume_yes=True
            )

        assert code == 1
        assert migrate_order == ["aaa", "bbb"]  # ccc never reached
        assert delete_order == [
            "aaa"
        ]  # bbb failed, so bbb not deleted; ccc never reached

    # ------------------------------------------------------------------
    # --yes without --confirm-delete via subprocess
    # ------------------------------------------------------------------

    def test_yes_without_confirm_delete_exits_two(self) -> None:
        """--yes without --confirm-delete exits 2 with a clear error message."""
        result = run_cli(
            "--resource=example",
            "--yes",
            env={"GOOGLE_CLOUD_PROJECT_ID": "test-proj"},
        )
        assert result.returncode == 2
        assert "--yes" in result.stderr


# ---------------------------------------------------------------------------
# TestDryRun — dry_run_resource via FakeFirestoreClient (DM-6)
# ---------------------------------------------------------------------------


class TestDryRun:
    """dry_run_resource tested against FakeFirestoreClient."""

    # ------------------------------------------------------------------
    # dry_run_resource — default extractor (prefix-strip)
    # ------------------------------------------------------------------

    def test_dry_run_default_extractor(self) -> None:
        """dry_run_resource counts source docs without writing to the destination."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_A/doc2", {"x": 2})
        client.seed("example_acc_B/doc1", {"x": 3})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = dry_run_resource(client, "example", config)

        output = buf.getvalue()
        assert exit_code == 0, output
        # No writes to destination
        dest_keys = [k for k in client._store if k.startswith("accounts/")]
        assert dest_keys == [], f"dry-run must not write: {dest_keys}"
        # Summary block present
        assert "Source doc count:" in output
        assert "DRY RUN" in output
        assert "re-run without --dry-run to copy" in output

    def test_dry_run_source_is_single_collection(self) -> None:
        """dry_run_resource handles source_is_single_collection=True without writes."""
        client = FakeFirestoreClient()
        client.seed("monitoring_topics/acc_X", {"topic": "seo"})
        client.seed("monitoring_topics/acc_Y", {"topic": "ppc"})

        config = MigrateConfig(
            old_prefix="",
            new_subcollection="monitoring_topics",
            source_is_single_collection=True,
            destination_doc_id="default",
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = dry_run_resource(client, "monitoring_topics", config)

        output = buf.getvalue()
        assert exit_code == 0, output
        dest_keys = [k for k in client._store if k.startswith("accounts/")]
        assert dest_keys == [], f"dry-run must not write: {dest_keys}"
        assert "DRY RUN" in output
        assert "Source collections found:" in output

    def test_dry_run_field_migration_raises_not_implemented(self) -> None:
        """dry_run_resource raises NotImplementedError for is_field_migration=True."""
        client = FakeFirestoreClient()
        config = MigrateConfig(
            old_prefix="",
            new_subcollection="members_migration",
            is_field_migration=True,
        )
        with pytest.raises(NotImplementedError, match="DM-PRD-07"):
            dry_run_resource(client, "members_migration", config)

    def test_dry_run_does_not_write_to_destination(self) -> None:
        """dry_run_resource leaves the _store completely unchanged for destination paths."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_A/doc2", {"x": 2})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")

        store_before = dict(client._store)
        dry_run_resource(client, "example", config)
        # Only the two original source docs may exist — no new accounts/... paths
        store_after = dict(client._store)
        assert store_before == store_after, (
            f"dry-run must not modify _store. "
            f"Added: {set(store_after) - set(store_before)}"
        )

    def test_dry_run_prints_summary_block_with_status(self) -> None:
        """dry_run_resource output contains the 6-line PRD §4 summary block."""
        client = FakeFirestoreClient()
        client.seed("example_acc_A/doc1", {"x": 1})
        client.seed("example_acc_A/doc2", {"x": 2})

        config = MigrateConfig(old_prefix="example_", new_subcollection="example")

        buf = io.StringIO()
        with redirect_stdout(buf):
            dry_run_resource(client, "example", config)

        output = buf.getvalue()
        lines = output.splitlines()

        assert any(ln.startswith("Resource:") and "example" in ln for ln in lines), (
            lines
        )
        assert any("Source collections found:" in ln for ln in lines), lines
        assert any(
            "Source doc count:" in ln and ln.rstrip().endswith("2") for ln in lines
        ), lines
        assert any(
            "Destination path:" in ln and "accounts/{id}/example" in ln for ln in lines
        ), lines
        assert any("Destination doc count:" in ln for ln in lines), lines
        assert any("Status:" in ln and "DRY RUN" in ln for ln in lines), lines
        assert any(
            "Next step:" in ln and "re-run without --dry-run" in ln for ln in lines
        ), lines

    # ------------------------------------------------------------------
    # CLI mutual exclusion: --dry-run + --confirm-delete → exit 2
    # ------------------------------------------------------------------

    def test_dry_run_and_confirm_delete_mutually_exclusive(self) -> None:
        """Passing --dry-run and --confirm-delete together exits with code 2."""
        result = run_cli(
            "--resource=foo",
            "--dry-run",
            "--confirm-delete",
            env={"GOOGLE_CLOUD_PROJECT_ID": "test-project-id"},
        )
        assert result.returncode == 2
        # argparse writes to stderr on mutual-exclusion failure
        assert "dry-run" in result.stderr or "confirm-delete" in result.stderr

    def test_dry_run_and_confirm_delete_mutually_exclusive_with_all(self) -> None:
        """--all --dry-run --confirm-delete together also exits with code 2."""
        result = run_cli(
            "--all",
            "--dry-run",
            "--confirm-delete",
            env={"GOOGLE_CLOUD_PROJECT_ID": "test-project-id"},
        )
        assert result.returncode == 2
        assert "dry-run" in result.stderr or "confirm-delete" in result.stderr

    # ------------------------------------------------------------------
    # CLI wiring: unknown resource with --dry-run still exits 2
    # ------------------------------------------------------------------

    def test_dry_run_unknown_resource_exits_two(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=unknown --dry-run hits the unknown-resource check first (exit 2)."""
        monkeypatch.setattr(cli_module, "RESOURCES", {})
        buf = io.StringIO()
        with redirect_stderr(buf):
            exit_code = cli_module.cmd_resource(
                "nonexistent", "proj", "(default)", dry_run=True, confirm_delete=False
            )
        assert exit_code == 2
        assert "unknown resource:" in buf.getvalue()

    # ------------------------------------------------------------------
    # cmd_all: --dry-run invokes dry_run_resource per entry
    # ------------------------------------------------------------------

    def test_all_dry_run_calls_dry_run_resource_per_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--all --dry-run calls dry_run_resource for each registered resource."""
        cfg_a = MigrateConfig(old_prefix="aaa_", new_subcollection="aaa")
        cfg_b = MigrateConfig(old_prefix="bbb_", new_subcollection="bbb")
        fake_resources = {"bbb": cfg_b, "aaa": cfg_a}
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)

        called: list[str] = []

        def fake_dry_run(client: object, name: str, config: object) -> int:
            called.append(name)
            return 0

        monkeypatch.setattr(cli_module, "dry_run_resource", fake_dry_run)

        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            exit_code = cli_module.cmd_all(
                "proj", "(default)", dry_run=True, confirm_delete=False
            )

        assert exit_code == 0
        assert called == ["aaa", "bbb"]  # alphabetical order


# ---------------------------------------------------------------------------
# TestStrategyResourcesRegistry — DM-12 (DM-PRD-01 Phase 1)
# ---------------------------------------------------------------------------


class TestStrategyResourcesRegistry:
    """Assert that the three strategy-suite resources are correctly registered.

    These tests use the module-level RESOURCES import (the live registry, not a
    monkeypatched copy) so that any accidental change to resources.py is caught
    immediately. Intentional coupling: if a resource is renamed or removed, these
    tests should fail to signal the breakage.
    """

    def test_strategy_processing_state_registered(self) -> None:
        assert "strategy_processing_state" in RESOURCES, (
            "strategy_processing_state not found in RESOURCES"
        )
        cfg = RESOURCES["strategy_processing_state"]
        assert cfg.old_prefix == "strategy_processing_state_"
        assert cfg.new_subcollection == "strategy_processing_state"
        assert cfg.has_versions is False

    def test_strategy_docs_registered_with_versions(self) -> None:
        assert "strategy_docs" in RESOURCES, "strategy_docs not found in RESOURCES"
        cfg = RESOURCES["strategy_docs"]
        assert cfg.old_prefix == "strategy_docs_"
        assert cfg.new_subcollection == "strategy_docs"
        assert cfg.has_versions is True

    def test_strategy_audit_registered(self) -> None:
        assert "strategy_audit" in RESOURCES, "strategy_audit not found in RESOURCES"
        cfg = RESOURCES["strategy_audit"]
        assert cfg.old_prefix == "strategy_audit_"
        assert cfg.new_subcollection == "strategy_audit"
        assert cfg.has_versions is False


# ---------------------------------------------------------------------------
# TestAnalyticsResourcesRegistry — DM-PRD-02 (DM-30)
# ---------------------------------------------------------------------------


class TestAnalyticsResourcesRegistry:
    """Assert the three analytics-suite resources are correctly registered.

    PO verification (2026-05-07) determined the PRD's "two source-collection
    naming variants" claim was unsupported by code or live data — account_ids
    are uniformly `acc_<uuid>` per `routers/accounts.py:72,87`, the only write
    site is `f"performance_profiles_{self.account_id}"`, and no `_acc_acc_`
    double-prefix collections exist in dev/staging/prod. The custom
    `_performance_profiles_extractor` was therefore removed; the default
    `removeprefix("performance_profiles_")` correctly returns `acc_<hex>`.
    """

    def test_agent_analytics_registered(self) -> None:
        assert RESOURCES["agent_analytics"] == MigrateConfig(
            old_prefix="agent_analytics_",
            new_subcollection="agent_analytics",
            has_versions=False,
        )

    def test_cost_aggregations_registered(self) -> None:
        assert RESOURCES["cost_aggregations"] == MigrateConfig(
            old_prefix="cost_aggregations_",
            new_subcollection="cost_aggregations",
            has_versions=False,
        )

    def test_performance_profiles_registered(self) -> None:
        cfg = RESOURCES["performance_profiles"]
        assert cfg == MigrateConfig(
            old_prefix="performance_profiles_",
            new_subcollection="performance_profiles",
            has_versions=False,
        )
        assert cfg.account_id_extractor is None


# ---------------------------------------------------------------------------
# TestShapeBLikeResourcesRegistry — DM-PRD-04 (DM-22)
# ---------------------------------------------------------------------------


class TestShapeBLikeResourcesRegistry:
    """Assert the two Shape B-like resources are correctly registered.

    DM-21 (PO-verified audit) confirmed:
    - Both collections hold exactly one document per account, whose doc-id IS the
      account_id.  The canonical destination doc-id is ``"default"`` for both.
    - MonitoringTopics (monitoring_models.py:146) carries ``account_id`` as a
      payload field only — no ``topic_id`` or ``doc_id`` field — so no Pydantic
      model edit is required.
    - AlertManager writes/reads via ``.document(self.account_id)``; the payload
      also holds ``account_id`` as a content field, fully decoupled from the
      Firestore doc-id.
    See DM-PRD-04 §8 open-questions (resolved) for the full audit trail.

    The live RESOURCES import is used (no monkeypatching) so that any accidental
    removal or renaming of an entry fails these tests immediately.
    """

    def test_monitoring_topics_registered(self) -> None:
        assert "monitoring_topics" in RESOURCES, (
            "monitoring_topics not found in RESOURCES"
        )

    def test_monitoring_topics_source_is_single_collection(self) -> None:
        assert RESOURCES["monitoring_topics"].source_is_single_collection is True

    def test_monitoring_topics_destination_doc_id(self) -> None:
        assert RESOURCES["monitoring_topics"].destination_doc_id == "default"

    def test_monitoring_topics_has_no_versions(self) -> None:
        assert RESOURCES["monitoring_topics"].has_versions is False

    def test_monitoring_topics_full_config(self) -> None:
        assert RESOURCES["monitoring_topics"] == MigrateConfig(
            old_prefix="",
            new_subcollection="monitoring_topics",
            has_versions=False,
            source_is_single_collection=True,
            destination_doc_id="default",
        )

    def test_alert_configurations_registered(self) -> None:
        assert "alert_configurations" in RESOURCES, (
            "alert_configurations not found in RESOURCES"
        )

    def test_alert_configurations_source_is_single_collection(self) -> None:
        assert RESOURCES["alert_configurations"].source_is_single_collection is True

    def test_alert_configurations_destination_doc_id(self) -> None:
        assert RESOURCES["alert_configurations"].destination_doc_id == "default"

    def test_alert_configurations_has_no_versions(self) -> None:
        assert RESOURCES["alert_configurations"].has_versions is False

    def test_alert_configurations_full_config(self) -> None:
        assert RESOURCES["alert_configurations"] == MigrateConfig(
            old_prefix="",
            new_subcollection="alert_configurations",
            has_versions=False,
            source_is_single_collection=True,
            destination_doc_id="default",
        )


# ---------------------------------------------------------------------------
# TestMalformedSourceCollection — DM-19 / DM-PRD-00 runner empty-account-id guard.
#
# Discovered in DM-19: ken-e-dev's `(default)` Firestore had a top-level
# collection literally named `strategy_docs_` (the resource prefix with no
# account suffix). The default `_extract_account_id` strips the prefix and
# returns `""`, which the runner then plugged into `accounts/{account_id}/...`
# producing the malformed Firestore path `accounts//strategy_docs` and
# `google.api_core.exceptions.InvalidArgument` at first call.
#
# Fix contract: every phase that walks `client.collections()` (copy, verify,
# delete, dry-run) must skip + warn on any source collection that yields an
# empty / `/`-bearing / `.`/`..` account_id; the rest of the migration must
# proceed normally.
# ---------------------------------------------------------------------------


class TestMalformedSourceCollection:
    """Runner skips source collections that produce an invalid account_id."""

    # ------------------------------------------------------------------
    # copy_resource
    # ------------------------------------------------------------------

    def test_copy_skips_empty_account_id_and_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """`strategy_docs_` (empty suffix) is skipped; real account still copied."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_/orphan_doc", {"title": "Orphan"})
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        with caplog.at_level("WARNING", logger="_migrate_shape_b.runner"):
            result = copy_resource(client, "strategy_docs", config)

        # Real account copied.
        assert client._store.get("accounts/acc_A/strategy_docs/swot") == {
            "title": "SWOT"
        }
        # Malformed destination never written.
        assert "accounts//strategy_docs/orphan_doc" not in client._store
        # source_collections_found counts only the migratable one.
        assert result.source_collections_found == 1
        assert result.total_docs == 1
        # Malformed source is recorded structurally so the CLI summary surfaces it.
        assert result.malformed_sources == ["strategy_docs_"]
        # A warning identifies the malformed source collection by name.
        warning_messages = [
            r.getMessage()
            for r in caplog.records
            if r.levelname == "WARNING" and r.name == "_migrate_shape_b.runner"
        ]
        assert any(
            "strategy_docs_" in msg and "skipping" in msg.lower()
            for msg in warning_messages
        ), f"expected skip warning naming `strategy_docs_`, got: {warning_messages}"

    # ------------------------------------------------------------------
    # verify_resource
    # ------------------------------------------------------------------

    def test_verify_skips_empty_account_id(self) -> None:
        """verify_resource ignores the malformed source collection."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_/orphan_doc", {"title": "Orphan"})
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        # Pretend acc_A was already copied to the destination.
        client.seed("accounts/acc_A/strategy_docs/swot", {"title": "SWOT"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        result = verify_resource(client, "strategy_docs", config)

        assert isinstance(result, VerifyResult)
        # Only acc_A is verified; the malformed orphan is skipped.
        account_ids = [a.account_id for a in result.accounts]
        assert account_ids == ["acc_A"]
        assert result.accounts[0].source_count == 1
        assert result.accounts[0].destination_count == 1
        assert result.malformed_sources == ["strategy_docs_"]

    # ------------------------------------------------------------------
    # delete_source_collections
    # ------------------------------------------------------------------

    def test_delete_skips_empty_account_id(self) -> None:
        """delete_source_collections skips the malformed source collection."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_/orphan_doc", {"title": "Orphan"})
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        result = delete_source_collections(client, "strategy_docs", config)

        assert isinstance(result, DeleteResult)
        # Only acc_A's source is deleted.
        assert "strategy_docs_acc_A/swot" not in client._store
        # The malformed orphan is left in place (operator must clean up manually).
        assert "strategy_docs_/orphan_doc" in client._store
        # Reported deletion accounts exclude the malformed one.
        account_ids = [a.account_id for a in result.accounts]
        assert account_ids == ["acc_A"]
        assert result.malformed_sources == ["strategy_docs_"]

    # ------------------------------------------------------------------
    # dry_run_resource
    # ------------------------------------------------------------------

    def test_dry_run_skips_empty_account_id(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry_run_resource counts only migratable source collections."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_/orphan_doc", {"title": "Orphan"})
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})
        client.seed("strategy_docs_acc_B/pestle", {"title": "PESTLE"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )
        exit_code = dry_run_resource(client, "strategy_docs", config)

        assert exit_code == 0
        captured = capsys.readouterr().out
        # The dry-run summary reports 2 migratable collections, not 3.
        assert "Source collections found:   2" in captured
        assert "Source doc count:            2" in captured
        # Malformed source is surfaced in the summary block, not just the WARNING log.
        assert "Malformed source collections (skipped): 1" in captured
        assert "strategy_docs_" in captured
        assert "Operator action:" in captured

    # ------------------------------------------------------------------
    # migrate_resource summary block — operator-facing stdout contract
    # ------------------------------------------------------------------

    def test_migrate_resource_surfaces_malformed_in_summary_block(self) -> None:
        """migrate_resource stdout names the malformed source + operator-action line."""
        client = FakeFirestoreClient()
        client.seed("strategy_docs_/orphan_doc", {"title": "Orphan"})
        client.seed("strategy_docs_acc_A/swot", {"title": "SWOT"})

        config = MigrateConfig(
            old_prefix="strategy_docs_", new_subcollection="strategy_docs"
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = migrate_resource(client, "strategy_docs", config)

        output = buf.getvalue()
        # Verify is still VERIFIED — the malformed source must not poison the verify status.
        assert exit_code == 0, output
        assert "Status:" in output and "VERIFIED" in output
        # Operator-facing summary lines present and name the offender.
        assert "Malformed source collections (skipped): 1" in output, output
        assert "strategy_docs_" in output, output
        assert "Operator action:" in output, output
        assert "before --confirm-delete" in output, output

    # ------------------------------------------------------------------
    # cmd_resource --confirm-delete summary — operator-facing stdout contract
    # ------------------------------------------------------------------

    def test_cmd_resource_confirm_delete_surfaces_malformed_left_in_place(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """cmd_resource's `deletion complete` block names malformed sources left in place."""
        fake_resources = {
            "strategy_docs": MigrateConfig(
                old_prefix="strategy_docs_", new_subcollection="strategy_docs"
            )
        }
        monkeypatch.setattr(cli_module, "RESOURCES", fake_resources)
        # Stub migrate_resource — irrelevant to this assertion.
        monkeypatch.setattr(cli_module, "migrate_resource", lambda c, n, cfg: 0)
        # Real DeleteResult so the new `malformed_sources` field is populated correctly
        # (MagicMock auto-truthy / auto-iterable would print garbage; this pins the contract).
        delete_result = DeleteResult(
            resource_name="strategy_docs",
            accounts=[
                AccountDeleteResult(
                    account_id="acc_A",
                    source_collection="strategy_docs_acc_A",
                    docs_deleted=1,
                )
            ],
            malformed_sources=["strategy_docs_"],
        )
        monkeypatch.setattr(
            cli_module,
            "delete_source_collections",
            lambda c, n, cfg: delete_result,
        )

        mock_fs = MagicMock()
        mock_fs.Client.return_value = MagicMock()
        with patch.dict("sys.modules", {"google.cloud.firestore": mock_fs}):
            code = cli_module.cmd_resource(
                "strategy_docs",
                "proj",
                "(default)",
                dry_run=False,
                confirm_delete=True,
                assume_yes=True,
            )

        assert code == 0
        output = capsys.readouterr().out
        assert "Resource: strategy_docs — deletion complete" in output, output
        assert "Malformed source collections (left in place): 1" in output, output
        assert "strategy_docs_" in output, output
        assert "Operator action:" in output and "AC-2" in output, output

    # ------------------------------------------------------------------
    # _extract_account_id — direct validation helper coverage
    # ------------------------------------------------------------------

    def test_invalid_account_id_helper_rejects_empty_slash_and_dots(self) -> None:
        """The internal validator rejects empty, `/`-bearing, and `.`/`..` ids."""
        assert _is_valid_account_id("acc_A") is True
        assert _is_valid_account_id("_test_account_123") is True
        assert _is_valid_account_id("") is False
        assert _is_valid_account_id("acc/A") is False
        assert _is_valid_account_id(".") is False
        assert _is_valid_account_id("..") is False
