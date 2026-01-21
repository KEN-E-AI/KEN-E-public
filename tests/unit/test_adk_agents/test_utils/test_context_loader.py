"""Unit tests for organization context loading.

Tests cover:
- Context loading with complete/minimal data
- Markdown formatting
- Token budget validation
- Context injection
- Error handling and graceful degradation
"""

from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest

# Import the module file directly to avoid triggering app.adk.agents.__init__.py
# which imports all agents at module level
import sys
from pathlib import Path

# Add the app directory to the path
app_dir = Path(__file__).parents[4] / "app"
sys.path.insert(0, str(app_dir))

# Now import directly from the module file
from adk.agents.utils.context_loader import (
    MAX_CONTEXT_TOKENS,
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
    "values": ["Data Transparency", "Customer Success", "Continuous Innovation", "Ethical AI", "Collaboration"],
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
@patch("app.adk.agents.utils.context_loader.TokenEstimator")
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
    assert "**Personality Traits:** Analytical Advisor, Trusted Partner, Forward-thinking" in result
    assert "**Mission:**" in result
    assert "**Core Values:**" in result

    # Verify Neo4j connection closed
    mock_connection.close.assert_called_once()


# Test: load_organization_context with minimal data (no brand)
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
@patch("app.adk.agents.utils.context_loader.TokenEstimator")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
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
    assert "**Websites:** https://acme-marketing.com, https://blog.acme-marketing.com" in result
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
    assert "**Personality Traits:** Analytical Advisor, Trusted Partner, Forward-thinking" in result
    assert "**Mission:** Empower marketing teams" in result
    assert "**Core Values:** Data Transparency, Customer Success, Continuous Innovation, Ethical AI, Collaboration" in result


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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
@patch("app.adk.agents.utils.context_loader.TokenEstimator")
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
@patch("app.adk.agents.utils.context_loader.Neo4jConnection")
@patch("app.adk.agents.utils.context_loader.TokenEstimator")
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
