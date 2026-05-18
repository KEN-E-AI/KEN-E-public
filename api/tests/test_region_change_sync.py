"""Test region change holiday sync functionality."""

import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from src.kene_api.database import Neo4jService
from src.kene_api.bigquery import BigQueryService
from src.kene_api.routers.accounts import (
    update_account,
    _sync_holiday_activity_logs_for_account,
)
from src.kene_api.models.kene_models import AccountRequest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock = AsyncMock(spec=Neo4jService)
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_bigquery_service():
    """Create a mock BigQuery service."""
    mock = MagicMock(spec=BigQueryService)
    mock.health_check = MagicMock(return_value=True)
    return mock


class TestRegionChangeSync:
    """Test that changing regions properly syncs holiday activity logs."""

    @pytest.mark.asyncio
    async def test_region_change_us_to_au_removes_us_holidays(
        self, mock_neo4j_service, mock_bigquery_service
    ):
        """Test that changing from US to AU removes US-specific holidays."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        # Mock current account with US region
        mock_neo4j_service.execute_query.side_effect = [
            # First call: check if account exists
            [{"exists": True}],
            # Second call: get current account (for get_account)
            [
                {
                    "acc": {
                        "account_id": account_id,
                        "account_name": "Test Account",
                        "plan": "Professional",
                        "organization_id": "org_123",
                        "region": ["US"],
                        "status": "Active",
                        "websites": [],
                        "timezone": "America/New_York",
                        "data_region": "US",
                        "industry": "Tech",
                    }
                }
            ],
            # Third call: get existing logs (including US_PresidentDay)
            [
                {
                    "log_id": "log_us_presidents_day",
                    "description": "US_PresidentDay",
                    "start_date": date(2024, 2, 19).isoformat(),
                    "end_date": date(2024, 2, 19).isoformat(),
                    "has_metric_relationship": False,
                },
                {
                    "log_id": "log_us_memorial_day",
                    "description": "US_MemorialDay",
                    "start_date": date(2024, 5, 27).isoformat(),
                    "end_date": date(2024, 5, 27).isoformat(),
                    "has_metric_relationship": False,
                },
            ],
            # Fourth call: check activity exists for act_00
            [{"count": 1}],
            # Fifth call: count deletable logs
            [{"to_delete_count": 2}],
            # Sixth call: get updated account (after update)
            [
                {
                    "acc": {
                        "account_id": account_id,
                        "account_name": "Test Account",
                        "plan": "Professional",
                        "organization_id": "org_123",
                        "region": ["AU"],  # Updated region
                        "status": "Active",
                        "websites": [],
                        "timezone": "America/New_York",
                        "data_region": "US",
                        "industry": "Tech",
                    }
                }
            ],
        ]

        # Mock BigQuery returns AU holidays only
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "AU_AustraliaDay",
                "start_date": date(2024, 1, 26).isoformat(),
                "end_date": date(2024, 1, 26).isoformat(),
            },
            {
                "description": "AU_AnzacDay",
                "start_date": date(2024, 4, 25).isoformat(),
                "end_date": date(2024, 4, 25).isoformat(),
            },
        ]

        # Mock write operations
        mock_neo4j_service.execute_write_query.side_effect = [
            # First: update account
            {"properties_set": 1},
            # Second: create new AU logs
            {"nodes_created": 2},
            # Third: delete US logs
            {"nodes_deleted": 2},
        ]

        # Prepare update request
        update_request = AccountRequest(region=["AU"])

        # Execute the update with env var set
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            result = await update_account(
                account_id=account_id,
                request=update_request,
                db=mock_neo4j_service,
                bigquery=mock_bigquery_service,
            )

        # Verify account was updated
        assert result.account_id == account_id
        assert result.region == ["AU"]

        # Verify BigQuery was called with AU region
        mock_bigquery_service.query_holiday_activities.assert_called_once_with(
            "test-project", ["AU"]
        )

        # Verify deletion query was called with US holiday log IDs
        delete_calls = [
            call
            for call in mock_neo4j_service.execute_write_query.call_args_list
            if "log_ids" in call[0][1]
        ]
        assert len(delete_calls) == 1
        delete_params = delete_calls[0][0][1]
        assert "log_us_presidents_day" in delete_params["log_ids"]
        assert "log_us_memorial_day" in delete_params["log_ids"]

    @pytest.mark.asyncio
    async def test_region_change_au_to_us_adds_us_holidays(
        self, mock_neo4j_service, mock_bigquery_service
    ):
        """Test that changing from AU to US adds US-specific holidays back."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        # Mock current account with AU region
        mock_neo4j_service.execute_query.side_effect = [
            # First call: check if account exists
            [{"exists": True}],
            # Second call: get current account
            [
                {
                    "account_id": account_id,
                    "account_name": "Test Account",
                    "plan": "Professional",
                    "organization_id": "org_123",
                    "region": ["AU"],
                }
            ],
            # Third call: get existing logs (AU holidays)
            [
                {
                    "log_id": "log_au_australia_day",
                    "description": "AU_AustraliaDay",
                    "start_date": date(2024, 1, 26).isoformat(),
                    "end_date": date(2024, 1, 26).isoformat(),
                    "has_metric_relationship": False,
                },
                {
                    "log_id": "log_au_anzac_day",
                    "description": "AU_AnzacDay",
                    "start_date": date(2024, 4, 25).isoformat(),
                    "end_date": date(2024, 4, 25).isoformat(),
                    "has_metric_relationship": False,
                },
            ],
            # Fourth call: check activity exists for act_00
            [{"count": 1}],
            # Fifth call: count deletable logs
            [{"to_delete_count": 2}],
        ]

        # Mock BigQuery returns US holidays
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "US_PresidentDay",
                "start_date": date(2024, 2, 19).isoformat(),
                "end_date": date(2024, 2, 19).isoformat(),
            },
            {
                "description": "US_MemorialDay",
                "start_date": date(2024, 5, 27).isoformat(),
                "end_date": date(2024, 5, 27).isoformat(),
            },
        ]

        # Mock write operations
        mock_neo4j_service.execute_write_query.side_effect = [
            # First: update account
            {"properties_set": 1},
            # Second: create new US logs
            {"nodes_created": 2},
            # Third: delete AU logs
            {"nodes_deleted": 2},
        ]

        # Prepare update request
        update_request = AccountRequest(region=["US"])

        # Execute the update
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            result = await update_account(
                account_id=account_id,
                request=update_request,
                db=mock_neo4j_service,
                bigquery=mock_bigquery_service,
            )

        # Verify account was updated
        assert result.account_id == account_id
        assert result.region == ["US"]

        # Verify BigQuery was called with US region
        mock_bigquery_service.query_holiday_activities.assert_called_once_with(
            "test-project", ["US"]
        )

        # Verify creation of US holidays
        create_calls = [
            call
            for call in mock_neo4j_service.execute_write_query.call_args_list
            if "logs" in call[0][1]
        ]
        assert len(create_calls) == 1
        created_logs = create_calls[0][0][1]["logs"]
        descriptions = [log["description"] for log in created_logs]
        assert "US_PresidentDay" in descriptions
        assert "US_MemorialDay" in descriptions

        # Verify deletion of AU holidays
        delete_calls = [
            call
            for call in mock_neo4j_service.execute_write_query.call_args_list
            if "log_ids" in call[0][1]
        ]
        assert len(delete_calls) == 1
        delete_params = delete_calls[0][0][1]
        assert "log_au_australia_day" in delete_params["log_ids"]
        assert "log_au_anzac_day" in delete_params["log_ids"]

    @pytest.mark.asyncio
    async def test_protected_logs_not_deleted(
        self, mock_neo4j_service, mock_bigquery_service
    ):
        """Test that ActivityLogs with metric relationships are not deleted."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        # Mock current account with US region
        mock_neo4j_service.execute_query.side_effect = [
            # First call: check if account exists
            [{"exists": True}],
            # Second call: get current account
            [
                {
                    "account_id": account_id,
                    "account_name": "Test Account",
                    "plan": "Professional",
                    "organization_id": "org_123",
                    "region": ["US"],
                }
            ],
            # Third call: get existing logs with one protected
            [
                {
                    "log_id": "log_us_presidents_day",
                    "description": "US_PresidentDay",
                    "start_date": date(2024, 2, 19).isoformat(),
                    "end_date": date(2024, 2, 19).isoformat(),
                    "has_metric_relationship": True,  # This one is protected
                },
                {
                    "log_id": "log_us_memorial_day",
                    "description": "US_MemorialDay",
                    "start_date": date(2024, 5, 27).isoformat(),
                    "end_date": date(2024, 5, 27).isoformat(),
                    "has_metric_relationship": False,
                },
            ],
            # Fourth call: check activity exists for act_00
            [{"count": 1}],
            # Fifth call: count deletable logs (only unprotected ones)
            [{"to_delete_count": 1}],
        ]

        # Mock BigQuery returns AU holidays
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "AU_AustraliaDay",
                "start_date": date(2024, 1, 26).isoformat(),
                "end_date": date(2024, 1, 26).isoformat(),
            }
        ]

        # Mock write operations
        mock_neo4j_service.execute_write_query.side_effect = [
            # First: update account
            {"properties_set": 1},
            # Second: create new AU logs
            {"nodes_created": 1},
            # Third: delete only unprotected US logs
            {"nodes_deleted": 1},
        ]

        # Prepare update request
        update_request = AccountRequest(region=["AU"])

        # Execute the update
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            result = await update_account(
                account_id=account_id,
                request=update_request,
                db=mock_neo4j_service,
                bigquery=mock_bigquery_service,
            )

        # Verify deletion query was called only with unprotected log ID
        delete_calls = [
            call
            for call in mock_neo4j_service.execute_write_query.call_args_list
            if "log_ids" in call[0][1]
        ]
        assert len(delete_calls) == 1
        delete_params = delete_calls[0][0][1]
        assert "log_us_memorial_day" in delete_params["log_ids"]
        assert (
            "log_us_presidents_day" not in delete_params["log_ids"]
        )  # Protected, not deleted


@pytest.mark.asyncio
async def test_direct_sync_function_deletes_correctly(
    mock_neo4j_service, mock_bigquery_service
):
    """Test the sync function directly to verify deletion logic."""
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Mock Neo4j responses
    mock_neo4j_service.execute_query.side_effect = [
        # Validate account
        [{"regions": ["AU"]}],
        # Get existing logs
        [
            {
                "log_id": "log_us_specific",
                "description": "US_PresidentDay",
                "start_date": "2024-02-19",
                "end_date": "2024-02-19",
                "has_metric_relationship": False,
            }
        ],
        # Check activity exists
        [{"exists": True}],
        # Count deletable
        [{"to_delete_count": 1}],
    ]

    # Mock BigQuery returns empty (no AU holidays match)
    mock_bigquery_service.query_holiday_activities.return_value = []

    # Mock delete operation
    mock_neo4j_service.execute_write_query.return_value = {"nodes_deleted": 1}

    # Execute sync
    with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _sync_holiday_activity_logs_for_account(
            mock_neo4j_service, mock_bigquery_service, account_id, "org_123", ["AU"]
        )

    # Verify the result
    assert result["deleted"] == 1
    assert result["created"] == 0
    assert "log_us_specific" in result["operations"]["to_delete"]
