"""Test region change holiday sync functionality."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.auth import UserContext
from src.kene_api.bigquery import BigQueryService
from src.kene_api.database import Neo4jService
from src.kene_api.models.kene_models import AccountRequest
from src.kene_api.routers.accounts import (
    _sync_holiday_activity_logs_for_account,
    update_account,
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


@pytest.fixture
def super_admin_user():
    """A super-admin UserContext that bypasses org/account access checks."""
    return UserContext(
        user_id="user_admin",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _account_record(account_id: str, region: list[str]) -> dict:
    """Build an Account node record as returned by Neo4j."""
    return {
        "acc": {
            "account_id": account_id,
            "account_name": "Test Account",
            "plan": "Professional",
            "organization_id": "org_123",
            "region": region,
            "status": "Active",
            "websites": [],
            "timezone": "America/New_York",
            "data_region": "US",
            "industry": "Tech",
        }
    }


class TestRegionChangeSync:
    """Test that changing regions properly syncs holiday activity logs."""

    @pytest.mark.asyncio
    async def test_region_change_us_to_au_removes_us_holidays(
        self, mock_neo4j_service, mock_bigquery_service, super_admin_user
    ):
        """Test that changing from US to AU removes US-specific holidays."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        # Region the account currently reports. Flipped to AU once the update
        # write has executed so the final get_account returns the new region.
        state = {"region": ["US"]}

        existing_logs = [
            {
                "log_id": "log_us_presidents_day",
                "description": "US_PresidentDay",
                "start_date": date(2024, 2, 19).isoformat(),
                "end_date": date(2024, 2, 19).isoformat(),
                "activity_id": "act_00_us",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_us_memorial_day",
                "description": "US_MemorialDay",
                "start_date": date(2024, 5, 27).isoformat(),
                "end_date": date(2024, 5, 27).isoformat(),
                "activity_id": "act_00_us",
                "has_metric_relationship": False,
            },
        ]

        async def mock_execute_query(query, params):
            if "count(acc) > 0 as exists" in query:
                return [{"exists": True}]
            if "org:Organization" in query and "organization_id" in query:
                return [{"organization_id": "org_123"}]
            if "RETURN acc" in query:
                return [_account_record(account_id, state["region"])]
            if "LOGGED" in query and "ActivityLog" in query:
                return existing_logs
            return []

        deleted_ids_seen = []

        async def mock_execute_write_query(query, params):
            if "SET" in query and "acc.region" in query:
                state["region"] = ["AU"]
                return {"properties_set": 1}
            if "CREATE (al:ActivityLog" in query:
                return {"nodes_created": len(params.get("logs", []))}
            if "DETACH DELETE al" in query:
                log_ids = params.get("log_ids", [])
                deleted_ids_seen.extend(log_ids)
                return {"nodes_deleted": len(log_ids)}
            return {}

        mock_neo4j_service.execute_query = mock_execute_query
        mock_neo4j_service.execute_write_query = mock_execute_write_query

        # Mock BigQuery returns AU holidays only
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "AU_AustraliaDay",
                "start_date": date(2024, 1, 26).isoformat(),
                "end_date": date(2024, 1, 26).isoformat(),
                "region": "AU",
            },
            {
                "description": "AU_AnzacDay",
                "start_date": date(2024, 4, 25).isoformat(),
                "end_date": date(2024, 4, 25).isoformat(),
                "region": "AU",
            },
        ]

        update_request = AccountRequest(region=["AU"])

        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            result = await update_account(
                account_id=account_id,
                request=update_request,
                user=super_admin_user,
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

        # Verify the US holiday logs were passed to the delete query
        assert "log_us_presidents_day" in deleted_ids_seen
        assert "log_us_memorial_day" in deleted_ids_seen

    @pytest.mark.asyncio
    async def test_region_change_au_to_us_adds_us_holidays(
        self, mock_neo4j_service, mock_bigquery_service, super_admin_user
    ):
        """Test that changing from AU to US adds US-specific holidays back."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        state = {"region": ["AU"]}

        existing_logs = [
            {
                "log_id": "log_au_australia_day",
                "description": "AU_AustraliaDay",
                "start_date": date(2024, 1, 26).isoformat(),
                "end_date": date(2024, 1, 26).isoformat(),
                "activity_id": "act_00_au",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_au_anzac_day",
                "description": "AU_AnzacDay",
                "start_date": date(2024, 4, 25).isoformat(),
                "end_date": date(2024, 4, 25).isoformat(),
                "activity_id": "act_00_au",
                "has_metric_relationship": False,
            },
        ]

        created_logs_seen = []
        deleted_ids_seen = []

        async def mock_execute_query(query, params):
            if "count(acc) > 0 as exists" in query:
                return [{"exists": True}]
            if "org:Organization" in query and "organization_id" in query:
                return [{"organization_id": "org_123"}]
            if "RETURN acc" in query:
                return [_account_record(account_id, state["region"])]
            if "LOGGED" in query and "ActivityLog" in query:
                return existing_logs
            return []

        async def mock_execute_write_query(query, params):
            if "SET" in query and "acc.region" in query:
                state["region"] = ["US"]
                return {"properties_set": 1}
            if "CREATE (al:ActivityLog" in query:
                logs = params.get("logs", [])
                created_logs_seen.extend(logs)
                return {"nodes_created": len(logs)}
            if "DETACH DELETE al" in query:
                log_ids = params.get("log_ids", [])
                deleted_ids_seen.extend(log_ids)
                return {"nodes_deleted": len(log_ids)}
            return {}

        mock_neo4j_service.execute_query = mock_execute_query
        mock_neo4j_service.execute_write_query = mock_execute_write_query

        # Mock BigQuery returns US holidays
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "US_PresidentDay",
                "start_date": date(2024, 2, 19).isoformat(),
                "end_date": date(2024, 2, 19).isoformat(),
                "region": "US",
            },
            {
                "description": "US_MemorialDay",
                "start_date": date(2024, 5, 27).isoformat(),
                "end_date": date(2024, 5, 27).isoformat(),
                "region": "US",
            },
        ]

        update_request = AccountRequest(region=["US"])

        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            result = await update_account(
                account_id=account_id,
                request=update_request,
                user=super_admin_user,
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
        descriptions = [log["description"] for log in created_logs_seen]
        assert "US_PresidentDay" in descriptions
        assert "US_MemorialDay" in descriptions

        # Verify deletion of AU holidays
        assert "log_au_australia_day" in deleted_ids_seen
        assert "log_au_anzac_day" in deleted_ids_seen

    @pytest.mark.asyncio
    async def test_protected_logs_not_deleted(
        self, mock_neo4j_service, mock_bigquery_service, super_admin_user
    ):
        """Test that ActivityLogs with metric relationships are not deleted."""
        account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

        state = {"region": ["US"]}

        existing_logs = [
            {
                "log_id": "log_us_presidents_day",
                "description": "US_PresidentDay",
                "start_date": date(2024, 2, 19).isoformat(),
                "end_date": date(2024, 2, 19).isoformat(),
                "activity_id": "act_00_us",
                "has_metric_relationship": True,  # This one is protected
            },
            {
                "log_id": "log_us_memorial_day",
                "description": "US_MemorialDay",
                "start_date": date(2024, 5, 27).isoformat(),
                "end_date": date(2024, 5, 27).isoformat(),
                "activity_id": "act_00_us",
                "has_metric_relationship": False,
            },
        ]

        deleted_ids_seen = []

        async def mock_execute_query(query, params):
            if "count(acc) > 0 as exists" in query:
                return [{"exists": True}]
            if "org:Organization" in query and "organization_id" in query:
                return [{"organization_id": "org_123"}]
            if "RETURN acc" in query:
                return [_account_record(account_id, state["region"])]
            if "LOGGED" in query and "ActivityLog" in query:
                return existing_logs
            return []

        async def mock_execute_write_query(query, params):
            if "SET" in query and "acc.region" in query:
                state["region"] = ["AU"]
                return {"properties_set": 1}
            if "CREATE (al:ActivityLog" in query:
                return {"nodes_created": len(params.get("logs", []))}
            if "DETACH DELETE al" in query:
                log_ids = params.get("log_ids", [])
                deleted_ids_seen.extend(log_ids)
                return {"nodes_deleted": len(log_ids)}
            return {}

        mock_neo4j_service.execute_query = mock_execute_query
        mock_neo4j_service.execute_write_query = mock_execute_write_query

        # Mock BigQuery returns AU holidays
        mock_bigquery_service.query_holiday_activities.return_value = [
            {
                "description": "AU_AustraliaDay",
                "start_date": date(2024, 1, 26).isoformat(),
                "end_date": date(2024, 1, 26).isoformat(),
                "region": "AU",
            }
        ]

        update_request = AccountRequest(region=["AU"])

        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            await update_account(
                account_id=account_id,
                request=update_request,
                user=super_admin_user,
                db=mock_neo4j_service,
                bigquery=mock_bigquery_service,
            )

        # The protected log must never reach the delete query; only the
        # unprotected one should be passed for deletion.
        assert "log_us_memorial_day" in deleted_ids_seen
        assert "log_us_presidents_day" not in deleted_ids_seen


@pytest.mark.asyncio
async def test_direct_sync_function_deletes_correctly(
    mock_neo4j_service, mock_bigquery_service
):
    """Test the sync function directly to verify deletion logic."""
    account_id = "acc_af08bd32c4f540da96f1c7d9642f8009"

    # Mock Neo4j responses. _sync_holiday_activity_logs_for_account calls
    # _fetch_existing_activity_logs (one query) then _execute_sync_operations.
    mock_neo4j_service.execute_query.side_effect = [
        # Get existing logs
        [
            {
                "log_id": "log_us_specific",
                "description": "US_PresidentDay",
                "start_date": "2024-02-19",
                "end_date": "2024-02-19",
                "activity_id": "act_00_us",
                "has_metric_relationship": False,
            }
        ],
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
