"""SK-5 / SK-PRD-00 Q4 — CPU resource limit probe.

Addresses AC #1 (three scripts committed at canonical paths) and feeds the
CPU sub-question in AC #2 (measured limits captured with failure signal).

The script enters a tight busy loop immediately after printing a start marker.
The harness's `executor_stdout_parts` will contain the start marker; the
sandbox enforcer should terminate the process before it can print anything
further. The harness `Elapsed (s)` value records the wall-clock at kill.

Expected harness outcome when limits are enforced:
  Exit status: error: executor outcome OUTCOME_DEADLINE_EXCEEDED
               or error: executor outcome OUTCOME_ERROR
               (exact enum value depends on how Vertex surfaces a CPU kill)
  Elapsed (s): <wall-clock at sandbox termination> — this is the effective
               CPU limit for an all-CPU workload on this sandbox tier.
"""

import sys

print("q4_cpu_loop: start — entering tight busy loop")
sys.stdout.flush()
while True:
    pass
