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

"""Parse a Locust _stats.csv file and validate that a percentile latency is below a threshold.

Despite the historical filename, this script gates against any of Locust's reported
percentile columns (50, 66, 75, 80, 90, 95, 98, 99).  Default percentile is 95 for
backward compatibility; pass --percentile 90 for the staging gate, which is much
more stable across runs than p95 because it sits below the Cloud Run cold-start tail
that dominates p95 at high VU counts with min_instances=0.

Usage:
    python check_p95_threshold.py <csv_path>
        [--threshold-ms THRESHOLD] [--endpoint ENDPOINT]
        [--max-failure-ratio RATIO] [--percentile P]

Arguments:
    csv_path             Path to the Locust stats CSV file (positional, required)
    --threshold-ms       Latency threshold in milliseconds (default: 100)
    --endpoint           Endpoint label to look up in the CSV (default: /api/v1/chat/conversations)
    --max-failure-ratio  Maximum tolerated failure ratio in [0, 1] (default: 0 — any
                         failure fails the gate).  Set to 0.01 in staging to tolerate
                         transient infra blips (gateway 502s during Cloud Run scale-up,
                         etc.) without masking real regressions — a ratio > 1 % still
                         fails.
    --percentile         Latency percentile to gate on; one of 50, 66, 75, 80, 90, 95,
                         98, 99 (default: 95).  Use a lower percentile (e.g. 90) when
                         min_instances=0 makes the upper tail dominated by cold-start
                         noise rather than steady-state performance.

Exit codes:
    0  percentile_value < threshold AND failure_ratio <= max_failure_ratio
    1  percentile_value >= threshold OR failure_ratio > max_failure_ratio
    2  Usage error: endpoint not found in CSV, file not found, or malformed CSV

Example:
    python check_p95_threshold.py .results/stats.csv --percentile 90 --threshold-ms 15000
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
    parser.add_argument(
        "--percentile",
        type=int,
        default=95,
        choices=[50, 66, 75, 80, 90, 95, 98, 99],
        help=(
            "Latency percentile to gate on (Locust columns are 50/66/75/80/90/95/98/99). "
            "Default 95 for backward compatibility.  Use 90 in staging where the upper "
            "tail is dominated by Cloud Run cold-start noise (min_instances=0) rather "
            "than steady-state performance."
        ),
    )
    args = parser.parse_args()

    csv_path: str = args.csv_path
    threshold_ms: float = args.threshold_ms
    endpoint: str = args.endpoint
    max_failure_ratio: float = args.max_failure_ratio
    percentile: int = args.percentile
    percentile_col = f"{percentile}%"

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
        latency = float(matching_row[percentile_col])
        failure_count = int(matching_row["Failure Count"])
        request_count = int(matching_row["Request Count"])
    except (KeyError, ValueError) as exc:
        print(f"[ERROR] Malformed CSV row for endpoint '{endpoint}': {exc}")
        sys.exit(2)

    # Avoid ZeroDivisionError: a run with 0 requests is a separate, more serious
    # failure mode (auth never resolved, target down, etc.) — surface it explicitly.
    if request_count == 0:
        print(
            f"[FAIL] {endpoint}: 0 requests recorded — load test did not exercise the endpoint"
        )
        sys.exit(1)

    failure_ratio = failure_count / request_count
    pname = f"p{percentile}"

    if failure_ratio > max_failure_ratio:
        print(
            f"[FAIL] {endpoint}: failure_ratio={failure_ratio:.4f} "
            f"({failure_count}/{request_count}) > max_failure_ratio={max_failure_ratio:.4f}"
            f" ({pname}={latency:.0f}ms)"
        )
        sys.exit(1)

    if latency >= threshold_ms:
        print(
            f"[FAIL] {endpoint}: {pname}={latency:.0f}ms >= {threshold_ms:.0f}ms threshold"
            f" (failure_ratio={failure_ratio:.4f} within tolerance)"
        )
        sys.exit(1)

    print(
        f"[PASS] {endpoint}: {pname}={latency:.0f}ms < {threshold_ms:.0f}ms threshold,"
        f" failure_ratio={failure_ratio:.4f} ({failure_count}/{request_count})"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
