"""SK-PRD-00 Q2 — in-sandbox workload script for cost-per-session measurement.

Invoked by the spike harness via:
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/q2_cost_per_session.py \\
        --project ken-e-dev \\
        --sandbox-resource-name <engine or sandbox resource name>

Runs three synthetic "tool call" stand-ins followed by a ~10s sleep, then
emits a single-line JSON record to stdout with per-step elapsed times and
peak RSS. The harness captures this as the session's stdout output.

Exit: 0 on success.

Can also be run standalone (without the harness) for structural verification:
    uv run python scripts/spike/skills/q2_cost_per_session.py
"""

from __future__ import annotations

import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _step_compute() -> float:
    """Deterministic float-math to exercise in-sandbox CPU."""
    t0 = time.perf_counter()
    result = sum(i * 1.23456789 for i in range(10_000))
    elapsed_ms = (time.perf_counter() - t0) * 1_000
    # consume result so the compiler can't optimize it away
    assert result > 0
    return elapsed_ms


def _step_file_io() -> float:
    """Write + read a 1 KB temp file to exercise in-sandbox file I/O."""
    t0 = time.perf_counter()
    payload = b"x" * 1_024
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "q2_blob.bin"
        p.write_bytes(payload)
        read_back = p.read_bytes()
    elapsed_ms = (time.perf_counter() - t0) * 1_000
    assert read_back == payload, "file-io round-trip mismatch"
    return elapsed_ms


def _step_subprocess() -> tuple[float, str]:
    """Spawn /bin/echo with a JSON payload to exercise subprocess overhead."""
    t0 = time.perf_counter()
    result = subprocess.run(
        ["/bin/echo", '{"tool": "stub", "result": "ok"}'],
        capture_output=True,
        text=True,
        check=True,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1_000
    output = result.stdout.strip()
    return elapsed_ms, output


def _step_sleep() -> float:
    """Sleep ~10s to simulate a long-running script invocation."""
    t0 = time.perf_counter()
    time.sleep(10)
    return (time.perf_counter() - t0) * 1_000


def main() -> None:
    compute_ms = _step_compute()
    file_io_ms = _step_file_io()
    subprocess_ms, subprocess_output = _step_subprocess()
    sleep_ms = _step_sleep()

    # Peak RSS after all steps (in KB on Linux, bytes on macOS — normalise to KB)
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    rss_raw = rusage.ru_maxrss
    rss_kb = rss_raw if sys.platform != "darwin" else rss_raw // 1_024

    record = {
        "steps": {
            "compute": {"elapsed_ms": round(compute_ms, 2)},
            "file_io": {"elapsed_ms": round(file_io_ms, 2)},
            "subprocess": {
                "elapsed_ms": round(subprocess_ms, 2),
                "output": subprocess_output,
            },
            "sleep": {"elapsed_ms": round(sleep_ms, 2)},
        },
        "rss_kb": rss_kb,
        "total_elapsed_ms": round(
            compute_ms + file_io_ms + subprocess_ms + sleep_ms, 2
        ),
    }
    print(json.dumps(record))


if __name__ == "__main__":
    main()
