#!/usr/bin/env python3
"""
Test strategy generation with the newly deployed agent.
"""

import os
import asyncio
from src.kene_api.tasks.strategy_tasks import trigger_strategy_generation

# Set the new agent engine ID
os.environ['VERTEX_AI_AGENT_ENGINE_ID'] = 'projects/525657242938/locations/us-central1/reasoningEngines/9101849613706461184'

async def test_strategy_generation():
    """Test strategy document generation."""
    print("Testing strategy generation with new agent...")
    print("=" * 60)
    
    # Test parameters
    test_params = {
        "company_name": "TestCompany",
        "industry": "Technology",
        "websites": ["testcompany.com"],
        "customer_regions": ["US"],
        "account_id": "test_acc_123",
        "user_id": "test_user",
        "annual_ad_budget": 50000
    }
    
    print(f"Parameters: {test_params}")
    print("=" * 60)
    
    try:
        # Call the strategy generation
        result = await trigger_strategy_generation(**test_params)
        
        if result.get("success"):
            print("✅ Strategy generation successful!")
            print(f"Documents created: {result.get('documents_created', [])}")
            if "message" in result:
                print(f"Message: {result['message'][:500]}...")
        else:
            print("❌ Strategy generation failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
            if "message" in result:
                print(f"Message: {result['message'][:500]}...")
        
        return result
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(test_strategy_generation())
    print("\n" + "=" * 60)
    print("Test complete")