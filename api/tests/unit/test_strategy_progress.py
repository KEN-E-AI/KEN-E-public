"""Unit tests for strategy generation progress tracking."""

from unittest.mock import patch

from src.kene_api.routers.accounts import AccountCreationProgress, ProgressStep
from src.kene_api.tasks.strategy_tasks import update_strategy_progress


class TestStrategyProgress:
    """Test suite for strategy generation progress tracking."""

    def test_update_strategy_progress_success(self) -> None:
        """Test successful update of strategy generation progress."""
        # Mock the progress cache
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            # Call the function
            update_strategy_progress("acc_test123", "Analyzing business...", 55)

            # Verify cache.set was called
            assert mock_cache.set.called
            call_args = mock_cache.set.call_args

            # Check the cache key
            assert call_args[0][0] == "account_creation:acc_test123"

            # Check the progress data structure
            progress_data = call_args[0][1]
            assert progress_data["percentage"] == 55
            assert progress_data["message"] == "Analyzing business..."
            assert progress_data["status"] == "processing"
            assert progress_data["current_step"] == 3
            assert progress_data["total_steps"] == 5

            # Check the steps
            assert len(progress_data["steps"]) == 5
            assert progress_data["steps"][0]["name"] == "Creating account"
            assert progress_data["steps"][0]["status"] == "completed"
            assert progress_data["steps"][2]["name"] == "Generating strategy"
            assert progress_data["steps"][2]["status"] == "processing"

            # Check TTL
            assert call_args[1]["ttl_seconds"] == 3600

    def test_update_strategy_progress_with_default_percentage(self) -> None:
        """Test progress update with default percentage value."""
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            # Call without specifying percentage
            update_strategy_progress("acc_test456", "Processing...")

            # Verify default percentage of 60
            call_args = mock_cache.set.call_args
            progress_data = call_args[0][1]
            assert progress_data["percentage"] == 60

    def test_update_strategy_progress_handles_cache_error(self) -> None:
        """Test that cache errors are handled gracefully."""
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            # Simulate cache error
            mock_cache.set.side_effect = AttributeError("Cache error")

            # Should not raise exception
            update_strategy_progress("acc_test789", "Test message", 70)

            # Verify the function attempted to set cache
            assert mock_cache.set.called

    def test_update_strategy_progress_handles_type_error(self) -> None:
        """Test handling of type errors in progress update."""
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            # Simulate type error
            mock_cache.set.side_effect = TypeError("Invalid type")

            # Should not raise exception
            update_strategy_progress("acc_test999", "Test", 80)

            # Verify the function attempted to set cache
            assert mock_cache.set.called

    def test_update_strategy_progress_validates_model(self) -> None:
        """Test that progress data uses proper AccountCreationProgress model."""
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            update_strategy_progress("acc_model_test", "Validating model", 65)

            # Get the data that was passed to cache.set
            call_args = mock_cache.set.call_args
            progress_data = call_args[0][1]

            # Verify it can be reconstructed as AccountCreationProgress
            progress = AccountCreationProgress(**progress_data)
            assert progress.percentage == 65
            assert progress.message == "Validating model"
            assert progress.current_step == 3
            assert len(progress.steps) == 5

            # Verify all steps have proper structure
            for step in progress.steps:
                assert isinstance(step, ProgressStep)
                assert step.name in [
                    "Creating account",
                    "Setting up database",
                    "Generating strategy",
                    "Syncing activities",
                    "Finalizing setup",
                ]

    def test_progress_steps_have_correct_status(self) -> None:
        """Test that progress steps have the correct status values."""
        with patch("src.kene_api.tasks.strategy_tasks.progress_cache") as mock_cache:
            update_strategy_progress("acc_status_test", "Checking status", 50)

            call_args = mock_cache.set.call_args
            progress_data = call_args[0][1]
            steps = progress_data["steps"]

            # Verify status progression
            assert steps[0]["status"] == "completed"  # Creating account
            assert steps[1]["status"] == "completed"  # Setting up database
            assert steps[2]["status"] == "processing"  # Generating strategy
            assert steps[3]["status"] == "pending"  # Syncing activities
            assert steps[4]["status"] == "pending"  # Finalizing setup
