"""Integration tests for the strategy agent system - testing actual components together."""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from app.adk.agents.strategy_agent.firestore import ContextManager, FirestoreClient
from app.adk.agents.strategy_agent.models import (
    StrategyContext,
)
from app.adk.agents.strategy_agent.orchestrator import (
    clean_json_string,
    execute_strategy_generation,
    process_and_save_documents,
)


class TestFirestoreIntegration:
    """Test Firestore operations with real-like scenarios."""

    @pytest.fixture
    def mock_firestore_db(self):
        """Create a mock Firestore database."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_document = Mock()

        # Chain the methods
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_document

        return mock_db, mock_collection, mock_document

    def test_save_and_retrieve_strategy_document(self, mock_firestore_db):
        """Test saving and retrieving a complete strategy document."""
        mock_db, mock_collection, mock_document = mock_firestore_db

        # Setup mock for retrieval
        mock_retrieved_doc = Mock()
        mock_retrieved_doc.exists = True
        mock_retrieved_doc.to_dict.return_value = {
            "content": {
                "businessStrategySummary": "Test summary",
                "companyOverview": "Test overview",
            },
            "doc_type": "business_strategy",
            "account_id": "test_account",
            "created_at": datetime.utcnow(),
            "version": 1,
        }
        mock_document.get.return_value = mock_retrieved_doc

        # Create client with mock
        client = FirestoreClient(client=mock_db)

        # Save document
        content = {
            "businessStrategySummary": "Test summary",
            "companyOverview": "Test overview",
        }

        result = client.save_strategy_document_sync(
            account_id="test_account",
            doc_type="business_strategy",
            content=content,
            user_id="test_user",
        )

        assert result is True

        # Verify the save call
        mock_document.set.assert_called_once()
        saved_data = mock_document.set.call_args[0][0]
        assert saved_data["content"] == content
        assert saved_data["doc_type"] == "business_strategy"
        assert saved_data["account_id"] == "test_account"
        assert saved_data["created_by"] == "test_user"

    def test_context_manager_with_firestore(self, mock_firestore_db):
        """Test ContextManager saving and retrieving context."""
        mock_db, _, mock_document = mock_firestore_db

        client = FirestoreClient(client=mock_db)
        manager = ContextManager(firestore_client=client)

        # Create context
        context = StrategyContext(
            account_id="test_account",
            company_name="Test Corp",
            websites=["https://test.com"],
            industry="Technology",
            customer_regions=["USA"],
            user_id="test_user",
        )

        # Test save
        @pytest.mark.asyncio
        async def test_save():
            result = await manager.save_context(context)
            assert result is True
            mock_document.set.assert_called_once()

        # Run async test
        import asyncio

        asyncio.run(test_save())


class TestEventProcessingIntegration:
    """Test event processing pipeline with realistic data."""

    def test_process_multi_agent_event_stream(self):
        """Test processing a realistic event stream from multiple agents."""
        # Create mock Firestore client
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = True

        # Create realistic event stream
        events = []

        # Business strategy event
        business_event = Mock()
        business_event.author = "business_strategy_agent"
        business_event.actions = Mock()
        business_event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "businessStrategySummary": "We provide AI solutions",
                    "companyOverview": "Leading AI company",
                    "strategicObjectives": ["Expand market", "Increase revenue"],
                    "swotAnalysis": {
                        "strengths": ["Innovation", "Team"],
                        "weaknesses": ["Funding"],
                        "opportunities": ["Market growth"],
                        "threats": ["Competition"],
                    },
                    "revenueStreams": ["SaaS", "Consulting"],
                    "growthOpportunities": ["International expansion"],
                }
            )
        }
        events.append(business_event)

        # Competitive strategy event
        competitive_event = Mock()
        competitive_event.author = "competitive_strategy_agent"
        competitive_event.actions = Mock()
        competitive_event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "competitiveAnalysis": "Strong position",
                    "marketPosition": "Top 5",
                    "competitorProfiles": [
                        {"name": "Competitor A", "strength": "Scale"},
                        {"name": "Competitor B", "strength": "Price"},
                    ],
                    "differentiators": ["Technology", "Service"],
                    "marketTrends": ["AI adoption", "Cloud migration"],
                    "competitiveAdvantages": ["First mover", "Patents"],
                }
            )
        }
        events.append(competitive_event)

        # Customer strategy event
        customer_event = Mock()
        customer_event.author = "customer_strategy_agent"
        customer_event.actions = Mock()
        customer_event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "targetAudience": "Enterprise clients",
                    "customerSegments": ["Fortune 500", "Mid-market"],
                    "valueProposition": "AI that works",
                    "customerJourney": ["Awareness", "Consideration", "Decision"],
                    "retentionStrategy": "Success management",
                    "satisfactionMetrics": ["NPS", "CSAT"],
                }
            )
        }
        events.append(customer_event)

        # Process all events
        result = process_and_save_documents(
            events,
            account_id="test_account",
            user_id="test_user",
            firestore_client=mock_client,
        )

        # Verify all documents were captured
        assert len(result) == 3
        assert "business_strategy" in result
        assert "competitive_strategy" in result
        assert "customer_strategy" in result

        # Verify content integrity
        assert (
            result["business_strategy"]["businessStrategySummary"]
            == "We provide AI solutions"
        )
        assert len(result["business_strategy"]["strategicObjectives"]) == 2
        assert result["competitive_strategy"]["marketPosition"] == "Top 5"
        assert len(result["competitive_strategy"]["competitorProfiles"]) == 2
        assert result["customer_strategy"]["targetAudience"] == "Enterprise clients"

        # Verify all documents were saved
        assert mock_client.save_strategy_document_sync.call_count == 3

    def test_handles_malformed_events_gracefully(self):
        """Test that malformed events don't crash the pipeline."""
        mock_client = Mock(spec=FirestoreClient)

        events = []

        # Valid event
        valid_event = Mock()
        valid_event.author = "business_strategy_agent"
        valid_event.actions = Mock()
        valid_event.actions.state_delta = {"updated_strategy_doc": '{"valid": "data"}'}
        events.append(valid_event)

        # Malformed JSON event
        malformed_event = Mock()
        malformed_event.author = "competitive_strategy_agent"
        malformed_event.actions = Mock()
        malformed_event.actions.state_delta = {
            "updated_strategy_doc": '{"invalid": json}'  # Invalid JSON
        }
        events.append(malformed_event)

        # Another valid event
        valid_event2 = Mock()
        valid_event2.author = "customer_strategy_agent"
        valid_event2.actions = Mock()
        valid_event2.actions.state_delta = {
            "updated_strategy_doc": '{"more": "valid data"}'
        }
        events.append(valid_event2)

        # Process events
        result = process_and_save_documents(
            events, account_id="test", user_id="user", firestore_client=mock_client
        )

        # Should capture valid events and skip malformed ones
        assert len(result) == 2
        assert "business_strategy" in result
        assert "customer_strategy" in result
        assert "competitive_strategy" not in result


class TestJSONCleaningIntegration:
    """Test JSON cleaning with real-world edge cases."""

    def test_clean_complex_markdown_json(self):
        """Test cleaning complex markdown-wrapped JSON."""
        content = """```json
{
  "businessStrategySummary": "We are a technology company focused on AI\\sinnovation",
  "companyOverview": "Founded in 2020, we provide cutting-edge solutions",
  "strategicObjectives": [
    "Expand to 10 new markets",
    "Achieve $100M ARR",
    "Launch 3 new products"
  ],
  "swotAnalysis": {
    "strengths": ["Strong team", "Innovative\\stechnology"],
    "weaknesses": ["Limited funding"],
    "opportunities": ["Market growth"],
    "threats": ["Competition from big\\stech"]
  }
}
```"""

        cleaned = clean_json_string(content)

        # Should be valid JSON after cleaning
        parsed = json.loads(cleaned)

        assert (
            parsed["businessStrategySummary"]
            == "We are a technology company focused on AI\\sinnovation"
        )
        assert len(parsed["strategicObjectives"]) == 3
        assert "Strong team" in parsed["swotAnalysis"]["strengths"]

    def test_clean_nested_escape_sequences(self):
        """Test cleaning nested structures with various escape sequences."""
        content = """{
  "text1": "Line with\\ttab",
  "text2": "Line with\\nnewline",
  "text3": "Line with\\sinvalid escape",
  "nested": {
    "field": "Another\\xinvalid"
  }
}"""

        cleaned = clean_json_string(content)
        parsed = json.loads(cleaned)

        # Valid escapes preserved
        assert parsed["text1"] == "Line with\ttab"
        assert parsed["text2"] == "Line with\nnewline"

        # Invalid escapes fixed
        assert parsed["text3"] == "Line with\\sinvalid escape"
        assert parsed["nested"]["field"] == "Another\\xinvalid"


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    @patch("app.adk.agents.strategy_agent.orchestrator.Runner")
    @patch(
        "app.adk.agents.strategy_agent.orchestrator.create_strategy_sequential_agent"
    )
    @patch("app.adk.agents.strategy_agent.orchestrator.InMemorySessionService")
    def test_complete_strategy_generation_flow(
        self, mock_session_service_class, mock_create_agent, mock_runner_class
    ):
        """Test complete flow from request to saved documents."""
        # Setup comprehensive mocks
        mock_agent = Mock()
        mock_create_agent.return_value = mock_agent

        mock_session_service = Mock()
        mock_session = Mock()
        mock_session_service.create_session_sync.return_value = mock_session
        mock_session_service_class.return_value = mock_session_service

        # Create full event stream for all 5 agents
        events = self._create_full_event_stream()

        mock_runner = Mock()
        mock_runner.run.return_value = events
        mock_runner_class.return_value = mock_runner

        # Create mock Firestore client
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = True

        # Execute complete generation
        result = execute_strategy_generation(
            company_name="AI Innovators Inc",
            industry="Artificial Intelligence",
            websites="https://ai-innovators.com,https://blog.ai-innovators.com",
            customer_regions="North America,Europe,Asia",
            account_id="acc_12345",
            user_id="user_67890",
            annual_ad_budget=5000000.0,
            firestore_client=mock_client,
        )

        # Verify success
        assert "Successfully generated 5 strategy documents" in result
        assert "AI Innovators Inc" in result

        # Verify all 5 documents were saved
        assert mock_client.save_strategy_document_sync.call_count == 5

        # Verify document types saved
        saved_types = set()
        for call in mock_client.save_strategy_document_sync.call_args_list:
            saved_types.add(call[1]["doc_type"])

        expected_types = {
            "business_strategy",
            "competitive_strategy",
            "customer_strategy",
            "marketing_strategy",
            "brand_guidelines",
        }
        assert saved_types == expected_types

    def _create_full_event_stream(self):
        """Helper to create a complete event stream for all 5 agents."""
        events = []

        # Business strategy
        event = Mock()
        event.author = "business_strategy_agent"
        event.actions = Mock()
        event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "businessStrategySummary": "AI solutions provider",
                    "companyOverview": "Leading AI company",
                    "strategicObjectives": ["Growth", "Innovation"],
                    "swotAnalysis": {"strengths": ["Tech"], "weaknesses": ["Scale"]},
                    "revenueStreams": ["SaaS", "Services"],
                    "growthOpportunities": ["Global expansion"],
                }
            )
        }
        events.append(event)

        # Competitive strategy
        event = Mock()
        event.author = "competitive_strategy_agent"
        event.actions = Mock()
        event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "competitiveAnalysis": "Strong position",
                    "marketPosition": "Top tier",
                    "competitorProfiles": [{"name": "Comp1"}],
                    "differentiators": ["Technology"],
                    "marketTrends": ["AI adoption"],
                    "competitiveAdvantages": ["Innovation"],
                }
            )
        }
        events.append(event)

        # Customer strategy
        event = Mock()
        event.author = "customer_strategy_agent"
        event.actions = Mock()
        event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "targetAudience": "Enterprises",
                    "customerSegments": ["Fortune 500"],
                    "valueProposition": "AI that delivers",
                    "customerJourney": ["Awareness", "Purchase"],
                    "retentionStrategy": "Success teams",
                    "satisfactionMetrics": ["NPS"],
                }
            )
        }
        events.append(event)

        # Marketing strategy
        event = Mock()
        event.author = "marketing_strategy_agent"
        event.actions = Mock()
        event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "marketingChannels": ["Digital", "Events"],
                    "contentStrategy": "Thought leadership",
                    "campaignThemes": ["Innovation", "Results"],
                    "budgetAllocation": {"Digital": 60, "Events": 40},
                    "kpis": ["Leads", "Conversions"],
                    "marketingCalendar": ["Q1: Launch", "Q2: Scale"],
                }
            )
        }
        events.append(event)

        # Brand guidelines
        event = Mock()
        event.author = "brand_guidelines_agent"
        event.actions = Mock()
        event.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "brandVoice": "Professional yet innovative",
                    "visualIdentity": "Modern, clean",
                    "brandValues": ["Innovation", "Trust"],
                    "messagingFramework": "AI for everyone",
                    "toneGuidelines": "Clear and confident",
                    "brandArchitecture": "Master brand",
                }
            )
        }
        events.append(event)

        return events

    def test_partial_execution_recovery(self):
        """Test that partial execution can be recovered."""
        mock_client = Mock(spec=FirestoreClient)

        # Simulate partial execution - only 3 of 5 documents
        events = []
        for agent_name in [
            "business_strategy_agent",
            "competitive_strategy_agent",
            "customer_strategy_agent",
        ]:
            event = Mock()
            event.author = agent_name
            event.actions = Mock()
            event.actions.state_delta = {
                "updated_strategy_doc": json.dumps({"test": f"data_{agent_name}"})
            }
            events.append(event)

        # First save succeeds, second fails, third succeeds
        mock_client.save_strategy_document_sync.side_effect = [True, False, True]

        result = process_and_save_documents(
            events, account_id="test", user_id="user", firestore_client=mock_client
        )

        # All documents should be in memory despite save failure
        assert len(result) == 3

        # Verify save was attempted for all
        assert mock_client.save_strategy_document_sync.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
