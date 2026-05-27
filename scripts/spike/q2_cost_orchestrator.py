"""SK-PRD-00 Q2 — orchestrator for cost-per-session measurement.

Drives N sessions against the dedicated spike Agent Engine, interleaving cold
(fresh sandbox resource) and warm (reused sandbox resource) cohorts per block
of 10.  Writes one JSON line per session to --out and prints summary stats.

Usage:
    uv run python scripts/spike/q2_cost_orchestrator.py \\
        --n 30 \\
        --cohorts cold,warm \\
        --out scripts/spike/skills/q2_sessions.jsonl

Dry-run smoke test (n=3, both cohorts, requires Vertex AI access):
    uv run python scripts/spike/q2_cost_orchestrator.py --n 3 --cohorts cold,warm

Environment variables required:
    GOOGLE_CLOUD_PROJECT                  GCP project id (e.g. ken-e-dev)
    VERTEX_AI_LOCATION                    e.g. us-central1
    KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME Engine resource name:
      projects/<proj>/locations/<loc>/reasoningEngines/<id>
      Used as the base for cold sessions (orchestrator appends a cohort counter
      to create distinct sandbox contexts per cold session).
      Falls back to KENE_SPIKE_SANDBOX_RESOURCE_NAME for backward compat.

Session record schema (one JSON line per session):
    {
      "session_id":            str,           # "cold_b0s0" or "warm_b0s0"
      "cohort":                "cold"|"warm",
      "block":                 int,           # 0-indexed block of 10
      "block_session":         int,           # 0-indexed position within the block
      "sandbox_resource_name": str,
      "session_start_iso":     str,           # UTC ISO 8601
      "session_end_iso":       str,           # UTC ISO 8601
      "elapsed_orchestrator_ms": float,       # wall-clock from orchestrator side
      "elapsed_harness_ms":    float | null,  # parsed from harness "Elapsed (s)" line
      "exit_status":           str,           # "ok" or "error: ..."
      "in_sandbox_record":     dict | null,   # parsed JSON from harness stdout
      "raw_stdout":            str            # full harness stdout for debugging
    }
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

_WORKLOAD_SCRIPT = Path(__file__).parent / "skills" / "q2_cost_per_session.py"
_HARNESS_SCRIPT = Path(__file__).parent / "sandbox_test_harness.py"

# Per-block sizes (5 cold + 5 warm = 10 sessions per block)
_BLOCK_COLD = 5
_BLOCK_WARM = 5
_BLOCK_SIZE = _BLOCK_COLD + _BLOCK_WARM

# Regex to extract the float from "Elapsed (s)  : 11.43"
_ELAPSED_RE = re.compile(r"Elapsed \(s\)\s*:\s*([\d.]+)")
# Regex to extract exit status from "Exit status  : ok"
_STATUS_RE = re.compile(r"Exit status\s*:\s*(.+)")


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _run_one_session(
    sandbox_resource_name: str,
    project: str,
    location: str,
    session_id: str,
) -> dict:
    """Invoke the harness for one session; return a partial session record."""
    cmd = [
        "uv",
        "run",
        "python",
        str(_HARNESS_SCRIPT),
        "--script",
        str(_WORKLOAD_SCRIPT),
        "--project",
        project,
        "--location",
        location,
        "--sandbox-resource-name",
        sandbox_resource_name,
    ]

    session_start = _utcnow()
    t0 = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min hard timeout per session
        )
        raw_stdout = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        # Kill the child so it doesn't keep the Vertex AI session (and billing)
        # running beyond the 300s budget — the process is still alive on TimeoutExpired.
        if exc.process is not None:
            exc.process.kill()
            exc.process.communicate()
        elapsed_ms = (time.perf_counter() - t0) * 1_000
        return {
            "session_start_iso": session_start,
            "session_end_iso": _utcnow(),
            "elapsed_orchestrator_ms": round(elapsed_ms, 2),
            "elapsed_harness_ms": None,
            "exit_status": "error: session timeout (300s)",
            "in_sandbox_record": None,
            "raw_stdout": f"<timeout after 300s for {session_id}>",
        }

    elapsed_ms = (time.perf_counter() - t0) * 1_000
    session_end = _utcnow()

    # Parse harness elapsed time
    elapsed_harness_ms: float | None = None
    m = _ELAPSED_RE.search(raw_stdout)
    if m:
        elapsed_harness_ms = float(m.group(1)) * 1_000

    # Parse harness exit status
    exit_status = "error: no exit status line found"
    m = _STATUS_RE.search(raw_stdout)
    if m:
        exit_status = m.group(1).strip()

    # Parse in-sandbox JSON record (first valid JSON line before the "---" separator)
    in_sandbox_record: dict | None = None
    for line in raw_stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                in_sandbox_record = json.loads(line)
                break
            except json.JSONDecodeError:
                pass

    return {
        "session_start_iso": session_start,
        "session_end_iso": session_end,
        "elapsed_orchestrator_ms": round(elapsed_ms, 2),
        "elapsed_harness_ms": round(elapsed_harness_ms, 2)
        if elapsed_harness_ms is not None
        else None,
        "exit_status": exit_status,
        "in_sandbox_record": in_sandbox_record,
        "raw_stdout": raw_stdout,
    }


def _pct(values: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of values using the nearest-rank method."""
    if not values:
        return float("nan")
    sorted_v = sorted(values)
    # nearest-rank: ceil(p/100 * n), 1-based → converted to 0-based
    idx = min(len(sorted_v) - 1, max(0, math.ceil(p / 100 * len(sorted_v)) - 1))
    return sorted_v[idx]


def _print_summary(records: list[dict]) -> None:
    by_cohort: dict[str, list[dict]] = {}
    for r in records:
        by_cohort.setdefault(r["cohort"], []).append(r)

    print("\n=== Q2 Cost Orchestrator — Run Summary ===")
    for cohort, cohort_records in sorted(by_cohort.items()):
        n = len(cohort_records)
        ok = sum(1 for r in cohort_records if r["exit_status"] == "ok")
        elapsed_values = [
            r["elapsed_orchestrator_ms"]
            for r in cohort_records
            if r["exit_status"] == "ok"
        ]
        p50 = _pct(elapsed_values, 50)
        p95 = _pct(elapsed_values, 95)
        mean = statistics.mean(elapsed_values) if elapsed_values else float("nan")
        print(
            f"  Cohort: {cohort:5s}  n={n}  ok={ok}  "
            f"p50={p50 / 1000:.2f}s  p95={p95 / 1000:.2f}s  mean={mean / 1000:.2f}s"
        )
    print(f"  Total sessions: {len(records)}")
    print()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="q2_cost_orchestrator",
        description=(
            "SK-PRD-00 Q2 cost-per-session orchestrator. "
            "Runs N sessions against the dedicated spike Agent Engine, "
            "interleaving cold and warm cohorts."
        ),
    )
    parser.add_argument(
        "--n",
        type=int,
        default=30,
        metavar="INT",
        help="Total number of sessions per cohort pair (default 30; bump to 60 if variance > 20%%).",
    )
    parser.add_argument(
        "--cohorts",
        default="cold,warm",
        metavar="LIST",
        help="Comma-separated cohort names to include (default: cold,warm).",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent / "skills" / "q2_sessions.jsonl"),
        metavar="PATH",
        help="Output path for JSONL session records.",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        metavar="PROJECT_ID",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
        metavar="REGION",
    )
    parser.add_argument(
        "--engine-resource-name",
        default=(
            (os.environ.get("KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME") or "").strip()
            or (os.environ.get("KENE_SPIKE_SANDBOX_RESOURCE_NAME") or "").strip()
        ),
        metavar="RESOURCE",
        help=(
            "Agent Engine resource name (reasoningEngines/<id>). "
            "Defaults to $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.project:
        sys.exit(
            "[q2-orchestrator] GCP project id required. "
            "Set $GOOGLE_CLOUD_PROJECT or pass --project."
        )
    if not args.engine_resource_name:
        sys.exit(
            "[q2-orchestrator] Engine resource name required. "
            "Set $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME or pass --engine-resource-name."
        )

    cohorts = [c.strip() for c in args.cohorts.split(",") if c.strip()]
    if not cohorts:
        sys.exit("[q2-orchestrator] --cohorts must name at least one cohort.")

    n = args.n
    # Safety cap: the plan budgets ≤240 sessions to leave quota for sibling spikes.
    _MAX_N = 240
    if n > _MAX_N:
        sys.exit(
            f"[q2-orchestrator] --n {n} exceeds the spike budget cap ({_MAX_N}). "
            "Edit _MAX_N in the source if this is intentional."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        sys.exit(
            f"[q2-orchestrator] Output file already exists: {out_path}\n"
            "Pass --out <new-path> or delete the existing file to avoid overwriting prior data."
        )

    # Build the session schedule: interleave cold + warm in blocks of 10.
    #
    # Cold/warm definition for this spike:
    #   - Cold session: first session in a block. ADK lazily creates (or allocates)
    #     a sandboxEnvironment under the engine on first call. Incurs Vertex-side
    #     container startup latency.
    #   - Warm session: follows immediately after a cold session in the same block,
    #     using the SAME engine resource name. The ADK singleton SandboxPool
    #     (SK-PRD-02 §4.6) reuses the same sandboxEnvironment within a process;
    #     here, where each harness call is a fresh process, "warmth" is Vertex-backend
    #     warmth — the existing container may be reused if it is still alive.
    #
    # Limitation: The SK-1 harness is single-shot (one sandboxEnvironment per process).
    # It does not expose the resolved sandboxEnvironments/<id> created by
    # agent_engine_resource_name=, so the orchestrator cannot pass the exact same
    # sandboxEnvironment path to subsequent warm sessions via sandbox_resource_name=.
    # Both cohorts therefore pass the same engine resource name; the Vertex backend
    # decides whether to reuse the underlying container. This measures infrastructure-
    # level warmth rather than SDK-object-level warmth. Note this in the findings.
    schedule: list[dict] = []
    sessions_per_block = max(1, _BLOCK_COLD)  # 5 cold then 5 warm per block
    n_blocks = max(1, (n + sessions_per_block - 1) // sessions_per_block)

    for block_idx in range(n_blocks):
        for s in range(sessions_per_block):
            unique_tag = f"b{block_idx}s{s}"
            if "cold" in cohorts:
                schedule.append(
                    {
                        "session_id": f"cold_{unique_tag}",
                        "cohort": "cold",
                        "block": block_idx,
                        "block_session": s,
                        "sandbox_resource_name": args.engine_resource_name,
                    }
                )
        for s in range(sessions_per_block):
            unique_tag = f"b{block_idx}s{s}"
            if "warm" in cohorts:
                schedule.append(
                    {
                        "session_id": f"warm_{unique_tag}",
                        "cohort": "warm",
                        "block": block_idx,
                        "block_session": s,
                        # Same engine resource name; Vertex backend decides container reuse.
                        "sandbox_resource_name": args.engine_resource_name,
                    }
                )

    print(
        f"[q2-orchestrator] Starting {len(schedule)} sessions "
        f"(n={n}, cohorts={cohorts}, blocks={n_blocks})"
    )
    print(f"[q2-orchestrator] Engine: {args.engine_resource_name}")
    print(f"[q2-orchestrator] Output: {out_path}")

    records: list[dict] = []
    with out_path.open("a", encoding="utf-8") as fh:
        for i, item in enumerate(schedule, start=1):
            print(
                f"  [{i:3d}/{len(schedule)}] {item['session_id']}  "
                f"cohort={item['cohort']}  "
                f"sandbox={item['sandbox_resource_name'][-40:]}"
            )
            partial = _run_one_session(
                sandbox_resource_name=item["sandbox_resource_name"],
                project=args.project,
                location=args.location,
                session_id=item["session_id"],
            )
            record = {**item, **partial}
            records.append(record)
            fh.write(json.dumps(record) + "\n")
            fh.flush()

            status_indicator = "✓" if partial["exit_status"] == "ok" else "✗"
            print(
                f"         {status_indicator} status={partial['exit_status']}  "
                f"elapsed={partial['elapsed_orchestrator_ms'] / 1000:.2f}s"
            )

    _print_summary(records)
    print(f"[q2-orchestrator] JSONL written to {out_path}")

    error_count = sum(1 for r in records if r["exit_status"] != "ok")
    if error_count > len(records) * 0.05:
        sys.exit(
            f"[q2-orchestrator] Error rate {error_count}/{len(records)} exceeds 5% threshold."
        )


if __name__ == "__main__":
    main()
