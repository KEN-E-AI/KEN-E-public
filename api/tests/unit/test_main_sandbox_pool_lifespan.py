"""Unit tests: SandboxPool start/stop wiring in the FastAPI lifespan (SK-37).

Verifies AC-2 (graceful shutdown calls stop()) and the defensive branch
(start() raising must not block lifespan setup).

The tests patch ``app.adk.agents.agent_factory.builder._DEFAULT_SANDBOX_POOL``
with a MagicMock(spec=SandboxPool) so no real Vertex AI connection is made.
Both ``start()`` and ``stop()`` are synchronous (the pool runs on threads, not
the event loop), so the spec'd mock auto-creates them as sync MagicMocks.

Pattern follows test_main_startup_guard.py: pure-unit, no network, no Firestore.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.adk.agents.agent_factory.sandbox_pool import SandboxPool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool_mock() -> MagicMock:
    """Return a MagicMock(spec=SandboxPool) — start()/stop() are sync MagicMocks."""
    return MagicMock(spec=SandboxPool)


# The import path that main.py uses inside the lifespan deferred import.
_POOL_TARGET = "app.adk.agents.agent_factory.builder._DEFAULT_SANDBOX_POOL"


# ---------------------------------------------------------------------------
# Happy path: start() called on startup, stop() awaited on shutdown
# ---------------------------------------------------------------------------


class TestSandboxPoolLifespanHappyPath:
    def test_start_called_exactly_once_on_startup(self) -> None:
        """start() is invoked once when the FastAPI lifespan enters."""
        pool = _make_pool_mock()
        with patch(_POOL_TARGET, pool):
            from src.kene_api.main import app

            with TestClient(app):
                pool.start.assert_called_once()

    def test_stop_called_exactly_once_on_shutdown(self) -> None:
        """stop() is called exactly once when the TestClient context exits."""
        pool = _make_pool_mock()
        with patch(_POOL_TARGET, pool):
            from src.kene_api.main import app

            with TestClient(app):
                pass  # lifespan start

            # After the context exits, lifespan shutdown has run.
            pool.stop.assert_called_once()

    def test_start_before_stop(self) -> None:
        """start() fires before stop() — startup ordering is correct."""
        call_order: list[str] = []
        pool = _make_pool_mock()
        pool.start.side_effect = lambda: call_order.append("start")
        pool.stop.side_effect = lambda: call_order.append("stop")
        with patch(_POOL_TARGET, pool):
            from src.kene_api.main import app

            with TestClient(app):
                pass

        assert call_order == ["start", "stop"]


# ---------------------------------------------------------------------------
# Defensive branch: start() raising must not block lifespan
# ---------------------------------------------------------------------------


class TestSandboxPoolLifespanDefensiveBranch:
    def test_start_exception_is_swallowed_lifespan_still_yields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A RuntimeError from start() must not prevent the lifespan from
        yielding — other startup components must still complete."""
        pool = _make_pool_mock()
        pool.start.side_effect = RuntimeError("no event loop")
        with patch(_POOL_TARGET, pool):
            from src.kene_api.main import app

            with caplog.at_level(logging.WARNING):
                with TestClient(app) as client:
                    # If lifespan yielded, the health endpoint is reachable.
                    resp = client.get("/health")
                    assert resp.status_code in (200, 503)  # up or degraded, not crash

        # The warning must be logged at WARNING level.
        assert any(
            "SandboxPool" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        ), "Expected a WARNING log mentioning SandboxPool when start() raises"

    def test_stop_exception_is_swallowed_shutdown_completes(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A RuntimeError from stop() must not prevent shutdown from completing."""
        pool = _make_pool_mock()
        pool.stop.side_effect = RuntimeError("already stopped")
        with patch(_POOL_TARGET, pool):
            from src.kene_api.main import app

            with caplog.at_level(logging.WARNING):
                with TestClient(app):
                    pass  # enter / exit triggers both startup and shutdown

        assert any(
            "SandboxPool" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        ), "Expected a WARNING log mentioning SandboxPool when stop() raises"
