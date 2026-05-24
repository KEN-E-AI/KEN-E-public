"""SK-PRD-00 spike harness — AgentEngineSandboxCodeExecutor evaluation.

Runs an arbitrary Python script through a Vertex AI Agent Engine sandbox so
SK-PRD-00 Q1-Q5 issues can measure network egress, cost, cross-skill state,
resource limits, and file I/O empirically.

ADK version pinned: google-adk==1.27.5 (spike/agent-engine-sandbox branch).
This branch is never merged to main (PRD §7 AC #1).

One-command reproduction:

    cd /home/agent/workspace
    uv run python scripts/spike/sandbox_test_harness.py \\
        --script scripts/spike/skills/hello.py

Required environment variables (see CLAUDE.md §Key Environment Variables):
    GOOGLE_CLOUD_PROJECT                  GCP project id
    VERTEX_AI_LOCATION                    e.g. us-central1
    KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME Vertex AI Agent Engine resource name
      e.g. projects/<proj>/locations/<loc>/reasoningEngines/<id>
      The executor lazily creates a sandboxEnvironment on first invocation.
    KENE_SPIKE_SANDBOX_RESOURCE_NAME      (legacy alias — backward compat only)
      e.g. projects/<proj>/locations/<loc>/reasoningEngines/<id>/sandboxEnvironments/<sid>
      Use KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME for new setups.

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

`Exit status` reflects what the harness observed in the ADK event stream, not
just whether the run completed without an exception:

  ok                                       executor produced a code_execution_result
  error: agent emitted no executable_code  LLM ignored the instruction or refused
  error: executor produced no result       code emitted but no result event observed
  error: executor outcome <OUTCOME_*>      executor ran but reported a non-OK outcome
  error (<ExceptionType>): ...             runner or executor raised

Downstream SK-PRD-00 issues (Q1-Q5) MUST treat anything other than `ok` as a
failed measurement — a clean traceback-free run does not imply the sandbox
actually executed anything.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import os
import sys
import time
from pathlib import Path
from typing import Any


def _import_adk() -> tuple[Any, ...]:
    """Return (LlmAgent, AgentEngineSandboxCodeExecutor, Runner, InMemorySessionService, types).

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

    from google.adk.runners import Runner  # type: ignore[import-untyped]
    from google.adk.sessions.in_memory_session_service import (
        InMemorySessionService,  # type: ignore[import-untyped]
    )
    from google.genai import types  # type: ignore[import-untyped]

    return LlmAgent, AgentEngineSandboxCodeExecutor, Runner, InMemorySessionService, types


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


async def _run_script(
    script_path: Path,
    sandbox_resource_name: str,
    project: str,
    location: str,
    model: str,
) -> tuple[str, str]:
    """Execute *script_path* through the sandbox and return (stdout, status).

    One sandbox session per invocation — this harness is intentionally
    single-shot so SK-3 (cost measurement) controls its own call volume.
    """
    LlmAgent, AgentEngineSandboxCodeExecutor, Runner, InMemorySessionService, types = _import_adk()

    script_content = _validate_script(script_path)

    # Initialise the Vertex AI client with the explicit project + location so
    # --project and --location flags are actually honoured rather than silently
    # falling through to ADC defaults.
    try:
        import vertexai  # type: ignore[import-untyped]

        vertexai.init(project=project, location=location)
    except ImportError:
        pass  # vertexai may not be installed; ADC defaults will be used

    # Route to the correct ADK kwarg based on resource name format.
    # ADK 1.27.5 __init__ signature:
    #   sandbox_resource_name:      …/sandboxEnvironments/<id>
    #   agent_engine_resource_name: …/reasoningEngines/<id>
    # Passing resource_name= (wrong kwarg) falls through **data and raises
    # ValueError: Either sandbox_resource_name or agent_engine_resource_name must be set.
    try:
        if "/sandboxEnvironments/" in sandbox_resource_name:
            sandbox_executor = AgentEngineSandboxCodeExecutor(
                sandbox_resource_name=sandbox_resource_name,
            )
        else:
            # reasoningEngines/<id> format — lazily creates a sandboxEnvironment
            sandbox_executor = AgentEngineSandboxCodeExecutor(
                agent_engine_resource_name=sandbox_resource_name,
            )
    except Exception as exc:
        return "", f"error ({type(exc).__name__}): could not construct AgentEngineSandboxCodeExecutor: {exc}"

    agent = LlmAgent(
        name="spike_sandbox_agent",
        model=model,
        instruction=(
            "You are a test agent for a sandbox spike. "
            "When the user sends you a Python script, execute it using your "
            "code execution tool and return the stdout verbatim. "
            "Do not explain or modify the script."
        ),
        code_executor=sandbox_executor,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="spike_harness",
        user_id="spike_user",
    )

    runner = Runner(
        agent=agent,
        app_name="spike_harness",
        session_service=session_service,
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=f"Execute this Python script:\n```python\n{script_content}\n```")],
    )

    # We track three independent signals so the final status reflects what
    # actually happened, not just whether the run threw:
    #   - executable_code parts  -> the LLM emitted code
    #   - code_execution_result  -> the executor returned a result
    #   - outcome on that result -> the executor reported OUTCOME_OK
    # A run that completes without ever invoking the executor would otherwise
    # be reported as `ok`, distorting every SK-PRD-00 Q1-Q5 measurement built
    # on this harness.
    llm_text_parts: list[str] = []
    executor_stdout_parts: list[str] = []
    executable_code_seen = False
    code_execution_result_seen = False
    executor_outcome: str | None = None
    try:
        async for event in runner.run_async(
            user_id="spike_user",
            session_id=session.id,
            new_message=user_message,
        ):
            if not (hasattr(event, "content") and event.content):
                continue
            for part in event.content.parts or []:
                if getattr(part, "executable_code", None) is not None:
                    executable_code_seen = True
                result = getattr(part, "code_execution_result", None)
                if result is not None:
                    code_execution_result_seen = True
                    outcome = getattr(result, "outcome", None)
                    if outcome is not None:
                        # outcome may be an enum (.name) or a string.
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
            f"that the sandbox resource '{sandbox_resource_name}' exists in "
            f"project '{project}', location '{location}'."
        )

    # Prefer executor stdout over LLM commentary so Q1-Q5 measurements are not
    # contaminated by the model paraphrasing the output. Fall back to LLM text
    # only when the executor produced no captured output (e.g., scripts that
    # print nothing) so the operator still sees what the agent said.
    captured_output = (
        "\n".join(executor_stdout_parts)
        if executor_stdout_parts
        else "\n".join(llm_text_parts)
    )

    if not executable_code_seen:
        return captured_output, "error: agent emitted no executable_code"
    if not code_execution_result_seen:
        return captured_output, "error: executor produced no result"
    if executor_outcome and executor_outcome not in {"OUTCOME_OK", "OK"}:
        return captured_output, f"error: executor outcome {executor_outcome}"

    return captured_output, "ok"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sandbox_test_harness",
        description=(
            "SK-PRD-00 spike: run a Python script through AgentEngineSandboxCodeExecutor "
            "and capture stdout. See module docstring for full usage."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--script",
        required=True,
        metavar="PATH",
        help=(
            "Path to a .py script to execute inside the sandbox. "
            "Script content is transmitted to Vertex AI."
        ),
    )
    parser.add_argument(
        "--sandbox-resource-name",
        default=(
            (os.environ.get("KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME") or "").strip()
            or (os.environ.get("KENE_SPIKE_SANDBOX_RESOURCE_NAME") or "").strip()
        ),
        metavar="RESOURCE",
        help=(
            "Vertex AI resource name (reasoningEngines/<id> or .../sandboxEnvironments/<sid>). "
            "Defaults to $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME "
            "(fallback: $KENE_SPIKE_SANDBOX_RESOURCE_NAME)."
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
        default="gemini-2.0-flash",
        metavar="MODEL",
        help="Gemini model to use. Default: gemini-2.0-flash.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    script_path = Path(args.script)
    if not script_path.is_file():
        sys.exit(f"[harness] Script not found: {script_path}")

    if not args.sandbox_resource_name:
        sys.exit(
            "[harness] Sandbox resource name is required. "
            "Set $KENE_SPIKE_AGENT_ENGINE_RESOURCE_NAME (or legacy $KENE_SPIKE_SANDBOX_RESOURCE_NAME) "
            "or pass --sandbox-resource-name."
        )

    if not args.project:
        sys.exit(
            "[harness] GCP project id is required. "
            "Set $GOOGLE_CLOUD_PROJECT or pass --project."
        )

    t0 = time.monotonic()
    stdout, status = asyncio.run(
        _run_script(
            script_path=script_path,
            sandbox_resource_name=args.sandbox_resource_name,
            project=args.project,
            location=args.location,
            model=args.model,
        )
    )
    elapsed = time.monotonic() - t0

    adk_version = importlib.metadata.version("google-adk")

    if stdout:
        print(stdout)
    print("---")
    print(f"ADK version  : {adk_version}")
    print(f"Sandbox      : {args.sandbox_resource_name}")
    print(f"Elapsed (s)  : {elapsed:.2f}")
    print(f"Exit status  : {status}")

    if status != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
