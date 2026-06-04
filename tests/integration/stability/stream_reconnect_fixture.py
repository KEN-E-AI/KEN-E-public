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
        marker_seen = False
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
                marker_seen = True
                break
        # The startup marker ("Application startup complete") is logged during
        # uvicorn's lifespan startup, BEFORE the listening socket begins
        # accepting connections. Returning on the marker alone races an
        # immediate request against the not-yet-accepting socket — harmless
        # under light load, but under heavy parallel CI contention the gap
        # widens and the first request hits connection-refused. Poll the real
        # socket until it accepts so readiness reflects the socket, not a log.
        if marker_seen and self._wait_for_socket_accepting(deadline):
            return
        self.terminate()
        raise TimeoutError(
            f"API subprocess did not log {_STARTUP_MARKER!r} and start accepting "
            f"connections within {self.startup_timeout_s}s"
        )

    def _wait_for_socket_accepting(self, deadline: float) -> bool:
        """Poll until the subprocess accepts a TCP connection, or the shared
        startup deadline elapses. Returns False (caller raises) if the process
        dies or the socket never comes up in time."""
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                return False
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.port), timeout=0.5
                ):
                    return True
            except OSError:
                time.sleep(0.05)
        return False

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
    session_id: str,
    *,
    chunks_before_kill: int = 2,
    payload: dict[str, object] | None = None,
    request_timeout_s: float = 120.0,
) -> AsyncIterator[tuple[str, list[bytes]]]:
    """Open a streaming chat request, kill the API mid-stream, restart it.

    The caller must pre-create the session_id (e.g. via
    ``POST /api/v1/chat/conversations``) and pass it in. KEN-E's
    ``/chat/completions`` streaming response is plain SSE
    (``data: <text>\\n\\n``) — session_id is not exposed mid-stream, so
    state-preservation validation requires the caller to know the
    session id up front.

    Yields ``(session_id, chunks_received_before_kill)``. The caller is
    expected to issue a follow-up request against the same session_id
    after the context exits to verify state preservation.
    """
    body = payload or {
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
        "session_id": session_id,
        "stream": True,
    }
    if "session_id" not in body:
        body["session_id"] = session_id
    chunks: list[bytes] = []
    headers = {"Authorization": f"Bearer {auth_token}"}

    async with httpx.AsyncClient(
        base_url=server.base_url, timeout=request_timeout_s
    ) as client:
        async with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json=body,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                if len(chunks) >= chunks_before_kill:
                    break

    # Kill mid-stream, then restart on the same port.
    port = server.port
    server.terminate(signal_term=True)
    server.port = port
    server.start()

    yield session_id, chunks
