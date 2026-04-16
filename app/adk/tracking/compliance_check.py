"""CLI for running trace compliance validation against fixture files.

Usage::

    uv run python -m app.adk.tracking.compliance_check \\
        --fixtures app/adk/tracking/tests/fixtures/

The CLI loads every ``*.json`` file from the fixtures directory, validates
each trace's ``metadata`` dict via :func:`validate_trace_compliance`, prints
a summary, and exits with status 1 if any trace is non-compliant.

Fixture format::

    {
      "trace_id": "<identifier>",
      "description": "<optional>",
      "metadata": { ... flat trace metadata dict ... }
    }

This is the CI gate for AC-6 ("non-compliant traces fail the build") — the
fixtures represent canonical compliant traces for each agent type (AC-5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.adk.tracking.compliance import (
    generate_compliance_report,
    validate_trace_compliance,
)


def _load_fixture(path: Path) -> tuple[str, dict]:
    """Load a fixture file and return (trace_id, metadata)."""
    data = json.loads(path.read_text())
    if "metadata" not in data:
        raise ValueError(f"{path}: fixture missing 'metadata' key")
    trace_id = data.get("trace_id", path.stem)
    return trace_id, data["metadata"]


def _print_result(
    path: Path, trace_id: str, result_is_compliant: bool, failures: list, warnings: list
) -> None:
    status = "PASS" if result_is_compliant else "FAIL"
    print(f"  [{status}] {path.name} ({trace_id})")
    for issue in failures:
        print(f"    ✗ {issue.field}: {issue.message}")
    for warning in warnings:
        print(f"    ! {warning.field}: {warning.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate KEN-E trace fixtures against the compliance spec.",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        required=True,
        help="Directory containing fixture JSON files",
    )
    args = parser.parse_args(argv)

    fixture_dir: Path = args.fixtures
    if not fixture_dir.is_dir():
        print(f"error: {fixture_dir} is not a directory", file=sys.stderr)
        return 2

    fixture_paths = sorted(fixture_dir.glob("*.json"))
    if not fixture_paths:
        print(f"error: no *.json fixtures found in {fixture_dir}", file=sys.stderr)
        return 2

    print(f"Validating {len(fixture_paths)} fixture(s) in {fixture_dir}:")
    all_metadata: list[dict] = []
    all_trace_ids: list[str | None] = []
    any_failed = False

    for path in fixture_paths:
        trace_id, metadata = _load_fixture(path)
        result = validate_trace_compliance(metadata, trace_id=trace_id)
        _print_result(path, trace_id, result.is_compliant, result.issues, result.warnings)
        all_metadata.append(metadata)
        all_trace_ids.append(trace_id)
        if not result.is_compliant:
            any_failed = True

    report = generate_compliance_report(all_metadata, all_trace_ids)
    print(
        f"\nCompliance: {report.compliant_traces}/{report.total_traces} "
        f"({report.compliance_percentage:.1f}%)"
    )
    if report.common_issues:
        print("Most common issues:")
        for issue, count in report.common_issues:
            print(f"  - {issue} ({count}x)")

    if any_failed:
        print("\n❌ One or more fixtures failed compliance validation", file=sys.stderr)
        return 1

    print("\n✅ All fixtures compliant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
