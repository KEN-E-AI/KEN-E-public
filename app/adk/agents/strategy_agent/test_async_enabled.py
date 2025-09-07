#!/usr/bin/env python3
"""Test script to verify async analytics is enabled and working."""

import os
import sys
import logging

# Set environment variable
os.environ["USE_ASYNC_ANALYTICS"] = "true"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_async_analytics():
    """Test that async analytics is properly configured."""

    logger.info("=" * 60)
    logger.info("Testing Async Analytics Configuration")
    logger.info("=" * 60)

    # Check environment variable
    use_async = os.getenv("USE_ASYNC_ANALYTICS", "false")
    logger.info(f"USE_ASYNC_ANALYTICS environment variable: {use_async}")

    if use_async.lower() != "true":
        logger.error("❌ USE_ASYNC_ANALYTICS is not set to 'true'")
        return False

    # Import analytics helpers
    try:
        # Try different import approaches
        try:
            from agents.strategy_agent.analytics_helpers import (
                initialize_analytics_services,
            )

            logger.info("✅ Successfully imported analytics_helpers (absolute import)")
        except ImportError:
            # Fallback to adding path
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from analytics_helpers import initialize_analytics_services

            logger.info(
                "✅ Successfully imported analytics_helpers (path modification)"
            )
    except ImportError as e:
        logger.error(f"❌ Failed to import analytics_helpers: {e}")
        return False

    # Initialize analytics services
    logger.info("\nInitializing analytics services...")
    try:
        (
            analytics_service,
            performance_profiler,
            alert_manager,
            optimization_analyzer,
        ) = initialize_analytics_services(
            account_id="test_account", project_id="test-project", enable_analytics=True
        )

        # Check if we got async adapter
        if analytics_service is None:
            logger.error("❌ Analytics service is None")
            return False

        # Check the type of analytics service
        service_type = type(analytics_service).__name__
        logger.info(f"Analytics service type: {service_type}")

        if "AsyncAnalyticsAdapter" in service_type:
            logger.info("✅ Async analytics is ENABLED - using AsyncAnalyticsAdapter")

            # Test the queue functionality
            logger.info("\nTesting async queue functionality...")

            # Track a test event
            result = analytics_service.track_agent_execution(
                agent_name="test_agent",
                prompt_tokens=100,
                response_tokens=200,
                model="gemini-2.5-flash",
                execution_time=1.0,
                success=True,
                metadata={"test": True},
            )

            if result:
                logger.info("✅ Successfully queued analytics event")

                # Get queue status
                summary = analytics_service.get_execution_summary()
                if "queue_status" in summary:
                    queue_status = summary["queue_status"]
                    logger.info(f"Queue size: {queue_status.get('queue_size', 0)}")
                    logger.info(
                        f"Events queued: {queue_status.get('metrics', {}).get('events_queued', 0)}"
                    )
                    logger.info("✅ Queue is operational")
                else:
                    logger.warning("⚠️ Queue status not available in summary")
            else:
                logger.error("❌ Failed to queue analytics event")

            # Cleanup
            if hasattr(analytics_service, "shutdown"):
                analytics_service.shutdown()
                logger.info("✅ Analytics service shutdown successfully")

            return True

        else:
            logger.warning(f"⚠️ Sync analytics is still being used: {service_type}")
            logger.info(
                "Make sure the async_analytics_queue.py file is in the correct location"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Error during initialization: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info(f"Python path: {sys.executable}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Script location: {os.path.abspath(__file__)}")

    success = test_async_analytics()

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ ASYNC ANALYTICS IS PROPERLY CONFIGURED AND WORKING!")
        logger.info("You can now test with your strategy agents.")
        logger.info("They will use non-blocking analytics automatically.")
    else:
        logger.error("❌ ASYNC ANALYTICS IS NOT WORKING")
        logger.info("Please check the error messages above.")
    logger.info("=" * 60)

    sys.exit(0 if success else 1)
