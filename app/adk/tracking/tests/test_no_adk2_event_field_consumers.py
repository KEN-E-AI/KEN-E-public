"""Static-analysis guard: no production tracking module reads ADK 2.0-only event fields.

ADK 2.0 adds ``Event.node_info`` (NodeInfo) and ``Event.isolation_scope`` to the
event stream. The single-specialist Weave span tree is unaffected because the
emitter (``app/adk/tracking/callbacks.py`` — ``weave_before/after_agent_callback``)
does not read those fields. This test pins that invariant so a future patch that
adds a ``node_info`` or ``isolation_scope`` reference to any production tracking
module fails CI loudly rather than silently regressing MER-E's quality-scoring
extractors.

Scope: every ``*.py`` file under ``app/adk/tracking/`` **excluding** ``tests/``
and symbolic links. Rationale for the scope restriction:

- ``app/adk/agents/agent_factory/tests/test_adk2_*`` legitimately read those
  fields to drive Pydantic round-trip assertions — they are test helpers, not
  emitters.
- Future supervisor-orchestration runtime code (AH-PRD-05) may carry span
  attributes that *wrap* node_info/isolation_scope context at a higher level; if
  that code lands under ``app/adk/tracking/``, revisit this guard and either
  broaden the scope to a per-file allow-list or tighten to the emitter-only files.

Scanning behaviour:
- Comment-only lines (``stripped.startswith("#")``) are skipped — a deliberate
  reference in a ``# comment`` is documentation, not an emitter call.
- Lines inside triple-quoted string literals (docstrings / multi-line constants)
  are skipped — documentation strings that name the fields should not trigger the
  guard. The scanner tracks opening and closing ``\"\"\"`` / ``'''`` delimiters to
  detect these regions.
- Violation messages truncate each offending line to 120 characters so that a
  temporarily-hardcoded secret in a comment never leaks in full to CI logs.

References:
- AH-PRD-13 §2 ("Tracing: confirm Weave / safe_weave_op spans survive the 2.0
  event shape") + §9 ("Weave autopatch fragility — record, don't block")
- ``app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json`` metadata
  block: "the emitter does not read node_info / isolation_scope"
- AH-113 (this issue) — offline regression component of AH-PRD-13 §7 AC #9
"""

from __future__ import annotations

import re
from pathlib import Path

# Resolve at import time so relative_to() comparisons are stable under symlinks
# and in CI environments where /workspace may be a bind mount.
_TRACKING_ROOT = Path(__file__).resolve().parent.parent

_FORBIDDEN_PATTERNS: tuple[str, ...] = ("node_info", "isolation_scope")

# Maximum characters of a source line to include in a violation message.
# Prevents accidental secret leakage into CI logs via raw-line echo.
_MAX_LINE_EXCERPT = 120


def _production_py_files() -> list[Path]:
    """Return sorted .py files under app/adk/tracking/ excluding tests/ and symlinks."""
    return sorted(
        p.resolve()
        for p in _TRACKING_ROOT.rglob("*.py")
        if not p.is_symlink()
        and "tests" not in p.relative_to(_TRACKING_ROOT).parts
    )


def _in_triple_quote_regions(lines: list[str]) -> list[bool]:
    """Return a bool list: True for each line that is a string-literal line.

    Marks lines that contain a triple-quote delimiter (``\"\"\"`` or ``'''``) as
    string-literal lines — these are docstring boundaries, single-line docstrings,
    or multi-line string continuations.  Lines that follow an unclosed opener are
    also marked True.  This is a best-effort heuristic that handles the common
    docstring / multi-line-string cases without requiring a full AST parse.
    """
    inside = [False] * len(lines)
    in_block = False
    block_delim = ""
    for i, line in enumerate(lines):
        if in_block:
            inside[i] = True
            if block_delim in line:
                in_block = False
                block_delim = ""
        else:
            for delim in ('"""', "'''"):
                if delim in line:
                    # Any line touching a triple-quote is a string-literal line.
                    inside[i] = True
                    count = line.count(delim)
                    if count % 2 == 1:
                        # Odd number of delimiters: block opened, not yet closed.
                        in_block = True
                        block_delim = delim
                    break
    return inside


def test_no_adk2_event_fields_in_production_tracking() -> None:
    """No production tracking module may read node_info or isolation_scope.

    Fails with a clear message naming the offending file and line so the
    contributor understands why the guard exists and where to look.
    """
    violations: list[str] = []
    repo_root = _TRACKING_ROOT.parent.parent.parent

    for py_file in _production_py_files():
        source = py_file.read_text(encoding="utf-8")
        raw_lines = source.splitlines()
        in_string = _in_triple_quote_regions(raw_lines)

        for lineno, (line, is_string_line) in enumerate(
            zip(raw_lines, in_string, strict=True), start=1
        ):
            # Skip comment-only lines and lines inside triple-quoted strings.
            stripped = line.strip()
            if stripped.startswith("#") or is_string_line:
                continue
            for pattern in _FORBIDDEN_PATTERNS:
                if re.search(r"\b" + re.escape(pattern) + r"\b", line):
                    rel_path = py_file.relative_to(repo_root)
                    excerpt = line.rstrip()[:_MAX_LINE_EXCERPT]
                    violations.append(f"  {rel_path}:{lineno}: {excerpt}")

    assert not violations, (
        "Production tracking modules must not read ADK 2.0-only event fields "
        "(node_info, isolation_scope). "
        "See AH-PRD-13 §2 + §9 and the transfer_to_specialist_trace.json metadata block. "
        "If you are adding a legitimate supervisor-orchestration span emitter, revisit the "
        "scope of this guard (see the module docstring for guidance).\n\n"
        "Violations found:\n" + "\n".join(violations)
    )
