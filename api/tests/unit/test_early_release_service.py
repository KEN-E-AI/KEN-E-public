"""Unit tests for EarlyReleaseService.

Coverage: DM-PRD-11 §4.5 ACs — validate/rotate/expiry/compare/redemption/count.

Uses MagicMock for the Firestore client (no emulator — integration tests own
emulator coverage).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore_v1.field_path import FieldPath
from src.kene_api.models.early_release_models import (
    EarlyReleaseConfig,
    EarlyReleaseWriteRequest,
)
from src.kene_api.services.early_release_service import (
    EarlyReleaseConfigNotFoundError,
    EarlyReleaseService,
    get_early_release_service,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(days=30)
_PAST = _NOW - timedelta(days=1)
_VALID_CODE = "super-secret-alpha-code"
_ACTOR = "uid_superadmin"


def _make_config(**overrides: object) -> EarlyReleaseConfig:
    base: dict[str, object] = {
        "code": _VALID_CODE,
        "is_active": True,
        "expires_at": None,
        "updated_by": _ACTOR,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return EarlyReleaseConfig(**base)


def _mock_db_with_config(config: EarlyReleaseConfig | None) -> MagicMock:
    """Return a MagicMock Firestore client whose app_config/early_release returns config."""
    db = MagicMock()
    doc = MagicMock()
    if config is None:
        doc.exists = False
        doc.to_dict.return_value = {}
    else:
        doc.exists = True
        doc.to_dict.return_value = config.model_dump(mode="json")

    # .collection("app_config").document("early_release").get() path
    db.collection.return_value.document.return_value.get.return_value = doc
    return db


# ---------------------------------------------------------------------------
# validate — happy path
# ---------------------------------------------------------------------------


async def test_validate_true_when_active_unexpired_correct_code() -> None:
    """validate returns True for an active, unexpired config with a matching code."""
    db = _mock_db_with_config(_make_config())
    svc = EarlyReleaseService(db=db)
    result = await svc.validate(_VALID_CODE)
    assert result is True


# ---------------------------------------------------------------------------
# validate — config absent
# ---------------------------------------------------------------------------


async def test_validate_false_when_config_absent() -> None:
    """validate returns False (without raising) when no config document exists."""
    db = _mock_db_with_config(None)
    svc = EarlyReleaseService(db=db)
    result = await svc.validate(_VALID_CODE)
    assert result is False


# ---------------------------------------------------------------------------
# validate — is_active=False
# ---------------------------------------------------------------------------


async def test_validate_false_when_inactive() -> None:
    """validate returns False when is_active=False regardless of the code."""
    db = _mock_db_with_config(_make_config(is_active=False))
    svc = EarlyReleaseService(db=db)
    assert await svc.validate(_VALID_CODE) is False


# ---------------------------------------------------------------------------
# validate — expired
# ---------------------------------------------------------------------------


async def test_validate_false_when_expired() -> None:
    """validate returns False when expires_at is in the past."""
    db = _mock_db_with_config(_make_config(expires_at=_PAST))
    svc = EarlyReleaseService(db=db)
    assert await svc.validate(_VALID_CODE) is False


# ---------------------------------------------------------------------------
# validate — wrong code (single-byte difference)
# ---------------------------------------------------------------------------


async def test_validate_false_when_code_differs_by_one_byte() -> None:
    """validate returns False when the submitted code differs by a single character."""
    db = _mock_db_with_config(_make_config())
    svc = EarlyReleaseService(db=db)
    wrong = _VALID_CODE[:-1] + "X"
    assert await svc.validate(wrong) is False


# ---------------------------------------------------------------------------
# validate — future expiry is allowed
# ---------------------------------------------------------------------------


async def test_validate_true_when_unexpired_future_expiry() -> None:
    """validate returns True when expires_at is in the future."""
    db = _mock_db_with_config(_make_config(expires_at=_FUTURE))
    svc = EarlyReleaseService(db=db)
    assert await svc.validate(_VALID_CODE) is True


# ---------------------------------------------------------------------------
# validate — constant-time compare is called on every failure path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [
        None,
        _make_config(is_active=False),
        _make_config(expires_at=_PAST),
    ],
    ids=["absent", "inactive", "expired"],
)
async def test_validate_constant_time_compare_called_on_failure_paths(
    config: EarlyReleaseConfig | None,
) -> None:
    """Exactly one compare_digest call is made on absent/inactive/expired paths.

    The refactored validate method does a single unconditional compare_digest
    (submitted vs. sentinel when config is invalid) to prevent timing channels.
    """
    db = _mock_db_with_config(config)
    svc = EarlyReleaseService(db=db)
    module = "src.kene_api.services.early_release_service.secrets.compare_digest"
    with patch(module) as mock_cd:
        mock_cd.return_value = False
        await svc.validate("any-code")
    assert mock_cd.call_count == 1, (
        f"Expected exactly 1 compare_digest call on failure path; got {mock_cd.call_count}"
    )


# ---------------------------------------------------------------------------
# validate — unicode code does not raise TypeError
# ---------------------------------------------------------------------------


async def test_validate_unicode_code_does_not_raise() -> None:
    """A non-ASCII code is accepted without raising TypeError."""
    db = _mock_db_with_config(_make_config(code="café-code-🚀"))
    svc = EarlyReleaseService(db=db)
    assert await svc.validate("café-code-🚀") is True
    assert await svc.validate("wrong") is False


# ---------------------------------------------------------------------------
# set_code — writes doc that matches EarlyReleaseConfig shape
# ---------------------------------------------------------------------------


async def test_set_code_writes_correct_document() -> None:
    """set_code writes the correct serialised shape to Firestore."""
    db = MagicMock()
    doc_ref = MagicMock()
    db.collection.return_value.document.return_value = doc_ref

    svc = EarlyReleaseService(db=db)
    config = await svc.set_code("new-code", actor_id=_ACTOR, expires_at=_FUTURE)

    assert config.code == "new-code"
    assert config.is_active is True
    assert config.expires_at == _FUTURE
    assert config.updated_by == _ACTOR

    # Verify .set() was called with the serialised body.
    doc_ref.set.assert_called_once()
    written_data: dict = doc_ref.set.call_args[0][0]
    assert written_data["code"] == "new-code"
    assert written_data["is_active"] is True
    assert written_data["updated_by"] == _ACTOR


async def test_set_code_defaults_is_active_true() -> None:
    """set_code defaults is_active=True — a plain rotation implies re-activation."""
    db = MagicMock()
    svc = EarlyReleaseService(db=db)
    config = await svc.set_code("rotated", actor_id=_ACTOR)
    assert config.is_active is True


async def test_set_code_can_rotate_into_disabled_state_in_one_write() -> None:
    """set_code(is_active=False) rotates the code already-disabled in a single write.

    This is the atomic rotate-with-disable primitive: no rotate-then-disable
    two-step that could leave a freshly-rotated code live if the second write
    failed.
    """
    db = MagicMock()
    doc_ref = MagicMock()
    db.collection.return_value.document.return_value = doc_ref

    svc = EarlyReleaseService(db=db)
    config = await svc.set_code("rotated", actor_id=_ACTOR, is_active=False)

    assert config.is_active is False
    # A single .set() carries is_active=False — no second write.
    doc_ref.set.assert_called_once()
    assert doc_ref.set.call_args[0][0]["is_active"] is False


# ---------------------------------------------------------------------------
# set_active — flips kill switch without changing the code
# ---------------------------------------------------------------------------


async def test_set_active_false_flips_kill_switch() -> None:
    """set_active(False) updates is_active without touching the code."""
    existing = _make_config(is_active=True)
    db = _mock_db_with_config(existing)
    doc_ref = db.collection.return_value.document.return_value
    svc = EarlyReleaseService(db=db)

    result = await svc.set_active(False, actor_id=_ACTOR)

    assert result.is_active is False
    assert result.code == _VALID_CODE  # code preserved
    written_data: dict = doc_ref.set.call_args[0][0]
    assert written_data["is_active"] is False
    assert written_data["code"] == _VALID_CODE


async def test_set_active_raises_when_config_absent() -> None:
    """set_active raises EarlyReleaseConfigNotFoundError when no doc exists."""
    db = _mock_db_with_config(None)
    svc = EarlyReleaseService(db=db)
    with pytest.raises(EarlyReleaseConfigNotFoundError):
        await svc.set_active(False, actor_id=_ACTOR)


# ---------------------------------------------------------------------------
# record_redemption — idempotency
# ---------------------------------------------------------------------------


async def test_record_redemption_writes_document_on_first_call() -> None:
    """record_redemption writes the redemption doc on the first call."""
    db = MagicMock()
    doc_ref = MagicMock()
    db.collection.return_value.document.return_value = doc_ref

    svc = EarlyReleaseService(db=db)
    await svc.record_redemption(
        user_id="uid_alice", email="alice@example.com", org_id="org_1"
    )

    doc_ref.create.assert_called_once()
    written_data: dict = doc_ref.create.call_args[0][0]
    assert written_data["user_id"] == "uid_alice"
    assert written_data["email"] == "alice@example.com"
    assert written_data["org_id"] == "org_1"
    assert "redeemed_at" in written_data


async def test_record_redemption_idempotent_swallows_already_exists() -> None:
    """record_redemption swallows AlreadyExists on the second call (idempotent)."""
    from google.api_core import exceptions as gcp_exceptions

    db = MagicMock()
    doc_ref = MagicMock()
    db.collection.return_value.document.return_value = doc_ref
    # First call succeeds; second raises AlreadyExists.
    doc_ref.create.side_effect = [None, gcp_exceptions.AlreadyExists("exists")]

    svc = EarlyReleaseService(db=db)
    await svc.record_redemption(
        user_id="uid_bob", email="bob@example.com", org_id="org_2"
    )
    # Second call must not raise.
    await svc.record_redemption(
        user_id="uid_bob", email="bob@example.com", org_id="org_2"
    )

    assert doc_ref.create.call_count == 2


# ---------------------------------------------------------------------------
# count_redemptions — Firestore COUNT aggregation (collection.count().get())
# ---------------------------------------------------------------------------


def _mock_db_for_count(value: object) -> MagicMock:
    """Wire ``db.collection().count().get()`` to return ``[[AggregationResult]]``."""
    db = MagicMock()
    agg = MagicMock()
    agg.value = value
    db.collection.return_value.count.return_value.get.return_value = [[agg]]
    return db


async def test_count_redemptions_returns_aggregation_value() -> None:
    """count_redemptions returns the scalar from the COUNT aggregation."""
    db = _mock_db_for_count(3)
    svc = EarlyReleaseService(db=db)
    count = await svc.count_redemptions()
    assert count == 3
    # A COUNT aggregation is used — the collection is never streamed.
    db.collection.return_value.count.return_value.get.assert_called_once()
    db.collection.return_value.stream.assert_not_called()


async def test_count_redemptions_zero_when_empty() -> None:
    """count_redemptions returns 0 when the collection is empty."""
    db = _mock_db_for_count(0)
    svc = EarlyReleaseService(db=db)
    assert await svc.count_redemptions() == 0


async def test_count_redemptions_defensive_zero_on_empty_aggregation() -> None:
    """An unexpected empty aggregation shape yields 0 rather than crashing."""
    db = MagicMock()
    db.collection.return_value.count.return_value.get.return_value = []
    svc = EarlyReleaseService(db=db)
    assert await svc.count_redemptions() == 0


# ---------------------------------------------------------------------------
# get_early_release_service — singleton via lru_cache
# ---------------------------------------------------------------------------


def test_get_early_release_service_returns_same_instance() -> None:
    """get_early_release_service returns the same instance on repeated calls."""
    get_early_release_service.cache_clear()
    with patch(
        "src.kene_api.services.early_release_service.get_firestore_client",
        return_value=MagicMock(),
    ):
        svc1 = get_early_release_service()
        svc2 = get_early_release_service()
    assert svc1 is svc2
    get_early_release_service.cache_clear()


# ---------------------------------------------------------------------------
# EarlyReleaseWriteRequest — empty code rejected at model layer
# ---------------------------------------------------------------------------


def test_write_request_rejects_empty_code() -> None:
    """EarlyReleaseWriteRequest raises ValidationError for an empty code."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EarlyReleaseWriteRequest(code="")


def test_write_request_accepts_valid_code() -> None:
    """EarlyReleaseWriteRequest accepts a non-empty code."""
    req = EarlyReleaseWriteRequest(code="valid-code")
    assert req.code == "valid-code"


# ---------------------------------------------------------------------------
# EarlyReleaseConfig — empty code rejected at model layer
# ---------------------------------------------------------------------------


def test_config_rejects_empty_code() -> None:
    """EarlyReleaseConfig raises ValidationError for an empty code."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EarlyReleaseConfig(
            code="",
            is_active=True,
            expires_at=None,
            updated_by=_ACTOR,
            updated_at=_NOW,
        )


# ---------------------------------------------------------------------------
# list_redemptions
# ---------------------------------------------------------------------------


def _make_redemption_doc(
    user_id: str,
    redeemed_at: datetime,
    email: str = "user@example.com",
    org_id: str = "org_test",
) -> MagicMock:
    """Return a MagicMock Firestore document snapshot for a redemption."""
    doc = MagicMock()
    doc.id = user_id
    doc.to_dict.return_value = {
        "user_id": user_id,
        "email": email,
        "org_id": org_id,
        "redeemed_at": redeemed_at.isoformat(),
    }
    return doc


def _mock_db_for_list(stream_docs: list[MagicMock]) -> MagicMock:
    """Return a MagicMock Firestore client suitable for list_redemptions tests.

    Mocks the ``collection().order_by().limit().stream()`` chain that
    ``list_redemptions._run`` executes on the first-page (no cursor) path.
    """
    db = MagicMock()
    # Build chained mock: .collection().order_by().order_by().limit().stream()
    order_by_mock = MagicMock()
    order_by_mock.limit.return_value.stream.return_value = stream_docs
    # The secondary order_by(document_id) tiebreaker chains off the first order_by.
    order_by_mock.order_by.return_value = order_by_mock
    # start_after also returns the same order_by mock (used in cursor path)
    order_by_mock.start_after.return_value = order_by_mock
    db.collection.return_value.order_by.return_value = order_by_mock
    return db


async def test_list_redemptions_first_page_returns_limit_docs_and_cursor() -> None:
    """First page (cursor=None): returns the most-recent ``limit`` docs, next_cursor set.

    We request limit=2 but provide 3 mock docs (limit+1) so the service
    detects has_next=True and sets next_cursor to the user_id of the last
    returned doc (the second one, index 1).
    """
    _t1 = _NOW
    _t0 = _NOW - timedelta(hours=1)
    _t_oldest = _NOW - timedelta(hours=2)

    doc0 = _make_redemption_doc("uid_newest", _t1)
    doc1 = _make_redemption_doc("uid_second", _t0)
    doc2 = _make_redemption_doc("uid_oldest", _t_oldest)

    # stream returns limit+1 = 3 docs to trigger has_next=True
    db = _mock_db_for_list([doc0, doc1, doc2])
    svc = EarlyReleaseService(db=db)

    entries, next_cursor = await svc.list_redemptions(limit=2, cursor=None)

    # Should return exactly limit=2 entries
    assert len(entries) == 2
    assert entries[0].user_id == "uid_newest"
    assert entries[1].user_id == "uid_second"
    # next_cursor is the user_id of the last returned entry (entries[-1])
    assert next_cursor == "uid_second"


async def test_list_redemptions_stale_cursor_returns_empty() -> None:
    """Stale cursor (user_id whose doc no longer exists): returns ([], None) without raising."""
    db = MagicMock()

    # cursor doc does NOT exist
    cursor_doc = MagicMock()
    cursor_doc.exists = False
    db.collection.return_value.document.return_value.get.return_value = cursor_doc

    # order_by chain — should not be called on the stale-cursor path, but set up anyway
    order_by_mock = MagicMock()
    db.collection.return_value.order_by.return_value = order_by_mock

    svc = EarlyReleaseService(db=db)
    entries, next_cursor = await svc.list_redemptions(limit=10, cursor="stale_uid")

    assert entries == []
    assert next_cursor is None


async def test_list_redemptions_terminal_page_has_no_next_cursor() -> None:
    """Terminal page: exactly ``limit`` docs exist, so ``next_cursor = None``.

    We request limit=3 and provide exactly 3 docs (not limit+1), so has_next=False.
    """
    docs = [
        _make_redemption_doc(f"uid_{i}", _NOW - timedelta(hours=i))
        for i in range(3)
    ]

    db = _mock_db_for_list(docs)
    svc = EarlyReleaseService(db=db)

    entries, next_cursor = await svc.list_redemptions(limit=3, cursor=None)

    assert len(entries) == 3
    assert next_cursor is None


async def test_list_redemptions_ordering_uses_descending_with_doc_id_tiebreaker() -> None:
    """The query orders by ``redeemed_at DESC`` then a document-id tiebreaker.

    The primary sort is verified by the ``order_by`` call on the collection; the
    secondary document-id sort (a unique tiebreaker for stable pagination) is
    verified by the chained ``order_by`` call.
    """
    from google.cloud import firestore as _fs

    doc = _make_redemption_doc("uid_only", _NOW)

    db = MagicMock()
    order_by_mock = MagicMock()
    order_by_mock.limit.return_value.stream.return_value = [doc]
    # The secondary order_by(document_id) chains off the first order_by.
    order_by_mock.order_by.return_value = order_by_mock
    db.collection.return_value.order_by.return_value = order_by_mock

    svc = EarlyReleaseService(db=db)
    await svc.list_redemptions(limit=5, cursor=None)

    # Primary sort: redeemed_at DESC on the collection.
    db.collection.return_value.order_by.assert_called_once_with(
        "redeemed_at", direction=_fs.Query.DESCENDING
    )
    # Secondary sort: a document-id tiebreaker chained off the primary order_by.
    order_by_mock.order_by.assert_called_once_with(FieldPath.document_id())


async def test_list_redemptions_invalid_cursor_with_slash_returns_empty() -> None:
    """A cursor containing '/' is treated as invalid and returns ([], None) without raising."""
    db = MagicMock()
    svc = EarlyReleaseService(db=db)
    entries, next_cursor = await svc.list_redemptions(limit=10, cursor="../../app_config/early_release")
    assert entries == []
    assert next_cursor is None
    # Firestore document lookup must NOT be called for an invalid cursor.
    db.collection.return_value.document.assert_not_called()
