"""Integration tests for api/scripts/lint/check_artifact_register.py.

Each test builds a minimal fixture tree under pytest's ``tmp_path`` and
invokes the lint script via ``subprocess.run`` with ``--root tmp_path`` so
the real source tree is never mutated. This makes the tests safe under
pytest-xdist and immune to crashes that leave stale files behind.

Covers the five lint-rule cases:
  (a) Clean tree       → exit 0
  (b) Violation file   → exit non-zero + file:line in output + remediation text
  (c) Wrapper (allow-listed)            → exit 0
  (d) Strategy-agent (allow-listed)     → exit 0
  (e) Test file                         → exit 0
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = REPO_ROOT / "api" / "scripts" / "lint" / "check_artifact_register.py"

# Raw call that the lint must detect — all three guarded variable names.
_VIOLATION_LINES = {
    "context": "context.save_artifact('foo.pdf', part)",
    "tool_context": "tool_context.save_artifact('bar.docx', data)",
    "artifact_service": "artifact_service.save_artifact('baz.png', img)",
}


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--root", str(root)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# (a) Clean tree
# ---------------------------------------------------------------------------


class TestCleanTree:
    def test_empty_root_exits_zero(self, tmp_path: Path) -> None:
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 on empty tree.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_ok_message_printed(self, tmp_path: Path) -> None:
        result = _run(tmp_path)
        assert "OK" in result.stdout, (
            f"Expected OK in stdout on clean tree.\nstdout: {result.stdout}"
        )


# ---------------------------------------------------------------------------
# (b) Violation: raw call in a non-allow-listed production file
# ---------------------------------------------------------------------------


class TestViolation:
    @pytest.mark.parametrize("var_name,call_expr", list(_VIOLATION_LINES.items()))
    def test_violation_detected(
        self, tmp_path: Path, var_name: str, call_expr: str
    ) -> None:
        violation_file = tmp_path / "some_new_file.py"
        violation_file.write_text(f"# lint test fixture\nresult = {call_expr}\n")
        result = _run(tmp_path)
        assert result.returncode != 0, (
            f"Expected non-zero exit for raw {var_name}.save_artifact call.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_violation_names_offending_file(self, tmp_path: Path) -> None:
        violation_file = tmp_path / "my_tool.py"
        violation_file.write_text("context.save_artifact('x.pdf', p)\n")
        result = _run(tmp_path)
        combined = result.stdout + result.stderr
        assert "my_tool.py" in combined, (
            f"Lint output should name the offending file.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_violation_names_line_number(self, tmp_path: Path) -> None:
        violation_file = tmp_path / "my_tool.py"
        violation_file.write_text(
            "# line 1\n# line 2\ntool_context.save_artifact('x.pdf', p)  # line 3\n"
        )
        result = _run(tmp_path)
        combined = result.stdout + result.stderr
        assert ":3" in combined, (
            f"Lint output should include line number ':3'.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_remediation_message_in_stderr(self, tmp_path: Path) -> None:
        """Asserts the exact remediation sentence rather than a substring so a
        reword (e.g. 'call register_artifact_v2') would still get caught."""
        (tmp_path / "agent_tool.py").write_text(
            "context.save_artifact('file.pdf', part)\n"
        )
        result = _run(tmp_path)
        assert "Use chat.artifacts.register_artifact() instead." in result.stderr, (
            f"Remediation message should be the exact sentence "
            f"'Use chat.artifacts.register_artifact() instead.'\n"
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (c) Allow-listed: wrapper file itself
# ---------------------------------------------------------------------------


class TestAllowlistBypass:
    def test_nested_wrapper_path_still_flagged(self, tmp_path: Path) -> None:
        """A file whose path *ends with* an allow-list suffix but is not at the
        correct repo-relative location must still be flagged (suffix-only matching
        would silently pass evil/api/src/kene_api/chat/artifacts.py)."""
        evil_dir = tmp_path / "evil" / "api" / "src" / "kene_api" / "chat"
        evil_dir.mkdir(parents=True)
        (evil_dir / "artifacts.py").write_text("context.save_artifact('x.pdf', part)\n")
        result = _run(tmp_path)
        assert result.returncode != 0, (
            f"A file at evil/.../artifacts.py must not bypass the allow-list.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


class TestWrapperAllowlisted:
    def test_wrapper_file_not_flagged(self, tmp_path: Path) -> None:
        """api/src/kene_api/chat/artifacts.py is allow-listed and must not
        trigger even if it contains a raw save_artifact call."""
        wrapper_dir = tmp_path / "api" / "src" / "kene_api" / "chat"
        wrapper_dir.mkdir(parents=True)
        wrapper_file = wrapper_dir / "artifacts.py"
        wrapper_file.write_text(
            "# the canonical wrapper\n"
            "version = await tool_context.save_artifact(filename, content)\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Wrapper file should not trigger the lint.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (d) Allow-listed: strategy-agent artifact_utils.py
# ---------------------------------------------------------------------------


class TestStrategyAgentAllowlisted:
    def test_strategy_agent_file_not_flagged(self, tmp_path: Path) -> None:
        """app/adk/agents/strategy_agent/artifact_utils.py is allow-listed
        as a setup-time input loader (separate ADK app, different GCS
        namespace). It must not trigger the lint."""
        strategy_dir = tmp_path / "app" / "adk" / "agents" / "strategy_agent"
        strategy_dir.mkdir(parents=True)
        strategy_file = strategy_dir / "artifact_utils.py"
        strategy_file.write_text(
            "# setup-time input loader\n"
            "version = await artifact_service.save_artifact(filename, part)\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Strategy-agent file should not trigger the lint.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (e) Test files are excluded
# ---------------------------------------------------------------------------


class TestTestFilesExcluded:
    def test_file_in_tests_directory_not_flagged(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "api" / "tests" / "integration" / "chat"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_something.py"
        test_file.write_text(
            "# test file — legitimately exercises the raw path\n"
            "result = context.save_artifact('foo.pdf', part)\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Files inside tests/ should not trigger the lint.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_test_prefixed_file_not_flagged(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_foo.py"
        test_file.write_text("tool_context.save_artifact('x.pdf', data)\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"test_*.py files should not trigger the lint.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_nested_tests_dir_not_flagged(self, tmp_path: Path) -> None:
        nested_tests = tmp_path / "app" / "adk" / "tests"
        nested_tests.mkdir(parents=True)
        nested_file = nested_tests / "some_file.py"
        nested_file.write_text("context.save_artifact('file.pdf', part)\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Files under any tests/ path-part should not trigger the lint.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
