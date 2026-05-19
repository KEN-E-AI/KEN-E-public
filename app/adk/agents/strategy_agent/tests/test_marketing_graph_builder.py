"""
Tests for MarketingGraphBuilder.

This module tests the marketing graph construction functionality,
ensuring that marketing research reports are correctly converted
into Neo4j graph nodes and relationships.
"""

from unittest.mock import Mock

import pytest

# Use relative imports to work both in tests and when deployed
try:
    # Try relative import first (for when running in Agent Engine)
    from ..marketing_graph_builder import MarketingGraphBuilder
    from ..marketing_models import (
        IdealCustomerProfile,
        MarketingResearchReport,
        MarketingStrategy,
        MarketingStrategyForProfile,
        ProductCategoryMapping,
    )
except ImportError:
    # Fall back to absolute import (for when running tests from root)
    from agents.strategy_agent.marketing_graph_builder import MarketingGraphBuilder
    from agents.strategy_agent.marketing_models import (
        IdealCustomerProfile,
        MarketingResearchReport,
        MarketingStrategy,
        MarketingStrategyForProfile,
        ProductCategoryMapping,
    )


@pytest.fixture
def mock_neo4j_ops():
    """Create a mock Neo4j operations instance."""
    mock = Mock()
    mock.connection = Mock()
    return mock


@pytest.fixture
def graph_builder(mock_neo4j_ops):
    """Create a MarketingGraphBuilder instance with mocked Neo4j ops."""
    return MarketingGraphBuilder(mock_neo4j_ops)


def create_test_narrative(name: str) -> str:
    """Create a valid test narrative meeting 2000 char minimum."""
    base = f"""Demographics:
- Age: 25-65 years old professionals and retirees across diverse life stages
- Gender: All genders welcome with inclusive banking products and services
- Education: Ranges from high school diplomas to advanced graduate degrees and professional certifications
- Location: Urban metropolitan areas and suburban communities across the United States, with emphasis on digitally-connected regions
- Household income: $50,000-$200,000+ annually depending on career stage and family structure
- Cultural background: Diverse professionals, families, and individuals from various ethnic and cultural communities

Psychographics:
- Values financial security, stability, and long-term wealth accumulation
- Seeks modern, convenient banking solutions that integrate with digital lifestyle
- Interested in cutting-edge digital tools, mobile access, and automated financial management
- Prefers efficiency and time-saving solutions in all financial transactions
- Values trust, reliability, and established reputation in financial institutions
- Embraces technology but also appreciates human touch for complex decisions

Needs / Jobs-to-be-done:
- Access comprehensive banking services anytime, anywhere through mobile and web platforms
- Manage personal and business finances efficiently with minimal friction and maximum transparency
- Receive personalized financial guidance tailored to individual goals and circumstances
- Save valuable time on routine banking tasks through automation and smart features
- Build wealth through savings, investments, and strategic financial planning

Pain Points:
- Frustrated by outdated banking technology that doesn't integrate with modern digital life
- Limited or expensive access to qualified financial advisors and personalized guidance
- Complicated and opaque fee structures that make it hard to understand true costs
- Difficulty managing multiple accounts across different institutions and platforms
- Lack of real-time insights into spending patterns and financial health

Goals:
- Achieve and maintain financial stability while growing wealth over time
- Simplify banking and financial management by consolidating services
- Build long-term wealth through smart saving and investment strategies
- Access premium banking services and benefits that enhance lifestyle
- Prepare for major life events like home purchase, education, retirement

Motivations:
- Driven by fundamental desire for financial independence and security
- Motivated to make optimal financial decisions that maximize returns
- Seeks peace of mind knowing finances are well-managed and secure
- Values convenience and time savings that come from efficient banking
- Desires status and recognition that comes with premium banking relationships

Buying Behaviors:
{name} typically researches banking options extensively for 2-4 weeks before making any commitment decisions. Generally price-conscious and fee-aware but definitely willing to pay premium prices for demonstrated value and superior service quality. Strong preference for digital onboarding processes that can be completed in minutes, but also appreciates availability of in-person support for complex questions or major life events. Makes final decisions based primarily on feature comprehensiveness, transparent fee structures, institutional reputation, and quality of customer service. Heavily relies on online reviews, peer recommendations from trusted sources, and detailed comparison of benefits before committing.

Communication Channels:
- Mobile banking apps with push notifications for account activity
- Email for important account updates and promotional offers
- Social media platforms for brand engagement and customer service
- Branch visits for complex needs requiring face-to-face consultation
- Online chat support for quick questions and issue resolution

Exclusion Criteria:
- Customers requiring exclusively cash-based services with no digital component
- Individuals completely unwilling or unable to use any digital banking tools
- Those seeking only basic transactional services with no growth ambitions
"""
    # Pad to meet 2000 character minimum
    if len(base) < 2000:
        base += "\n\nAdditional context: " + "x" * (2000 - len(base) - 23)
    return base


@pytest.fixture
def sample_marketing_report():
    """
    Create a sample marketing research report matching the Bank of America example.

    This fixture represents the actual data structure generated by the marketing
    formatter agent, including multiple customer profiles and product categories.
    """
    return MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Student Steve",
                narrative=create_test_narrative("Student Steve"),
                references=[
                    "https://www.ey.com/en_gl/banking-capital-markets/how-banks-can-build-stronger-relationships-with-gen-z",
                ],
            ),
            IdealCustomerProfile(
                display_name="Middle-Class Maria",
                narrative=create_test_narrative("Middle-Class Maria"),
                references=[
                    "https://www.forbes.com/advisor/banking/state-of-banking-2024/",
                ],
            ),
            IdealCustomerProfile(
                display_name="Small Business Owner Sam",
                narrative=create_test_narrative("Small Business Owner Sam"),
                references=[
                    "https://www.jpmorganchase.com/institute/research/small-business/small-business-banking-relationships",
                ],
            ),
            IdealCustomerProfile(
                display_name="High-Net-Worth Helen",
                narrative=create_test_narrative("High-Net-Worth Helen"),
                references=[
                    "https://www.capgemini.com/us-en/research/world-wealth-report/",
                ],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Consumer Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Student Steve",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Many students are unaware...",
                            brand_awareness_strategy="Introduce Bank of America...",
                            consideration_strategy="Steve compares banking options...",
                            conversion_strategy="Conversion for Steve is a quick...",
                            loyalty_strategy="Loyalty is built by providing...",
                            references=[
                                "https://www.ey.com/en_gl/banking-capital-markets/how-banks-can-build-stronger-relationships-with-gen-z",
                            ],
                        ),
                    ),
                    MarketingStrategyForProfile(
                        customer_profile_name="Middle-Class Maria",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Maria's problem isn't...",
                            brand_awareness_strategy="Position Bank of America...",
                            consideration_strategy="Maria evaluates banks...",
                            conversion_strategy="Conversion involves moving...",
                            loyalty_strategy="Loyalty is retained through...",
                            references=[
                                "https://www.forbes.com/advisor/banking/state-of-banking-2024/",
                            ],
                        ),
                    ),
                ],
            ),
            ProductCategoryMapping(
                category_name="Business Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Small Business Owner Sam",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Sam's biggest problems...",
                            brand_awareness_strategy="Position Bank of America...",
                            consideration_strategy="Sam evaluates banks...",
                            conversion_strategy="The conversion action is...",
                            loyalty_strategy="Loyalty is built on a strong...",
                            references=[
                                "https://www.jpmorganchase.com/institute/research/small-business/small-business-banking-relationships",
                            ],
                        ),
                    ),
                ],
            ),
            ProductCategoryMapping(
                category_name="Wealth Management and Institutional Services",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="High-Net-Worth Helen",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Helen is aware she needs...",
                            brand_awareness_strategy="Position Bank of America's...",
                            consideration_strategy="Helen will not be swayed...",
                            conversion_strategy="Conversion is a long-term...",
                            loyalty_strategy="Loyalty for Helen is the...",
                            references=[
                                "https://www.capgemini.com/us-en/research/world-wealth-report/",
                            ],
                        ),
                    ),
                ],
            ),
        ],
    )


def test_get_product_category_node_id_returns_correct_value(
    graph_builder, mock_neo4j_ops
):
    """
    Test that _get_product_category_node_id correctly parses Neo4j results.

    This test specifically verifies the fix for the KeyError: 0 bug.
    The bug occurred because the code incorrectly assumed Neo4j's execute_query
    returns [[{"node_id": "..."}]] but it actually returns [{"node_id": "..."}].

    The incorrect code was:
        if result and len(result[0]) > 0:
            return result[0][0]["node_id"]

    The correct code is:
        if result and len(result) > 0:
            return result[0]["node_id"]
    """
    account_id = "test_acc_456"
    category_name = "Consumer Banking"
    expected_node_id = "prod_consumer_banking_xyz"

    # Mock Neo4j response in the correct format: [{"node_id": "..."}]
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"node_id": expected_node_id}
    ]

    # Execute
    result = graph_builder._get_product_category_node_id(category_name, account_id)

    # Verify
    assert result == expected_node_id

    # Verify the query was called with correct parameters
    call_args = mock_neo4j_ops.connection.execute_query.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    assert "MATCH (pc:ProductCategory)" in query
    assert params["account_id"] == account_id
    assert params["category_name"] == category_name


def test_get_product_category_node_id_handles_not_found(graph_builder, mock_neo4j_ops):
    """
    Test that _get_product_category_node_id returns None when category not found.

    This test verifies the method handles empty result sets correctly,
    which was part of the bug fix validation.
    """
    account_id = "test_acc_789"
    category_name = "Nonexistent Category"

    # Mock Neo4j response: empty result
    mock_neo4j_ops.connection.execute_query.return_value = []

    # Execute
    result = graph_builder._get_product_category_node_id(category_name, account_id)

    # Verify
    assert result is None


@pytest.mark.skip(
    reason="Test uses obsolete methods that have been refactored. Functionality covered by batch query tests."
)
def test_build_marketing_graph_skips_invalid_product_categories(
    graph_builder, mock_neo4j_ops, sample_marketing_report
):
    """
    Test that build_marketing_graph gracefully skips product categories not in Neo4j.

    This test verifies the behavior when a product category name from the
    marketing formatter doesn't match any ProductCategory node in Neo4j.
    The system should log a warning and skip creating strategies for that
    product category, but continue processing other valid categories.
    """
    account_id = "test_acc_999"

    # Mock Neo4j responses: first category not found, others found
    mock_neo4j_ops.connection.execute_query.side_effect = [
        # First call: Consumer Banking not found
        [],
        # Second call: Business Banking found
        [{"node_id": "prod_business_banking_002"}],
        # Third call: Wealth Management found
        [{"node_id": "prod_wealth_management_003"}],
    ]

    # Mock profile creation
    profile_node_ids = {
        "Student Steve": "profile_student_steve_001",
        "Middle-Class Maria": "profile_maria_002",
        "Small Business Owner Sam": "profile_sam_003",
        "High-Net-Worth Helen": "profile_helen_004",
    }

    def mock_create_profile(profile, account_id):
        return profile_node_ids[profile.display_name]

    graph_builder._create_customer_profile_node = mock_create_profile

    # Mock strategy creation
    created_strategies = []

    def mock_create_strategies(
        profile_node_id, customer_strategy, product_category_id, account_id
    ):
        created_strategies.append(
            {
                "profile_node_id": profile_node_id,
                "customer_profile_name": customer_strategy.customer_profile_name,
                "product_category_id": product_category_id,
            }
        )

    graph_builder._create_strategy_nodes_for_customer = mock_create_strategies

    # Execute
    graph_builder.build_marketing_graph(sample_marketing_report, account_id)

    # Verify: Only strategies for Business Banking and Wealth Management were created
    # Consumer Banking strategies (Student Steve and Maria) should be skipped
    # Calculate expected count: mappings[1] (Business Banking) + mappings[2] (Wealth Management)
    expected_strategies = sum(
        len(mapping.customer_strategies)
        for mapping in sample_marketing_report.product_category_mappings[
            1:
        ]  # Skip first (Consumer Banking)
    )
    assert len(created_strategies) == expected_strategies

    # Verify Sam's strategy was created
    sam_strategies = [
        s
        for s in created_strategies
        if s["customer_profile_name"] == "Small Business Owner Sam"
    ]
    assert len(sam_strategies) == 1

    # Verify Helen's strategy was created
    helen_strategies = [
        s
        for s in created_strategies
        if s["customer_profile_name"] == "High-Net-Worth Helen"
    ]
    assert len(helen_strategies) == 1

    # Verify Student Steve and Maria strategies were NOT created
    steve_strategies = [
        s for s in created_strategies if s["customer_profile_name"] == "Student Steve"
    ]
    assert len(steve_strategies) == 0

    maria_strategies = [
        s
        for s in created_strategies
        if s["customer_profile_name"] == "Middle-Class Maria"
    ]
    assert len(maria_strategies) == 0


def test_link_product_category_to_customer_profile_returns_correct_value(
    graph_builder, mock_neo4j_ops
):
    """
    Test that _link_product_category_to_customer_profile correctly parses Neo4j results.

    This test verifies the fix for the SECOND occurrence of the KeyError: 0 bug.
    The bug was in the same pattern as _get_product_category_node_id, where the
    code incorrectly assumed Neo4j returns [[{...}]] instead of [{...}].

    Bug location: marketing_graph_builder.py line 524-528
    """
    product_category_id = "prod_banking_001"
    customer_profile_id = "profile_steve_001"
    account_id = "test_acc_456"

    # Mock Neo4j response in the correct format: [{"category": "...", "profile": "..."}]
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category": "Consumer Banking", "profile": customer_profile_id}
    ]

    # Execute
    result = graph_builder._link_product_category_to_customer_profile(
        product_category_id, customer_profile_id, account_id
    )

    # Verify
    assert result is not None
    assert result["category"] == "Consumer Banking"
    assert result["profile"] == customer_profile_id

    # Verify the query was called with correct parameters
    call_args = mock_neo4j_ops.connection.execute_query.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    assert "MATCH (pc:ProductCategory" in query
    assert "MATCH (cp:CustomerProfile" in query
    assert "IS_MARKETED_TO" in query
    assert params["category_id"] == product_category_id
    assert params["profile_id"] == customer_profile_id


def test_link_product_category_to_customer_profile_handles_failure(
    graph_builder, mock_neo4j_ops
):
    """
    Test that _link_product_category_to_customer_profile returns None on failure.

    This verifies proper handling of empty results when the link cannot be created
    (e.g., when one of the nodes doesn't exist).
    """
    product_category_id = "prod_nonexistent_001"
    customer_profile_id = "profile_steve_001"
    account_id = "test_acc_789"

    # Mock Neo4j response: empty result (nodes not found or link failed)
    mock_neo4j_ops.connection.execute_query.return_value = []

    # Execute
    result = graph_builder._link_product_category_to_customer_profile(
        product_category_id, customer_profile_id, account_id
    )

    # Verify
    assert result is None


def test_customer_profile_includes_display_name(graph_builder, mock_neo4j_ops):
    """
    Test that _create_customer_profile passes display_name to Neo4j.

    This verifies the enhancement where display_name is added to the node_data
    on line 235 of marketing_graph_builder.py. The display_name should be
    lowercased and passed as a property to the Neo4j CustomerProfile node.

    Validates:
    1. display_name is included in node_data
    2. display_name is lowercased
    3. display_name is passed to neo4j_ops.create_strategy_node
    """
    account_id = "test_acc_123"

    # Create test customer profile with display_name
    test_profile = IdealCustomerProfile(
        display_name="Recent Graduate Rachel",
        narrative=create_test_narrative("Rachel"),
        references=["https://example.com/ref1"],
    )

    # Mock the create_strategy_node method to capture the call
    mock_neo4j_ops.create_strategy_node = Mock(
        return_value={
            "node_id": "icp_test_123",
            "display_name": "recent graduate rachel",
        }
    )

    # Execute
    _ = graph_builder._create_customer_profile(test_profile, account_id)

    # Verify create_strategy_node was called
    assert mock_neo4j_ops.create_strategy_node.called
    call_args = mock_neo4j_ops.create_strategy_node.call_args

    # Verify the arguments: (node_type, node_data, account_id)
    node_type = call_args[0][0]
    node_data = call_args[0][1]
    passed_account_id = call_args[0][2]

    # Verify node type
    assert node_type == "CustomerProfile"

    # Verify account_id
    assert passed_account_id == account_id

    # Verify node_data contains display_name
    assert "display_name" in node_data
    assert node_data["display_name"] == "recent graduate rachel"  # Lowercased

    # Verify other expected fields
    assert "node_id" in node_data
    assert "description" in node_data
    assert node_data["description"] == test_profile.narrative
    assert "references" in node_data
    assert node_data["references"] == test_profile.references


def test_display_name_lowercasing(graph_builder, mock_neo4j_ops):
    """
    Test that display_name is properly lowercased.

    This ensures consistent querying and comparison of customer profiles
    in Neo4j regardless of the original casing from the LLM.
    """
    account_id = "test_acc_456"

    test_cases = [
        ("Family Manager Frank", "family manager frank"),
        ("SMALL BUSINESS OWNER SARAH", "small business owner sarah"),
        ("High Net Worth Henry", "high net worth henry"),
        ("MiXeD CaSe NaMe", "mixed case name"),
    ]

    mock_neo4j_ops.create_strategy_node = Mock(return_value={"node_id": "test_id"})

    for original_name, expected_lowercase in test_cases:
        test_profile = IdealCustomerProfile(
            display_name=original_name,
            narrative=create_test_narrative(original_name),
            references=[],
        )

        # Execute
        graph_builder._create_customer_profile(test_profile, account_id)

        # Get the last call's arguments
        call_args = mock_neo4j_ops.create_strategy_node.call_args
        node_data = call_args[0][1]

        # Verify lowercasing
        assert node_data["display_name"] == expected_lowercase


@pytest.mark.skip(
    reason="Test uses obsolete methods. Functionality now covered by Pydantic validation test."
)
def test_build_graph_with_nonexistent_profile_reference(graph_builder, mock_neo4j_ops):
    """
    Test that build_marketing_graph raises ValueError when a customer strategy
    references a profile that doesn't exist in the master profile list.

    This validates the strategy count validation that detects skipped profiles.
    """
    account_id = "test_acc_123"

    # Create report with profile reference mismatch
    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Student Steve",
                narrative=create_test_narrative("Student Steve"),
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Consumer Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Non-Existent Profile",  # Mismatch!
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Strategy text...",
                            brand_awareness_strategy="Strategy text...",
                            consideration_strategy="Strategy text...",
                            conversion_strategy="Strategy text...",
                            loyalty_strategy="Strategy text...",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock Neo4j to return a valid product category
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"node_id": "prod_consumer_banking_001"}
    ]
    mock_neo4j_ops.create_strategy_node = Mock()

    # Execute and expect ValueError
    with pytest.raises(ValueError) as exc_info:
        graph_builder.build_marketing_graph(report, account_id, "user_123")

    # Verify error message contains details
    error_msg = str(exc_info.value)
    assert "Strategy count mismatch" in error_msg
    assert "expected 1" in error_msg
    assert "created 0" in error_msg
    assert "Non-Existent Profile" in error_msg


@pytest.mark.skip(
    reason="Test uses obsolete methods. Functionality now covered by Pydantic validation test."
)
def test_build_graph_with_all_strategies_skipped(graph_builder, mock_neo4j_ops):
    """
    Test that build_marketing_graph raises ValueError when all strategies
    are skipped due to profile name mismatches.
    """
    account_id = "test_acc_456"

    # Create report where NO profiles match
    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Student Steve",
                narrative=create_test_narrative("Student Steve"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Business Owner Beth",
                narrative=create_test_narrative("Business Owner Beth"),
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Consumer Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Wrong Name 1",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="...",
                            brand_awareness_strategy="...",
                            consideration_strategy="...",
                            conversion_strategy="...",
                            loyalty_strategy="...",
                            references=[],
                        ),
                    ),
                ],
            ),
            ProductCategoryMapping(
                category_name="Business Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Wrong Name 2",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="...",
                            brand_awareness_strategy="...",
                            consideration_strategy="...",
                            conversion_strategy="...",
                            loyalty_strategy="...",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock Neo4j to return valid product categories
    mock_neo4j_ops.connection.execute_query.side_effect = [
        [{"node_id": "prod_consumer_001"}],
        [{"node_id": "prod_business_002"}],
    ]
    mock_neo4j_ops.create_strategy_node = Mock()

    # Execute and expect ValueError
    with pytest.raises(ValueError) as exc_info:
        graph_builder.build_marketing_graph(report, account_id, "user_456")

    # Verify error contains both skipped profiles
    error_msg = str(exc_info.value)
    assert "expected 2" in error_msg
    assert "created 0" in error_msg
    assert "Skipped 2 profile references" in error_msg
    assert "Wrong Name 1" in error_msg
    assert "Wrong Name 2" in error_msg


@pytest.mark.skip(
    reason="Test uses obsolete methods. Functionality now covered by Pydantic validation test."
)
def test_build_graph_with_partial_profile_matches(graph_builder, mock_neo4j_ops):
    """
    Test that build_marketing_graph raises ValueError when some (but not all)
    profile references don't match, providing detailed error information.
    """
    account_id = "test_acc_789"

    # Create report with mix of valid and invalid references
    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Student Steve",
                narrative=create_test_narrative("Student Steve"),
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Consumer Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Student Steve",  # Valid
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="...",
                            brand_awareness_strategy="...",
                            consideration_strategy="...",
                            conversion_strategy="...",
                            loyalty_strategy="...",
                            references=[],
                        ),
                    ),
                    MarketingStrategyForProfile(
                        customer_profile_name="Invalid Profile",  # Invalid
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="...",
                            brand_awareness_strategy="...",
                            consideration_strategy="...",
                            conversion_strategy="...",
                            loyalty_strategy="...",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock Neo4j responses
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"node_id": "prod_consumer_001"}
    ]
    mock_neo4j_ops.create_strategy_node = Mock()

    # Execute and expect ValueError
    with pytest.raises(ValueError) as exc_info:
        graph_builder.build_marketing_graph(report, account_id, "user_789")

    # Verify error shows partial success
    error_msg = str(exc_info.value)
    assert "expected 2" in error_msg
    assert "created 1" in error_msg
    assert "Skipped 1 profile references" in error_msg
    assert "Invalid Profile" in error_msg


def test_get_product_category_node_ids_batch_query(graph_builder, mock_neo4j_ops):
    """
    Test that _get_product_category_node_ids correctly handles batch queries.

    This test validates the fix on line 272 where the code iterates over
    result directly instead of result[0]. The batch query method returns
    multiple records in a single list: [{"category_name": "...", "node_id": "..."}, ...]
    """
    account_id = "test_acc_batch_001"
    category_names = ["Consumer Banking", "Business Banking", "Wealth Management"]

    # Mock Neo4j response with multiple records
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Consumer Banking", "node_id": "prod_consumer_001"},
        {"category_name": "Business Banking", "node_id": "prod_business_002"},
        {"category_name": "Wealth Management", "node_id": "prod_wealth_003"},
    ]

    # Execute
    result = graph_builder._get_product_category_node_ids(category_names, account_id)

    # Verify all three categories are returned correctly
    assert result == {
        "Consumer Banking": "prod_consumer_001",
        "Business Banking": "prod_business_002",
        "Wealth Management": "prod_wealth_003",
    }

    # Verify query was called with correct parameters
    call_args = mock_neo4j_ops.connection.execute_query.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    assert "MATCH (pc:ProductCategory)" in query
    assert "WHERE toLower(pc.product_name) IN" in query
    assert params["account_id"] == account_id
    assert params["category_names"] == category_names


def test_get_product_category_node_ids_empty_result(graph_builder, mock_neo4j_ops):
    """
    Test that _get_product_category_node_ids handles empty results correctly.

    When no categories match, the method should return an empty dict.
    """
    account_id = "test_acc_batch_002"
    category_names = ["Nonexistent Category"]

    # Mock Neo4j response: empty result
    mock_neo4j_ops.connection.execute_query.return_value = []

    # Execute
    result = graph_builder._get_product_category_node_ids(category_names, account_id)

    # Verify empty dict is returned
    assert result == {}


def test_get_product_category_node_ids_empty_input(graph_builder, mock_neo4j_ops):
    """
    Test that _get_product_category_node_ids handles empty input list.

    When called with an empty list, should return empty dict without querying.
    """
    account_id = "test_acc_batch_003"
    category_names = []

    # Execute
    result = graph_builder._get_product_category_node_ids(category_names, account_id)

    # Verify empty dict is returned
    assert result == {}

    # Verify no query was made
    mock_neo4j_ops.connection.execute_query.assert_not_called()


def test_get_product_category_node_ids_partial_matches(graph_builder, mock_neo4j_ops):
    """
    Test that _get_product_category_node_ids handles partial matches correctly.

    When only some categories exist in Neo4j, only those should be returned.
    """
    account_id = "test_acc_batch_004"
    category_names = ["Consumer Banking", "Nonexistent Category", "Business Banking"]

    # Mock Neo4j response: only 2 out of 3 categories found
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Consumer Banking", "node_id": "prod_consumer_001"},
        {"category_name": "Business Banking", "node_id": "prod_business_002"},
    ]

    # Execute
    result = graph_builder._get_product_category_node_ids(category_names, account_id)

    # Verify only found categories are returned
    assert result == {
        "Consumer Banking": "prod_consumer_001",
        "Business Banking": "prod_business_002",
    }
    assert "Nonexistent Category" not in result


def test_strategy_count_validation_success(graph_builder, mock_neo4j_ops):
    """
    Test that strategy count validation passes when counts match.

    Validates the validation logic on lines 215-227 for the success case.
    """
    account_id = "test_acc_count_001"

    # Create report with 2 profiles, 1 category, 1 strategy = 5 total strategy nodes
    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Student Steve",
                narrative=create_test_narrative("Student Steve"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Business Owner Beth",
                narrative=create_test_narrative("Business Owner Beth"),
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Consumer Banking",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Student Steve",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Problem strategy",
                            brand_awareness_strategy="Brand strategy",
                            consideration_strategy="Consideration strategy",
                            conversion_strategy="Conversion strategy",
                            loyalty_strategy="Loyalty strategy",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock Neo4j responses
    mock_neo4j_ops.connection.execute_query.side_effect = [
        [{"category_name": "Consumer Banking", "node_id": "prod_consumer_001"}],
        [],  # Link strategy responses (called 5 times)
        [],
        [],
        [],
        [],
        [{"category": "Consumer Banking", "profile": "icp_test"}],  # IS_MARKETED_TO
    ]
    mock_neo4j_ops.create_strategy_node = Mock()

    # Execute - should NOT raise ValueError
    result = graph_builder.build_marketing_graph(report, account_id, "user_count_001")

    # Verify all 5 strategy types were created (1 of each type)
    assert len(result["problem_awareness_strategies"]) == 1
    assert len(result["brand_awareness_strategies"]) == 1
    assert len(result["consideration_strategies"]) == 1
    assert len(result["conversion_strategies"]) == 1
    assert len(result["loyalty_strategies"]) == 1


def test_pydantic_validation_prevents_invalid_profile_references(
    graph_builder, mock_neo4j_ops
):
    """
    Test that Pydantic validation prevents invalid profile references at model creation time.

    The MarketingResearchReport model has a field validator that checks profile references
    before the data ever reaches the graph builder. This test verifies that invalid
    references are caught early by Pydantic, not later by the graph builder logic.
    """
    # Attempt to create report with invalid profile reference should fail at Pydantic level
    with pytest.raises(ValueError) as exc_info:
        MarketingResearchReport(
            ideal_customer_profiles=[
                IdealCustomerProfile(
                    display_name="Student Steve",
                    narrative=create_test_narrative("Student Steve"),
                    references=[],
                ),
                IdealCustomerProfile(
                    display_name="Business Owner Beth",
                    narrative=create_test_narrative("Business Owner Beth"),
                    references=[],
                ),
            ],
            product_category_mappings=[
                ProductCategoryMapping(
                    category_name="Consumer Banking",
                    customer_strategies=[
                        MarketingStrategyForProfile(
                            customer_profile_name="Wrong Name",  # Doesn't exist
                            strategy=MarketingStrategy(
                                problem_awareness_strategy="...",
                                brand_awareness_strategy="...",
                                consideration_strategy="...",
                                conversion_strategy="...",
                                loyalty_strategy="...",
                                references=[],
                            ),
                        ),
                    ],
                ),
            ],
        )

    # Verify Pydantic validation error contains profile name details
    error_msg = str(exc_info.value)
    assert "Wrong Name" in error_msg
    assert "Consumer Banking" in error_msg
    assert "not found in master profile list" in error_msg


# ==================== ROLLUP MARKETING STRATEGY TESTS ====================


def test_create_rollup_marketing_hub(graph_builder, mock_neo4j_ops):
    """Test that rollup marketing hub is created correctly."""
    account_id = "test_acc_123"
    user_id = "user_456"

    # Mock the execute_query to return a list with one record
    mock_neo4j_ops.connection.execute_query.return_value = [{"hub": "linked"}]

    hub_node = graph_builder._create_rollup_marketing_hub(account_id, user_id)

    # Verify node structure
    assert hub_node["node_id"] == f"rollup_marketing_hub_{account_id}"
    assert (
        hub_node["description"]
        == "Consolidated marketing strategy for the entire business"
    )
    assert hub_node["created_by"] == user_id
    assert hub_node["last_modified_by"] == user_id
    assert hub_node["embedding"] is None
    assert "created_time" in hub_node
    assert "last_modified" in hub_node

    # Verify create_strategy_node was called
    mock_neo4j_ops.create_strategy_node.assert_called_once()
    call_args = mock_neo4j_ops.create_strategy_node.call_args
    assert call_args[0][0] == "RollupMarketingStrategy"
    assert call_args[0][1]["node_id"] == f"rollup_marketing_hub_{account_id}"
    assert call_args[0][2] == account_id

    # Verify link to Account was created
    assert mock_neo4j_ops.connection.execute_query.called


def test_create_single_rollup_strategy(graph_builder, mock_neo4j_ops):
    """Test creating a single rollup strategy node."""
    config = {
        "stage": "problem_awareness",
        "node_type": "ProblemAwarenessStrategy",
        "hub_relationship": "INCREASES_PROBLEM_AWARENESS_BY",
    }

    individual_strategies = [
        {"node_id": "pas_1", "description": "Strategy 1 for profile A"},
        {"node_id": "pas_2", "description": "Strategy 2 for profile B"},
        {"node_id": "pas_3", "description": "Strategy 3 for profile C"},
    ]

    hub_node_id = "rollup_marketing_hub_test_acc"
    account_id = "test_acc_123"
    user_id = "user_456"

    rollup_node = graph_builder._create_single_rollup_strategy(
        config=config,
        individual_strategies=individual_strategies,
        hub_node_id=hub_node_id,
        account_id=account_id,
        user_id=user_id,
    )

    # Verify node structure
    # Note: .replace('_', '') removes all underscores from stage name
    assert rollup_node["node_id"] == f"rollup_problemawareness_{account_id}"
    assert rollup_node["description"] == ""  # Empty for MVP
    assert rollup_node["references"] == []
    assert rollup_node["created_by"] == user_id
    assert rollup_node["last_modified_by"] == user_id
    assert rollup_node["embedding"] is None

    # Verify relationships created (hub link + individual links)
    assert mock_neo4j_ops.connection.execute_query.call_count >= 2


def test_rollup_strategy_has_empty_description(graph_builder, mock_neo4j_ops):
    """Test that rollup strategies are created with empty descriptions for MVP."""
    config = {
        "stage": "problem_awareness",
        "node_type": "ProblemAwarenessStrategy",
        "hub_relationship": "INCREASES_PROBLEM_AWARENESS_BY",
    }

    individual_strategies = [
        {"node_id": "pas_1", "description": "Strategy 1 with content"},
        {"node_id": "pas_2", "description": "Strategy 2 with content"},
    ]

    rollup_node = graph_builder._create_single_rollup_strategy(
        config=config,
        individual_strategies=individual_strategies,
        hub_node_id="rollup_marketing_hub_test",
        account_id="test_acc",
        user_id="test_user",
    )

    # Verify description is empty string
    assert rollup_node["description"] == ""
    # Verify references is empty list
    assert rollup_node["references"] == []


def test_create_rollup_strategies_success(
    graph_builder,
    mock_neo4j_ops,
):
    """Test full rollup strategy creation flow."""
    account_id = "test_acc_123"
    user_id = "user_456"

    # Mock execute_query to return proper list for all Neo4j operations
    mock_neo4j_ops.connection.execute_query.return_value = [{"result": "success"}]

    # Create individual strategies first
    created_nodes = {
        "problem_awareness_strategies": [
            {"node_id": "pas_1", "description": "Strategy 1"},
            {"node_id": "pas_2", "description": "Strategy 2"},
        ],
        "brand_awareness_strategies": [
            {"node_id": "bas_1", "description": "Brand 1"},
        ],
        "consideration_strategies": [
            {"node_id": "cs_1", "description": "Consideration 1"},
        ],
        "conversion_strategies": [
            {"node_id": "cvs_1", "description": "Conversion 1"},
        ],
        "loyalty_strategies": [
            {"node_id": "ls_1", "description": "Loyalty 1"},
        ],
    }

    # Create minimal research report (not actually used in this test, just satisfies validation)
    from ..marketing_models import MarketingResearchReport

    research_report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Dummy Profile 1",
                narrative=create_test_narrative("Dummy 1"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Dummy Profile 2",
                narrative=create_test_narrative("Dummy 2"),
                references=[],
            ),
        ],
        product_category_mappings=[],
    )

    rollup_nodes = graph_builder._create_rollup_strategies(
        research_report=research_report,
        account_id=account_id,
        user_id=user_id,
        created_nodes=created_nodes,
    )

    # Verify structure
    assert "hub" in rollup_nodes
    assert "strategies" in rollup_nodes

    # Verify hub
    assert rollup_nodes["hub"]["node_id"] == f"rollup_marketing_hub_{account_id}"

    # Verify 5 rollup strategies created
    assert len(rollup_nodes["strategies"]) == 5
    assert "problem_awareness" in rollup_nodes["strategies"]
    assert "brand_awareness" in rollup_nodes["strategies"]
    assert "consideration" in rollup_nodes["strategies"]
    assert "conversion" in rollup_nodes["strategies"]
    assert "loyalty" in rollup_nodes["strategies"]


def test_create_rollup_strategies_fails_without_individuals(
    graph_builder,
):
    """Test that rollup creation fails if individual strategies don't exist."""
    account_id = "test_acc_123"
    user_id = "user_456"

    # Empty created_nodes
    created_nodes = {
        "problem_awareness_strategies": [],  # Empty!
        "brand_awareness_strategies": [],
        "consideration_strategies": [],
        "conversion_strategies": [],
        "loyalty_strategies": [],
    }

    # Create minimal research report (not actually used in this test, just satisfies validation)
    from ..marketing_models import MarketingResearchReport

    research_report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Dummy Profile 1",
                narrative=create_test_narrative("Dummy 1"),
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Dummy Profile 2",
                narrative=create_test_narrative("Dummy 2"),
                references=[],
            ),
        ],
        product_category_mappings=[],
    )

    with pytest.raises(ValueError, match="Cannot create rollup strategies"):
        graph_builder._create_rollup_strategies(
            research_report=research_report,
            account_id=account_id,
            user_id=user_id,
            created_nodes=created_nodes,
        )


def test_build_marketing_graph_includes_rollups(
    graph_builder,
    mock_neo4j_ops,
):
    """Test that build_marketing_graph creates rollups in Phase 3."""
    account_id = "test_acc_789"
    user_id = "user_123"

    # Create a minimal but valid report
    from ..marketing_models import (
        IdealCustomerProfile,
        MarketingResearchReport,
        MarketingStrategy,
        MarketingStrategyForProfile,
        ProductCategoryMapping,
    )

    # Create narrative with all required sections (Pydantic validation requirement)
    long_narrative = (
        """
Demographics: Test user, 25 years old, software engineer.

Psychographics: Values efficiency and modern technology.

Needs / Jobs-to-be-done: Needs reliable marketing analytics platform.

Pain Points: Current solution is too complex and expensive.

Goals: Streamline marketing operations and reduce costs.

Motivations: Wants to make data-driven decisions quickly.

Buying Behaviors: Researches online, prefers self-service trials.

Communication Channels: LinkedIn, email, product documentation.

Exclusion Criteria: Not interested in enterprise-only solutions.
    """
        * 4
    )  # Repeat to ensure >2000 characters

    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=long_narrative,
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Second Profile",
                narrative=long_narrative,
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Test Category",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Test Profile",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Test strategy",
                            brand_awareness_strategy="Test strategy",
                            consideration_strategy="Test strategy",
                            conversion_strategy="Test strategy",
                            loyalty_strategy="Test strategy",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock product categories exist
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Test Category", "node_id": "pc_001"},
    ]

    result = graph_builder.build_marketing_graph(
        report,
        account_id,
        user_id,
    )

    # Verify rollups were created
    assert "rollup_marketing_hub" in result
    assert "rollup_strategies" in result

    # Verify hub exists
    assert result["rollup_marketing_hub"] is not None
    assert result["rollup_marketing_hub"]["node_id"].startswith("rollup_marketing_hub_")

    # Verify 5 rollup strategies
    assert len(result["rollup_strategies"]) == 5


def test_build_marketing_graph_rollup_failure_is_non_critical(
    graph_builder,
    mock_neo4j_ops,
    caplog,
):
    """Test that rollup creation failure doesn't fail entire graph build."""
    account_id = "test_acc_999"
    user_id = "user_999"

    # Create a minimal but valid report
    from ..marketing_models import (
        IdealCustomerProfile,
        MarketingResearchReport,
        MarketingStrategy,
        MarketingStrategyForProfile,
        ProductCategoryMapping,
    )

    # Create narrative with all required sections (Pydantic validation requirement)
    long_narrative = (
        """
Demographics: Test user, 25 years old, software engineer.

Psychographics: Values efficiency and modern technology.

Needs / Jobs-to-be-done: Needs reliable marketing analytics platform.

Pain Points: Current solution is too complex and expensive.

Goals: Streamline marketing operations and reduce costs.

Motivations: Wants to make data-driven decisions quickly.

Buying Behaviors: Researches online, prefers self-service trials.

Communication Channels: LinkedIn, email, product documentation.

Exclusion Criteria: Not interested in enterprise-only solutions.
    """
        * 4
    )  # Repeat to ensure >2000 characters

    report = MarketingResearchReport(
        ideal_customer_profiles=[
            IdealCustomerProfile(
                display_name="Test Profile",
                narrative=long_narrative,
                references=[],
            ),
            IdealCustomerProfile(
                display_name="Second Profile",
                narrative=long_narrative,
                references=[],
            ),
        ],
        product_category_mappings=[
            ProductCategoryMapping(
                category_name="Test Category",
                customer_strategies=[
                    MarketingStrategyForProfile(
                        customer_profile_name="Test Profile",
                        strategy=MarketingStrategy(
                            problem_awareness_strategy="Test strategy",
                            brand_awareness_strategy="Test strategy",
                            consideration_strategy="Test strategy",
                            conversion_strategy="Test strategy",
                            loyalty_strategy="Test strategy",
                            references=[],
                        ),
                    ),
                ],
            ),
        ],
    )

    # Mock product categories
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Test Category", "node_id": "pc_001"},
    ]

    # Mock rollup creation to fail
    def side_effect(*args, **kwargs):
        if args and args[0] == "RollupMarketingStrategy":
            raise Exception("Rollup creation failed!")
        return []

    mock_neo4j_ops.create_strategy_node.side_effect = side_effect

    # Should NOT raise exception
    result = graph_builder.build_marketing_graph(
        report,
        account_id,
        user_id,
    )

    # Verify individual strategies still created
    assert len(result["problem_awareness_strategies"]) > 0

    # Verify warning was logged
    assert "Failed to create rollup strategies" in caplog.text
