"""
Unit tests for marketing strategy Pydantic models.

Tests the product-scoped strategy structure where:
- 2-5 master ideal customer profiles are created (WITHOUT strategies)
- Product categories contain customer_strategies for each relevant profile
- Each strategy is scoped to product category + customer profile combination
"""

import pytest
from pydantic import ValidationError

from ..marketing_models import (
    IdealCustomerProfile,
    MarketingResearchReport,
    MarketingStrategy,
    MarketingStrategyForProfile,
    ProductCategoryMapping,
)


class TestMarketingStrategy:
    """Test MarketingStrategy model validation."""

    def test_valid_strategy_creation(self):
        """Test creating a valid marketing strategy."""
        strategy = MarketingStrategy(
            problem_awareness_strategy="Educate through LinkedIn articles and webinars...",
            brand_awareness_strategy="Target with LinkedIn sponsored content...",
            consideration_strategy="Provide case studies and ROI calculators...",
            conversion_strategy="Offer personalized demos and trial periods...",
            loyalty_strategy="Regular check-ins and customer success programs...",
            references=["https://example.com/research"],
        )

        assert "LinkedIn" in strategy.problem_awareness_strategy
        assert len(strategy.references) == 1

    def test_strategy_requires_all_fields(self):
        """Test that all 5 strategy fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            MarketingStrategy(
                problem_awareness_strategy="Test strategy",
                brand_awareness_strategy="Test strategy",
                # Missing consideration, conversion, loyalty
            )

        errors = exc_info.value.errors()
        required_fields = {
            "consideration_strategy",
            "conversion_strategy",
            "loyalty_strategy",
        }
        missing_fields = {error["loc"][0] for error in errors}
        assert required_fields.issubset(missing_fields)

    def test_strategy_max_length_validation(self):
        """Test that strategy fields respect max_length constraint."""
        long_text = "x" * 4001  # Exceeds 4000 char limit

        with pytest.raises(ValidationError) as exc_info:
            MarketingStrategy(
                problem_awareness_strategy=long_text,
                brand_awareness_strategy="Valid",
                consideration_strategy="Valid",
                conversion_strategy="Valid",
                loyalty_strategy="Valid",
            )

        errors = exc_info.value.errors()
        assert any("at most 4000 characters" in str(error) for error in errors)


class TestMarketingStrategyForProfile:
    """Test MarketingStrategyForProfile model validation."""

    def test_valid_strategy_for_profile_creation(self):
        """Test creating a valid strategy-profile link."""
        strategy_for_profile = MarketingStrategyForProfile(
            customer_profile_name="Marketing Manager Mary",
            strategy=MarketingStrategy(
                problem_awareness_strategy="Problem awareness strategy...",
                brand_awareness_strategy="Brand awareness strategy...",
                consideration_strategy="Consideration strategy...",
                conversion_strategy="Conversion strategy...",
                loyalty_strategy="Loyalty strategy...",
                references=["https://example.com"],
            ),
        )

        assert strategy_for_profile.customer_profile_name == "Marketing Manager Mary"
        assert isinstance(strategy_for_profile.strategy, MarketingStrategy)

    def test_strategy_for_profile_requires_profile_name(self):
        """Test that customer_profile_name is required."""
        with pytest.raises(ValidationError) as exc_info:
            MarketingStrategyForProfile(
                strategy=MarketingStrategy(
                    problem_awareness_strategy="Test",
                    brand_awareness_strategy="Test",
                    consideration_strategy="Test",
                    conversion_strategy="Test",
                    loyalty_strategy="Test",
                )
            )

        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "customer_profile_name" for error in errors)


class TestIdealCustomerProfile:
    """Test IdealCustomerProfile model validation."""

    def test_valid_profile_creation(self):
        """Test creating a valid ideal customer profile WITHOUT strategies."""
        profile = IdealCustomerProfile(
            display_name="Marketing Manager Mary",
            narrative="Mary is a 35-year-old marketing manager at a mid-sized B2B company...",
            references=["https://example.com/research"],
        )

        assert profile.display_name == "Marketing Manager Mary"
        assert "Mary" in profile.narrative
        assert len(profile.references) == 1

    def test_profile_has_no_strategy_fields(self):
        """Test that profiles do NOT contain strategy fields."""
        profile = IdealCustomerProfile(
            display_name="Test Profile",
            narrative="Test narrative",
            references=[],
        )

        # Verify no strategy fields exist
        assert not hasattr(profile, "problem_awareness_strategy")
        assert not hasattr(profile, "brand_awareness_strategy")
        assert not hasattr(profile, "consideration_strategy")
        assert not hasattr(profile, "conversion_strategy")
        assert not hasattr(profile, "loyalty_strategy")

    def test_profile_requires_display_name_and_narrative(self):
        """Test that display_name and narrative are required."""
        with pytest.raises(ValidationError) as exc_info:
            IdealCustomerProfile()

        errors = exc_info.value.errors()
        required_fields = {"display_name", "narrative"}
        missing_fields = {error["loc"][0] for error in errors}
        assert required_fields.issubset(missing_fields)


class TestProductCategoryMapping:
    """Test ProductCategoryMapping model validation."""

    def test_valid_mapping_with_customer_strategies(self):
        """Test creating a valid product category mapping with strategies."""
        mapping = ProductCategoryMapping(
            category_name="Cloud Services",
            customer_strategies=[
                MarketingStrategyForProfile(
                    customer_profile_name="Marketing Manager Mary",
                    strategy=MarketingStrategy(
                        problem_awareness_strategy="Problem awareness for cloud...",
                        brand_awareness_strategy="Brand awareness for cloud...",
                        consideration_strategy="Consideration for cloud...",
                        conversion_strategy="Conversion for cloud...",
                        loyalty_strategy="Loyalty for cloud...",
                    ),
                ),
                MarketingStrategyForProfile(
                    customer_profile_name="Technical Director Tom",
                    strategy=MarketingStrategy(
                        problem_awareness_strategy="Problem awareness for Tom...",
                        brand_awareness_strategy="Brand awareness for Tom...",
                        consideration_strategy="Consideration for Tom...",
                        conversion_strategy="Conversion for Tom...",
                        loyalty_strategy="Loyalty for Tom...",
                    ),
                ),
            ],
        )

        assert mapping.category_name == "Cloud Services"
        assert len(mapping.customer_strategies) == 2
        assert mapping.customer_strategies[0].customer_profile_name == "Marketing Manager Mary"

    def test_mapping_requires_minimum_one_strategy(self):
        """Test that at least 1 customer strategy is required per category."""
        with pytest.raises(ValidationError) as exc_info:
            ProductCategoryMapping(
                category_name="Test Category",
                customer_strategies=[],
            )

        errors = exc_info.value.errors()
        assert any("at least 1 item" in str(error) for error in errors)

    def test_mapping_allows_maximum_five_strategies(self):
        """Test that at most 5 customer strategies are allowed per category."""
        strategies = [
            MarketingStrategyForProfile(
                customer_profile_name=f"Profile {i}",
                strategy=MarketingStrategy(
                    problem_awareness_strategy="Test",
                    brand_awareness_strategy="Test",
                    consideration_strategy="Test",
                    conversion_strategy="Test",
                    loyalty_strategy="Test",
                ),
            )
            for i in range(6)
        ]

        with pytest.raises(ValidationError) as exc_info:
            ProductCategoryMapping(
                category_name="Test Category",
                customer_strategies=strategies,
            )

        errors = exc_info.value.errors()
        assert any("at most 5 items" in str(error) for error in errors)


class TestMarketingResearchReport:
    """Test MarketingResearchReport model validation."""

    def test_valid_report_with_product_scoped_strategies(self):
        """Test creating a valid report with strategies scoped to product+profile."""
        profiles = [
            IdealCustomerProfile(
                display_name="Marketing Manager Mary",
                narrative="Mary manages marketing for B2B companies...",
                references=["https://example.com/mary-research"],
            ),
            IdealCustomerProfile(
                display_name="Technical Director Tom",
                narrative="Tom evaluates technical solutions...",
                references=["https://example.com/tom-research"],
            ),
        ]

        mappings = [
            ProductCategoryMapping(
                category_name="Cloud Services",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Marketing Manager Mary",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Cloud services problem for Mary...",
                            brand_awareness_strategy="Cloud services brand for Mary...",
                            consideration_strategy="Cloud services consideration for Mary...",
                            conversion_strategy="Cloud services conversion for Mary...",
                            loyalty_strategy="Cloud services loyalty for Mary...",
                        ),
                    ),
                    MarketingStrategyForProfile(
                        customer_profile_name="Technical Director Tom",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Cloud services problem for Tom...",
                            brand_awareness_strategy="Cloud services brand for Tom...",
                            consideration_strategy="Cloud services consideration for Tom...",
                            conversion_strategy="Cloud services conversion for Tom...",
                            loyalty_strategy="Cloud services loyalty for Tom...",
                        ),
                    ),
                ],
            ),
            ProductCategoryMapping(
                category_name="Analytics Platform",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Marketing Manager Mary",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Analytics problem for Mary...",
                            brand_awareness_strategy="Analytics brand for Mary...",
                            consideration_strategy="Analytics consideration for Mary...",
                            conversion_strategy="Analytics conversion for Mary...",
                            loyalty_strategy="Analytics loyalty for Mary...",
                        ),
                    ),
                ],
            ),
        ]

        report = MarketingResearchReport(
            ideal_customer_profiles=profiles, product_category_mappings=mappings
        )

        assert len(report.ideal_customer_profiles) == 2
        assert len(report.product_category_mappings) == 2
        # Verify strategies are nested under categories
        assert len(report.product_category_mappings[0].customer_strategies) == 2
        assert len(report.product_category_mappings[1].customer_strategies) == 1

    def test_report_requires_minimum_two_profiles(self):
        """Test that at least 2 master profiles are required."""
        profile = IdealCustomerProfile(
            display_name="Only One",
            narrative="Test narrative",
            references=[],
        )

        mapping = ProductCategoryMapping(
            category_name="Test",
            customer_strategies=[
                MarketingStrategyForProfile(
                    customer_profile_name="Only One",
                    strategy=MarketingStrategy(
                        problem_awareness_strategy="Test",
                        brand_awareness_strategy="Test",
                        consideration_strategy="Test",
                        conversion_strategy="Test",
                        loyalty_strategy="Test",
                    ),
                )
            ],
        )

        with pytest.raises(ValidationError) as exc_info:
            MarketingResearchReport(
                ideal_customer_profiles=[profile], product_category_mappings=[mapping]
            )

        errors = exc_info.value.errors()
        assert any("at least 2 items" in str(error) for error in errors)

    def test_report_allows_maximum_five_profiles(self):
        """Test that at most 5 master profiles are allowed."""
        profiles = [
            IdealCustomerProfile(
                display_name=f"Profile {i}",
                narrative=f"Narrative {i}",
                references=[],
            )
            for i in range(6)
        ]

        mapping = ProductCategoryMapping(
            category_name="Test",
            customer_strategies=[
                MarketingStrategyForProfile(
                    customer_profile_name="Profile 0",
                    strategy=MarketingStrategy(
                        problem_awareness_strategy="Test",
                        brand_awareness_strategy="Test",
                        consideration_strategy="Test",
                        conversion_strategy="Test",
                        loyalty_strategy="Test",
                    ),
                )
            ],
        )

        with pytest.raises(ValidationError) as exc_info:
            MarketingResearchReport(
                ideal_customer_profiles=profiles, product_category_mappings=[mapping]
            )

        errors = exc_info.value.errors()
        assert any("at most 5 items" in str(error) for error in errors)

    def test_customer_profile_name_references_must_exist(self):
        """Test validation that customer_profile_name references exist in master list."""
        profiles = [
            IdealCustomerProfile(
                display_name="Existing Profile",
                narrative="Test narrative",
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Another Profile",
                narrative="Test narrative 2",
                references=[],
            ),
        ]

        mappings = [
            ProductCategoryMapping(
                category_name="Valid Category",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Non-Existent Profile",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Test",
                            brand_awareness_strategy="Test",
                            consideration_strategy="Test",
                            conversion_strategy="Test",
                            loyalty_strategy="Test",
                        ),
                    ),
                ],
            )
        ]

        # This should fail validation
        with pytest.raises(ValidationError) as exc_info:
            MarketingResearchReport(
                ideal_customer_profiles=profiles, product_category_mappings=mappings
            )

        errors = exc_info.value.errors()
        error_messages = [str(error) for error in errors]
        assert any(
            "Non-Existent Profile" in msg or "not found" in msg.lower()
            for msg in error_messages
        )


class TestProfileReusageAcrossCategories:
    """Test that profiles can be reused across multiple categories with different strategies."""

    def test_same_profile_different_strategies_per_category(self):
        """Test that a profile can have different strategies for different categories."""
        profiles = [
            IdealCustomerProfile(
                display_name="Enterprise Buyer",
                narrative="Purchases for large organizations...",
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Small Business Owner",
                narrative="Runs small businesses...",
                references=[],
            ),
        ]

        mappings = [
            ProductCategoryMapping(
                category_name="Software Suite",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Enterprise Buyer",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Software suite problem for enterprise...",
                            brand_awareness_strategy="Software suite brand for enterprise...",
                            consideration_strategy="Software suite consideration for enterprise...",
                            conversion_strategy="Software suite conversion for enterprise...",
                            loyalty_strategy="Software suite loyalty for enterprise...",
                        ),
                    ),
                    MarketingStrategyForProfile(
                        customer_profile_name="Small Business Owner",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Software suite problem for SMB...",
                            brand_awareness_strategy="Software suite brand for SMB...",
                            consideration_strategy="Software suite consideration for SMB...",
                            conversion_strategy="Software suite conversion for SMB...",
                            loyalty_strategy="Software suite loyalty for SMB...",
                        ),
                    ),
                ],
            ),
            ProductCategoryMapping(
                category_name="Cloud Storage",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Enterprise Buyer",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="DIFFERENT: Cloud storage problem for enterprise...",
                            brand_awareness_strategy="DIFFERENT: Cloud storage brand for enterprise...",
                            consideration_strategy="DIFFERENT: Cloud storage consideration for enterprise...",
                            conversion_strategy="DIFFERENT: Cloud storage conversion for enterprise...",
                            loyalty_strategy="DIFFERENT: Cloud storage loyalty for enterprise...",
                        ),
                    ),
                ],
            ),
        ]

        report = MarketingResearchReport(
            ideal_customer_profiles=profiles, product_category_mappings=mappings
        )

        # Verify structure
        assert len(report.ideal_customer_profiles) == 2
        assert len(report.product_category_mappings) == 2

        # Verify Enterprise Buyer appears in both categories
        enterprise_categories = [
            mapping
            for mapping in report.product_category_mappings
            if any(
                cs.customer_profile_name == "Enterprise Buyer"
                for cs in mapping.customer_strategies
            )
        ]
        assert len(enterprise_categories) == 2

        # Verify strategies are different per category
        software_enterprise_strategy = None
        cloud_enterprise_strategy = None

        for mapping in report.product_category_mappings:
            for cs in mapping.customer_strategies:
                if cs.customer_profile_name == "Enterprise Buyer":
                    if mapping.category_name == "Software Suite":
                        software_enterprise_strategy = cs.strategy.problem_awareness_strategy
                    elif mapping.category_name == "Cloud Storage":
                        cloud_enterprise_strategy = cs.strategy.problem_awareness_strategy

        # Strategies should be different
        assert software_enterprise_strategy != cloud_enterprise_strategy
        assert "Software suite" in software_enterprise_strategy
        assert "Cloud storage" in cloud_enterprise_strategy
