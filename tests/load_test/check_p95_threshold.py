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

"""Parse a Locust _stats.csv file and validate that the p95 latency is below a threshold.

Usage:
    python check_p95_threshold.py <csv_path> [--threshold-ms THRESHOLD] [--endpoint ENDPOINT]
                                              [--max-failure-ratio RATIO]

Arguments:
    csv_path             Path to the Locust stats CSV file (positional, required)
    --threshold-ms       p95 latency threshold in milliseconds (default: 100)
    --endpoint           Endpoint label to look up in the CSV (default: /api/v1/chat/conversations)
    --max-failure-ratio  Maximum tolerated failure ratio in [0, 1] (default: 0 — any
                         failure fails the gate).  Set to 0.01 in staging to tolerate
                         transient infra blips (gateway 502s during Cloud Run scale-up,
                         etc.) without masking real regressions — a ratio > 1 % still
                         fails.

Exit codes:
    0  p95 < threshold AND failure_ratio <= max_failure_ratio
    1  p95 >= threshold OR failure_ratio > max_failure_ratio
    2  Usage error: endpoint not found in CSV, file not found, or malformed CSV

Example:
    python check_p95_threshold.py .results/stats.csv --threshold-ms 200 --endpoint /api/v1/chat/conversations
"""

import argparse
import csv
import sys


def main() -> None:
    """Entry point: parse args, read CSV, validate p95 threshold, and exit with appropriate code."""
    parser = argparse.ArgumentParser(
        description="Validate p95 latency from a Locust stats CSV against a threshold."
    )
    parser.add_argument(
        "csv_path",
        help="Path to the Locust _stats.csv file",
    )
    parser.add_argument(
        "--threshold-ms",
        type=float,
        default=100.0,
        dest="threshold_ms",
        help="p95 latency threshold in milliseconds (default: 100)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/api/v1/chat/conversations",
        help="Endpoint label to look up in the CSV (default: /api/v1/chat/conversations)",
    )
    parser.add_argument(
        "--max-failure-ratio",
        type=float,
        default=0.0,
        dest="max_failure_ratio",
        help=(
            "Maximum tolerated failure ratio in [0, 1].  Default 0 = any failure fails "
            "the gate (prod-strict).  Set to e.g. 0.01 in staging to tolerate transient "
            "infra blips (Cloud Run scale-up 502s) without masking real regressions."
        ),
    )
    args = parser.parse_args()

    csv_path: str = args.csv_path
    threshold_ms: float = args.threshold_ms
    endpoint: str = args.endpoint
    max_failure_ratio: float = args.max_failure_ratio

    if not 0.0 <= max_failure_ratio <= 1.0:
        print(f"[ERROR] --max-failure-ratio must be in [0, 1], got {max_failure_ratio}")
        sys.exit(2)

    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"[ERROR] CSV file not found: {csv_path}")
        sys.exit(2)
    except (OSError, csv.Error) as exc:
        print(f"[ERROR] Failed to read CSV file '{csv_path}': {exc}")
        sys.exit(2)

    matching_row: dict[str, str] | None = None
    for row in rows:
        if row.get("Name") == endpoint:
            matching_row = row
            break

    if matching_row is None:
        print(f"[ERROR] Endpoint '{endpoint}' not found in CSV: {csv_path}")
        sys.exit(2)

    try:
        p95 = float(matching_row["95%"])
        failure_count = int(matching_row["Failure Count"])
        request_count = int(matching_row["Request Count"])
    except (KeyError, ValueError) as exc:
        print(f"[ERROR] Malformed CSV row for endpoint '{endpoint}': {exc}")
        sys.exit(2)

    # Avoid ZeroDivisionError: a run with 0 requests is a separate, more serious
    # failure mode (auth never resolved, target down, etc.) — surface it explicitly.
    if request_count == 0:
        print(f"[FAIL] {endpoint}: 0 requests recorded — load test did not exercise the endpoint")
        sys.exit(1)

    failure_ratio = failure_count / request_count

    if failure_ratio > max_failure_ratio:
        print(
            f"[FAIL] {endpoint}: failure_ratio={failure_ratio:.4f} "
            f"({failure_count}/{request_count}) > max_failure_ratio={max_failure_ratio:.4f}"
            f" (p95={p95:.0f}ms)"
        )
        sys.exit(1)

    if p95 >= threshold_ms:
        print(
            f"[FAIL] {endpoint}: p95={p95:.0f}ms >= {threshold_ms:.0f}ms threshold"
            f" (failure_ratio={failure_ratio:.4f} within tolerance)"
        )
        sys.exit(1)

    print(
        f"[PASS] {endpoint}: p95={p95:.0f}ms < {threshold_ms:.0f}ms threshold,"
        f" failure_ratio={failure_ratio:.4f} ({failure_count}/{request_count})"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
