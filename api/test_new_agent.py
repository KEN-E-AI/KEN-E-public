#!/usr/bin/env python3
"""
Test the newly deployed agent to debug the 400 error.
"""

import os
import vertexai
from vertexai import agent_engines

# Configuration
project_id = "ken-e-dev"
location = "us-central1"
agent_engine_id = "projects/525657242938/locations/us-central1/reasoningEngines/9101849613706461184"

print(f"Testing Agent Engine: {agent_engine_id}")
print("=" * 60)

# Initialize Vertex AI
vertexai.init(project=project_id, location=location)

try:
    # Get the agent engine
    print("Getting agent engine...")
    agent_engine = agent_engines.get(agent_engine_id)
    print(f"✅ Agent retrieved successfully")
    
    # Test with a simple message first
    print("\n1. Testing with simple message...")
    response = agent_engine.stream_query(
        message="Hello, please respond with 'I am working'",
        user_id="test_user"
    )
    
    chunks = []
    for chunk in response:
        if isinstance(chunk, dict) and 'content' in chunk:
            if isinstance(chunk['content'], dict) and 'parts' in chunk['content']:
                for part in chunk['content']['parts']:
                    if isinstance(part, dict) and 'text' in part:
                        chunks.append(part['text'])
    
    if chunks:
        print(f"✅ Simple test passed: {' '.join(chunks)[:100]}")
    else:
        print("❌ No response from simple test")
    
    # Test with strategy generation format
    print("\n2. Testing with strategy generation format...")
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
    
    print(f"Sending: {test_message[:100]}...")
    
    response = agent_engine.stream_query(
        message=test_message,
        user_id="test_user"
    )
    
    chunks = []
    error_found = False
    for chunk in response:
        if isinstance(chunk, dict) and 'content' in chunk:
            if isinstance(chunk['content'], dict) and 'parts' in chunk['content']:
                for part in chunk['content']['parts']:
                    if isinstance(part, dict) and 'text' in part:
                        text = part['text']
                        chunks.append(text)
                        if 'error' in text.lower() or 'failed' in text.lower():
                            error_found = True
                            print(f"⚠️ Error in response: {text[:200]}")
    
    if chunks:
        full_response = ' '.join(chunks)
        print(f"\n{'❌' if error_found else '✅'} Response preview: {full_response[:500]}")
    else:
        print("❌ No response from strategy test")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete")