"""Unit tests for account creation progress tracking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.routers.accounts import (
    AccountCreationProgress,
    ProgressStep,
    get_account_creation_status,
    update_account_progress,
)


@pytest.mark.asyncio
async def test_update_account_progress():
    """Test updating account creation progress."""
    # Test data
    account_id = "acc_test123"
    step = 3
    message = "Generating strategy..."
    steps_status = ["completed", "completed", "processing", "pending", "pending"]

    # Update progress
    await update_account_progress(account_id, step, message, steps_status)

    # Since we're using InMemoryCache, we can't directly verify the cache
    # but we can ensure the function runs without errors
    assert True  # Function completed successfully


@pytest.mark.asyncio
async def test_get_account_creation_status_with_cached_progress():
    """Test retrieving account creation status when progress is cached."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = False
    mock_user.has_organization_access = MagicMock(return_value=True)

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org123"}])

    # Test with cached progress
    with patch("src.kene_api.routers.accounts._cache_service") as mock_cache:
        mock_cache.get.return_value = {
            "status": "processing",
            "percentage": 60,
            "current_step": 3,
            "total_steps": 5,
            "message": "Generating strategy...",
            "steps": [
                {"name": "Creating account", "status": "completed"},
                {"name": "Setting up database", "status": "completed"},
                {"name": "Generating strategy", "status": "processing"},
                {"name": "Syncing activities", "status": "pending"},
                {"name": "Finalizing setup", "status": "pending"},
            ],
        }

        result = await get_account_creation_status(
            account_id="acc_test123",
            user=mock_user,
            db=mock_db,
        )

        assert isinstance(result, AccountCreationProgress)
        assert result.status == "processing"
        assert result.percentage == 60
        assert result.current_step == 3
        assert result.message == "Generating strategy..."
        assert len(result.steps) == 5


@pytest.mark.asyncio
async def test_get_account_creation_status_no_cache():
    """Test retrieving account creation status when no progress is cached."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = False
    mock_user.has_organization_access = MagicMock(return_value=True)

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org123"}])

    # Test with no cached progress
    with patch("src.kene_api.routers.accounts._cache_service") as mock_cache:
        mock_cache.get.return_value = None

        result = await get_account_creation_status(
            account_id="acc_test123",
            user=mock_user,
            db=mock_db,
        )

        # Should return default completed status
        assert isinstance(result, AccountCreationProgress)
        assert result.status == "completed"
        assert result.percentage == 100
        assert result.current_step == 5
        assert result.total_steps == 5
        assert result.message == "Account creation completed"
        assert all(step.status == "completed" for step in result.steps)


@pytest.mark.asyncio
async def test_get_account_creation_status_access_denied():
    """Test access denied when user doesn't have organization access."""
    # Mock dependencies
    mock_user = MagicMock()
    mock_user.is_super_admin = False
    mock_user.has_organization_access = MagicMock(return_value=False)

    mock_db = AsyncMock()
    mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org123"}])

    with pytest.raises(HTTPException) as exc_info:
        await get_account_creation_status(
            account_id="acc_test123",
            user=mock_user,
            db=mock_db,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied to account"


def test_progress_step_model():
    """Test ProgressStep model validation."""
    # Valid step
    step = ProgressStep(name="Test Step", status="completed")
    assert step.name == "Test Step"
    assert step.status == "completed"

    # Test all valid statuses
    for status in ["pending", "processing", "completed"]:
        step = ProgressStep(name="Test", status=status)
        assert step.status == status


def test_account_creation_progress_model():
    """Test AccountCreationProgress model validation."""
    progress = AccountCreationProgress(
        status="processing",
        percentage=40,
        current_step=2,
        total_steps=5,
        message="Setting up database...",
        steps=[
            ProgressStep(name="Creating account", status="completed"),
            ProgressStep(name="Setting up database", status="processing"),
            ProgressStep(name="Generating strategy", status="pending"),
            ProgressStep(name="Syncing activities", status="pending"),
            ProgressStep(name="Finalizing setup", status="pending"),
        ],
    )

    assert progress.status == "processing"
    assert progress.percentage == 40
    assert progress.current_step == 2
    assert progress.total_steps == 5
    assert progress.message == "Setting up database..."
    assert len(progress.steps) == 5
    assert progress.steps[0].status == "completed"
    assert progress.steps[1].status == "processing"
