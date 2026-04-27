"""Tests for the diverse invocation runner using pytest-httpx."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from tests.integration.sprint6_harness.diverse_invocation_runner import (
    RunReport,
    run_corpus,
)
from tests.integration.sprint6_harness.query_corpus import QUERIES

_API = "http://example.test"


def _ok_response(seq: int) -> dict[str, object]:
    return {
        "role": "assistant",
        "content": f"answer #{seq}",
        "session_id": f"sess_{seq:03d}",
        "metadata": {
            "agent_type": "chatbot",
            "usage": {"input_tokens": 10 + seq, "output_tokens": 50 + seq},
        },
    }


@pytest.mark.asyncio
async def test_run_corpus_happy_path(httpx_mock: HTTPXMock) -> None:
    cases = QUERIES[:5]
    for i in range(len(cases)):
        httpx_mock.add_response(
            url=f"{_API}/api/v1/chat/completions",
            method="POST",
            json=_ok_response(i),
        )

    report = await run_corpus(cases, _API, auth_token="t")

    assert isinstance(report, RunReport)
    assert report.total_runs == 5
    assert report.error_count == 0
    assert report.error_rate == 0.0
    assert report.latency_p50_s >= 0.0
    assert report.latency_p95_s >= report.latency_p50_s
    assert all(
        r.session_id and r.session_id.startswith("sess_") for r in report.results
    )
    assert all(r.tokens_in is not None for r in report.results)


@pytest.mark.asyncio
async def test_run_corpus_records_errors(httpx_mock: HTTPXMock) -> None:
    cases = QUERIES[:3]
    httpx_mock.add_response(
        url=f"{_API}/api/v1/chat/completions",
        method="POST",
        json=_ok_response(0),
    )
    httpx_mock.add_response(
        url=f"{_API}/api/v1/chat/completions",
        method="POST",
        status_code=503,
        text="upstream down",
    )
    httpx_mock.add_response(
        url=f"{_API}/api/v1/chat/completions",
        method="POST",
        json=_ok_response(2),
    )

    report = await run_corpus(cases, _API, auth_token="t")
    assert report.total_runs == 3
    assert report.error_count == 1
    assert report.error_rate == pytest.approx(1 / 3)
    failing = [r for r in report.results if r.error is not None]
    assert len(failing) == 1
    assert failing[0].status_code == 503


@pytest.mark.asyncio
async def test_run_corpus_writes_json_report(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    cases = QUERIES[:2]
    for i in range(len(cases)):
        httpx_mock.add_response(
            url=f"{_API}/api/v1/chat/completions",
            method="POST",
            json=_ok_response(i),
        )

    out = tmp_path / "run.json"
    await run_corpus(cases, _API, auth_token="t", output_path=out)

    payload = json.loads(out.read_text())
    assert payload["total_runs"] == 2
    assert len(payload["results"]) == 2
    assert payload["results"][0]["actual_agent_type"] == "chatbot"
