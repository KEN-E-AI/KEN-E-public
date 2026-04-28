"""Tests for the API-subprocess stream-reconnect fixture.

These two tests spin up a trivial FastAPI app on an ephemeral port to
exercise the fixture end-to-end (subprocess lifecycle, streaming chunk
capture, mid-stream kill, restart) without touching ADC, auth, or the
real KEN-E API. AC-6.22 ("session preserved across stream reconnect")
is validated separately by Story 5 driving the fixture against the
real dev API — that run is not part of this harness's self-test suite.
"""

from __future__ import annotations

import socket
from pathlib import Path
from textwrap import dedent

import httpx
import pytest

from tests.integration.stability.stream_reconnect_fixture import (
    APIServerSubprocess,
    streaming_chat_with_kill,
)


def _bind_ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


_STUB_APP_SOURCE = dedent(
    """
    import asyncio
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.post("/api/v1/chat/completions")
    async def chat(_: dict | None = None):
        async def gen():
            for i in range(20):
                yield f"chunk-{i}\\n".encode()
                await asyncio.sleep(0.05)

        return StreamingResponse(
            gen(),
            media_type="text/plain",
            headers={"X-Session-Id": "sess_stub_123"},
        )
    """
).strip()


def test_subprocess_lifecycle_against_stub_app(tmp_path: Path) -> None:
    """Verify start → request → terminate → restart works end-to-end."""
    (tmp_path / "stub_app.py").write_text(_STUB_APP_SOURCE)
    port = _bind_ephemeral_port()
    server = APIServerSubprocess(
        port=port,
        startup_timeout_s=15.0,
        app_module="stub_app:app",
        cwd=tmp_path,
    )

    try:
        server.start()
        assert server.is_alive()

        resp = httpx.get(f"{server.base_url}/ping", timeout=5.0)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        rc = server.terminate(signal_term=True)
        assert rc in (0, -15, 15, 143)
        assert not server.is_alive()

        # Restart on the same port and verify it's reachable again.
        server.start()
        assert server.is_alive()
        resp2 = httpx.get(f"{server.base_url}/ping", timeout=5.0)
        assert resp2.status_code == 200
    finally:
        server.terminate()


@pytest.mark.asyncio
async def test_streaming_chat_with_kill_against_stub_app(tmp_path: Path) -> None:
    """Exercise streaming_chat_with_kill end-to-end against a stub.

    Verifies that the helper captures `session_id` from response headers,
    receives chunks before kill, and the API restarts cleanly on the same
    port — without needing real ADC or super-admin tokens.
    """
    (tmp_path / "stub_app.py").write_text(_STUB_APP_SOURCE)
    port = _bind_ephemeral_port()
    server = APIServerSubprocess(
        port=port,
        startup_timeout_s=15.0,
        app_module="stub_app:app",
        cwd=tmp_path,
    )

    try:
        server.start()
        async with streaming_chat_with_kill(
            server,
            auth_token="ignored-by-stub",
            chunks_before_kill=2,
        ) as (session_id, chunks):
            assert session_id == "sess_stub_123"
            assert len(chunks) >= 2
            assert all(c.startswith(b"chunk-") for c in chunks)
            assert server.is_alive()
    finally:
        server.terminate()
