"""Tests for monitoring topics functionality."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.models.monitoring_models import (
    CompetitorEntry,
    IndustryKeywords,
    MonitoringTopics,
)
from src.kene_api.routers.monitoring_topics import (
    get_industry_keywords_for_industry,
    get_or_create_monitoring_topics,
    update_accounts_with_industry,
)


@pytest.mark.asyncio
async def test_get_or_create_monitoring_topics_existing():
    """Test getting existing monitoring topics."""
    # Mock data
    account_id = "acc_123"
    organization_id = "org_456"
    industry = "Manufacturing"

    existing_data = {
        "account_id": account_id,
        "organization_id": organization_id,
        "industry_keywords": ["manufacturing", "production"],
        "company_keywords": ["acme", "widgets"],
        "customer_keywords": ["b2b", "enterprise"],
        "competitor_entries": [],
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }

    # Mock Firestore service
    firestore_mock = MagicMock()
    firestore_mock.get_document.return_value = existing_data

    # Call function
    result = await get_or_create_monitoring_topics(
        account_id, organization_id, industry, firestore_mock
    )

    # Assertions
    assert isinstance(result, MonitoringTopics)
    assert result.account_id == account_id
    assert result.organization_id == organization_id
    assert result.company_keywords == ["acme", "widgets"]
    assert result.customer_keywords == ["b2b", "enterprise"]

    # Verify Firestore was called correctly
    firestore_mock.get_document.assert_called_once_with(
        collection=f"accounts/{account_id}/monitoring_topics",
        document_id="default",
    )


@pytest.mark.asyncio
async def test_get_or_create_monitoring_topics_new():
    """Test creating new monitoring topics when none exist."""
    account_id = "acc_123"
    organization_id = "org_456"
    industry = "Technology"

    firestore_mock = MagicMock()
    firestore_mock.get_document.return_value = None

    with patch(
        "src.kene_api.routers.monitoring_topics._cache_service"
    ) as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()
        result = await get_or_create_monitoring_topics(
            account_id, organization_id, industry, firestore_mock
        )

    assert isinstance(result, MonitoringTopics)
    assert result.account_id == account_id
    assert result.organization_id == organization_id
    # Verify create_document was called at the Shape B path
    firestore_mock.create_document.assert_called_once_with(
        collection=f"accounts/{account_id}/monitoring_topics",
        document_id="default",
        data=result.model_dump(),
    )


@pytest.mark.asyncio
async def test_get_industry_keywords_for_industry():
    """Test getting keywords for a specific industry."""
    industry = "Healthcare"
    expected_keywords = ["healthcare", "medical", "hospital"]

    # Mock Firestore service
    firestore_mock = MagicMock()
    firestore_mock.get_document.return_value = {
        "industry": industry,
        "keywords": expected_keywords,
        "updated_by": "admin_123",
        "updated_at": "2025-01-01T00:00:00",
    }

    # Patch the module-level cache so CacheService.set() doesn't call redis.setex
    with patch(
        "src.kene_api.routers.monitoring_topics._cache_service"
    ) as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set = MagicMock()
        # Call function
        result = await get_industry_keywords_for_industry(industry, firestore_mock)

    # Assertions
    assert result == expected_keywords

    # Verify Firestore was called correctly
    firestore_mock.get_document.assert_called_once_with(
        collection="industry_keywords",
        document_id="healthcare",
    )


@pytest.mark.asyncio
async def test_get_industry_keywords_for_industry_not_found():
    """Test getting keywords when industry has no defined keywords."""
    industry = "Unknown Industry"

    # Mock Firestore service
    firestore_mock = MagicMock()
    firestore_mock.get_document.return_value = None

    # Call function
    result = await get_industry_keywords_for_industry(industry, firestore_mock)

    # Assertions
    assert result == []


@pytest.mark.asyncio
async def test_update_accounts_with_industry():
    """Test updating all accounts with new industry keywords via collection-group query.

    Verifies that account_id is derived from the document path (not the payload field),
    per DM-PRD-04 §8 correctness requirement.
    """
    industry = "Finance"
    keywords = ["finance", "banking", "investment"]
    account_ids = ["acc_1", "acc_2", "acc_3"]

    # Build mock DocumentSnapshot objects whose .reference.parent.parent.id
    # returns the expected account_id (path-derived, not payload-derived).
    def make_doc_snap(account_id: str) -> MagicMock:
        doc_ref = MagicMock()
        subcollection_ref = MagicMock()
        account_doc_ref = MagicMock()
        account_doc_ref.id = account_id
        subcollection_ref.parent = account_doc_ref
        doc_ref.parent = subcollection_ref
        snap = MagicMock()
        snap.id = "default"
        snap.reference = doc_ref
        return snap

    mock_snaps = [make_doc_snap(aid) for aid in account_ids]

    # Mock the raw Firestore client returned by firestore.get_client()
    mock_db = MagicMock()
    mock_db.collection_group.return_value.stream.return_value = iter(mock_snaps)

    # Mock Firestore service
    firestore_mock = MagicMock()
    firestore_mock.get_client.return_value = mock_db

    # Call function
    await update_accounts_with_industry(industry, keywords, firestore_mock)

    # Verify collection_group was called (not query_documents)
    mock_db.collection_group.assert_called_once_with("monitoring_topics")
    assert not firestore_mock.query_documents.called

    # Verify each account was updated at the subcollection path (not a payload-derived path)
    assert firestore_mock.update_document.call_count == 3
    for i, account_id in enumerate(account_ids):
        call_args = firestore_mock.update_document.call_args_list[i]
        assert call_args[1]["collection"] == f"accounts/{account_id}/monitoring_topics"
        assert call_args[1]["document_id"] == "default"
        assert call_args[1]["data"]["industry_keywords"] == keywords
        assert "updated_at" in call_args[1]["data"]


@pytest.mark.asyncio
async def test_update_accounts_with_industry_skips_legacy_root_docs():
    """Legacy root-level docs (parent.parent is None) must be skipped during the
    DM-23 → DM-28 window to avoid writing to wrong paths."""
    industry = "Finance"
    keywords = ["finance", "banking"]

    # Build a legacy root-level snap: reference.parent exists but parent.parent is None
    legacy_snap = MagicMock()
    legacy_snap.id = "some_account_id"
    subcollection_ref = MagicMock()
    subcollection_ref.parent = None  # no parent — root-level collection
    legacy_snap.reference = MagicMock()
    legacy_snap.reference.parent = subcollection_ref

    mock_db = MagicMock()
    mock_db.collection_group.return_value.stream.return_value = iter([legacy_snap])

    firestore_mock = MagicMock()
    firestore_mock.get_client.return_value = mock_db

    await update_accounts_with_industry(industry, keywords, firestore_mock)

    # No writes should have happened
    firestore_mock.update_document.assert_not_called()


def test_competitor_entry_model():
    """Test CompetitorEntry model validation."""
    # Valid competitor
    competitor = CompetitorEntry(
        name="Acme Corp",
        website="https://acmecorp.com",
        keywords=["acme", "competitor"],
    )
    assert competitor.name == "Acme Corp"
    assert competitor.website == "https://acmecorp.com"
    assert competitor.keywords == ["acme", "competitor"]

    # Competitor without website
    competitor2 = CompetitorEntry(name="Beta Inc", keywords=["beta"])
    assert competitor2.name == "Beta Inc"
    assert competitor2.website is None
    assert competitor2.keywords == ["beta"]


def test_monitoring_topics_model():
    """Test MonitoringTopics model validation."""
    now = datetime.utcnow().isoformat()

    topics = MonitoringTopics(
        account_id="acc_123",
        organization_id="org_456",
        industry_keywords=["tech", "software"],
        company_keywords=["mycompany"],
        customer_keywords=["enterprise", "b2b"],
        competitor_entries=[
            {
                "name": "Competitor A",
                "website": "https://competitor-a.com",
                "keywords": ["comp-a"],
            }
        ],
        created_at=now,
        updated_at=now,
    )

    assert topics.account_id == "acc_123"
    assert topics.organization_id == "org_456"
    assert len(topics.industry_keywords) == 2
    assert len(topics.competitor_entries) == 1
    assert topics.competitor_entries[0].name == "Competitor A"


def test_industry_keywords_model():
    """Test IndustryKeywords model validation."""
    keywords = IndustryKeywords(
        industry="Retail",
        keywords=["retail", "shopping", "ecommerce"],
        updated_by="admin_user",
        updated_at=datetime.utcnow().isoformat(),
    )

    assert keywords.industry == "Retail"
    assert len(keywords.keywords) == 3
    assert keywords.updated_by == "admin_user"
    assert keywords.updated_at is not None
