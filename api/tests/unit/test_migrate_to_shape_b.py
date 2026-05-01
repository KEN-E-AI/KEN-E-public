"""Unit tests for migrate_to_shape_b.py CLI scaffolding (DM-1 / DM-2).

Covers:
- MigrateConfig validation (empty old_prefix / new_subcollection, special-case flags)
- --list exit code 0 with empty RESOURCES (subprocess, real CLI)
- --list rendering with a non-empty RESOURCES (monkeypatch + main() invocation)
- Missing GOOGLE_CLOUD_PROJECT_ID → exit code 2
- --resource=unknown exits with code 2 and a clear "unknown resource" message (DM-2)
"""

import io
import subprocess
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — add api/scripts/ so the package is importable without install.
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import migrate_to_shape_b as cli_module  # noqa: E402
from _migrate_shape_b.config import MigrateConfig  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
        cfg = MigrateConfig(old_prefix="strategy_docs_", new_subcollection="strategy_docs")
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
        with pytest.raises(AttributeError):  # FrozenInstanceError (subclass of AttributeError)
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

    def test_list_non_empty_registry_sorted(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

    def test_list_logs_project_and_database_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
