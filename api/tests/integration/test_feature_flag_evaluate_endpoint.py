"""Integration tests for POST /api/v1/feature-flags/evaluate.

Exercises the full evaluate path — Firebase auth, server-built EvaluationContext,
email-domain targeting, request-body validation, body-spoofing resistance, and the
60 s in-process LRU cache — against the real Firestore emulator.

PRD §8 integration scenarios all covered here. Unit-level isolation (mock Firestore)
lives in test_feature_flag_router.py and test_feature_flag_service.py.

Enable by setting the FIRESTORE_EMULATOR_HOST environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_feature_flag_evaluate_endpoint.py -v

Dep: mock_firebase_auth autouse fixture (conftest.py:51) must remain a session-scoped
autouse so the 401 case behaves correctly; if that fixture becomes non-autouse, this
test should be revised to patch verify_id_token explicitly.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
import src.kene_api.services.feature_flag_service as _ff_svc_module
from fastapi.testclient import TestClient
from src.kene_api.auth.user_context import UserContext, get_current_user_context
from src.kene_api.dependencies import get_feature_flag_service
from src.kene_api.main import app
from src.kene_api.models.feature_flag_models import FeatureFlag, TargetingRules
from src.kene_api.services.feature_flag_service import (
    TTL_SECONDS,
    FeatureFlagService,
)

# ---------------------------------------------------------------------------
# Skip gate — identical to test_user_deletion_no_orphans.py:72-79
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _emulator_client() -> Any:
    """Real Firestore client pointed at the local emulator."""
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _make_user(
    email: str = "user@example.com", user_id: str = "uid_test"
) -> UserContext:
    return UserContext(
        user_id=user_id,
        email=email,
        organization_permissions={},
        account_permissions={},
    )


def _seed_flag(db: Any, flag_key: str) -> None:
    """Seed feature_flags/{flag_key} with email_domains=['ken-e.ai'], default_enabled=False.

    Uses FeatureFlag.model_dump(mode='json') to guarantee field completeness at
    compile time — a missing required field surfaces here instead of as a flaky
    'unknown_flag' reason deep in the test assertion (plan Decision 3).
    """
    flag = FeatureFlag(
        key=flag_key,
        description="Integration test flag",
        default_enabled=False,
        is_active=True,
        targeting_rules=TargetingRules(email_domains=["ken-e.ai"]),
        bucketing_entity="account",
        owner="test@ken-e.ai",
        created_at=_NOW,
        updated_at=_NOW,
    )
    seed_data = flag.model_dump(mode="json")
    seed_data.pop("key", None)
    db.collection("feature_flags").document(flag_key).set(seed_data)


class FakeClock:
    """Monotonic clock whose value can be advanced deterministically."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def emulator_db() -> Any:
    """Real Firestore emulator client, shared across the test class."""
    return _emulator_client()


@pytest.fixture
def run_id() -> str:
    """Unique 8-hex suffix per test run to prevent cross-run pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def flag_key(run_id: str) -> str:
    return f"test_flag_{run_id}"


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
    """Guarantee dependency_overrides is clean and the service singleton is reset.

    Calls get_feature_flag_service.cache_clear() belt-and-braces so even if an
    earlier test warmed the module-level singleton, this test starts fresh
    (plan Risk 2 mitigation).
    """
    from src.kene_api.services.feature_flag_service import (
        get_feature_flag_service as _svc_singleton,
    )

    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()
    yield
    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()


@pytest.fixture(autouse=True)
def cleanup_emulator(
    emulator_db: Any,
    flag_key: str,
) -> Generator[None, None, None]:
    """Best-effort cleanup of the seeded flag doc before and after each test.

    Pre-test pass removes stale data from a prior failed run; post-test pass
    removes data from the current run including the case where an assertion
    fired before manual cleanup.  Mirrors test_user_deletion_no_orphans.py:184-224.
    """

    def _delete() -> None:
        try:
            emulator_db.collection("feature_flags").document(flag_key).delete()
        except Exception:
            pass

    _delete()
    yield
    _delete()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestEvaluateEndpoint:
    """PRD §8 integration scenarios for POST /api/v1/feature-flags/evaluate.

    All seven test methods share a single class so they reuse the class-scoped
    emulator_db fixture and the common _install_overrides helper without
    duplicating fixture wiring (plan Decision 2).
    """

    def _install_overrides(
        self,
        emulator_db: Any,
        email: str,
        user_id: str = "uid_test",
    ) -> tuple[FeatureFlagService, FakeClock]:
        """Wire per-test auth and service dependency overrides.

        Returns (svc, clock) so tests can spy on _fetch_flag or advance time.
        Mirrors test_feature_flag_router.py:127 override pattern.
        """
        clock = FakeClock()
        svc = FeatureFlagService(db=emulator_db, time_provider=clock)
        user = _make_user(email=email, user_id=user_id)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: svc
        return svc, clock

    def test_ken_e_ai_domain_match(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """@ken-e.ai token → enabled=True, reason='domain_match' (PRD §8 case 1)."""
        _seed_flag(emulator_db, flag_key)
        self._install_overrides(emulator_db, email="alice@ken-e.ai")

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": [flag_key]},
        )

        assert resp.status_code == 200
        ev = resp.json()["evaluations"][flag_key]
        assert ev == {"key": flag_key, "enabled": True, "reason": "domain_match"}

    def test_non_matching_domain_returns_default(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """Non-@ken-e.ai token → enabled=False, reason='default' (PRD §8 case 2)."""
        _seed_flag(emulator_db, flag_key)
        self._install_overrides(emulator_db, email="bob@example.com")

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": [flag_key]},
        )

        assert resp.status_code == 200
        ev = resp.json()["evaluations"][flag_key]
        assert ev == {"key": flag_key, "enabled": False, "reason": "default"}

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401 before the service is reached (PRD §8 case 3).

        No auth or service override is installed so the real auth dependency runs.
        HTTPBearer (auto_error=False) in get_current_user_context returns None
        credentials → the dependency raises 401 before evaluate_batch is called.

        If this assertion fires it means _reset_overrides failed to clear a stale
        override from a prior test, which would make the 401 test meaningless.
        """
        assert get_current_user_context not in app.dependency_overrides, (
            "get_current_user_context must not be overridden for this 401 test — "
            "_reset_overrides should have cleared it"
        )
        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["some_flag"]},
        )
        assert resp.status_code == 401

    def test_empty_flag_keys_returns_422(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """flag_keys=[] violates min_length=1 → 422 (PRD §8 case 4 / AC-10)."""
        self._install_overrides(emulator_db, email="alice@ken-e.ai")

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": []},
        )
        assert resp.status_code == 422

    def test_oversized_flag_keys_returns_422(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """flag_keys with 101 distinct entries violates max_length=100 → 422 (PRD §8 case 5 / AC-10).

        Each key matches FLAG_KEY_REGEX so the list-length constraint is what triggers 422,
        not per-item validation (plan Decision 6).
        """
        self._install_overrides(emulator_db, email="alice@ken-e.ai")

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": [f"valid_key_{i:03d}" for i in range(101)]},
        )
        assert resp.status_code == 422

    def test_body_spoof_fields_are_ignored(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """Body identity fields cannot override the server-built EvaluationContext (PRD §8 case 6 / AC-9).

        Spoof probe: client sends user_id/account_id/organization_id/user_email in the
        body alongside flag_keys; assert EvaluationContext.user_id and user_email come
        from the token, not the body.

        Patches the module-level evaluate() function (not the bound method) so the test
        pins the seam documented in PRD §4 — plan Decision 4.
        """
        _seed_flag(emulator_db, flag_key)
        self._install_overrides(emulator_db, email="alice@ken-e.ai", user_id="real_uid")

        captured_ctx: list[Any] = []
        real_evaluate = _ff_svc_module.evaluate

        def _capturing_evaluate(flag: Any, ctx: Any, *, cache_hit: bool) -> Any:
            captured_ctx.append(ctx)
            return real_evaluate(flag, ctx, cache_hit=cache_hit)

        with patch.object(_ff_svc_module, "evaluate", side_effect=_capturing_evaluate):
            resp = client.post(
                "/api/v1/feature-flags/evaluate",
                json={
                    "flag_keys": [flag_key],
                    "user_id": "spoof_uid",
                    "user_email": "attacker@evil.com",
                    "organization_id": "spoof_org",
                    "account_id": "spoof_acc",
                },
            )

        assert resp.status_code == 200
        assert len(captured_ctx) == 1
        ctx = captured_ctx[0]
        assert ctx.user_id == "real_uid"
        assert str(ctx.user_email) == "alice@ken-e.ai"
        assert ctx.organization_id is None
        assert ctx.account_id is None

    def test_cache_within_ttl_single_firestore_read(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """Two calls within TTL issue exactly one Firestore read; past TTL reloads (PRD §8 cache / AC-8).

        Uses FakeClock to avoid a real 60 s wait and patch.object(wraps=) to count
        _fetch_flag invocations while still exercising the real emulator (plan Decision 3).
        """
        _seed_flag(emulator_db, flag_key)
        svc, clock = self._install_overrides(emulator_db, email="alice@ken-e.ai")

        with patch.object(svc, "_fetch_flag", wraps=svc._fetch_flag) as spy_cold:
            resp1 = client.post(
                "/api/v1/feature-flags/evaluate",
                json={"flag_keys": [flag_key]},
            )
            clock.advance(30.0)  # still within TTL
            resp2 = client.post(
                "/api/v1/feature-flags/evaluate",
                json={"flag_keys": [flag_key]},
            )

        # Assert status first so a broken service surfaces the HTTP error before
        # the call_count assertion fires with a confusing message (CLAUDE.md §T-8).
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["evaluations"][flag_key]["enabled"] is True
        assert resp2.json()["evaluations"][flag_key]["enabled"] is True
        assert spy_cold.call_count == 1, (
            f"Expected exactly 1 Firestore read for 2 calls within TTL; "
            f"got {spy_cold.call_count}"
        )

        # Advance past TTL — next call must reload from Firestore.
        clock.advance(TTL_SECONDS + 1.0)
        with patch.object(svc, "_fetch_flag", wraps=svc._fetch_flag) as spy_reload:
            resp3 = client.post(
                "/api/v1/feature-flags/evaluate",
                json={"flag_keys": [flag_key]},
            )

        assert resp3.status_code == 200
        assert resp3.json()["evaluations"][flag_key]["enabled"] is True
        assert spy_reload.call_count == 1, (
            f"Expected 1 Firestore reload after TTL expiry; got {spy_reload.call_count}"
        )
