"""SK-5 / SK-PRD-00 Q4 — Wall-clock resource limit probe.

Addresses AC #1 (three scripts committed at canonical paths) and feeds the
wall-clock sub-question in AC #2 (measured limits captured with failure signal).

Tests both idle-sleep and compute-bound durations at three breakpoints:
30 s / 120 s / 600 s. Sandbox runtimes may cap wall-clock differently for
idle-sleep vs CPU-burning compute; running both in the same script surfaces
the difference if present (SK-5 Architecture Decision).

Probes are cumulative within one invocation so a single harness call finds the
threshold without needing three separate sandbox sessions (saves quota).

Compute-bound probes run first so a wall-clock cap shorter than the 750 s
idle-sleep sequence does not prevent them from running. The compute path uses
a monotonic spin loop rather than a counted inner loop so the measurement is
independent of CPython arithmetic speed on the sandbox CPU tier.

The bracketing time.monotonic() prints around every probe let the harness
output show exactly which probe was last completed before sandbox termination.
The harness `Elapsed (s)` value cross-validates the script-side deltas.

If the script completes all probes without being killed, it prints a final
"all probes completed" line -- meaning no wall-clock cap was observed in the
0-600 s band. That outcome is itself a finding: document it and flag for SK-8.
"""

import sys
import time


def probe(label: str, target_seconds: float, *, compute: bool) -> None:
    t_start = time.monotonic()
    print(f"q4_wall_clock: {label} — start (target {target_seconds:.0f}s)")
    sys.stdout.flush()

    if compute:
        # Spin for exactly target_seconds of wall-clock so the measurement
        # is independent of CPython arithmetic speed on the sandbox tier.
        deadline = time.monotonic() + target_seconds
        while time.monotonic() < deadline:
            pass
    else:
        time.sleep(target_seconds)

    elapsed = time.monotonic() - t_start
    print(f"q4_wall_clock: {label} — done ({elapsed:.1f}s elapsed)")
    sys.stdout.flush()


# --- Compute-bound probes first so a wall-clock cap < 750 s does not prevent
#     them from running (idle-sleep sequence alone would take 750 s). ---
probe("compute-30s", 30, compute=True)
probe("compute-120s", 120, compute=True)
probe("compute-600s", 600, compute=True)

# --- Idle-sleep probes ---
probe("idle-sleep-30s", 30, compute=False)
probe("idle-sleep-120s", 120, compute=False)
probe("idle-sleep-600s", 600, compute=False)

print("q4_wall_clock: all probes completed -- no wall-clock cap observed in 0-600s band")
