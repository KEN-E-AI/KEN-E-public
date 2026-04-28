"""Production trace compliance validation (local).

Drives the KEN-E ADK agent through ≥20 diverse invocations, captures
every weave Call pushed onto the call stack via ``TraceCapture``, then
feeds each captured span through
``app.adk.tracking.compliance.generate_compliance_report``.

What this validates:

* AC-6.18 — ≥20 diverse invocations execute and emit traces.
* AC-6.19 — every captured span is **compliant** with the trace spec
  (``docs/trace-structure-spec.md`` §11). Required fields:
  ``agent_id``, ``agent_version``, ``account_id``, ``session_id``.
  Fields with defaults (``experiment_id``, ``variant_name``,
  ``environment``, ``rollout_percentage``) are validated only when
  present.
* AC-6.20 — the runner emits Weave call URLs to stdout; spot-check
  ≥10 manually in the Weave UI (URLs are saved in the JSON report).

Design choice — direct ADK Runner over HTTP:

Same rationale as ``run_adk_stability.py``: the trace emitter is the
target of validation, not the HTTP plumbing. Driving via
``InMemorySessionService`` + ``Runner`` exercises the entire callback
+ tracking chain without an auth-token mint.

Output:

* Console: per-invocation Weave call URL + aggregate compliance %.
* JSON: ``runs/run_trace_compliance_<ts>.json`` with the full
  ``TraceComplianceReport`` plus per-invocation outcome / Weave URL.

Exit code:

* ``0`` when ``compliance_percentage == 100.0``.
* ``1`` otherwise (issues itemised in the JSON report's
  ``common_issues`` and ``field_compliance``).

Usage::

    cd /path/to/KEN-E
    PYTHONPATH=.:api/src uv run --project api python \
        tests/integration/stability/runs/run_trace_compliance.py

Required environment:

* Application Default Credentials authenticated to a project that has
  the ``agent_configs/ken_e_chatbot`` Firestore doc.
* ``GOOGLE_CLOUD_PROJECT_ID`` (defaults to ``ken-e-dev``).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure repo root on sys.path so ``app.adk.*`` imports resolve when
# invoked via ``python`` (script mode) from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_corpus() -> list[Any]:
    """Load the harness QueryCase corpus by file path.

    Same workaround as ``run_adk_stability.py`` — ``api/tests/__init__.py``
    shadows the repo-root ``tests/`` namespace package, so we resolve
    the corpus by file path.
    """
    module_name = "_harness_query_corpus_for_trace"
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
    """Load ``TraceCapture`` by file path (same namespace dodge)."""
    module_name = "_harness_trace_capture"
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


# ── Result dataclasses ─────────────────────────────────────────────────────


@dataclass
class InvocationOutcome:
    index: int
    query: str
    category: str
    duration_s: float
    error: str | None = None
    spans_captured: int = 0
    weave_url: str | None = None


@dataclass
class ComplianceRunReport:
    started_at: str
    finished_at: str
    target_invocations: int
    invocations: list[InvocationOutcome]
    total_spans: int
    compliance_report: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)


async def _invoke_one(
    runner: Any,
    user_id: str,
    session_id: str,
    query: str,
) -> tuple[str, str | None]:
    """Drive a single Runner invocation; return (response_text, error_str)."""
    from google.genai.types import Content, Part

    safe_text = query if query else " "
    user_message = Content(role="user", parts=[Part.from_text(text=safe_text)])
    chunks: list[str] = []
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        chunks.append(part.text)
    except Exception as e:
        return "".join(chunks), f"{type(e).__name__}: {e}"
    return "".join(chunks), None


async def run_compliance_check(
    target_invocations: int,
    output_path: Path,
) -> ComplianceRunReport:
    """Drive ``target_invocations`` queries, capture every span, validate.

    Wraps the entire driving phase in ``TraceCapture`` so root + child
    spans are intercepted regardless of the agent's nesting depth.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.ken_e_agent import create_ken_e_agent
    from app.adk.tracking.compliance import generate_compliance_report

    QUERIES = _load_corpus()
    TraceCapture = _load_trace_capture()

    started_at = datetime.now(UTC).isoformat()
    print(f"== Trace compliance run started {started_at} ==")
    print(f"Target invocations: {target_invocations}")
    print(f"Output: {output_path}")
    print()

    agent = create_ken_e_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ken_e_chatbot",
        session_service=session_service,
    )

    outcomes: list[InvocationOutcome] = []

    print("[1/2] driving invocations + capturing weave call stack...")
    with TraceCapture() as capture:
        for i in range(target_invocations):
            case = QUERIES[i % len(QUERIES)]
            user_id = f"compliance_user_{i:03d}"
            session_id = f"compliance_session_{i:03d}"

            await session_service.create_session(
                app_name="ken_e_chatbot",
                user_id=user_id,
                session_id=session_id,
            )

            spans_before = len(capture.traces)
            started = time.monotonic()
            _, error = await _invoke_one(runner, user_id, session_id, case.query)
            duration = time.monotonic() - started
            spans_added = len(capture.traces) - spans_before

            # First newly-captured span's call_id is the trace root for this
            # invocation; surface its Weave URL for the AC-6.20 spot-check.
            weave_url: str | None = None
            if spans_added > 0:
                root_span = capture.traces[spans_before]
                call_id = root_span.get("_weave_call_id")
                if call_id:
                    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
                    weave_url = f"https://wandb.ai/ken-e/{project}/r/call/{call_id}"

            outcomes.append(
                InvocationOutcome(
                    index=i,
                    query=case.query[:120],
                    category=case.category.value,
                    duration_s=duration,
                    error=error,
                    spans_captured=spans_added,
                    weave_url=weave_url,
                )
            )

            if (i + 1) % 5 == 0:
                err_n = sum(1 for o in outcomes if o.error)
                spans_n = sum(o.spans_captured for o in outcomes)
                print(
                    f"  [{i + 1}/{target_invocations}] "
                    f"errors={err_n} spans_total={spans_n}"
                )

        all_traces = capture.traces

    print(f"      done — {len(outcomes)} invocations, {len(all_traces)} spans captured")
    print()

    # Strip weave-identity hints before compliance validation, but keep
    # ``op_name`` alongside each cleaned trace so we can attribute failures.
    cleaned_traces = [
        {k: v for k, v in trace.items() if not k.startswith("_weave_")}
        for trace in all_traces
    ]
    trace_ids = [trace.get("_weave_call_id") for trace in all_traces]
    op_names = [trace.get("_weave_op_name") for trace in all_traces]

    print("[2/2] validating spans against trace compliance spec...")
    report = generate_compliance_report(cleaned_traces, trace_ids=trace_ids)
    print(
        f"      done — {report.compliant_traces}/{report.total_traces} compliant "
        f"({report.compliance_percentage:.1f}%)"
    )
    print()

    finished_at = datetime.now(UTC).isoformat()

    # Per-op_name compliance breakdown: which span types are failing?
    from collections import Counter

    op_total: Counter[str] = Counter()
    op_failures: Counter[str] = Counter()
    for op_name, result in zip(op_names, report.results, strict=True):
        key = op_name or "<no-op-name>"
        op_total[key] += 1
        if not result.is_compliant:
            op_failures[key] += 1

    op_compliance: dict[str, dict[str, int | float]] = {
        op: {
            "total": op_total[op],
            "failed": op_failures[op],
            "compliant_pct": (op_total[op] - op_failures[op]) / op_total[op] * 100,
        }
        for op in op_total
    }

    summary = {
        "total_spans": report.total_traces,
        "compliant_spans": report.compliant_traces,
        "non_compliant_spans": report.non_compliant_traces,
        "compliance_percentage": report.compliance_percentage,
        "field_compliance": report.field_compliance,
        "common_issues": report.common_issues,
        "op_compliance": op_compliance,
        "invocations_target": target_invocations,
        "invocations_completed": len(outcomes),
        "invocations_failed": sum(1 for o in outcomes if o.error),
        "overall_passed": report.compliance_percentage == 100.0,
    }

    run_report = ComplianceRunReport(
        started_at=started_at,
        finished_at=finished_at,
        target_invocations=target_invocations,
        invocations=outcomes,
        total_spans=report.total_traces,
        compliance_report=report.model_dump(),
        summary=summary,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(asdict(run_report), f, indent=2, default=str)

    return run_report


def _print_summary(report: ComplianceRunReport) -> None:
    s = report.summary
    pf = lambda b: "PASS" if b else "FAIL"  # noqa: E731

    print("=" * 64)
    print(f"== Trace Compliance Run Summary  ({report.finished_at}) ==")
    print("=" * 64)
    print(
        f"  invocations    : {s['invocations_completed']}/{s['invocations_target']}"
        f" completed, {s['invocations_failed']} failed"
    )
    print(
        f"  spans          : {s['compliant_spans']}/{s['total_spans']} compliant "
        f"({s['compliance_percentage']:.1f}%)   [{pf(s['overall_passed'])}]"
    )
    print()
    print("  Per-required-field compliance:")
    for field_name, pct in s["field_compliance"].items():
        print(f"    {field_name:18s} {pct:6.1f}%")

    if s["common_issues"]:
        print()
        print("  Top issues:")
        for issue, count in s["common_issues"][:5]:
            print(f"    {count:3d}x  {issue}")

    if s["op_compliance"]:
        print()
        print("  Per-op compliance:")
        for op, stats in sorted(
            s["op_compliance"].items(), key=lambda kv: -kv[1]["failed"]
        ):
            print(
                f"    {op:40s} "
                f"{stats['total'] - stats['failed']:3d}/{stats['total']:3d} "
                f"({stats['compliant_pct']:5.1f}%)"
            )

    print("-" * 64)
    print(f"  Overall: {pf(s['overall_passed'])}")
    print("=" * 64)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Production trace compliance validation",
    )
    parser.add_argument(
        "--invocations",
        type=int,
        default=20,
        help="Number of ADK invocations to drive (default 20).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to JSON report (default: runs/run_trace_compliance_<ts>.json).",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = (
            _REPO_ROOT
            / "tests/integration/stability/runs"
            / f"run_trace_compliance_{int(time.time())}.json"
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

    report = asyncio.run(run_compliance_check(args.invocations, args.output))
    _print_summary(report)
    sys.exit(0 if report.summary["overall_passed"] else 1)


if __name__ == "__main__":
    _cli()
