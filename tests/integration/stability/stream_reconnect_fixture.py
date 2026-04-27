"""API-server subprocess fixture for the Sprint 6 stream-reconnect tests.

Used by Story 5 (AC 6.22 — stream reconnect after process kill preserves
the ADK session). Spawns a uvicorn subprocess on an ephemeral port, opens
a streaming chat request, kills the process mid-stream, restarts on the
same port, and lets the caller issue a follow-up against the captured
``session_id``.

The fixture itself is unit-tested against a trivial stub FastAPI app —
see ``tests/test_stream_reconnect_fixture.py``. Story 5's validation run
points it at the real KEN-E API with ADC + a super-admin Bearer token.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_DIR = _REPO_ROOT / "api"

_STARTUP_MARKER = "Application startup complete"
_DEFAULT_STARTUP_TIMEOUT_S = 30.0


def _bind_ephemeral_port() -> int:
    """Reserve an ephemeral port and immediately release it for the child."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@dataclass
class APIServerSubprocess:
    """Manages a single uvicorn subprocess running the KEN-E API.

    `app_module` and `cwd` are parameterized so unit tests can spawn a
    trivial FastAPI app instead of the full API; live validation runs
    use the defaults.
    """

    port: int
    startup_timeout_s: float = _DEFAULT_STARTUP_TIMEOUT_S
    extra_env: dict[str, str] = field(default_factory=dict)
    app_module: str = "src.kene_api.main:app"
    cwd: Path = _API_DIR
    _proc: subprocess.Popen[bytes] | None = field(default=None, init=False, repr=False)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            raise RuntimeError("API subprocess already running")
        env = {**os.environ, **self.extra_env}
        self._proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                self.app_module,
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "info",
            ],
            cwd=self.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._wait_for_startup()

    def _wait_for_startup(self) -> None:
        assert self._proc is not None
        deadline = time.monotonic() + self.startup_timeout_s
        assert self._proc.stdout is not None
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                if self._proc.poll() is not None:
                    raise RuntimeError(
                        f"API subprocess exited during startup "
                        f"(rc={self._proc.returncode})"
                    )
                continue
            if _STARTUP_MARKER.encode() in line:
                return
        self.terminate()
        raise TimeoutError(
            f"API subprocess did not log {_STARTUP_MARKER!r} within "
            f"{self.startup_timeout_s}s"
        )

    def terminate(self, signal_term: bool = True) -> int:
        if self._proc is None:
            return 0
        if self._proc.poll() is None:
            if signal_term:
                self._proc.terminate()
            else:
                self._proc.kill()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        rc = self._proc.returncode or 0
        self._proc = None
        return rc

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


@asynccontextmanager
async def streaming_chat_with_kill(
    server: APIServerSubprocess,
    auth_token: str,
    *,
    chunks_before_kill: int = 2,
    payload: dict[str, object] | None = None,
) -> AsyncIterator[tuple[str, list[bytes]]]:
    """Open a streaming chat request, kill the API mid-stream, restart it.

    Yields a tuple of `(session_id, chunks_received_before_kill)`. The caller
    is expected to issue a follow-up request against the same `session_id` to
    verify state preservation.
    """
    body = payload or {
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
        "stream": True,
    }
    chunks: list[bytes] = []
    session_id: str | None = None
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with httpx.AsyncClient(base_url=server.base_url, timeout=30.0) as client:
        async with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json=body,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                # Best-effort session_id extraction — the streaming contract
                # may carry it as a header or an early SSE/JSON chunk.
                if session_id is None:
                    session_id = resp.headers.get("X-Session-Id")
                if len(chunks) >= chunks_before_kill:
                    break

    # Kill mid-stream, then restart on the same port.
    port = server.port
    server.terminate(signal_term=True)
    server.port = port
    server.start()

    if session_id is None:
        raise RuntimeError("No session_id captured from streaming response")

    yield session_id, chunks
