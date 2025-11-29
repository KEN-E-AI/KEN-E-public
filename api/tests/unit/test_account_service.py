"""Unit tests for account service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException
from src.kene_api.auth import UserContext
from src.kene_api.models.kene_models import Account, AccountRequest
from src.kene_api.services.account_service import create_account_internal


class TestCreateAccountInternal:
    """Test the create_account_internal function."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for testing."""
        mocks = {
            "user": MagicMock(spec=UserContext),
            "firestore": MagicMock(),
            "storage": MagicMock(),
            "neo4j": AsyncMock(),  # Add Neo4j mock
            "bigquery": MagicMock(),
            "background_tasks": BackgroundTasks(),
        }

        # Setup user mock
        mocks["user"].uid = "user_123"
        mocks["user"].user_id = "user_123"

        # Setup firestore mock
        mocks["firestore"].get_document = MagicMock(
            return_value={"data": {"agency": False}}
        )
        mocks["firestore"].set_document = MagicMock(return_value=True)
        mocks["firestore"].create_document = MagicMock(return_value="doc_123")
        mocks["firestore"].set_nested_field = MagicMock(return_value=True)

        # Setup Neo4j mock - organization exists and is not an agency
        mocks["neo4j"].execute_query = AsyncMock(
            return_value=[{"agency": False, "organization_name": "Test Organization"}]
        )
        mocks["neo4j"].execute_write_query = AsyncMock(return_value=True)

        # Setup storage mock
        mocks["storage"].ensure_bucket_exists = AsyncMock(
            return_value=("bucket", "us-central1")
        )
        mocks["storage"].ensure_account_folder = AsyncMock(return_value=True)

        return mocks

    @pytest.fixture
    def sample_request(self):
        """Create a sample AccountRequest."""
        return AccountRequest(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites=["https://example.com"],
            timezone="America/New_York",
            data_region="US",
            region=["North America"],
            marketing_channels=["SEO", "PPC"],
            product_integrations=["Analytics"],
            estimated_annual_ad_budget=50000,
        )

    @pytest.mark.asyncio
    async def test_successful_account_creation(self, mock_dependencies, sample_request):
        """Test successful account creation."""
        with patch("src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"):
            result = await create_account_internal(
                request=sample_request,
                uploaded_document_urls=[],
                background_tasks=mock_dependencies["background_tasks"],
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=mock_dependencies["bigquery"],
            )

            assert isinstance(result, Account)
            assert result.account_name == "Test Account"
            assert result.organization_id == "org_123"
            assert result.industry == "Technology"
            assert result.status == "Active"

            # Verify firestore was called
            mock_dependencies["firestore"].create_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_organization_not_found(self, mock_dependencies, sample_request):
        """Test that missing organization raises 404."""
        # Mock Neo4j to return empty result (organization not found)
        mock_dependencies["neo4j"].execute_query.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await create_account_internal(
                request=sample_request,
                uploaded_document_urls=[],
                background_tasks=mock_dependencies["background_tasks"],
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=None,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_agency_organization_forbidden(
        self, mock_dependencies, sample_request
    ):
        """Test that agency organizations cannot create accounts."""
        # Mock Neo4j to return agency=True
        mock_dependencies["neo4j"].execute_query.return_value = [
            {"agency": True, "organization_name": "Test Agency Organization"}
        ]

        with pytest.raises(HTTPException) as exc_info:
            await create_account_internal(
                request=sample_request,
                uploaded_document_urls=[],
                background_tasks=mock_dependencies["background_tasks"],
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=None,
            )

        assert exc_info.value.status_code == 403
        assert "Agency organizations cannot create accounts" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_account_id_generation(self, mock_dependencies, sample_request):
        """Test that account ID is generated when not provided."""
        sample_request.account_id = None

        with patch("src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"):
            result = await create_account_internal(
                request=sample_request,
                uploaded_document_urls=[],
                background_tasks=mock_dependencies["background_tasks"],
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=None,
            )

            assert result.account_id is not None
            assert result.account_id.startswith("account_")

    @pytest.mark.asyncio
    async def test_uploaded_documents_passed_to_strategy(
        self, mock_dependencies, sample_request
    ):
        """Test that uploaded document URLs are passed to strategy generation."""
        uploaded_urls = ["gs://bucket/doc1.pdf", "gs://bucket/doc2.docx"]

        # Create a mock BackgroundTasks that tracks the added tasks
        mock_bg_tasks = MagicMock(spec=BackgroundTasks)
        added_tasks = []

        def track_task(func, *args, **kwargs):
            added_tasks.append((func, args, kwargs))

        mock_bg_tasks.add_task = MagicMock(side_effect=track_task)

        with patch(
            "src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"
        ) as mock_task:
            await create_account_internal(
                request=sample_request,
                uploaded_document_urls=uploaded_urls,
                background_tasks=mock_bg_tasks,
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=None,
            )

            # Verify background task was added with correct parameters
            mock_bg_tasks.add_task.assert_called_once()
            call_args = mock_bg_tasks.add_task.call_args

            # Check that the trigger_strategy_generation function was passed
            assert call_args[0][0] == mock_task

            # Check the keyword arguments
            kwargs = call_args[1]
            assert kwargs["uploaded_document_urls"] == uploaded_urls
            assert (
                kwargs["company_name"] == "Test Account"
            )  # Uses account_name from the request
            assert kwargs["industry"] == "Technology"

    @pytest.mark.asyncio
    async def test_firestore_failure_raises_500(
        self, mock_dependencies, sample_request
    ):
        """Test that Neo4j write failure raises 500 error."""
        # Mock Neo4j write to fail
        mock_dependencies["neo4j"].execute_write_query.side_effect = Exception(
            "Neo4j error"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_account_internal(
                request=sample_request,
                uploaded_document_urls=[],
                background_tasks=mock_dependencies["background_tasks"],
                user=mock_dependencies["user"],
                firestore=mock_dependencies["firestore"],
                storage=mock_dependencies["storage"],
                neo4j_service=mock_dependencies["neo4j"],
                bigquery_service=None,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to create account" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_notification_created_on_account_creation(
        self, mock_dependencies, sample_request
    ):
        """Test that a welcome notification is created when account is created."""
        # Mock firestore client for notification repository
        mock_firestore_client = MagicMock()
        mock_dependencies["firestore"].get_client.return_value = mock_firestore_client

        with patch("src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"):
            with patch(
                "src.kene_api.services.notification_service_v2.NotificationService"
            ) as mock_notification_service:
                with patch("src.kene_api.repositories.FirestoreNotificationRepository"):
                    # Setup mock notification service
                    mock_service_instance = AsyncMock()
                    mock_service_instance.create_notification.return_value = (
                        "notif_test_123"
                    )
                    mock_notification_service.return_value = mock_service_instance

                    # Also mock batch_create_user_statuses
                    mock_repo_instance = AsyncMock()
                    mock_repo_instance.batch_create_user_statuses = AsyncMock()

                    result = await create_account_internal(
                        request=sample_request,
                        uploaded_document_urls=[],
                        background_tasks=mock_dependencies["background_tasks"],
                        user=mock_dependencies["user"],
                        firestore=mock_dependencies["firestore"],
                        storage=mock_dependencies["storage"],
                        neo4j_service=mock_dependencies["neo4j"],
                        bigquery_service=None,
                    )

                    # Verify notification was created
                    mock_service_instance.create_notification.assert_called_once()
                    call_kwargs = (
                        mock_service_instance.create_notification.call_args.kwargs
                    )

                    assert call_kwargs["account_id"] == result.account_id
                    assert call_kwargs["description"] == "Configure your new account"
                    assert "account_name" in call_kwargs["data"]
                    assert call_kwargs["data"]["account_name"] == "Test Account"
