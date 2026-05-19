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


def create_valid_test_narrative(name: str = "Test") -> str:
    """Create a minimal valid narrative for testing (meets 2000 char minimum)."""
    base_narrative = f"""Demographics:
- Age: 30-45 years old
- Gender: All genders
- Education: Bachelor's degree or higher
- Location: Urban and suburban areas
- Household income: $75,000-$150,000 annually
- Cultural background: Diverse professionals

Psychographics:
- Values efficiency and innovation
- Adopts technology to improve productivity
- Seeks professional development opportunities
- Interested in sustainable practices
- Prefers data-driven decision making

Needs / Jobs-to-be-done:
- Streamline complex workflows
- Access real-time data for informed decisions
- Collaborate effectively with teams
- Maintain security and compliance

Pain Points:
- Frustrated by fragmented tools
- Struggles with manual data entry
- Limited visibility into progress
- Difficulty justifying ROI
- Concerned about data security

Goals:
- Increase productivity by 30%
- Reduce operational costs
- Improve collaboration
- Achieve measurable outcomes
- Build scalable infrastructure

Motivations:
- Driven by career advancement
- Motivated to solve problems
- Seeks solutions with clear ROI
- Values ongoing support

Buying Behaviors:
{name} researches extensively before purchasing. Price-sensitive but willing to pay for proven solutions. Prefers annual subscriptions. Makes collaborative decisions. Relies on peer reviews and demos.

Communication Channels:
- LinkedIn for professional content
- Industry webinars and conferences
- Email newsletters
- Podcasts during commute
- Professional forums

Exclusion Criteria:
- Companies with less than 50 employees
- Those without budget authority
- Price-sensitive buyers prioritizing cost over functionality
- Organizations unwilling to adopt cloud solutions
"""
    # Pad to meet 2000 character minimum if needed
    if len(base_narrative) < 2000:
        base_narrative += (
            "\n" + "Additional context: " + "x" * (2000 - len(base_narrative) - 20)
        )
    return base_narrative


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
        valid_narrative = """
Demographics:
- Age: 35-40 years old
- Gender: All genders
- Education: Bachelor's degree in Marketing or Business
- Location: Urban areas, primarily United States
- Household income: $80,000-$120,000 annually

Psychographics:
- Values data-driven decision making
- Results-oriented and goal-focused
- Interested in continuous learning and professional development
- Prefers collaborative team environments

Needs / Jobs-to-be-done:
- Generate qualified leads and improve conversion rates
- Measure and optimize marketing campaign performance
- Manage marketing budgets effectively
- Coordinate cross-functional marketing initiatives

Pain Points:
- Difficulty proving ROI on marketing spend to executives
- Struggles with fragmented marketing tools and data silos
- Limited time for strategic planning due to tactical demands
- Challenge of staying current with rapidly evolving marketing channels

Goals:
- Increase qualified lead generation by 25% year-over-year
- Improve marketing attribution and campaign tracking
- Build a more cohesive brand presence across channels
- Develop more efficient workflows to reclaim strategic time

Motivations:
- Career advancement and recognition from leadership
- Driven to demonstrate measurable business impact
- Motivated by solving complex marketing challenges
- Values solutions that save time and improve team productivity

Buying Behaviors:
Mary researches extensively before purchasing, typically spending 4-6 weeks evaluating options. She's moderately price-sensitive and seeks solutions that offer clear ROI. Prefers SaaS subscriptions with monthly or annual billing. Makes decisions after consulting with her team and reviewing case studies from similar companies. Values free trials and proof-of-concept opportunities.

Communication Channels:
- LinkedIn for professional networking and industry insights
- Marketing-focused podcasts during commute
- Industry conferences and virtual webinars
- Email newsletters from marketing thought leaders
- Slack communities for B2B marketers

Exclusion Criteria:
- Marketing professionals in B2C consumer goods companies
- Individuals without budget authority or purchasing influence
- Those in companies with less than 25 employees
- Marketing coordinators or specialists without management responsibility
"""
        profile = IdealCustomerProfile(
            display_name="Marketing Manager Mary",
            narrative=valid_narrative,
            references=["https://example.com/research"],
        )

        assert profile.display_name == "Marketing Manager Mary"
        assert "Demographics:" in profile.narrative
        assert len(profile.references) == 1

    def test_profile_has_no_strategy_fields(self):
        """Test that profiles do NOT contain strategy fields."""
        minimal_valid_narrative = (
            """Demographics:
- Age: 30-45
- Gender: All
- Education: Bachelor's
- Location: Urban
- Income: $50k+

Psychographics:
- Values quality
- Tech-savvy

Needs / Jobs-to-be-done:
- Solve daily problems
- Improve efficiency

Pain Points:
- Time constraints
- Budget limitations

Goals:
- Achieve success
- Grow professionally

Motivations:
- Career growth
- Recognition

Buying Behaviors:
Researches before buying. Price-conscious but values quality. Prefers annual subscriptions.

Communication Channels:
- LinkedIn
- Email

Exclusion Criteria:
- Non-target demographics
"""
            + "x" * (2000 - 500)
        )

        profile = IdealCustomerProfile(
            display_name="Test Profile",
            narrative=minimal_valid_narrative,
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

    def test_narrative_with_all_required_sections(self):
        """Narrative with all 9 required sections should pass validation."""
        valid_narrative = """
Demographics:
- Age: 30-45 years old
- Gender: All genders
- Education: Bachelor's degree or higher
- Location: Urban and suburban areas across North America
- Household income: $75,000-$150,000 annually
- Cultural background: Diverse, tech-savvy professionals

Psychographics:
- Values efficiency, innovation, and work-life balance
- Adopts technology early to improve productivity
- Actively seeks professional development opportunities
- Interested in sustainable and ethical business practices
- Prefers data-driven decision making

Needs / Jobs-to-be-done:
- Streamline complex workflows and reduce manual tasks
- Access real-time data and analytics for informed decisions
- Collaborate effectively with distributed teams
- Maintain security and compliance in digital operations

Pain Points:
- Frustrated by fragmented tools requiring multiple logins
- Struggles with manual data entry and reconciliation
- Limited visibility into project status and team progress
- Difficulty justifying ROI on technology investments
- Concerned about data security and privacy compliance

Goals:
- Increase team productivity by 30% within the next year
- Reduce operational costs through automation
- Improve collaboration across departments
- Achieve measurable business outcomes from technology investments
- Build a scalable infrastructure for future growth

Motivations:
- Driven by career advancement and professional recognition
- Motivated to solve problems that directly impact business results
- Seeks solutions that demonstrate clear ROI and efficiency gains
- Values vendors who provide ongoing support and education

Buying Behaviors:
Researches extensively before purchasing, typically spending 2-3 months evaluating options. Highly price-sensitive but willing to pay premium for proven solutions with strong support. Prefers annual subscriptions with flexibility to scale. Makes decisions collaboratively with input from technical teams and finance. Relies heavily on peer reviews, case studies, and product demos before committing.

Communication Channels:
- LinkedIn for professional content and peer recommendations
- Industry-specific webinars and virtual conferences
- Email newsletters from trusted industry sources
- Podcasts during commute time
- Slack communities and professional forums

Exclusion Criteria:
- Individuals in companies with less than 50 employees
- Those without budget authority or purchasing influence
- Professionals in highly regulated industries requiring custom solutions
- Price-sensitive buyers prioritizing cost over functionality
- Organizations unwilling to adopt cloud-based solutions
"""
        profile = IdealCustomerProfile(
            display_name="Tech-Savvy Manager",
            narrative=valid_narrative,
            references=["https://example.com/research"],
        )

        assert profile.narrative == valid_narrative
        assert len(profile.narrative) >= 2000
        assert len(profile.narrative) <= 6000

    def test_narrative_too_short_fails_validation(self):
        """Narrative under 2000 characters should fail validation."""
        short_narrative = "x" * 1999

        with pytest.raises(ValidationError) as exc_info:
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=short_narrative,
                references=[],
            )

        errors = exc_info.value.errors()
        assert any("at least 2000 characters" in str(error) for error in errors)

    def test_narrative_too_long_fails_validation(self):
        """Narrative over 6000 characters should fail validation."""
        long_narrative = "x" * 6001

        with pytest.raises(ValidationError) as exc_info:
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=long_narrative,
                references=[],
            )

        errors = exc_info.value.errors()
        assert any("at most 6000 characters" in str(error) for error in errors)

    def test_narrative_exactly_2000_characters_passes(self):
        """Narrative with exactly 2000 characters should pass validation."""
        # Create a narrative with all sections and exactly 2000 chars
        narrative_base = """Demographics:
- Age: 30-45
- Gender: All
- Education: Bachelor's
- Location: Urban areas
- Income: $75k-$150k

Psychographics:
- Values efficiency
- Tech-savvy
- Career-focused

Needs / Jobs-to-be-done:
- Streamline workflows
- Access real-time data

Pain Points:
- Frustrated by fragmented tools
- Manual data entry issues

Goals:
- Increase productivity by 30%
- Reduce operational costs

Motivations:
- Career advancement
- Solve business problems

Buying Behaviors:
Researches extensively for 2-3 months. Price-sensitive but willing to pay for quality.

Communication Channels:
- LinkedIn
- Industry webinars

Exclusion Criteria:
- Companies under 50 employees
"""
        # Pad to exactly 2000 characters
        narrative = narrative_base + "x" * (2000 - len(narrative_base))

        profile = IdealCustomerProfile(
            display_name="Test Profile",
            narrative=narrative,
            references=[],
        )

        assert len(profile.narrative) == 2000

    def test_narrative_exactly_6000_characters_passes(self):
        """Narrative with exactly 6000 characters should pass validation."""
        narrative_base = """Demographics:
- Age: 30-45
- Gender: All
- Education: Bachelor's
- Location: Urban areas
- Income: $75k-$150k

Psychographics:
- Values efficiency
- Tech-savvy
- Career-focused

Needs / Jobs-to-be-done:
- Streamline workflows
- Access real-time data

Pain Points:
- Frustrated by fragmented tools
- Manual data entry issues

Goals:
- Increase productivity by 30%
- Reduce operational costs

Motivations:
- Career advancement
- Solve business problems

Buying Behaviors:
Researches extensively for 2-3 months. Price-sensitive but willing to pay for quality.

Communication Channels:
- LinkedIn
- Industry webinars

Exclusion Criteria:
- Companies under 50 employees
"""
        # Pad to exactly 6000 characters
        narrative = narrative_base + "x" * (6000 - len(narrative_base))

        profile = IdealCustomerProfile(
            display_name="Test Profile",
            narrative=narrative,
            references=[],
        )

        assert len(profile.narrative) == 6000

    def test_narrative_missing_demographics_fails(self):
        """Narrative missing Demographics section should fail validation."""
        narrative_missing_demographics = "x" * 2000  # No sections at all

        with pytest.raises(ValidationError) as exc_info:
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=narrative_missing_demographics,
                references=[],
            )

        errors = exc_info.value.errors()
        assert any("Demographics:" in str(error) for error in errors)

    def test_narrative_missing_multiple_sections_fails(self):
        """Narrative missing multiple sections should list all missing sections."""
        narrative_partial = (
            """Demographics:
- Age: 30-45

Psychographics:
- Values efficiency
"""
            + "x" * 2000
        )

        with pytest.raises(ValidationError) as exc_info:
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=narrative_partial,
                references=[],
            )

        errors = exc_info.value.errors()
        # Should mention missing sections
        assert any(
            "missing required sections" in str(error).lower() for error in errors
        )


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
        assert (
            mapping.customer_strategies[0].customer_profile_name
            == "Marketing Manager Mary"
        )

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
                narrative=create_valid_test_narrative("Mary"),
                references=["https://example.com/mary-research"],
            ),
            IdealCustomerProfile(
                display_name="Technical Director Tom",
                narrative=create_valid_test_narrative("Tom"),
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
            narrative=create_valid_test_narrative("Only One"),
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
                narrative=create_valid_test_narrative(f"Profile {i}"),
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
                narrative=create_valid_test_narrative("Existing Profile"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Another Profile",
                narrative=create_valid_test_narrative("Another Profile"),
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
                narrative=create_valid_test_narrative("Enterprise Buyer"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Small Business Owner",
                narrative=create_valid_test_narrative("Small Business Owner"),
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
                        software_enterprise_strategy = (
                            cs.strategy.problem_awareness_strategy
                        )
                    elif mapping.category_name == "Cloud Storage":
                        cloud_enterprise_strategy = (
                            cs.strategy.problem_awareness_strategy
                        )

        # Strategies should be different
        assert software_enterprise_strategy != cloud_enterprise_strategy
        assert "Software suite" in software_enterprise_strategy
        assert "Cloud storage" in cloud_enterprise_strategy
