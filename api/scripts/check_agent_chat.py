#!/usr/bin/env python3
"""
Test script to verify the Agent Engine chat functionality works locally.
This will test the AgentEngineClient class directly without running the full API.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the API root to the Python path (parent of scripts directory)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our chat module
from src.kene_api.auth.models import UserContext
from src.kene_api.routers.chat import AgentEngineClient, ChatMessage


def load_staging_env():
    """Load environment variables for staging using user credentials"""
    # Use staging configuration since that's where the Agent Engine is deployed
    env_overrides = {
        "GOOGLE_CLOUD_PROJECT_ID": "ken-e-staging",
        "VERTEX_AI_LOCATION": "us-central1",
        "VERTEX_AI_AGENT_ENGINE_ID": "projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232",
    }

    print("📋 Setting up staging environment variables...")
    for key, value in env_overrides.items():
        os.environ[key] = value
        print(f"  ✅ {key}={value}")

    # Remove any service account credentials to force use of user credentials
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        print("  🗑️ Removed GOOGLE_APPLICATION_CREDENTIALS to use user credentials")

    print("📋 Will use user credentials from 'gcloud auth application-default login'")
    print("   Make sure you've run: gcloud auth application-default login")

    return True


async def test_agent_chat():
    """Test the agent chat functionality"""
    print("🚀 Testing Agent Engine Chat Integration")
    print("=" * 50)

    # Load environment
    if not load_staging_env():
        return

    # Check required environment variables
    required_vars = [
        "VERTEX_AI_AGENT_ENGINE_ID",
        "GOOGLE_CLOUD_PROJECT_ID",
        "VERTEX_AI_LOCATION",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print(f"✅ {var}={os.getenv(var)}")

    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return

    print("\n🔧 Creating AgentEngineClient...")
    try:
        client = AgentEngineClient()
        print("✅ AgentEngineClient created successfully")
    except Exception as e:
        print(f"❌ Failed to create AgentEngineClient: {e}")
        return

    print("\n🔗 Testing Agent Engine connection...")
    try:
        # This will trigger the lazy loading of the agent engine
        agent_engine = client.agent_engine
        if agent_engine:
            print("✅ Successfully connected to Agent Engine")
            print(f"🏷️ Agent Engine type: {type(agent_engine)}")

            # Log available methods
            methods = [
                method for method in dir(agent_engine) if not method.startswith("_")
            ]
            print(f"📋 Available methods: {', '.join(methods)}")

            # Try to understand what this object actually is
            if hasattr(agent_engine, "__class__"):
                print(f"🏷️ Agent Engine class: {agent_engine.__class__}")
                print(f"🏷️ Agent Engine MRO: {agent_engine.__class__.__mro__}")

            # Let's inspect the stream_query method signature
            if hasattr(agent_engine, "stream_query"):
                import inspect

                try:
                    sig = inspect.signature(agent_engine.stream_query)
                    print(f"🔍 stream_query signature: {sig}")
                except Exception as e:
                    print(f"❌ Could not get stream_query signature: {e}")

            # Also check create_session signature
            if hasattr(agent_engine, "create_session"):
                try:
                    sig = inspect.signature(agent_engine.create_session)
                    print(f"🔍 create_session signature: {sig}")
                except Exception as e:
                    print(f"❌ Could not get create_session signature: {e}")
        else:
            print("❌ agent_engine is None")
            return
    except Exception as e:
        print(f"❌ Failed to connect to Agent Engine: {e}")
        print(f"Error type: {type(e).__name__}")

        # Let's try to understand what's happening
        print("\n🔍 Debugging the connection...")
        print(f"Project ID: {os.getenv('GOOGLE_CLOUD_PROJECT_ID')}")
        print(f"Location: {os.getenv('VERTEX_AI_LOCATION')}")
        print(f"Agent Engine ID: {os.getenv('VERTEX_AI_AGENT_ENGINE_ID')}")
        print(f"Credentials: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        return

    print("\n💬 Testing chat completion...")

    # Create test data
    test_messages = [
        ChatMessage(
            role="user",
            content="Hello! What can you help me with?",
            timestamp="2025-01-31T12:00:00Z",
        )
    ]

    test_user = UserContext(
        user_id="test_user_123",
        email="test@example.com",
        accessible_accounts=[],
        permissions={},
        organization_permissions={},
    )

    test_session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        print(f"📤 Sending message: '{test_messages[0].content}'")
        print(f"👤 User: {test_user.email}")
        print(f"🆔 Session: {test_session_id}")

        response = await client.chat_completion(
            messages=test_messages, user_context=test_user, session_id=test_session_id
        )

        print("\n✅ Chat completion successful!")
        print(f"📥 Raw response: {response}")
        print(f"📏 Response length: {len(response)} characters")
        print(f"🔍 Response type: {type(response)}")

        # Test what the API would actually return to frontend
        if isinstance(response, str) and response.startswith("{'parts'"):
            import ast

            try:
                parsed = ast.literal_eval(response)
                if isinstance(parsed, dict) and "parts" in parsed:
                    api_response = ""
                    for part in parsed["parts"]:
                        if isinstance(part, dict) and "text" in part:
                            api_response += part["text"]
                    print(f"🔧 API would return: {api_response}")
            except:
                print("🔧 Could not parse response for API preview")

    except Exception as e:
        print(f"❌ Chat completion failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()
        return

    print("\n🌊 Testing streaming chat completion...")
    try:
        print(f"📤 Streaming message: '{test_messages[0].content}'")

        response_parts = []
        async for chunk in client.stream_chat_completion(
            messages=test_messages,
            user_context=test_user,
            session_id=test_session_id + "_stream",
        ):
            response_parts.append(chunk)
            print(f"📥 Chunk: {chunk[:50]}...")

        full_response = "".join(response_parts)
        print("\n✅ Streaming completion successful!")
        print(f"📥 Full response: {full_response}")
        print(f"📏 Response length: {len(full_response)} characters")
        print(f"🧩 Chunks received: {len(response_parts)}")

    except Exception as e:
        print(f"❌ Streaming completion failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()

    print("\n✅ Agent chat test completed!")


if __name__ == "__main__":
    asyncio.run(test_agent_chat())
