#!/usr/bin/env python3
"""
Test the agent engine directly to debug strategy generation.
"""

import os
import vertexai
from vertexai import agent_engines

# Configuration
project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
agent_engine_id = "projects/525657242938/locations/us-central1/reasoningEngines/7673997425597480960"

print(f"Testing Agent Engine: {agent_engine_id}")
print("=" * 60)

# Initialize Vertex AI
vertexai.init(project=project_id, location=location)

try:
    # Get the agent engine
    print("Getting agent engine...")
    agent_engine = agent_engines.get(agent_engine_id)
    print(f"✅ Agent retrieved successfully")
    
    # Test with strategy generation format
    print("\nTesting strategy generation...")
    test_message = """Generate all 5 strategy documents for TestCompany

Please execute strategy generation with these parameters:
- company_name: TestCompany
- industry: Technology  
- websites: testcompany.com
- customer_regions: US
- account_id: test_acc_123
- user_id: test_user
- annual_ad_budget: 50000
- project_id: ken-e-dev"""
    
    print(f"Sending message ({len(test_message)} chars)...")
    
    response = agent_engine.stream_query(
        message=test_message,
        user_id="test_user"
    )
    
    chunks = []
    error_found = False
    strategy_available = False
    
    for chunk in response:
        if isinstance(chunk, dict) and 'content' in chunk:
            if isinstance(chunk['content'], dict) and 'parts' in chunk['content']:
                for part in chunk['content']['parts']:
                    if isinstance(part, dict) and 'text' in part:
                        text = part['text']
                        chunks.append(text)
                        
                        # Check for key phrases
                        if 'strategy agent not available' in text.lower():
                            error_found = True
                            print(f"\n⚠️ Strategy agent not available")
                        elif 'error' in text.lower() or 'failed' in text.lower():
                            error_found = True
                            print(f"\n⚠️ Error detected: {text[:200]}")
                        elif 'business strategy' in text.lower() or 'competitive analysis' in text.lower():
                            strategy_available = True
                            print(f"\n✅ Strategy content detected")
    
    if chunks:
        full_response = ' '.join(chunks)
        print(f"\n{'❌' if error_found else '✅'} Response length: {len(full_response)} chars")
        print(f"\nResponse preview:\n{full_response[:1000]}")
        
        if strategy_available:
            print("\n✅ Strategy generation appears to be working!")
        elif error_found:
            print("\n❌ Strategy agent is not properly deployed")
    else:
        print("❌ No response from agent")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete")