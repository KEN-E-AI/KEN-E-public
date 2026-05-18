"""Tests for strategy generation error handling and empty response scenarios."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.kene_api.tasks.strategy_tasks import trigger_strategy_generation


@pytest.mark.skip(
    reason="Needs full rewrite: vertexai lazily imported (patch targets invalid), stale expected error messages, removed function parameters (target_audience, firestore_service, neo4j_service) — see DM-85"
)
class TestStrategyGenerationErrorHandling:
    """Test error handling in strategy generation."""

    @pytest.fixture
    def mock_account_data(self):
        """Mock account data for testing."""
        return {
            "account_id": "acc_test123",
            "company_name": "Test Company",
            "websites": ["https://example.com"],
            "industry": "Technology",
            "customer_regions": ["North America"],
            "user_id": "user_test123",
            "annual_ad_budget": 100000.0,
            "uploaded_document_urls": None,
            "user_context": None,
        }

    @pytest.mark.asyncio
    async def test_empty_agent_response_marks_account_failed(self, mock_account_data):
        """Test that empty agent response marks account as failed."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                    ):
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                        ):
                            # Mock agent engine returning empty response
                            mock_agent = MagicMock()
                            mock_agent.stream_query.return_value = []  # Empty iterator
                            mock_engines.get.return_value = mock_agent

                            # Run the task
                            await trigger_strategy_generation(
                                account_id=mock_account_data["account_id"],
                                company_name=mock_account_data["company_name"],
                                websites=mock_account_data["websites"],
                                industry=mock_account_data["industry"],
                                customer_regions=mock_account_data["customer_regions"],
                                user_id=mock_account_data["user_id"],
                                annual_ad_budget=mock_account_data["annual_ad_budget"],
                                uploaded_document_urls=mock_account_data[
                                    "uploaded_document_urls"
                                ],
                                user_context=mock_account_data["user_context"],
                            )

                            # Verify account was marked as failed
                            mock_update_status.assert_called_with(
                                mock_account_data["account_id"],
                                "failed",
                                completed=False,
                                error_message="Strategy generation failed - no response from agent. Please try again.",
                            )

    @pytest.mark.asyncio
    async def test_agent_response_with_no_chunks_marks_failed(self, mock_account_data):
        """Test that agent response that yields no chunks marks account as failed."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                    ):
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                        ):
                            # Mock agent engine with iterator that immediately stops
                            class EmptyIterator:
                                def __iter__(self):
                                    return self

                                def __next__(self):
                                    raise StopIteration

                            mock_agent = MagicMock()
                            mock_agent.stream_query.return_value = EmptyIterator()
                            mock_engines.get.return_value = mock_agent

                            # Run the task
                            await trigger_strategy_generation(
                                account_id=mock_account_data["account_id"],
                                company_name=mock_account_data["company_name"],
                                websites=mock_account_data["websites"],
                                industry=mock_account_data["industry"],
                                customer_regions=mock_account_data["customer_regions"],
                                user_id=mock_account_data["user_id"],
                                annual_ad_budget=mock_account_data["annual_ad_budget"],
                                uploaded_document_urls=mock_account_data[
                                    "uploaded_document_urls"
                                ],
                                user_context=mock_account_data["user_context"],
                            )

                            # Verify account was marked as failed
                            mock_update_status.assert_called_with(
                                mock_account_data["account_id"],
                                "failed",
                                completed=False,
                                error_message="Strategy generation failed - no response from agent. Please try again.",
                            )

    @pytest.mark.asyncio
    async def test_agent_iteration_error_handles_gracefully(self, mock_account_data):
        """Test that errors during chunk iteration are handled gracefully."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                    ):
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                        ):
                            # Mock agent engine that raises error during iteration
                            class ErrorIterator:
                                def __iter__(self):
                                    return self

                                def __next__(self):
                                    raise RuntimeError("Connection lost")

                            mock_agent = MagicMock()
                            mock_agent.stream_query.return_value = ErrorIterator()
                            mock_engines.get.return_value = mock_agent

                            # Run the task
                            await trigger_strategy_generation(
                                account_id=mock_account_data["account_id"],
                                company_name=mock_account_data["company_name"],
                                websites=mock_account_data["websites"],
                                industry=mock_account_data["industry"],
                                customer_regions=mock_account_data["customer_regions"],
                                user_id=mock_account_data["user_id"],
                                annual_ad_budget=mock_account_data["annual_ad_budget"],
                                uploaded_document_urls=mock_account_data[
                                    "uploaded_document_urls"
                                ],
                                user_context=mock_account_data["user_context"],
                            )

                            # Verify account was marked as failed
                            mock_update_status.assert_called_with(
                                mock_account_data["account_id"],
                                "failed",
                                completed=False,
                                error_message="Strategy generation failed - no response from agent. Please try again.",
                            )

    @pytest.mark.asyncio
    async def test_successful_response_but_no_documents_created(
        self, mock_account_data
    ):
        """Test that successful agent response but no documents created marks as failed."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.verify_strategy_documents_created"
                    ) as mock_verify:
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                        ) as mock_get_firestore:
                            with patch(
                                "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                            ) as mock_get_neo4j:
                                # Setup mocks
                                mock_get_firestore.return_value = mock_firestore_service
                                mock_get_neo4j.return_value = mock_neo4j_service

                                # Mock agent engine returning valid response
                                mock_agent = MagicMock()
                                mock_agent.stream_query.return_value = [
                                    {
                                        "content": {
                                            "parts": [{"text": "Strategy content"}]
                                        }
                                    }
                                ]
                                mock_engines.get.return_value = mock_agent

                                # Mock document verification always returning False
                                mock_verify.return_value = False

                                # Run the task with a short timeout for testing
                                with patch(
                                    "src.kene_api.tasks.strategy_tasks.asyncio.sleep"
                                ) as mock_sleep:
                                    mock_sleep.side_effect = [
                                        None
                                    ] * 3  # Allow 3 iterations

                                    await trigger_strategy_generation(
                                        account_id=mock_account_data["account_id"],
                                        company_name=mock_account_data["company_name"],
                                        industry=mock_account_data["industry"],
                                        target_audience=mock_account_data[
                                            "target_audience"
                                        ],
                                        user_id=mock_account_data["user_id"],
                                        firestore_service=mock_firestore_service,
                                        neo4j_service=mock_neo4j_service,
                                    )

                                # Verify account was marked as failed after timeout
                                mock_update_status.assert_called_with(
                                    mock_account_data["account_id"],
                                    "failed",
                                    completed=False,
                                    error_message="Strategy document generation timed out. Please try again.",
                                )

    @pytest.mark.asyncio
    async def test_agent_response_timeout_handling(self, mock_account_data):
        """Test that agent response collection times out after 25 minutes."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                    ) as mock_get_firestore:
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                        ) as mock_get_neo4j:
                            with patch(
                                "src.kene_api.tasks.strategy_tasks.asyncio.get_event_loop"
                            ) as mock_loop:
                                # Setup mocks
                                mock_get_firestore.return_value = mock_firestore_service
                                mock_get_neo4j.return_value = mock_neo4j_service

                                # Mock time to simulate timeout
                                mock_loop.return_value.time.side_effect = [
                                    0,  # Start time
                                    1501,  # First chunk - exceeds 1500 second timeout
                                ]

                                # Mock agent engine with infinite iterator
                                class InfiniteIterator:
                                    def __iter__(self):
                                        return self

                                    def __next__(self):
                                        return {
                                            "content": {"parts": [{"text": "chunk"}]}
                                        }

                                mock_agent = MagicMock()
                                mock_agent.stream_query.return_value = (
                                    InfiniteIterator()
                                )
                                mock_engines.get.return_value = mock_agent

                                # Run the task
                                await trigger_strategy_generation(
                                    account_id=mock_account_data["account_id"],
                                    company_name=mock_account_data["company_name"],
                                    industry=mock_account_data["industry"],
                                    target_audience=mock_account_data[
                                        "target_audience"
                                    ],
                                    user_id=mock_account_data["user_id"],
                                    firestore_service=mock_firestore_service,
                                    neo4j_service=mock_neo4j_service,
                                )

                                # Should not fail immediately but continue with what was collected
                                # The timeout is logged but processing continues

    @pytest.mark.asyncio
    async def test_successful_strategy_generation_flow(self, mock_account_data):
        """Test successful strategy generation flow."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.update_account_setup_status"
                ) as mock_update_status:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.verify_strategy_documents_created"
                    ) as mock_verify:
                        with patch(
                            "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                        ) as mock_get_firestore:
                            with patch(
                                "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                            ) as mock_get_neo4j:
                                # Setup mocks
                                mock_get_firestore.return_value = mock_firestore_service
                                mock_get_neo4j.return_value = mock_neo4j_service

                                # Mock agent engine returning valid response
                                mock_agent = MagicMock()
                                mock_agent.stream_query.return_value = [
                                    {
                                        "content": {
                                            "parts": [
                                                {"text": "Business strategy content"}
                                            ]
                                        }
                                    },
                                    {
                                        "content": {
                                            "parts": [
                                                {"text": "Marketing strategy content"}
                                            ]
                                        }
                                    },
                                    {
                                        "content": {
                                            "parts": [
                                                {"text": "Customer strategy content"}
                                            ]
                                        }
                                    },
                                ]
                                mock_engines.get.return_value = mock_agent

                                # Mock document verification returning True (all docs complete)
                                mock_verify.return_value = True

                                # Run the task
                                await trigger_strategy_generation(
                                    account_id=mock_account_data["account_id"],
                                    company_name=mock_account_data["company_name"],
                                    industry=mock_account_data["industry"],
                                    target_audience=mock_account_data[
                                        "target_audience"
                                    ],
                                    user_id=mock_account_data["user_id"],
                                    firestore_service=mock_firestore_service,
                                    neo4j_service=mock_neo4j_service,
                                )

                                # Verify account was marked as completed
                                mock_update_status.assert_called_with(
                                    mock_account_data["account_id"],
                                    "completed",
                                    completed=True,
                                )

    @pytest.mark.asyncio
    async def test_agent_call_failure_raises_exception(self, mock_account_data):
        """Test that agent call failure raises exception."""
        with patch("src.kene_api.tasks.strategy_tasks.vertexai") as mock_vertexai:
            with patch(
                "src.kene_api.tasks.strategy_tasks.agent_engines"
            ) as mock_engines:
                with patch(
                    "src.kene_api.tasks.strategy_tasks.get_firestore_service"
                ) as mock_get_firestore:
                    with patch(
                        "src.kene_api.tasks.strategy_tasks.get_neo4j_service"
                    ) as mock_get_neo4j:
                        # Setup mocks
                        mock_get_firestore.return_value = mock_firestore_service
                        mock_get_neo4j.return_value = mock_neo4j_service

                        # Mock agent engine raising error on stream_query
                        mock_agent = MagicMock()
                        mock_agent.stream_query.side_effect = Exception(
                            "Agent unavailable"
                        )
                        mock_engines.get.return_value = mock_agent

                        # Run the task and expect exception
                        with pytest.raises(Exception, match="Agent unavailable"):
                            await trigger_strategy_generation(
                                account_id=mock_account_data["account_id"],
                                company_name=mock_account_data["company_name"],
                                industry=mock_account_data["industry"],
                                target_audience=mock_account_data["target_audience"],
                                user_id=mock_account_data["user_id"],
                                firestore_service=mock_firestore_service,
                                neo4j_service=mock_neo4j_service,
                            )
