"""Unit tests for feature_flags/security_critical.py (AH-79).

Covers:
- SECURITY_CRITICAL_FLAGS membership
- emit_audit_if_critical no-op for non-critical keys
- emit_audit_if_critical emits CRITICAL audit log with expected payload
- emit_audit_if_critical increments Prometheus counter with correct labels
- audit logger failure is swallowed (does not raise)
- Prometheus counter failure is swallowed (does not raise)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.kene_api.feature_flags.security_critical import (
    SECURITY_CRITICAL_FLAGS,
    emit_audit_if_critical,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flag(
    key: str = "rate_limit_backend_override",
    default_enabled: bool = False,
    is_active: bool = True,
) -> Any:
    """Create a minimal FeatureFlag-like object using a MagicMock."""
    flag = MagicMock()
    flag.key = key
    flag.default_enabled = default_enabled
    flag.is_active = is_active
    return flag


# ---------------------------------------------------------------------------
# 1. SECURITY_CRITICAL_FLAGS membership
# ---------------------------------------------------------------------------


class TestSecurityCriticalFlagsSet:
    def test_rate_limit_backend_override_is_critical(self) -> None:
        """rate_limit_backend_override must be in SECURITY_CRITICAL_FLAGS."""
        assert "rate_limit_backend_override" in SECURITY_CRITICAL_FLAGS

    def test_flags_set_is_frozenset(self) -> None:
        """SECURITY_CRITICAL_FLAGS is immutable (frozenset)."""
        assert isinstance(SECURITY_CRITICAL_FLAGS, frozenset)

    def test_unrelated_flag_is_not_critical(self) -> None:
        """An unrelated flag key is not in SECURITY_CRITICAL_FLAGS."""
        assert "chat_v2_enabled" not in SECURITY_CRITICAL_FLAGS
        assert "some_random_flag" not in SECURITY_CRITICAL_FLAGS


# ---------------------------------------------------------------------------
# 2. No-op for non-critical keys
# ---------------------------------------------------------------------------


class TestNoOpForNonCriticalKey:
    async def test_non_critical_key_does_not_call_audit_logger(self) -> None:
        """emit_audit_if_critical is a no-op for flags not in SECURITY_CRITICAL_FLAGS."""
        mock_logger = AsyncMock()

        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_logger,
        ):
            await emit_audit_if_critical(
                key="some_unrelated_flag",
                before=_make_flag("some_unrelated_flag"),
                after=_make_flag("some_unrelated_flag"),
                actor_email="admin@example.com",
            )

        mock_logger.log_event.assert_not_awaited()

    async def test_non_critical_key_does_not_increment_counter(self) -> None:
        """emit_audit_if_critical does not increment the Prometheus counter for non-critical keys."""
        mock_counter = MagicMock()
        mock_counter.labels.return_value.inc = MagicMock()

        with patch(
            "src.kene_api.feature_flags.security_critical.ratelimit_backend_override_flips_total",
            mock_counter,
        ):
            await emit_audit_if_critical(
                key="some_unrelated_flag",
                before=None,
                after=_make_flag("some_unrelated_flag"),
                actor_email="admin@example.com",
            )

        mock_counter.labels.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Audit log emission for critical flags
# ---------------------------------------------------------------------------


class TestAuditLogEmission:
    async def test_emits_critical_audit_log_on_update(self) -> None:
        """emit_audit_if_critical calls audit_logger.log_event with CRITICAL severity
        when the flag key is security-critical."""
        from src.kene_api.auth.audit_logger import SecurityEventType

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        before = _make_flag(default_enabled=False, is_active=True)
        after = _make_flag(default_enabled=True, is_active=True)

        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_audit_logger,
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=before,
                after=after,
                actor_email="superadmin@ken-e.ai",
            )

        mock_audit_logger.log_event.assert_awaited_once()
        call_kwargs = mock_audit_logger.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == SecurityEventType.FEATURE_FLAG_CHANGED
        assert call_kwargs["severity"] == "CRITICAL"
        assert call_kwargs["email"] == "superadmin@ken-e.ai"

    async def test_audit_log_details_contain_before_and_after(self) -> None:
        """details dict must include before + after with is_active and default_enabled."""
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        before = _make_flag(default_enabled=False, is_active=True)
        after = _make_flag(default_enabled=True, is_active=True)

        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_audit_logger,
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=before,
                after=after,
                actor_email="superadmin@ken-e.ai",
            )

        details = mock_audit_logger.log_event.call_args.kwargs["details"]
        assert details["flag_key"] == "rate_limit_backend_override"
        assert details["before"]["default_enabled"] is False
        assert details["before"]["is_active"] is True
        assert details["after"]["default_enabled"] is True
        assert details["after"]["is_active"] is True

    async def test_audit_log_before_none_on_create(self) -> None:
        """On create (before=None), before dict contains None values."""
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        after = _make_flag(default_enabled=True, is_active=True)

        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_audit_logger,
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=None,
                after=after,
                actor_email="superadmin@ken-e.ai",
            )

        details = mock_audit_logger.log_event.call_args.kwargs["details"]
        assert details["before"]["default_enabled"] is None
        assert details["before"]["is_active"] is None

    async def test_audit_log_after_none_on_delete(self) -> None:
        """On delete (after=None), after dict contains None values."""
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        before = _make_flag(default_enabled=True, is_active=True)

        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_audit_logger,
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=before,
                after=None,
                actor_email="superadmin@ken-e.ai",
            )

        details = mock_audit_logger.log_event.call_args.kwargs["details"]
        assert details["after"]["default_enabled"] is None
        assert details["after"]["is_active"] is None


# ---------------------------------------------------------------------------
# 4. Prometheus counter increments
# ---------------------------------------------------------------------------


class TestPrometheusCounterIncrement:
    async def test_counter_incremented_with_correct_labels_on_update(self) -> None:
        """Prometheus counter is incremented with previous_enabled + new_enabled labels."""
        mock_counter = MagicMock()
        mock_labels_instance = MagicMock()
        mock_counter.labels.return_value = mock_labels_instance

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        before = _make_flag(default_enabled=False, is_active=True)
        after = _make_flag(default_enabled=True, is_active=True)

        with (
            patch(
                "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
                return_value=mock_audit_logger,
            ),
            patch(
                "src.kene_api.feature_flags.security_critical.ratelimit_backend_override_flips_total",
                mock_counter,
            ),
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=before,
                after=after,
                actor_email="admin@ken-e.ai",
            )

        mock_counter.labels.assert_called_once_with(
            previous_enabled="false",
            new_enabled="true",
        )
        mock_labels_instance.inc.assert_called_once()

    async def test_counter_labels_for_create(self) -> None:
        """On create (before=None), previous_enabled='none' and new_enabled='true'."""
        mock_counter = MagicMock()
        mock_labels_instance = MagicMock()
        mock_counter.labels.return_value = mock_labels_instance

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        after = _make_flag(default_enabled=True, is_active=True)

        with (
            patch(
                "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
                return_value=mock_audit_logger,
            ),
            patch(
                "src.kene_api.feature_flags.security_critical.ratelimit_backend_override_flips_total",
                mock_counter,
            ),
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=None,
                after=after,
                actor_email="admin@ken-e.ai",
            )

        mock_counter.labels.assert_called_once_with(
            previous_enabled="none",
            new_enabled="true",
        )


# ---------------------------------------------------------------------------
# 5. Resilience: hook failures are swallowed
# ---------------------------------------------------------------------------


class TestHookResilienceOnFailure:
    async def test_audit_logger_exception_does_not_propagate(self) -> None:
        """If audit_logger.log_event raises, emit_audit_if_critical does NOT propagate."""
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock(
            side_effect=RuntimeError("audit sink is down")
        )

        # Should not raise
        with patch(
            "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
            return_value=mock_audit_logger,
        ):
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=None,
                after=_make_flag(default_enabled=True),
                actor_email="admin@ken-e.ai",
            )

    async def test_prometheus_counter_exception_does_not_propagate(self) -> None:
        """If counter increment raises, emit_audit_if_critical does NOT propagate."""
        mock_counter = MagicMock()
        mock_counter.labels.side_effect = RuntimeError("registry reset in tests")

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_event = AsyncMock()

        with (
            patch(
                "src.kene_api.feature_flags.security_critical.get_audit_logger",  # module-level import
                return_value=mock_audit_logger,
            ),
            patch(
                "src.kene_api.feature_flags.security_critical.ratelimit_backend_override_flips_total",
                mock_counter,
            ),
        ):
            # Should not raise even though the counter increment fails
            await emit_audit_if_critical(
                key="rate_limit_backend_override",
                before=None,
                after=_make_flag(default_enabled=True),
                actor_email="admin@ken-e.ai",
            )
