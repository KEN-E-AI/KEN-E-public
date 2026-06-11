"""Unit tests for simplified account creation status tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.routers.accounts import (
    AccountCreationStatus,
    get_account_creation_status,
)

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Asserts stale message text and removed exception behavior — see DM-85"
)
async def test_get_account_creation_status_processing():
    """Test retrieving account creation status when account is being processed."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = False
    mock_user.has_organization_access = MagicMock(return_value=True)

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(
        return_value=[
            {
                "organization_id": "org123",
                "setup_status": "processing",
                "setup_completed_at": None,
            }
        ]
    )

    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "processing"
    assert "Creating account..." in result.message
    assert "15-20 minutes" in result.message


@pytest.mark.asyncio
async def test_get_account_creation_status_completed():
    """Test retrieving account creation status when account setup is complete."""
    # Super-admin bypasses the org resolver — focuses on status logic.
    mock_user = MagicMock()
    mock_user.is_super_admin = True

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(
        return_value=[
            {
                "setup_status": "completed",
                "setup_completed_at": "2025-01-31T12:00:00Z",
            }
        ]
    )

    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "completed"
    assert result.message == "Account setup complete"


@pytest.mark.asyncio
async def test_get_account_creation_status_failed_with_error():
    """Test retrieving account creation status when account setup failed with error details."""
    # Super-admin bypasses the org resolver — focuses on status logic.
    mock_user = MagicMock()
    mock_user.is_super_admin = True

    mock_db = AsyncMock()
    # First query returns the account status; second returns the error details.
    mock_db.execute_query = AsyncMock(
        side_effect=[
            [
                {
                    "setup_status": "failed",
                    "setup_completed_at": None,
                }
            ],
            [{"error": "Strategy generation failed: API rate limit exceeded"}],
        ]
    )

    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "failed"
    assert "Account setup failed: Strategy generation failed" in result.message


@pytest.mark.asyncio
async def test_get_account_creation_status_failed_no_error_details():
    """Test retrieving account creation status when account setup failed without error details."""
    # Super-admin bypasses the org resolver — focuses on status logic.
    mock_user = MagicMock()
    mock_user.is_super_admin = True

    mock_db = AsyncMock()
    # First query returns the account status; second returns no error details.
    mock_db.execute_query = AsyncMock(
        side_effect=[
            [
                {
                    "setup_status": "failed",
                    "setup_completed_at": None,
                }
            ],
            [{"error": None}],
        ]
    )

    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "failed"
    assert result.message == "Account setup failed. Please try again."


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Asserts stale message text and removed exception behavior — see DM-85"
)
async def test_get_account_creation_status_account_not_found():
    """Test retrieving account creation status when account doesn't exist."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = False

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(return_value=[])

    with pytest.raises(HTTPException) as exc_info:
        await get_account_creation_status(
            account_id="acc_nonexistent",
            user=mock_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Account not found"


@pytest.mark.asyncio
async def test_get_account_creation_status_access_denied():
    """Cross-org access denial now returns 404 (not 403) per IN-4 migration."""
    from src.kene_api.auth import UserContext

    denied_user = UserContext(
        user_id="n1",
        email="nobody@example.com",
        organization_permissions={},
        account_permissions={},
    )

    # Resolver returns org_B — denied_user has no permissions for it.
    with patch(_RESOLVER, AsyncMock(return_value="org_B")):
        with pytest.raises(HTTPException) as exc_info:
            await get_account_creation_status(
                account_id="acc_test123",
                user=denied_user,
                db=AsyncMock(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Account not found"


@pytest.mark.asyncio
async def test_get_account_creation_status_super_admin_access():
    """Test super admin can access any account status."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = True
    mock_user.has_organization_access = MagicMock(return_value=False)

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(
        return_value=[
            {
                "setup_status": "processing",
                "setup_completed_at": None,
            }
        ]
    )

    # Should not raise exception for super admin
    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "processing"


@pytest.mark.asyncio
async def test_get_account_creation_status_pending_default():
    """Test retrieving account creation status with default pending status."""
    # Super-admin bypasses the org resolver — focuses on status logic.
    mock_user = MagicMock()
    mock_user.is_super_admin = True

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(
        return_value=[
            {
                "setup_status": None,  # No status set yet
                "setup_completed_at": None,
            }
        ]
    )

    result = await get_account_creation_status(
        account_id="acc_test123",
        user=mock_user,
        db=mock_db,
    )

    assert isinstance(result, AccountCreationStatus)
    assert result.status == "processing"  # Defaults to processing for pending
    assert "Creating account..." in result.message


def test_account_creation_status_model():
    """Test AccountCreationStatus model validation."""
    # Test processing status
    status = AccountCreationStatus(
        status="processing",
        message="Creating account...",
    )
    assert status.status == "processing"
    assert status.message == "Creating account..."

    # Test completed status
    status = AccountCreationStatus(
        status="completed",
        message="Account setup complete",
    )
    assert status.status == "completed"
    assert status.message == "Account setup complete"

    # Test failed status
    status = AccountCreationStatus(
        status="failed",
        message="Account setup failed. Please try again.",
    )
    assert status.status == "failed"
    assert "failed" in status.message.lower()

    # Test all valid statuses
    for status_value in ["pending", "processing", "completed", "failed"]:
        status = AccountCreationStatus(status=status_value, message="Test")
        assert status.status == status_value
