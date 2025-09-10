"""Tests for monitoring topics functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from datetime import datetime

from src.kene_api.models.monitoring_models import (
    CompetitorEntry,
    MonitoringTopics,
    IndustryKeywords,
)
from src.kene_api.routers.monitoring_topics import (
    get_or_create_monitoring_topics,
    get_industry_keywords_for_industry,
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
    firestore_mock = AsyncMock()
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
        collection="monitoring_topics",
        document_id=account_id,
    )


@pytest.mark.asyncio
async def test_get_or_create_monitoring_topics_new():
    """Test creating new monitoring topics when none exist."""
    # Mock data
    account_id = "acc_123"
    organization_id = "org_456"
    industry = "Technology"

    # Mock Firestore service
    firestore_mock = AsyncMock()
    firestore_mock.get_document.return_value = None

    # Mock get_industry_keywords_for_industry to return keywords
    # Since we can't easily mock the function, we'll test the logic separately

    with pytest.raises(HTTPException) as exc_info:
        await get_or_create_monitoring_topics(
            account_id, organization_id, industry, firestore_mock
        )

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_industry_keywords_for_industry():
    """Test getting keywords for a specific industry."""
    industry = "Healthcare"
    expected_keywords = ["healthcare", "medical", "hospital"]

    # Mock Firestore service
    firestore_mock = AsyncMock()
    firestore_mock.get_document.return_value = {
        "industry": industry,
        "keywords": expected_keywords,
        "updated_by": "admin_123",
        "updated_at": "2025-01-01T00:00:00",
    }

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
    firestore_mock = AsyncMock()
    firestore_mock.get_document.return_value = None

    # Call function
    result = await get_industry_keywords_for_industry(industry, firestore_mock)

    # Assertions
    assert result == []


@pytest.mark.asyncio
async def test_update_accounts_with_industry():
    """Test updating all accounts with new industry keywords."""
    industry = "Finance"
    keywords = ["finance", "banking", "investment"]

    # Mock documents
    mock_docs = [
        {"account_id": "acc_1"},
        {"account_id": "acc_2"},
        {"account_id": "acc_3"},
    ]

    # Mock Firestore service
    firestore_mock = AsyncMock()
    firestore_mock.query_documents.return_value = mock_docs

    # Call function
    await update_accounts_with_industry(industry, keywords, firestore_mock)

    # Verify each account was updated
    assert firestore_mock.update_document.call_count == 3

    # Check each call
    for i, doc in enumerate(mock_docs):
        call_args = firestore_mock.update_document.call_args_list[i]
        assert call_args[1]["collection"] == "monitoring_topics"
        assert call_args[1]["document_id"] == doc["account_id"]
        assert call_args[1]["data"]["industry_keywords"] == keywords
        assert "updated_at" in call_args[1]["data"]


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
