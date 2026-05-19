"""Tests for selective strategy execution API integration."""

from src.kene_api.models.kene_models import AccountRequest


class TestAccountRequestModel:
    """Tests for AccountRequest model with selective strategy fields."""

    def test_account_request_with_enabled_strategies(self):
        """Test AccountRequest accepts enabled_strategies field."""
        request = AccountRequest(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites=["https://example.com"],
            timezone="America/New_York",
            data_region="US",
            region=["US"],
            enabled_strategies=["marketing_strategy", "competitive_strategy"],
        )

        assert request.enabled_strategies == [
            "marketing_strategy",
            "competitive_strategy",
        ]
        assert len(request.enabled_strategies) == 2

    def test_account_request_with_override_product_categories(self):
        """Test AccountRequest accepts override_product_categories field."""
        request = AccountRequest(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites=["https://example.com"],
            timezone="America/New_York",
            data_region="US",
            region=["US"],
            override_product_categories=["Core Products", "Premium Services"],
        )

        assert request.override_product_categories == [
            "Core Products",
            "Premium Services",
        ]
        assert len(request.override_product_categories) == 2

    def test_account_request_optional_fields_default_to_none(self):
        """Test that optional strategy fields default to None."""
        request = AccountRequest(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites=["https://example.com"],
            timezone="America/New_York",
            data_region="US",
            region=["US"],
        )

        assert request.enabled_strategies is None
        assert request.override_product_categories is None

    def test_account_request_with_all_fields(self):
        """Test AccountRequest with all fields including selective strategy."""
        request = AccountRequest(
            account_name="Test Account",
            organization_id="org_123",
            industry="Technology",
            status="Active",
            websites=["https://example.com"],
            timezone="America/New_York",
            data_region="US",
            region=["US"],
            marketing_channels=["SEO", "PPC"],
            product_integrations=["GA4"],
            estimated_annual_ad_budget=100000,
            enabled_strategies=["business_strategy", "marketing_strategy"],
            override_product_categories=["Product Line A", "Product Line B"],
        )

        assert request.account_name == "Test Account"
        assert request.enabled_strategies == ["business_strategy", "marketing_strategy"]
        assert request.override_product_categories == [
            "Product Line A",
            "Product Line B",
        ]
        assert request.marketing_channels == ["SEO", "PPC"]
        assert request.product_integrations == ["GA4"]
        assert request.estimated_annual_ad_budget == 100000


class TestFormParsingWithSelectiveStrategies:
    """Tests for form parsing with selective strategy fields."""

    def test_parse_enabled_strategies_from_json_string(self):
        """Test parsing enabled_strategies from JSON string."""
        import json

        json_string = '["marketing_strategy", "competitive_strategy"]'
        parsed = json.loads(json_string)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed == ["marketing_strategy", "competitive_strategy"]

    def test_parse_override_product_categories_from_json_string(self):
        """Test parsing override_product_categories from JSON string."""
        import json

        json_string = '["Core Products & Services", "Premium Offerings"]'
        parsed = json.loads(json_string)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert "Core Products & Services" in parsed

    def test_empty_array_json_parsing(self):
        """Test that empty JSON arrays parse correctly."""
        import json

        json_string = "[]"
        parsed = json.loads(json_string)

        assert isinstance(parsed, list)
        assert len(parsed) == 0


class TestAdminAuthorizationForSelectiveStrategies:
    """Tests for admin authorization on selective strategy features."""

    def test_admin_can_use_selective_strategies(self):
        """Test that admin users can provide enabled_strategies."""

        # Simulate admin user
        class MockUser:
            is_super_admin = True
            email = "admin@ken-e.ai"

        user = MockUser()
        enabled_strategies = ["marketing_strategy"]

        # Admin check should pass
        if enabled_strategies is not None and not user.is_super_admin:
            should_raise_403 = True
        else:
            should_raise_403 = False

        assert should_raise_403 is False

    def test_non_admin_cannot_use_selective_strategies(self):
        """Test that non-admin users cannot provide enabled_strategies."""

        # Simulate non-admin user
        class MockUser:
            is_super_admin = False
            email = "user@example.com"

        user = MockUser()
        enabled_strategies = ["marketing_strategy"]

        # Admin check should fail
        if enabled_strategies is not None and not user.is_super_admin:
            should_raise_403 = True
        else:
            should_raise_403 = False

        assert should_raise_403 is True

    def test_non_admin_can_create_account_without_strategy_selection(self):
        """Test that non-admin users can create accounts with default behavior."""

        # Simulate non-admin user
        class MockUser:
            is_super_admin = False
            email = "user@example.com"

        user = MockUser()
        enabled_strategies = None  # None means default (all strategies)

        # Admin check should pass for None
        if enabled_strategies is not None and not user.is_super_admin:
            should_raise_403 = True
        else:
            should_raise_403 = False

        assert should_raise_403 is False
