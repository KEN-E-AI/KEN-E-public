"""OTEL production stability validation (local).

Closes the OTEL ``google-genai`` workaround probe and validates Sprint 6
ACs 6.14–6.17 in four sequential steps:

1. **Probe**: invoke a strategy formatter (``output_schema=Pydantic``) on
   ADK ≥1.27.4 with the ``google-genai`` OTEL instrumentation **enabled**.
   If the known ``model_dump()`` ``TypeError`` fires → Outcome A (bug
   still present, must keep workaround). Clean → Outcome B (bug fixed,
   workaround can be removed).

2. **Memory delta** (AC-6.14): spawn two subprocess runs of
   ``run_adk_stability.py --invocations 10``, one with
   ``OTEL_SDK_DISABLED=true`` and one with OTEL on. Compare peak RSS
   via the ``psutil`` sampler in ``memory_profiler.py``. Assert
   ``delta_pct < 10``.

3. **GenAI span coverage** (AC-6.15, 6.16): drive 50 ADK invocations
   inside ``TraceCapture``. Assert 100% of
   ``google.genai.models.AsyncModels.generate_content`` spans carry
   ``model_used`` and ``temperature``.

4. **Non-GenAI spans** (AC-6.17): same trace capture, assert at least
   one ``load_config_from_firestore`` (DB) span and at least one
   ``mcp.client.session.ClientSession.call_tool.*`` (HTTP) span show
   up across the 20+ invocation set.

The probe step also applies the consistency cleanup: based on outcome,
either re-enables the workaround everywhere (A) or strips it
everywhere and marks the spike doc resolved (B). Run with
``--no-apply-cleanup`` to skip the file mutations and only write the
JSON report.

Output: ``runs/run_otel_stability_<ts>.json`` plus a console summary.
Exit 0 only when **all four steps pass**.

Usage::

    cd /path/to/KEN-E
    PYTHONPATH=.:api/src uv run --project api python \
        tests/integration/stability/runs/run_otel_stability.py
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure repo root on sys.path so ``app.adk.*`` imports resolve.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_corpus() -> list[Any]:
    """Load the harness QueryCase corpus by file path (namespace dodge)."""
    module_name = "_harness_query_corpus_for_otel"
    if module_name in sys.modules:
        return sys.modules[module_name].QUERIES

    corpus_path = Path(__file__).resolve().parent.parent / "query_corpus.py"
    spec = importlib.util.spec_from_file_location(module_name, corpus_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load query corpus from {corpus_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.QUERIES


def _load_trace_capture() -> Any:
    module_name = "_harness_trace_capture_for_otel"
    if module_name in sys.modules:
        return sys.modules[module_name].TraceCapture

    cap_path = Path(__file__).resolve().parent.parent / "weave_trace_capture.py"
    spec = importlib.util.spec_from_file_location(module_name, cap_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load weave_trace_capture from {cap_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.TraceCapture


@dataclass
class StepResult:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class OTELRunReport:
    started_at: str
    finished_at: str
    probe_outcome: str  # "A" | "B" | "indeterminate"
    cleanup_applied: bool
    steps: list[StepResult]
    summary: dict[str, Any] = field(default_factory=dict)


# ── Step 1: probe ──────────────────────────────────────────────────────────


async def run_step1_probe() -> StepResult:
    """Run the formatter once with OTEL google-genai instrumentation ON.

    The formatter (``business_formatter`` config) has
    ``output_schema=StructuredBusinessStrategy``. If the known OTEL
    google-genai bug is still present, ``model_dump()`` will throw a
    ``TypeError`` on the Pydantic class — caught + reported here as
    Outcome A.
    """
    print("[1/4] probe — running strategy formatter with output_schema "
          "(OTEL google-genai instrumentation ENABLED)...")

    # Force the workaround OFF for the probe regardless of .env state.
    os.environ.pop("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", None)

    error_text: str | None = None
    crashed_in_otel = False

    try:
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai.types import Content, Part
        from pydantic import BaseModel, Field

        # Tiny Pydantic schema — small enough to pass Vertex's "too many
        # states for serving" guard while still exercising the
        # ``response_schema`` path that the OTEL google-genai
        # instrumentation tried to ``model_dump()`` and crashed on. The
        # bug fires regardless of schema complexity (it's a serialisation
        # issue on the SCHEMA OBJECT, not the response value), so a
        # minimal model is sufficient as a probe.
        class _ProbeOutput(BaseModel):
            company_name: str = Field(description="The name of the company.")
            tagline: str = Field(description="A 1-line tagline.")

        agent = Agent(
            name="otel_probe_formatter",
            model="gemini-2.5-flash",
            output_schema=_ProbeOutput,
            instruction=(
                "Extract a company_name and a 1-line tagline from the user's "
                "input. Return JSON matching the schema."
            ),
        )
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="otel_probe",
            session_service=session_service,
        )

        await session_service.create_session(
            app_name="otel_probe",
            user_id="otel_probe_user",
            session_id="otel_probe_session",
        )

        prompt = (
            "Format this research into a business strategy: "
            "Acme Corp is a B2B SaaS company offering analytics tools "
            "to mid-market companies. Their main competitors are Tableau "
            "and Looker. Their unique value is real-time alerting."
        )
        async for _event in runner.run_async(
            user_id="otel_probe_user",
            session_id="otel_probe_session",
            new_message=Content(role="user", parts=[Part.from_text(text=prompt)]),
        ):
            pass

    except TypeError as e:
        # The signature of the OTEL google-genai bug: TypeError mentioning
        # model_dump or Pydantic class while serialising args.
        msg = str(e)
        error_text = f"TypeError: {msg}"
        if "model_dump" in msg or "BaseModel" in msg or "ModelMetaclass" in msg:
            crashed_in_otel = True
    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"

    if crashed_in_otel:
        print("      OUTCOME A — google-genai OTEL bug STILL PRESENT on this ADK version")
        return StepResult(
            name="probe",
            passed=True,  # probe completed; outcome is informational
            details={
                "outcome": "A",
                "error": error_text,
                "interpretation": (
                    "Workaround required: OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"
                    "=google-genai must remain set in .env files."
                ),
            },
        )

    if error_text:
        # Some other unrelated failure happened — surface it but do not
        # claim either outcome.
        print(f"      INDETERMINATE — non-OTEL error: {error_text}")
        return StepResult(
            name="probe",
            passed=False,
            details={
                "outcome": "indeterminate",
                "error": error_text,
                "interpretation": (
                    "Probe failed for non-OTEL reasons; cannot conclude bug "
                    "state. Inspect the error and re-run."
                ),
            },
        )

    print("      OUTCOME B — google-genai OTEL bug RESOLVED (clean run)")
    return StepResult(
        name="probe",
        passed=True,
        details={
            "outcome": "B",
            "interpretation": (
                "Workaround can be removed: OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"
                "=google-genai is no longer needed on this ADK version."
            ),
        },
    )


# ── Step 1 cleanup: env-file consistency ───────────────────────────────────


_ENV_FILES = (
    _REPO_ROOT / "app" / "adk" / ".env.development",
    _REPO_ROOT / "app" / "adk" / ".env.staging",
    _REPO_ROOT / "app" / "adk" / ".env.production",
)
_DEPLOY_PY = _REPO_ROOT / "app" / "adk" / "deploy_ken_e.py"


def _apply_outcome_a(verification_date: str) -> dict[str, Any]:
    """Re-enable the workaround everywhere consistently."""
    changes: dict[str, Any] = {}
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        text = env_file.read_text()
        if "# OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai" in text:
            new_text = text.replace(
                "# OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai",
                "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai",
            )
            env_file.write_text(new_text)
            changes[str(env_file.relative_to(_REPO_ROOT))] = "uncommented"
        else:
            changes[str(env_file.relative_to(_REPO_ROOT))] = "already-active-or-absent"

    if _DEPLOY_PY.exists():
        text = _DEPLOY_PY.read_text()
        if (
            '# os.environ.setdefault("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"'
            in text
        ):
            new_text = text.replace(
                '        # os.environ.setdefault("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "google-genai")',
                '        os.environ.setdefault("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "google-genai")',
            )
            _DEPLOY_PY.write_text(new_text)
            changes["app/adk/deploy_ken_e.py"] = "uncommented"
    return changes


def _apply_outcome_b(verification_date: str) -> dict[str, Any]:
    """Strip the workaround everywhere — bug is gone."""
    changes: dict[str, Any] = {}
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        text = env_file.read_text()
        original = text
        # Remove either the active or commented line; collapse adjacent blank
        # lines to keep the file tidy.
        for needle in (
            "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai\n",
            "# OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai\n",
        ):
            text = text.replace(needle, "")
        if text != original:
            env_file.write_text(text)
            changes[str(env_file.relative_to(_REPO_ROOT))] = "removed"
        else:
            changes[str(env_file.relative_to(_REPO_ROOT))] = "absent"

    if _DEPLOY_PY.exists():
        text = _DEPLOY_PY.read_text()
        original = text
        block_marker = (
            "        # Workaround for buggy google-genai OTEL instrumentation"
        )
        if block_marker in text:
            # Drop the 4-line workaround block (3 comment lines + commented-out
            # setdefault). Re-do via list of lines.
            lines = text.splitlines(keepends=True)
            kept: list[str] = []
            skip_next = 0
            for line in lines:
                if skip_next > 0:
                    skip_next -= 1
                    continue
                if "# Workaround for buggy google-genai OTEL" in line:
                    skip_next = 4  # skip the 4 lines after this marker
                    continue
                kept.append(line)
            text = "".join(kept)
        if text != original:
            _DEPLOY_PY.write_text(text)
            changes["app/adk/deploy_ken_e.py"] = "block-removed"
    return changes


def _update_spike_doc(outcome: str, verification_date: str) -> bool:
    """Append a verification note to the spike findings doc."""
    spike_doc = _REPO_ROOT / "docs" / "spike-otel-pydantic-findings.md"
    if not spike_doc.exists():
        return False
    text = spike_doc.read_text()
    note_marker = "## Sprint 6 verification"
    if note_marker in text:
        # Already noted; skip.
        return False

    if outcome == "B":
        note = (
            f"\n\n{note_marker} ({verification_date})\n\n"
            "- **Outcome**: clean run.\n"
            "- The `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=google-genai` "
            "workaround is no longer required on ADK ≥1.27.4 + matching "
            "google-genai. Removed from all `.env.*` files and from "
            "`app/adk/deploy_ken_e.py`.\n"
            "- Probe: `tests/integration/stability/runs/run_otel_stability.py` "
            "Step 1.\n"
        )
    elif outcome == "A":
        note = (
            f"\n\n{note_marker} ({verification_date})\n\n"
            "- **Outcome**: bug still present.\n"
            "- The `model_dump()` `TypeError` reproduces on ADK ≥1.27.4 "
            "when running a strategy formatter with `output_schema=`.\n"
            "- Workaround re-applied consistently to `.env.development`, "
            "`.env.staging`, `.env.production`, `deploy_ken_e.py`.\n"
            "- Probe: `tests/integration/stability/runs/run_otel_stability.py` "
            "Step 1.\n"
        )
    else:
        return False

    spike_doc.write_text(text + note)
    return True


# ── Step 2: paired memory delta via subprocess ─────────────────────────────


def _run_subprocess_with_rss_sample(
    extra_env: dict[str, str], invocations: int
) -> dict[str, Any]:
    """Spawn ``run_adk_stability.py`` and sample RSS via psutil periodically.

    Returns peak RSS plus duration + child exit status. The subprocess
    pattern is required because Python doesn't unload OTEL
    instrumentation cleanly mid-process — the only reliable way to do a
    "with vs. without OTEL" comparison is two clean processes.
    """
    import psutil

    env = os.environ.copy()
    env.update(extra_env)
    env.setdefault("PYTHONPATH", ":".join(["", "api/src"]))

    cmd = [
        sys.executable,
        str(
            _REPO_ROOT / "tests/integration/stability/runs/run_adk_stability.py"
        ),
        "--invocations",
        str(invocations),
    ]

    # Redirect subprocess stdout/stderr to a temp log instead of PIPE.
    # The subprocess writes a lot (httpx/weave debug logs) and we don't
    # consume from PIPE in this loop — that would block the child once the
    # OS pipe buffer fills (~64 KB on macOS), wedging the whole step.
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w+",
        prefix="otel_subprocess_",
        suffix=".log",
        delete=False,
    ) as log_file:
        subprocess_log_path = log_file.name

    started = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603
        cmd,
        env=env,
        stdout=open(subprocess_log_path, "w"),  # noqa: SIM115
        stderr=subprocess.STDOUT,
        cwd=str(_REPO_ROOT),
    )

    try:
        ps = psutil.Process(proc.pid)
        peak_rss = 0
        while proc.poll() is None:
            try:
                rss = ps.memory_info().rss
                # Include child process trees (genai client may spawn).
                for child in ps.children(recursive=True):
                    try:
                        rss += child.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                peak_rss = max(peak_rss, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            time.sleep(0.5)
    finally:
        proc.wait()

    duration = time.monotonic() - started
    return {
        "peak_rss_bytes": peak_rss,
        "peak_rss_mb": peak_rss / (1024 * 1024),
        "duration_s": duration,
        "exit_code": proc.returncode,
        "subprocess_log": subprocess_log_path,
    }


def run_step2_memory_delta(invocations: int) -> StepResult:
    """Compare peak RSS with OTEL on vs off (paired runs)."""
    print(f"[2/4] memory delta — paired {invocations}-invocation runs "
          "(OTEL on vs OTEL_SDK_DISABLED=true)...")

    print("      → run A: OTEL_SDK_DISABLED=true")
    a = _run_subprocess_with_rss_sample(
        {"OTEL_SDK_DISABLED": "true"}, invocations
    )
    print(f"        peak={a['peak_rss_mb']:.1f} MB  duration={a['duration_s']:.1f}s "
          f"exit={a['exit_code']}")

    print("      → run B: OTEL on (default)")
    # Make sure SDK_DISABLED is NOT inherited
    b = _run_subprocess_with_rss_sample({"OTEL_SDK_DISABLED": "false"}, invocations)
    print(f"        peak={b['peak_rss_mb']:.1f} MB  duration={b['duration_s']:.1f}s "
          f"exit={b['exit_code']}")

    if a["exit_code"] != 0 or b["exit_code"] != 0:
        return StepResult(
            name="memory_delta",
            passed=False,
            details={
                "run_a_otel_disabled": a,
                "run_b_otel_enabled": b,
                "error": "one or both subprocess runs exited non-zero",
            },
        )

    delta = b["peak_rss_mb"] - a["peak_rss_mb"]
    delta_pct = (delta / a["peak_rss_mb"] * 100) if a["peak_rss_mb"] else 0
    passed = abs(delta_pct) < 10
    print(f"      delta = {delta:+.1f} MB ({delta_pct:+.1f}%)  "
          f"[{'PASS' if passed else 'FAIL'}]")

    return StepResult(
        name="memory_delta",
        passed=passed,
        details={
            "run_a_otel_disabled": a,
            "run_b_otel_enabled": b,
            "delta_mb": delta,
            "delta_pct": delta_pct,
            "threshold_pct": 10,
        },
    )


# ── Step 3: GenAI span coverage ────────────────────────────────────────────


async def run_step3_genai_coverage(invocations: int) -> StepResult:
    """Drive ``invocations`` queries inside TraceCapture, validate genai spans.

    Asserts every captured ``google.genai.models.AsyncModels.generate_content``
    span carries the GenAI required fields: ``model_used`` and
    ``temperature``.
    """
    print(f"[3/4] genai span coverage — {invocations} invocations under "
          "TraceCapture...")

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    from app.adk.agents.ken_e_agent import create_ken_e_agent

    QUERIES = _load_corpus()
    TraceCapture = _load_trace_capture()

    agent = create_ken_e_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ken_e_chatbot",
        session_service=session_service,
    )

    with TraceCapture() as cap:
        for i in range(invocations):
            case = QUERIES[i % len(QUERIES)]
            user_id = f"otel_user_{i:03d}"
            session_id = f"otel_session_{i:03d}"
            await session_service.create_session(
                app_name="ken_e_chatbot",
                user_id=user_id,
                session_id=session_id,
            )
            prompt = case.query if case.query else " "
            try:
                async for _ in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=Content(role="user", parts=[Part.from_text(text=prompt)]),
                ):
                    pass
            except Exception:
                # Per-invocation crashes are AC-6.10 territory (Story 1.1.1-3),
                # not OTEL coverage — keep going so we still get spans.
                pass

        spans = cap.traces

    # Find genai spans by op_name pattern.
    genai_spans = [
        s for s in spans
        if "google.genai" in (s.get("_weave_op_name") or "")
        and "generate_content" in (s.get("_weave_op_name") or "")
    ]

    required_fields = ("model_used", "temperature")
    field_present = {f: 0 for f in required_fields}
    for span in genai_spans:
        for f in required_fields:
            if span.get(f) is not None:
                field_present[f] += 1

    n = len(genai_spans)
    coverage = {
        f: (field_present[f] / n * 100 if n else 0.0) for f in required_fields
    }
    passed = n > 0 and all(coverage[f] == 100.0 for f in required_fields)

    print(f"      genai spans captured: {n}")
    for f in required_fields:
        print(f"        {f:18s} {coverage[f]:6.1f}%  ({field_present[f]}/{n})")
    print(f"      [{'PASS' if passed else 'FAIL'}]")

    return StepResult(
        name="genai_coverage",
        passed=passed,
        details={
            "genai_span_count": n,
            "field_coverage_pct": coverage,
            "field_present": field_present,
        },
    )


# ── Step 4: non-GenAI span presence ────────────────────────────────────────


async def run_step4_non_genai(invocations: int) -> StepResult:
    """Confirm the trace stream includes non-LLM spans (DB/HTTP).

    Reuses the same TraceCapture run mechanism as step 3 but counts
    span types other than ``google.genai.*``. A passing AC requires at
    least one DB-shaped op (``load_config_from_firestore``) and at
    least one HTTP-shaped op (``mcp.client.session.ClientSession.call_tool.*``)
    in the captured set.
    """
    print(f"[4/4] non-genai spans — {invocations} invocations under "
          "TraceCapture...")

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    from app.adk.agents.ken_e_agent import create_ken_e_agent

    QUERIES = _load_corpus()
    TraceCapture = _load_trace_capture()

    agent = create_ken_e_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ken_e_chatbot",
        session_service=session_service,
    )

    with TraceCapture() as cap:
        for i in range(invocations):
            case = QUERIES[i % len(QUERIES)]
            user_id = f"otel_ng_user_{i:03d}"
            session_id = f"otel_ng_session_{i:03d}"
            await session_service.create_session(
                app_name="ken_e_chatbot",
                user_id=user_id,
                session_id=session_id,
            )
            prompt = case.query if case.query else " "
            try:
                async for _ in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=Content(role="user", parts=[Part.from_text(text=prompt)]),
                ):
                    pass
            except Exception:
                pass
        spans = cap.traces

    op_names = [s.get("_weave_op_name") or "<unknown>" for s in spans]
    non_genai = [op for op in op_names if "google.genai" not in op]

    has_db = any("load_config_from_firestore" in op for op in op_names)
    has_http = any(
        "mcp.client.session.ClientSession.call_tool" in op
        or "search_company_news" in op
        for op in op_names
    )
    passed = has_db and has_http

    # Bucket op_names for the report.
    from collections import Counter

    op_counts = Counter(op_names)

    print(f"      total spans: {len(op_names)}; non-genai: {len(non_genai)}")
    print(f"      has DB-shaped span (firestore_config) : {has_db}")
    print(f"      has HTTP-shaped span (mcp/news search): {has_http}")
    print(f"      [{'PASS' if passed else 'FAIL'}]")

    return StepResult(
        name="non_genai_spans",
        passed=passed,
        details={
            "total_spans": len(op_names),
            "non_genai_spans": len(non_genai),
            "has_db_span": has_db,
            "has_http_span": has_http,
            "op_counts": dict(op_counts.most_common(20)),
        },
    )


# ── Orchestration ──────────────────────────────────────────────────────────


async def run_all(
    memory_invocations: int,
    span_invocations: int,
    apply_cleanup: bool,
    output_path: Path,
) -> OTELRunReport:
    started_at = datetime.now(UTC).isoformat()
    print(f"== OTEL Stability Run started {started_at} ==")
    print(f"Output: {output_path}")
    print()

    steps: list[StepResult] = []

    step1 = await run_step1_probe()
    steps.append(step1)
    outcome = step1.details.get("outcome", "indeterminate")

    cleanup_applied = False
    if apply_cleanup and outcome in ("A", "B"):
        verification_date = datetime.now(UTC).strftime("%Y-%m-%d")
        if outcome == "A":
            changes = _apply_outcome_a(verification_date)
        else:
            changes = _apply_outcome_b(verification_date)
        spike_updated = _update_spike_doc(outcome, verification_date)
        cleanup_applied = True
        step1.details["cleanup_changes"] = changes
        step1.details["spike_doc_updated"] = spike_updated
        print(f"      cleanup applied → {len(changes)} files changed; "
              f"spike doc updated={spike_updated}")
    print()

    # Steps 2–4: only meaningful if probe didn't fail catastrophically
    if step1.passed:
        steps.append(run_step2_memory_delta(memory_invocations))
        print()
        steps.append(await run_step3_genai_coverage(span_invocations))
        print()
        steps.append(await run_step4_non_genai(span_invocations))
        print()
    else:
        print("Skipping steps 2–4 because probe was indeterminate.")

    finished_at = datetime.now(UTC).isoformat()
    overall = all(s.passed for s in steps)
    summary = {
        "probe_outcome": outcome,
        "cleanup_applied": cleanup_applied,
        "step_results": {s.name: s.passed for s in steps},
        "overall_passed": overall,
    }

    report = OTELRunReport(
        started_at=started_at,
        finished_at=finished_at,
        probe_outcome=outcome,
        cleanup_applied=cleanup_applied,
        steps=steps,
        summary=summary,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(asdict(report), f, indent=2, default=str)

    return report


def _print_summary(report: OTELRunReport) -> None:
    s = report.summary
    pf = lambda b: "PASS" if b else "FAIL"  # noqa: E731

    print("=" * 64)
    print(f"== OTEL Stability Run Summary  ({report.finished_at}) ==")
    print("=" * 64)
    print(f"  probe outcome    : {report.probe_outcome}")
    print(f"  cleanup applied  : {report.cleanup_applied}")
    for name, passed in s["step_results"].items():
        print(f"  {name:18s} : [{pf(passed)}]")
    print("-" * 64)
    print(f"  Overall: {pf(s['overall_passed'])}")
    print("=" * 64)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="OTEL production stability validation",
    )
    parser.add_argument(
        "--memory-invocations",
        type=int,
        default=10,
        help="Invocations per memory-delta subprocess run (default 10).",
    )
    parser.add_argument(
        "--span-invocations",
        type=int,
        default=20,
        help="Invocations for span coverage steps 3 + 4 (default 20).",
    )
    parser.add_argument(
        "--no-apply-cleanup",
        action="store_true",
        help="Skip Outcome A/B file mutations; report only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to JSON report (default: runs/run_otel_stability_<ts>.json).",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = (
            _REPO_ROOT
            / "tests/integration/stability/runs"
            / f"run_otel_stability_{int(time.time())}.json"
        )

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ken-e-dev")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

    try:
        from dotenv import load_dotenv

        env_specific = (
            _REPO_ROOT
            / "app"
            / "adk"
            / f".env.{os.environ.get('ENVIRONMENT', 'development')}"
        )
        if env_specific.exists():
            load_dotenv(env_specific, override=False)
    except ImportError:
        pass

    report = asyncio.run(
        run_all(
            memory_invocations=args.memory_invocations,
            span_invocations=args.span_invocations,
            apply_cleanup=not args.no_apply_cleanup,
            output_path=args.output,
        )
    )
    _print_summary(report)
    sys.exit(0 if report.summary["overall_passed"] else 1)


if __name__ == "__main__":
    _cli()
