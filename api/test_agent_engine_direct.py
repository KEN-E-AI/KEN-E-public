#!/usr/bin/env python3
"""
Direct test of Agent Engine connection and strategy generation.
Tests if we can call the deployed supervisor directly.
"""

import os
import asyncio
from google.cloud import logging as cloud_logging
from vertexai import agent_engines
import vertexai

# Set up environment
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/dvalia/Code/python/KEN-E/api/ken-e-dev.json'

async def test_agent_engine():
    """Test direct connection to Agent Engine."""
    
    print("=" * 60)
    print("AGENT ENGINE DIRECT TEST")
    print("=" * 60)
    
    # Configuration
    project_id = "ken-e-dev"
    location = "us-central1"
    agent_engine_id = "projects/525657242938/locations/us-central1/reasoningEngines/8641004708086939648"
    
    print(f"\n📍 Project: {project_id}")
    print(f"📍 Location: {location}")
    print(f"📍 Agent Engine ID: {agent_engine_id}")
    
    try:
        # Initialize Vertex AI
        print("\n🔧 Initializing Vertex AI...")
        vertexai.init(project=project_id, location=location)
        
        # Get the agent engine
        print("🔧 Getting Agent Engine...")
        agent_engine = agent_engines.get(agent_engine_id)
        print(f"✅ Agent Engine retrieved: {agent_engine}")
        
        # Test with a simple message first
        test_message = "Hello, can you respond?"
        print(f"\n📤 Sending test message: {test_message}")
        
        try:
            # Try stream_query
            print("🔧 Calling stream_query...")
            response = agent_engine.stream_query(
                message=test_message,
                user_id="test_user_123"
            )
            
            print("📥 Response chunks:")
            chunks = []
            for i, chunk in enumerate(response):
                print(f"  Chunk {i+1}: {type(chunk).__name__}")
                if isinstance(chunk, dict):
                    print(f"    Keys: {list(chunk.keys())[:5]}")
                    if 'content' in chunk and isinstance(chunk['content'], dict):
                        if 'parts' in chunk['content']:
                            for part in chunk['content']['parts']:
                                if isinstance(part, dict) and 'text' in part:
                                    text = part['text']
                                    chunks.append(text)
                                    print(f"    Text: {text[:100]}...")
                
            if chunks:
                print(f"\n✅ Received {len(chunks)} text chunks")
                full_response = ''.join(chunks)
                print(f"📝 Full response preview: {full_response[:200]}...")
            else:
                print("\n⚠️ No text chunks received")
                
        except Exception as e:
            print(f"\n❌ stream_query failed: {e}")
            import traceback
            traceback.print_exc()
            
        # Now test strategy generation
        print("\n" + "=" * 60)
        print("STRATEGY GENERATION TEST")
        print("=" * 60)
        
        strategy_message = """Generate all 5 strategy documents for TestCompany

NEW INFORMATION:
Project ID: ken-e-dev
Company to analyze: TestCompany
Company websites: ['https://testcompany.com']
Industry: Technology
Customer regions: United States"""
        
        print(f"📤 Sending strategy generation request...")
        print(f"Message: {strategy_message[:100]}...")
        
        try:
            response = agent_engine.stream_query(
                message=strategy_message,
                user_id="test_user_123"
            )
            
            print("📥 Strategy response chunks:")
            strategy_chunks = []
            for i, chunk in enumerate(response):
                print(f"  Chunk {i+1}: {type(chunk).__name__}")
                if isinstance(chunk, dict) and 'content' in chunk:
                    if isinstance(chunk['content'], dict) and 'parts' in chunk['content']:
                        for part in chunk['content']['parts']:
                            if isinstance(part, dict) and 'text' in part:
                                strategy_chunks.append(part['text'])
                                
            if strategy_chunks:
                print(f"\n✅ Received {len(strategy_chunks)} strategy response chunks")
                strategy_response = ''.join(strategy_chunks)
                print(f"📝 Strategy response preview: {strategy_response[:500]}...")
            else:
                print("\n⚠️ No strategy response chunks received")
                
        except Exception as e:
            print(f"\n❌ Strategy generation failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"\n❌ Failed to connect to Agent Engine: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

def check_cloud_logs():
    """Check Cloud Logs for agent activity."""
    print("\n" + "=" * 60)
    print("CHECKING CLOUD LOGS")
    print("=" * 60)
    
    try:
        client = cloud_logging.Client(project="ken-e-dev")
        
        # Query for logs from our reasoning engine
        filter_str = f'''
        resource.labels.reasoning_engine_id="8641004708086939648"
        OR resource.type="aiplatform.googleapis.com/ReasoningEngine"
        OR logName="projects/ken-e-dev/logs/adk"
        '''
        
        print(f"🔍 Searching for agent logs...")
        print(f"Filter: {filter_str}")
        
        entries = client.list_entries(filter_=filter_str, max_results=20)
        
        count = 0
        for entry in entries:
            count += 1
            print(f"\n📋 Log Entry {count}:")
            print(f"  Timestamp: {entry.timestamp}")
            print(f"  Severity: {entry.severity}")
            if hasattr(entry, 'payload'):
                print(f"  Payload: {str(entry.payload)[:200]}...")
                
        if count == 0:
            print("\n⚠️ No logs found for this agent engine")
            print("This could mean:")
            print("  1. The agent hasn't been called yet")
            print("  2. Logs are in a different location")
            print("  3. There's a permissions issue")
        else:
            print(f"\n✅ Found {count} log entries")
            
    except Exception as e:
        print(f"\n❌ Failed to check Cloud Logs: {e}")
        print("You may need to run: gcloud auth application-default login")

if __name__ == "__main__":
    print("Testing Agent Engine connection...\n")
    
    # Run async test
    asyncio.run(test_agent_engine())
    
    # Check cloud logs
    check_cloud_logs()
    
    print("\n🔍 Note: W&B logs should appear at: https://wandb.ai/YOUR_USERNAME/ken-e-strategy-agent")
    print("If no W&B activity, the agent may not be executing the strategy code properly.")