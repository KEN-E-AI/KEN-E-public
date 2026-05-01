"""Unit tests for migrate_to_shape_b.py CLI scaffolding (DM-1 / DM-2) and runner (DM-3).

Covers:
- MigrateConfig validation (empty old_prefix / new_subcollection, special-case flags)
- --list exit code 0 with empty RESOURCES (subprocess, real CLI)
- --list rendering with a non-empty RESOURCES (monkeypatch + main() invocation)
- Missing GOOGLE_CLOUD_PROJECT_ID → exit code 2
- --resource=unknown exits with code 2 and a clear "unknown resource" message (DM-2)
- Runner: copy_resource, verify_resource, migrate_resource via FakeFirestoreClient
- CLI wiring: --resource and --all dispatch
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
from _migrate_shape_b.runner import (  # noqa: E402
    CopyResult,
    VerifyResult,
    copy_resource,
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
    """Minimal write-batch that applies writes to the client store on commit."""

    def __init__(self, client: "FakeFirestoreClient") -> None:
        self._client = client
        self._ops: list[tuple[str, dict[str, Any]]] = []

    def set(self, doc_ref: _FakeDocRef, data: dict[str, Any]) -> None:
        self._ops.append((doc_ref._path, data))

    def commit(self) -> None:
        for path, data in self._ops:
            self._client._store[path] = data
        self._ops.clear()


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

    def test_list_empty_registry_exits_zero(self) -> None:
        """AC-1: --list with empty RESOURCES exits 0 and prints the empty-state message."""
        result = run_cli("--list", env={"GOOGLE_CLOUD_PROJECT_ID": "test-project-id"})
        assert result.returncode == 0
        assert "(no resources registered)" in result.stdout

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
            exit_code = cli_module.cmd_resource("missing_name")

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
            exit_code = cli_module.cmd_resource("strategy_docs")

        stderr_output = buf.getvalue()
        assert exit_code == 3
        assert "unknown resource:" not in stderr_output
        assert "DM-3" in stderr_output


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

    def test_resource_dry_run_returns_usage_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<name> --dry-run routes to DM-6 stub (exit 2)."""
        monkeypatch.setattr(
            cli_module,
            "RESOURCES",
            {
                "example": MigrateConfig(
                    old_prefix="example_", new_subcollection="example"
                )
            },
        )
        exit_code = cli_module.cmd_resource(
            "example", "proj", "(default)", dry_run=True, confirm_delete=False
        )
        assert exit_code == 2

    def test_resource_confirm_delete_returns_usage_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--resource=<name> --confirm-delete routes to DM-5 stub (exit 2)."""
        monkeypatch.setattr(
            cli_module,
            "RESOURCES",
            {
                "example": MigrateConfig(
                    old_prefix="example_", new_subcollection="example"
                )
            },
        )
        exit_code = cli_module.cmd_resource(
            "example", "proj", "(default)", dry_run=False, confirm_delete=True
        )
        assert exit_code == 2
