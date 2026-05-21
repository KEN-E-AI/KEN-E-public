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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.models.feature_flag_models import (
    EvaluationContext,
    FeatureFlag,
    FeatureFlagWriteRequest,
    FlagEvaluation,
    TargetingRules,
)
from src.kene_api.services.feature_flag_service import (
    TTL_SECONDS,
    DuplicateFeatureFlagError,
    FeatureFlagNotFoundError,
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
# Case 4b — TTL=0 boundary: same-timestamp call is a cache hit, not a miss
# ---------------------------------------------------------------------------


async def test_ttl_zero_same_timestamp_is_cache_hit() -> None:
    """With TTL_SECONDS=0 the freshness check must use strict < (not <=).

    At install time expires_at == now.  A subsequent call at the same
    monotonic timestamp must NOT treat the entry as expired — doing so would
    cause every request to incur a Firestore read even though TTL=0 is
    intentionally used only for the E2E kill-switch scenario (where one fresh
    read per request is the correct behaviour, but the first call within that
    request must use the entry it just fetched).

    Regression guard: the `<=` bug in lines ~216 and ~250 of
    feature_flag_service.py would fail this test by issuing 2 Firestore reads.
    """
    flag = _make_flag(key="ttl_zero_flag")
    db = _mock_db_with_flag(flag)
    # Clock is frozen — both calls occur at the same monotonic timestamp.
    clock = FakeClock(start=42.0)

    with patch(
        "src.kene_api.services.feature_flag_service.TTL_SECONDS", 0
    ):
        svc = FeatureFlagService(db=db, time_provider=clock)
        result1 = await svc.evaluate_batch(["ttl_zero_flag"], _ctx())
        # Do NOT advance the clock — same timestamp as the install.
        result2 = await svc.evaluate_batch(["ttl_zero_flag"], _ctx())

    get_mock = db.collection.return_value.document.return_value.get
    assert get_mock.call_count == 1, (
        f"TTL=0 same-timestamp: expected 1 Firestore read; got {get_mock.call_count}"
    )
    assert result1["ttl_zero_flag"].reason != "unknown_flag", (
        "First call must not return unknown_flag with TTL=0"
    )
    assert result2["ttl_zero_flag"].reason != "unknown_flag", (
        "Second call at same timestamp must not return unknown_flag with TTL=0"
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


# ---------------------------------------------------------------------------
# TestListAndGetFlags — FF-12 (FF-PRD-02 B1)
# ---------------------------------------------------------------------------


class TestListAndGetFlags:
    """Unit tests for the two new FeatureFlagService read methods added in FF-12.

    Cases:
      (a) list_flags() returns docs from a mocked Firestore client in updated_at desc order.
      (b) list_flags() does NOT warm the per-flag TTL cache.
      (c) get_flag(key) returns the same FeatureFlag on the second call within TTL
          without a second Firestore read (cache-aware path).
      (d) get_flag("absent") returns None.
      (e) get_flag propagates Firestore exceptions (not swallowed).
    """

    def _make_list_db(self, flags: list[FeatureFlag]) -> MagicMock:
        """Mock Firestore client whose collection().stream() returns flag docs."""
        db = MagicMock()
        docs = []
        for flag in flags:
            doc = MagicMock()
            doc.id = flag.key
            data = flag.model_dump(mode="json")
            data.pop("key", None)
            doc.to_dict.return_value = data
            docs.append(doc)
        db.collection.return_value.stream.return_value = iter(docs)
        return db

    async def test_list_flags_returns_docs_sorted_updated_at_desc(self) -> None:
        """(a) list_flags() returns flags sorted by updated_at descending."""
        older = _make_flag(
            key="older_flag",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        newer = _make_flag(
            key="newer_flag",
            updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        db = self._make_list_db([older, newer])
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        result = await svc.list_flags()

        assert [f.key for f in result] == ["newer_flag", "older_flag"]

    async def test_list_flags_does_not_warm_cache(self) -> None:
        """(b) list_flags() bypasses the per-flag TTL cache entirely.

        After list_flags(), calling evaluate_batch for the same key should still
        issue a Firestore read (cache was not warmed).
        """
        flag = _make_flag(key="list_cache_test")
        list_db = self._make_list_db([flag])
        svc = FeatureFlagService(db=list_db, time_provider=FakeClock())

        await svc.list_flags()

        # The cache should still be empty for this key.
        assert "list_cache_test" not in svc._cache

    async def test_get_flag_returns_flag_and_caches(self) -> None:
        """(c) get_flag() returns the flag and the second call within TTL skips Firestore."""
        flag = _make_flag(key="get_test_flag")
        db = _mock_db_with_flag(flag)
        clock = FakeClock(start=0.0)
        svc = FeatureFlagService(db=db, time_provider=clock)

        result1 = await svc.get_flag("get_test_flag")
        clock.advance(30.0)  # still within TTL
        result2 = await svc.get_flag("get_test_flag")

        assert result1 is not None
        assert result1.key == "get_test_flag"
        assert (
            result2 is result1
        )  # identical object — served from cache, not reconstructed

        # Only one Firestore read should have been issued.
        get_mock = db.collection.return_value.document.return_value.get
        assert get_mock.call_count == 1

    async def test_get_flag_absent_returns_none(self) -> None:
        """(d) get_flag() returns None for a key with no matching Firestore doc."""
        db = _mock_db_with_flag(None)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        result = await svc.get_flag("absent_flag")

        assert result is None

    async def test_get_flag_propagates_firestore_exception(self) -> None:
        """(e) get_flag() does not swallow Firestore exceptions — admin callers need them."""
        db = MagicMock()
        db.collection.return_value.document.return_value.get.side_effect = RuntimeError(
            "Firestore boom"
        )
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with pytest.raises(RuntimeError, match="Firestore boom"):
            await svc.get_flag("boom_flag")


# ---------------------------------------------------------------------------
# TestMutatingFlags — FF-13 (FF-PRD-02 B2)
# ---------------------------------------------------------------------------


def _make_write_request(**overrides: object) -> FeatureFlagWriteRequest:
    base: dict[str, object] = {
        "key": "mut_flag",
        "description": "A mutable test flag",
        "default_enabled": False,
        "is_active": True,
        "owner": "dev@ken-e.ai",
        "targeting_rules": TargetingRules(),
        "bucketing_entity": "account",
    }
    base.update(overrides)
    return FeatureFlagWriteRequest(**base)


def _mock_create_db(raise_already_exists: bool = False) -> MagicMock:
    """Firestore mock suitable for create_flag tests."""
    from google.api_core import exceptions as gcp_exceptions

    db = MagicMock()
    doc_ref = MagicMock()
    if raise_already_exists:
        doc_ref.create.side_effect = gcp_exceptions.AlreadyExists("flag exists")
    else:
        doc_ref.create.return_value = None
    db.collection.return_value.document.return_value = doc_ref
    return db


def _mock_existing_db(flag: FeatureFlag) -> MagicMock:
    """Firestore mock that returns an existing flag doc on .get() and no-ops on .set/.delete."""
    db = MagicMock()
    doc = MagicMock()
    doc.exists = True
    data = flag.model_dump(mode="json")
    data.pop("key", None)
    doc.to_dict.return_value = data
    doc_ref = MagicMock()
    doc_ref.get.return_value = doc
    doc_ref.set.return_value = None
    doc_ref.delete.return_value = None
    db.collection.return_value.document.return_value = doc_ref
    return db


class TestMutatingFlags:
    """Unit tests for create_flag / update_flag / delete_flag on FeatureFlagService.

    All tests patch record_audit at the module level so Firestore's audit
    collection is never touched and the audit-invocation arguments are
    inspectable via mock assertions.

    Cases:
      (a) create_flag writes to Firestore and calls record_audit with action="create"
          and before=None.
      (b) create_flag raises DuplicateFeatureFlagError when Firestore raises AlreadyExists.
      (c) update_flag reads existing doc, stamps updated_at, preserves created_at, and
          calls record_audit with action="update".
      (d) update_flag raises FeatureFlagNotFoundError when the doc is absent.
      (e) delete_flag reads existing doc, deletes it, and calls record_audit with
          action="delete" and after=None.
      (f) delete_flag raises FeatureFlagNotFoundError when absent.
    """

    _AUDIT_PATCH = "src.kene_api.services.feature_flag_service.record_audit"

    async def test_create_flag_writes_firestore_and_calls_audit(self) -> None:
        """(a) Successful create: Firestore .create() called; audit action='create'."""
        db = _mock_create_db()
        svc = FeatureFlagService(db=db, time_provider=FakeClock())
        request = _make_write_request()

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            result = await svc.create_flag(request, "admin@ken-e.ai")

        # Firestore create was called once.
        db.collection.return_value.document.return_value.create.assert_called_once()

        # Returned flag has server-stamped timestamps.
        assert result.key == "mut_flag"
        assert result.created_at == result.updated_at

        # Audit called with action="create" and before=None in diff.
        # record_audit(db, flag_key, actor_email, action, diff)
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args.args
        assert call_args[3] == "create"
        diff = call_args[4]
        # A create diff should have at least the core fields and before=None for all.
        assert len(diff) > 0
        assert "key" in diff
        assert all(entry["before"] is None for entry in diff.values())

    async def test_create_flag_raises_duplicate_error_on_already_exists(self) -> None:
        """(b) Firestore AlreadyExists → DuplicateFeatureFlagError with offending key."""
        db = _mock_create_db(raise_already_exists=True)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock):
            with pytest.raises(DuplicateFeatureFlagError) as exc_info:
                await svc.create_flag(_make_write_request(), "admin@ken-e.ai")

        assert exc_info.value.key == "mut_flag"

    async def test_update_flag_stamps_updated_at_preserves_created_at_and_calls_audit(
        self,
    ) -> None:
        """(c) Successful update: server stamps updated_at, preserves created_at."""
        existing = _make_flag(
            key="mut_flag",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        db = _mock_existing_db(existing)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())
        request = _make_write_request(description="Updated description")

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            result = await svc.update_flag("mut_flag", request, "admin@ken-e.ai")

        # created_at preserved; updated_at is newer than the original.
        assert result.created_at == existing.created_at
        assert result.updated_at > existing.updated_at

        # Firestore .set() was called with the updated doc.
        db.collection.return_value.document.return_value.set.assert_called_once()

        # Audit called with action="update".
        mock_audit.assert_called_once()
        assert mock_audit.call_args.args[3] == "update"

    async def test_update_flag_raises_not_found_when_absent(self) -> None:
        """(d) update_flag on a non-existent key → FeatureFlagNotFoundError."""
        db = _mock_db_with_flag(None)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock):
            with pytest.raises(FeatureFlagNotFoundError) as exc_info:
                await svc.update_flag(
                    "ghost_flag",
                    _make_write_request(key="ghost_flag"),
                    "admin@ken-e.ai",
                )

        assert exc_info.value.key == "ghost_flag"

    async def test_delete_flag_deletes_doc_and_calls_audit(self) -> None:
        """(e) Successful delete: Firestore .delete() called; audit action='delete' with after=None."""
        existing = _make_flag(key="mut_flag")
        db = _mock_existing_db(existing)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await svc.delete_flag("mut_flag", "admin@ken-e.ai")

        db.collection.return_value.document.return_value.delete.assert_called_once()

        # Audit called with action="delete" and diff entries having after=None.
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args.args
        assert call_args[3] == "delete"
        diff = call_args[4]
        assert len(diff) > 0
        assert "key" in diff
        assert all(entry["after"] is None for entry in diff.values())

    async def test_delete_flag_raises_not_found_when_absent(self) -> None:
        """(f) delete_flag on a non-existent key → FeatureFlagNotFoundError."""
        db = _mock_db_with_flag(None)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with patch(self._AUDIT_PATCH, new_callable=AsyncMock):
            with pytest.raises(FeatureFlagNotFoundError) as exc_info:
                await svc.delete_flag("ghost_flag", "admin@ken-e.ai")

        assert exc_info.value.key == "ghost_flag"


# ---------------------------------------------------------------------------
# TestGetFlagAudit — FF-15 (FF-PRD-02 B4)
# ---------------------------------------------------------------------------


class TestGetFlagAudit:
    """Unit tests for FeatureFlagService.get_flag_audit.

    All tests use MagicMock for the Firestore client — no Firestore emulator
    (that is FF-17's territory per the implementation plan).

    Cases:
      (a) Results are returned newest-first (ordered by created_at DESC via query).
      (b) limit+1 detection: mock 6 docs, limit=5 → 5 entries + cursor = 5th audit_id.
      (c) Terminal page: mock 3 docs, limit=5 → 3 entries + next_cursor=None.
      (d) First page: cursor=None → start_after is NOT called.
      (e) Stale cursor: cursor doc .exists is False → returns ([], None) immediately,
          no page query issued.
      (f) Exception propagation: Firestore raises → service raises (not swallowed).
    """

    def _make_audit_doc(self, audit_id: str, created_at: str) -> MagicMock:
        """Return a MagicMock Firestore doc whose to_dict() returns a valid audit row."""
        doc = MagicMock()
        doc.id = audit_id
        doc.to_dict.return_value = {
            "audit_id": audit_id,
            "flag_key": "test_flag",
            "actor_email": "admin@ken-e.ai",
            "action": "update",
            "diff": {"description": {"before": "old", "after": "new"}},
            "created_at": created_at,
        }
        return doc

    def _mock_audit_db(
        self,
        page_docs: list[MagicMock],
        cursor_doc: MagicMock | None = None,
        raise_on_stream: Exception | None = None,
    ) -> MagicMock:
        """Return a Firestore mock suitable for get_flag_audit.

        The mock sets up the fluent query chain:
          db.collection(...).where(...).order_by(...)[.start_after(...)].limit(...).stream()
        """
        db = MagicMock()
        coll = db.collection.return_value

        # Cursor doc lookup: db.collection("feature_flag_audit").document(cursor_id).get()
        if cursor_doc is not None:
            coll.document.return_value.get.return_value = cursor_doc
        else:
            # No cursor path expected — set exists=True as a safe default
            default_cursor_doc = MagicMock()
            default_cursor_doc.exists = False
            coll.document.return_value.get.return_value = default_cursor_doc

        # Build the fluent query chain.  Each chained method returns the same
        # mock so start_after / no start_after both resolve to the same query object.
        query_mock = MagicMock()
        coll.where.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.start_after.return_value = query_mock
        query_mock.limit.return_value = query_mock
        if raise_on_stream:
            query_mock.stream.side_effect = raise_on_stream
        else:
            query_mock.stream.return_value = iter(page_docs)
        return db

    async def test_entries_returned_newest_first(self) -> None:
        """(a) Documents returned by the query (order_by DESC) are passed through in order."""
        # Simulate Firestore returning 3 docs newest-first.
        docs = [
            self._make_audit_doc("2026-03-01_aaa", "2026-03-01T00:00:00+00:00"),
            self._make_audit_doc("2026-02-01_bbb", "2026-02-01T00:00:00+00:00"),
            self._make_audit_doc("2026-01-01_ccc", "2026-01-01T00:00:00+00:00"),
        ]
        db = self._mock_audit_db(docs)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        entries, next_cursor = await svc.get_flag_audit("test_flag", limit=5, cursor=None)

        assert len(entries) == 3
        assert [e.audit_id for e in entries] == ["2026-03-01_aaa", "2026-02-01_bbb", "2026-01-01_ccc"]
        assert next_cursor is None

    async def test_limit_plus_one_detection_sets_next_cursor(self) -> None:
        """(b) When 6 docs come back for limit=5, next_cursor = 5th entry's audit_id."""
        docs = [
            self._make_audit_doc(f"2026-01-0{7 - i}_id{i}", f"2026-01-0{7 - i}T00:00:00+00:00")
            for i in range(1, 7)
        ]
        db = self._mock_audit_db(docs)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        entries, next_cursor = await svc.get_flag_audit("test_flag", limit=5, cursor=None)

        assert len(entries) == 5
        assert next_cursor == entries[-1].audit_id

    async def test_terminal_page_returns_no_cursor(self) -> None:
        """(c) When 3 docs come back for limit=5, next_cursor=None."""
        docs = [
            self._make_audit_doc(f"2026-01-0{3 - i}_id{i}", f"2026-01-0{3 - i}T00:00:00+00:00")
            for i in range(3)
        ]
        db = self._mock_audit_db(docs)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        entries, next_cursor = await svc.get_flag_audit("test_flag", limit=5, cursor=None)

        assert len(entries) == 3
        assert next_cursor is None

    async def test_no_cursor_does_not_call_start_after(self) -> None:
        """(d) When cursor=None, start_after is never called."""
        db = self._mock_audit_db([])
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        await svc.get_flag_audit("test_flag", limit=5, cursor=None)

        query_mock = db.collection.return_value.where.return_value
        query_mock.start_after.assert_not_called()

    async def test_stale_cursor_returns_empty_page_no_exception(self) -> None:
        """(e) Stale cursor (doc not in Firestore) returns ([], None) without raising."""
        absent_cursor_doc = MagicMock()
        absent_cursor_doc.exists = False
        db = self._mock_audit_db([], cursor_doc=absent_cursor_doc)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        entries, next_cursor = await svc.get_flag_audit("test_flag", limit=5, cursor="stale_id")

        assert entries == []
        assert next_cursor is None
        # The page query (stream) should NOT have been issued.
        query_mock = db.collection.return_value.where.return_value
        query_mock.stream.assert_not_called()

    async def test_firestore_exception_propagates(self) -> None:
        """(f) Firestore exceptions are not swallowed — admin callers need real errors."""
        db = self._mock_audit_db([], raise_on_stream=RuntimeError("Firestore down"))
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        with pytest.raises(RuntimeError, match="Firestore down"):
            await svc.get_flag_audit("test_flag", limit=5, cursor=None)

    async def test_cross_flag_cursor_returns_empty_page(self) -> None:
        """Cross-flag cursor: cursor doc belongs to a different flag_key → ([], None)."""
        # Cursor doc exists but its flag_key doesn't match the request flag_key.
        cross_flag_cursor_doc = MagicMock()
        cross_flag_cursor_doc.exists = True
        cross_flag_cursor_doc.to_dict.return_value = {
            "audit_id": "stale_id",
            "flag_key": "other_flag",  # different from "test_flag"
            "actor_email": "admin@ken-e.ai",
            "action": "update",
            "diff": {},
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        db = self._mock_audit_db([], cursor_doc=cross_flag_cursor_doc)
        svc = FeatureFlagService(db=db, time_provider=FakeClock())

        entries, next_cursor = await svc.get_flag_audit(
            "test_flag", limit=5, cursor="cross_flag_cursor"
        )

        assert entries == []
        assert next_cursor is None
        # The page query (stream) should NOT have been issued.
        query_mock = db.collection.return_value.where.return_value
        query_mock.stream.assert_not_called()

    async def test_empty_entries_with_has_next_returns_null_cursor(self) -> None:
        """IndexError guard: has_next=True but all docs fail Pydantic validation → next_cursor=None."""
        # The inner _run function would fetch limit+1 docs to detect has_next=True,
        # but after model_validate strips invalid docs entries would be [].
        # This test directly verifies the `has_next and entries` guard by
        # simulating 6 docs for limit=5 but making model_validate raise on all of them.
        from unittest.mock import patch

        class _FailingAuditEntry:
            @classmethod
            def model_validate(cls, data: object) -> object:
                raise ValueError("Intentional validation failure for testing")

        with patch(
            "src.kene_api.services.feature_flag_service.FeatureFlagAuditEntry",
            _FailingAuditEntry,
        ):
            docs = [
                self._make_audit_doc(f"id_{i}", f"2026-01-0{i+1}T00:00:00+00:00")
                for i in range(6)
            ]
            db2 = self._mock_audit_db(docs)
            svc2 = FeatureFlagService(db=db2, time_provider=FakeClock())

            # Should not raise IndexError even though has_next=True and entries=[].
            entries, next_cursor = await svc2.get_flag_audit("test_flag", limit=5, cursor=None)

        assert entries == []
        assert next_cursor is None


# ---------------------------------------------------------------------------
# TTL_SECONDS env override
# ---------------------------------------------------------------------------


def test_ttl_seconds_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """TTL_SECONDS defaults to 60.0 and reads from KENE_FF_CACHE_TTL_SECONDS when set."""
    import importlib

    import src.kene_api.services.feature_flag_service as svc_module

    try:
        monkeypatch.delenv("KENE_FF_CACHE_TTL_SECONDS", raising=False)
        importlib.reload(svc_module)
        assert svc_module.TTL_SECONDS == 60.0

        monkeypatch.setenv("KENE_FF_CACHE_TTL_SECONDS", "1.0")
        importlib.reload(svc_module)
        assert svc_module.TTL_SECONDS == 1.0
    finally:
        # Always restore default so later tests see the unmodified module state.
        monkeypatch.delenv("KENE_FF_CACHE_TTL_SECONDS", raising=False)
        importlib.reload(svc_module)
