"""Unit tests for EarlyReleaseService.

Coverage: DM-PRD-11 §4.5 ACs — validate/rotate/expiry/compare/redemption/count.

Uses MagicMock for the Firestore client (no emulator — integration tests own
emulator coverage).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
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


async def test_set_code_sets_is_active_true_always() -> None:
    """set_code always sets is_active=True — rotating implies re-activation."""
    db = MagicMock()
    svc = EarlyReleaseService(db=db)
    config = await svc.set_code("rotated", actor_id=_ACTOR)
    assert config.is_active is True


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
# count_redemptions — returns accurate length
# ---------------------------------------------------------------------------


async def test_count_redemptions_returns_collection_size() -> None:
    """count_redemptions returns the number of docs in early_release_redemptions."""
    db = MagicMock()
    # stream() returns 3 fake docs
    db.collection.return_value.stream.return_value = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    svc = EarlyReleaseService(db=db)
    count = await svc.count_redemptions()
    assert count == 3


async def test_count_redemptions_zero_when_empty() -> None:
    """count_redemptions returns 0 when the collection is empty."""
    db = MagicMock()
    db.collection.return_value.stream.return_value = []
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
