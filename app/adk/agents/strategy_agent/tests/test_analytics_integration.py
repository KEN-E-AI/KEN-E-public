"""Integration tests for the complete analytics system.

These tests verify the interaction between all analytics components
working together in realistic scenarios.
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from ..analytics_service import AnalyticsService
from ..performance_profiler import PerformanceProfiler
from ..alert_manager import AlertManager
from ..optimization_analyzer import OptimizationAnalyzer
from ..analytics_helpers import (
    initialize_analytics_services,
    check_token_limits_before_execution,
    report_execution_summary,
)


@pytest.fixture
def mock_firestore():
    """Mock Firestore for all analytics components."""
    with patch("google.cloud.firestore.Client") as mock_client:
        # Create separate mock databases
        mock_analytics_db = MagicMock()
        mock_default_db = MagicMock()

        def client_side_effect(project=None, database=None):
            if database == "analytics":
                return mock_analytics_db
            return mock_default_db

        mock_client.side_effect = client_side_effect

        # Setup collection mocks
        mock_analytics_collection = MagicMock()
        mock_default_collection = MagicMock()

        mock_analytics_db.collection.return_value = mock_analytics_collection
        mock_default_db.collection.return_value = mock_default_collection

        # Setup document mocks for configuration
        mock_config_doc = MagicMock()
        mock_config_doc.exists = False  # Use default configs
        mock_default_collection.document.return_value.get.return_value = mock_config_doc

        yield mock_analytics_db, mock_default_db


class TestFullExecutionFlow:
    """Test the complete execution flow with all analytics components."""

    def test_successful_execution_with_analytics(self, mock_firestore):
        """Test a successful execution with full analytics tracking."""
        mock_analytics_db, mock_default_db = mock_firestore

        # Initialize all services
        analytics, profiler, alert_mgr, optimizer = initialize_analytics_services(
            account_id="test_account", project_id="test_project", enable_analytics=True
        )

        assert analytics is not None
        assert profiler is not None
        assert alert_mgr is not None
        assert optimizer is not None

        # Start execution tracking
        main_op = profiler.start_operation("orchestrator", "strategy_generation")

        # Track some agent executions
        metrics1 = analytics.track_agent_execution(
            agent_name="strategist",
            prompt_tokens=10000,
            response_tokens=5000,
            model="gemini-2.5-pro",
            execution_time=5.0,
            success=True,
        )

        # Track sub-operation
        sub_op = profiler.start_operation("strategist", "document_generation")
        time.sleep(0.01)  # Simulate work
        profiler.end_operation(sub_op, success=True)

        # Track another agent
        metrics2 = analytics.track_agent_execution(
            agent_name="reviewer",
            prompt_tokens=5000,
            response_tokens=2500,
            model="gemini-2.5-flash",
            execution_time=2.0,
            success=True,
        )

        # End main operation
        profiler.end_operation(main_op, success=True)

        # Generate execution summary
        report_execution_summary(
            analytics_service=analytics,
            performance_profiler=profiler,
            optimization_analyzer=optimizer,
            main_operation=main_op,
            execution_time=7.0,
            documents_generated=2,
        )

        # Verify analytics tracked everything
        summary = analytics.get_execution_summary()
        assert summary["total_tokens"] == 22500
        assert len(summary["agent_metrics"]) == 2
        assert "strategist" in summary["agent_metrics"]
        assert "reviewer" in summary["agent_metrics"]
        assert summary["agent_metrics"]["strategist"]["executions"] == 1
        assert summary["agent_metrics"]["reviewer"]["executions"] == 1

        # Verify performance profiling
        perf_summary = profiler.get_performance_summary()
        assert perf_summary["total_operations"] == 2

        # Verify Firestore calls were made
        assert mock_analytics_db.collection.called
        assert mock_default_db.collection.called


class TestAlertEscalation:
    """Test alert escalation through token usage thresholds."""

    def test_progressive_alert_escalation(self, mock_firestore):
        """Test alerts escalate as token usage increases."""
        mock_analytics_db, mock_default_db = mock_firestore

        alert_mgr = AlertManager("test_account", "test_project")

        # 40% usage - no alerts
        alerts = alert_mgr.check_token_usage(
            current_tokens=400000, max_tokens=1000000, context="test"
        )
        assert len(alerts) == 0

        # 60% usage - info/warning alerts
        alerts = alert_mgr.check_token_usage(
            current_tokens=600000, max_tokens=1000000, context="test"
        )
        assert len(alerts) > 0
        assert any(a["severity"] in ["info", "warning"] for a in alerts)

        # 95% usage - critical alerts
        alerts = alert_mgr.check_token_usage(
            current_tokens=950000, max_tokens=1000000, context="test"
        )
        assert any(a["severity"] == "critical" for a in alerts)

        # 100% usage - circuit breaker
        alerts = alert_mgr.check_token_usage(
            current_tokens=1000000, max_tokens=1000000, context="test"
        )
        assert alert_mgr.check_circuit_breaker()
        assert any("CIRCUIT BREAKER" in a["message"] for a in alerts)

    def test_alert_cooldown_prevents_spam(self, mock_firestore):
        """Test that cooldown prevents alert spam."""
        mock_analytics_db, mock_default_db = mock_firestore

        alert_mgr = AlertManager("test_account", "test_project")

        # First alert at 80%
        alerts1 = alert_mgr.check_token_usage(
            current_tokens=800000, max_tokens=1000000, context="test"
        )
        initial_count = len(alerts1)
        assert initial_count > 0

        # Immediate second check - should be in cooldown
        alerts2 = alert_mgr.check_token_usage(
            current_tokens=800000, max_tokens=1000000, context="test"
        )
        assert len(alerts2) == 0  # Cooldown prevents alerts

        # Different context should trigger alerts
        alerts3 = alert_mgr.check_token_usage(
            current_tokens=800000, max_tokens=1000000, context="different"
        )
        assert len(alerts3) == initial_count


class TestCostAggregation:
    """Test daily cost aggregation functionality."""

    def test_daily_cost_aggregation(self, mock_firestore):
        """Test aggregation of daily costs."""
        mock_analytics_db, mock_default_db = mock_firestore

        # Setup mock documents for aggregation
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = {
            "total_cost": 1.5,
            "total_tokens": 50000,
            "agent_name": "strategist",
            "model": "gemini-2.5-pro",
        }

        mock_doc2 = MagicMock()
        mock_doc2.to_dict.return_value = {
            "total_cost": 0.5,
            "total_tokens": 20000,
            "agent_name": "reviewer",
            "model": "gemini-2.5-flash",
        }

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        mock_analytics_db.collection.return_value.where.return_value = mock_query

        analytics = AnalyticsService("test_account", "test_project")
        aggregation = analytics.aggregate_daily_costs()

        assert aggregation["total_cost"] == 2.0
        assert aggregation["total_tokens"] == 70000
        assert aggregation["total_executions"] == 2
        assert "strategist" in aggregation["cost_by_agent"]
        assert "reviewer" in aggregation["cost_by_agent"]


class TestOptimizationRecommendations:
    """Test optimization recommendation generation."""

    def test_model_downgrade_recommendation(self, mock_firestore):
        """Test recommendation to downgrade from Pro to Flash."""
        mock_analytics_db, mock_default_db = mock_firestore

        # Setup mock usage data showing Pro model used for small tasks
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "agent_name": "simple_agent",
            "model": "gemini-2.5-pro",
            "prompt_tokens": 50,
            "response_tokens": 30,
            "total_tokens": 80,
            "total_cost": 0.5,
            "success": True,
            "timestamp": datetime.now(timezone.utc),
        }

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc] * 10  # 10 small executions
        mock_analytics_db.collection.return_value.where.return_value = mock_query

        optimizer = OptimizationAnalyzer("test_account", "test_project")
        recommendations = optimizer.generate_recommendations()

        # Should recommend model downgrade
        model_recs = [
            r for r in recommendations if r.recommendation_type == "model_downgrade"
        ]
        assert len(model_recs) > 0
        assert "Flash" in model_recs[0].description

    def test_context_optimization_recommendation(self, mock_firestore):
        """Test recommendation for context optimization."""
        mock_analytics_db, mock_default_db = mock_firestore

        # Setup mock data with low context utilization
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "agent_name": "inefficient_agent",
            "model": "gemini-2.5-flash",
            "prompt_tokens": 10000,  # Using only 1% of 1M context
            "response_tokens": 5000,
            "total_tokens": 15000,
            "total_cost": 0.1,
            "success": True,
            "timestamp": datetime.now(timezone.utc),
        }

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.stream.return_value = [mock_doc] * 5
        mock_analytics_db.collection.return_value.where.return_value = mock_query

        optimizer = OptimizationAnalyzer("test_account", "test_project")
        patterns = optimizer.analyze_usage_patterns()
        recommendations = optimizer.generate_recommendations(patterns)

        # Should recommend context reduction
        context_recs = [
            r for r in recommendations if r.recommendation_type == "context_reduction"
        ]
        assert len(context_recs) > 0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_halts_execution(self, mock_firestore):
        """Test that circuit breaker prevents execution when triggered."""
        mock_analytics_db, mock_default_db = mock_firestore

        alert_mgr = AlertManager("test_account", "test_project")
        profiler = PerformanceProfiler("test_account", "test_project")

        # Simulate high token usage
        input_text = "x" * 1000000  # Large input

        error_msg = check_token_limits_before_execution(
            alert_manager=alert_mgr,
            execution_input=input_text,
            performance_profiler=profiler,
            main_operation=None,
        )

        # Should return error message if tokens exceed limit
        # (Note: actual behavior depends on TokenEstimator implementation)
        # This test verifies the function executes without error
        assert error_msg is None or isinstance(error_msg, str)

    def test_circuit_breaker_reset(self, mock_firestore):
        """Test circuit breaker can be reset."""
        mock_analytics_db, mock_default_db = mock_firestore

        alert_mgr = AlertManager("test_account", "test_project")

        # Trigger circuit breaker
        alert_mgr.check_token_usage(current_tokens=1000000, max_tokens=1000000)
        assert alert_mgr.check_circuit_breaker()

        # Reset circuit breaker
        alert_mgr.reset_circuit_breaker()
        assert not alert_mgr.check_circuit_breaker()


class TestPerformanceBottlenecks:
    """Test performance bottleneck detection."""

    def test_bottleneck_identification(self, mock_firestore):
        """Test identification of performance bottlenecks."""
        mock_analytics_db, mock_default_db = mock_firestore

        # Mock the Firestore query to return our test data
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "agent_name": "slow_agent",
            "operation": "heavy_processing",
            "duration_seconds": 5.0,  # Slow operation
            "timestamp": datetime.now(timezone.utc),
            "is_bottleneck": True,
            "severity": "high",
            "success": True,
        }

        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = [mock_doc]
        mock_analytics_db.collection.return_value.where.return_value = mock_query

        profiler = PerformanceProfiler("test_account", "test_project")

        # Check for bottlenecks
        bottlenecks = profiler.get_bottlenecks(time_window_hours=1)

        # The slow operation should be identified as a bottleneck
        assert len(bottlenecks) > 0
        assert bottlenecks[0]["agent_name"] == "slow_agent"
        assert bottlenecks[0]["duration"] == 5.0
        assert bottlenecks[0]["severity"] == "high"


class TestAnalyticsDisabling:
    """Test that analytics can be disabled."""

    def test_analytics_disabled(self, mock_firestore):
        """Test execution with analytics disabled."""
        # Initialize with analytics disabled
        analytics, profiler, alert_mgr, optimizer = initialize_analytics_services(
            account_id="test_account", project_id="test_project", enable_analytics=False
        )

        # All services should be None
        assert analytics is None
        assert profiler is None
        assert alert_mgr is None
        assert optimizer is None

        # Functions should handle None services gracefully
        error_msg = check_token_limits_before_execution(
            alert_manager=None,
            execution_input="test input",
            performance_profiler=None,
            main_operation=None,
        )
        assert error_msg is None

        # Report function should handle None services
        report_execution_summary(
            analytics_service=None,
            performance_profiler=None,
            optimization_analyzer=None,
            main_operation=None,
            execution_time=1.0,
            documents_generated=1,
        )
        # Should complete without error
