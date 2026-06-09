"""Onboarding gate predicate for the Early Release signup gate.

Spec: docs/design/components/data-management/projects/DM-PRD-11-early-release-signup-gate.md §4.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..auth.models import UserContext

logger = logging.getLogger(__name__)


@dataclass
class OnboardingDecision:
    """Result of the caller_may_onboard predicate.

    ``allowed`` signals whether the caller passes the gate.
    ``used_code`` is True only when clause 4 (Early Release code) granted access
    — the router uses this to decide whether to write a redemption record.
    """

    allowed: bool
    used_code: bool = False


async def caller_may_onboard(
    user: UserContext,
    access_code: str | None,
    *,
    firestore_service: Any,
    early_release_service: Any,
) -> OnboardingDecision:
    """Return an OnboardingDecision for a net-new org-create caller.

    Implements the four-clause predicate from DM-PRD-11 §4.3.  Branch order
    puts the cheapest checks first (in-memory) to short-circuit before any
    Firestore I/O:

    1. Staff / super-admin bypass (email domain + role — no I/O).
    2. Existing org membership (non-empty organization_permissions — no I/O).
    3. Pending invitation for caller's email (one Firestore read).
    4. Valid Early Release code (one Firestore read + constant-time compare).

    Args:
        user:                  Authenticated caller's UserContext.
        access_code:           Optional Early Release code from the request body.
        firestore_service:     FirestoreService singleton for invitation lookups.
        early_release_service: EarlyReleaseService singleton for code validation.
    """
    # Clause 1 — Super-admin always passes.
    # NOTE: an email-domain check (endswith "@ken-e.ai") is intentionally absent.
    # auth/models.py:33-34 documents why: Firebase signup is open, so an email
    # string is not a trustworthy authorization signal.  Every KEN-E staff member
    # who needs gate bypass must hold the server-provisioned super_admin role.
    if user.is_super_admin:
        return OnboardingDecision(allowed=True, used_code=False)

    # Clause 2 — Existing users (already belong to >= 1 org) are never blocked.
    if user.organization_permissions:
        return OnboardingDecision(allowed=True, used_code=False)

    # Clause 3 — Pending invitation for the caller's email.
    if await _has_pending_invitation(user.email, firestore_service):
        return OnboardingDecision(allowed=True, used_code=False)

    # Clause 4 — Valid Early Release code.
    if access_code and await early_release_service.validate(access_code):
        return OnboardingDecision(allowed=True, used_code=True)

    return OnboardingDecision(allowed=False, used_code=False)


async def _has_pending_invitation(email: str, firestore_service: Any) -> bool:
    """Return True if a non-expired pending invitation exists for ``email``.

    Mirrors the query pattern in ``routers/firestore.py::get_organization_invitations``
    (L2902-2926): query by ``email`` field, filter in Python.  No extra index
    required — the ``invitations`` collection is already queried by email today.

    Email comparison is case-insensitive (both sides lowercased) so invites
    sent with mixed-case recipients match regardless of signup casing.
    """
    normalised = email.strip().lower()
    invitations: list[dict[str, Any]] = await asyncio.to_thread(
        firestore_service.query_documents,
        "invitations",
        "email",
        "==",
        normalised,
        50,  # limit: one valid pending invite is enough; cap to avoid full-history scans
    )
    now = datetime.now(timezone.utc)
    for inv in invitations:
        if inv.get("status") != "pending":
            continue
        expires_at_raw = inv.get("expires_at")
        if expires_at_raw is None:
            continue
        try:
            expires_at = _parse_iso(expires_at_raw)
        except (ValueError, TypeError):
            logger.debug(
                "onboarding_gate_invalid_expires_at",
                extra={"expires_at": expires_at_raw},
            )
            continue
        if now <= expires_at:
            return True
    return False


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string to a timezone-aware UTC datetime.

    Invitation ``expires_at`` values are stored as ISO-8601 strings.  They may
    be timezone-aware (``Z`` / ``+00:00``) or naive (no suffix).  Naive strings
    are treated as UTC, matching the rest of the codebase's convention.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
