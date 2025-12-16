"""Unit tests for monitoring models validation."""

import pytest
from pydantic import ValidationError

from src.kene_api.models.monitoring_models import (
    CompetitorEntry,
    CustomerProfileEntry,
)


class TestCompetitorEntry:
    """Test CompetitorEntry validation."""

    def test_valid_with_node_id(self):
        """Test valid competitor entry with node_id."""
        entry = CompetitorEntry(node_id="comp_123", keywords=["keyword1"])
        assert entry.node_id == "comp_123"
        assert entry.keywords == ["keyword1"]

    def test_valid_with_name(self):
        """Test valid competitor entry with legacy name."""
        entry = CompetitorEntry(name="Competitor Inc", keywords=["keyword1"])
        assert entry.name == "Competitor Inc"
        assert entry.keywords == ["keyword1"]

    def test_valid_with_both_node_id_and_name(self):
        """Test valid competitor entry with both node_id and name."""
        entry = CompetitorEntry(
            node_id="comp_123", name="Competitor Inc", keywords=["keyword1"]
        )
        assert entry.node_id == "comp_123"
        assert entry.name == "Competitor Inc"
        assert entry.keywords == ["keyword1"]

    def test_invalid_without_identifier(self):
        """Test that entry without node_id or name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CompetitorEntry(keywords=["keyword1"])

        assert "Either node_id or name must be provided" in str(exc_info.value)

    def test_valid_with_website(self):
        """Test valid competitor entry with website."""
        entry = CompetitorEntry(
            node_id="comp_123",
            website="https://example.com",
            keywords=["keyword1"],
        )
        assert entry.website == "https://example.com"

    def test_invalid_website_format(self):
        """Test that invalid website format raises ValidationError."""
        with pytest.raises(ValidationError):
            CompetitorEntry(
                node_id="comp_123",
                website="not-a-url",
                keywords=["keyword1"],
            )

    def test_empty_keywords_list_allowed(self):
        """Test that empty keywords list is allowed."""
        entry = CompetitorEntry(node_id="comp_123", keywords=[])
        assert entry.keywords == []


class TestCustomerProfileEntry:
    """Test CustomerProfileEntry validation."""

    def test_valid_with_node_id(self):
        """Test valid customer profile entry with node_id."""
        entry = CustomerProfileEntry(node_id="prof_123", keywords=["keyword1"])
        assert entry.node_id == "prof_123"
        assert entry.keywords == ["keyword1"]

    def test_valid_with_name(self):
        """Test valid customer profile entry with legacy name."""
        entry = CustomerProfileEntry(name="Marketing Mary", keywords=["keyword1"])
        assert entry.name == "Marketing Mary"
        assert entry.keywords == ["keyword1"]

    def test_valid_with_both_node_id_and_name(self):
        """Test valid customer profile entry with both node_id and name."""
        entry = CustomerProfileEntry(
            node_id="prof_123", name="Marketing Mary", keywords=["keyword1"]
        )
        assert entry.node_id == "prof_123"
        assert entry.name == "Marketing Mary"
        assert entry.keywords == ["keyword1"]

    def test_invalid_without_identifier(self):
        """Test that entry without node_id or name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CustomerProfileEntry(keywords=["keyword1"])

        assert "Either node_id or name must be provided" in str(exc_info.value)

    def test_empty_keywords_list_allowed(self):
        """Test that empty keywords list is allowed."""
        entry = CustomerProfileEntry(node_id="prof_123", keywords=[])
        assert entry.keywords == []

    def test_multiple_keywords(self):
        """Test customer profile entry with multiple keywords."""
        entry = CustomerProfileEntry(
            node_id="prof_123",
            keywords=["keyword1", "keyword2", "keyword3"],
        )
        assert len(entry.keywords) == 3
        assert "keyword2" in entry.keywords
