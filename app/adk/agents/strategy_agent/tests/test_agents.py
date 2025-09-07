"""
Unit tests for strategy agent creation functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

from ..models import StrategyContext
from ..agents import (
    create_google_search_agent,
    create_business_strategist,
    create_business_reviewer,
    create_business_editor,
    create_competitive_strategist,
    create_competitive_reviewer,
    create_competitive_editor,
    create_customer_strategist,
    create_customer_reviewer,
    create_customer_editor,
    create_marketing_strategist,
    create_marketing_reviewer,
    create_marketing_editor,
    create_brand_strategist,
    create_brand_reviewer,
    create_brand_editor,
)


class TestAgentCreation:
    """Test suite for agent creation functions."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock StrategyContext for testing."""
        return StrategyContext(
            company_name="TestCompany",
            websites=["https://testcompany.com"],
            industry="Technology",
            customer_regions=["North America", "Europe"],
            annual_ad_budget="$1M-$5M",
            account_id="test_account_123",
            tenant_id="test_tenant_456",
        )

    @pytest.fixture
    def mock_firestore(self):
        """Mock Firestore functions."""
        with (
            patch(
                "app.adk.agents.strategy_agent.agents.get_best_practices_sync"
            ) as mock_bp,
            patch(
                "app.adk.agents.strategy_agent.agents.get_reviewer_guidelines_sync"
            ) as mock_rg,
            patch(
                "app.adk.agents.strategy_agent.agents.extract_field_requirements_from_best_practices"
            ) as mock_extract,
        ):
            mock_bp.return_value = (
                '{"sections": ["overview", "analysis", "recommendations"]}'
            )
            mock_rg.return_value = "Review for completeness and accuracy"
            mock_extract.return_value = (
                "Required fields: overview, analysis, recommendations"
            )

            yield {
                "best_practices": mock_bp,
                "reviewer_guidelines": mock_rg,
                "extract_requirements": mock_extract,
            }

    def test_create_google_search_agent(self):
        """Test Google search agent creation."""
        agent = create_google_search_agent()

        assert agent.name == "google_search_agent"
        assert agent.model == "gemini-2.5-flash"
        assert (
            agent.description
            == "Expert web researcher that searches Google for public information"
        )
        assert agent.generate_content_config.temperature == 0.2
        assert agent.generate_content_config.max_output_tokens == 8192

    def test_create_business_strategist_with_context(
        self, mock_context, mock_firestore
    ):
        """Test business strategist creation with context."""
        agent = create_business_strategist(mock_context)

        assert agent.name == "business_strategist"
        assert agent.model == "gemini-2.5-pro"
        assert agent.output_key == "business_strategy_doc"
        assert agent.generate_content_config.temperature == 0.2
        assert agent.generate_content_config.max_output_tokens == 65535

        # Verify context information is included in instruction
        assert mock_context.company_name in agent.instruction
        assert mock_context.industry in agent.instruction

        # Verify Firestore was called
        mock_firestore["best_practices"].assert_called_once_with("business_strategy")
        mock_firestore["extract_requirements"].assert_called_once()

    def test_create_business_strategist_without_context(self, mock_firestore):
        """Test business strategist creation without context."""
        agent = create_business_strategist(None)

        assert agent.name == "business_strategist"
        assert agent.model == "gemini-2.5-pro"
        assert "the company" in agent.instruction
        assert "the industry" in agent.instruction

    def test_create_business_reviewer(self, mock_firestore):
        """Test business reviewer agent creation."""
        agent = create_business_reviewer()

        assert agent.name == "business_reviewer"
        assert (
            agent.model == "gemini-2.5-flash"
        )  # Should use flash for cost optimization
        assert agent.tools == [exit_loop]
        assert agent.generate_content_config.temperature == 0.1

        mock_firestore["reviewer_guidelines"].assert_called_once_with(
            "business_strategy"
        )

    def test_create_business_editor(self, mock_firestore):
        """Test business editor agent creation."""
        agent = create_business_editor()

        assert agent.name == "business_editor"
        assert (
            agent.model == "gemini-2.5-flash"
        )  # Should use flash for cost optimization
        assert len(agent.tools) == 2  # google_search_agent and exit_loop
        assert agent.generate_content_config.temperature == 0.2

    @pytest.mark.parametrize(
        "strategist_func,name,doc_type",
        [
            (
                create_competitive_strategist,
                "competitive_strategist",
                "competitive_strategy",
            ),
            (create_customer_strategist, "customer_strategist", "customer_strategy"),
            (create_marketing_strategist, "marketing_strategist", "marketing_strategy"),
            (create_brand_strategist, "brand_strategist", "brand_guidelines"),
        ],
    )
    def test_all_strategists_use_pro_model(
        self, strategist_func, name, doc_type, mock_context, mock_firestore
    ):
        """Test that all strategist agents use gemini-2.5-pro model."""
        agent = strategist_func(mock_context)

        assert agent.name == name
        assert agent.model == "gemini-2.5-pro", (
            f"{name} should use gemini-2.5-pro for quality"
        )
        assert agent.generate_content_config.max_output_tokens == 65535

        mock_firestore["best_practices"].assert_called_with(doc_type)

    @pytest.mark.parametrize(
        "reviewer_func,name",
        [
            (create_competitive_reviewer, "competitive_reviewer"),
            (create_customer_reviewer, "customer_reviewer"),
            (create_marketing_reviewer, "marketing_reviewer"),
            (create_brand_reviewer, "brand_reviewer"),
        ],
    )
    def test_all_reviewers_use_flash_model(self, reviewer_func, name, mock_firestore):
        """Test that all reviewer agents use gemini-2.5-flash model."""
        agent = reviewer_func()

        assert agent.name == name
        assert agent.model == "gemini-2.5-flash", (
            f"{name} should use gemini-2.5-flash for cost"
        )

    @pytest.mark.parametrize(
        "editor_func,name",
        [
            (create_competitive_editor, "competitive_editor"),
            (create_customer_editor, "customer_editor"),
            (create_marketing_editor, "marketing_editor"),
            (create_brand_editor, "brand_editor"),
        ],
    )
    def test_all_editors_use_flash_model(self, editor_func, name, mock_firestore):
        """Test that all editor agents use gemini-2.5-flash model."""
        agent = editor_func()

        assert agent.name == name
        assert agent.model == "gemini-2.5-flash", (
            f"{name} should use gemini-2.5-flash for cost"
        )

    def test_cascading_document_review_in_instructions(
        self, mock_context, mock_firestore
    ):
        """Test that each agent's instructions reference reviewing prior documents."""
        # Competitive should review business
        competitive = create_competitive_strategist(mock_context)
        assert "business_strategy_doc" in competitive.instruction
        assert "Review Prior Analysis" in competitive.instruction

        # Customer should review business and competitive
        customer = create_customer_strategist(mock_context)
        assert "business_strategy_doc" in customer.instruction
        assert "competitive_strategy_doc" in customer.instruction

        # Marketing should review all prior docs
        marketing = create_marketing_strategist(mock_context)
        assert "business_strategy_doc" in marketing.instruction
        assert "competitive_strategy_doc" in marketing.instruction
        assert "customer_strategy_doc" in marketing.instruction

        # Brand guidelines optionally reviews all
        brand = create_brand_strategist(mock_context)
        assert "prior strategy documents" in brand.instruction.lower()

    def test_firestore_fallback_when_unavailable(self):
        """Test that agents handle Firestore unavailability gracefully."""
        with patch(
            "app.adk.agents.strategy_agent.agents.get_best_practices_sync",
            return_value=None,
        ):
            agent = create_business_strategist(None)

            assert agent is not None
            assert (
                "default best practices" in agent.instruction.lower()
                or "Create a comprehensive" in agent.instruction
            )

    def test_agent_output_keys(self, mock_context, mock_firestore):
        """Test that all agents have correct output keys for state management."""
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
