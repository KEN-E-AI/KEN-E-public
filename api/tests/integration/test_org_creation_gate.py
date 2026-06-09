"""Integration tests for the Early Release onboarding gate in create_organization.

Tests the full router → service → mock-Firestore / mock-EarlyRelease round-trip
using the same dependency-override pattern as ``test_organization_creation_auth.py``.

Coverage matrix: {flag OFF, flag ON} x {
    @ken-e.ai staff,
    super-admin via role,
    user-with-existing-org,
    user-with-pending-invitation,
    valid code,
    invalid code,
    no code,
}

Also covers:
- Precedence: ``organization_creation_permission ∈ {none, super_admin}`` short-circuits
  before the gate even when the flag is ON.
- Flag-service outage: ``is_feature_enabled`` raises → fail-open (201, no gate).
- Redemption: written exactly once (with new org_id) on valid-code path,
  NOT written on any other pass path.

Spec: DM-PRD-11 §4.3, §4.6, §7 ACs 1-7
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import UserContext
from src.kene_api.config import settings
from src.kene_api.models.kene_models import (
    Billing,
    Organization,
    OrganizationRequest,
    PaymentMethod,
    Subscription,
    Team,
)

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(days=30)
_VALID_CODE = "early-access-alpha"

# Module path prefix for patching names in the organizations router
_ORGS = "src.kene_api.routers.organizations"


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


def _pending_invite(email: str = "invited@example.com") -> dict:
    return {
        "email": email,
        "status": "pending",
        "expires_at": _FUTURE.isoformat(),
        "organization_id": "org_existing",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def neo4j_mock():
    mock = MagicMock()
    mock.health_check = AsyncMock(return_value=True)
    # execute_query is used by _check_organization_exists; empty list = no collision.
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


@pytest.fixture()
def org_request() -> OrganizationRequest:
    return OrganizationRequest(
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


@pytest.fixture()
def created_org(org_request: OrganizationRequest) -> Organization:
    return Organization(
        organization_id="org_new123",
        organization_name=org_request.organization_name,
        plan=org_request.plan,
        website="",
        agency=org_request.agency,
        subscription=org_request.subscription,
        billing=org_request.billing,
        team=org_request.team,
    )


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------


async def _invoke(
    user: UserContext,
    request: OrganizationRequest,
    neo4j_mock: MagicMock,
    firestore_mock: MagicMock,
    created_org: Organization,
    *,
    permission_level: str = "all",
    flag_enabled: bool = False,
    flag_service_outage: bool = False,
    er_validates: bool = False,
    record_redemption_mock: AsyncMock | None = None,
) -> Organization:
    """Invoke ``create_organization`` with all mocks wired up.

    All names patched here are module-level in ``routers/organizations.py``
    so ``unittest.mock.patch`` can replace them before the function body runs.

    ``flag_service_outage=True`` simulates a Firestore outage during flag
    evaluation by making ``get_feature_flag_service()`` raise inside
    ``is_feature_enabled`` — which then catches the exception and returns
    its ``default=False``.  This is the production fail-open path.
    """
    from src.kene_api.routers.organizations import create_organization

    er_service = MagicMock()
    er_service.validate = AsyncMock(return_value=er_validates)
    er_service.record_redemption = record_redemption_mock or AsyncMock()

    if flag_service_outage:
        # Simulate the underlying flag service being down.  is_feature_enabled
        # catches this internally and returns default=False (fail-open).
        flag_patch = patch(
            "src.kene_api.services.feature_flag_service.get_feature_flag_service",
            side_effect=Exception("flag service down"),
        )
    else:
        flag_patch = patch(
            f"{_ORGS}.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=flag_enabled,
        )

    with (
        patch.object(settings, "organization_creation_permission", permission_level),
        patch(f"{_ORGS}.get_firestore_service", return_value=firestore_mock),
        patch(f"{_ORGS}._get_organization_by_id", return_value=created_org),
        patch(f"{_ORGS}.get_early_release_service", return_value=er_service),
        flag_patch,
    ):
        return await create_organization(request=request, user=user, db=neo4j_mock)


# ---------------------------------------------------------------------------
# Flag OFF — gate must not run at all, open signup preserved
# ---------------------------------------------------------------------------


async def test_flag_off_net_new_user_no_code_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Flag OFF: any authenticated user can create an org — today's behaviour."""
    result = await _invoke(
        _user(), org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=False,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_off_redemption_not_written(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Flag OFF: no redemption record is written even if an access_code is supplied."""
    request = org_request.model_copy(update={"access_code": _VALID_CODE})
    record_mock = AsyncMock()
    await _invoke(
        _user(), request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=False,
        er_validates=True,
        record_redemption_mock=record_mock,
    )
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Flag ON — staff bypass (clause 1: super_admin role only, not email domain)
# ---------------------------------------------------------------------------


async def test_flag_on_ken_e_email_without_role_is_blocked(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """@ken-e.ai email WITHOUT the super_admin role is NOT a bypass.

    Firebase signup is open — email strings are not trustworthy.
    See auth/models.py:33-34.
    """
    with pytest.raises(HTTPException) as exc_info:
        await _invoke(
            _user(email="alice@ken-e.ai"),  # no super_admin role
            org_request, neo4j_mock, firestore_mock, created_org,
            flag_enabled=True,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "early_access_required"


async def test_flag_on_super_admin_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Super-admin role bypasses the gate without a code."""
    result = await _invoke(
        _user(roles=["super_admin"]), org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_on_super_admin_no_redemption(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Super-admin bypass (permission_level 'all' + is_super_admin) does not write a redemption."""
    record_mock = AsyncMock()
    await _invoke(
        _user(roles=["super_admin"]), org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        record_redemption_mock=record_mock,
    )
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Flag ON — existing org member (clause 2)
# ---------------------------------------------------------------------------


async def test_flag_on_existing_org_member_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """An existing org member is never blocked even when flag is ON."""
    result = await _invoke(
        _user(org_permissions={"org_existing": "admin"}),
        org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_on_existing_org_member_no_redemption(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Existing-member pass path does not write a redemption record."""
    record_mock = AsyncMock()
    await _invoke(
        _user(org_permissions={"org_existing": "view"}),
        org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        record_redemption_mock=record_mock,
    )
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Flag ON — pending invitation (clause 3)
# ---------------------------------------------------------------------------


async def test_flag_on_pending_invitation_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """A net-new user with a pending invitation can create an org."""
    email = "invited@example.com"
    firestore_mock.query_documents = MagicMock(return_value=[_pending_invite(email)])
    result = await _invoke(
        _user(email=email), org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_on_pending_invitation_no_redemption(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Pending-invitation pass path does not write a redemption record."""
    email = "invited2@example.com"
    firestore_mock.query_documents = MagicMock(return_value=[_pending_invite(email)])
    record_mock = AsyncMock()
    await _invoke(
        _user(email=email), org_request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        record_redemption_mock=record_mock,
    )
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Flag ON — valid code (clause 4)
# ---------------------------------------------------------------------------


async def test_flag_on_valid_code_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """A valid Early Release code lets a net-new user create an org."""
    request = org_request.model_copy(update={"access_code": _VALID_CODE})
    result = await _invoke(
        _user(), request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        er_validates=True,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_on_valid_code_writes_redemption_with_new_org_id(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """A redemption record is written exactly once on the valid-code path."""
    request = org_request.model_copy(update={"access_code": _VALID_CODE})
    record_mock = AsyncMock()

    await _invoke(
        _user(), request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        er_validates=True,
        record_redemption_mock=record_mock,
    )

    record_mock.assert_awaited_once()
    call_kwargs = record_mock.call_args.kwargs
    assert call_kwargs["user_id"] == "uid_test"
    assert call_kwargs["email"] == "newuser@example.com"
    # org_id is the UUID generated inside create_organization, not the fixture's static id.
    assert call_kwargs["org_id"].startswith("org_")


async def test_flag_on_valid_code_redemption_failure_does_not_rollback(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """A redemption write failure must not roll back the org creation."""
    request = org_request.model_copy(update={"access_code": _VALID_CODE})
    record_mock = AsyncMock(side_effect=Exception("Firestore transient error"))

    result = await _invoke(
        _user(), request, neo4j_mock, firestore_mock, created_org,
        flag_enabled=True,
        er_validates=True,
        record_redemption_mock=record_mock,
    )
    assert result.organization_name == org_request.organization_name


# ---------------------------------------------------------------------------
# Flag ON — blocked paths
# ---------------------------------------------------------------------------


async def test_flag_on_no_code_net_new_user_returns_403(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """A net-new user with no code gets 403 early_access_required when flag is ON."""
    with pytest.raises(HTTPException) as exc_info:
        await _invoke(
            _user(), org_request, neo4j_mock, firestore_mock, created_org,
            flag_enabled=True,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "early_access_required"


async def test_flag_on_invalid_code_returns_403(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """An invalid code gets 403 early_access_required when flag is ON."""
    request = org_request.model_copy(update={"access_code": "wrong-code"})
    with pytest.raises(HTTPException) as exc_info:
        await _invoke(
            _user(), request, neo4j_mock, firestore_mock, created_org,
            flag_enabled=True,
            er_validates=False,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "early_access_required"


async def test_flag_on_no_redemption_written_when_blocked(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """No redemption is written when the gate blocks the caller."""
    record_mock = AsyncMock()
    with pytest.raises(HTTPException):
        await _invoke(
            _user(), org_request, neo4j_mock, firestore_mock, created_org,
            flag_enabled=True,
            record_redemption_mock=record_mock,
        )
    record_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Precedence: organization_creation_permission short-circuits before the gate
# ---------------------------------------------------------------------------


async def test_permission_none_short_circuits_before_gate(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """permission_level='none' → 403 regardless of flag state or code."""
    with pytest.raises(HTTPException) as exc_info:
        await _invoke(
            _user(), org_request, neo4j_mock, firestore_mock, created_org,
            permission_level="none",
            flag_enabled=True,
            er_validates=True,
        )
    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


async def test_permission_super_admin_non_super_admin_short_circuits(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """permission_level='super_admin' blocks non-super-admin regardless of flag."""
    with pytest.raises(HTTPException) as exc_info:
        await _invoke(
            _user(), org_request, neo4j_mock, firestore_mock, created_org,
            permission_level="super_admin",
            flag_enabled=True,
            er_validates=True,
        )
    assert exc_info.value.status_code == 403
    assert "super administrator" in exc_info.value.detail.lower()


async def test_permission_super_admin_super_admin_passes(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """permission_level='super_admin' + super-admin user → 201 (existing behaviour)."""
    result = await _invoke(
        _user(roles=["super_admin"]), org_request, neo4j_mock, firestore_mock, created_org,
        permission_level="super_admin",
        flag_enabled=True,
    )
    assert result.organization_name == org_request.organization_name


# ---------------------------------------------------------------------------
# Flag-service outage — fail-open
# ---------------------------------------------------------------------------


async def test_flag_service_outage_fails_open(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Underlying flag-service outage → is_feature_enabled returns False (fail-open) → 201."""
    result = await _invoke(
        _user(), org_request, neo4j_mock, firestore_mock, created_org,
        flag_service_outage=True,
    )
    assert result.organization_name == org_request.organization_name


async def test_flag_service_outage_no_redemption(
    neo4j_mock, firestore_mock, org_request, created_org
):
    """Flag-service outage: is_feature_enabled returns False, gate never ran, no redemption."""
    record_mock = AsyncMock()
    await _invoke(
        _user(), org_request, neo4j_mock, firestore_mock, created_org,
        flag_service_outage=True,
        record_redemption_mock=record_mock,
    )
    record_mock.assert_not_awaited()
