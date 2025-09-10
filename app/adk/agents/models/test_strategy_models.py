"""
Tests for Pydantic strategy models.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from .strategy_models import (
    StrategyParameters,
    StrategyResponse,
    parse_strategy_query,
)


class TestStrategyParameters:
    """Test the StrategyParameters model validation."""

    def test_valid_parameters(self):
        """Test creation with valid parameters."""
        params = StrategyParameters(
            company_name="Acme Corp",
            industry="Technology",
            websites="https://acme.com,https://blog.acme.com",
            customer_regions="North America,Europe,Asia",
            account_id="acc_123",
            user_id="usr_456",
            annual_ad_budget=100000.0,
            project_id="test-project",
            uploaded_documents=["gs://bucket/doc1.pdf", "gs://bucket/doc2.pdf"],
        )

        assert params.company_name == "Acme Corp"
        assert params.industry == "Technology"
        assert params.websites == "https://acme.com,https://blog.acme.com"
        assert params.customer_regions == "North America,Europe,Asia"
        assert params.account_id == "acc_123"
        assert params.user_id == "usr_456"
        assert params.annual_ad_budget == 100000.0
        assert params.project_id == "test-project"
        assert len(params.uploaded_documents) == 2

    def test_minimal_required_parameters(self):
        """Test creation with only required parameters."""
        params = StrategyParameters(
            company_name="MinCorp",
            industry="Retail",
            account_id="acc_min",
            user_id="usr_min",
        )

        assert params.company_name == "MinCorp"
        assert params.industry == "Retail"
        assert params.account_id == "acc_min"
        assert params.user_id == "usr_min"
        assert params.websites == ""
        assert params.customer_regions == ""
        assert params.annual_ad_budget == 0.0
        assert params.uploaded_documents == []

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            StrategyParameters(
                industry="Tech",
                account_id="acc_123",
                user_id="usr_456",
            )
        errors = exc.value.errors()
        assert any(e["loc"] == ("company_name",) for e in errors)

    def test_empty_string_validation(self):
        """Test that empty strings for required fields are rejected."""
        with pytest.raises(ValidationError) as exc:
            StrategyParameters(
                company_name="",  # Empty string should fail min_length=1
                industry="Tech",
                account_id="acc_123",
                user_id="usr_456",
            )
        errors = exc.value.errors()
        assert any(e["type"] == "string_too_short" for e in errors)

    def test_budget_parsing_from_string(self):
        """Test budget parsing from various string formats."""
        # Test with dollar sign and commas
        params = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            annual_ad_budget="$1,234,567.89",
        )
        assert params.annual_ad_budget == 1234567.89

        # Test with just number string
        params2 = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            annual_ad_budget="50000",
        )
        assert params2.annual_ad_budget == 50000.0

        # Test with empty string
        params3 = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            annual_ad_budget="",
        )
        assert params3.annual_ad_budget == 0.0

    def test_budget_validation(self):
        """Test that negative budgets are rejected."""
        with pytest.raises(ValidationError) as exc:
            StrategyParameters(
                company_name="Corp",
                industry="Tech",
                account_id="acc",
                user_id="usr",
                annual_ad_budget=-1000.0,
            )
        errors = exc.value.errors()
        assert any(e["type"] == "greater_than_equal" for e in errors)

    def test_project_id_default(self):
        """Test default project ID from environment."""
        # The validator only runs when project_id is not provided or is None
        # When not explicitly set, it defaults to None first, then the validator sets it
        with patch.dict(
            os.environ, {"VERTEX_AI_PROJECT_ID": "env-project"}, clear=True
        ):
            params = StrategyParameters(
                company_name="Corp",
                industry="Tech",
                account_id="acc",
                user_id="usr",
                project_id=None,  # Explicitly pass None to trigger validator
            )
            assert params.project_id == "env-project"

        # Test fallback to ken-e-dev when env var not set
        with patch.dict(os.environ, {}, clear=True):
            params2 = StrategyParameters(
                company_name="Corp",
                industry="Tech",
                account_id="acc",
                user_id="usr",
                project_id=None,  # Explicitly pass None to trigger validator
            )
            assert params2.project_id == "ken-e-dev"

    def test_uploaded_documents_parsing(self):
        """Test parsing of uploaded documents from various formats."""
        # Test with list
        params = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            uploaded_documents=["doc1.pdf", "doc2.pdf"],
        )
        assert params.uploaded_documents == ["doc1.pdf", "doc2.pdf"]

        # Test with comma-separated string
        params2 = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            uploaded_documents="doc1.pdf,doc2.pdf,doc3.pdf",
        )
        assert params2.uploaded_documents == ["doc1.pdf", "doc2.pdf", "doc3.pdf"]

        # Test with empty string
        params3 = StrategyParameters(
            company_name="Corp",
            industry="Tech",
            account_id="acc",
            user_id="usr",
            uploaded_documents="",
        )
        assert params3.uploaded_documents == []

    def test_string_stripping(self):
        """Test that whitespace is stripped from string fields."""
        params = StrategyParameters(
            company_name="  Acme Corp  ",
            industry="  Technology  ",
            account_id="  acc_123  ",
            user_id="  usr_456  ",
            websites="  https://acme.com  ",
        )
        assert params.company_name == "Acme Corp"
        assert params.industry == "Technology"
        assert params.account_id == "acc_123"
        assert params.user_id == "usr_456"
        assert params.websites == "https://acme.com"


class TestStrategyResponse:
    """Test the StrategyResponse model."""

    def test_valid_response(self):
        """Test creation of valid response."""
        response = StrategyResponse(
            status="success",
            query="Generate strategy for Acme Corp",
            result={"strategy": "Marketing plan details"},
            account_id="acc_123",
        )

        assert response.status == "success"
        assert response.query == "Generate strategy for Acme Corp"
        assert response.result == {"strategy": "Marketing plan details"}
        assert response.source == "strategy_specialist"
        assert response.agent == "strategy"
        assert response.account_id == "acc_123"
        assert response.error is None

    def test_error_response(self):
        """Test creation of error response."""
        response = StrategyResponse(
            status="error",
            query="Generate strategy",
            result=None,
            account_id="acc_123",
            error="Failed to connect to agent",
        )

        assert response.status == "error"
        assert response.result is None
        assert response.error == "Failed to connect to agent"

    def test_custom_source_and_agent(self):
        """Test overriding default source and agent."""
        response = StrategyResponse(
            status="success",
            query="Query",
            result="Result",
            source="custom_source",
            agent="custom_agent",
            account_id="acc_123",
        )

        assert response.source == "custom_source"
        assert response.agent == "custom_agent"


class TestParseStrategyQuery:
    """Test the parse_strategy_query function."""

    def test_parse_complete_query(self):
        """Test parsing a complete formatted query."""
        query = """
        Generate strategy for:
        - company_name: Acme Corporation
        - industry: Technology
        - websites: https://acme.com,https://blog.acme.com
        - customer_regions: North America,Europe
        - account_id: acc_123
        - user_id: usr_456
        - annual_ad_budget: $100,000
        - project_id: test-project
        - uploaded_documents: gs://bucket/doc1.pdf,gs://bucket/doc2.pdf
        """

        result = parse_strategy_query(query)

        assert result["company_name"] == "Acme Corporation"
        assert result["industry"] == "Technology"
        assert result["websites"] == "https://acme.com,https://blog.acme.com"
        assert result["customer_regions"] == "North America,Europe"
        assert result["account_id"] == "acc_123"
        assert result["user_id"] == "usr_456"
        assert result["annual_ad_budget"] == "$100,000"
        assert result["project_id"] == "test-project"
        assert (
            result["uploaded_documents"] == "gs://bucket/doc1.pdf,gs://bucket/doc2.pdf"
        )

    def test_parse_with_bullet_points(self):
        """Test parsing with bullet point format."""
        query = """
        • company_name: BulletCorp
        • industry: Retail
        • account_id: acc_bullet
        • user_id: usr_bullet
        """

        result = parse_strategy_query(query)

        assert result["company_name"] == "BulletCorp"
        assert result["industry"] == "Retail"
        assert result["account_id"] == "acc_bullet"
        assert result["user_id"] == "usr_bullet"

    def test_parse_partial_query(self):
        """Test parsing with only some fields present."""
        query = """
        - company_name: PartialCorp
        - industry: Finance
        Some other text that should be ignored
        - account_id: acc_partial
        Random text here
        """

        result = parse_strategy_query(query)

        assert result["company_name"] == "PartialCorp"
        assert result["industry"] == "Finance"
        assert result["account_id"] == "acc_partial"
        assert "user_id" not in result
        assert "websites" not in result

    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        query = """
        - COMPANY_NAME: UpperCorp
        - Industry: MixedCase
        - account_ID: acc_mixed
        """

        result = parse_strategy_query(query)

        assert result["company_name"] == "UpperCorp"
        assert result["industry"] == "MixedCase"
        assert result["account_id"] == "acc_mixed"

    def test_parse_with_multiline_values(self):
        """Test parsing values that span to end of line."""
        query = """
        - company_name: Company with spaces and special chars!
        - industry: Technology & Innovation Sector
        - websites: https://site1.com, https://site2.com, https://site3.com
        """

        result = parse_strategy_query(query)

        assert result["company_name"] == "Company with spaces and special chars!"
        assert result["industry"] == "Technology & Innovation Sector"
        assert (
            result["websites"]
            == "https://site1.com, https://site2.com, https://site3.com"
        )

    def test_parse_empty_query(self):
        """Test parsing an empty or invalid query."""
        result = parse_strategy_query("")
        assert result == {}

        result2 = parse_strategy_query("No parameters here")
        assert result2 == {}

    def test_integration_with_model(self):
        """Test that parsed query can be used to create StrategyParameters."""
        query = """
        - company_name: IntegrationCorp
        - industry: Healthcare
        - account_id: acc_int
        - user_id: usr_int
        - annual_ad_budget: $50,000.00
        """

        parsed = parse_strategy_query(query)
        params = StrategyParameters(**parsed)

        assert params.company_name == "IntegrationCorp"
        assert params.industry == "Healthcare"
        assert params.account_id == "acc_int"
        assert params.user_id == "usr_int"
        assert params.annual_ad_budget == 50000.0
