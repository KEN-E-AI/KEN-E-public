"""Probe Q11 — Live sandbox round-trip (AgentEngineSandboxCodeExecutor + SandboxPool). (LIVE)

Extends Probe 9's static checks to a live agent-engine sandbox resource on ken-e-dev.

Three validations:

  Leg A — Live execute_code round-trip (requires ADC + provisioned sandbox resource):
    1. Constructs AgentEngineSandboxCodeExecutor(sandbox_resource_name=<resource>).
    2. Calls .execute_code(invocation_context, CodeExecutionInput(code="print(2+2)"))
       synchronously, with a minimal stub InvocationContext.  The executor only reads
       invocation_context.session.state, so no full Runner turn is required (see
       _make_stub_context).
    3. Asserts the result stdout contains "4".
    This is the primary live gate: proves the SK-PRD-02 code-exec path on ADK 2.0.

  Leg B — SandboxPool.lease() live round-trip (requires ADC):
    1. Constructs a real SandboxPool (no mock) with a _construct override that returns
       a live executor for the CLI-supplied sandbox resource.
    2. Drives code-exec through pool.lease() — the production path that
       LeasedSandboxExecutor.execute_code uses.  (get_or_create() is the pool's
       diagnostic/test-only accessor; production callers MUST use lease().)
    3. Calls .execute_code(invocation_context, CodeExecutionInput(code="print(1+1)"))
       on the leased executor and asserts the result stdout contains "2".
    4. Confirms the pool cached the construction via get_or_create() (cache-hit check,
       clearly labeled as the diagnostic accessor).
    This validates the SK-PRD-02 pool contract end-to-end on a live sandbox.

  Leg C — Version confirmation (informational):
    Prints the installed google-adk version so the run log captures the exact ADK
    version under which the live execution succeeded.

Run with (from repo root):
    uv run python docs/spike-adk2/probe-11-deploy-sandbox-live.py \\
        --project ken-e-dev \\
        --location us-central1 \\
        --sandbox-id <SANDBOX_ENV_ID> \\
        --reasoning-engine-id <REASONING_ENGINE_ID>

Or with a full resource name directly:
    uv run python docs/spike-adk2/probe-11-deploy-sandbox-live.py \\
        --sandbox-resource-name \\
            "projects/<NUM>/locations/us-central1/reasoningEngines/<ID>/sandboxEnvironments/<SID>"

Prerequisites:
    1. gcloud auth application-default login (ADC configured for ken-e-dev).
    2. A provisioned sandbox environment in ken-e-dev. If none exists, create one:
           gcloud beta ai sandboxes create --project=ken-e-dev --region=us-central1
       The output includes a resource name you can pass to --sandbox-resource-name.
       Alternatively, AgentEngineSandboxCodeExecutor will lazy-create a sandbox on
       first execute_code if the resource does not exist yet (ADK 2.0 behaviour).

Exit codes:
    0 — all live assertions pass (GO)
    1 — at least one assertion failed (NO-GO finding)
    2 — infrastructure/credentials error (ADC missing, 401/403/5xx, resource not found)

ADK version required: 2.0.0
AH-111 live evidence: docs/runs/AH-111-adk2-deploy-smoke.md (paste the Leg A/B output there)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path: ensure harness and repo root are importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import _live_harness  # noqa: E402

# Vertex AI routing — must be set before any google.adk or google.cloud import.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

print("=== Probe Q11 (live): AgentEngineSandboxCodeExecutor + SandboxPool — live round-trip ===\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Live sandbox probe for AH-111 (ADK 2.0 deploy + sandbox smoke-test).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Run with")[0].strip(),
    )
    p.add_argument(
        "--project",
        default="ken-e-dev",
        help=(
            "GCP project ID or project NUMBER (default: ken-e-dev). "
            "When used with --sandbox-id, the value is embedded directly in the resource name; "
            "ADK 2.0 requires the numeric project number in resource names. "
            "To resolve: gcloud projects describe <PROJECT_ID> --format='value(projectNumber)'"
        ),
    )
    p.add_argument(
        "--location",
        default="us-central1",
        help="Vertex AI region (default: us-central1).",
    )
    p.add_argument(
        "--sandbox-id",
        dest="sandbox_id",
        default=None,
        help="Bare sandbox environment ID (combined with --project, --location, "
             "--reasoning-engine-id to build the full resource name).",
    )
    p.add_argument(
        "--reasoning-engine-id",
        dest="reasoning_engine_id",
        default=None,
        help="Bare reasoningEngines resource ID (required with --sandbox-id).",
    )
    p.add_argument(
        "--sandbox-resource-name",
        dest="sandbox_resource_name",
        default=None,
        help="Full sandbox resource name "
             "(projects/<NUM>/locations/<LOC>/reasoningEngines/<ID>/sandboxEnvironments/<SID>). "
             "Overrides --sandbox-id / --reasoning-engine-id / --project / --location.",
    )
    p.add_argument(
        "--skip-pool",
        action="store_true",
        help="Skip Leg B (SandboxPool round-trip). Use when the pool modules are not importable.",
    )
    return p.parse_args()


# ADK 2.0 validates the sandbox resource name format at constructor time.
# Expected: projects/<PROJ_NUM>/locations/<LOC>/reasoningEngines/<ENGINE_ID>/sandboxEnvironments/<SID>
_RESOURCE_NAME_RE = re.compile(
    r"^projects/[\w-]+/locations/[\w-]+/reasoningEngines/[\w-]+"
    r"/sandboxEnvironments/[\w-]+$"
)


def _validate_resource_name(resource_name: str) -> None:
    """Validate sandbox resource name format.  Exits 2 on bad format."""
    if not _RESOURCE_NAME_RE.fullmatch(resource_name):
        print(
            f"ERROR: malformed sandbox resource name: {resource_name!r}\n"
            "  Expected format: projects/<NUM>/locations/<LOC>/reasoningEngines/<ID>"
            "/sandboxEnvironments/<SID>\n"
            "  Use gcloud projects describe <PROJECT_ID> --format='value(projectNumber)' "
            "to resolve the numeric project number."
        )
        sys.exit(2)


def _build_resource_name(args: argparse.Namespace) -> str:
    """Return the full sandbox resource name from CLI args.

    Precedence: --sandbox-resource-name > --project+--location+--reasoning-engine-id+--sandbox-id.
    """
    if args.sandbox_resource_name:
        resource = args.sandbox_resource_name
        _validate_resource_name(resource)
        return resource

    if not args.reasoning_engine_id or not args.sandbox_id:
        print(
            "ERROR: supply either --sandbox-resource-name OR both "
            "--reasoning-engine-id and --sandbox-id.\n"
            "       Run with --help for usage examples."
        )
        sys.exit(2)

    # Build the full resource name from components.
    # ADK 2.0 validates the format:
    #   projects/<PROJ_NUM>/locations/<LOC>/reasoningEngines/<ENGINE_ID>/sandboxEnvironments/<SANDBOX_ID>
    # Note: --project must be the numeric project NUMBER, not the project ID string.
    # Resolve with: gcloud projects describe <PROJECT_ID> --format='value(projectNumber)'
    resource = (
        f"projects/{args.project}/locations/{args.location}"
        f"/reasoningEngines/{args.reasoning_engine_id}"
        f"/sandboxEnvironments/{args.sandbox_id}"
    )
    _validate_resource_name(resource)
    return resource


def _make_stub_context() -> Any:
    """Return a minimal InvocationContext for a standalone execute_code call.

    AgentEngineSandboxCodeExecutor.execute_code only touches
    ``invocation_context.session.state`` (it reads/writes the cached ``sandbox_name``
    key — ADK 2.0 agent_engine_sandbox_code_executor.py:138/173), so a full
    Runner-built context is unnecessary.  We hand-build the pydantic
    InvocationContext with a real Session (its ``.state`` is a fresh mutable dict)
    and a spec-conforming BaseSessionService stub that satisfies pydantic's
    isinstance validation without any I/O.
    """
    from unittest.mock import create_autospec

    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.sessions.base_session_service import BaseSessionService
    from google.adk.sessions.session import Session

    session = Session(
        id=f"ah111-probe-{uuid.uuid4().hex[:8]}",
        app_name="ah111-probe",
        user_id="ah111-probe",
    )
    session_service = create_autospec(BaseSessionService, instance=True)
    return InvocationContext(
        session_service=session_service,
        invocation_id=f"ah111-{uuid.uuid4().hex[:8]}",
        session=session,
    )


# ---------------------------------------------------------------------------
# Leg A — Live execute_code round-trip
# ---------------------------------------------------------------------------

def run_leg_a(sandbox_resource_name: str) -> tuple[list[str], int]:
    """Live execute_code round-trip.

    Returns (failures, worst_exit_code): failures is a list of failure strings (empty = pass);
    worst_exit_code is 0 (all pass), 1 (NO-GO finding), or 2 (infrastructure/credentials).
    """
    print("--- Leg A: Live execute_code round-trip ---\n")
    failures: list[str] = []
    worst: int = 0

    # A1: import
    try:
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )
        print("PASS A1: AgentEngineSandboxCodeExecutor imported successfully.")
    except ImportError as exc:
        failures.append(
            f"FAIL A1: ImportError — google.adk.code_executors.agent_engine_sandbox_code_executor: {exc}\n"
            "  This is a hard NO-GO."
        )
        return failures, 1

    # A2: construct with resource name (no I/O)
    try:
        executor = AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=sandbox_resource_name,
        )
        print(f"PASS A2: Constructed AgentEngineSandboxCodeExecutor(sandbox_resource_name={sandbox_resource_name!r}).")
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        worst = max(worst, code)
        failures.append(f"FAIL A2: Constructor raised {type(exc).__name__}: {exc}")
        return failures, worst

    # A3: execute_code — the live call.
    # ADK 2.0 contract: execute_code(invocation_context, CodeExecutionInput(code=...)).
    print("       Calling .execute_code(ctx, CodeExecutionInput(code='print(2+2)')) — live GCP call ...")
    try:
        from google.adk.code_executors.code_execution_utils import CodeExecutionInput

        ctx = _make_stub_context()
        result = executor.execute_code(ctx, CodeExecutionInput(code="print(2+2)"))
        print(f"       Raw result: {result!r}")
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        worst = max(worst, code)
        label = "INFRA/CREDENTIALS" if code == 2 else "FINDING"
        failures.append(
            f"FAIL A3 [{label}] (exit {code}): {type(exc).__name__}: {exc}\n"
            + (
                "  Infrastructure/credentials issue — verify ADC and sandbox resource provisioning."
                if code == 2
                else "  Real finding — executor path on ADK 2.0 is broken."
            )
        )
        return failures, worst

    # A4: assert result stdout contains "4"
    result_text = _extract_result_text(result)
    if "4" not in result_text:
        worst = max(worst, 1)
        stderr = _extract_stderr(result)
        failures.append(
            f"FAIL A4: execute_code stdout does not contain '4'. stdout={result_text!r}"
            + (f", stderr={stderr!r}" if stderr else "")
            + f"\n  Full result: {result!r}"
        )
    else:
        print(f"PASS A3+A4: execute_code returned; stdout contains '4'. stdout={result_text!r}")

    print()
    return failures, worst


def _extract_result_text(result: Any) -> str:
    """Extract stdout text from an ADK 2.0 CodeExecutionResult.

    ``CodeExecutionResult`` exposes ``.stdout`` / ``.stderr``; we return stdout.
    A plain-string result is returned as-is, and any other shape (or empty stdout)
    falls back to repr() for diagnostics.
    """
    if isinstance(result, str):
        return result
    stdout = getattr(result, "stdout", None)
    if stdout:
        return str(stdout)
    return repr(result)


def _extract_stderr(result: Any) -> str:
    """Return the stderr of a CodeExecutionResult (empty string if absent)."""
    return str(getattr(result, "stderr", "") or "")


# ---------------------------------------------------------------------------
# Leg B — SandboxPool.lease() live round-trip
# ---------------------------------------------------------------------------

def run_leg_b(sandbox_resource_name: str) -> tuple[list[str], int]:
    """SandboxPool.lease() live round-trip.

    Returns (failures, worst_exit_code) — same contract as run_leg_a.

    Drives code-exec through pool.lease() — the production path that
    LeasedSandboxExecutor.execute_code uses (lease() tracks refcount and runs
    _clear_tmp at the 0 → 1 boundary, SK-42). get_or_create() is the pool's
    diagnostic/test-only accessor (production callers MUST use lease(), per
    sandbox_pool.py); it is used here ONLY for the B5 cache-hit assertion.
    """
    print("--- Leg B: SandboxPool.lease() live round-trip ---\n")
    failures: list[str] = []
    worst: int = 0

    # B1: import pool modules
    try:
        from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

        print("PASS B1: SandboxPool imported successfully.")
    except ImportError as exc:
        failures.append(
            f"FAIL B1: ImportError — production pool modules not importable: {exc}\n"
            "  Use --skip-pool to skip this leg if pool modules are unavailable."
        )
        return failures, 1

    # B2: build a real SandboxPool with a _construct that returns a live executor
    try:
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )
    except ImportError as exc:
        failures.append(f"FAIL B2: Cannot import AgentEngineSandboxCodeExecutor for live _construct: {exc}")
        return failures, 1

    # ops-only: monkey-patch _construct to inject the live sandbox resource.
    # Do NOT copy this pattern into production test fixtures — use SandboxPool's
    # test seam instead (tracked as a follow-up in the SK-PRD-02 implementation).
    def _live_construct(*, account_id: str, config_id: str) -> Any:
        return AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=sandbox_resource_name,
        )

    pool = SandboxPool()
    pool._construct = _live_construct  # type: ignore[method-assign]  # ops-only

    # B3: drive code-exec through pool.lease() — the production path.
    # ADK 2.0 contract: execute_code(invocation_context, CodeExecutionInput(code=...)).
    print("       Calling pool.lease() + execute_code(ctx, CodeExecutionInput(code='print(1+1)')) ...")
    try:
        from google.adk.code_executors.code_execution_utils import CodeExecutionInput

        ctx = _make_stub_context()
        with pool.lease(
            account_id="ah111-probe-acct",
            config_id="ah111-probe-cfg",
        ) as inner_executor:
            result = inner_executor.execute_code(ctx, CodeExecutionInput(code="print(1+1)"))
        print(f"       Raw result: {result!r}")
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        worst = max(worst, code)
        label = "INFRA/CREDENTIALS" if code == 2 else "FINDING"
        failures.append(
            f"FAIL B3 [{label}] (exit {code}): {type(exc).__name__}: {exc}\n"
            + (
                "  Verify ADC and sandbox resource."
                if code == 2
                else "  Real NO-GO finding."
            )
        )
        return failures, worst

    result_text = _extract_result_text(result)
    if "2" not in result_text:
        worst = max(worst, 1)
        stderr = _extract_stderr(result)
        failures.append(
            f"FAIL B4: execute_code stdout does not contain '2'. stdout={result_text!r}"
            + (f", stderr={stderr!r}" if stderr else "")
        )
    else:
        print(f"PASS B3+B4: pool.lease() execute_code returned; stdout contains '2'. stdout={result_text!r}")

    # B5: get_or_create() for the same key is a cache hit — it returns the SAME executor
    # that lease() constructed. get_or_create() is the diagnostic accessor (production
    # callers use lease()); here it only confirms the pool cached the construction.
    cached = pool.get_or_create(account_id="ah111-probe-acct", config_id="ah111-probe-cfg")
    if cached is not inner_executor:
        worst = max(worst, 1)
        failures.append(
            "FAIL B5: get_or_create() after lease() returned a different object — "
            "pool did not cache the construction."
        )
    else:
        print("PASS B5: get_or_create() is a cache hit — same executor lease() constructed.")

    print()
    return failures, worst


# ---------------------------------------------------------------------------
# Leg C — Version confirmation (informational)
# ---------------------------------------------------------------------------

def run_leg_c() -> None:
    """Print the installed google-adk version. Never fails."""
    print("--- Leg C: ADK version confirmation (informational) ---\n")
    try:
        import google.adk as _adk
        adk_version = getattr(_adk, "__version__", "unknown")
        print(f"INFO: google-adk version = {adk_version!r}")
    except Exception as exc:
        print(f"INFO: could not read google.adk.__version__: {exc}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _parse_args()

    # Set project/location env vars from CLI so any ADK sub-call picks them up.
    os.environ["GOOGLE_CLOUD_PROJECT"] = args.project
    os.environ["GOOGLE_CLOUD_LOCATION"] = args.location
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = args.project
    os.environ["VERTEX_AI_LOCATION"] = args.location

    resource_name = _build_resource_name(args)
    print(f"Sandbox resource: {resource_name}\n")

    run_leg_c()

    leg_a_failures, leg_a_exit = run_leg_a(resource_name)

    if args.skip_pool:
        print("--- Leg B: SKIPPED (--skip-pool) ---\n")
        leg_b_failures: list[str] = []
        leg_b_exit = 0
    else:
        leg_b_failures, leg_b_exit = run_leg_b(resource_name)

    all_failures = leg_a_failures + leg_b_failures
    # worst_exit tracks the most severe exit code: 2 (infra) > 1 (finding) > 0 (pass).
    # Exit 2 means INDETERMINATE (infrastructure/credentials); 1 means NO-GO (real finding).
    worst_exit = max(leg_a_exit, leg_b_exit)

    if all_failures:
        print("=== PROBE Q11: FAIL ===")
        for f in all_failures:
            print(f"  {f}")
        return worst_exit if worst_exit > 0 else 1

    print("=== PROBE Q11: PASS ===")
    print("All legs passed on ADK 2.0:")
    print("  Leg A: AgentEngineSandboxCodeExecutor.execute_code(ctx, CodeExecutionInput('print(2+2)')) returned '4' (live).")
    if not args.skip_pool:
        print("  Leg B: SandboxPool.lease() execute_code('print(1+1)') returned '2' (live).")
        print("  Leg B: Pool cache hit verified — get_or_create() returns the executor lease() constructed.")
    print("\nPaste this output into docs/runs/AH-111-adk2-deploy-smoke.md §AC-3 row.")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except SystemExit:
        raise
    except Exception as exc:
        code = _live_harness.classify_exit_code(exc)
        label = "infrastructure/credentials" if code == 2 else "FINDING"
        print(f"\nERROR [{label}] (exit {code}): {type(exc).__name__}: {exc}")
        sys.exit(code)
    sys.exit(exit_code)
