"""Test script for AsyncAnalyticsQueue integration with existing agents.

This script demonstrates how to test the async analytics queue with real agents
and compare performance against the synchronous implementation.
"""

import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

from .async_analytics_queue import AsyncAnalyticsQueue, AsyncAnalyticsAdapter
from .analytics_service import AnalyticsService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceComparison:
    """Compare performance between sync and async analytics."""

    def __init__(self, account_id: str = "test_account"):
        self.account_id = account_id
        self.results = {
            "sync": {"times": [], "total": 0},
            "async": {"times": [], "total": 0},
        }

    def simulate_agent_execution(
        self, analytics_service, num_agents: int = 5, num_iterations: int = 3
    ) -> float:
        """Simulate multiple agent executions with analytics tracking.

        Args:
            analytics_service: Analytics service instance (sync or async)
            num_agents: Number of different agents to simulate
            num_iterations: Number of iterations per agent

        Returns:
            Total execution time in seconds
        """
        start_time = time.time()

        agents = [
            "business_strategist",
            "competitive_strategist",
            "customer_strategist",
            "marketing_strategist",
            "brand_strategist",
        ][:num_agents]

        for iteration in range(num_iterations):
            for agent_name in agents:
                # Simulate agent execution
                execution_start = time.time()

                # Track the analytics event
                analytics_service.track_agent_execution(
                    agent_name=agent_name,
                    prompt_tokens=1000 + (iteration * 100),
                    response_tokens=2000 + (iteration * 200),
                    model="gemini-2.5-flash"
                    if iteration % 2 == 0
                    else "gemini-2.5-pro",
                    execution_time=5.0 + iteration,
                    success=True,
                    metadata={"iteration": iteration, "test_run": True},
                )

                # Simulate some processing time
                time.sleep(0.01)  # 10ms of "agent work"

                execution_time = time.time() - execution_start
                logger.debug(
                    f"{agent_name} iteration {iteration}: {execution_time:.4f}s"
                )

        total_time = time.time() - start_time
        return total_time

    def run_comparison(self):
        """Run performance comparison between sync and async analytics."""
        logger.info("=" * 60)
        logger.info("Starting Performance Comparison")
        logger.info("=" * 60)

        # Test synchronous analytics
        logger.info("\n1. Testing SYNCHRONOUS Analytics")
        logger.info("-" * 40)
        sync_service = AnalyticsService(self.account_id)
        sync_time = self.simulate_agent_execution(sync_service)
        self.results["sync"]["total"] = sync_time
        logger.info(f"Sync total time: {sync_time:.4f}s")

        # Get sync summary
        sync_summary = sync_service.get_execution_summary()
        logger.info(f"Sync events processed: {sync_summary['total_tokens']} tokens")

        # Test asynchronous analytics
        logger.info("\n2. Testing ASYNCHRONOUS Analytics")
        logger.info("-" * 40)
        async_service = AsyncAnalyticsAdapter(self.account_id)
        async_time = self.simulate_agent_execution(async_service)
        self.results["async"]["total"] = async_time
        logger.info(f"Async total time: {async_time:.4f}s")

        # Wait for async queue to flush
        time.sleep(1)
        async_summary = async_service.get_execution_summary()
        queue_status = async_summary.get("queue_status", {})
        logger.info(
            f"Async events queued: {queue_status.get('metrics', {}).get('events_queued', 0)}"
        )

        # Calculate improvement
        improvement = ((sync_time - async_time) / sync_time) * 100
        logger.info("\n" + "=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info(f"Synchronous:  {sync_time:.4f}s")
        logger.info(f"Asynchronous: {async_time:.4f}s")
        logger.info(f"Improvement:  {improvement:.1f}% faster")
        logger.info(f"Time saved:   {sync_time - async_time:.4f}s")

        # Cleanup
        async_service.shutdown()


class AsyncQueueTests:
    """Test cases for AsyncAnalyticsQueue functionality."""

    def __init__(self):
        self.account_id = "test_account"

    def test_queue_overflow(self):
        """Test behavior when queue is full."""
        logger.info("\nTesting Queue Overflow Behavior")
        logger.info("-" * 40)

        # Create small queue for testing
        queue = AsyncAnalyticsQueue(
            account_id=self.account_id,
            queue_size=10,
            batch_size=5,
            enable_background_worker=False,  # Disable worker to fill queue
        )

        # Fill the queue
        success_count = 0
        fail_count = 0

        for i in range(20):
            success = queue.track_event(
                event_type="test", data={"index": i}, priority=False
            )
            if success:
                success_count += 1
            else:
                fail_count += 1

        logger.info(f"Events queued: {success_count}")
        logger.info(f"Events rejected: {fail_count}")

        status = queue.get_queue_status()
        logger.info(f"Queue utilization: {status['utilization_percent']:.1f}%")

        queue.shutdown()

    def test_batch_processing(self):
        """Test batch processing of events."""
        logger.info("\nTesting Batch Processing")
        logger.info("-" * 40)

        queue = AsyncAnalyticsQueue(
            account_id=self.account_id,
            batch_size=5,
            flush_interval=1.0,
            enable_background_worker=True,
        )

        # Queue multiple events
        for i in range(12):
            queue.track_agent_execution(
                agent_name=f"test_agent_{i}",
                prompt_tokens=100,
                response_tokens=200,
                model="gemini-2.5-flash",
                execution_time=1.0,
                success=True,
            )

        # Check initial status
        initial_status = queue.get_queue_status()
        logger.info(f"Initial queue size: {initial_status['queue_size']}")

        # Wait for batch processing
        time.sleep(2)

        # Check final status
        final_status = queue.get_queue_status()
        logger.info(f"Final queue size: {final_status['queue_size']}")
        logger.info(f"Batches written: {final_status['metrics']['batches_written']}")
        logger.info(f"Events processed: {final_status['metrics']['events_processed']}")

        queue.shutdown()

    def test_graceful_shutdown(self):
        """Test graceful shutdown with pending events."""
        logger.info("\nTesting Graceful Shutdown")
        logger.info("-" * 40)

        queue = AsyncAnalyticsQueue(
            account_id=self.account_id,
            batch_size=100,  # Large batch to keep events pending
            flush_interval=60.0,  # Long interval
            enable_background_worker=True,
        )

        # Queue events
        for i in range(10):
            queue.track_event("shutdown_test", {"index": i})

        status_before = queue.get_queue_status()
        logger.info(f"Queue size before shutdown: {status_before['queue_size']}")

        # Shutdown should flush pending events
        queue.shutdown(timeout=5.0)

        logger.info("Shutdown completed - pending events should be flushed")

    def run_all_tests(self):
        """Run all test cases."""
        logger.info("=" * 60)
        logger.info("Running AsyncAnalyticsQueue Tests")
        logger.info("=" * 60)

        self.test_queue_overflow()
        self.test_batch_processing()
        self.test_graceful_shutdown()


def test_with_mock_agent():
    """Test async analytics with a mock agent execution."""
    logger.info("\nTesting with Mock Agent")
    logger.info("-" * 40)

    # Create async analytics adapter
    analytics = AsyncAnalyticsAdapter(account_id="mock_test", project_id="test-project")

    # Simulate agent execution
    def mock_agent_execution(analytics_service):
        """Simulate an agent execution with analytics tracking."""
        start_time = time.time()

        # Track start
        analytics_service.track_agent_execution(
            agent_name="mock_strategist",
            prompt_tokens=1500,
            response_tokens=3000,
            model="gemini-2.5-pro",
            execution_time=0,
            success=True,
            metadata={"phase": "start"},
        )

        # Simulate work
        time.sleep(0.1)

        # Track completion
        execution_time = time.time() - start_time
        result = analytics_service.track_agent_execution(
            agent_name="mock_strategist",
            prompt_tokens=0,
            response_tokens=0,
            model="gemini-2.5-pro",
            execution_time=execution_time,
            success=True,
            metadata={"phase": "complete"},
        )

        return result

    # Run mock execution
    result = mock_agent_execution(analytics)
    logger.info(f"Mock execution completed: {result['total_tokens']} tokens")

    # Check queue status
    summary = analytics.get_execution_summary()
    queue_status = summary["queue_status"]
    logger.info(
        f"Queue status: {queue_status['metrics']['events_queued']} events queued"
    )

    # Cleanup
    analytics.shutdown()


def main():
    """Main test runner."""
    # Run performance comparison
    comparison = PerformanceComparison()
    comparison.run_comparison()

    print("\n" + "=" * 60)

    # Run functional tests
    tests = AsyncQueueTests()
    tests.run_all_tests()

    print("\n" + "=" * 60)

    # Run mock agent test
    test_with_mock_agent()

    logger.info("\n" + "=" * 60)
    logger.info("All tests completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
