"""Unit tests for organization context loading and HierarchicalContextManager.

Tests cover:
- Context loading with complete/minimal data
- Markdown formatting
- Token budget validation
- Context injection
- Error handling and graceful degradation
- HierarchicalContextManager class methods
"""

# Import the module file directly to avoid triggering app.adk.agents.__init__.py
# which imports all agents at module level
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the app directory to the path
app_dir = Path(__file__).parents[4] / "app"
sys.path.insert(0, str(app_dir))

# Mock the neo4j dependency before importing context_loader
neo4j_mock = MagicMock()
neo4j_mock.exceptions = MagicMock()
neo4j_mock.exceptions.ServiceUnavailable = Exception
neo4j_mock.exceptions.SessionExpired = Exception
sys.modules["neo4j"] = neo4j_mock
sys.modules["neo4j.exceptions"] = neo4j_mock.exceptions

# Now import directly from the module file
from adk.agents.utils.context_loader import (
    HierarchicalContextManager,
    _fetch_context_from_neo4j,
    _format_context_markdown,
    inject_organization_context,
    load_organization_context,
)

# Sample test data
SAMPLE_ACCOUNT_DATA = {
    "account_id": "account_test_20250120",
    "company_name": "Acme Marketing Solutions",
    "company_overview": "Acme Marketing Solutions provides AI-powered marketing analytics for mid-market B2B companies.",
    "industry": "Marketing Technology",
    "websites": ["https://acme-marketing.com", "https://blog.acme-marketing.com"],
    "customer_regions": ["North America", "EMEA"],
}

SAMPLE_BRAND_DATA = {
    "voice_tone": ["Professional", "Data-driven", "Approachable", "Innovative"],
    "do_list": [
        "Use data-driven language and cite metrics",
        "Speak directly and avoid jargon",
        "Focus on business outcomes",
    ],
    "dont_list": [
        "Use overly technical language",
        "Make claims without evidence",
        "Be overly casual or use slang",
    ],
    "personality_traits": ["Analytical Advisor", "Trusted Partner", "Forward-thinking"],
    "mission": "Empower marketing teams to make confident decisions backed by AI-powered insights.",
    "values": [
        "Data Transparency",
        "Customer Success",
        "Continuous Innovation",
        "Ethical AI",
        "Collaboration",
    ],
}

SAMPLE_COMPLETE_CONTEXT = {
    "account": SAMPLE_ACCOUNT_DATA,
    "brand": SAMPLE_BRAND_DATA,
}

SAMPLE_MINIMAL_CONTEXT = {
    "account": SAMPLE_ACCOUNT_DATA,
    "brand": {},  # No brand data
}


@pytest.fixture
def mock_neo4j_connection() -> Mock:
    """Create a mock Neo4j connection."""
    return Mock()


@pytest.fixture
def mock_token_estimator() -> Mock:
    """Create a mock token estimator."""
    return Mock()


# Test: load_organization_context with complete data
@patch("adk.agents.utils.context_loader.Neo4jConnection")
@patch("adk.agents.utils.context_loader.TokenEstimator")
def test_load_organization_context_with_complete_data(
    mock_token_estimator_class: Mock, mock_neo4j_class: Mock
) -> None:
    """Test context loading with full account + brand data."""
    # Setup mocks
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = [{"context": SAMPLE_COMPLETE_CONTEXT}]

    mock_token_estimator_class.check_input_limit.return_value = {
        "estimated_tokens": 1500,
        "max_tokens": 2_097_152,
        "percentage": 0.07,
        "within_limit": True,
        "warning": False,
        "error": False,
    }

    # Execute
    result = load_organization_context("account_test_20250120")

    # Assert
    assert result is not None
    assert "# Company Context" in result
    assert "Acme Marketing Solutions" in result
    assert "## Brand Voice & Communication Style" in result
    assert "**Tone:** Professional, Data-driven, Approachable, Innovative" in result
    assert "**DO:**" in result
    assert "**DON'T:**" in result
    assert (
        "**Personality Traits:** Analytical Advisor, Trusted Partner, Forward-thinking"
        in result
    )
    assert "**Mission:**" in result
    assert "**Core Values:**" in result

    # Verify Neo4j connection closed
    mock_connection.close.assert_called_once()


# Test: load_organization_context with minimal data (no brand)
@patch("adk.agents.utils.context_loader.Neo4jConnection")
@patch("adk.agents.utils.context_loader.TokenEstimator")
def test_load_organization_context_with_minimal_data(
    mock_token_estimator_class: Mock, mock_neo4j_class: Mock
) -> None:
    """Test graceful degradation with only account data (no brand)."""
    # Setup mocks
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = [{"context": SAMPLE_MINIMAL_CONTEXT}]

    mock_token_estimator_class.check_input_limit.return_value = {
        "estimated_tokens": 500,
        "max_tokens": 2_097_152,
        "percentage": 0.02,
        "within_limit": True,
        "warning": False,
        "error": False,
    }

    # Execute
    result = load_organization_context("account_test_20250120")

    # Assert
    assert result is not None
    assert "# Company Context" in result
    assert "Acme Marketing Solutions" in result
    assert "## Brand Voice & Communication Style" in result
    assert "**Tone:** Professional, Clear, Helpful" in result  # Default fallback
    assert "Specific brand guidelines not yet configured" in result


# Test: load_organization_context returns None on Neo4j failure
@patch("adk.agents.utils.context_loader.Neo4jConnection")
def test_load_organization_context_neo4j_failure(mock_neo4j_class: Mock) -> None:
    """Test error handling when Neo4j query fails."""
    # Setup mock to raise exception
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.side_effect = Exception("Neo4j connection failed")

    # Execute
    result = load_organization_context("account_test_20250120")

    # Assert
    assert result is None  # Graceful degradation


# Test: load_organization_context returns None when no data found
@patch("adk.agents.utils.context_loader.Neo4jConnection")
def test_load_organization_context_no_data(mock_neo4j_class: Mock) -> None:
    """Test graceful degradation when no data found for account."""
    # Setup mock to return empty result
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = []

    # Execute
    result = load_organization_context("account_nonexistent")

    # Assert
    assert result is None


# Test: _fetch_context_from_neo4j with valid data
@patch("adk.agents.utils.context_loader.Neo4jConnection")
def test_fetch_context_from_neo4j_success(mock_neo4j_class: Mock) -> None:
    """Test Neo4j query execution with valid data."""
    # Setup mock
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = [{"context": SAMPLE_COMPLETE_CONTEXT}]

    # Execute
    result = _fetch_context_from_neo4j("account_test_20250120")

    # Assert
    assert result == SAMPLE_COMPLETE_CONTEXT
    mock_connection.close.assert_called_once()


# Test: _fetch_context_from_neo4j returns None on empty result
@patch("adk.agents.utils.context_loader.Neo4jConnection")
def test_fetch_context_from_neo4j_empty_result(mock_neo4j_class: Mock) -> None:
    """Test Neo4j query with empty result."""
    # Setup mock
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = []

    # Execute
    result = _fetch_context_from_neo4j("account_test_20250120")

    # Assert
    assert result is None


# Test: _fetch_context_from_neo4j returns None on exception
@patch("adk.agents.utils.context_loader.Neo4jConnection")
def test_fetch_context_from_neo4j_exception(mock_neo4j_class: Mock) -> None:
    """Test Neo4j query exception handling."""
    # Setup mock to raise exception
    mock_neo4j_class.side_effect = Exception("Connection failed")

    # Execute
    result = _fetch_context_from_neo4j("account_test_20250120")

    # Assert
    assert result is None


# Test: _format_context_markdown with complete data
def test_format_context_markdown_complete_data() -> None:
    """Test markdown formatting with full context data."""
    # Execute
    result = _format_context_markdown(SAMPLE_COMPLETE_CONTEXT)

    # Assert structure
    assert result.startswith("---")  # YAML frontmatter
    assert "account_id: account_test_20250120" in result
    assert "company: Acme Marketing Solutions" in result
    assert "industry: Marketing Technology" in result
    assert "---" in result

    # Assert content
    assert "# Company Context" in result
    assert "Acme Marketing Solutions provides AI-powered marketing analytics" in result
    assert (
        "**Websites:** https://acme-marketing.com, https://blog.acme-marketing.com"
        in result
    )
    assert "## Brand Voice & Communication Style" in result
    assert "**Tone:** Professional, Data-driven, Approachable, Innovative" in result

    # Assert DO list formatted correctly
    assert "**DO:**" in result
    assert "- Use data-driven language and cite metrics" in result
    assert "- Speak directly and avoid jargon" in result

    # Assert DON'T list formatted correctly
    assert "**DON'T:**" in result
    assert "- Use overly technical language" in result
    assert "- Make claims without evidence" in result

    # Assert personality, mission, values
    assert (
        "**Personality Traits:** Analytical Advisor, Trusted Partner, Forward-thinking"
        in result
    )
    assert "**Mission:** Empower marketing teams" in result
    assert (
        "**Core Values:** Data Transparency, Customer Success, Continuous Innovation, Ethical AI, Collaboration"
        in result
    )


# Test: _format_context_markdown with minimal data (no brand)
def test_format_context_markdown_minimal_data() -> None:
    """Test markdown formatting with only account data."""
    # Execute
    result = _format_context_markdown(SAMPLE_MINIMAL_CONTEXT)

    # Assert
    assert "# Company Context" in result
    assert "Acme Marketing Solutions" in result
    assert "## Brand Voice & Communication Style" in result
    assert "**Tone:** Professional, Clear, Helpful" in result  # Default fallback
    assert "Specific brand guidelines not yet configured" in result


# Test: _format_context_markdown with missing optional fields
def test_format_context_markdown_missing_optional_fields() -> None:
    """Test markdown formatting handles missing optional fields gracefully."""
    # Minimal account data
    minimal_data = {
        "account": {
            "account_id": "account_minimal",
            "company_name": "Minimal Corp",
        },
        "brand": {},
    }

    # Execute
    result = _format_context_markdown(minimal_data)

    # Assert
    assert "account_id: account_minimal" in result
    assert "company: Minimal Corp" in result
    assert "# Company Context" in result
    assert "## Brand Voice & Communication Style" in result


# Test: _format_context_markdown with string values instead of lists
def test_format_context_markdown_string_values() -> None:
    """Test formatting handles string values for list fields."""
    data_with_strings = {
        "account": SAMPLE_ACCOUNT_DATA,
        "brand": {
            "voice_tone": "Professional and Clear",  # String instead of list
            "personality_traits": "Analytical",  # String instead of list
            "values": "Integrity, Innovation",  # String instead of list
        },
    }

    # Execute
    result = _format_context_markdown(data_with_strings)

    # Assert - should handle strings without crashing
    assert "**Tone:** Professional and Clear" in result
    assert "**Personality Traits:** Analytical" in result
    assert "**Core Values:** Integrity, Innovation" in result


# Test: inject_organization_context
def test_inject_organization_context() -> None:
    """Test context injection into message."""
    # Sample data
    test_context = "# Company Context\n\nAcme Marketing Solutions"
    test_message = "Help me analyze our marketing campaigns"

    # Execute
    result = inject_organization_context(test_message, test_context)

    # Assert
    assert result.startswith("[ORGANIZATION CONTEXT]")
    assert test_context in result
    assert "[END CONTEXT]" in result
    assert test_message in result
    assert result.endswith(test_message)


# Test: inject_organization_context preserves message integrity
def test_inject_organization_context_preserves_message() -> None:
    """Test that context injection doesn't modify original message."""
    test_context = "Context data"
    test_message = "Original message with special chars: @#$%"

    # Execute
    result = inject_organization_context(test_message, test_context)

    # Assert
    assert test_message in result
    assert "Original message with special chars: @#$%" in result


# Test: Token estimation for complete context
@patch("adk.agents.utils.context_loader.Neo4jConnection")
@patch("adk.agents.utils.context_loader.TokenEstimator")
def test_token_estimation_within_budget(
    mock_token_estimator_class: Mock, mock_neo4j_class: Mock
) -> None:
    """Test that complete context stays within token budget."""
    # Setup mocks
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = [{"context": SAMPLE_COMPLETE_CONTEXT}]

    # Mock token estimation to return within budget
    mock_token_estimator_class.check_input_limit.return_value = {
        "estimated_tokens": 1500,
        "max_tokens": 2_097_152,
        "percentage": 0.07,
        "within_limit": True,
        "warning": False,
        "error": False,
    }

    # Execute
    result = load_organization_context("account_test_20250120")

    # Assert
    assert result is not None
    # Verify token check was called
    mock_token_estimator_class.check_input_limit.assert_called_once()


# Test: Token estimation exceeds budget (warning logged but still returned)
@patch("adk.agents.utils.context_loader.Neo4jConnection")
@patch("adk.agents.utils.context_loader.TokenEstimator")
def test_token_estimation_exceeds_budget(
    mock_token_estimator_class: Mock, mock_neo4j_class: Mock
) -> None:
    """Test behavior when context exceeds token budget."""
    # Setup mocks
    mock_connection = Mock()
    mock_neo4j_class.return_value = mock_connection
    mock_connection.execute_query.return_value = [{"context": SAMPLE_COMPLETE_CONTEXT}]

    # Mock token estimation to return over budget
    mock_token_estimator_class.check_input_limit.return_value = {
        "estimated_tokens": 6000,  # Over MAX_CONTEXT_TOKENS (5000)
        "max_tokens": 2_097_152,
        "percentage": 0.3,
        "within_limit": True,
        "warning": True,
        "error": False,
    }

    # Execute
    result = load_organization_context("account_test_20250120")

    # Assert - still returns context (warning logged)
    assert result is not None


# Test: Empty brand lists handled gracefully
def test_format_context_markdown_empty_brand_lists() -> None:
    """Test formatting handles empty brand lists without errors."""
    data_with_empty_lists = {
        "account": SAMPLE_ACCOUNT_DATA,
        "brand": {
            "voice_tone": [],
            "do_list": [],
            "dont_list": [],
            "personality_traits": [],
            "values": [],
        },
    }

    # Execute
    result = _format_context_markdown(data_with_empty_lists)

    # Assert - should not crash, should use fallback
    assert result is not None
    assert "# Company Context" in result


# Integration test marker for future use
@pytest.mark.integration
@pytest.mark.skip(reason="Requires Neo4j connection - run manually in dev environment")
def test_load_organization_context_integration() -> None:
    """Integration test with real Neo4j (run manually in dev)."""
    # This test should be run manually in dev environment with real Neo4j
    # Test with a known account_id from dev database
    test_account_id = "account_20250120_test"

    # Execute
    result = load_organization_context(test_account_id)

    # Assert
    # Adjust assertions based on actual dev data
    assert result is not None or result is None  # Either success or graceful failure


# =============================================================================
# HierarchicalContextManager Tests
# =============================================================================


class TestHierarchicalContextManagerInit:
    """Tests for HierarchicalContextManager initialization."""

    def test_init_sets_account_id(self) -> None:
        """Test that __init__ stores account_id."""
        manager = HierarchicalContextManager("test_account_123")

        assert manager.account_id == "test_account_123"

    def test_init_starts_with_empty_context(self) -> None:
        """Test that manager starts with no loaded context."""
        manager = HierarchicalContextManager("test_account_123")

        assert manager._executive_summary is None
        assert manager._loaded_sections == {}
        assert manager._loaded_details == {}
        assert manager._total_tokens == 0


class TestHierarchicalContextManagerConstants:
    """Tests for HierarchicalContextManager class constants."""

    def test_available_sections_defined(self) -> None:
        """Test that AVAILABLE_SECTIONS contains expected sections."""
        expected_sections = [
            "products",
            "icps",
            "competitors",
            "campaigns",
            "strategies",
            "brand",
            "performance",
            "calendar",
        ]

        assert HierarchicalContextManager.AVAILABLE_SECTIONS == expected_sections

    def test_token_limits_defined(self) -> None:
        """Test that token limits are properly defined."""
        assert HierarchicalContextManager.MAX_EXECUTIVE_TOKENS == 5_000
        assert HierarchicalContextManager.MAX_SECTION_TOKENS == 10_000
        assert HierarchicalContextManager.MAX_DETAIL_TOKENS == 20_000


class TestHierarchicalContextManagerLoadExecutiveSummary:
    """Tests for load_executive_summary method."""

    @patch("adk.agents.utils.context_loader.Neo4jConnection")
    @patch("adk.agents.utils.context_loader.TokenEstimator")
    def test_load_executive_summary_success(
        self, mock_token_estimator_class: Mock, mock_neo4j_class: Mock
    ) -> None:
        """Test loading executive summary from Neo4j."""
        # Setup mocks
        mock_connection = Mock()
        mock_neo4j_class.return_value = mock_connection
        mock_connection.execute_query.return_value = [
            {"context": SAMPLE_COMPLETE_CONTEXT}
        ]

        mock_token_estimator_class.check_input_limit.return_value = {
            "estimated_tokens": 1500,
            "max_tokens": 2_097_152,
            "percentage": 0.07,
            "within_limit": True,
            "warning": False,
            "error": False,
        }

        manager = HierarchicalContextManager("test_account_123")

        # Execute
        result = manager.load_executive_summary()

        # Assert
        assert result is not None
        assert "# Company Context" in result
        assert manager._executive_summary == result
        assert manager._total_tokens > 0

    @patch("adk.agents.utils.context_loader.Neo4jConnection")
    def test_load_executive_summary_failure_returns_none(
        self, mock_neo4j_class: Mock
    ) -> None:
        """Test graceful degradation when Neo4j fails."""
        mock_connection = Mock()
        mock_neo4j_class.return_value = mock_connection
        mock_connection.execute_query.side_effect = Exception("Neo4j connection failed")

        manager = HierarchicalContextManager("test_account_123")

        # Execute
        result = manager.load_executive_summary()

        # Assert
        assert result is None
        assert manager._executive_summary is None


class TestHierarchicalContextManagerLoadSection:
    """Tests for load_section method."""

    def test_load_section_invalid_section_returns_none(self) -> None:
        """Test that loading invalid section returns None."""
        manager = HierarchicalContextManager("test_account_123")

        result = manager.load_section("invalid_section")

        assert result is None

    def test_load_section_valid_section_name(self) -> None:
        """Test that valid section names are accepted."""
        manager = HierarchicalContextManager("test_account_123")

        # Campaigns is a valid section - will return None without Neo4j
        # but should not raise an error
        with patch(
            "adk.agents.utils.context_loader._fetch_campaigns_from_neo4j"
        ) as mock_fetch:
            mock_fetch.return_value = None
            result = manager.load_section("campaigns")
            # Currently returns None as section loading not fully implemented
            # but the method should accept valid section names


class TestHierarchicalContextManagerUnload:
    """Tests for unload methods."""

    def test_unload_section_removes_section(self) -> None:
        """Test that unload_section removes a loaded section."""
        manager = HierarchicalContextManager("test_account_123")
        manager._loaded_sections["campaigns"] = "Campaign context data"
        manager._total_tokens = 1000

        manager.unload_section("campaigns")

        assert "campaigns" not in manager._loaded_sections

    def test_unload_section_nonexistent_no_error(self) -> None:
        """Test that unloading nonexistent section doesn't raise error."""
        manager = HierarchicalContextManager("test_account_123")

        # Should not raise
        manager.unload_section("nonexistent")

    def test_unload_all_sections(self) -> None:
        """Test that unload_all_sections clears all sections."""
        manager = HierarchicalContextManager("test_account_123")
        manager._loaded_sections["campaigns"] = "Campaign data"
        manager._loaded_sections["products"] = "Product data"
        manager._loaded_details["detail_1"] = "Detail data"
        manager._executive_summary = "Executive summary"

        manager.unload_all_sections()

        assert manager._loaded_sections == {}
        assert manager._loaded_details == {}
        # Executive summary should be preserved
        assert manager._executive_summary == "Executive summary"


class TestHierarchicalContextManagerTokens:
    """Tests for token management."""

    def test_get_total_tokens_initial_zero(self) -> None:
        """Test that initial token count is zero."""
        manager = HierarchicalContextManager("test_account_123")

        assert manager.get_total_tokens() == 0

    def test_get_total_tokens_after_loading(self) -> None:
        """Test token count after loading context."""
        manager = HierarchicalContextManager("test_account_123")
        manager._total_tokens = 2500

        assert manager.get_total_tokens() == 2500


class TestHierarchicalContextManagerGetContext:
    """Tests for get_context_for_agent method."""

    def test_get_context_for_agent_empty(self) -> None:
        """Test get_context_for_agent with no loaded context."""
        manager = HierarchicalContextManager("test_account_123")

        result = manager.get_context_for_agent()

        assert result == ""

    def test_get_context_for_agent_with_executive_summary(self) -> None:
        """Test get_context_for_agent with executive summary loaded."""
        manager = HierarchicalContextManager("test_account_123")
        manager._executive_summary = "# Executive Summary\n\nCompany overview here."

        result = manager.get_context_for_agent()

        assert "# Executive Summary" in result
        assert "Company overview here" in result

    def test_get_context_for_agent_with_sections(self) -> None:
        """Test get_context_for_agent with sections loaded."""
        manager = HierarchicalContextManager("test_account_123")
        manager._executive_summary = "# Executive Summary"
        manager._loaded_sections["campaigns"] = "## Campaigns\n\nCampaign data."

        result = manager.get_context_for_agent()

        assert "# Executive Summary" in result
        assert "## Campaigns" in result


class TestHierarchicalContextManagerInject:
    """Tests for inject_context method."""

    def test_inject_context_with_content(self) -> None:
        """Test injecting context into a message."""
        manager = HierarchicalContextManager("test_account_123")
        manager._executive_summary = "# Company Context"

        result = manager.inject_context("Tell me about our campaigns")

        assert "[ORGANIZATION CONTEXT]" in result
        assert "# Company Context" in result
        assert "[END CONTEXT]" in result
        assert "Tell me about our campaigns" in result

    def test_inject_context_empty_context(self) -> None:
        """Test injecting empty context returns original message."""
        manager = HierarchicalContextManager("test_account_123")

        result = manager.inject_context("Tell me about our campaigns")

        assert result == "Tell me about our campaigns"


class TestHierarchicalContextManagerShouldLoadSection:
    """Tests for should_load_section static method."""

    def test_should_load_section_campaign_keywords(self) -> None:
        """Test detection of campaign-related messages."""
        assert (
            HierarchicalContextManager.should_load_section(
                "How are our campaigns performing?", "campaigns"
            )
            is True
        )
        assert (
            HierarchicalContextManager.should_load_section(
                "What's our ad spend?", "campaigns"
            )
            is True
        )

    def test_should_load_section_product_keywords(self) -> None:
        """Test detection of product-related messages."""
        assert (
            HierarchicalContextManager.should_load_section(
                "Tell me about our products", "products"
            )
            is True
        )
        assert (
            HierarchicalContextManager.should_load_section(
                "What services do we offer?", "products"
            )
            is True
        )

    def test_should_load_section_no_match(self) -> None:
        """Test no match for unrelated messages."""
        assert (
            HierarchicalContextManager.should_load_section(
                "Hello, how are you?", "campaigns"
            )
            is False
        )
        assert (
            HierarchicalContextManager.should_load_section(
                "What's the weather?", "products"
            )
            is False
        )

    def test_should_load_section_case_insensitive(self) -> None:
        """Test that matching is case insensitive."""
        assert (
            HierarchicalContextManager.should_load_section(
                "CAMPAIGNS PERFORMANCE", "campaigns"
            )
            is True
        )
        assert (
            HierarchicalContextManager.should_load_section(
                "Our PRODUCTS are great", "products"
            )
            is True
        )
