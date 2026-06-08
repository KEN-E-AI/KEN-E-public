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

Also covers:
  (g) ISOLATION_ALLOWLIST leaf-billing-callback companion (AH-146 / AH-PRD-05 §7 AC-9)
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LINT_SCRIPT = (
    REPO_ROOT / "api" / "scripts" / "lint" / "check_no_agent_tool_in_chat_tree.py"
)

# ---------------------------------------------------------------------------
# Load ISOLATION_ALLOWLIST from the lint script at import time.
# Using importlib.util so we can reference the frozenset defined there without
# adding api/scripts/ to sys.path or importing it as a top-level module.
#
# Guard against spec_from_file_location returning None (e.g. when the script
# is absent in a stripped CI image): module_from_spec(None) raises TypeError
# which would crash pytest collection for the entire module, taking the six
# pre-existing test classes with it.  A None spec produces an empty frozenset;
# test_allowlist_matches_known_sanctioned_names will then fail with an
# actionable message rather than silently being skipped.
# ---------------------------------------------------------------------------
_lint_spec = importlib.util.spec_from_file_location(
    "_no_agent_tool_lint_check", LINT_SCRIPT
)
if _lint_spec is not None:
    _lint_mod = importlib.util.module_from_spec(_lint_spec)
    _lint_spec.loader.exec_module(_lint_mod)  # type: ignore[union-attr]
    _ISOLATION_ALLOWLIST: frozenset[str] = _lint_mod.ISOLATION_ALLOWLIST
else:
    _ISOLATION_ALLOWLIST: frozenset[str] = frozenset()  # type: ignore[no-redef]

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


# ---------------------------------------------------------------------------
# (g) ISOLATION_ALLOWLIST leaf-billing-callback companion (AH-146 / AH-PRD-05 §7 AC-9)
#
# The lint allow-list (ISOLATION_ALLOWLIST) is the source of truth for which files
# may construct an AgentTool. This class ties each allow-listed file to its factory
# and verifies the factory's leaf carries the capture_agent_tool_usage billing
# callback — so an AgentTool can never be added to the allow-list without its
# billing. Mirrors AH-PRD-15 §7 AC-4 (amended) at the supervisor-path level.
#
# Convention enforced (D5):
#   tools/agent_tools/<name>.py  →  module app.adk.tools.agent_tools.<name>
#                                →  factory create_<name>_agent_tool()
#
# Adding a file to ISOLATION_ALLOWLIST without a billing-callback-carrying factory
# that follows the convention causes the parametrized test to fail with an explicit,
# actionable error — the companion test documents this contract for future maintainers.
# ---------------------------------------------------------------------------


def _load_agent_tool_factory(allowlist_entry: str) -> object:
    """Derive and invoke the factory for an allow-list entry.

    Convention: ``tools/agent_tools/<name>.py`` →
        module ``app.adk.tools.agent_tools.<name>``,
        factory ``create_<name>_agent_tool``.

    Raises ImportError or AttributeError if the module or factory does not
    exist — surfaces a violated convention loudly at test time so future
    maintainers see *exactly* which factory is missing.
    """
    # Make app.adk.* importable by appending the workspace root to sys.path.
    # append (not insert(0, ...)) so the workspace never shadows stdlib or
    # installed packages in the test-runner process.
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.append(repo_root_str)

    name = Path(allowlist_entry).stem  # e.g. "google_search"
    module_path = f"app.adk.tools.agent_tools.{name}"
    factory_name = f"create_{name}_agent_tool"

    module = importlib.import_module(module_path)
    factory = getattr(module, factory_name)
    return factory()


class TestIsolationAllowlistLeafCallbacks:
    """Guard: every file in ISOLATION_ALLOWLIST must have a factory whose leaf
    carries capture_agent_tool_usage (AH-146 / AH-PRD-15 §7 AC-4 amended).

    Ties the allow-list (source of truth for which files may construct an
    AgentTool) to the billing-callback contract so an AgentTool can never be
    reintroduced without its billing. Adding a new file to ISOLATION_ALLOWLIST
    without a billing-callback-carrying factory that follows the
    create_<name>_agent_tool convention fails the parametrized test with an
    explicit, named error — the contract is self-documenting.
    """

    @pytest.mark.parametrize("entry", sorted(_ISOLATION_ALLOWLIST))
    def test_each_allowlist_entry_factory_has_billing_callback(
        self, entry: str
    ) -> None:
        """Each allow-listed file has a factory whose leaf carries capture_agent_tool_usage.

        Parametrized over the live ISOLATION_ALLOWLIST imported from the lint script —
        a new entry in the allow-list is automatically picked up here without any
        change to this test. Each entry is an independent test node so a broken
        ``numerical_analyst`` leaf is caught even when ``google_search`` still passes.
        The assertion names both the entry and the missing callback so the failure
        is immediately actionable.
        """
        tool = _load_agent_tool_factory(entry)
        from app.adk.agents.agent_tool_billing import (
            capture_agent_tool_usage,
        )

        leaf = tool.agent
        cb = getattr(leaf, "after_model_callback", None)
        has_callback = cb is capture_agent_tool_usage or (
            isinstance(cb, (list, tuple)) and capture_agent_tool_usage in cb
        )
        assert has_callback, (
            f"Allow-listed file {entry!r}: the factory's wrapped leaf is missing "
            "capture_agent_tool_usage as its after_model_callback. "
            "AgentTool.run_async drops the leaf's usage_metadata (GitHub #3984) — "
            "without this callback those tokens go unbilled (AH-75 defect). "
            f"Convention: create_{Path(entry).stem}_agent_tool() must build a leaf "
            "with after_model_callback=capture_agent_tool_usage. "
            "See app/adk/agents/agent_tool_billing.py and AH-PRD-15 §5 / §7.7."
        )

    def test_missing_factory_raises_with_actionable_error(self) -> None:
        """A synthetic allow-list entry without a matching factory fails explicitly.

        Documents the create_<name>_agent_tool convention: if someone adds a new
        file to ISOLATION_ALLOWLIST without creating a factory that follows the
        naming convention, the companion test above raises ImportError or
        AttributeError — not a silent pass. This negative-guard sibling proves
        the failure mode is explicit and actionable, not obscure.
        """
        fake_entry = "tools/agent_tools/nonexistent_isolation_tool.py"
        with pytest.raises((ImportError, AttributeError)):
            _load_agent_tool_factory(fake_entry)

    def test_allowlist_matches_known_sanctioned_names(self) -> None:
        """ISOLATION_ALLOWLIST matches the expected set of two sanctioned leaves.

        Pins the allow-list content so an inadvertent addition or removal is
        caught by a minimal assertion. The expected set mirrors _SANCTIONED_NAMES
        in TestNoAgentToolInSupervisorPath (app/adk) — both must be updated in
        tandem when a new sanctioned leaf is introduced.
        """
        expected_names = {"google_search", "numerical_analyst"}
        actual_names = {Path(e).stem for e in _ISOLATION_ALLOWLIST}
        assert actual_names == expected_names, (
            f"ISOLATION_ALLOWLIST names {actual_names!r} != expected {expected_names!r}. "
            "If a new sanctioned leaf was added, update this assertion AND "
            "TestNoAgentToolInSupervisorPath._SANCTIONED_NAMES in "
            "app/adk/agents/agent_factory/tests/test_chat_billing_parity.py, AND "
            "update the leaf billing tests in app/adk/agents/tests/test_agent_tool_billing.py. "
            "If a leaf was removed, remove it from both allow-lists and the billing tests."
        )
