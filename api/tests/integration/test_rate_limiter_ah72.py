"""Regression test for AH-72 — E2E migration + drop CH-54 tactical overrides.

Proves that the structural fix delivered by AH-71 (authenticated_key_strategy
wired into token_rate_limiter) makes the CH-54 tactical overrides in
start_e2e_stack.sh unnecessary.

Specifically this test covers AH-PRD-10 §7 AC-2:
  "Concurrent Playwright requests from different test-user logins don't share
   a bucket; the CH-54 KENE_TOKEN_RATE_LIMIT_PER_MINUTE=10000 override is
   removed from start_e2e_stack.sh and CI stays green at the canonical 60/min
   default."

The DM-104 e2e flake was caused by all Playwright requests coming from
127.0.0.1 — with the old IP-keyed strategy every test user shared a single
bucket and parallel tests stomped on each other's quota.  This test verifies
that the canonical 60/min default is sufficient when each user has their own
per-UID bucket.

Test structure mirrors the seeded users in start_e2e_stack.sh:
  alice-uid  / alice@ken-e.ai  (super-admin in the emulator)
  bob-uid    / bob@example.com (regular user)
and uses the same 127.0.0.1 source IP that Playwright requests carry in CI.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from src.kene_api.auth.models import UserContext
from src.kene_api.rate_limiter import (
    SwitchableRateLimiter,
    authenticated_key_strategy,
    build_rate_limiter,
)

# ---------------------------------------------------------------------------
# Helpers — mirror the e2e stack's seeded identities and network topology
# ---------------------------------------------------------------------------


def _make_ci_request(url_path: str = "/api/v1/chat/completions") -> Request:
    """Build a mock request with the 127.0.0.1 source IP Playwright uses in CI.

    The e2e stack runs on loopback: every Playwright request arrives from
    127.0.0.1 — the exact topology that triggered the DM-104 flake under the
    old IP-keyed strategy.
    """
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    # Playwright in CI goes through loopback; no X-Forwarded-For chain.
    # _validated_ip_key will return the sentinel key for a missing XFF header —
    # which is fine here because authenticated_key_strategy uses ctx.user_id,
    # not the IP, when ctx is provided.
    request.headers = {"X-Forwarded-For": "127.0.0.1"}
    request.url = MagicMock()
    request.url.path = url_path
    return request


def _make_e2e_user(uid: str, email: str) -> UserContext:
    """Build a UserContext matching start_e2e_stack.sh seeded users."""
    return UserContext(
        user_id=uid,
        email=email,
        organization_permissions={},
        account_permissions={},
        roles=[],
    )


def _make_token_limiter(fake_redis: Any, rpm: int = 60, rph: int = 1000) -> SwitchableRateLimiter:
    """Build a token_rate_limiter clone backed by fakeredis.

    Uses authenticated_key_strategy — identical to the live token_rate_limiter
    after AH-71 wiring.
    """
    return build_rate_limiter(  # type: ignore[return-value]
        name="token_ah72_regression",
        requests_per_minute=rpm,
        requests_per_hour=rph,
        key_strategy=authenticated_key_strategy,
        fallback_cap_divisor=1,
        fail_open=True,
        redis_client=fake_redis,
    )


# ---------------------------------------------------------------------------
# AC-2 regression: concurrent test users don't share a bucket at 60/min default
# ---------------------------------------------------------------------------


class TestCh54OverrideNoLongerNeeded:
    """AH-PRD-10 §7 AC-2: the canonical 60/min default is sufficient when each
    test user gets their own per-UID bucket.

    Before AH-71 (IP-keyed strategy): all Playwright test users shared a single
    127.0.0.1 bucket.  With N parallel test processes each making ~10 requests,
    the shared bucket exhausted quickly and triggered 429s — leading CH-54 to
    set KENE_TOKEN_RATE_LIMIT_PER_MINUTE=10000 as a band-aid.

    After AH-71 (authenticated_key_strategy): each UID gets its own bucket.
    Alice and Bob can each make up to 60 requests per minute with no collision.
    """

    async def test_alice_and_bob_each_get_full_60_per_min_quota(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Alice and Bob each issue 60 requests; neither triggers 429.

        Both share 127.0.0.1 — the exact CI topology that caused DM-104.
        With authenticated_key_strategy, their buckets are independent.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter = _make_token_limiter(fake_redis, rpm=60, rph=1000)
        request = _make_ci_request()

        alice = _make_e2e_user("alice-uid", "alice@ken-e.ai")
        bob = _make_e2e_user("bob-uid", "bob@example.com")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # Both users issue their full 60/min quota — no 429 expected.
            for _ in range(60):
                await limiter.check_rate_limit(request, alice)
            for _ in range(60):
                await limiter.check_rate_limit(request, bob)

            # Alice's 61st request hits her own bucket ceiling.
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, alice)
            assert exc_info.value.status_code == 429

            # Bob's 61st request hits his own bucket ceiling — independent of Alice.
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, bob)
            assert exc_info.value.status_code == 429

    async def test_concurrent_requests_from_distinct_users_no_shared_bucket(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Simulate concurrent CI parallelism: 4 distinct test users each making
        10 requests concurrently — all succeed at the canonical 60/min default.

        This is the load pattern that triggered the DM-104 flake:
        - 4 Playwright workers each running tests that call the API ~10 times
        - All coming from 127.0.0.1
        - Under IP-keyed: 40 shared requests exhausted the old CH-54-era 10/min
          bucket almost immediately (without the 10000 override)
        - Under UID-keyed: 40 requests across 4 distinct users = 10 per user, well
          within 60/min per user
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter = _make_token_limiter(fake_redis, rpm=60, rph=1000)
        request = _make_ci_request()

        users = [
            _make_e2e_user("alice-uid", "alice@ken-e.ai"),
            _make_e2e_user("bob-uid", "bob@example.com"),
            _make_e2e_user("carol-uid", "carol@example.com"),
            _make_e2e_user("dave-uid", "dave@example.com"),
        ]
        requests_per_user = 10

        async def run_user_requests(ctx: UserContext) -> int:
            count = 0
            for _ in range(requests_per_user):
                await limiter.check_rate_limit(request, ctx)
                count += 1
            return count

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # Fire all user request batches concurrently — mirrors Playwright parallelism.
            results = await asyncio.gather(*[run_user_requests(u) for u in users])

        total = sum(results)
        assert total == len(users) * requests_per_user, (
            f"Expected all {len(users) * requests_per_user} requests to succeed "
            f"(per-UID buckets at 60/min each), but only {total} did. "
            "This indicates the old IP-keyed shared-bucket regression has returned."
        )

    async def test_ip_keyed_would_have_failed_proving_the_fix_is_load_bearing(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Negative-control: demonstrate that IP-keyed strategy at the old e2e-
        visible threshold (10/min without the CH-54 override) would have caused
        exactly the DM-104 failure pattern.

        This test is intentionally asserting failure under ip_only_key_strategy
        to prove the regression test is actually testing the right thing.
        If authenticated_key_strategy were swapped back to ip_only_key_strategy,
        this negative-control scenario would fire and the test above would fail.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        from src.kene_api.rate_limiter import ip_only_key_strategy

        # Simulate the old IP-keyed limiter at a low threshold
        # (demonstrates what the DM-104 flake looked like without CH-54's 10000 override).
        ip_limiter = build_rate_limiter(  # type: ignore[return-value]
            name="ip_keyed_control",
            requests_per_minute=10,
            requests_per_hour=100,
            key_strategy=ip_only_key_strategy,
            fallback_cap_divisor=1,
            fail_open=False,
            redis_client=fake_redis,
        )
        request = _make_ci_request()

        alice = _make_e2e_user("alice-uid", "alice@ken-e.ai")
        bob = _make_e2e_user("bob-uid", "bob@example.com")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # Fill the shared IP bucket (Alice + Bob together exceed the limit)
            allowed_count = 0
            hit_429 = False
            for user in [alice, bob]:
                for _ in range(6):
                    try:
                        await ip_limiter.check_rate_limit(request, user)
                        allowed_count += 1
                    except HTTPException as exc:
                        if exc.status_code == 429:
                            hit_429 = True
                        break
                if hit_429:
                    break

        # With IP-keyed strategy and a 10/min cap, 12 combined requests (6 each)
        # from the same IP must have triggered a 429 — this is the DM-104 pattern.
        assert hit_429, (
            "Expected IP-keyed strategy to trigger 429 when two users share the "
            "same 127.0.0.1 IP bucket at 10/min. If this fails, the negative "
            "control is broken and the regression test above may be giving false "
            "confidence."
        )
