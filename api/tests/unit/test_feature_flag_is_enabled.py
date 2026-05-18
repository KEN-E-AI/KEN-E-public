"""Unit tests for the is_feature_enabled ergonomic helper and get_feature_flag_service factory.

Coverage: FF-PRD-01 AC-7 (is_feature_enabled contract: happy path, default-on-error,
log shape, default-argument propagation, no PII in logs).

Uses AsyncMock to patch FeatureFlagService.evaluate_batch so no real Firestore
or network I/O occurs.  The @lru_cache singleton is cleared before each test via
a per-test fixture to prevent cross-test cache interference.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.models.feature_flag_models import (
    EvaluationContext,
    FlagEvaluation,
)
from src.kene_api.services.feature_flag_service import (
    FeatureFlagService,
    get_feature_flag_service,
    is_feature_enabled,
)

# ---------------------------------------------------------------------------
# Shared helpers (mirrored from test_feature_flag_service.py for consistency)
# ---------------------------------------------------------------------------

# The PII field *values* that must never appear in any log record.
_PII_VALUES = {"uid_test", "tester@example.com"}
_PII_FIELDS = {"user_id", "user_email", "organization_id", "account_id"}


def _ctx(**overrides: object) -> EvaluationContext:
    base: dict[str, object] = {
        "user_id": "uid_test",
        "user_email": "tester@example.com",
        "organization_id": None,
        "account_id": None,
    }
    base.update(overrides)
    return EvaluationContext(**base)


def _enabled_evaluation(key: str = "some_flag") -> dict[str, FlagEvaluation]:
    return {key: FlagEvaluation(key=key, enabled=True, reason="domain_match")}


def _disabled_evaluation(key: str = "some_flag") -> dict[str, FlagEvaluation]:
    return {key: FlagEvaluation(key=key, enabled=False, reason="default")}


# ---------------------------------------------------------------------------
# Fixture: clear the @lru_cache singleton before every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_service_singleton() -> Generator[None, None, None]:
    """Ensure each test starts with a clean get_feature_flag_service cache."""
    get_feature_flag_service.cache_clear()
    yield
    get_feature_flag_service.cache_clear()


# ---------------------------------------------------------------------------
# Case 1 — Happy path: service returns enabled=True → helper returns True
# ---------------------------------------------------------------------------


async def test_returns_true_when_service_returns_enabled() -> None:
    """AC-7: helper returns True when evaluate_batch says enabled=True."""
    mock_service = MagicMock(spec=FeatureFlagService)
    mock_service.evaluate_batch = AsyncMock(
        return_value=_enabled_evaluation("feature_x")
    )

    with patch(
        "src.kene_api.services.feature_flag_service.get_feature_flag_service",
        return_value=mock_service,
    ):
        result = await is_feature_enabled("feature_x", _ctx())

    assert result is True
    mock_service.evaluate_batch.assert_called_once_with(["feature_x"], _ctx())


# ---------------------------------------------------------------------------
# Case 2 — Happy path: service returns enabled=False → helper returns False
# ---------------------------------------------------------------------------


async def test_returns_false_when_service_returns_disabled() -> None:
    """AC-7: helper returns False when evaluate_batch says enabled=False."""
    mock_service = MagicMock(spec=FeatureFlagService)
    mock_service.evaluate_batch = AsyncMock(
        return_value=_disabled_evaluation("feature_x")
    )

    with patch(
        "src.kene_api.services.feature_flag_service.get_feature_flag_service",
        return_value=mock_service,
    ):
        result = await is_feature_enabled("feature_x", _ctx())

    assert result is False


# ---------------------------------------------------------------------------
# Case 3 — Service raises: helper returns default (False) and logs WARN
# ---------------------------------------------------------------------------


async def test_returns_default_and_logs_on_service_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-7: service raises → helper returns False (default) and logs feature_flag_helper_error at WARN."""
    mock_service = MagicMock(spec=FeatureFlagService)
    mock_service.evaluate_batch = AsyncMock(side_effect=RuntimeError("Firestore boom"))

    with patch(
        "src.kene_api.services.feature_flag_service.get_feature_flag_service",
        return_value=mock_service,
    ):
        with caplog.at_level(
            logging.WARNING,
            logger="src.kene_api.services.feature_flag_service",
        ):
            result = await is_feature_enabled("broken_flag", _ctx())

    assert result is False

    # Exactly one WARN record for this helper.
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warn_records) == 1
    record = warn_records[0]
    assert record.getMessage() == "feature_flag_helper_error"
    assert record.__dict__.get("flag_key") == "broken_flag"
    assert record.__dict__.get("error_type") == "RuntimeError"
    assert record.exc_info is None

    # PII-absence: the actual PII *values* (not just field names) must not
    # appear anywhere in the serialised record — catches accidental ctx inclusion.
    _STANDARD_LOG_ATTRS = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    )
    extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_LOG_ATTRS}
    extras_str = str(extras)
    for pii_value in _PII_VALUES:
        assert pii_value not in extras_str, (
            f"PII value {pii_value!r} found in log extras: {extras_str}"
        )


# ---------------------------------------------------------------------------
# Case 4 — Explicit default=True: service raises → helper returns True
# ---------------------------------------------------------------------------


async def test_returns_explicit_default_true_on_service_error() -> None:
    """AC-7: `default=True` is returned when the service raises."""
    mock_service = MagicMock(spec=FeatureFlagService)
    mock_service.evaluate_batch = AsyncMock(side_effect=ValueError("unexpected"))

    with patch(
        "src.kene_api.services.feature_flag_service.get_feature_flag_service",
        return_value=mock_service,
    ):
        result = await is_feature_enabled("some_flag", _ctx(), default=True)

    assert result is True


# ---------------------------------------------------------------------------
# Case 5 — No WARN log on success
# ---------------------------------------------------------------------------


async def test_no_warn_log_on_success(caplog: pytest.LogCaptureFixture) -> None:
    """AC-7: no WARN log is emitted when the service returns successfully."""
    mock_service = MagicMock(spec=FeatureFlagService)
    mock_service.evaluate_batch = AsyncMock(
        return_value=_enabled_evaluation("happy_flag")
    )

    with patch(
        "src.kene_api.services.feature_flag_service.get_feature_flag_service",
        return_value=mock_service,
    ):
        with caplog.at_level(
            logging.WARNING,
            logger="src.kene_api.services.feature_flag_service",
        ):
            await is_feature_enabled("happy_flag", _ctx())

    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warn_records == [], f"Unexpected WARN records: {warn_records}"


# ---------------------------------------------------------------------------
# Case 6 — get_feature_flag_service returns a FeatureFlagService (smoke)
# ---------------------------------------------------------------------------


def test_get_feature_flag_service_returns_service_instance() -> None:
    """Smoke-test the factory: returns a FeatureFlagService without crashing.

    Patches get_firestore_client so no real GCP credentials are needed.
    """
    fake_client = MagicMock()

    with patch(
        "src.kene_api.services.feature_flag_service.get_firestore_client",
        return_value=fake_client,
    ):
        service = get_feature_flag_service()

    assert isinstance(service, FeatureFlagService)
    assert service._db is fake_client


# ---------------------------------------------------------------------------
# Case 7 — get_feature_flag_service is cached (same object returned twice)
# ---------------------------------------------------------------------------


def test_get_feature_flag_service_is_singleton() -> None:
    """@lru_cache: two calls return the identical object."""
    fake_client = MagicMock()

    with patch(
        "src.kene_api.services.feature_flag_service.get_firestore_client",
        return_value=fake_client,
    ):
        svc_a = get_feature_flag_service()
        svc_b = get_feature_flag_service()

    assert svc_a is svc_b


# ---------------------------------------------------------------------------
# Case 8 — router DI and helper share the same singleton (FF-PRD-01 §7.4)
# ---------------------------------------------------------------------------


def test_router_di_and_helper_share_singleton() -> None:
    """dependencies.get_feature_flag_service and the service-side factory return
    the SAME cached FeatureFlagService — otherwise the router path and the
    is_feature_enabled helper hold independent 60s TTL caches and a kill-switch
    flip takes up to 2x the SLO window to propagate (FF-PRD-01 §7.4)."""
    from src.kene_api.dependencies import (
        get_feature_flag_service as dep_get_feature_flag_service,
    )

    fake_client = MagicMock()

    with patch(
        "src.kene_api.services.feature_flag_service.get_firestore_client",
        return_value=fake_client,
    ):
        svc_via_helper = get_feature_flag_service()
        svc_via_dep = dep_get_feature_flag_service()

    assert svc_via_helper is svc_via_dep
