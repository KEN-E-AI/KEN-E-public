"""SK-43 — Latency-measurement script for vertexai.Client construction.

Measures the per-call construction latency of ``vertexai.Client(project, location)``
over 100 iterations and reports mean / p95 / max.  Reads ``GOOGLE_CLOUD_PROJECT_ID``
and ``VERTEX_AI_LOCATION`` env vars (same defaults as ``SandboxPool._sandbox_resource_name``).

Optionally compares uncached vs. cached construction so the before/after latency
profile for SK-43 can be captured in one run (``--cached`` flag).

Usage
-----
    # Standard run (100 uncached constructions):
    uv run python scripts/skills/measure_vertexai_client_init.py

    # Compare uncached vs cached:
    uv run python scripts/skills/measure_vertexai_client_init.py --cached

    # Custom iteration count:
    uv run python scripts/skills/measure_vertexai_client_init.py --n 200

    # Dry-run (no network calls — just prints the table template):
    uv run python scripts/skills/measure_vertexai_client_init.py --dry-run

The output is formatted as a copy-pasteable Markdown table ready for posting as
a comment on Linear SK-43 (AC-3 satisfaction).

AC-3 note
---------
This script requires valid Application Default Credentials (ADC) or a service
account key.  The Dev Team VM lacks GCP credentials, so AC-3 is satisfied by
a PO or Test Team member with ADC running this script and posting the table to
SK-43.  See the Decisions & Assumptions section of the SK-43 implementation plan.
"""

from __future__ import annotations

import argparse
import functools
import os
import statistics
import time


def _measure_uncached(project: str, location: str, n: int) -> list[float]:
    """Construct vertexai.Client n times without caching; return latencies in ms."""
    import vertexai

    latencies: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        vertexai.Client(project=project, location=location)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def _measure_cached(project: str, location: str, n: int) -> list[float]:
    """Construct vertexai.Client via lru_cache n times; return latencies in ms.

    The first call pays the construction cost; subsequent calls are pure
    Python dict lookups.
    """
    @functools.lru_cache(maxsize=1)
    def _cached_client(proj: str, loc: str) -> object:
        import vertexai
        return vertexai.Client(project=proj, location=loc)

    latencies: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        _cached_client(project, location)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def _format_table(label: str, latencies: list[float]) -> str:
    """Format a summary row for the results table."""
    mean = statistics.mean(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    maximum = max(latencies)
    return f"| {label} | {mean:.2f} ms | {p95:.2f} ms | {maximum:.2f} ms |"


def _dry_run() -> None:
    print("## SK-43 — vertexai.Client init latency (dry-run)\n")
    print("| Mode | Mean | p95 | Max |")
    print("|------|------|-----|-----|")
    print("| Uncached (100 calls) | _pending_ | _pending_ | _pending_ |")
    print("| Cached (100 calls) | _pending_ | _pending_ | _pending_ |")
    print("\n_Run without --dry-run on a credentialled workstation to capture real numbers._")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure vertexai.Client construction latency (SK-43 AC-3)."
    )
    parser.add_argument(
        "--n",
        type=int,
        default=100,
        help="Number of construction iterations (default: 100)",
    )
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Also measure cached (lru_cache) construction for before/after comparison",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the table template without making any network calls",
    )
    args = parser.parse_args()

    if args.dry_run:
        _dry_run()
        return

    if args.n < 20:
        parser.error("--n must be >= 20: statistics.quantiles requires at least 20 data points to compute p95")

    project = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

    print(f"Project: {project}, Location: {location}, Iterations: {args.n}\n")

    print("## SK-43 — vertexai.Client init latency\n")
    print("| Mode | Mean | p95 | Max |")
    print("|------|------|-----|-----|")

    uncached = _measure_uncached(project, location, args.n)
    print(_format_table(f"Uncached ({args.n} calls)", uncached))

    if args.cached:
        cached = _measure_cached(project, location, args.n)
        print(_format_table(f"Cached ({args.n} calls)", cached))
        first_call = cached[0]
        rest_mean = statistics.mean(cached[1:]) if len(cached) > 1 else 0.0
        print(
            f"\nCached breakdown: first call (construction) = {first_call:.2f} ms; "
            f"subsequent calls (cache lookup) mean = {rest_mean:.4f} ms"
        )

    print(
        "\n_Post this table as a comment on Linear SK-43 to satisfy AC-3._"
    )


if __name__ == "__main__":
    main()
