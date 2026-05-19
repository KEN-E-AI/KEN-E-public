"""Unit tests for form parsing service."""

import json

import pytest
from src.kene_api.models.kene_models import AccountRequest
from src.kene_api.services.form_parsing_service import (
    parse_account_form_data,
    parse_json_field,
)


class TestParseJsonField:
    """Test the parse_json_field function."""

    def test_parse_valid_json_array(self):
        """Test parsing a valid JSON array string."""
        result = parse_json_field('["item1", "item2"]', "test_field")
        assert result == ["item1", "item2"]

    def test_parse_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = parse_json_field("", "test_field")
        assert result is None

    def test_parse_none_returns_none(self):
        """Test that None input returns None."""
        result = parse_json_field(None, "test_field")
        assert result is None

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON in test_field"):
            parse_json_field("not json", "test_field")

    def test_parse_non_array_json_raises_error(self):
        """Test that non-array JSON raises ValueError."""
        with pytest.raises(ValueError, match="test_field must be a JSON array"):
            parse_json_field('{"key": "value"}', "test_field")

    def test_parse_complex_array(self):
        """Test parsing array with complex objects."""
        input_json = json.dumps(
            [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]
        )
        result = parse_json_field(input_json, "test_field")
        assert result == [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]


class TestParseAccountFormData:
    """Test the parse_account_form_data function."""

    def test_parse_required_fields_only(self):
        """Test parsing with only required fields."""
        result = parse_account_form_data(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites='["https://example.com"]',
            timezone="America/New_York",
        )

        assert isinstance(result, AccountRequest)
        assert result.account_name == "Test Account"
        assert result.organization_id == "org_123"
        assert result.industry == "Technology"
        assert result.status == "Active"
        assert result.websites == ["https://example.com"]
        assert result.timezone == "America/New_York"
        assert result.account_id is None
        assert result.data_region is None
        assert result.region is None
        assert result.marketing_channels == []
        assert result.product_integrations == []

    def test_parse_all_fields(self):
        """Test parsing with all fields provided."""
        result = parse_account_form_data(
            account_name="Full Account",
            organization_id="org_456",
            industry="Healthcare",
            status="Pending",
            websites='["https://site1.com", "https://site2.com"]',
            timezone="Europe/London",
            account_id="acc_789",
            data_region="EU",
            region='["Europe", "Asia"]',
            marketing_channels='["SEO", "PPC"]',
            product_integrations='["Google Analytics", "Salesforce"]',
            estimated_annual_ad_budget=50000,
        )

        assert result.account_name == "Full Account"
        assert result.account_id == "acc_789"
        assert result.data_region == "EU"
        assert result.region == ["Europe", "Asia"]
        assert result.marketing_channels == ["SEO", "PPC"]
        assert result.product_integrations == ["Google Analytics", "Salesforce"]
        assert result.estimated_annual_ad_budget == 50000

    def test_parse_empty_optional_arrays(self):
        """Test that empty optional arrays default to empty lists."""
        result = parse_account_form_data(
            account_name="Test",
            organization_id="org_1",
            industry="Tech",
            status="Active",
            websites="[]",
            timezone="UTC",
            marketing_channels="[]",
            product_integrations="[]",
        )

        assert result.websites == []
        assert result.marketing_channels == []
        assert result.product_integrations == []

    def test_parse_null_websites_defaults_to_empty_list(self):
        """Test that null websites field defaults to empty list."""
        result = parse_account_form_data(
            account_name="Test",
            organization_id="org_1",
            industry="Tech",
            status="Active",
            websites=None,
            timezone="UTC",
        )

        assert result.websites == []

    def test_parse_invalid_json_in_field_raises_error(self):
        """Test that invalid JSON in any field raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON in websites"):
            parse_account_form_data(
                account_name="Test",
                organization_id="org_1",
                industry="Tech",
                status="Active",
                websites="not json",
                timezone="UTC",
            )

    def test_parse_preserves_data_types(self):
        """Test that data types are preserved correctly."""
        result = parse_account_form_data(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites='["https://example.com"]',
            timezone="America/New_York",
            estimated_annual_ad_budget=0,  # Test zero value
        )

        assert result.estimated_annual_ad_budget == 0
        assert result.estimated_annual_ad_budget is not None
