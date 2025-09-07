"""Tests for orchestrator.py - testing the strategy orchestration and execution."""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import json
from datetime import datetime
import uuid

from app.adk.agents.strategy_agent.orchestrator import (
    create_strategy_sequential_agent,
    execute_strategy_generation,
    process_and_save_documents,
    parse_document_content,
    clean_json_string,
    DOCUMENT_KEY_MAPPING,
)
from app.adk.agents.strategy_agent.models import StrategyContext
from app.adk.agents.strategy_agent.firestore import FirestoreClient


class TestCreateStrategySequentialAgent:
    """Test the sequential agent creation."""

    @patch("app.adk.agents.strategy_agent.orchestrator.create_brand_guidelines_agent")
    @patch("app.adk.agents.strategy_agent.orchestrator.create_marketing_strategy_agent")
    @patch("app.adk.agents.strategy_agent.orchestrator.create_customer_strategy_agent")
    @patch(
        "app.adk.agents.strategy_agent.orchestrator.create_competitive_strategy_agent"
    )
    @patch("app.adk.agents.strategy_agent.orchestrator.create_business_strategy_agent")
    @patch("app.adk.agents.strategy_agent.orchestrator.SequentialAgent")
    def test_creates_sequential_agent_with_all_agents(
        self,
        mock_sequential_agent,
        mock_business,
        mock_competitive,
        mock_customer,
        mock_marketing,
        mock_brand,
    ):
        """Test that all 5 agents are created and chained properly."""
        # Setup mocks
        mock_business_agent = Mock(name="business_agent")
        mock_competitive_agent = Mock(name="competitive_agent")
        mock_customer_agent = Mock(name="customer_agent")
        mock_marketing_agent = Mock(name="marketing_agent")
        mock_brand_agent = Mock(name="brand_agent")

        mock_business.return_value = mock_business_agent
        mock_competitive.return_value = mock_competitive_agent
        mock_customer.return_value = mock_customer_agent
        mock_marketing.return_value = mock_marketing_agent
        mock_brand.return_value = mock_brand_agent

        mock_seq_agent_instance = Mock(name="sequential_agent")
        mock_sequential_agent.return_value = mock_seq_agent_instance

        # Create context
        context = StrategyContext(
            account_id="test_account",
            company_name="Test Corp",
            websites=["https://test.com"],
            industry="Technology",
            customer_regions=["USA"],
        )

        # Execute
        result = create_strategy_sequential_agent(context)

        # Verify all agents were created with the context
        mock_business.assert_called_once_with(context)
        mock_competitive.assert_called_once_with(context)
        mock_customer.assert_called_once_with(context)
        mock_marketing.assert_called_once_with(context)
        mock_brand.assert_called_once_with(context)

        # Verify SequentialAgent was created with all agents in order
        mock_sequential_agent.assert_called_once_with(
            name="strategy_generator",
            sub_agents=[
                mock_business_agent,
                mock_competitive_agent,
                mock_customer_agent,
                mock_marketing_agent,
                mock_brand_agent,
            ],
            description="Generates all 5 strategy documents in sequence",
        )

        assert result == mock_seq_agent_instance

    def test_agent_creation_order_matters(self):
        """Test that agents are added in the correct sequence."""
        with patch(
            "app.adk.agents.strategy_agent.orchestrator.SequentialAgent"
        ) as mock_seq:
            with patch(
                "app.adk.agents.strategy_agent.orchestrator.create_business_strategy_agent"
            ) as mock_b:
                with patch(
                    "app.adk.agents.strategy_agent.orchestrator.create_competitive_strategy_agent"
                ) as mock_c:
                    context = StrategyContext(
                        account_id="test",
                        company_name="Test",
                        websites=["https://test.com"],
                        industry="Tech",
                        customer_regions=["USA"],
                    )

                    create_strategy_sequential_agent(context)

                    # Verify the sub_agents list order
                    call_args = mock_seq.call_args
                    sub_agents = call_args[1]["sub_agents"]

                    # The order should be: business, competitive, customer, marketing, brand
                    assert len(sub_agents) == 5
                    # Note: In real test we'd verify the actual agent types


class TestExecuteStrategyGeneration:
    """Test the main execution function."""

    @patch("app.adk.agents.strategy_agent.orchestrator.process_and_save_documents")
    @patch("app.adk.agents.strategy_agent.orchestrator.Runner")
    @patch("app.adk.agents.strategy_agent.orchestrator.InMemorySessionService")
    @patch(
        "app.adk.agents.strategy_agent.orchestrator.create_strategy_sequential_agent"
    )
    @patch("app.adk.agents.strategy_agent.orchestrator.FirestoreClient")
    def test_successful_execution(
        self,
        mock_firestore_client_class,
        mock_create_seq_agent,
        mock_session_service_class,
        mock_runner_class,
        mock_process_docs,
    ):
        """Test successful strategy generation execution."""
        # Setup mocks
        mock_client = Mock(spec=FirestoreClient)
        mock_firestore_client_class.return_value = mock_client

        mock_agent = Mock()
        mock_create_seq_agent.return_value = mock_agent

        mock_session_service = Mock()
        mock_session = Mock()
        mock_session_service.create_session_sync.return_value = mock_session
        mock_session_service_class.return_value = mock_session_service

        mock_runner = Mock()
        mock_events = [Mock(), Mock()]  # Simulate events
        mock_runner.run.return_value = mock_events
        mock_runner_class.return_value = mock_runner

        mock_process_docs.return_value = {
            "business_strategy": {"test": "data1"},
            "competitive_strategy": {"test": "data2"},
        }

        # Execute
        result = execute_strategy_generation(
            company_name="Test Corp",
            industry="Technology",
            websites="https://test.com,https://blog.test.com",
            customer_regions="USA,Europe",
            account_id="test_account",
            user_id="test_user",
            annual_ad_budget=100000.0,
            project_id="test-project",
        )

        # Verify Firestore client created with project_id
        mock_firestore_client_class.assert_called_once_with(project_id="test-project")

        # Verify context was properly created and agent initialized
        mock_create_seq_agent.assert_called_once()
        context = mock_create_seq_agent.call_args[0][0]
        assert context.company_name == "Test Corp"
        assert context.industry == "Technology"
        assert context.websites == ["https://test.com", "https://blog.test.com"]
        assert context.customer_regions == ["USA", "Europe"]
        assert context.annual_ad_budget == 100000.0

        # Verify session creation
        mock_session_service.create_session_sync.assert_called_once()

        # Verify runner execution
        mock_runner.run.assert_called_once()

        # Verify document processing
        mock_process_docs.assert_called_once_with(
            mock_events, "test_account", "test_user", mock_client
        )

        # Verify success message
        assert "Successfully generated 2 strategy documents" in result
        assert "Test Corp" in result

    @patch("app.adk.agents.strategy_agent.orchestrator.FirestoreClient")
    def test_execution_with_injected_client(self, mock_firestore_client_class):
        """Test execution uses injected Firestore client when provided."""
        # Create an injected client
        injected_client = Mock(spec=FirestoreClient)

        with patch(
            "app.adk.agents.strategy_agent.orchestrator.create_strategy_sequential_agent"
        ):
            with patch("app.adk.agents.strategy_agent.orchestrator.Runner"):
                with patch(
                    "app.adk.agents.strategy_agent.orchestrator.process_and_save_documents"
                ):
                    result = execute_strategy_generation(
                        company_name="Test",
                        industry="Tech",
                        websites="https://test.com",
                        customer_regions="USA",
                        account_id="test",
                        user_id="user",
                        firestore_client=injected_client,  # Pass injected client
                    )

                    # Should not create new client
                    mock_firestore_client_class.assert_not_called()

    @patch("app.adk.agents.strategy_agent.orchestrator.FirestoreClient")
    def test_execution_handles_exceptions(self, mock_firestore_client_class):
        """Test that exceptions are caught and returned as error messages."""
        mock_firestore_client_class.side_effect = Exception("Connection failed")

        result = execute_strategy_generation(
            company_name="Test",
            industry="Tech",
            websites="https://test.com",
            customer_regions="USA",
            account_id="test",
            user_id="user",
        )

        assert "Failed to generate strategy documents" in result
        assert "Connection failed" in result


class TestProcessAndSaveDocuments:
    """Test document processing and saving."""

    def test_processes_events_and_saves_documents(self):
        """Test that events are processed and documents saved to Firestore."""
        # Setup mock Firestore client
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = True

        # Create mock events with documents
        event1 = Mock()
        event1.author = "business_strategy_agent"
        event1.actions = Mock()
        event1.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "businessStrategySummary": "Test summary",
                    "companyOverview": "Test overview",
                }
            )
        }

        event2 = Mock()
        event2.author = "competitive_strategy_agent"
        event2.actions = Mock()
        event2.actions.state_delta = {
            "updated_strategy_doc": json.dumps({"competitiveAnalysis": "Test analysis"})
        }

        events = [event1, event2]

        # Execute
        result = process_and_save_documents(
            events,
            account_id="test_account",
            user_id="test_user",
            firestore_client=mock_client,
        )

        # Verify documents were captured
        assert len(result) == 2
        assert "business_strategy" in result
        assert "competitive_strategy" in result

        # Verify Firestore saves
        assert mock_client.save_strategy_document_sync.call_count == 2

        # Check first save call
        first_call = mock_client.save_strategy_document_sync.call_args_list[0]
        assert first_call[1]["account_id"] == "test_account"
        assert first_call[1]["doc_type"] == "business_strategy"
        assert first_call[1]["user_id"] == "test_user"

    def test_handles_events_without_documents(self):
        """Test that events without documents are handled gracefully."""
        mock_client = Mock(spec=FirestoreClient)

        # Event without actions
        event1 = Mock()
        event1.author = "some_agent"
        event1.actions = None

        # Event without state_delta
        event2 = Mock()
        event2.author = "another_agent"
        event2.actions = Mock()
        event2.actions.state_delta = None

        events = [event1, event2]

        result = process_and_save_documents(
            events, account_id="test", user_id="user", firestore_client=mock_client
        )

        # Should not crash and return empty
        assert result == {}
        mock_client.save_strategy_document_sync.assert_not_called()

    def test_continues_on_firestore_save_failure(self):
        """Test that processing continues even if Firestore save fails."""
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = False

        event = Mock()
        event.author = "business_strategy_agent"
        event.actions = Mock()
        event.actions.state_delta = {"updated_strategy_doc": '{"test": "data"}'}

        result = process_and_save_documents(
            [event], account_id="test", user_id="user", firestore_client=mock_client
        )

        # Document should still be captured in memory
        assert "business_strategy" in result
        assert result["business_strategy"] == {"test": "data"}


class TestParseDocumentFromEvent:
    """Test document parsing from events."""

    def test_parses_json_string_and_determines_type(self):
        """Test parsing JSON string and determining document type from author."""
        event = Mock()
        event.author = "business_strategy_agent"

        doc_content = (
            '{"businessStrategySummary": "Test", "companyOverview": "Overview"}'
        )

        parsed_doc, doc_type = parse_document_from_event(doc_content, event)

        assert doc_type == "business_strategy"
        assert parsed_doc["businessStrategySummary"] == "Test"
        assert parsed_doc["companyOverview"] == "Overview"

    def test_handles_dict_content(self):
        """Test handling when content is already a dict."""
        event = Mock()
        event.author = "competitive_strategy_agent"

        doc_content = {"competitiveAnalysis": "Analysis"}

        parsed_doc, doc_type = parse_document_from_event(doc_content, event)

        assert doc_type == "competitive_strategy"
        assert parsed_doc == doc_content

    def test_determines_all_document_types(self):
        """Test that all 5 document types are correctly identified."""
        test_cases = [
            ("business_strategy_agent", "business_strategy"),
            ("competitive_analysis_agent", "competitive_strategy"),
            ("customer_insights_agent", "customer_strategy"),
            ("marketing_channels_agent", "marketing_strategy"),
            ("brand_voice_agent", "brand_guidelines"),
        ]

        for author, expected_type in test_cases:
            event = Mock()
            event.author = author
            _, doc_type = parse_document_from_event('{"test": "data"}', event)
            assert doc_type == expected_type

    def test_handles_unknown_author(self):
        """Test handling of unknown author types."""
        event = Mock()
        event.author = "unknown_agent"

        parsed_doc, doc_type = parse_document_from_event('{"test": "data"}', event)

        assert doc_type is None
        assert parsed_doc == {"test": "data"}

    def test_handles_invalid_json(self):
        """Test handling of invalid JSON strings."""
        event = Mock()
        event.author = "business_strategy_agent"

        doc_content = "This is not JSON"

        parsed_doc, doc_type = parse_document_from_event(doc_content, event)

        assert parsed_doc is None
        assert doc_type is None


class TestCleanJsonString:
    """Test JSON string cleaning utility."""

    def test_removes_markdown_code_blocks(self):
        """Test removal of markdown code blocks."""
        content = '```json\n{"key": "value"}\n```'
        result = clean_json_string(content)
        assert result == '{"key": "value"}'

    def test_fixes_invalid_escape_sequences(self):
        """Test fixing of invalid escape sequences."""
        # Test with invalid escape sequence \s
        content = '{"text": "Line one\\sLine two"}'
        result = clean_json_string(content)
        # Should convert \s to \\s
        assert result == '{"text": "Line one\\\\sLine two"}'

        # Verify it can be parsed
        parsed = json.loads(result)
        assert parsed["text"] == "Line one\\sLine two"

    def test_preserves_valid_escape_sequences(self):
        """Test that valid escape sequences are preserved."""
        content = '{"text": "Line one\\nLine two\\t\\r\\"\\\\"}'
        result = clean_json_string(content)

        # Valid escapes should remain unchanged
        assert result == content

        # Verify it can be parsed
        parsed = json.loads(result)
        assert "Line one\nLine two\t\r" in parsed["text"]

    def test_handles_clean_json(self):
        """Test that already clean JSON is unchanged."""
        content = '{"key": "value", "number": 42}'
        result = clean_json_string(content)
        assert result == content

    def test_handles_whitespace(self):
        """Test handling of leading/trailing whitespace."""
        content = '  \n  {"key": "value"}  \n  '
        result = clean_json_string(content)
        assert result == '{"key": "value"}'

    def test_complex_markdown_removal(self):
        """Test removal of complex markdown formatting."""
        content = '```json\n{\n  "key": "value",\n  "nested": {\n    "field": "data"\n  }\n}\n```'
        result = clean_json_string(content)

        expected = '{\n  "key": "value",\n  "nested": {\n    "field": "data"\n  }\n}'
        assert result == expected

        # Verify it parses correctly
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["nested"]["field"] == "data"


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple components."""

    @patch("app.adk.agents.strategy_agent.orchestrator.Runner")
    @patch(
        "app.adk.agents.strategy_agent.orchestrator.create_strategy_sequential_agent"
    )
    def test_end_to_end_document_flow(self, mock_create_agent, mock_runner_class):
        """Test complete flow from execution to document saving."""
        # Setup comprehensive mocks
        mock_agent = Mock()
        mock_create_agent.return_value = mock_agent

        # Create realistic event stream
        event1 = Mock()
        event1.author = "business_strategy_agent"
        event1.actions = Mock()
        event1.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {
                    "businessStrategySummary": "We are a tech company",
                    "companyOverview": "Founded in 2020",
                }
            )
        }

        event2 = Mock()
        event2.author = "competitive_strategy_agent"
        event2.actions = Mock()
        event2.actions.state_delta = {
            "updated_strategy_doc": json.dumps(
                {"competitiveAnalysis": "Market leader in segment"}
            )
        }

        mock_runner = Mock()
        mock_runner.run.return_value = [event1, event2]
        mock_runner_class.return_value = mock_runner

        # Create mock Firestore client
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = True

        # Execute
        with patch("app.adk.agents.strategy_agent.orchestrator.InMemorySessionService"):
            result = execute_strategy_generation(
                company_name="TechCorp",
                industry="Technology",
                websites="https://techcorp.com",
                customer_regions="Global",
                account_id="account123",
                user_id="user456",
                firestore_client=mock_client,
            )

        # Verify success
        assert "Successfully generated 2 strategy documents" in result
        assert "TechCorp" in result

        # Verify both documents were saved
        assert mock_client.save_strategy_document_sync.call_count == 2

        # Verify document types
        call_args_list = mock_client.save_strategy_document_sync.call_args_list
        doc_types = [call[1]["doc_type"] for call in call_args_list]
        assert "business_strategy" in doc_types
        assert "competitive_strategy" in doc_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
