"""Run a query corpus through the chat completion endpoint and report.

Used by every Sprint 6 stability validation story to drive load through
``POST /api/v1/chat/completions`` and capture per-call latency, errors,
session id, and (best-effort) the agent the request was dispatched to.

CLI::

    python -m tests.integration.sprint6_harness.diverse_invocation_runner \\
        --queries 50 --output run_<ts>.json

The CLI requires ``HARNESS_API_BASE_URL`` and ``HARNESS_AUTH_TOKEN`` env
vars. The library entry point :func:`run_corpus` accepts both directly,
which is what the harness's own tests use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from tests.integration.sprint6_harness.query_corpus import QUERIES, QueryCase


@dataclass
class InvocationResult:
    query: str
    category: str
    expected_agent_type: str
    actual_agent_type: str | None = None
    duration_s: float = 0.0
    error: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    session_id: str | None = None
    status_code: int | None = None


@dataclass
class RunReport:
    started_at: str
    finished_at: str
    total_runs: int
    error_count: int
    error_rate: float
    latency_p50_s: float
    latency_p95_s: float
    results: list[InvocationResult] = field(default_factory=list)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100)[int(pct) - 1]


def _extract_agent_type(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("agent_type", "actual_agent_type", "dispatched_agent"):
        if key in metadata:
            return str(metadata[key])
    return None


def _extract_tokens(metadata: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not metadata:
        return None, None
    usage = metadata.get("usage") or metadata
    tokens_in = usage.get("input_tokens") or usage.get("prompt_tokens")
    tokens_out = usage.get("output_tokens") or usage.get("completion_tokens")
    return (
        int(tokens_in) if tokens_in is not None else None,
        int(tokens_out) if tokens_out is not None else None,
    )


async def _invoke_one(
    client: httpx.AsyncClient,
    query: QueryCase,
    auth_token: str,
) -> InvocationResult:
    headers = {"Authorization": f"Bearer {auth_token}"}
    body = {"messages": [{"role": "user", "content": query.query}], "stream": False}

    started = time.monotonic()
    try:
        resp = await client.post("/api/v1/chat/completions", json=body, headers=headers)
    except httpx.HTTPError as e:
        return InvocationResult(
            query=query.query,
            category=query.category.value,
            expected_agent_type=query.expected_agent_type,
            duration_s=time.monotonic() - started,
            error=f"{type(e).__name__}: {e}",
        )

    duration = time.monotonic() - started

    if resp.status_code >= 400:
        return InvocationResult(
            query=query.query,
            category=query.category.value,
            expected_agent_type=query.expected_agent_type,
            duration_s=duration,
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            status_code=resp.status_code,
        )

    try:
        data = resp.json()
    except ValueError as e:
        return InvocationResult(
            query=query.query,
            category=query.category.value,
            expected_agent_type=query.expected_agent_type,
            duration_s=duration,
            error=f"json decode: {e}",
            status_code=resp.status_code,
        )

    metadata = data.get("metadata") if isinstance(data, dict) else None
    tokens_in, tokens_out = _extract_tokens(metadata)
    return InvocationResult(
        query=query.query,
        category=query.category.value,
        expected_agent_type=query.expected_agent_type,
        actual_agent_type=_extract_agent_type(metadata),
        duration_s=duration,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        session_id=data.get("session_id") if isinstance(data, dict) else None,
        status_code=resp.status_code,
    )


async def run_corpus(
    queries: Iterable[QueryCase],
    api_url: str,
    auth_token: str,
    output_path: Path | str | None = None,
    timeout_s: float = 60.0,
) -> RunReport:
    """Drive `queries` through `api_url` sequentially and emit a RunReport.

    Sequential (not concurrent) on purpose — the stability ACs measure
    behavior under realistic single-user load, and concurrent floods would
    obscure per-call latency distribution.
    """
    started_at = datetime.now(UTC).isoformat()
    cases = list(queries)
    results: list[InvocationResult] = []

    async with httpx.AsyncClient(base_url=api_url, timeout=timeout_s) as client:
        for case in cases:
            results.append(await _invoke_one(client, case, auth_token))

    finished_at = datetime.now(UTC).isoformat()
    error_count = sum(1 for r in results if r.error is not None)
    durations = sorted(r.duration_s for r in results if r.error is None)

    report = RunReport(
        started_at=started_at,
        finished_at=finished_at,
        total_runs=len(results),
        error_count=error_count,
        error_rate=(error_count / len(results)) if results else 0.0,
        latency_p50_s=_percentile(durations, 50),
        latency_p95_s=_percentile(durations, 95),
        results=results,
    )

    if output_path:
        Path(output_path).write_text(json.dumps(asdict(report), indent=2, default=str))

    return report


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Sprint 6 query corpus against /api/v1/chat/completions"
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=len(QUERIES),
        help="Maximum number of queries to send (default: full corpus).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"run_{int(time.time())}.json"),
        help="Path to write the JSON report.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("HARNESS_API_BASE_URL", "http://localhost:8000"),
    )
    args = parser.parse_args()

    auth = os.environ.get("HARNESS_AUTH_TOKEN")
    if not auth:
        raise SystemExit("HARNESS_AUTH_TOKEN env var is required")

    cases = QUERIES[: args.queries]
    report = asyncio.run(run_corpus(cases, args.api_url, auth, args.output))
    print(
        f"Ran {report.total_runs}; errors={report.error_count} "
        f"({report.error_rate:.1%}); p50={report.latency_p50_s:.2f}s "
        f"p95={report.latency_p95_s:.2f}s; report -> {args.output}"
    )


if __name__ == "__main__":
    _cli()
