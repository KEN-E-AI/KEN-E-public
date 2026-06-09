"""End-to-end invariant suite for the Early Release onboarding gate (DM-PRD-11 §7).

One test per load-bearing invariant. Each test exercises POST /api/v1/organizations/
through the full FastAPI app stack (TestClient + dependency_overrides) so a future
router refactor -- extracting the gate to a dependency, moving the predicate, or
swapping import paths -- breaks these tests rather than only the unit-level patches
in test_org_creation_gate.py.

The invariants:
  A. Flag ON + un-invited, no code -> 403 early_access_required
  A2. Flag ON + invalid code -> 403 (code is checked, not just presence)
  B. Flag ON + pending invitation -> 200, no redemption written
  C. Flag ON + valid code -> 200, redemption recorded with org_id starting 'org_'
  D. Flag ON + super_admin role -> 200, no redemption;
     @ken-e.ai email WITHOUT the role -> 403 (role-only bypass per Review 48)
  E. Flag OFF -> 200 (open signup), no redemption
  F. Flag ON + existing org member -> 200, no redemption (existing users never locked out)
  G. Flag-service outage -> fail-open (200, gate never ran)

Spec: DM-PRD-11 §7 ACs 1-7, §8 e2e bullets, DESIGN-REVIEW-LOG Review 48 (role-only bypass).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.config import settings
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app
from src.kene_api.models.kene_models import (
    Billing,
    Organization,
    OrganizationRequest,
    PaymentMethod,
    Subscription,
    Team,
)
from src.kene_api.services.early_release_service import get_early_release_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
# _has_pending_invitation compares expires_at against the real wall clock, not _NOW,
# so the pending-invite expiry must be future-relative to run time — a fixed date
# would silently expire and red-fail invariant B once that date passes.
_FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
_VALID_CODE = "early-access-alpha"

_ORGS = "src.kene_api.routers.organizations"
_URL = "/api/v1/organizations/"

# ---------------------------------------------------------------------------
# Module-level stubs (immutable; do not mutate in tests)
# ---------------------------------------------------------------------------

_BASE_REQUEST = OrganizationRequest(
    organization_name="Test Org",
    plan="Starter",
    agency=False,
    subscription=Subscription(
        plan_name="Starter",
        plan_description="Starter plan",
        price=0.0,
        currency="USD",
        billing_cycle="monthly",
        next_billing_date=_NOW.isoformat(),
        features=[],
        usage={},
    ),
    billing=Billing(
        payment_method=PaymentMethod(last_four="0000", brand="Visa", expires="01/30"),
        address="1 Main St",
        tax_id="",
    ),
    team=Team(members_used=1, members_limit=5, pending_invitations=0),
)

_CREATED_ORG = Organization(
    organization_id="org_new123",
    organization_name="Test Org",
    plan="Starter",
    website="",
    agency=False,
    subscription=_BASE_REQUEST.subscription,
    billing=_BASE_REQUEST.billing,
    team=_BASE_REQUEST.team,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(
    email: str = "newuser@example.com",
    org_permissions: dict[str, str] | None = None,
    roles: list[str] | None = None,
) -> UserContext:
    return UserContext(
        user_id="uid_test",
        email=email,
        organization_permissions=org_permissions or {},
        account_permissions={},
        roles=roles or [],
    )


def _pending_invite(email: str) -> dict:
    return {
        "email": email,
        "status": "pending",
        "expires_at": _FUTURE.isoformat(),
        "organization_id": "org_existing",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_overrides():
    """Isolate dependency overrides and service caches between tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    # The early-release service uses @lru_cache; clear it per the service docstring.
    get_early_release_service.cache_clear()


@pytest.fixture()
def neo4j_mock():
    mock = MagicMock()
    mock.health_check = AsyncMock(return_value=True)
    # execute_query is used by _check_organization_exists; empty list = no collision
    mock.execute_query = AsyncMock(return_value=[{"exists": False}])
    mock.execute_write_query = AsyncMock(return_value={"nodes_created": 1})
    mock.execute_write_operation = AsyncMock(return_value=None)
    return mock


@pytest.fixture()
def firestore_mock():
    mock = MagicMock()
    mock.set_nested_field = MagicMock(return_value=True)
    mock.query_documents = MagicMock(return_value=[])
    return mock


# ---------------------------------------------------------------------------
# Core invoke helper
# ---------------------------------------------------------------------------


def _invoke(
    *,
    user: UserContext,
    neo4j_mock: MagicMock,
    firestore_mock: MagicMock,
    flag_on: bool,
    request_overrides: dict | None = None,
    er_validates: bool = False,
    record_redemption_mock: AsyncMock | None = None,
    flag_outage: bool = False,
) -> tuple[int, dict]:
    """POST /api/v1/organizations/ through the full app stack.

    Uses ``app.dependency_overrides`` for Depends()-injected parameters (auth, neo4j)
    and ``patch`` for module-level calls inside the router body. ``settings.organization_
    creation_permission`` is pinned to ``"all"`` so the gate path is always exercised,
    regardless of the ambient environment configuration.

    Returns (status_code, response_body_dict).
    """
    er_service = MagicMock()
    er_service.validate = AsyncMock(return_value=er_validates)
    er_service.record_redemption = record_redemption_mock or AsyncMock()

    app.dependency_overrides[get_current_user_context] = lambda: user
    app.dependency_overrides[get_neo4j_service] = lambda: neo4j_mock

    req = _BASE_REQUEST.model_copy(update=request_overrides or {})
    body = req.model_dump(mode="json")

    # Fail-open path: simulate the underlying flag-service being down.
    # is_feature_enabled catches the internal error and returns default=False.
    if flag_outage:
        flag_patch = patch(
            "src.kene_api.services.feature_flag_service.get_feature_flag_service",
            side_effect=Exception("flag service down"),
        )
    else:
        flag_patch = patch(
            f"{_ORGS}.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=flag_on,
        )

    with (
        patch.object(settings, "organization_creation_permission", "all"),
        patch(f"{_ORGS}.get_firestore_service", return_value=firestore_mock),
        patch(f"{_ORGS}.get_early_release_service", return_value=er_service),
        patch(f"{_ORGS}._get_organization_by_id", return_value=_CREATED_ORG),
        flag_patch,
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(_URL, json=body)

    return resp.status_code, resp.json()


# ---------------------------------------------------------------------------
# Invariant A -- Un-invited user with no code is blocked when flag ON
# ---------------------------------------------------------------------------


def test_invariant_a_un_invited_no_code_blocked_when_flag_on(neo4j_mock, firestore_mock):
    """AC-1: flag ON + no code + no pending invitation -> 403 early_access_required."""
    status, body = _invoke(
        user=_user(),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
    )
    assert status == 403
    assert body.get("detail") == "early_access_required"


# ---------------------------------------------------------------------------
# Invariant A2 -- An invalid code is still blocked (code is validated, not just present)
# ---------------------------------------------------------------------------


def test_invariant_a2_invalid_code_blocked_when_flag_on(neo4j_mock, firestore_mock):
    """AC-1 (complement): a wrong code must not bypass the gate."""
    status, body = _invoke(
        user=_user(),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
        request_overrides={"access_code": "wrong-code"},
        er_validates=False,
    )
    assert status == 403
    assert body.get("detail") == "early_access_required"


# ---------------------------------------------------------------------------
# Invariant B -- Invited user signs up and joins their org without a code
# ---------------------------------------------------------------------------


def test_invariant_b_invited_user_signs_up_without_code(neo4j_mock, firestore_mock):
    """AC-2: a pending invitation passes the gate (clause 3); no redemption written."""
    email = "invited@example.com"
    firestore_mock.query_documents = MagicMock(return_value=[_pending_invite(email)])
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(email=email),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Invariant C -- Valid code creates workspace and records redemption
# ---------------------------------------------------------------------------


def test_invariant_c_valid_code_creates_workspace_and_records_redemption(neo4j_mock, firestore_mock):
    """AC-3: valid shared code -> 200, redemption written with org_id prefixed 'org_'."""
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
        request_overrides={"access_code": _VALID_CODE},
        er_validates=True,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_awaited_once()
    kwargs = record_mock.call_args.kwargs
    assert kwargs["user_id"] == "uid_test"
    assert kwargs["email"] == "newuser@example.com"
    # org_id is generated inside create_organization, not the static stub value
    assert kwargs["org_id"].startswith("org_")


# ---------------------------------------------------------------------------
# Invariant D -- Super-admin role bypasses; @ken-e.ai email without role does NOT
# ---------------------------------------------------------------------------


def test_invariant_d_super_admin_role_bypasses_gate(neo4j_mock, firestore_mock):
    """AC-5a: super_admin role -> 200 with no code; no redemption written."""
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(roles=["super_admin"]),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_not_awaited()


def test_invariant_d_ken_e_email_without_super_admin_role_is_blocked(neo4j_mock, firestore_mock):
    """AC-5b: @ken-e.ai WITHOUT super_admin role -> 403 (Review 48 -- role-only bypass).

    Firebase signup is open so an email string is not a trustworthy auth signal.
    The bypass is role-based only; email domain confers no special access.
    """
    status, body = _invoke(
        user=_user(email="staff@ken-e.ai"),  # no super_admin role
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
    )
    assert status == 403
    assert body.get("detail") == "early_access_required"


# ---------------------------------------------------------------------------
# Invariant E -- Flag OFF = open signup (gate never runs)
# ---------------------------------------------------------------------------


def test_invariant_e_flag_off_is_open_signup(neo4j_mock, firestore_mock):
    """AC-6: flag OFF -> 200 for any authenticated user; gate does not run; no redemption."""
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=False,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Invariant F -- Existing user (already in an org) is never locked out
# ---------------------------------------------------------------------------


def test_invariant_f_existing_user_never_locked_out_when_flag_on(neo4j_mock, firestore_mock):
    """AC-7: a user already in an org bypasses the gate (clause 2); no redemption written."""
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(org_permissions={"org_existing": "admin"}),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=True,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Invariant G -- Flag-service outage fails open (signup reopens, PRD §4.4, §9)
# ---------------------------------------------------------------------------


def test_invariant_g_flag_service_outage_fails_open(neo4j_mock, firestore_mock):
    """PRD §4.4: a flag-service error returns default=False, reopening signup.

    A service outage must not lock out legitimate users who cannot verify their code.
    """
    record_mock = AsyncMock()

    status, _ = _invoke(
        user=_user(),
        neo4j_mock=neo4j_mock,
        firestore_mock=firestore_mock,
        flag_on=False,  # ignored when flag_outage=True
        flag_outage=True,
        record_redemption_mock=record_mock,
    )
    assert status == 200
    record_mock.assert_not_awaited()
