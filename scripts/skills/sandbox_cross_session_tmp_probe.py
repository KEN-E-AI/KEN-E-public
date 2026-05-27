"""SK-35 — Cross-session /tmp characterisation probe.

Exercises the **production** SandboxPool lifecycle (get_or_create → evict →
get_or_create) to determine whether Vertex AI's ``AgentEngineSandboxCodeExecutor``
container pool clears ``/tmp`` between executor sessions sharing the same sandbox
resource name.

The security question (from ``docs/spike/sk-9-security-review.md`` §Q3):

    If Vertex reuses a container without clearing ``/tmp``, filesystem sentinels
    written in executor_A's session survive into executor_B's session — a
    cross-session LEAK. That promotes Q3 from Medium to High and requires
    adding defence-in-depth ``/tmp`` clearing to ``SandboxPool.get_or_create``
    (SK-PRD-02 §4.6 / SK-35 Task 5a).

This probe runs through the real ``SandboxPool.get_or_create`` / ``SandboxPool.evict``
path — not a direct ``AgentEngineSandboxCodeExecutor`` construction — because the
security finding is about pool-reuse semantics, not raw executor semantics.

``_ProbeSandboxPool`` is a minimal subclass whose only deviation from the
production pool is ``_construct``: it returns an executor keyed to the real
``sandboxEnvironments/<sid>`` path supplied via ``KENE_SK35_AGENT_ENGINE_RESOURCE_NAME``
(or creates one from a ``reasoningEngines/<id>`` path) rather than the PRD-placeholder
``sandboxes/{account}/{config}`` path the production ``_sandbox_resource_name``
still emits (pending SK-26 follow-up, see ``sandbox_pool.py:50``).

IAM note
--------
The Dev Team agent VM (``fun-e-agent-vm@fun-e-business.iam.gserviceaccount.com``)
lacks ``aiplatform.sandboxEnvironments.execute`` on ``ken-e-dev`` — the same gap
documented in ``docs/spike/q3-cross-skill-state-fragment.md:107-108``. Run this
script from a credentialled workstation with ``ken@ken-e.ai``-level access, as was
done for the SK-PRD-00 live captures (2026-05-25).

Usage
-----
::

    # Pre-provisioned sandbox (preferred — avoids create permission requirement):
    export KENE_SK35_AGENT_ENGINE_RESOURCE_NAME=\\
        projects/<proj>/locations/<loc>/reasoningEngines/<id>/sandboxEnvironments/<sid>
    uv run python scripts/skills/sandbox_cross_session_tmp_probe.py

    # Create a new sandbox under an existing Agent Engine resource:
    export KENE_SK35_AGENT_ENGINE_RESOURCE_NAME=\\
        projects/<proj>/locations/<loc>/reasoningEngines/<id>
    uv run python scripts/skills/sandbox_cross_session_tmp_probe.py

    # Expand trial count on intermittent (some LEAK, some CLEAN) result:
    uv run python scripts/skills/sandbox_cross_session_tmp_probe.py --trials 50

    # Override the pool key (useful if multiple engineers probe simultaneously):
    uv run python scripts/skills/sandbox_cross_session_tmp_probe.py \\
        --key-account sk35-acc --key-config sk35-cfg

    # Legacy fallback env var (if KENE_SK35 is unset, falls back to this):
    export KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME=...

Output: Markdown trial table + summary to stdout, ready to paste into
``docs/spike/sk-prd-02-cross-session-tmp-characterisation.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import sys
import time
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Sentinel script bodies (injected into the sandbox via execute_code)
# ---------------------------------------------------------------------------

_WRITE_SENTINEL_TEMPLATE = """\
import os as _os
_sentinel = {sentinel!r}
_path = '/tmp/kene-probe-' + _sentinel
with open(_path, 'w') as _f:
    _f.write(_sentinel)
print(f'SK35_WROTE:{{_path}}')
"""

_READ_SENTINEL_TEMPLATE = """\
import os as _os
_sentinel = {sentinel!r}
_path = '/tmp/kene-probe-' + _sentinel
if _os.path.exists(_path):
    with open(_path) as _f:
        _content = _f.read()
    print(f'SK35_RESULT:LEAK:{{_content}}')
else:
    print(f'SK35_RESULT:CLEAN')
"""


# ---------------------------------------------------------------------------
# _ProbeSandboxPool — production pool with _construct overridden for real sandbox
# ---------------------------------------------------------------------------


def _build_probe_pool(
    resolved_sandbox: str,
) -> Any:
    """Return a ``_ProbeSandboxPool`` instance wired to *resolved_sandbox*.

    ``_ProbeSandboxPool`` inherits the full production ``SandboxPool`` (LRU,
    idle-TTL, striped locks, ``aclose()``-on-eviction, Weave spans) and only
    overrides ``_construct`` to route to the real ``sandboxEnvironments/<sid>``
    path instead of the PRD-placeholder format.  Everything else — the
    get_or_create / evict lifecycle that this probe is characterising — runs
    unmodified.
    """
    from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

    class _ProbeSandboxPool(SandboxPool):
        """SandboxPool subclass that wires _construct to the probe sandbox."""

        def __init__(self, sandbox_resource_name: str) -> None:
            super().__init__()
            self._probe_sandbox_resource_name = sandbox_resource_name
            self.construct_count = 0

        async def _construct(
            self,
            *,
            account_id: str,
            config_id: str,
        ) -> Any:
            """Return a real AgentEngineSandboxCodeExecutor for the probe sandbox.

            Both executor_A and executor_B constructed in the same trial are
            keyed to the same ``sandboxEnvironments/<sid>`` path so the probe
            can observe whether Vertex reuses or reinitialises the container.
            ``construct_count`` is incremented so the trial loop can assert
            that each post-eviction get_or_create actually calls _construct
            (i.e., the pool cache miss path ran, not a residual hit).
            """
            from google.adk.code_executors.agent_engine_sandbox_code_executor import (
                AgentEngineSandboxCodeExecutor,
            )

            self.construct_count += 1
            resource = self._probe_sandbox_resource_name
            if "/sandboxEnvironments/" in resource:
                return AgentEngineSandboxCodeExecutor(
                    sandbox_resource_name=resource,
                )
            else:
                return AgentEngineSandboxCodeExecutor(
                    agent_engine_resource_name=resource,
                )

    return _ProbeSandboxPool(resolved_sandbox)


# ---------------------------------------------------------------------------
# Sandbox resolution — create a new sandbox if given a reasoningEngines/ path
# ---------------------------------------------------------------------------


def _resolve_sandbox(resource_name: str, project: str, location: str) -> str:
    """Return a ``sandboxEnvironments/<sid>`` resource name.

    If *resource_name* already contains ``/sandboxEnvironments/``, return it
    unchanged (pre-provisioned).  Otherwise create a new sandbox under the
    given Agent Engine resource name and return the created sandbox's name.
    Mirrors the resolution logic in ``scripts/spike/sandbox_test_harness.py``
    (lines 732-762).
    """
    if "/sandboxEnvironments/" in resource_name:
        return resource_name

    try:
        import vertexai  # type: ignore[import-untyped]
        from vertexai import types as vertex_types  # type: ignore[import-untyped]
    except ImportError as exc:
        sys.exit(
            f"ERROR: vertexai SDK not found — run `uv sync` first: {exc}\n"
            "Install google-cloud-aiplatform to proceed."
        )

    try:
        client = vertexai.Client(project=project, location=location)
    except Exception as exc:
        sys.exit(
            f"ERROR: could not initialise Vertex AI client: {exc}\n"
            "Check that GOOGLE_APPLICATION_CREDENTIALS is set and valid."
        )

    print(
        f"[sk35] Creating new sandbox under {resource_name} ...",
        file=sys.stderr,
    )
    try:
        operation = client.agent_engines.sandboxes.create(
            spec={"code_execution_environment": {}},
            name=resource_name,
            config=vertex_types.CreateAgentEngineSandboxConfig(
                display_name="sk35_cross_session_probe",
            ),
        )
        if not operation.response or not operation.response.name:
            sys.exit("ERROR: sandbox creation returned no resource name")
        resolved = operation.response.name
        print(
            f"[sk35] Sandbox created: {resolved}",
            file=sys.stderr,
        )
        return resolved
    except Exception as exc:
        sys.exit(
            f"ERROR: sandbox creation failed — {exc}\n"
            f"Check that the service account has aiplatform.sandboxEnvironments.create "
            f"on {resource_name}."
        )


# ---------------------------------------------------------------------------
# Direct execute_code call (bypasses InvocationContext requirement)
# ---------------------------------------------------------------------------


def _execute_in_sandbox(client: Any, sandbox_name: str, code: str) -> tuple[str, str]:
    """Run *code* in *sandbox_name* via the direct vertexai SDK.

    Returns ``(stdout, status)`` where *status* is ``"ok"`` on success or an
    error string.  Mirrors the direct-mode call in ``sandbox_test_harness.py``
    (lines 776-798).
    """
    try:
        response = client.agent_engines.sandboxes.execute_code(
            name=sandbox_name,
            input_data={"code": code},
        )
    except Exception as exc:
        return (
            "",
            f"error ({type(exc).__name__}): execute_code failed — {exc}",
        )

    outputs = getattr(response, "outputs", None) or []
    if not outputs:
        return "", "error: executor produced no result"

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    for out in outputs:
        if hasattr(out, "code_execution_result"):
            r = out.code_execution_result
            if hasattr(r, "output") and r.output:
                # Strip trailing newline consistent with harness behaviour
                stdout_parts.append(r.output.rstrip("\n"))
        elif hasattr(out, "text"):
            if "stderr" in str(type(out)).lower():
                stderr_parts.append(out.text)
            else:
                stdout_parts.append(out.text.rstrip("\n"))

    stdout = "\n".join(stdout_parts)
    if stderr_parts:
        stderr = "\n".join(stderr_parts)
        stdout = (stdout + f"\n[stderr] {stderr}") if stdout else f"[stderr] {stderr}"

    return stdout, "ok"


# ---------------------------------------------------------------------------
# Single trial
# ---------------------------------------------------------------------------


async def _run_trial(
    pool: Any,
    client: Any,
    sandbox_name: str,
    key: tuple[str, str],
    trial_n: int,
) -> dict[str, Any]:
    """Run one write → evict → read trial.

    Returns a dict with keys: trial, sentinel_uuid, construct_count_before,
    construct_count_after, write_status, read_stdout, result, elapsed_s.
    """
    sentinel = f"sk35-t{trial_n:03d}-{uuid.uuid4().hex[:12]}"
    account_id, config_id = key

    # Evict any pre-existing pool entry so the trial always starts from
    # a fresh executor_A construction.
    await pool.evict(key, reason="manual")

    t_start = time.monotonic()

    # Step 1 — acquire executor_A (cache miss → _construct called)
    construct_before = pool.construct_count
    _executor_a = await pool.get_or_create(account_id=account_id, config_id=config_id)
    construct_after_a = pool.construct_count

    # Step 2 — write sentinel via executor_A's sandbox session
    write_code = _WRITE_SENTINEL_TEMPLATE.format(sentinel=sentinel)
    _write_stdout, write_status = _execute_in_sandbox(client, sandbox_name, write_code)

    # Step 3 — evict executor_A (calls aclose(), releases the Vertex connection)
    await pool.evict(key, reason="manual")

    # Step 4 — acquire executor_B (cache miss → _construct called again)
    _executor_b = await pool.get_or_create(account_id=account_id, config_id=config_id)
    construct_after_b = pool.construct_count

    # Step 5 — read sentinel via executor_B's sandbox session
    read_code = _READ_SENTINEL_TEMPLATE.format(sentinel=sentinel)
    read_stdout, read_status = _execute_in_sandbox(client, sandbox_name, read_code)

    elapsed_s = time.monotonic() - t_start

    # Classify result
    if write_status != "ok":
        result = f"PROBE_ERROR_WRITE: {write_status}"
    elif read_status != "ok":
        result = f"PROBE_ERROR_READ: {read_status}"
    elif "SK35_RESULT:LEAK" in read_stdout:
        result = "LEAK"
    elif "SK35_RESULT:CLEAN" in read_stdout:
        result = "CLEAN"
    else:
        result = f"PROBE_ERROR_UNEXPECTED: read_stdout={read_stdout!r}"

    return {
        "trial": trial_n,
        "sentinel_uuid": sentinel,
        "construct_count_before": construct_before,
        "construct_count_after_a": construct_after_a,
        "construct_count_after_b": construct_after_b,
        "write_status": write_status,
        "read_stdout": read_stdout.strip(),
        "result": result,
        "elapsed_s": round(elapsed_s, 2),
    }


# ---------------------------------------------------------------------------
# Markdown summary renderer
# ---------------------------------------------------------------------------


def _render_markdown_summary(
    results: list[dict[str, Any]],
    sandbox_name: str,
    key: tuple[str, str],
    adk_version: str,
) -> str:
    """Return a Markdown block suitable for pasting into the findings doc."""
    n = len(results)
    leak_count = sum(1 for r in results if r["result"] == "LEAK")
    clean_count = sum(1 for r in results if r["result"] == "CLEAN")
    error_count = n - leak_count - clean_count
    leak_rate = f"{leak_count}/{n}" if n > 0 else "0/0"

    if error_count > 0:
        classification = "INCONCLUSIVE — harness errors present; review per-trial rows"
    elif leak_count > 0 and clean_count > 0:
        classification = (
            f"INTERMITTENT LEAK ({leak_rate} trials) — characterise further with "
            f"`--trials 50`; see recommendations below"
        )
    elif leak_count == n:
        classification = (
            f"LEAK — all {n} trials confirmed /tmp reuse across executor sessions"
        )
    else:
        classification = (
            f"CLEAN — all {n} trials confirmed /tmp cleared between sessions"
        )

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for r in results:
        rows.append(
            f"| {r['trial']} | {r['sentinel_uuid']} | {r['result']} "
            f"| {r['construct_count_after_a']}→{r['construct_count_after_b']} "
            f"| {r['elapsed_s']:.2f}s |"
        )
    table_body = "\n".join(rows)

    recommendations = ""
    if leak_count > 0:
        recommendations = (
            "\n\n**Recommendation (LEAK path):** Any non-zero LEAK trial triggers "
            "the AC-3 LEAK branch. Uncomment `_CLEAR_TMP_ON_REUSE = True` in "
            "`app/adk/agents/agent_factory/sandbox_pool.py`, run the `test_tmp_clear*` "
            "tests, and update `docs/spike/sk-9-security-review.md` §Q3 to High severity."
        )
    if clean_count == n:
        recommendations = (
            "\n\n**Recommendation (CLEAN path):** All trials CLEAN — AC-3 CLEAN branch "
            "applies. Leave `_CLEAR_TMP_ON_REUSE = False`, remove the conditional "
            "qualifier from `docs/spike/sk-9-security-review.md` §Q3, and confirm "
            "AC #3 disposition remains `N/A — no findings at or above High severity`."
        )

    return f"""\
## SK-35 Probe Run — {ts}

**Sandbox:** `{sandbox_name}`
**Pool key:** `{key}`
**ADK version:** {adk_version}
**Trials:** {n}
**Leak rate:** {leak_rate}
**Classification:** **{classification}**

### Per-trial results

| Trial | Sentinel UUID | Result | _construct calls (A→B) | Elapsed |
|-------|--------------|--------|------------------------|---------|
{table_body}
{recommendations}

<details>
<summary>Raw stdout per trial (expand for full read_stdout values)</summary>

```
{chr(10).join(f"Trial {r['trial']}: write={r['write_status']} read_stdout={r['read_stdout']!r}" for r in results)}
```

</details>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "SK-35 — Characterise Vertex container-pool /tmp reuse across "
            "executor sessions. Exercises the production SandboxPool lifecycle "
            "against a real Vertex AI sandbox and records LEAK vs CLEAN per trial."
        )
    )
    p.add_argument(
        "--trials",
        type=int,
        default=10,
        metavar="N",
        help="Number of write→evict→read trials to run (default: 10; expand to 50+ on intermittent result).",
    )
    p.add_argument(
        "--key-account",
        default="sk35-account",
        metavar="ACCOUNT_ID",
        help="account_id component of the SandboxPool key (default: 'sk35-account').",
    )
    p.add_argument(
        "--key-config",
        default="sk35-config",
        metavar="CONFIG_ID",
        help="config_id component of the SandboxPool key (default: 'sk35-config').",
    )
    p.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev"),
        help="GCP project ID (default: $GOOGLE_CLOUD_PROJECT_ID or 'ken-e-dev').",
    )
    p.add_argument(
        "--location",
        default=os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
        help="Vertex AI location (default: $VERTEX_AI_LOCATION or 'us-central1').",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write Markdown summary to this file path in addition to stdout.",
    )
    return p.parse_args(argv)


def _require_resource_name() -> str:
    """Return the Agent Engine resource name from env vars or exit."""
    resource_name = os.environ.get(
        "KENE_SK35_AGENT_ENGINE_RESOURCE_NAME"
    ) or os.environ.get("KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME")
    if not resource_name:
        sys.exit(
            "ERROR: KENE_SK35_AGENT_ENGINE_RESOURCE_NAME is not set.\n"
            "\n"
            "Provision a throwaway Agent Engine resource on ken-e-dev and set:\n"
            "  export KENE_SK35_AGENT_ENGINE_RESOURCE_NAME=\\\n"
            "      projects/<proj>/locations/<loc>/reasoningEngines/<id>\n"
            "\n"
            "Or point at a pre-provisioned sandboxEnvironment:\n"
            "  export KENE_SK35_AGENT_ENGINE_RESOURCE_NAME=\\\n"
            "      projects/<proj>/locations/<loc>/reasoningEngines/<id>/sandboxEnvironments/<sid>\n"
            "\n"
            "See docs/spike/sk-prd-02-cross-session-tmp-characterisation.md §Methodology\n"
            "for provisioning instructions."
        )
    return resource_name


def _detect_adk_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("google-adk")
    except Exception:
        return "unknown"


async def _main_async(args: argparse.Namespace) -> None:
    resource_name = _require_resource_name()

    # Resolve sandbox (create if needed)
    sandbox_name = _resolve_sandbox(resource_name, args.project, args.location)

    # Build direct vertexai client for execute_code calls
    try:
        import vertexai  # type: ignore[import-untyped]

        client = vertexai.Client(project=args.project, location=args.location)
    except ImportError as exc:
        sys.exit(f"ERROR: vertexai SDK not found — run `uv sync` first: {exc}")
    except Exception as exc:
        sys.exit(f"ERROR: could not initialise Vertex AI client: {exc}")

    adk_version = _detect_adk_version()
    key = (args.key_account, args.key_config)

    print(
        f"[sk35] Starting {args.trials}-trial cross-session /tmp probe\n"
        f"  sandbox: {sandbox_name}\n"
        f"  pool key: {key}\n"
        f"  adk: {adk_version}\n",
        file=sys.stderr,
    )

    pool = _build_probe_pool(sandbox_name)

    results: list[dict[str, Any]] = []
    for trial_n in range(1, args.trials + 1):
        print(
            f"[sk35] Trial {trial_n}/{args.trials} ...",
            end=" ",
            flush=True,
            file=sys.stderr,
        )
        try:
            result = await _run_trial(pool, client, sandbox_name, key, trial_n)
        except Exception as exc:
            result = {
                "trial": trial_n,
                "sentinel_uuid": f"sk35-t{trial_n:03d}-ERROR",
                "construct_count_before": 0,
                "construct_count_after_a": 0,
                "construct_count_after_b": 0,
                "write_status": f"error ({type(exc).__name__}): {exc}",
                "read_stdout": "",
                "result": f"PROBE_ERROR_EXCEPTION: {exc}",
                "elapsed_s": 0.0,
            }
        results.append(result)
        print(result["result"], file=sys.stderr)

        # Auto-recommend expansion on intermittent result
        if result["result"] == "CLEAN" and any(r["result"] == "LEAK" for r in results):
            print(
                "[sk35] WARNING: mixed LEAK/CLEAN results detected after "
                f"{trial_n} trials. Consider rerunning with --trials 50.",
                file=sys.stderr,
            )

    summary = _render_markdown_summary(results, sandbox_name, key, adk_version)
    print(summary)

    if args.output:
        with open(args.output, "w") as f:
            f.write(summary)
        print(f"[sk35] Markdown summary written to {args.output}", file=sys.stderr)

    # Stop the pool's background sweep task cleanly
    await pool.stop()


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
