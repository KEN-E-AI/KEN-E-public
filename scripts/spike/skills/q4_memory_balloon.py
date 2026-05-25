"""SK-5 / SK-PRD-00 Q4 — Memory resource limit probe.

Addresses AC #1 (three scripts committed at canonical paths) and feeds the
memory sub-question in AC #2 (measured limits captured with failure signal).

Allocates memory using `bytearray(N)` with N doubling each iteration starting
at 1 MiB. Uses `bytearray` rather than `[0]*N` because bytearray yields an
exact byte count (SK-5 Architecture Decision: bytes-precise for SandboxPool
tuning), whereas a list of ints confounds object overhead with payload size.

The last successfully printed cumulative-MiB line is the peak before kill.
Two failure modes are distinguished:
  - Hard OOM kill: sandbox kills the process; MemoryError sentinel NOT printed.
  - Python MemoryError: Python raises before kernel OOM; sentinel IS printed.
SK-PRD-02 SandboxPool tuning only needs the peak MiB, not the failure mode.
"""

import sys

cumulative_bytes = 0
chunk_bytes = 1 * 1024 * 1024  # start at 1 MiB
allocations: list[bytearray] = []

while True:
    try:
        allocations.append(bytearray(chunk_bytes))
        cumulative_bytes += chunk_bytes
        cumulative_mib = cumulative_bytes / (1024 * 1024)
        print(f"q4_memory_balloon: allocated {cumulative_mib:.0f} MiB total")
        sys.stdout.flush()
        chunk_bytes *= 2
    except MemoryError:
        print(
            f"q4_memory_balloon: MemoryError — peak before exception was "
            f"{cumulative_bytes / (1024*1024):.0f} MiB"
        )
        sys.stdout.flush()
        break
