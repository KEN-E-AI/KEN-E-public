"""Tests for organization creation with authentication."""

import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.kene_api.auth import UserContext
from src.kene_api.config import settings
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.models.kene_models import (
    Billing,
    Organization,
    OrganizationRequest,
    PaymentMethod,
    Subscription,
    Team,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)

client = TestClient(app)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service for testing."""
    mock_service = MagicMock()

    # Use AsyncMock for async methods
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(
        return_value={
            "nodes_created": 1,
            "nodes_deleted": 0,
            "relationships_created": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }
    )

    return mock_service


@pytest.fixture
def mock_firestore_service():
    """Create a mock Firestore service for testing."""
    mock_service = MagicMock()
    mock_service.set_nested_field = MagicMock(return_value=True)
    mock_service.get_client = MagicMock()
    return mock_service


@pytest.fixture
def mock_user_context():
    """Create a mock user context."""
    return UserContext(
        user_id="test-user-123",
        email="test@example.com",
        organization_permissions={"existing-org": "admin"},
        account_permissions={},
    )


@pytest.fixture
def mock_super_admin_context():
    """Create a mock super admin user context."""
    return UserContext(
        user_id="super-admin-123",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


@pytest.fixture
def sample_organization_request():
    """Create a sample organization request."""
    return OrganizationRequest(
        organization_name="Test Organization",
        plan="Professional",
        website="https://test.com",
        company_size="medium",
        agency=False,
        child_organizations=[],
        subscription=Subscription(
            plan_name="Professional",
            plan_description="Professional features",
            price=99.0,
            currency="USD",
            billing_cycle="monthly",
            next_billing_date=datetime.now(timezone.utc).isoformat(),
            features=["Feature 1", "Feature 2"],
            usage={"reports_generated": 0, "reports_limit": 100},
        ),
        billing=Billing(
            payment_method=PaymentMethod(
                last_four="1234", brand="Visa", expires="12/25"
            ),
            address="123 Main St",
            tax_id="TAX123",
        ),
        team=Team(members_used=1, members_limit=10, pending_invitations=0),
    )


class TestCreateOrganizationAuth:
    """Test organization creation with authentication."""

    @pytest.mark.asyncio
    async def test_create_organization_success(
        self,
        mock_neo4j_service,
        mock_firestore_service,
        mock_user_context,
        sample_organization_request,
    ):
        """Test successful organization creation."""
        from src.kene_api.routers.organizations import create_organization

        # Mock the internal helper to return an organization
        with patch(
            "src.kene_api.routers.organizations._get_organization_by_id"
        ) as mock_get_org:
            mock_org = Organization(
                organization_id="org_test123",
                organization_name=sample_organization_request.organization_name,
                plan=sample_organization_request.plan,
                website=sample_organization_request.website,
                company_size=sample_organization_request.company_size,
                agency=sample_organization_request.agency,
                child_organizations=sample_organization_request.child_organizations,
                subscription=sample_organization_request.subscription,
                billing=sample_organization_request.billing,
                team=sample_organization_request.team,
            )
            mock_get_org.return_value = mock_org

            # Test with default permission level ("all")
            with patch.object(settings, "organization_creation_permission", "all"):
                with patch(
                    "src.kene_api.routers.organizations.get_firestore_service",
                    return_value=mock_firestore_service,
                ):
                    result = await create_organization(
                        request=sample_organization_request,
                        user=mock_user_context,
                        db=mock_neo4j_service,
                    )

                    # Verify organization was created
                    assert (
                        result.organization_name
                        == sample_organization_request.organization_name
                    )
                    assert result.plan == sample_organization_request.plan

                    # Verify Neo4j was called
                    mock_neo4j_service.execute_write_query.assert_called_once()

                    # Verify Firestore permission was set
                    mock_firestore_service.set_nested_field.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_organization_super_admin_only(
        self,
        mock_neo4j_service,
        mock_firestore_service,
        mock_user_context,
        mock_super_admin_context,
        sample_organization_request,
    ):
        """Test organization creation when restricted to super admins."""
        from src.kene_api.routers.organizations import create_organization

        with patch.object(settings, "organization_creation_permission", "super_admin"):
            # Test with regular user - should fail
            with pytest.raises(HTTPException) as exc_info:
                await create_organization(
                    request=sample_organization_request,
                    user=mock_user_context,
                    db=mock_neo4j_service,
                )
            assert exc_info.value.status_code == 403
            assert "Only super administrators" in str(exc_info.value.detail)

            # Test with super admin - should succeed
            with patch(
                "src.kene_api.routers.organizations._get_organization_by_id"
            ) as mock_get_org:
                mock_org = Organization(
                    organization_id="org_test123",
                    organization_name=sample_organization_request.organization_name,
                    plan=sample_organization_request.plan,
                    website=sample_organization_request.website,
                    company_size=sample_organization_request.company_size,
                    agency=sample_organization_request.agency,
                    child_organizations=sample_organization_request.child_organizations,
                    subscription=sample_organization_request.subscription,
                    billing=sample_organization_request.billing,
                    team=sample_organization_request.team,
                )
                mock_get_org.return_value = mock_org

                result = await create_organization(
                    request=sample_organization_request,
                    user=mock_super_admin_context,
                    db=mock_neo4j_service,
                )
                assert (
                    result.organization_name
                    == sample_organization_request.organization_name
                )

    @pytest.mark.asyncio
    async def test_create_organization_disabled(
        self,
        mock_neo4j_service,
        mock_firestore_service,
        mock_user_context,
        sample_organization_request,
    ):
        """Test organization creation when disabled."""
        from src.kene_api.routers.organizations import create_organization

        with patch.object(settings, "organization_creation_permission", "none"):
            with pytest.raises(HTTPException) as exc_info:
                await create_organization(
                    request=sample_organization_request,
                    user=mock_user_context,
                    db=mock_neo4j_service,
                )
            assert exc_info.value.status_code == 403
            assert "Organization creation is currently disabled" in str(
                exc_info.value.detail
            )

    @pytest.mark.asyncio
    async def test_create_organization_firestore_failure_rollback(
        self,
        mock_neo4j_service,
        mock_firestore_service,
        mock_user_context,
        sample_organization_request,
    ):
        """Test rollback when Firestore permission grant fails."""
        from src.kene_api.routers.organizations import create_organization

        # Mock Firestore to fail
        mock_firestore_service.set_nested_field.return_value = False

        with patch(
            "src.kene_api.routers.organizations.get_firestore_service",
            return_value=mock_firestore_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_organization(
                    request=sample_organization_request,
                    user=mock_user_context,
                    db=mock_neo4j_service,
                )

            assert exc_info.value.status_code == 500
            assert "Failed to complete organization setup" in str(exc_info.value.detail)

            # Verify rollback was attempted (DELETE query executed)
            assert (
                mock_neo4j_service.execute_write_query.call_count == 2
            )  # CREATE + DELETE

    @pytest.mark.asyncio
    async def test_create_organization_firestore_exception_rollback(
        self,
        mock_neo4j_service,
        mock_firestore_service,
        mock_user_context,
        sample_organization_request,
    ):
        """Test rollback when Firestore throws an exception."""
        from src.kene_api.routers.organizations import create_organization

        # Mock Firestore to raise an exception
        mock_firestore_service.set_nested_field.side_effect = Exception(
            "Firestore connection error"
        )

        with patch(
            "src.kene_api.routers.organizations.get_firestore_service",
            return_value=mock_firestore_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_organization(
                    request=sample_organization_request,
                    user=mock_user_context,
                    db=mock_neo4j_service,
                )

            assert exc_info.value.status_code == 500
            assert "permission system error" in str(exc_info.value.detail)

            # Verify rollback was attempted
            assert (
                mock_neo4j_service.execute_write_query.call_count == 2
            )  # CREATE + DELETE


class TestGetOrganizationRefactored:
    """Test the refactored get_organization endpoint."""

    @pytest.mark.asyncio
    async def test_get_organization_with_access(
        self, mock_neo4j_service, mock_user_context
    ):
        """Test getting an organization with proper access."""
        from src.kene_api.routers.organizations import get_organization

        # Mock the internal helper
        with patch(
            "src.kene_api.routers.organizations._get_organization_by_id"
        ) as mock_get_org:
            mock_org = Organization(
                organization_id="existing-org",
                organization_name="Existing Org",
                plan="Professional",
                website="https://existing.com",
                company_size="large",
                agency=False,
                child_organizations=[],
                subscription=Subscription(
                    plan_name="Professional",
                    plan_description="Pro features",
                    price=99.0,
                    currency="USD",
                    billing_cycle="monthly",
                    next_billing_date="2024-01-01T00:00:00Z",
                    features=["Feature 1"],
                    usage={"reports_generated": 0, "reports_limit": 100},
                ),
                billing=Billing(
                    payment_method=PaymentMethod(
                        last_four="1234", brand="Visa", expires="12/25"
                    ),
                    address="123 Main St",
                    tax_id="TAX123",
                ),
                team=Team(members_used=1, members_limit=10, pending_invitations=0),
            )
            mock_get_org.return_value = mock_org

            result = await get_organization(
                organization_id="existing-org",
                user=mock_user_context,
                db=mock_neo4j_service,
            )

            assert result.organization_id == "existing-org"
            mock_get_org.assert_called_once_with("existing-org", mock_neo4j_service)

    @pytest.mark.asyncio
    async def test_get_organization_without_access(
        self, mock_neo4j_service, mock_user_context
    ):
        """Test getting an organization without access."""
        from src.kene_api.routers.organizations import get_organization

        with pytest.raises(HTTPException) as exc_info:
            await get_organization(
                organization_id="unauthorized-org",
                user=mock_user_context,
                db=mock_neo4j_service,
            )

        assert exc_info.value.status_code == 403
        assert "Access denied" in str(exc_info.value.detail)


class TestInternalHelperFunction:
    """Test the _get_organization_by_id internal helper."""

    @pytest.mark.asyncio
    async def test_get_organization_by_id_success(self, mock_neo4j_service):
        """Test successful organization retrieval."""
        from src.kene_api.routers.organizations import _get_organization_by_id

        # Mock Neo4j response
        mock_neo4j_service.execute_query.return_value = [
            {
                "org": {
                    "organization_id": "test-org",
                    "organization_name": "Test Org",
                    "plan": "Professional",
                    "website": "https://test.com",
                    "company_size": "medium",
                    "agency": False,
                    "child_organizations": [],
                    "subscription": json.dumps(
                        {
                            "plan_name": "Professional",
                            "plan_description": "Pro features",
                            "price": 99.0,
                            "currency": "USD",
                            "billing_cycle": "monthly",
                            "next_billing_date": "2024-01-01T00:00:00Z",
                            "features": ["Feature 1"],
                            "usage": {"reports_generated": 0, "reports_limit": 100},
                        }
                    ),
                    "billing": json.dumps(
                        {
                            "payment_method": {
                                "last_four": "1234",
                                "brand": "Visa",
                                "expires": "12/25",
                            },
                            "address": "123 Main St",
                            "tax_id": "TAX123",
                        }
                    ),
                    "team": json.dumps(
                        {
                            "members_used": 1,
                            "members_limit": 10,
                            "pending_invitations": 0,
                        }
                    ),
                }
            }
        ]

        result = await _get_organization_by_id("test-org", mock_neo4j_service)

        assert result.organization_id == "test-org"
        assert result.organization_name == "Test Org"
        assert result.plan == "Professional"

    @pytest.mark.asyncio
    async def test_get_organization_by_id_not_found(self, mock_neo4j_service):
        """Test organization not found."""
        from src.kene_api.routers.organizations import _get_organization_by_id

        # Mock empty response
        mock_neo4j_service.execute_query.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await _get_organization_by_id("nonexistent-org", mock_neo4j_service)

        assert exc_info.value.status_code == 404
        assert "Organization not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_organization_by_id_db_error(self, mock_neo4j_service):
        """Test database connectivity error."""
        from src.kene_api.routers.organizations import _get_organization_by_id

        # Mock health check failure
        mock_neo4j_service.health_check.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await _get_organization_by_id("test-org", mock_neo4j_service)

        assert exc_info.value.status_code == 503
        assert "Database service unavailable" in str(exc_info.value.detail)
