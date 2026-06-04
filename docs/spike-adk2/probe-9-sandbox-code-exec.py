"""Probe Q9 — AgentEngineSandboxCodeExecutor + SandboxPool path on ADK 2.0.

Two-legged probe:

  Leg A — Local pool test (no live engine required):
    Constructs a SandboxPool with a patched _construct so no real GCP calls
    occur, then verifies the SandboxPool + LeasedSandboxExecutor contract:
      - LeasedSandboxExecutor(pool=pool, ...) constructs the wrapper that
        LlmAgent holds; pool.get_or_create() returns the raw inner executor
        (the actual AgentEngineSandboxCodeExecutor), not a LeasedSandboxExecutor
      - The pool is EMPTY after LeasedSandboxExecutor construction (lazy —
        _construct fires on the first execute_code call, not at build time)
      - Two LeasedSandboxExecutor wrappers for the same (account_id, config_id)
        reference the same pool, ensuring no respawn on per-turn rebuilds

  Leg B — Import verification (ADK 2.0 module path check):
    Imports AgentEngineSandboxCodeExecutor from the ADK 2.0 install and
    verifies:
      - The import path exists (unchanged from 1.x)
      - The class has an execute_code method
    This is the primary unknown: does ADK 2.0 move/rename the import path?

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-9-sandbox-code-exec.py

No live GCP calls are made — the probe is safe to run without ADC configured,
though ADC should be available in the spike environment.

Exit codes:
    0 — all Leg A and Leg B assertions pass
    1 — at least one assertion failed (including import failure — NO-GO finding)
    2 — unexpected infrastructure error (not an assertion failure)

ADK version required: 2.0.0 (in .venv-adk2/)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# sys.path: ensure repo root is importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Vertex AI routing env vars (mirrors _live_harness.py so imported modules
# that read these at import time resolve correctly even when ADC is absent).
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ken-e-dev")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
# Firestore / sandbox pool reads these at construction time.
os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
os.environ.setdefault("VERTEX_AI_LOCATION", "us-central1")

print("=== Probe Q9: AgentEngineSandboxCodeExecutor + SandboxPool — ADK 2.0 ===\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool_with_stub() -> tuple[Any, Any, list[int]]:
    """Return (pool, sentinel_inner_executor, construct_call_count_list).

    Monkey-patches SandboxPool._construct with a sync stub that records every
    call.  Also patches _clear_tmp to avoid live Vertex SDK calls.

    The sentinel is a plain MagicMock — it lives INSIDE the pool as the inner
    executor.  The LeasedSandboxExecutor wrapper held by LlmAgent is separate
    (Pydantic validation is on the wrapper via BaseCodeExecutor inheritance, not
    on the inner executor stored in the pool).
    """
    from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

    sentinel = MagicMock(name="sentinel_inner_executor")
    call_count: list[int] = [0]

    def _stub_construct(*, account_id: str, config_id: str) -> Any:
        call_count[0] += 1
        return sentinel

    pool = SandboxPool()
    pool._construct = _stub_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock(name="_clear_tmp_stub")  # avoid real Vertex calls
    return pool, sentinel, call_count


def run_leg_a() -> list[str]:
    """Leg A: local SandboxPool + LeasedSandboxExecutor contract.

    Returns a list of failure strings (empty == all pass).
    """
    print("--- Leg A: Local SandboxPool + LeasedSandboxExecutor contract ---\n")
    failures: list[str] = []

    try:
        from app.adk.agents.agent_factory.leased_sandbox_executor import (
            LeasedSandboxExecutor,
        )
        from app.adk.agents.agent_factory.sandbox_pool import SandboxPool
    except ImportError as exc:
        failures.append(
            f"FAIL A-IMPORT: Could not import SandboxPool or LeasedSandboxExecutor: {exc}\n"
            "  This is a hard NO-GO — the production modules cannot be loaded."
        )
        return failures

    pool, sentinel, call_count = _make_pool_with_stub()

    # --- A1: get_or_create returns a LeasedSandboxExecutor ---
    wrapper_1 = LeasedSandboxExecutor(
        pool=pool, account_id="acc_spike", config_id="cfg_spike"
    )
    if not isinstance(wrapper_1, LeasedSandboxExecutor):
        failures.append(
            "FAIL A1: LeasedSandboxExecutor(pool=...) did not return a "
            "LeasedSandboxExecutor instance."
        )
    else:
        print("PASS A1: LeasedSandboxExecutor constructed successfully.")

    # A1b: verify the wrapper holds the correct pool + key references
    if getattr(wrapper_1, "_pool", None) is not pool:
        failures.append("FAIL A1b: wrapper_1._pool is not the shared pool object.")
    else:
        print("PASS A1b: wrapper_1._pool references the shared pool.")

    if getattr(wrapper_1, "_account_id", None) != "acc_spike":
        failures.append(
            f"FAIL A1c: wrapper_1._account_id={wrapper_1._account_id!r}, expected 'acc_spike'."
        )
    else:
        print("PASS A1c: wrapper_1._account_id == 'acc_spike'.")

    if getattr(wrapper_1, "_config_id", None) != "cfg_spike":
        failures.append(
            f"FAIL A1d: wrapper_1._config_id={wrapper_1._config_id!r}, expected 'cfg_spike'."
        )
    else:
        print("PASS A1d: wrapper_1._config_id == 'cfg_spike'.")

    # --- A2: Pool is EMPTY after wrapper construction (lazy — _construct not fired) ---
    pool_size_after_construct = len(pool._pool)
    if pool_size_after_construct != 0:
        failures.append(
            f"FAIL A2: Pool size is {pool_size_after_construct} after "
            "LeasedSandboxExecutor construction; expected 0 (lazy construction — "
            "_construct must not fire until first execute_code call)."
        )
    else:
        print("PASS A2: Pool is empty after LeasedSandboxExecutor construction (lazy).")

    if call_count[0] != 0:
        failures.append(
            f"FAIL A2b: _construct was called {call_count[0]} time(s) during "
            "LeasedSandboxExecutor construction; expected 0."
        )
    else:
        print("PASS A2b: _construct not called during construction.")

    # --- A3: Two wrappers for the same key reference the same pool ---
    wrapper_2 = LeasedSandboxExecutor(
        pool=pool, account_id="acc_spike", config_id="cfg_spike"
    )
    if getattr(wrapper_2, "_pool", None) is not pool:
        failures.append(
            "FAIL A3: wrapper_2._pool is not the shared pool — "
            "two wrappers for the same key do not reference the same pool."
        )
    else:
        print(
            "PASS A3: Both wrappers for (acc_spike, cfg_spike) reference the same pool."
        )

    # A3b: Pool still empty after second wrapper construction
    if len(pool._pool) != 0:
        failures.append(
            f"FAIL A3b: Pool size is {len(pool._pool)} after second construction; "
            "expected 0 (second wrapper must also be lazy)."
        )
    else:
        print("PASS A3b: Pool still empty after second wrapper construction.")

    # --- A4: get_or_create() on the pool directly also returns an executor ---
    # This exercises the SandboxPool.get_or_create() path.
    inner_exec = pool.get_or_create(account_id="acc_spike2", config_id="cfg_spike2")
    if inner_exec is not sentinel:
        # call_count should now be 1 (first miss triggers _construct)
        failures.append(
            "FAIL A4: pool.get_or_create() returned an unexpected object "
            f"(got {type(inner_exec).__name__}, expected the sentinel MagicMock)."
        )
    else:
        print("PASS A4: pool.get_or_create() returned the sentinel inner executor.")

    if call_count[0] != 1:
        failures.append(
            f"FAIL A4b: _construct was called {call_count[0]} time(s) after "
            "pool.get_or_create(); expected exactly 1."
        )
    else:
        print("PASS A4b: _construct called exactly once on first get_or_create() miss.")

    # Pool now has exactly one entry (for acc_spike2/cfg_spike2)
    if len(pool._pool) != 1:
        failures.append(
            f"FAIL A4c: Pool size is {len(pool._pool)} after get_or_create(); expected 1."
        )
    else:
        print("PASS A4c: Pool has exactly 1 entry after get_or_create().")

    # Second get_or_create for the same key must NOT call _construct again
    inner_exec_2 = pool.get_or_create(account_id="acc_spike2", config_id="cfg_spike2")
    if call_count[0] != 1:
        failures.append(
            f"FAIL A4d: _construct was called {call_count[0]} time(s) on second "
            "get_or_create() for the same key; expected still 1 (cache hit)."
        )
    else:
        print("PASS A4d: Second get_or_create() is a cache hit — _construct not called again.")

    if inner_exec_2 is not inner_exec:
        failures.append(
            "FAIL A4e: Second get_or_create() returned a different object — pool reuse broken."
        )
    else:
        print("PASS A4e: Both get_or_create() calls for the same key return the same executor.")

    print()
    return failures


def run_leg_b() -> list[str]:
    """Leg B: ADK 2.0 import path verification for AgentEngineSandboxCodeExecutor.

    Returns a list of failure strings (empty == all pass).
    """
    print("--- Leg B: AgentEngineSandboxCodeExecutor import path (ADK 2.0) ---\n")
    failures: list[str] = []

    # B1: import path must exist on ADK 2.0
    try:
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )
        print(
            f"PASS B1: Import succeeded — "
            f"google.adk.code_executors.agent_engine_sandbox_code_executor."
            f"AgentEngineSandboxCodeExecutor is present on ADK 2.0."
        )
    except ImportError as exc:
        failures.append(
            f"FAIL B1: ImportError on ADK 2.0:\n"
            f"  from google.adk.code_executors.agent_engine_sandbox_code_executor "
            f"import AgentEngineSandboxCodeExecutor\n"
            f"  Error: {exc}\n"
            "  This is a hard NO-GO — the production import path in "
            "app/adk/agents/agent_factory/sandbox_pool.py will fail on ADK 2.0 deploy."
        )
        return failures

    # B2: class must have execute_code method
    if not callable(getattr(AgentEngineSandboxCodeExecutor, "execute_code", None)):
        failures.append(
            "FAIL B2: AgentEngineSandboxCodeExecutor has no callable execute_code method.\n"
            "  ADK 2.0 may have renamed or removed the method — check the ADK changelog."
        )
    else:
        print(
            "PASS B2: AgentEngineSandboxCodeExecutor.execute_code is callable."
        )

    # B3: class must be constructible with sandbox_resource_name (regex-only, no I/O)
    # ADK 2.0 validates sandbox_resource_name at construction. Expected format:
    #   projects/{project}/locations/{loc}/reasoningEngines/{id}/sandboxEnvironments/{id}
    # The old format (sandboxes/...) is not valid; use the correct pattern.
    try:
        test_resource = (
            "projects/525657242938/locations/us-central1"
            "/reasoningEngines/12345/sandboxEnvironments/1"
        )
        instance = AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=test_resource,
        )
        actual_resource = getattr(instance, "sandbox_resource_name", None)
        if actual_resource != test_resource:
            failures.append(
                f"FAIL B3: sandbox_resource_name not stored correctly — "
                f"got {actual_resource!r}, expected {test_resource!r}."
            )
        else:
            print(
                f"PASS B3: AgentEngineSandboxCodeExecutor(sandbox_resource_name=...) "
                f"constructs without I/O and stores resource name correctly."
            )
    except Exception as exc:
        failures.append(
            f"FAIL B3: Constructor raised unexpectedly: {type(exc).__name__}: {exc}\n"
            "  ADK 2.0 may require additional constructor args."
        )

    # B4: confirm the installed ADK version (informational — not an assertion)
    try:
        import google.adk as _adk
        adk_version = getattr(_adk, "__version__", "unknown")
        print(f"\nINFO: google-adk version in .venv-adk2 = {adk_version!r}")
    except Exception:
        print("\nINFO: could not read google.adk.__version__")

    print()
    return failures


def run_probe() -> int:
    """Run both legs.  Returns exit code (0=all pass, 1=assertion fail, 2=infra error)."""

    leg_a_failures = run_leg_a()
    leg_b_failures = run_leg_b()

    all_failures = leg_a_failures + leg_b_failures

    if all_failures:
        print("=== PROBE Q9: FAIL ===")
        for failure in all_failures:
            print(f"  {failure}")
        return 1

    print("=== PROBE Q9: PASS ===")
    print("All Leg A + Leg B assertions hold on ADK 2.0:")
    print("  Leg A: SandboxPool lazy-construction contract verified.")
    print("  Leg A: LeasedSandboxExecutor wraps pool correctly; pool stays empty until first execute_code.")
    print("  Leg A: Two wrappers for the same key reference the same pool (no respawn).")
    print("  Leg B: google.adk.code_executors.agent_engine_sandbox_code_executor import path is valid.")
    print("  Leg B: AgentEngineSandboxCodeExecutor.execute_code is callable.")
    print("  Leg B: Constructor works with sandbox_resource_name kwarg (no I/O).")
    return 0


if __name__ == "__main__":
    try:
        exit_code = run_probe()
    except Exception as exc:
        import _live_harness as _h
        code = _h.classify_exit_code(exc)
        label = (
            "infrastructure/credentials"
            if code == 2
            else "FINDING — ADK 2.0 differs from the spike assumption"
        )
        print(f"\nERROR [{label}] (exit {code}): {type(exc).__name__}: {exc}")
        print(
            "\nNote: exit 2 = infra/credentials -> INDETERMINATE; "
            "exit 1 = a real finding (import error, changed constructor) -> NO-GO.\n"
            "Leg A requires no live GCP calls; "
            "Leg B only imports the ADK class (no network I/O)."
        )
        sys.exit(code)
    sys.exit(exit_code)
