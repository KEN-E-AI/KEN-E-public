"""Test suite for token monitoring and logging utilities."""

import json
import pytest
from unittest.mock import MagicMock, patch

from ..token_utils import TokenEstimator, TokenLimitError, check_and_log_tokens
from ..logging_config import StrategyAgentLogger, safe_agent_execution
from ..tracing_config import WeaveTracer, check_token_budget


class TestTokenEstimator:
    """Tests for TokenEstimator class."""

    def test_estimate_tokens_string(self):
        """Test token estimation for strings."""
        # 4 chars = 1 token approximation
        text = "Hello, World!"  # 13 chars
        tokens = TokenEstimator.estimate_tokens(text)
        assert tokens == 3  # 13 // 4 = 3

        long_text = "a" * 4000  # 4000 chars
        tokens = TokenEstimator.estimate_tokens(long_text)
        assert tokens == 1000  # 4000 // 4 = 1000

    def test_estimate_tokens_dict(self):
        """Test token estimation for dictionaries."""
        data = {"key": "value", "number": 123}
        tokens = TokenEstimator.estimate_tokens(data)
        assert tokens > 0

    def test_estimate_tokens_list(self):
        """Test token estimation for lists."""
        data = ["item1", "item2", "item3"]
        tokens = TokenEstimator.estimate_tokens(data)
        assert tokens > 0

    def test_estimate_tokens_none(self):
        """Test token estimation for None."""
        assert TokenEstimator.estimate_tokens(None) == 0

    def test_check_input_limit_within(self):
        """Test checking content within limits."""
        content = "a" * 1000  # Small content
        result = TokenEstimator.check_input_limit(content, raise_on_exceed=False)

        assert result["within_limit"] is True
        assert result["error"] is False
        assert result["percentage"] < 1  # Should be well under 1% of 2M tokens

    def test_check_input_limit_warning(self):
        """Test warning when approaching limit."""
        # Create content that's 85% of limit
        # 2M tokens * 4 chars/token * 0.85 = 7,127,654 chars
        large_content = "a" * 7_127_654

        result = TokenEstimator.check_input_limit(large_content, raise_on_exceed=False)
        assert result["warning"] is True
        assert result["within_limit"] is True
        assert result["error"] is False

    def test_check_input_limit_exceed(self):
        """Test exception when exceeding limit."""
        # Create content that exceeds limit
        # 2M tokens * 4 chars/token * 1.1 = 9,215,827 chars
        huge_content = "a" * 9_215_827

        with pytest.raises(TokenLimitError) as exc_info:
            TokenEstimator.check_input_limit(huge_content, raise_on_exceed=True)

        assert "exceed limit" in str(exc_info.value)

    def test_estimate_agent_input(self):
        """Test estimating tokens for complete agent input."""
        state = {"key": "value"}
        best_practices = "Best practices document content"
        business_info = {"company": "Test Corp"}
        documents = [{"content": "Document 1"}, {"content": "Document 2"}]

        breakdown = TokenEstimator.estimate_agent_input(
            state=state,
            best_practices=best_practices,
            business_info=business_info,
            documents=documents,
        )

        assert "state" in breakdown
        assert "best_practices" in breakdown
        assert "business_info" in breakdown
        assert "documents" in breakdown
        assert "total" in breakdown
        assert "percentage" in breakdown
        assert "within_limit" in breakdown
        assert breakdown["total"] > 0

    def test_chunk_content(self):
        """Test content chunking."""
        # Create content that needs chunking
        content = "a" * 2_500_000  # ~625k tokens

        chunks = TokenEstimator.chunk_content(content, max_chunk_tokens=500_000)

        assert len(chunks) == 2
        assert len(chunks[0]) + len(chunks[1]) == len(content)

    def test_chunk_content_small(self):
        """Test chunking small content that doesn't need splitting."""
        content = "Small content"
        chunks = TokenEstimator.chunk_content(content)

        assert len(chunks) == 1
        assert chunks[0] == content


class TestStrategyAgentLogger:
    """Tests for StrategyAgentLogger class."""

    @patch("google.cloud.logging.Client")
    def test_logger_initialization(self, mock_client):
        """Test logger initialization."""
        logger = StrategyAgentLogger("test_agent")

        assert logger.agent_name == "test_agent"
        assert logger.execution_id is None

    def test_logger_without_cloud(self):
        """Test logger works without Google Cloud Logging."""
        with patch.dict("sys.modules", {"google.cloud.logging": None}):
            logger = StrategyAgentLogger("test_agent", use_cloud_logging=False)

            assert logger.agent_name == "test_agent"
            assert logger.cloud_logger is None

    def test_log_agent_start(self):
        """Test logging agent start."""
        logger = StrategyAgentLogger("test_agent", use_cloud_logging=False)

        logger.log_agent_start(
            execution_id="test-123",
            input_tokens=1000,
            context={"function": "test_func"},
        )

        assert logger.execution_id == "test-123"

    def test_log_token_usage(self):
        """Test logging token usage."""
        logger = StrategyAgentLogger("test_agent", use_cloud_logging=False)

        logger.log_token_usage(
            phase="input_assembly",
            tokens={"input": 1000, "total": 1500},
            percentage_of_limit=50.0,
        )
        # Should not raise any exceptions

    def test_log_error(self):
        """Test error logging."""
        logger = StrategyAgentLogger("test_agent", use_cloud_logging=False)

        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.log_error(e, context={"test": "context"})
        # Should not raise any exceptions

    def test_log_completion(self):
        """Test logging completion."""
        logger = StrategyAgentLogger("test_agent", use_cloud_logging=False)

        logger.log_completion(
            success=True,
            output_tokens=500,
            duration_seconds=10.5,
            metadata={"documents": 5},
        )
        # Should not raise any exceptions


class TestSafeAgentExecution:
    """Tests for safe_agent_execution decorator."""

    def test_successful_execution(self):
        """Test decorator with successful function execution."""

        @safe_agent_execution(agent_name="test", check_token_limits=False)
        def test_function(x: int) -> int:
            return x * 2

        result = test_function(5)
        assert result == 10

    def test_execution_with_error(self):
        """Test decorator handling function errors."""

        @safe_agent_execution(agent_name="test", check_token_limits=False)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

    def test_token_limit_check(self):
        """Test decorator with token limit checking."""

        @safe_agent_execution(agent_name="test", check_token_limits=True)
        def function_with_large_input(data: str) -> str:
            return data[:10]

        # Should work with small input
        result = function_with_large_input("small data")
        assert result == "small data"


class TestWeaveTracing:
    """Tests for Weave tracing utilities."""

    def test_weave_tracer_init(self):
        """Test WeaveTracer initialization."""
        # Should not raise even without weave installed
        WeaveTracer.init_tracing("test-project")

    def test_check_token_budget_within(self):
        """Test token budget check within limit."""
        result = check_token_budget(
            current_tokens=1000, max_tokens=10000, operation="test_op"
        )
        assert result is True

    def test_check_token_budget_warning(self):
        """Test token budget check with warning."""
        result = check_token_budget(
            current_tokens=8500,
            max_tokens=10000,
            operation="test_op",
            warn_threshold=0.8,
        )
        assert result is True  # Still within budget

    def test_check_token_budget_exceed(self):
        """Test token budget check exceeding limit."""
        result = check_token_budget(
            current_tokens=11000, max_tokens=10000, operation="test_op"
        )
        assert result is False


class TestCheckAndLogTokens:
    """Tests for check_and_log_tokens utility function."""

    def test_check_and_log_within_limit(self):
        """Test checking and logging tokens within limit."""
        content = "Test content"
        result = check_and_log_tokens(
            content, context="test_context", raise_on_exceed=False
        )

        assert "estimated_tokens" in result
        assert "percentage" in result
        assert result["within_limit"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
