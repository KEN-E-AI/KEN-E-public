"""ADK production stability validation (local).

Drives the KEN-E ADK agent through ≥50 invocations and monitors
callback-bus health.

What this validates:

* ≥50 ADK ``Runner`` invocations complete with zero construction or
  callback exceptions.
* The callback bus emits zero errors / warnings during the run, scoped
  to the four callback-host modules.

Design choice — ``Runner`` instead of HTTP:

The agent factory + callback chain is what we want to exercise; HTTP
plumbing is covered separately by the harness's
``diverse_invocation_runner`` self-tests. Driving via
``InMemorySessionService`` + ``Runner`` hits the same five callbacks
(``before_agent`` / ``after_agent`` / ``after_model`` / ``before_tool``
/ ``after_tool``) and the live ``config_cache`` — without needing
Firebase ID tokens or a running uvicorn.

Output: a JSON report at
``tests/integration/stability/runs/run_adk_stability_<ts>.json`` plus a
human-readable console summary.

Usage::

    cd /path/to/KEN-E
    uv run --directory api python -m tests.integration.stability.runs.run_adk_stability

Required environment:

* Application Default Credentials authenticated to a project that has
  the ``agent_configs/ken_e_chatbot`` Firestore doc.
* ``GOOGLE_CLOUD_PROJECT_ID`` (defaults to ``ken-e-dev``).
* ``GOOGLE_API_KEY`` or Vertex creds for Gemini calls (optional — none
  of the checks here require live LLM responses; any non-callback
  exception during ``runner.run_async`` is counted as a failure).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
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

    Bypasses the ``tests.integration.stability.query_corpus`` import
    name because ``api/tests/__init__.py`` shadows the repo-root
    ``tests/`` namespace package, which would otherwise hide every
    sibling module under the harness when run from inside ``api/``'s
    venv. Importing by file path is robust to that.
    """
    import importlib.util

    module_name = "_harness_query_corpus"
    if module_name in sys.modules:
        return sys.modules[module_name].QUERIES

    corpus_path = Path(__file__).resolve().parent.parent / "query_corpus.py"
    spec = importlib.util.spec_from_file_location(module_name, corpus_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load query corpus from {corpus_path}")
    module = importlib.util.module_from_spec(spec)
    # Register *before* exec so dataclass(frozen=True) can resolve the
    # owning module via sys.modules during class processing.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.QUERIES


# ── Callback-bus log capture ────────────────────────────────────────────────


# Module names of the five callback hosts. A WARNING/ERROR record from any of
# these during an invocation counts as a callback-bus error.
_CALLBACK_LOGGER_NAMES: tuple[str, ...] = (
    "app.adk.tracking.callbacks",
    "app.adk.security.hooks",
    "app.adk.agents.utils.config_cache",
    "app.adk.agents.ken_e_agent",
)


class CallbackErrorCapture(logging.Handler):
    """Log handler that records WARNING+ records from callback modules.

    Attached to the root logger when the run starts; filters by
    ``record.name`` so unrelated subsystems (httpx, urllib3, weave
    background uploads) don't pollute the count.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if not any(record.name.startswith(prefix) for prefix in _CALLBACK_LOGGER_NAMES):
            return
        self.records.append(
            {
                "logger": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
                "ts": time.time(),
            }
        )

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.records if r["level"] in {"ERROR", "CRITICAL"})

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.records if r["level"] == "WARNING")


# ── Result dataclasses ──────────────────────────────────────────────────────


@dataclass
class InvocationOutcome:
    """One ADK Runner invocation's bookkeeping."""

    index: int
    query: str
    category: str
    duration_s: float
    error: str | None = None
    response_chars: int = 0


@dataclass
class StabilityReport:
    started_at: str
    finished_at: str
    invocations: list[InvocationOutcome] = field(default_factory=list)
    callback_records: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _invoke_one(
    runner: Any,
    user_id: str,
    session_id: str,
    query: str,
) -> tuple[str, str | None]:
    """Drive a single Runner invocation; return (response_text, error_str)."""
    from google.genai.types import Content, Part

    # Some corpus entries are deliberately empty (the "ERROR_SCENARIO →
    # chatbot asks for clarification" probe). Substitute a single space so
    # the genai client doesn't reject the Part outright before the agent
    # even sees it — the chatbot's clarification path is what we want
    # exercised, not Part validation.
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
        # Any exception during run_async counts as an invocation failure;
        # we want the stability count to reflect every shape of crash.
        return "".join(chunks), f"{type(e).__name__}: {e}"
    return "".join(chunks), None


# ── Story acceptance-criteria runners ───────────────────────────────────────


async def run_invocations(
    target_invocations: int,
    capture: CallbackErrorCapture,
) -> tuple[list[InvocationOutcome], dict[str, Any]]:
    """Drive the agent through ``target_invocations`` and capture outcomes.

    Each call uses a **fresh session** so we exercise both session
    creation and the full callback chain repeatedly. Sequential, not
    concurrent — the goal is per-call stability, not throughput.

    Counts any exception during ``runner.run_async`` as an invocation
    failure; ``capture`` collects callback-side log errors separately.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory import build_hierarchy

    # Import the corpus by file path to avoid the namespace-package
    # collision between the repo-root ``tests/`` and ``api/tests/``
    # (which has its own ``__init__.py`` and would shadow the harness).
    QUERIES = _load_corpus()

    # Single agent instance. Per-invocation stability is the focus;
    # per-construction stability is covered by the import + instantiate
    # above (which itself runs the agent factory end-to-end once).
    construction_started = time.monotonic()
    agent = build_hierarchy()
    construction_duration_s = time.monotonic() - construction_started

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ken_e_chatbot",
        session_service=session_service,
    )

    outcomes: list[InvocationOutcome] = []

    # Cycle through the corpus until we hit target_invocations. The corpus
    # has 28 entries; with target=50 we wrap once.
    for i in range(target_invocations):
        case = QUERIES[i % len(QUERIES)]
        user_id = f"stability_user_{i:03d}"
        session_id = f"stability_session_{i:03d}"

        await session_service.create_session(
            app_name="ken_e_chatbot",
            user_id=user_id,
            session_id=session_id,
        )

        started = time.monotonic()
        response_text, error = await _invoke_one(
            runner, user_id, session_id, case.query
        )
        duration = time.monotonic() - started

        outcomes.append(
            InvocationOutcome(
                index=i,
                query=case.query[:120],
                category=case.category.value,
                duration_s=duration,
                error=error,
                response_chars=len(response_text),
            )
        )

        if (i + 1) % 10 == 0:
            print(
                f"  [{i + 1}/{target_invocations}] "
                f"errors={sum(1 for o in outcomes if o.error)} "
                f"cb_warns={capture.warning_count} cb_errs={capture.error_count}"
            )

    timing = {
        "construction_duration_s": construction_duration_s,
        "invocation_durations_s": [o.duration_s for o in outcomes],
    }
    return outcomes, timing


# ── Driver ──────────────────────────────────────────────────────────────────


@contextlib.contextmanager
def _attach_callback_capture():
    """Install + uninstall the callback-bus log handler around the run."""
    capture = CallbackErrorCapture()
    root = logging.getLogger()
    prior_level = root.level
    if prior_level > logging.WARNING:
        root.setLevel(logging.WARNING)
    root.addHandler(capture)
    try:
        yield capture
    finally:
        root.removeHandler(capture)
        root.setLevel(prior_level)


async def run_full(target_invocations: int, output_path: Path) -> StabilityReport:
    started_at = datetime.now(UTC).isoformat()
    print(f"== ADK Stability Run started {started_at} ==")
    print(f"Target invocations: {target_invocations}")
    print(f"Output: {output_path}")
    print()

    with _attach_callback_capture() as capture:
        # Bulk invocations + callback-bus capture (paired — same run).
        print("[1/1] driving invocations + capturing callback bus...")
        outcomes, timing = await run_invocations(target_invocations, capture)
        print(f"      done — {len(outcomes)} invocations completed")
        print()

    # Snapshot capture state. Must read inside the with-block to count
    # records emitted during the run, but the dataclasses are frozen
    # after — copy the list out.
    callback_records = list(capture.records)

    invocation_errors = sum(1 for o in outcomes if o.error)
    callback_errors = sum(
        1 for r in callback_records if r["level"] in {"ERROR", "CRITICAL"}
    )
    callback_warnings = sum(1 for r in callback_records if r["level"] == "WARNING")

    summary = {
        "invocations_target": target_invocations,
        "invocations_completed": len(outcomes),
        "invocations_failed": invocation_errors,
        "invocations_passed": invocation_errors == 0
        and len(outcomes) >= target_invocations,
        "callback_errors": callback_errors,
        "callback_warnings": callback_warnings,
        "callback_passed": callback_errors == 0,
        "construction_duration_s": timing["construction_duration_s"],
        "invocation_p50_s": _percentile(timing["invocation_durations_s"], 50),
        "invocation_p95_s": _percentile(timing["invocation_durations_s"], 95),
    }
    summary["overall_passed"] = all(
        summary[k]
        for k in (
            "invocations_passed",
            "callback_passed",
        )
    )

    report = StabilityReport(
        started_at=started_at,
        finished_at=datetime.now(UTC).isoformat(),
        invocations=outcomes,
        callback_records=callback_records,
        summary=summary,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2, default=str))

    _print_summary(report)
    return report


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    import statistics

    return statistics.quantiles(values, n=100)[int(pct) - 1]


def _print_summary(report: StabilityReport) -> None:
    s = report.summary

    def _pf(b: bool) -> str:
        return "PASS" if b else "FAIL"

    print("=" * 64)
    print(f"== ADK Stability Run Summary  ({report.finished_at}) ==")
    print("=" * 64)
    print(
        f"  invocations    : "
        f"{s['invocations_completed']}/{s['invocations_target']} "
        f"completed, {s['invocations_failed']} failed   [{_pf(s['invocations_passed'])}]"
    )
    print(
        f"  callback bus   : "
        f"{s['callback_errors']} errors, "
        f"{s['callback_warnings']} warnings   [{_pf(s['callback_passed'])}]"
    )
    print("-" * 64)
    print(
        f"  Construction: {s['construction_duration_s']:.2f}s  | "
        f"p50={s['invocation_p50_s']:.2f}s  p95={s['invocation_p95_s']:.2f}s"
    )
    print(f"  Overall: {_pf(s['overall_passed'])}")
    print("=" * 64)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="ADK production stability validation",
    )
    parser.add_argument(
        "--invocations",
        type=int,
        default=50,
        help="Number of ADK invocations to drive (default 50).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to JSON report (default: tests/integration/stability/runs/run_adk_stability_<ts>.json).",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = (
            _REPO_ROOT
            / "tests/integration/stability/runs"
            / f"run_adk_stability_{int(time.time())}.json"
        )

    # Default to dev project + Vertex backend so the genai client used by
    # ADK ``Runner`` can authenticate via ADC. Caller can override these
    # before launch for staging/prod runs.
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "ken-e-dev")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

    # Pre-load the environment-specific .env so sub-agent construction succeeds.
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

    report = asyncio.run(run_full(args.invocations, args.output))
    sys.exit(0 if report.summary["overall_passed"] else 1)


if __name__ == "__main__":
    _cli()
