"""Unit tests for the onboarding gate predicate.

Covers each branch of ``caller_may_onboard`` independently.
No Firestore emulator — service interfaces are faked via MagicMock / AsyncMock.

Spec: DM-PRD-11 §4.3
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.kene_api.auth.models import UserContext
from src.kene_api.services.onboarding_gate import (
    OnboardingDecision,
    _has_pending_invitation,
    caller_may_onboard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(days=30)
_PAST = _NOW - timedelta(days=1)
_VALID_CODE = "early-access-alpha"


def _user(
    email: str = "newuser@example.com",
    org_permissions: dict | None = None,
    roles: list | None = None,
) -> UserContext:
    return UserContext(
        user_id="uid_test",
        email=email,
        organization_permissions=org_permissions or {},
        account_permissions={},
        roles=roles or [],
    )


def _fs_with_invitations(invitations: list[dict]) -> MagicMock:
    """Return a mock FirestoreService whose query_documents returns invitations."""
    fs = MagicMock()
    fs.query_documents.return_value = invitations
    return fs


def _er_validates(code: str | None) -> AsyncMock:
    """Return a mock EarlyReleaseService that validates exactly ``code``."""
    er = MagicMock()
    er.validate = AsyncMock(side_effect=lambda c: c == code)
    return er


# ---------------------------------------------------------------------------
# Clause 1 — email domain does NOT bypass the gate (security fix per auth/models.py:33-34)
# ---------------------------------------------------------------------------


async def test_staff_email_domain_alone_does_not_bypass() -> None:
    """@ken-e.ai email without the super_admin role does NOT bypass the gate.

    Firebase signup is open — email strings are not trustworthy authorization
    signals (see auth/models.py:33-34).  Only the server-provisioned
    super_admin role grants clause-1 bypass.
    """
    user = _user(email="alice@ken-e.ai")  # no super_admin role
    decision = await caller_may_onboard(
        user, None,
        firestore_service=_fs_with_invitations([]),
        early_release_service=_er_validates(None),
    )
    # Without the super_admin role, the user falls through to clauses 2-4.
    # No org membership, no invitation, no code → denied.
    assert decision == OnboardingDecision(allowed=False, used_code=False)


# ---------------------------------------------------------------------------
# Clause 1 — Staff bypass via super_admin role
# ---------------------------------------------------------------------------


async def test_super_admin_role_passes() -> None:
    """A user with the super_admin role bypasses the gate."""
    user = _user(email="external@example.com", roles=["super_admin"])
    fs = _fs_with_invitations([])
    er = _er_validates(None)

    decision = await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    assert decision == OnboardingDecision(allowed=True, used_code=False)
    fs.query_documents.assert_not_called()
    er.validate.assert_not_called()


# ---------------------------------------------------------------------------
# Clause 2 — Existing org membership short-circuits
# ---------------------------------------------------------------------------


async def test_existing_org_member_passes() -> None:
    """A user already belonging to an org passes without a Firestore read."""
    user = _user(org_permissions={"org_abc": "admin"})
    fs = _fs_with_invitations([])
    er = _er_validates(None)

    decision = await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    assert decision == OnboardingDecision(allowed=True, used_code=False)
    fs.query_documents.assert_not_called()
    er.validate.assert_not_called()


async def test_existing_org_member_multiple_orgs_passes() -> None:
    """A user belonging to multiple orgs passes."""
    user = _user(org_permissions={"org_1": "admin", "org_2": "view"})
    decision = await caller_may_onboard(
        user, None,
        firestore_service=_fs_with_invitations([]),
        early_release_service=_er_validates(None),
    )
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Clause 3 — Pending invitation
# ---------------------------------------------------------------------------


async def test_pending_invitation_not_expired_passes() -> None:
    """A net-new user with a pending, non-expired invitation passes."""
    user = _user(email="invited@example.com")
    inv = {
        "email": "invited@example.com",
        "status": "pending",
        "expires_at": _FUTURE.isoformat(),
    }
    fs = _fs_with_invitations([inv])
    er = _er_validates(None)

    decision = await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    assert decision == OnboardingDecision(allowed=True, used_code=False)
    er.validate.assert_not_called()


async def test_pending_invitation_expired_does_not_pass() -> None:
    """An expired pending invitation does not satisfy clause 3."""
    user = _user(email="expired@example.com")
    inv = {
        "email": "expired@example.com",
        "status": "pending",
        "expires_at": _PAST.isoformat(),
    }
    fs = _fs_with_invitations([inv])
    er = _er_validates(None)

    decision = await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    assert decision.allowed is False


async def test_accepted_invitation_does_not_satisfy_clause_3() -> None:
    """An accepted invitation is filtered out (status != "pending")."""
    user = _user(email="accepted@example.com")
    inv = {
        "email": "accepted@example.com",
        "status": "accepted",
        "expires_at": _FUTURE.isoformat(),
    }
    decision = await caller_may_onboard(
        user, None,
        firestore_service=_fs_with_invitations([inv]),
        early_release_service=_er_validates(None),
    )
    assert decision.allowed is False


# ---------------------------------------------------------------------------
# Clause 4 — Valid Early Release code
# ---------------------------------------------------------------------------


async def test_valid_code_passes_and_sets_used_code() -> None:
    """A net-new user with a valid code passes with used_code=True."""
    user = _user()
    fs = _fs_with_invitations([])
    er = _er_validates(_VALID_CODE)

    decision = await caller_may_onboard(user, _VALID_CODE, firestore_service=fs, early_release_service=er)

    assert decision == OnboardingDecision(allowed=True, used_code=True)
    er.validate.assert_awaited_once_with(_VALID_CODE)


async def test_invalid_code_is_rejected() -> None:
    """A wrong code is rejected."""
    user = _user()
    decision = await caller_may_onboard(
        user, "wrong-code",
        firestore_service=_fs_with_invitations([]),
        early_release_service=_er_validates(_VALID_CODE),
    )
    assert decision == OnboardingDecision(allowed=False, used_code=False)


async def test_no_code_and_no_invite_is_rejected() -> None:
    """A net-new user with no code and no pending invite is denied."""
    user = _user()
    decision = await caller_may_onboard(
        user, None,
        firestore_service=_fs_with_invitations([]),
        early_release_service=_er_validates(None),
    )
    assert decision == OnboardingDecision(allowed=False, used_code=False)


# ---------------------------------------------------------------------------
# Short-circuit: Firestore not called for staff / existing member
# ---------------------------------------------------------------------------


async def test_firestore_not_called_for_super_admin() -> None:
    """Clause 1 (super_admin role) must short-circuit before any Firestore call."""
    user = _user(roles=["super_admin"])
    fs = MagicMock()
    er = MagicMock()

    await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    fs.query_documents.assert_not_called()


async def test_firestore_not_called_for_existing_member() -> None:
    """Clause 2 (org membership) must short-circuit before any Firestore call."""
    user = _user(org_permissions={"org_x": "view"})
    fs = MagicMock()
    er = MagicMock()

    await caller_may_onboard(user, None, firestore_service=fs, early_release_service=er)

    fs.query_documents.assert_not_called()


# ---------------------------------------------------------------------------
# _has_pending_invitation — case-insensitive email matching
# ---------------------------------------------------------------------------


async def test_has_pending_invitation_case_insensitive() -> None:
    """Invitation lookup is case-insensitive on the email side."""
    inv = {
        "email": "User@Example.COM",
        "status": "pending",
        "expires_at": _FUTURE.isoformat(),
    }
    fs = _fs_with_invitations([inv])
    # The query is issued with the lowercased email; the invitation row itself
    # may have mixed-case because query_documents is mocked.
    result = await _has_pending_invitation("user@example.com", fs)
    assert result is True


async def test_has_pending_invitation_returns_false_when_empty() -> None:
    """No invitations → False."""
    result = await _has_pending_invitation("nobody@example.com", _fs_with_invitations([]))
    assert result is False


async def test_has_pending_invitation_skips_invalid_expires_at() -> None:
    """An invitation with an unparsable expires_at is silently skipped."""
    inv = {
        "email": "x@example.com",
        "status": "pending",
        "expires_at": "NOT_A_DATE",
    }
    result = await _has_pending_invitation("x@example.com", _fs_with_invitations([inv]))
    assert result is False


async def test_has_pending_invitation_naive_datetime_treated_as_utc() -> None:
    """A naive expires_at ISO string (no tz suffix) is treated as UTC."""
    # _FUTURE is timezone-aware; strip the tzinfo to simulate a naive stored value.
    naive_future = _FUTURE.replace(tzinfo=None).isoformat()
    inv = {"email": "y@example.com", "status": "pending", "expires_at": naive_future}
    result = await _has_pending_invitation("y@example.com", _fs_with_invitations([inv]))
    assert result is True
