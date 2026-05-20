"""Unit tests for api/scripts/seed_chat_feature_flags.py.

Tests:
  - Three flags are submitted with the correct keys, defaults, and actor email.
  - Idempotent: a second call catches DuplicateFeatureFlagError and skips.
  - --dry-run produces zero create_flag calls.
  - CHAT_FLAGS_SCOPED_OUT_OF_V1 and CHAT_FLAGS_TO_REGISTER are disjoint.
  - audit actor_email is exactly 'system+ch-19-seed@ken-e.ai'.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.kene_api.services.feature_flag_service import DuplicateFeatureFlagError

from api.scripts.seed_chat_feature_flags import (
    _ACTOR_EMAIL,
    CHAT_FLAGS_SCOPED_OUT_OF_V1,
    CHAT_FLAGS_TO_REGISTER,
    _seed_flags,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _make_flag_stub(key: str) -> MagicMock:
    stub = MagicMock()
    stub.key = key
    return stub


# ---------------------------------------------------------------------------
# Tests: registry invariants (no I/O)
# ---------------------------------------------------------------------------


class TestRegistryInvariants:
    def test_exactly_three_flags_registered(self) -> None:
        assert len(CHAT_FLAGS_TO_REGISTER) == 3

    def test_registered_keys(self) -> None:
        assert {f.key for f in CHAT_FLAGS_TO_REGISTER} == {
            "chat_v2_enabled",
            "chat_status_detail_enabled",
            "chat_categories_enabled",
        }

    def test_all_default_disabled(self) -> None:
        for flag in CHAT_FLAGS_TO_REGISTER:
            assert flag.default_enabled is False, (
                f"{flag.key} should default to disabled at registration time"
            )

    def test_scoped_out_disjoint_from_registered(self) -> None:
        registered_keys = frozenset(f.key for f in CHAT_FLAGS_TO_REGISTER)
        assert registered_keys & CHAT_FLAGS_SCOPED_OUT_OF_V1 == frozenset()

    def test_actor_email(self) -> None:
        assert _ACTOR_EMAIL == "system+ch-19-seed@ken-e.ai"


# ---------------------------------------------------------------------------
# Tests: _seed_flags (async logic, mocked FeatureFlagService)
# ---------------------------------------------------------------------------


class TestSeedFlags:
    def _make_service(self) -> MagicMock:
        svc = MagicMock()
        svc.create_flag = AsyncMock(
            side_effect=lambda req, actor_email: _make_flag_stub(req.key)
        )
        return svc

    def test_creates_three_flags_with_correct_actor(self) -> None:
        fake_db = MagicMock()
        svc = self._make_service()

        with patch(
            "api.scripts.seed_chat_feature_flags.FeatureFlagService",
            return_value=svc,
        ):
            results = _run(_seed_flags(fake_db, dry_run=False))

        assert set(results.keys()) == {
            "chat_v2_enabled",
            "chat_status_detail_enabled",
            "chat_categories_enabled",
        }
        assert all(v == "created" for v in results.values())
        assert svc.create_flag.call_count == 3

        # Every call must use the canonical actor email.
        for call in svc.create_flag.call_args_list:
            assert call.kwargs.get("actor_email") == _ACTOR_EMAIL or call.args[1] == _ACTOR_EMAIL

    def test_idempotent_on_duplicate(self) -> None:
        """Second run catches DuplicateFeatureFlagError and records 'already_exists'."""
        fake_db = MagicMock()
        svc = MagicMock()
        svc.create_flag = AsyncMock(side_effect=DuplicateFeatureFlagError("exists"))

        with patch(
            "api.scripts.seed_chat_feature_flags.FeatureFlagService",
            return_value=svc,
        ):
            results = _run(_seed_flags(fake_db, dry_run=False))

        assert all(v == "already_exists" for v in results.values())
        assert svc.create_flag.call_count == 3

    def test_dry_run_produces_no_create_calls(self) -> None:
        fake_db = MagicMock()
        svc = self._make_service()

        with patch(
            "api.scripts.seed_chat_feature_flags.FeatureFlagService",
            return_value=svc,
        ):
            results = _run(_seed_flags(fake_db, dry_run=True))

        svc.create_flag.assert_not_called()
        assert all(v == "dry_run" for v in results.values())

    def test_partial_duplicate_mixed_results(self) -> None:
        """First flag already exists, other two are created."""
        fake_db = MagicMock()
        call_count = [0]

        async def _side_effect(req: Any, actor_email: str) -> Any:
            call_count[0] += 1
            if call_count[0] == 1:
                raise DuplicateFeatureFlagError("already exists")
            return _make_flag_stub(req.key)

        svc = MagicMock()
        svc.create_flag = AsyncMock(side_effect=_side_effect)

        with patch(
            "api.scripts.seed_chat_feature_flags.FeatureFlagService",
            return_value=svc,
        ):
            results = _run(_seed_flags(fake_db, dry_run=False))

        outcomes = list(results.values())
        assert outcomes.count("already_exists") == 1
        assert outcomes.count("created") == 2
