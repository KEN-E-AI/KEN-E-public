"""Security-critical feature-flag side-effects registry (AH-79).

Exposes:
  - ``SECURITY_CRITICAL_FLAGS`` — frozenset of flag keys that require CRITICAL
    audit logging + Cloud Monitoring counter increment on every write.
  - ``emit_audit_if_critical`` — called by ``feature_flag_service`` after each
    create / update / delete for flags in ``SECURITY_CRITICAL_FLAGS``.

Design decisions (from the approved Implementation Plan):
  - Dependency direction is clean: ``feature_flag_service`` imports from
    ``feature_flags/``, NOT from ``rate_limiter.py``.
  - Hook failures are intentionally swallowed at the call site (not here) so
    a broken audit sink never blocks the actual flag write.
  - The Prometheus counter is the wire to Cloud Monitoring; the alert policy
    lives in Terraform (AH-73 scope).
  - A ``before=None`` means this is a create; ``after=None`` means delete.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

# Module-level import of audit logger utilities so tests can patch at this
# module's namespace (e.g. ``src.kene_api.feature_flags.security_critical.get_audit_logger``).
from ..auth.audit_logger import SecurityEventType, get_audit_logger
from ..metrics.rate_limiter_metrics import ratelimit_backend_override_flips_total

if TYPE_CHECKING:
    from ..models.feature_flag_models import FeatureFlag

logger = logging.getLogger(__name__)

SECURITY_CRITICAL_FLAGS: frozenset[str] = frozenset({"rate_limit_backend_override"})


async def emit_audit_if_critical(
    key: str,
    before: FeatureFlag | None,
    after: FeatureFlag | None,
    actor_email: str,
) -> None:
    """Emit a CRITICAL audit log entry and increment the Prometheus counter
    when ``key`` is a security-critical feature flag.

    If ``key`` is not in ``SECURITY_CRITICAL_FLAGS``, this function is a no-op.

    Args:
        key:         The feature-flag key being mutated.
        before:      The flag's state BEFORE the mutation.  ``None`` on create.
        after:       The flag's state AFTER the mutation.   ``None`` on delete.
        actor_email: Email of the super-admin performing the write.
    """
    if key not in SECURITY_CRITICAL_FLAGS:
        return

    previous_enabled: bool | None = before.default_enabled if before is not None else None
    new_enabled: bool | None = after.default_enabled if after is not None else None
    previous_is_active: bool | None = before.is_active if before is not None else None
    new_is_active: bool | None = after.is_active if after is not None else None

    details: dict[str, object] = {
        "flag_key": key,
        "before": {
            "is_active": previous_is_active,
            "default_enabled": previous_enabled,
        },
        "after": {
            "is_active": new_is_active,
            "default_enabled": new_enabled,
        },
    }

    # asyncio.shield prevents request-cancellation between the flag-write
    # commit and this audit-write from leaving inconsistent state. If the
    # caller is cancelled mid-await, the shielded coroutine still runs to
    # completion; only the outer `await` raises CancelledError after. The
    # flag write is durable and the audit row lands.
    try:
        await asyncio.shield(
            get_audit_logger().log_event(
                event_type=SecurityEventType.FEATURE_FLAG_CHANGED,
                email=actor_email,
                severity="CRITICAL",
                details=details,
            )
        )
    except Exception:
        # ERROR not WARNING — silent audit-sink failure on a SECURITY-CRITICAL
        # flag flip means the flag-flip record never lands and an attacker who
        # induces audit-sink errors can flip backends invisibly. exc_info=True
        # so the underlying cause is debuggable 6 months from now.
        logger.error(
            "emit_audit_if_critical: audit log write failed for flag '%s' "
            "(actor=%s). Proceeding — audit failure must not block flag write.",
            key,
            actor_email,
            exc_info=True,
        )

    # Increment the Prometheus counter regardless of audit success.
    prev_label = str(previous_enabled).lower()
    new_label = str(new_enabled).lower()
    try:
        ratelimit_backend_override_flips_total.labels(
            previous_enabled=prev_label,
            new_enabled=new_label,
        ).inc()
    except Exception:
        # ERROR + exc_info for the same reason: the counter is the SECOND
        # observability path (Cloud Monitoring alert source); silent failure
        # here is equally invisible.
        logger.error(
            "emit_audit_if_critical: Prometheus counter increment failed for "
            "flag '%s'. Proceeding.",
            key,
            exc_info=True,
        )
