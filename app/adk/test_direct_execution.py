#!/usr/bin/env python3
"""
Test script for direct sequential execution of strategy agents.
"""

import logging
import os
import sys
from pathlib import Path

# Add the app/adk directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the orchestrator
from agents.strategy_agent.orchestrator import execute_strategy_generation

def test_strategy_generation():
    """Test the strategy generation with direct execution."""

    # Test parameters
    test_params = {
        "company_name": "Test AI Solutions",
        "industry": "Technology",
        "websites": "www.example.com",
        "customer_regions": "North America,Europe",
        "account_id": "test_account_123",
        "user_id": "test_user_456",
        "annual_ad_budget": 100000.0,
        "project_id": "ken-e-dev"
    }

    print(f"\n{'='*60}")
    print("TESTING DIRECT SEQUENTIAL EXECUTION")
    print(f"{'='*60}\n")
    print(f"Company: {test_params['company_name']}")
    print(f"Industry: {test_params['industry']}")
    print(f"Account ID: {test_params['account_id']}")
    print(f"\n{'='*60}\n")

    # Run the strategy generation
    result = execute_strategy_generation(**test_params)

    print(f"\n{'='*60}")
    print("RESULT:")
    print(f"{'='*60}")
    print(result)
    print(f"{'='*60}\n")

    return result

if __name__ == "__main__":
    # Set environment variables if needed
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-dev"
    os.environ["ENVIRONMENT"] = "development"

    try:
        result = test_strategy_generation()
        if "Successfully generated" in result:
            print("✅ Test PASSED")
            sys.exit(0)
        else:
            print("❌ Test FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Test FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)