"""Integration tests for api/scripts/lint/check_no_agent_tool_in_chat_tree.py.

Each test builds a minimal fixture tree under pytest's ``tmp_path`` and
invokes the lint script via ``subprocess.run`` with ``--root tmp_path`` so
the real source tree is never mutated.  This makes the tests safe under
pytest-xdist and immune to crashes that leave stale files behind.

Covers six lint-rule cases:
  (a) Clean tree                        → exit 0
  (b) Violation in chat-tree file       → exit non-zero + file:line + remediation
  (c) ``strategy_agent/`` excluded      → exit 0
  (d) Test files excluded               → exit 0
  (e) Docstring / comment mentions      → exit 0  (not flagged)
  (f) Import line (no constructor)      → exit 0  (not flagged)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LINT_SCRIPT = (
    REPO_ROOT / "api" / "scripts" / "lint" / "check_no_agent_tool_in_chat_tree.py"
)

# A constructor call that the lint must detect.
_VIOLATION_LINE = "x = AgentTool(agent=some_agent)"


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
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_ok_message_printed(self, tmp_path: Path) -> None:
        result = _run(tmp_path)
        assert "OK" in result.stdout, (
            f"Expected OK in stdout on clean tree.\nstdout: {result.stdout}"
        )


# ---------------------------------------------------------------------------
# (b) Violation in a chat-tree-shaped file
# ---------------------------------------------------------------------------


class TestViolation:
    def test_violation_detected(self, tmp_path: Path) -> None:
        violation_file = tmp_path / "agent_factory" / "some_resolver.py"
        violation_file.parent.mkdir(parents=True)
        violation_file.write_text(f"# lint test fixture\nresult = {_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        assert result.returncode != 0, (
            f"Expected non-zero exit for AgentTool( constructor.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_violation_names_offending_file(self, tmp_path: Path) -> None:
        violation_file = tmp_path / "agent_factory" / "my_resolver.py"
        violation_file.parent.mkdir(parents=True)
        violation_file.write_text(f"{_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        combined = result.stdout + result.stderr
        assert "my_resolver.py" in combined, (
            f"Lint output should name the offending file.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_violation_names_line_number(self, tmp_path: Path) -> None:
        violation_file = tmp_path / "agent_factory" / "my_resolver.py"
        violation_file.parent.mkdir(parents=True)
        violation_file.write_text(f"# line 1\n# line 2\n{_VIOLATION_LINE}  # line 3\n")
        result = _run(tmp_path)
        combined = result.stdout + result.stderr
        assert ":3" in combined, (
            f"Lint output should include line number ':3'.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_remediation_message_in_stderr(self, tmp_path: Path) -> None:
        (tmp_path / "agent_factory").mkdir()
        (tmp_path / "agent_factory" / "tool.py").write_text(f"{_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        assert "isolation-required" in result.stderr, (
            f"Remediation message missing from stderr.\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (g) Isolation allow-list (AH-PRD-15 §7.7 re-plan)
# ---------------------------------------------------------------------------


class TestIsolationAllowlist:
    """The two sanctioned isolation leaves may construct AgentTool with the marker;
    anything else (including an allow-listed file WITHOUT the marker) is flagged."""

    def _write(self, root: Path, rel: str, body: str) -> None:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body)

    def test_allowlisted_file_with_marker_on_same_line_ok(self, tmp_path: Path) -> None:
        self._write(
            tmp_path,
            "tools/agent_tools/google_search.py",
            f"{_VIOLATION_LINE}  # isolation-required: AH-PRD-15 §7.7\n",
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Allow-listed file with the marker must pass.\nstderr: {result.stderr}"
        )

    def test_allowlisted_file_with_marker_on_preceding_line_ok(
        self, tmp_path: Path
    ) -> None:
        self._write(
            tmp_path,
            "tools/agent_tools/numerical_analyst.py",
            "    # isolation-required: AH-PRD-15 §7.7\n    return "
            f"{_VIOLATION_LINE.split('= ', 1)[1]}\n",
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Marker on the immediately preceding line must satisfy the guard.\n"
            f"stderr: {result.stderr}"
        )

    def test_allowlisted_file_without_marker_is_flagged(self, tmp_path: Path) -> None:
        self._write(
            tmp_path, "tools/agent_tools/google_search.py", f"{_VIOLATION_LINE}\n"
        )
        result = _run(tmp_path)
        assert result.returncode != 0, (
            "An allow-listed file must STILL be flagged when the construction lacks "
            f"the isolation-required marker.\nstdout: {result.stdout}"
        )

    def test_non_allowlisted_file_with_marker_is_flagged(self, tmp_path: Path) -> None:
        # The marker alone does not sanction a non-allow-listed file.
        self._write(
            tmp_path,
            "agent_factory/sneaky.py",
            f"{_VIOLATION_LINE}  # isolation-required\n",
        )
        result = _run(tmp_path)
        assert result.returncode != 0, (
            "A non-allow-listed file must be flagged even with the marker.\n"
            f"stdout: {result.stdout}"
        )


# ---------------------------------------------------------------------------
# (c) strategy_agent/ is excluded
# ---------------------------------------------------------------------------


class TestStrategyAgentExcluded:
    def test_strategy_agent_dir_not_flagged(self, tmp_path: Path) -> None:
        strategy_dir = tmp_path / "agents" / "strategy_agent"
        strategy_dir.mkdir(parents=True)
        (strategy_dir / "config_loader.py").write_text(
            f"# strategy-agent — stays on ADK 1.34.1\n{_VIOLATION_LINE}\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"strategy_agent/ must not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_non_strategy_sibling_still_flagged(self, tmp_path: Path) -> None:
        """Excluding strategy_agent/ must not exempt siblings."""
        sibling_dir = tmp_path / "agents" / "agent_factory"
        sibling_dir.mkdir(parents=True)
        (sibling_dir / "resolver.py").write_text(f"{_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        assert result.returncode != 0, (
            f"Non-strategy sibling should still be flagged.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (d) Test files excluded
# ---------------------------------------------------------------------------


class TestTestFilesExcluded:
    def test_file_in_tests_directory_not_flagged(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "agents" / "agent_factory" / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_something.py").write_text(
            f"# test fixture that legitimately exercises AgentTool\n"
            f"result = {_VIOLATION_LINE}\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Files inside tests/ should not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_test_prefixed_file_not_flagged(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_agent_tool_usage.py"
        test_file.write_text(f"{_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"test_*.py files should not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_nested_tests_dir_not_flagged(self, tmp_path: Path) -> None:
        nested = tmp_path / "agents" / "utils" / "tests"
        nested.mkdir(parents=True)
        (nested / "helper.py").write_text(f"{_VIOLATION_LINE}\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Files under any tests/ path-part should not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (e) Docstring and comment mentions not flagged
# ---------------------------------------------------------------------------


class TestDocstringCommentNotFlagged:
    def test_docstring_mention_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "some_module.py"
        f.write_text(
            '"""AgentTool( is the old way — use LlmAgent(mode=\'task\') instead."""\n'
            "x = 1\n"
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Docstring mention of AgentTool( must not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_comment_line_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "some_module.py"
        f.write_text("# Do NOT use AgentTool(agent=x) — see AH-PRD-15.\nx = 1\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Comment-only line with AgentTool( must not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# (f) Import line (no constructor) not flagged
# ---------------------------------------------------------------------------


class TestImportNotFlagged:
    def test_import_line_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "some_module.py"
        f.write_text("from google.adk.tools import AgentTool\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"A bare import of AgentTool (no constructor) must not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_isinstance_check_not_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "some_module.py"
        f.write_text("if isinstance(tool, AgentTool):\n    pass\n")
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"isinstance(x, AgentTool) must not trigger the lint.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
