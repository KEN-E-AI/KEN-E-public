"""Redis TTL controller for the Sprint 6 stability stories.

**Approach:** don't fake Redis. The behaviour under test is the
fallback path that activates when a key is *absent* — code that's
identical whether absence comes from natural TTL expiry or from an
explicit delete. Faking the entire `RedisService` would require
mocking `setex`/`get` throughout the API for negligible realism gain.

Instead, this module exposes :class:`TTLController` (and a pytest
fixture wrapping it) that talks to the dev Redis the API normally
uses, lets tests seed/inspect/expire keys directly, and skips
gracefully if Redis is unavailable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

# ``kene_api.redis_client`` does ``import redis`` at module top, and the
# CI integration-tests step runs from the repo-root venv which doesn't
# install the ``redis`` package (only ``api/.venv`` does). Defer the
# import to fixture-resolution time so module collection succeeds in any
# venv; tests that need it then ``importorskip`` cleanly.
if TYPE_CHECKING:
    from kene_api.redis_client import RedisService


class TTLController:
    """Thin wrapper around :class:`RedisService` for harness tests."""

    def __init__(self, service: Any) -> None:
        self._svc = service

    @property
    def service(self) -> Any:
        return self._svc

    def is_available(self) -> bool:
        return self._svc.is_available()

    def seed(self, key: str, value: str, ttl_s: int = 60) -> bool:
        return self._svc.set(key, value, ttl=ttl_s)

    def get(self, key: str) -> str | None:
        return self._svc.get(key)

    def delete_key(self, key: str) -> bool:
        return self._svc.delete(key)

    def expire_now(self, key: str) -> bool:
        """Simulate TTL expiry by deleting the key."""
        return self._svc.delete(key)

    def flush_pattern(self, pattern: str) -> int:
        """Delete every key matching `pattern`. Returns deleted count."""
        if not self._svc.client:
            return 0
        deleted = 0
        # SCAN is cooperative; safe against the dev Redis we share with the API.
        for key in self._svc.client.scan_iter(match=pattern):
            if self._svc.client.delete(key):
                deleted += 1
        return deleted


@pytest.fixture
def ttl_controller() -> TTLController:
    """Provide a TTLController; skip the test if dev Redis isn't reachable.

    Skip-then-import order matters: ``importorskip("redis")`` runs before the
    ``kene_api.redis_client`` import so we don't blow up on ``ModuleNotFoundError``
    in venvs that don't ship ``redis`` (notably the CI root venv).
    """
    pytest.importorskip("redis", reason="redis package not installed in this venv")
    from kene_api.redis_client import get_redis_service

    service = get_redis_service()
    if not service.is_available():
        pytest.skip("Redis unavailable — cannot run TTL fixture tests")
    return TTLController(service)
