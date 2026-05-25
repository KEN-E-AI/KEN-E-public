"""SK-PRD-00 spike harness — AgentEngineSandboxCodeExecutor evaluation.

Runs one or more Python scripts through a Vertex AI Agent Engine sandbox so
SK-PRD-00 Q1-Q5 issues can measure network egress, cost, cross-skill state,
resource limits, and file I/O empirically.

ADK version pinned: google-adk==1.27.5 (spike/agent-engine-sandbox branch).
# TODO(SK-10): remove explicit ADK pin when SK-10 unblocks branch deletion.
This branch is never merged to main (PRD §7 AC #1).

=== Execution Modes ===

Three modes are available. All produce the same output format.

DEFAULT (direct mode):
    Calls the Vertex AI sandbox execute_code API directly without any LlmAgent
    or Gemini model call. The script is sent straight to the sandbox's
    execute_code API endpoint. This is the recommended measurement path: it
    removes the LlmAgent entirely, eliminating every hallucination failure mode
    documented in docs/spike/harness-validation.md.
    Status is inferred from stdout content and API exception types.
    Requires: aiplatform.sandboxEnvironments.* ONLY (no Gemini access needed).

    cd /home/agent/workspace
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/hello.py

LEGACY LLM-LOOP mode (--legacy-llm-loop flag):
    Routes scripts through an LlmAgent backed by Gemini. The LLM receives the
    script text as a user message and uses its code_executor to execute it.
    CAUTION: this mode can produce hallucinated results even with the
    force-tool-use config applied. See docs/spike/harness-validation.md for the
    full failure evidence (Runs 1-4). Use this mode only if you need to measure
    LLM-loop-specific behaviour; for empirical sandbox measurements use direct
    mode (the default).
    Requires: aiplatform.endpoints.predict + aiplatform.sandboxEnvironments.*

    cd /home/agent/workspace
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/hello.py \\
        --legacy-llm-loop

=== ADK 1.27.5 text-suppression surface (AC-2 research, Wave 2.5) ===

Three candidate knobs were investigated in ADK 1.27.5:

(a) generate_content_config.tool_config.function_calling_config.mode = "ANY"
    EXPOSED at 1.27.5. LlmAgent accepts generate_content_config
    (llm_agent.py:288). The validator (llm_agent.py:857-874) rejects `tools`,
    `system_instruction`, and `response_schema` but NOT `tool_config`. The
    FunctionCallingConfigMode enum includes "ANY" (google.genai.types). The
    --legacy-llm-loop mode applies this config.
    Source: site-packages/google/adk/agents/llm_agent.py:288 (field)
            site-packages/google/adk/agents/llm_agent.py:857 (validator)

(b) generate_content_config.response_modalities (list[str]) excluding "TEXT"
    EXPOSED at 1.27.5 on GenerateContentConfig (google.genai.types). However,
    this field is documented for live/voice agents ("defaults to AUDIO"); for
    standard LlmAgent chat turns ADK does not populate it and the model ignores
    it. NOT a reliable text-suppression mechanism for code-executor mode.
    Source: site-packages/google/adk/models/llm_request.py (RunConfig note)
            site-packages/google/adk/agents/run_config.py:198

(c) explicit tools=[...] wiring bypassing code_executor=
    The code executor is wired by ADK internally; re-implementing it as an
    explicit tool would require subclassing or low-level ADK internals. Not
    attempted in v1 — direct mode is a cleaner path.

PRIMARY CHOSEN KNOB: mode="ANY" via generate_content_config.tool_config
(option a). Applied in _run_scripts() to the LlmAgent. This is the best
available force-tool-use surface in 1.27.5.

=== Direct-call surface confirmation (AC-4 research, Wave 2.5) ===

AgentEngineSandboxCodeExecutor.execute_code() signature:
    execute_code(self, invocation_context: InvocationContext,
                 code_execution_input: CodeExecutionInput) -> CodeExecutionResult
Source: site-packages/google/adk/code_executors/agent_engine_sandbox_code_executor.py:95

This method requires a full ADK InvocationContext — it is NOT a direct
script-string surface. The direct-call surface is:
    vertexai.Client(project, location).agent_engines.sandboxes.execute_code(
        name=sandbox_resource_name, input_data={"code": script_content}
    )
This API is already used in the harness's (now-default) direct mode.
CONFIRMATION: direct-call surface confirmed. Direct mode is the default.

LOCAL-LIMITS mode (--local-limits flag):
    Runs the script in an isolated subprocess with OS-level resource limits
    applied via Python's `resource` module (RLIMIT_CPU for CPU time,
    RLIMIT_AS for virtual memory on Linux) plus a wall-clock timeout.
    No Vertex AI credentials or network access required.
    Produces real OS kill signals (SIGXCPU, SIGKILL) and real MemoryError
    sentinel lines — empirical measurements, not simulations, just from the
    local Linux kernel rather than the Vertex AI platform.

    cd /home/agent/workspace
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/q4_cpu_loop.py \\
        --local-limits --cpu-limit-s 5

    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/q4_memory_balloon.py \\
        --local-limits --mem-limit-mib 768

    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/q4_wall_clock.py \\
        --local-limits --wall-clock-timeout-s 45

Use --local-limits when aiplatform.sandboxEnvironments.* permissions are
unavailable. The measurements are labelled "LOCAL MODE" in the output to
distinguish them from Vertex AI sandbox measurements. For SK-5 Q4, this
yields the kill behaviour, peak-MiB, and wall-clock threshold the fragment
needs, with clear caveats that Vertex AI platform limits may differ.

Multi-script reproduction (SK-4 Q3 — same-session cross-skill probe):

    cd /home/agent/workspace
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/q3_skill_a_writer.py \\
        --script scripts/spike/skills/q3_skill_b_reader.py

Required environment variables (see CLAUDE.md §Key Environment Variables):
    GOOGLE_CLOUD_PROJECT                  GCP project id
    VERTEX_AI_LOCATION                    e.g. us-central1
    KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME Vertex AI Agent Engine resource name
      e.g. projects/<proj>/locations/<loc>/reasoningEngines/<id>
      Creates a new sandboxEnvironment on first invocation.
      Requires: aiplatform.sandboxEnvironments.create
    KENE_SPIKE_SANDBOX_RESOURCE_NAME      Pre-provisioned sandbox environment (preferred)
      e.g. projects/<proj>/locations/<loc>/reasoningEngines/<id>/sandboxEnvironments/<sid>
      When this value contains /sandboxEnvironments/, it takes priority over
      KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME. The harness uses the sandbox
      directly without a create step — requires only execute permission, not
      aiplatform.sandboxEnvironments.create. Set this when the service account
      lacks create permission but has access to an already-running sandbox.

The harness routes to the correct ADK constructor kwarg automatically:
  path contains /sandboxEnvironments/ → sandbox_resource_name=
  path does NOT contain /sandboxEnvironments/ → agent_engine_resource_name=

CLI overrides are available for all three (--project, --location,
--sandbox-resource-name) so Q1-Q5 issues can swap configs without forking
this module.

Output format:
  <sandbox stdout>
  ---
  ADK version  : <installed version>
  Sandbox      : <resource name>
  Elapsed (s)  : <float>
  Exit status  : ok | error: <reason>

Direct mode and LLM-loop mode `Exit status` signals:

  ok                                       measurement succeeded
  error: script_tampered                   executable_code part contained a
                                           different script than submitted;
                                           diff written to /tmp/*.diff
  error: agent emitted text alongside executable_code
                                           LLM emitted free-form text parts in
                                           addition to executable_code (LLM loop
                                           mode only)
  error: canary_verification_failed: {reason}
                                           hello.py canary output failed
                                           external verification (wrong SHA-256
                                           or big-int; see canary_verifier.py)
  error: agent emitted no executable_code  LLM ignored the instruction or refused
                                           (LLM loop mode)
  error: executor produced no result       code emitted but no result event /
                                           API returned empty outputs
  error: executor outcome <OUTCOME_*>      executor ran but reported a non-OK
                                           outcome (LLM loop mode)
  error (<ExceptionType>): ...             runner or executor raised

Direct mode `Exit status` reflects what the Vertex AI sandbox API returned:

  ok                                       execute_code API call completed
  error (<ExceptionType>): ...             execute_code API call raised an exception
  error: executor produced no result       API returned empty outputs

  Note: stderr from the sandbox is appended to stdout under a [stderr] label
  so resource-limit kill signals (which may arrive via msg_err) are not lost.

Local-limits mode `Exit status` reflects what the subprocess and OS reported:

  ok                                       script exited with code 0
  error: local executor — SIGXCPU ...      CPU time limit exceeded (RLIMIT_CPU)
  error: local executor — SIGKILL ...      killed by OOM or external signal
  error: local executor — wall-clock ...   subprocess.timeout exceeded
  error: local executor — exit code N      non-zero exit for other reasons
  error: local executor — killed by SIG*   other kill signal

  Note: RLIMIT_AS (virtual address space) is applied on Linux only. On macOS
  and other platforms, only the wall-clock timeout and RLIMIT_CPU are used.
  Python itself uses ~100-200 MiB of virtual address space at startup; set
  --mem-limit-mib above 300 to avoid killing the interpreter before the user
  script runs.

In all modes anything other than `ok` indicates a failed or truncated
measurement. For resource-limit probes (TC-1/TC-2/TC-3) partial stdout is
the primary signal — check the last printed line against the script's markers,
not just the exit status code.

=== Status priority (worst first, i.e. lowest index = highest severity) ===

1. script_tampered       — submitted script was modified before execution
2. agent emitted text alongside executable_code — LLM prose leaked into run
3. canary_verification_failed — proof-of-execution check failed
4. agent emitted no executable_code — LLM did not invoke the tool
5. executor produced no result — code submitted but result missing
6. executor outcome <OUTCOME_*> — non-OK outcome from executor
7. error (<ExceptionType>): ... — runtime exception

`ok` is only reported when every per-script status is `ok`.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Make sibling modules importable when this file is invoked as a script
# (e.g. `python scripts/spike/sandbox_test_harness.py ...` per the runbook).
# Without this, `from canary_verifier import ...` raises ModuleNotFoundError
# because the script's own directory is on sys.path[0] but the package
# `scripts.spike` is not — the runbook's documented AC-6 smoke depends on
# this working.
sys.path.insert(0, str(Path(__file__).parent))

from canary_verifier import verify_canary

# Status severity ordering — lower index = higher severity (worse).
# Aggregate status picks the highest-severity non-ok status observed.
_STATUS_SEVERITY: list[str] = [
    "script_tampered",
    "agent emitted text alongside executable_code",
    "canary_verification_failed",
    "agent emitted no executable_code",
    "executor produced no result",
    "executor outcome",
]


def _status_severity_key(status: str) -> int:
    """Return a sortable severity key — lower = worse.

    Unknown statuses (including generic `error (...)` strings) are treated as
    medium severity (between `executor produced no result` and `ok`).

    NOTE: `"ok"` returns the same key as unknown error strings
    (`len(_STATUS_SEVERITY)`). This is intentional and only safe because
    `_worst_status` filters out `"ok"` before sorting. Do not call this
    function directly on raw status strings without that pre-filter, or
    `"ok"` will be ranked the same as an uncategorised error.
    """
    prefix = status.split("(")[0].strip().removeprefix("error: ").strip()
    for i, known in enumerate(_STATUS_SEVERITY):
        if prefix == known or status.startswith(f"error: {known}"):
            return i
    # Generic error or unexpected string — worse than ok, better than the named ones.
    return len(_STATUS_SEVERITY)


def _worst_status(*statuses: str) -> str:
    """Return the highest-severity (worst) status from the given set."""
    non_ok = [s for s in statuses if s != "ok"]
    if not non_ok:
        return "ok"
    return min(non_ok, key=_status_severity_key)


def _import_adk() -> tuple[Any, ...]:
    """Return (LlmAgent, AgentEngineSandboxCodeExecutor, Runner, InMemorySessionService, InMemoryArtifactService, types).

    Raises SystemExit with an actionable message if any import fails so the
    caller sees a clear directive rather than an unhandled traceback.
    """
    try:
        from google.adk.agents.llm_agent import LlmAgent  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        sys.exit(
            f"[harness] google-adk not found — run `uv sync` on the "
            f"spike/agent-engine-sandbox branch first.\nUnderlying error: {exc}"
        )

    try:
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (  # type: ignore[import-untyped]
            AgentEngineSandboxCodeExecutor,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        sys.exit(
            f"[harness] AgentEngineSandboxCodeExecutor not found in google-adk 1.27.5.\n"
            f"The symbol is documented as 'ADK v1.25.0+, experimental'; if it is absent "
            f"at 1.27.5, re-pin to the smallest version that exports it and document "
            f"the new pin in pyproject.toml, app/adk/pyproject.toml, "
            f"app/adk/requirements.txt, and this docstring.\n"
            f"Underlying error: {exc}"
        )

    from google.adk.artifacts.in_memory_artifact_service import (
        InMemoryArtifactService,  # type: ignore[import-untyped]
    )
    from google.adk.runners import Runner  # type: ignore[import-untyped]
    from google.adk.sessions.in_memory_session_service import (
        InMemorySessionService,  # type: ignore[import-untyped]
    )
    from google.genai import types  # type: ignore[import-untyped]

    return (
        LlmAgent,
        AgentEngineSandboxCodeExecutor,
        Runner,
        InMemorySessionService,
        InMemoryArtifactService,
        types,
    )


def _validate_script(script_path: Path) -> str:
    """Read and validate the script; return its text content.

    Guards against non-Python files and basic injection patterns by running
    compile() before forwarding to the LLM — any syntax error surfaces here
    rather than confusingly inside the sandbox.
    """
    if script_path.suffix != ".py":
        sys.exit(
            f"[harness] --script must point to a .py file (got '{script_path.suffix}'). "
            "Note: script content is transmitted to Vertex AI."
        )
    content = script_path.read_text(encoding="utf-8")
    try:
        compile(content, str(script_path), "exec")
    except SyntaxError as exc:
        sys.exit(f"[harness] Script has a syntax error — fix before running: {exc}")
    return content


def _sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _write_diff_sidecar(expected: str, observed: str) -> str:
    """Write a unified diff of expected vs observed code to a temp file.

    Returns the path so the harness can print it inline for the operator.
    The sidecar approach keeps the stdout schema stable (multi-line diffs would
    corrupt the Q* fragment paste-targets) while preserving the actionable
    evidence.
    """
    diff_lines = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            observed.splitlines(keepends=True),
            fromfile="expected (submitted)",
            tofile="observed (executed)",
        )
    )
    diff_text = "".join(diff_lines) if diff_lines else "(no diff output — strings equal by splitlines but differ by bytes)\n"
    fd, diff_path = tempfile.mkstemp(prefix="harness_tampered_", suffix=".diff")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(diff_text)
    except OSError:
        return "(failed to write diff sidecar)"
    return diff_path


def _check_script_tampering(
    script_content: str,
    captured_code_parts: list[str],
) -> str | None:
    """Compare each captured executable_code part against the submitted script.

    Returns a `script_tampered` error string (with diff-sidecar path) if any
    mismatch is found, or None if every captured part matches byte-for-byte.

    A SHA-256 would obscure *where* the script was modified. Using direct
    string comparison lets the diff sidecar show the exact mutation.

    CAUTION (legacy-llm-loop only): byte-for-byte equality can false-positive
    if Gemini's executor normalises whitespace (trailing newlines, line-ending
    rewrites, indent changes around fenced code blocks). Direct mode (the
    default) is unaffected because the script string is passed straight to
    the sandbox API. If a `script_tampered` error reports a diff that contains
    only whitespace mutations under --legacy-llm-loop, re-run with --direct
    to confirm it's a transport artifact rather than real tampering.
    """
    for observed in captured_code_parts:
        if observed != script_content:
            diff_path = _write_diff_sidecar(script_content, observed)
            exp_short = _sha256_short(script_content)
            obs_short = _sha256_short(observed)
            return (
                f"error: script_tampered "
                f"(expected={exp_short}, observed={obs_short}, diff={diff_path})"
            )
    return None


def _parse_sandbox_outputs(outputs: list[Any]) -> tuple[str, str]:
    """Parse Vertex AI sandbox execute_code outputs into (stdout, stderr).

    Mirrors the parsing logic in AgentEngineSandboxCodeExecutor.execute_code()
    so direct-mode output is consistent with the ADK-mediated path.
    """
    stdout = ""
    stderr = ""
    for output in outputs or []:
        if output.mime_type == "application/json" and (
            output.metadata is None
            or output.metadata.attributes is None
            or "file_name" not in output.metadata.attributes
        ):
            try:
                data = json.loads(output.data.decode("utf-8"))
                stdout = data.get("msg_out", "")
                stderr = data.get("msg_err", "")
            except (json.JSONDecodeError, AttributeError):
                pass
    return stdout, stderr


async def _run_one_message(
    runner: Any,
    session_id: str,
    script_path: Path,
    types: Any,
) -> tuple[str, str]:
    """Send one script as a user message and return (stdout, status).

    Called for each --script path in the same session so the Python
    interpreter's state persists across messages (SK-4 Q3 same-session probe).

    AC-1: captures part.executable_code.code for byte-for-byte tampering check.
    AC-2: detects free LLM text parts alongside executable_code parts.
    Status priority: script_tampered > text_leakage > no_executable_code >
                     no_result > bad_outcome > ok.
    """
    script_content = _validate_script(script_path)

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=f"Execute this Python script:\n```python\n{script_content}\n```")],
    )

    llm_text_parts: list[str] = []
    executor_stdout_parts: list[str] = []
    captured_code_parts: list[str] = []  # AC-1: capture for tampering check
    executable_code_seen = False
    code_execution_result_seen = False
    executor_outcome: str | None = None
    try:
        async for event in runner.run_async(
            user_id="spike_user",
            session_id=session_id,
            new_message=user_message,
        ):
            if not (hasattr(event, "content") and event.content):
                continue
            for part in event.content.parts or []:
                ec = getattr(part, "executable_code", None)
                if ec is not None:
                    executable_code_seen = True
                    # AC-1: record the exact code the model sent to the executor.
                    # A None .code field is treated as an empty string so that
                    # _check_script_tampering always fires when ec was present
                    # (an ec with no code is guaranteed ≠ any real script).
                    code_text = getattr(ec, "code", None)
                    captured_code_parts.append(str(code_text) if code_text is not None else "")
                result = getattr(part, "code_execution_result", None)
                if result is not None:
                    code_execution_result_seen = True
                    outcome = getattr(result, "outcome", None)
                    if outcome is not None:
                        executor_outcome = getattr(outcome, "name", str(outcome))
                    output_text = getattr(result, "output", None)
                    if output_text:
                        executor_stdout_parts.append(str(output_text))
                text = getattr(part, "text", None)
                if text:
                    llm_text_parts.append(text)
    except Exception as exc:
        return "", (
            f"error ({type(exc).__name__}): agent run failed — {exc}\n"
            f"Check that the service account has roles/aiplatform.user and "
            f"that the sandbox resource exists."
        )

    # Prefer executor stdout over LLM commentary — see module docstring.
    captured_output = (
        "\n".join(executor_stdout_parts)
        if executor_stdout_parts
        else "\n".join(llm_text_parts)
    )

    # AC-1: tampering check — highest severity, checked first.
    if captured_code_parts:
        tamper_error = _check_script_tampering(script_content, captured_code_parts)
        if tamper_error:
            return captured_output, tamper_error

    # AC-2: text-leakage detection — LLM prose alongside code is a measurement failure.
    if executable_code_seen and llm_text_parts:
        return captured_output, "error: agent emitted text alongside executable_code"

    if not executable_code_seen:
        return captured_output, "error: agent emitted no executable_code"
    if not code_execution_result_seen:
        return captured_output, "error: executor produced no result"
    if executor_outcome and executor_outcome not in {"OUTCOME_OK", "OK"}:
        return captured_output, f"error: executor outcome {executor_outcome}"

    return captured_output, "ok"


async def _run_scripts(
    script_paths: list[Path],
    sandbox_resource_name: str,
    project: str,
    location: str,
    model: str,
) -> tuple[list[tuple[str, str]], str]:
    """Execute *script_paths* sequentially via LlmAgent + Gemini model.

    CAUTION — legacy LLM-loop mode. Use direct mode (the default) for
    empirical measurements. See module docstring and
    docs/spike/harness-validation.md for the full failure evidence.

    Requires: aiplatform.endpoints.predict + aiplatform.sandboxEnvironments.*

    AC-2 knob applied: generate_content_config.tool_config.function_calling_config
    .mode = "ANY" (force tool use). This is the primary knob identified in ADK
    1.27.5 — see the "ADK 1.27.5 text-suppression surface" section above.

    Returns a list of (stdout, status) per script and an aggregate status.
    The aggregate is the highest-severity non-ok status observed (or "ok" when
    all scripts pass). This matches the SK-4 Q3 design: both writer and reader
    execute inside a single AgentEngineSandboxCodeExecutor session so the Python
    interpreter's state persists across them — the closest available proxy for
    two skills attached to one specialist.
    """
    (
        LlmAgent,
        AgentEngineSandboxCodeExecutor,
        Runner,
        InMemorySessionService,
        InMemoryArtifactService,
        types,
    ) = _import_adk()

    # Initialise the Vertex AI client so --project and --location are honoured.
    # If vertexai is missing, fall back to ADC defaults — but emit a stderr
    # warning so the operator knows --project/--location were silently ignored
    # (the previous silent-pass swallow contradicted the "actually honoured"
    # comment that used to live here; PR #636 review caught the inconsistency).
    try:
        import vertexai  # type: ignore[import-untyped]

        vertexai.init(project=project, location=location)
    except ImportError as exc:
        print(
            f"[harness] WARNING: vertexai SDK not importable ({exc}); "
            f"--project and --location flags will NOT be honoured for this run "
            f"(falling back to ADC defaults). Install google-cloud-aiplatform "
            f"to silence.",
            file=sys.stderr,
        )

    # Route to the correct ADK kwarg based on resource name format.
    # ADK 1.27.5 __init__ signature:
    #   sandbox_resource_name:      …/sandboxEnvironments/<id>
    #   agent_engine_resource_name: …/reasoningEngines/<id>
    try:
        if "/sandboxEnvironments/" in sandbox_resource_name:
            sandbox_executor = AgentEngineSandboxCodeExecutor(
                sandbox_resource_name=sandbox_resource_name,
            )
        else:
            sandbox_executor = AgentEngineSandboxCodeExecutor(
                agent_engine_resource_name=sandbox_resource_name,
            )
    except Exception as exc:
        error_status = f"error ({type(exc).__name__}): could not construct AgentEngineSandboxCodeExecutor: {exc}"
        return [("", error_status)] * len(script_paths), error_status

    # AC-2: apply force-tool-use config so the model cannot emit free-form text.
    # generate_content_config.tool_config.function_calling_config.mode = "ANY"
    # is the primary knob in ADK 1.27.5 (see module docstring).
    # The LlmAgent validator (llm_agent.py:857-874) blocks `tools`,
    # `system_instruction`, and `response_schema` but NOT `tool_config`.
    try:
        force_tool_config = types.GenerateContentConfig(
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY
                )
            )
        )
    except Exception as exc:
        # AC-2 surface unavailable — most likely an ADK type change. Emit a
        # loud stderr warning rather than silently disabling text-suppression
        # (silent fallback would re-expose every hallucination failure mode
        # the rework was built to prevent).
        print(
            f"[harness] WARNING: force-tool-use config could not be "
            f"constructed ({type(exc).__name__}: {exc}). "
            f"Text-suppression knob (FunctionCallingConfigMode.ANY) is DISABLED for "
            f"this run; legacy-llm-loop mode reverts to the pre-AC-2 hallucination-prone "
            f"behaviour. Verify your google-adk / google-genai versions match the "
            f"pin in pyproject.toml.",
            file=sys.stderr,
        )
        force_tool_config = None

    agent_kwargs: dict[str, Any] = {
        "name": "spike_sandbox_agent",
        "model": model,
        "instruction": (
            "You are a test agent for a sandbox spike. "
            "When the user sends you a Python script, execute it using your "
            "code execution tool and return the stdout verbatim. "
            "Do not explain or modify the script."
        ),
        "code_executor": sandbox_executor,
    }
    if force_tool_config is not None:
        agent_kwargs["generate_content_config"] = force_tool_config

    agent = LlmAgent(**agent_kwargs)

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="spike_harness",
        user_id="spike_user",
    )

    runner = Runner(
        agent=agent,
        app_name="spike_harness",
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
    )

    results: list[tuple[str, str]] = []
    aggregate_status = "ok"
    for script_path in script_paths:
        stdout, status = await _run_one_message(
            runner=runner,
            session_id=session.id,
            script_path=script_path,
            types=types,
        )
        # AC-3: canary proof-of-execution verification (kept symmetric with
        # _run_direct_scripts so legacy-llm-loop is no less defended). The
        # filename match is the contract: if the canary fixture is renamed,
        # this dispatch must be updated. Worth noting that legacy mode is
        # exactly where Vertex's stub-OUTCOME_OK hypothesis (harness-validation.md
        # §Hypotheses #3) is most likely to fire, so the symmetric check is
        # specifically load-bearing here.
        if status == "ok" and script_path.name == "hello.py":
            verified, reason = verify_canary(stdout)
            if not verified:
                status = f"error: canary_verification_failed: {reason}"
        results.append((stdout, status))
        aggregate_status = _worst_status(aggregate_status, status)

    return results, aggregate_status


async def _run_direct_scripts(
    script_paths: list[Path],
    sandbox_resource_name: str,
    project: str,
    location: str,
) -> tuple[list[tuple[str, str]], str]:
    """Execute *script_paths* directly via the Vertex AI sandbox API.

    Bypasses LlmAgent and the Gemini model entirely — the script is sent
    straight to the sandbox's execute_code API endpoint. This is the DEFAULT
    mode; it removes every hallucination failure mode documented in
    docs/spike/harness-validation.md.

    Requires: aiplatform.sandboxEnvironments.* ONLY.
    Does NOT require: aiplatform.endpoints.predict (Gemini model access).

    Each script runs in the same sandbox session so Python interpreter state
    persists across invocations (mirrors the LlmAgent multi-script behaviour
    for SK-4 Q3). A new sandbox is created from agent_engine_resource_name
    (reasoningEngines/<id> path) or reused from sandbox_resource_name
    (sandboxEnvironments/<id> path).

    Status strings differ from LlmAgent mode:
      ok                              execute_code API call completed
      error (<ExceptionType>): ...    execute_code API call raised
      error: executor produced no result  API returned empty outputs

    For resource-limit probes the exit status is secondary — the primary
    signal is the last printed line in stdout (see module docstring).
    """
    try:
        import vertexai  # type: ignore[import-untyped]
        from vertexai import types as vertex_types  # type: ignore[import-untyped]
    except ImportError as exc:
        error_status = f"error (ImportError): vertexai SDK not found — run `uv sync` first: {exc}"
        return [("", error_status)] * len(script_paths), error_status

    try:
        # Match the ADK executor pattern: Client(project, location) only.
        # Do NOT call vertexai.init() first — it sets global state that may
        # conflict with the Client's own credential resolution path.
        client = vertexai.Client(project=project, location=location)
    except Exception as exc:
        error_status = f"error ({type(exc).__name__}): could not initialise Vertex AI client: {exc}"
        return [("", error_status)] * len(script_paths), error_status

    # Resolve sandbox name — create a new sandbox if given a reasoningEngines/ path.
    resolved_sandbox: str
    if "/sandboxEnvironments/" in sandbox_resource_name:
        # Pre-provisioned sandbox — use directly.
        resolved_sandbox = sandbox_resource_name
    else:
        # Create a new sandbox under the given Agent Engine resource.
        # wait_for_completion defaults to True; create() blocks until the
        # sandbox is STATE_RUNNING and re-fetches the resource before returning.
        # If the SA lacks aiplatform.sandboxEnvironments.create this raises here.
        try:
            operation = client.agent_engines.sandboxes.create(
                spec={"code_execution_environment": {}},
                name=sandbox_resource_name,
                config=vertex_types.CreateAgentEngineSandboxConfig(
                    display_name="spike_direct",
                ),
            )
            # operation.response is re-fetched by the SDK after wait_for_completion;
            # operation.response.name is the sandbox resource name.
            if not operation.response or not operation.response.name:
                error_status = "error: sandbox creation returned no resource name"
                return [("", error_status)] * len(script_paths), error_status
            resolved_sandbox = operation.response.name
        except Exception as exc:
            error_status = (
                f"error ({type(exc).__name__}): sandbox creation failed — {exc}\n"
                f"Check that the service account has aiplatform.sandboxEnvironments.create "
                f"on {sandbox_resource_name}."
            )
            return [("", error_status)] * len(script_paths), error_status

    results: list[tuple[str, str]] = []
    aggregate_status = "ok"

    for script_path in script_paths:
        script_content = _validate_script(script_path)
        try:
            # execute_code is a synchronous blocking call. Calling it inside an
            # async function blocks the event loop for the duration of the sandbox
            # run (up to several minutes for TC-3). This is intentional for the
            # spike harness: asyncio.run() uses a single-threaded loop with nothing
            # else waiting, so no tasks are starved. Ctrl+C will be unresponsive
            # during a long sandbox run — kill the process with SIGTERM if needed.
            response = client.agent_engines.sandboxes.execute_code(
                name=resolved_sandbox,
                input_data={"code": script_content},
            )
            outputs = getattr(response, "outputs", None) or []
            if not outputs:
                stdout, status = "", "error: executor produced no result"
            else:
                stdout, stderr = _parse_sandbox_outputs(outputs)
                # Include stderr in the output so resource-limit kill signals
                # (which may arrive via msg_err, not msg_out) are not silently
                # discarded. TC-1 / TC-3 failure signals may appear in stderr.
                if stderr:
                    stdout = (stdout + f"\n[stderr] {stderr}") if stdout else f"[stderr] {stderr}"
                status = "ok"
        except Exception as exc:
            stdout = ""
            status = (
                f"error ({type(exc).__name__}): execute_code call failed — {exc}\n"
                f"Check that the service account has aiplatform.sandboxEnvironments.* "
                f"on {resolved_sandbox}."
            )

        # AC-3: canary proof-of-execution verification. The filename match
        # is the contract: if the canary fixture is renamed, this dispatch
        # and the _run_scripts symmetric dispatch must both be updated.
        # canary_verifier.verify_canary recomputes the SHA-256 from
        # time_ns + urandom_hex and checks big_int_check == 2**73 - 1 — any
        # hallucinated stub-OUTCOME_OK response will fail at least one check.
        if status == "ok" and script_path.name == "hello.py":
            verified, reason = verify_canary(stdout)
            if not verified:
                status = f"error: canary_verification_failed: {reason}"

        results.append((stdout, status))
        aggregate_status = _worst_status(aggregate_status, status)

    return results, aggregate_status


def _run_local_scripts_with_limits(
    script_paths: list[Path],
    *,
    cpu_limit_s: int,
    mem_limit_mib: int,
    wall_clock_timeout_s: int,
) -> tuple[list[tuple[str, str]], str]:
    """Execute scripts locally with OS-level resource limits.

    Each script runs in an isolated subprocess.  Three limits are applied:

    * RLIMIT_CPU (CPU time, seconds) via `resource.setrlimit` — sends SIGXCPU
      when the soft limit is reached.  Supported on Linux and macOS.
    * RLIMIT_AS (virtual address space) via `resource.setrlimit` — prevents
      allocations beyond `mem_limit_mib` MiB.  Linux only; silently skipped on
      macOS / other platforms.  Python itself uses ~100-200 MiB of virtual AS
      at startup, so set this above 300 MiB to avoid killing the interpreter.
    * Wall-clock timeout via `subprocess.run(timeout=...)` — catches scripts
      that idle-sleep past the CPU limit (e.g. q4_wall_clock.py sleep probes).

    No Vertex AI credentials or network access required.  Output format is
    identical to the Vertex AI modes; the summary block labels results as
    LOCAL MODE so they are clearly distinguishable in the Q4 fragment.
    """
    is_linux = platform.system() == "Linux"

    def _preexec_fn() -> None:
        # CPU time limit — Linux and macOS.
        # Hard limit is soft+1 so SIGXCPU fires at the soft limit (before SIGKILL at hard).
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_s, cpu_limit_s + 1))
        except (OSError, ValueError):
            pass
        # Virtual address space limit — Linux only.
        if is_linux:
            mem_bytes = mem_limit_mib * 1024 * 1024
            try:
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            except (OSError, ValueError):
                pass

    results: list[tuple[str, str]] = []
    aggregate_status = "ok"

    for script_path in script_paths:
        stdout_text = ""
        status: str
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=wall_clock_timeout_s,
                preexec_fn=_preexec_fn,
                # Strip GCP credentials and API tokens; probe scripts only need PATH.
                env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
            )
            stdout_text = proc.stdout or ""
            stderr_text = (proc.stderr or "").strip()
            if stderr_text:
                stderr_line = f"[stderr] {stderr_text}"
                stdout_text = (
                    (stdout_text + "\n" + stderr_line) if stdout_text else stderr_line
                )
            if proc.returncode == 0:
                status = "ok"
            elif proc.returncode < 0:
                sig_num = -proc.returncode
                try:
                    sig_name = signal.Signals(sig_num).name
                except ValueError:
                    sig_name = f"signal {sig_num}"
                if sig_num == getattr(signal, "SIGXCPU", None):
                    status = (
                        f"error: local executor — {sig_name} "
                        f"(CPU time limit {cpu_limit_s}s exceeded)"
                    )
                else:
                    status = (
                        f"error: local executor — killed by {sig_name} "
                        f"(OOM or external kill)"
                    )
            else:
                status = f"error: local executor — exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            # TimeoutExpired.stdout may be bytes even when text=True is set (CPython
            # implementation detail — partial output is not always decoded on timeout).
            raw = exc.stdout or b""
            stdout_text = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            status = (
                f"error: local executor — wall-clock timeout "
                f"({wall_clock_timeout_s}s)"
            )
        except Exception as exc:
            status = (
                f"error ({type(exc).__name__}): local execution failed — {exc}"
            )

        results.append((stdout_text, status))
        aggregate_status = _worst_status(aggregate_status, status)

    return results, aggregate_status


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sandbox_test_harness",
        description=(
            "SK-PRD-00 spike: run one or more Python scripts through "
            "AgentEngineSandboxCodeExecutor and capture stdout. "
            "DEFAULT mode: direct (bypasses LlmAgent, recommended for "
            "empirical measurements). "
            "See module docstring for full usage and mode explanations."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--script",
        required=True,
        action="append",
        dest="scripts",
        metavar="PATH",
        help=(
            "Path to a .py script to execute inside the sandbox. "
            "Repeat to run multiple scripts sequentially within the same "
            "sandbox session (SK-4 Q3 cross-skill probe). "
            "Script content is transmitted to Vertex AI."
        ),
    )
    # Resolve default: a KENE_SPIKE_SANDBOX_RESOURCE_NAME value that contains
    # /sandboxEnvironments/ wins over KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME so
    # the harness can skip sandbox creation (aiplatform.sandboxEnvironments.create)
    # when a pre-provisioned sandbox is available.
    _engine_name = (os.environ.get("KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME") or "").strip()
    _sandbox_env = (os.environ.get("KENE_SPIKE_SANDBOX_RESOURCE_NAME") or "").strip()
    _default_resource = (
        _sandbox_env if "/sandboxEnvironments/" in _sandbox_env else _engine_name or _sandbox_env
    )
    parser.add_argument(
        "--sandbox-resource-name",
        default=_default_resource,
        metavar="RESOURCE",
        help=(
            "Vertex AI resource name. "
            "Accepts .../reasoningEngines/<id> (creates a sandbox on first use; "
            "requires aiplatform.sandboxEnvironments.create) or "
            ".../sandboxEnvironments/<sid> (uses pre-existing sandbox; skips create). "
            "$KENE_SPIKE_SANDBOX_RESOURCE_NAME takes priority when it is a "
            "sandboxEnvironments/ path; otherwise $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME "
            "is used (fallback: $KENE_SPIKE_SANDBOX_RESOURCE_NAME)."
        ),
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        metavar="PROJECT_ID",
        help="GCP project id. Defaults to $GOOGLE_CLOUD_PROJECT.",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("VERTEX_AI_LOCATION", "us-central1"),
        metavar="REGION",
        help="Vertex AI region. Defaults to $VERTEX_AI_LOCATION (fallback: us-central1).",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        metavar="MODEL",
        help=(
            "Gemini model to use in --legacy-llm-loop mode. "
            "Default: gemini-2.5-flash. "
            "For AC-6 smoke runs, test against all three pins: "
            "gemini-2.0-flash (validated hallucination-prone in harness-validation.md), "
            "gemini-2.5-flash (default), gemini-2.5-pro (strongest tool-use). "
            "The canary (hello.py) MUST pass on the chosen model before any "
            "measurement probe is run. "
            "Ignored when direct mode (default) is used."
        ),
    )
    parser.add_argument(
        "--legacy-llm-loop",
        action="store_true",
        default=False,
        help=(
            "CAUTION: route scripts through LlmAgent + Gemini instead of calling "
            "the sandbox API directly. This mode can produce hallucinated results "
            "even with the force-tool-use config applied — see "
            "docs/spike/harness-validation.md for full failure evidence (Runs 1-4). "
            "For empirical measurements use the default direct mode. "
            "Requires: aiplatform.endpoints.predict + aiplatform.sandboxEnvironments.*"
        ),
    )
    parser.add_argument(
        "--local-limits",
        action="store_true",
        default=False,
        help=(
            "Run scripts locally in isolated subprocesses with OS-level "
            "resource limits (RLIMIT_CPU, RLIMIT_AS on Linux, wall-clock "
            "timeout). No Vertex AI credentials required. Results are labelled "
            "LOCAL MODE. Use when aiplatform.sandboxEnvironments.* permissions "
            "are unavailable. See --cpu-limit-s, --mem-limit-mib, "
            "--wall-clock-timeout-s."
        ),
    )
    parser.add_argument(
        "--cpu-limit-s",
        type=int,
        default=10,
        metavar="SECONDS",
        help=(
            "CPU time limit in seconds applied via RLIMIT_CPU when "
            "--local-limits is set. The subprocess receives SIGXCPU at this "
            "limit. Default: 10."
        ),
    )
    parser.add_argument(
        "--mem-limit-mib",
        type=int,
        default=1024,
        metavar="MIB",
        help=(
            "Virtual address space limit in MiB applied via RLIMIT_AS "
            "(Linux only) when --local-limits is set. Python itself uses "
            "~100-200 MiB of virtual AS; set this above 300 to avoid killing "
            "the interpreter before user code runs. Default: 1024."
        ),
    )
    parser.add_argument(
        "--wall-clock-timeout-s",
        type=int,
        default=120,
        metavar="SECONDS",
        help=(
            "Wall-clock timeout in seconds applied via subprocess.run(timeout=) "
            "when --local-limits is set. Acts as a backstop for idle-sleep "
            "probes that would not be caught by RLIMIT_CPU. Default: 120."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Warn if --legacy-llm-loop is used — it's the mode that produced the
    # hallucinated results documented in harness-validation.md.
    if args.legacy_llm_loop:
        print(
            "[harness] WARNING: --legacy-llm-loop mode selected. "
            "This mode can produce hallucinated results even with force-tool-use config. "
            "For empirical measurements use the default direct mode.",
            file=sys.stderr,
        )

    script_paths: list[Path] = []
    for raw in args.scripts:
        p = Path(raw)
        if not p.is_file():
            sys.exit(f"[harness] Script not found: {p}")
        script_paths.append(p)

    # --local-limits does not need Vertex AI credentials or a sandbox resource.
    if not args.local_limits:
        if not args.sandbox_resource_name:
            sys.exit(
                "[harness] Sandbox resource name is required. "
                "Set $KENE_SPIKE_SANDBOX_RESOURCE_NAME to a .../sandboxEnvironments/<id> path "
                "(preferred; skips sandbox creation) or $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME "
                "to a reasoningEngines/<id> path (creates a sandbox on first use), "
                "or pass --sandbox-resource-name.  "
                "To run without Vertex AI credentials use --local-limits."
            )
        if not args.project:
            sys.exit(
                "[harness] GCP project id is required. "
                "Set $GOOGLE_CLOUD_PROJECT or pass --project.  "
                "To run without Vertex AI credentials use --local-limits."
            )

    t0 = time.monotonic()

    if args.local_limits:
        results, aggregate_status = _run_local_scripts_with_limits(
            script_paths=script_paths,
            cpu_limit_s=args.cpu_limit_s,
            mem_limit_mib=args.mem_limit_mib,
            wall_clock_timeout_s=args.wall_clock_timeout_s,
        )
    elif args.legacy_llm_loop:
        results, aggregate_status = asyncio.run(
            _run_scripts(
                script_paths=script_paths,
                sandbox_resource_name=args.sandbox_resource_name,
                project=args.project,
                location=args.location,
                model=args.model,
            )
        )
    else:
        # Default: direct mode (bypasses LlmAgent entirely).
        results, aggregate_status = asyncio.run(
            _run_direct_scripts(
                script_paths=script_paths,
                sandbox_resource_name=args.sandbox_resource_name,
                project=args.project,
                location=args.location,
            )
        )
    elapsed = time.monotonic() - t0

    try:
        adk_version = importlib.metadata.version("google-adk")
    except importlib.metadata.PackageNotFoundError:
        adk_version = "n/a (not installed)"

    for i, (script_path, (stdout, status)) in enumerate(
        zip(script_paths, results, strict=True), start=1
    ):
        label = f"[{i}/{len(script_paths)}] {script_path.name}"
        if stdout:
            print(f"=== {label} stdout ===")
            print(stdout)
        print(f"=== {label} status: {status} ===")

    print("---")
    print(f"ADK version  : {adk_version}")
    if args.local_limits:
        print(
            f"Sandbox      : LOCAL MODE (cpu={args.cpu_limit_s}s "
            f"mem={args.mem_limit_mib}MiB wall-clock={args.wall_clock_timeout_s}s)"
        )
        print("Mode         : local-limits (subprocess + OS resource limits)")
    else:
        print(f"Sandbox      : {args.sandbox_resource_name}")
        if args.legacy_llm_loop:
            print(f"Mode         : legacy-llm-loop (LlmAgent, model={args.model})")
        else:
            print("Mode         : direct (no LlmAgent)")
    print(f"Scripts      : {len(script_paths)}")
    print(f"Elapsed (s)  : {elapsed:.2f}")
    print(f"Exit status  : {aggregate_status}")

    if aggregate_status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
