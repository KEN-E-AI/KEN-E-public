# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for check_p95_threshold.py.

Tests cover:
- PASS: p95 below threshold with zero failures
- FAIL: p95 at or above threshold
- FAIL: non-zero failure count even when p95 is within threshold
- ERROR (exit 2): endpoint label absent from CSV
- Boundary: p95 exactly equal to threshold (must fail — strictly less-than required)
- Custom threshold value
"""

import subprocess
import sys
from pathlib import Path

CSV_HEADER = (
    "Type,Name,Request Count,Failure Count,Median Response Time,"
    "Average Response Time,Min Response Time,Max Response Time,"
    "Average Content Size,Requests/s,Failures/s,"
    "50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%\n"
)

DEFAULT_ENDPOINT = "/api/v1/chat/conversations"

# Resolve script + workspace relative to this test file so the suite works
# both locally and on CI agent VMs (no hardcoded /home/agent/workspace path).
_THIS_DIR = Path(__file__).resolve().parent
SCRIPT_PATH = str(_THIS_DIR / "check_p95_threshold.py")
WORKSPACE = str(_THIS_DIR.parent.parent)  # repo root


def make_csv_row(
    name: str,
    failure_count: int,
    p95: float,
    p90: float = 60.0,
) -> str:
    """Build a minimal valid Locust stats CSV data row.

    Only the Name, Failure Count, and percentile columns are semantically significant
    for the checker; all other fields are filled with plausible placeholder values.
    """
    return (
        f"GET,{name},1000,{failure_count},40,42,10,200,5000,100,0,"
        f"40,43,44,46,{p90},{p95},80,90,95,99,200\n"
    )


def run_checker(
    csv_path: Path,
    endpoint: str = DEFAULT_ENDPOINT,
    threshold_ms: float = 100.0,
    max_failure_ratio: float | None = None,
    percentile: int | None = None,
) -> tuple[int, str, str]:
    """Run check_p95_threshold.py as a subprocess and return (returncode, stdout, stderr)."""
    cmd = [
        sys.executable,
        SCRIPT_PATH,
        str(csv_path),
        "--endpoint",
        endpoint,
        "--threshold-ms",
        str(threshold_ms),
    ]
    if max_failure_ratio is not None:
        cmd.extend(["--max-failure-ratio", str(max_failure_ratio)])
    if percentile is not None:
        cmd.extend(["--percentile", str(percentile)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    return result.returncode, result.stdout, result.stderr


def write_csv(tmp_path: Path, rows: list[str]) -> Path:
    """Write a CSV file with the standard Locust header plus the given data rows."""
    csv_file = tmp_path / "stats.csv"
    csv_file.write_text(CSV_HEADER + "".join(rows), encoding="utf-8")
    return csv_file


class TestCheckP95Threshold:
    def test_pass_low_p95_no_failures(self, tmp_path: Path) -> None:
        """p95=50ms, failure_count=0, threshold=100ms should exit 0."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=50.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, threshold_ms=100.0)
        assert returncode == 0
        assert "[PASS]" in stdout
        assert "p95=50ms" in stdout
        assert "failure_ratio=0.0000" in stdout

    def test_fail_high_p95(self, tmp_path: Path) -> None:
        """p95=150ms, failure_count=0, threshold=100ms should exit 1."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=150.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, threshold_ms=100.0)
        assert returncode == 1
        assert "[FAIL]" in stdout
        assert "p95=150ms" in stdout

    def test_fail_failures_even_when_p95_ok(self, tmp_path: Path) -> None:
        """p95=50ms, failure_count=5, threshold=100ms should exit 1 due to failures."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=5, p95=50.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, threshold_ms=100.0)
        assert returncode == 1
        assert "[FAIL]" in stdout
        # Default max_failure_ratio=0 means any failure_ratio > 0 fails.
        assert "failure_ratio=0.0050" in stdout
        assert "max_failure_ratio=0.0000" in stdout

    def test_pass_failures_within_max_ratio(self, tmp_path: Path) -> None:
        """5 failures out of 1000 (= 0.5 %) with max_failure_ratio=0.01 should exit 0."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=5, p95=50.0)],
        )
        returncode, stdout, _ = run_checker(
            csv_file, threshold_ms=100.0, max_failure_ratio=0.01
        )
        assert returncode == 0
        assert "[PASS]" in stdout
        assert "failure_ratio=0.0050" in stdout

    def test_fail_failures_exceed_max_ratio(self, tmp_path: Path) -> None:
        """20 failures out of 1000 (= 2 %) with max_failure_ratio=0.01 should exit 1."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=20, p95=50.0)],
        )
        returncode, stdout, _ = run_checker(
            csv_file, threshold_ms=100.0, max_failure_ratio=0.01
        )
        assert returncode == 1
        assert "[FAIL]" in stdout
        assert "failure_ratio=0.0200" in stdout
        assert "max_failure_ratio=0.0100" in stdout

    def test_error_endpoint_not_found(self, tmp_path: Path) -> None:
        """Endpoint not present in CSV should exit 2."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row("/api/v1/other/endpoint", failure_count=0, p95=50.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, endpoint=DEFAULT_ENDPOINT)
        assert returncode == 2
        assert "[ERROR]" in stdout
        assert DEFAULT_ENDPOINT in stdout

    def test_fail_p95_exactly_at_threshold(self, tmp_path: Path) -> None:
        """p95 equal to threshold should exit 1 (strictly less-than required)."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=100.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, threshold_ms=100.0)
        assert returncode == 1
        assert "[FAIL]" in stdout
        assert "p95=100ms" in stdout

    def test_custom_threshold(self, tmp_path: Path) -> None:
        """p95=80ms, threshold=90ms should exit 0."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=80.0)],
        )
        returncode, stdout, _ = run_checker(csv_file, threshold_ms=90.0)
        assert returncode == 0
        assert "[PASS]" in stdout
        assert "p95=80ms" in stdout
        assert "90ms threshold" in stdout

    def test_percentile_90_passes_when_p90_below_threshold_even_if_p95_above(
        self, tmp_path: Path
    ) -> None:
        """--percentile 90 gates on p90 only; a runaway p95 (cold-start tail) is
        ignored.  Staging gate uses this to avoid noisy failures from Cloud Run
        scale-up at high VU counts."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=77000.0, p90=5400.0)],
        )
        returncode, stdout, _ = run_checker(
            csv_file, threshold_ms=15000.0, percentile=90
        )
        assert returncode == 0
        assert "[PASS]" in stdout
        assert "p90=5400ms" in stdout
        # The p95 value is never read or surfaced when --percentile 90 is used.
        assert "p95" not in stdout

    def test_percentile_90_fails_when_p90_above_threshold(self, tmp_path: Path) -> None:
        """--percentile 90 with p90=16000ms vs threshold 15000ms should exit 1."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=20000.0, p90=16000.0)],
        )
        returncode, stdout, _ = run_checker(
            csv_file, threshold_ms=15000.0, percentile=90
        )
        assert returncode == 1
        assert "[FAIL]" in stdout
        assert "p90=16000ms" in stdout

    def test_unsupported_percentile_rejected(self, tmp_path: Path) -> None:
        """--percentile 75 is supported; --percentile 73 is not (argparse choices)."""
        csv_file = write_csv(
            tmp_path,
            [make_csv_row(DEFAULT_ENDPOINT, failure_count=0, p95=50.0)],
        )
        returncode, _, stderr = run_checker(csv_file, threshold_ms=100.0, percentile=73)
        assert returncode == 2
        assert "invalid choice" in stderr or "argument --percentile" in stderr
