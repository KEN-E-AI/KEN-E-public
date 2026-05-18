"""Test that user cache is properly invalidated when organization permissions change."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.auth.models import UserContext
from src.kene_api.models.kene_models import (
    Billing,
    OrganizationRequest,
    PaymentMethod,
    Subscription,
    Team,
)
from src.kene_api.routers.organizations import create_organization


@pytest.mark.asyncio
async def test_organization_creation_invalidates_user_cache():
    """Test that creating an organization invalidates the user's cached context."""

    # Create mock user context
    mock_user = UserContext(
        user_id="test_user_123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
    )

    # Create mock request
    request = OrganizationRequest(
        organization_name="Test Organization",
        plan="Professional",
        website="https://test-org.example.com",
        agency=False,
        subscription=Subscription(
            plan_name="Professional",
            plan_description="Professional plan",
            price=99.99,
            currency="USD",
            billing_cycle="monthly",
            next_billing_date="2025-02-01",
            features=["feature1"],
            usage={"reports_generated": 0, "reports_limit": 100},
        ),
        billing=Billing(
            payment_method=PaymentMethod(
                last_four="1234",
                brand="Visa",
                expires="12/25",
            ),
            address="123 Test St, Test City, TC 12345",
            tax_id="TAX123456",
        ),
        team=Team(
            members_used=1,
            members_limit=10,
            pending_invitations=0,
        ),
    )

    # Create mocks
    mock_db = MagicMock()
    mock_db.health_check = AsyncMock(return_value=True)
    mock_db.execute_write_query = AsyncMock(return_value=[])
    # The org record mirrors what Neo4j returns after creation. Organization
    # requires a non-null `website`, so the stored record must include it.
    mock_db.execute_query = AsyncMock(
        return_value=[
            {
                "org": {
                    "organization_id": "org_test123",
                    "organization_name": "Test Organization",
                    "plan": "Professional",
                    "website": "https://test-org.example.com",
                    "agency": False,
                    "subscription": json.dumps(request.subscription.model_dump()),
                    "billing": json.dumps(request.billing.model_dump()),
                    "team": json.dumps(request.team.model_dump()),
                }
            }
        ]
    )

    # Track if cache invalidation was called
    cache_invalidation_called = False
    invalidated_user_id = None

    def mock_invalidate_user_context(user_id):
        nonlocal cache_invalidation_called, invalidated_user_id
        cache_invalidation_called = True
        invalidated_user_id = user_id

    with patch(
        "src.kene_api.routers.organizations.get_firestore_service"
    ) as mock_firestore_service:
        with patch(
            "src.kene_api.auth.cached_user_context.get_cached_user_context_service"
        ) as mock_cache_service:
            with patch(
                "src.kene_api.routers.organizations._check_organization_exists",
                new_callable=AsyncMock,
            ) as mock_check_exists:
                with patch(
                    "src.kene_api.routers.organizations.generate_unique_organization_id"
                ) as mock_generate_id:
                    with patch(
                        "src.kene_api.routers.organizations.settings"
                    ) as mock_settings:
                        # Setup mocks
                        mock_settings.organization_creation_permission = "all"
                        mock_generate_id.return_value = "org_test123"
                        mock_check_exists.return_value = False

                        mock_fs = MagicMock()
                        mock_fs.set_nested_field = MagicMock(return_value=True)
                        mock_firestore_service.return_value = mock_fs

                        mock_cached_service = MagicMock()
                        mock_cached_service.invalidate_user_context = (
                            mock_invalidate_user_context
                        )
                        mock_cache_service.return_value = mock_cached_service

                        # Call the function
                        result = await create_organization(request, mock_user, mock_db)

                        # Verify organization was created
                        assert result.organization_id == "org_test123"
                        assert result.organization_name == "Test Organization"

                        # Verify permissions were granted
                        mock_fs.set_nested_field.assert_called_once_with(
                            collection="users",
                            document_id="test_user_123",
                            field_path="permissions.organizations.org_test123",
                            value="admin",
                        )

                        # Verify cache was invalidated
                        assert cache_invalidation_called, (
                            "Cache invalidation was not called"
                        )
                        assert invalidated_user_id == "test_user_123", (
                            f"Cache was invalidated for wrong user: {invalidated_user_id}"
                        )


@pytest.mark.asyncio
async def test_organization_creation_rollback_on_permission_failure():
    """Test that organization creation is rolled back if permission grant fails."""

    # Create mock user context
    mock_user = UserContext(
        user_id="test_user_123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
    )

    # Create mock request
    request = OrganizationRequest(
        organization_name="Test Organization",
        plan="Professional",
        agency=False,
        subscription=Subscription(
            plan_name="Professional",
            plan_description="Professional plan",
            price=99.99,
            currency="USD",
            billing_cycle="monthly",
            next_billing_date="2025-02-01",
            features=["feature1"],
            usage={"reports_generated": 0, "reports_limit": 100},
        ),
        billing=Billing(
            payment_method=PaymentMethod(
                last_four="1234",
                brand="Visa",
                expires="12/25",
            ),
            address="123 Test St, Test City, TC 12345",
            tax_id="TAX123456",
        ),
        team=Team(
            members_used=1,
            members_limit=10,
            pending_invitations=0,
        ),
    )

    # Create mocks
    mock_db = MagicMock()
    mock_db.health_check = AsyncMock(return_value=True)
    mock_db.execute_write_query = AsyncMock(return_value=[])
    mock_db.execute_write_operation = AsyncMock(return_value={})

    with patch(
        "src.kene_api.routers.organizations.get_firestore_service"
    ) as mock_firestore_service:
        with patch(
            "src.kene_api.routers.organizations._check_organization_exists",
            new_callable=AsyncMock,
        ) as mock_check_exists:
            with patch(
                "src.kene_api.routers.organizations.generate_unique_organization_id"
            ) as mock_generate_id:
                with patch(
                    "src.kene_api.routers.organizations.settings"
                ) as mock_settings:
                    # Setup mocks
                    mock_settings.organization_creation_permission = "all"
                    mock_generate_id.return_value = "org_test123"
                    mock_check_exists.return_value = False

                    mock_fs = MagicMock()
                    # Simulate permission grant failure
                    mock_fs.set_nested_field = MagicMock(return_value=False)
                    mock_firestore_service.return_value = mock_fs

                    # Call the function and expect it to raise an exception
                    with pytest.raises(Exception) as exc_info:
                        await create_organization(request, mock_user, mock_db)

                    # Verify rollback was attempted
                    mock_db.execute_write_operation.assert_called_once()
                    call_args = mock_db.execute_write_operation.call_args
                    assert (
                        "DELETE org" in call_args[0][0]
                    )  # Check that DELETE query was executed
                    assert call_args[0][1]["organization_id"] == "org_test123"
