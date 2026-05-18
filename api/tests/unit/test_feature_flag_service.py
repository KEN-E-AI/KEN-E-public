"""Unit tests for FeatureFlagService.evaluate_batch.

Coverage: FF-PRD-01 AC-6 (batch contract, unknown flags) and AC-8 (cache behaviour).

Uses MagicMock for the Firestore client (no emulator — FF-9 owns emulator coverage)
and a controllable FakeClock for time_provider so TTL logic is exercised
deterministically without freezegun.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.models.feature_flag_models import (
    EvaluationContext,
    FeatureFlag,
    FlagEvaluation,
    TargetingRules,
)
from src.kene_api.services.feature_flag_service import (
    TTL_SECONDS,
    FeatureFlagService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_flag(**overrides: object) -> FeatureFlag:
    base: dict[str, object] = {
        "key": "test_flag",
        "description": "A test flag",
        "default_enabled": False,
        "is_active": True,
        "owner": "dev@ken-e.ai",
        "targeting_rules": TargetingRules(),
        "bucketing_entity": "account",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return FeatureFlag(**base)


def _ctx(**overrides: object) -> EvaluationContext:
    base: dict[str, object] = {
        "user_id": "uid_123",
        "user_email": "alice@example.com",
        "organization_id": None,
        "account_id": None,
    }
    base.update(overrides)
    return EvaluationContext(**base)


class FakeClock:
    """Monotonic clock whose value can be advanced deterministically."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _mock_db_with_flag(flag: FeatureFlag | None) -> MagicMock:
    """Return a MagicMock Firestore client whose .document().get() returns flag."""
    db = MagicMock()
    doc = MagicMock()
    if flag is None:
        doc.exists = False
        doc.to_dict.return_value = {}
    else:
        doc.exists = True
        # to_dict() excludes the key field; _fetch_flag merges it from the doc ID.
        data = flag.model_dump(mode="json")
        data.pop("key", None)
        doc.to_dict.return_value = data
    db.collection.return_value.document.return_value.get.return_value = doc
    return db


# ---------------------------------------------------------------------------
# Case 1 — Unknown flag returns unknown_flag without raising
# ---------------------------------------------------------------------------


async def test_unknown_flag_returns_unknown_flag_no_exception() -> None:
    """AC-6: unknown key returns reason='unknown_flag', enabled=False, no raise."""
    db = _mock_db_with_flag(None)
    svc = FeatureFlagService(db=db, time_provider=FakeClock())

    result = await svc.evaluate_batch(["nonexistent_key"], _ctx())

    assert result == {
        "nonexistent_key": FlagEvaluation(
            key="nonexistent_key", enabled=False, reason="unknown_flag"
        )
    }


# ---------------------------------------------------------------------------
# Case 2 — Batch with one known + one unknown
# ---------------------------------------------------------------------------


async def test_batch_mixed_known_and_unknown() -> None:
    """Both entries appear in the response dict with correct enabled/reason."""
    flag = _make_flag(key="known_flag", default_enabled=True)
    db = MagicMock()

    def _doc_factory(flag_key: str) -> MagicMock:
        doc = MagicMock()
        if flag_key == "known_flag":
            doc.exists = True
            data = flag.model_dump(mode="json")
            data.pop("key", None)
            doc.to_dict.return_value = data
        else:
            doc.exists = False
            doc.to_dict.return_value = {}
        return doc

    db.collection.return_value.document.side_effect = lambda k: MagicMock(
        get=MagicMock(return_value=_doc_factory(k))
    )

    svc = FeatureFlagService(db=db, time_provider=FakeClock())
    result = await svc.evaluate_batch(["known_flag", "ghost_flag"], _ctx())

    assert result["known_flag"] == FlagEvaluation(
        key="known_flag", enabled=True, reason="default"
    )
    assert result["ghost_flag"] == FlagEvaluation(
        key="ghost_flag", enabled=False, reason="unknown_flag"
    )


# ---------------------------------------------------------------------------
# Case 3 — AC-8: second call within 60 s hits cache (single Firestore read)
# ---------------------------------------------------------------------------


async def test_second_call_within_ttl_uses_cache() -> None:
    """AC-8: two evaluate_batch calls within 60 s issue exactly one Firestore read."""
    flag = _make_flag(key="cached_flag")
    db = _mock_db_with_flag(flag)
    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    await svc.evaluate_batch(["cached_flag"], _ctx())
    clock.advance(30.0)  # still within TTL
    await svc.evaluate_batch(["cached_flag"], _ctx())

    get_mock = db.collection.return_value.document.return_value.get
    assert get_mock.call_count == 1, (
        f"Expected 1 Firestore read; got {get_mock.call_count}"
    )


# ---------------------------------------------------------------------------
# Case 4 — AC-8: after TTL expires, cache reloads (second Firestore read)
# ---------------------------------------------------------------------------


async def test_cache_reloads_after_ttl_expires() -> None:
    """After TTL_SECONDS the cache entry expires and a fresh Firestore read is issued."""
    flag = _make_flag(key="expiring_flag")
    db = _mock_db_with_flag(flag)
    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    await svc.evaluate_batch(["expiring_flag"], _ctx())
    clock.advance(TTL_SECONDS + 1.0)  # past expiry
    await svc.evaluate_batch(["expiring_flag"], _ctx())

    get_mock = db.collection.return_value.document.return_value.get
    assert get_mock.call_count == 2, (
        f"Expected 2 Firestore reads (initial + reload); got {get_mock.call_count}"
    )


# ---------------------------------------------------------------------------
# Case 5 — Cold-batch parallelism: N cold keys trigger concurrent reads
# ---------------------------------------------------------------------------


async def test_cold_batch_reads_are_parallel() -> None:
    """N cold keys must issue fetches concurrently, not sequentially.

    Strategy: replace _fetch_flag with a coroutine that yields via
    asyncio.sleep(0) so the event loop can observe all in-flight calls
    before any completes. Assert that max concurrent count >= 2.
    """
    max_concurrent: list[int] = [0]
    current: list[int] = [0]

    async def fake_fetch(flag_key: str) -> None:
        current[0] += 1
        if current[0] > max_concurrent[0]:
            max_concurrent[0] = current[0]
        await asyncio.sleep(0)  # yield; lets the next coroutine start
        current[0] -= 1
        return None  # treat all as absent (unknown_flag)

    flag_keys = [f"cold_key_{i}" for i in range(5)]
    db = MagicMock()
    svc = FeatureFlagService(db=db, time_provider=FakeClock())

    with patch.object(svc, "_fetch_flag", side_effect=fake_fetch):
        await svc.evaluate_batch(flag_keys, _ctx())

    assert max_concurrent[0] >= 2, (
        f"Expected >= 2 concurrent _fetch_flag calls; got max {max_concurrent[0]}"
    )


# ---------------------------------------------------------------------------
# Case 6 — Transient Firestore error: unknown_flag returned, cache NOT poisoned
# ---------------------------------------------------------------------------


async def test_transient_firestore_error_returns_unknown_flag_and_is_not_cached(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Firestore error → unknown_flag for this batch; next call retries Firestore."""
    db = MagicMock()
    db.collection.return_value.document.return_value.get.side_effect = RuntimeError(
        "Firestore boom"
    )
    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    with caplog.at_level(
        logging.ERROR, logger="src.kene_api.services.feature_flag_service"
    ):
        result = await svc.evaluate_batch(["error_flag"], _ctx())

    assert result == {
        "error_flag": FlagEvaluation(
            key="error_flag", enabled=False, reason="unknown_flag"
        )
    }

    # The error was logged.
    assert any("feature_flag_fetch_error" in r.message for r in caplog.records)

    # Now fix the Firestore stub and call again within TTL — should retry.
    db.collection.return_value.document.return_value.get.side_effect = None
    flag = _make_flag(key="error_flag")
    doc = MagicMock()
    doc.exists = True
    data = flag.model_dump(mode="json")
    data.pop("key", None)
    doc.to_dict.return_value = data
    db.collection.return_value.document.return_value.get.return_value = doc

    clock.advance(1.0)  # still within TTL, but error path skipped caching
    result2 = await svc.evaluate_batch(["error_flag"], _ctx())

    # The error was NOT cached — the second call retries Firestore and now succeeds.
    # With default_enabled=False and no targeting rules, the result is reason="default".
    assert result2["error_flag"] == FlagEvaluation(
        key="error_flag", enabled=False, reason="default"
    )
    # Both calls hit Firestore (total=2) since the first error was not cached.
    assert db.collection.return_value.document.return_value.get.call_count == 2


# ---------------------------------------------------------------------------
# Case 7 — Cached unknown verdict: absent key requested twice → one Firestore read
# ---------------------------------------------------------------------------


async def test_absent_key_cached_for_ttl() -> None:
    """Unknown key (doc absent) is cached so a second call doesn't re-read Firestore."""
    db = _mock_db_with_flag(None)
    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    await svc.evaluate_batch(["ghost_key"], _ctx())
    clock.advance(30.0)  # within TTL
    await svc.evaluate_batch(["ghost_key"], _ctx())

    get_mock = db.collection.return_value.document.return_value.get
    assert get_mock.call_count == 1, (
        f"Expected 1 Firestore read for absent key; got {get_mock.call_count}"
    )


# ---------------------------------------------------------------------------
# Case 8 — Per-key isolation: caching flag A does not prevent fresh read for B
# ---------------------------------------------------------------------------


async def test_cache_per_key_isolation() -> None:
    """Caching flag_a does not affect whether flag_b issues a Firestore read."""
    flag_a = _make_flag(key="flag_a")
    flag_b = _make_flag(key="flag_b")

    db = MagicMock()

    def _doc(flag_key: str) -> MagicMock:
        flag = flag_a if flag_key == "flag_a" else flag_b
        doc = MagicMock()
        doc.exists = True
        data = flag.model_dump(mode="json")
        data.pop("key", None)
        doc.to_dict.return_value = data
        return doc

    db.collection.return_value.document.side_effect = lambda k: MagicMock(
        get=MagicMock(return_value=_doc(k))
    )

    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    # Warm flag_a.
    await svc.evaluate_batch(["flag_a"], _ctx())

    # Now request flag_b (cold) — should still issue a Firestore read for flag_b.
    doc_b_mock = MagicMock()
    doc_b_mock.exists = True
    b_data = flag_b.model_dump(mode="json")
    b_data.pop("key", None)
    doc_b_mock.to_dict.return_value = b_data

    b_document = MagicMock()
    b_document.get.return_value = doc_b_mock

    def _document_side_effect(key: str) -> MagicMock:
        if key == "flag_b":
            return b_document
        return MagicMock(get=MagicMock(return_value=_doc(key)))

    db.collection.return_value.document.side_effect = _document_side_effect

    await svc.evaluate_batch(["flag_b"], _ctx())
    assert b_document.get.call_count == 1


# ---------------------------------------------------------------------------
# Case 9 — Targeting-rule integration: wires through to evaluate() unchanged
# ---------------------------------------------------------------------------


async def test_evaluate_batch_wires_through_to_evaluate() -> None:
    """A flag with default_enabled=True returns reason='default', enabled=True."""
    flag = _make_flag(
        key="ga_flag",
        default_enabled=True,
        is_active=True,
        targeting_rules=TargetingRules(),
    )
    db = _mock_db_with_flag(flag)
    svc = FeatureFlagService(db=db, time_provider=FakeClock())

    result = await svc.evaluate_batch(["ga_flag"], _ctx())

    assert result["ga_flag"] == FlagEvaluation(
        key="ga_flag", enabled=True, reason="default"
    )


# ---------------------------------------------------------------------------
# Case 10 — AC-13 cache_hit plumbing: warm reads log cache_hit=True
# ---------------------------------------------------------------------------


async def test_warm_cache_read_logs_cache_hit_true(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second evaluate_batch call within TTL must log cache_hit=True via evaluate()."""
    flag = _make_flag(key="warm_flag")
    db = _mock_db_with_flag(flag)
    clock = FakeClock(start=0.0)
    svc = FeatureFlagService(db=db, time_provider=clock)

    await svc.evaluate_batch(["warm_flag"], _ctx())  # cold read — warms the cache

    caplog.clear()  # discard cold-read records before asserting warm-read behaviour
    with caplog.at_level(
        logging.INFO, logger="src.kene_api.services.feature_flag_service"
    ):
        await svc.evaluate_batch(["warm_flag"], _ctx())  # warm read

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info_records) == 1
    assert info_records[0].__dict__["cache_hit"] is True
