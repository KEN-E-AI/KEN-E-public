"""
Basic unit tests for strategy agent creation - Quick implementation for immediate coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import StrategyContext


class TestCriticalAgentFeatures:
    """Critical tests that must pass before deployment."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock StrategyContext for testing."""
        return StrategyContext(
            company_name="TestCompany",
            websites=["https://testcompany.com"],
            industry="Technology",
            customer_regions=["North America"],
            annual_ad_budget="$1M-$5M",
            account_id="test_123",
            tenant_id="tenant_456",
        )

    @patch("agents.get_best_practices_sync")
    @patch("agents.extract_field_requirements_from_best_practices")
    def test_strategists_use_pro_model(
        self, mock_extract, mock_best_practices, mock_context
    ):
        """CRITICAL: Ensure all strategists use expensive Pro model for quality."""
        from agents import (
            create_business_strategist,
            create_competitive_strategist,
            create_customer_strategist,
            create_marketing_strategist,
            create_brand_strategist,
        )

        mock_best_practices.return_value = '{"test": "data"}'
        mock_extract.return_value = "test requirements"

        # Test all strategists
        strategists = [
            create_business_strategist,
            create_competitive_strategist,
            create_customer_strategist,
            create_marketing_strategist,
            create_brand_strategist,
        ]

        for strategist_func in strategists:
            agent = strategist_func(mock_context)
            assert agent.model == "gemini-2.5-pro", (
                f"{strategist_func.__name__} must use gemini-2.5-pro"
            )
            assert agent.generate_content_config.max_output_tokens == 65535

    @patch("agents.get_reviewer_guidelines_sync")
    def test_reviewers_use_flash_model(self, mock_guidelines):
        """CRITICAL: Ensure all reviewers use cheaper Flash model for cost optimization."""
        from agents import (
            create_business_reviewer,
            create_competitive_reviewer,
            create_customer_reviewer,
            create_marketing_reviewer,
            create_brand_reviewer,
        )

        mock_guidelines.return_value = "test guidelines"

        # Test all reviewers
        reviewers = [
            create_business_reviewer,
            create_competitive_reviewer,
            create_customer_reviewer,
            create_marketing_reviewer,
            create_brand_reviewer,
        ]

        for reviewer_func in reviewers:
            agent = reviewer_func()
            assert agent.model == "gemini-2.5-flash", (
                f"{reviewer_func.__name__} must use gemini-2.5-flash"
            )

    @patch("agents.get_best_practices_sync")
    @patch("agents.extract_field_requirements_from_best_practices")
    def test_editors_use_flash_model(self, mock_extract, mock_best_practices):
        """CRITICAL: Ensure all editors use cheaper Flash model for cost optimization."""
        from agents import (
            create_business_editor,
            create_competitive_editor,
            create_customer_editor,
            create_marketing_editor,
            create_brand_editor,
        )

        mock_best_practices.return_value = "test practices"
        mock_extract.return_value = "test requirements"

        # Test all editors
        editors = [
            create_business_editor,
            create_competitive_editor,
            create_customer_editor,
            create_marketing_editor,
            create_brand_editor,
        ]

        for editor_func in editors:
            agent = editor_func()
            assert agent.model == "gemini-2.5-flash", (
                f"{editor_func.__name__} must use gemini-2.5-flash"
            )

    @patch("agents.get_best_practices_sync")
    @patch("agents.extract_field_requirements_from_best_practices")
    def test_cascading_document_review(
        self, mock_extract, mock_best_practices, mock_context
    ):
        """CRITICAL: Ensure each agent reviews prior documents in cascade."""
        from agents import (
            create_competitive_strategist,
            create_customer_strategist,
            create_marketing_strategist,
        )

        mock_best_practices.return_value = '{"test": "data"}'
        mock_extract.return_value = "test requirements"

        # Competitive should review business_strategy_doc
        competitive = create_competitive_strategist(mock_context)
        assert "business_strategy_doc" in competitive.instruction
        assert (
            "Review Prior Analysis" in competitive.instruction
            or "BUSINESS STRATEGY" in competitive.instruction
        )

        # Customer should review both business and competitive
        customer = create_customer_strategist(mock_context)
        assert "business_strategy_doc" in customer.instruction
        assert "competitive_strategy_doc" in customer.instruction

        # Marketing should review all three prior docs
        marketing = create_marketing_strategist(mock_context)
        assert "business_strategy_doc" in marketing.instruction
        assert "competitive_strategy_doc" in marketing.instruction
        assert "customer_strategy_doc" in marketing.instruction

    @patch("agents.get_best_practices_sync")
    @patch("agents.extract_field_requirements_from_best_practices")
    def test_firestore_fallback(self, mock_extract, mock_best_practices, mock_context):
        """CRITICAL: Ensure agents handle Firestore unavailability gracefully."""
        from agents import create_business_strategist

        # Simulate Firestore unavailable
        mock_best_practices.return_value = None
        mock_extract.return_value = ""

        # Should not crash, should use defaults
        agent = create_business_strategist(mock_context)

        assert agent is not None
        assert agent.name == "business_strategist"
        assert (
            "Create a comprehensive" in agent.instruction
            or "default" in agent.instruction.lower()
        )

    @patch("agents.get_best_practices_sync")
    @patch("agents.extract_field_requirements_from_best_practices")
    def test_output_keys_for_state_management(
        self, mock_extract, mock_best_practices, mock_context
    ):
        """CRITICAL: Ensure all agents have correct output keys for state management."""
        from agents import (
            create_business_strategist,
            create_competitive_strategist,
            create_customer_strategist,
            create_marketing_strategist,
            create_brand_strategist,
        )

        mock_best_practices.return_value = '{"test": "data"}'
        mock_extract.return_value = "test requirements"

        expected_keys = {
            create_business_strategist: "business_strategy_doc",
            create_competitive_strategist: "competitive_strategy_doc",
            create_customer_strategist: "customer_strategy_doc",
            create_marketing_strategist: "marketing_strategy_doc",
            create_brand_strategist: "brand_guidelines_doc",
        }

        for func, expected_key in expected_keys.items():
            agent = func(mock_context)
            assert agent.output_key == expected_key, (
                f"{func.__name__} should have output_key={expected_key}"
            )

    def test_google_search_agent_configuration(self):
        """Test Google search agent has correct configuration."""
        from agents import create_google_search_agent

        agent = create_google_search_agent()

        assert agent.name == "google_search_agent"
        assert agent.model == "gemini-2.5-flash"  # Should use Flash for cost
        assert agent.generate_content_config.temperature == 0.2
        assert agent.generate_content_config.max_output_tokens == 8192


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
