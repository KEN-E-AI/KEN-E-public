#!/usr/bin/env python3
"""
Inspect ADK session to debug strategy generation issues.
"""

import os
import asyncio
from vertexai import agent_engines
import vertexai
from google.adk.sessions import VertexAiSessionService
import json

# Set up environment
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/dvalia/Code/python/KEN-E/api/ken-e-dev.json'

async def inspect_sessions():
    """Inspect ADK sessions and their state."""
    
    print("=" * 60)
    print("ADK SESSION INSPECTION")
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
        
        # Create session service
        print("🔧 Creating Session Service...")
        session_service = VertexAiSessionService(project_id, location)
        
        # List recent sessions
        print("\n📋 Listing recent sessions...")
        try:
            # Try to list sessions (this might need specific API calls)
            # The session service might have a list method or we need to use the agent engine
            agent_engine = agent_engines.get(agent_engine_id)
            
            # Try to get session information
            # Sessions are typically named with patterns like "strategy_acc_*" or "chat_*"
            test_session_ids = [
                "strategy_acc_f48c4580d26a4eaaa350973c08bbe03f",
                "chat_acc_f48c4580d26a4eaaa350973c08bbe03f",
            ]
            
            for session_id in test_session_ids:
                print(f"\n🔍 Checking session: {session_id}")
                try:
                    # Try to query with the session
                    response = agent_engine.stream_query(
                        message="What is the status of strategy generation?",
                        user_id="system_check",
                        session_id=session_id
                    )
                    
                    print(f"  ✅ Session exists!")
                    
                    # Collect response
                    chunks = []
                    for i, chunk in enumerate(response):
                        if i == 0:
                            print(f"  📥 Response structure: {list(chunk.keys()) if isinstance(chunk, dict) else type(chunk)}")
                        
                        if isinstance(chunk, dict):
                            # Check for execution information
                            if 'invocation_id' in chunk:
                                print(f"  🔧 Invocation ID: {chunk['invocation_id']}")
                            if 'author' in chunk:
                                print(f"  👤 Author: {chunk['author']}")
                            if 'actions' in chunk and chunk['actions']:
                                print(f"  🎯 Actions taken: {len(chunk['actions'])} actions")
                                for action in chunk['actions'][:3]:  # Show first 3 actions
                                    print(f"    - {action}")
                            
                            # Extract text content
                            if 'content' in chunk and isinstance(chunk['content'], dict):
                                if 'parts' in chunk['content']:
                                    for part in chunk['content']['parts']:
                                        if isinstance(part, dict) and 'text' in part:
                                            chunks.append(part['text'])
                    
                    if chunks:
                        response_text = ''.join(chunks)
                        print(f"  📝 Response: {response_text[:200]}...")
                        
                except Exception as e:
                    print(f"  ❌ Session not found or error: {str(e)[:100]}")
                    
        except Exception as e:
            print(f"\n❌ Failed to list sessions: {e}")
            
        # Also try to call the agent directly to see what happens
        print("\n" + "=" * 60)
        print("DIRECT AGENT TEST WITH SESSION")
        print("=" * 60)
        
        strategy_message = """Generate all 5 strategy documents for TestCompany

NEW INFORMATION:
Project ID: ken-e-dev
Company to analyze: TestCompany
Company websites: ['https://testcompany.com']
Industry: Technology
Customer regions: United States"""
        
        print(f"📤 Sending test strategy generation request...")
        
        # Create a new session for testing
        test_session_id = f"debug_session_{int(asyncio.get_event_loop().time())}"
        print(f"🔧 Using session ID: {test_session_id}")
        
        try:
            response = agent_engine.stream_query(
                message=strategy_message,
                user_id="debug_user",
                session_id=test_session_id
            )
            
            print("📥 Response chunks:")
            error_found = False
            for i, chunk in enumerate(response):
                print(f"\n  Chunk {i+1}:")
                if isinstance(chunk, dict):
                    # Look for error indicators
                    if 'content' in chunk:
                        content_str = str(chunk['content'])
                        if 'error' in content_str.lower() or 'failed' in content_str.lower():
                            error_found = True
                            print(f"    ⚠️ ERROR DETECTED: {content_str[:500]}")
                    
                    # Show actions if any
                    if 'actions' in chunk and chunk['actions']:
                        print(f"    Actions: {chunk['actions'][:2]}")
                        
            if error_found:
                print("\n⚠️ Errors were detected in the agent response!")
                
        except Exception as e:
            print(f"\n❌ Direct test failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"\n❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n" + "=" * 60)
    print("INSPECTION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    print("Inspecting ADK sessions...\n")
    asyncio.run(inspect_sessions())