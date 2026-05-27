#!/usr/bin/env python3
"""
Test script to verify conversation persistence with ADK sessions.
This script tests the full flow of creating conversations, sending messages,
and retrieving conversation history.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kene_api.auth.models import UserContext
from kene_api.routers.chat import AgentEngineClient, ChatMessage


def setup_environment():
    """Set up environment variables for testing."""
    print("🔧 Setting up test environment...")

    # Set staging environment variables
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"
    os.environ["VERTEX_AI_LOCATION"] = "us-central1"
    os.environ["VERTEX_AI_AGENT_ENGINE_ID"] = (
        "projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232"
    )

    # Remove service account to use user credentials
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    print("  ✅ Environment configured for staging")
    print("  📋 Make sure you've run: gcloud auth application-default login")
    print()


async def test_conversation_persistence():
    """Test the full conversation persistence flow."""

    print("🚀 Testing Conversation Persistence")
    print("=" * 60)

    # Create test user context
    test_user = UserContext(
        user_id="test_persistence_user",
        email="test@example.com",
        accessible_accounts=["test_account"],
        permissions={},
        organization_permissions={},
        account_permissions={},
    )

    try:
        # Initialize the client
        print("🔧 Creating AgentEngineClient...")
        client = AgentEngineClient()
        print("✅ AgentEngineClient created successfully")
        print()

        # Test 1: Create a new conversation
        print("📝 Test 1: Creating new conversation...")
        conversation_name = f"Test Chat {datetime.now().strftime('%H:%M:%S')}"
        session_id = await client.create_conversation(
            user_id=test_user.user_id, conversation_name=conversation_name
        )
        print(f"✅ Created conversation with session ID: {session_id}")
        print(f"📛 Conversation name: {conversation_name}")
        print()

        # Test 2: Send a message to the conversation
        print("💬 Test 2: Sending message to conversation...")
        test_messages = [
            ChatMessage(role="user", content="Hello! Can you tell me about Apple Inc?")
        ]

        response, returned_session_id = await client.chat_completion(
            messages=test_messages,
            user_context=test_user,
            session_id=session_id,
            conversation_name=conversation_name,
        )

        print("✅ Message sent successfully")
        print(f"📥 Response: {response[:100]}...")
        print(f"🆔 Returned session ID: {returned_session_id}")
        print(f"🔗 Session IDs match: {session_id == returned_session_id}")
        print()

        # Test 3: Send another message to build conversation history
        print("💬 Test 3: Sending follow-up message...")
        test_messages_2 = [
            ChatMessage(role="user", content="Hello! Can you tell me about Apple Inc?"),
            ChatMessage(role="assistant", content=response),
            ChatMessage(
                role="user", content="What about their recent financial performance?"
            ),
        ]

        response_2, returned_session_id_2 = await client.chat_completion(
            messages=test_messages_2, user_context=test_user, session_id=session_id
        )

        print("✅ Follow-up message sent successfully")
        print(f"📥 Response: {response_2[:100]}...")
        print(f"🆔 Session ID consistency: {session_id == returned_session_id_2}")
        print()

        # Test 4: List all conversations for the user
        print("📋 Test 4: Listing all conversations...")
        conversations = await client.get_user_conversations(test_user.user_id)
        print(f"✅ Found {len(conversations)} conversations")

        # Find our test conversation
        test_conversation = None
        for conv in conversations:
            if conv.session_id == session_id:
                test_conversation = conv
                break

        if test_conversation:
            print("✅ Test conversation found in list!")
            print(f"   📛 Name: {test_conversation.conversation_name}")
            print(f"   🆔 Session ID: {test_conversation.session_id}")
            print(f"   📊 Message count: {test_conversation.message_count}")
            print(f"   📅 Created: {test_conversation.created_at}")
            print(f"   🕐 Updated: {test_conversation.last_updated}")
        else:
            print("❌ Test conversation NOT found in conversation list!")
            print("Available conversations:")
            for conv in conversations:
                print(f"   - {conv.conversation_name} (ID: {conv.session_id})")
        print()

        # Test 5: Retrieve conversation history
        print("🔍 Test 5: Retrieving conversation history...")
        try:
            history = await client.get_conversation_history(
                test_user.user_id, session_id
            )
            if history:
                print("✅ Conversation history retrieved!")
                print(f"📊 History type: {type(history)}")
                if hasattr(history, "messages") and history.messages:
                    print(f"💬 Found {len(history.messages)} messages in history")
                    for i, msg in enumerate(history.messages):
                        role = getattr(msg, "role", "unknown")
                        content = getattr(msg, "content", str(msg))[:50]
                        print(f"   {i + 1}. [{role}]: {content}...")
                else:
                    print("⚠️  History object exists but no messages found")
                    print(f"🔍 History structure: {history}")
            else:
                print("❌ No conversation history found!")
        except Exception as history_error:
            print(f"❌ Error retrieving conversation history: {history_error}")
        print()

        # Test 6: Create another conversation to test multiple conversations
        print("📝 Test 6: Creating second conversation...")
        session_id_2 = await client.create_conversation(
            user_id=test_user.user_id,
            conversation_name=f"Second Test Chat {datetime.now().strftime('%H:%M:%S')}",
        )
        print(f"✅ Created second conversation: {session_id_2}")

        # Send a message to the second conversation
        response_3, _ = await client.chat_completion(
            messages=[ChatMessage(role="user", content="Tell me about Microsoft.")],
            user_context=test_user,
            session_id=session_id_2,
        )
        print("✅ Sent message to second conversation")
        print()

        # Test 7: List conversations again to see both
        print("📋 Test 7: Listing all conversations (should show 2+)...")
        all_conversations = await client.get_user_conversations(test_user.user_id)
        print(f"✅ Found {len(all_conversations)} total conversations")

        test_sessions = [session_id, session_id_2]
        found_sessions = []

        for conv in all_conversations:
            if conv.session_id in test_sessions:
                found_sessions.append(conv.session_id)
                print(f"   ✅ Found: {conv.conversation_name} (ID: {conv.session_id})")

        missing_sessions = set(test_sessions) - set(found_sessions)
        if missing_sessions:
            print(f"   ❌ Missing sessions: {missing_sessions}")
        else:
            print("   🎉 All test sessions found!")
        print()

        # Summary
        print("📊 TEST SUMMARY")
        print("=" * 30)
        print(f"✅ Conversation creation: {'PASS' if session_id else 'FAIL'}")
        print(f"✅ Message sending: {'PASS' if response else 'FAIL'}")
        print(
            f"✅ Session ID consistency: {'PASS' if session_id == returned_session_id else 'FAIL'}"
        )
        print(f"✅ Conversation listing: {'PASS' if test_conversation else 'FAIL'}")
        print(
            f"✅ Multiple conversations: {'PASS' if len(found_sessions) == 2 else 'FAIL'}"
        )
        print(f"✅ History retrieval: {'PASS' if history else 'FAIL'}")

        if all(
            [
                session_id,
                response,
                session_id == returned_session_id,
                test_conversation,
                len(found_sessions) == 2,
            ]
        ):
            print("\n🎉 ALL TESTS PASSED! Conversation persistence is working!")
        else:
            print("\n⚠️  Some tests failed. Check the details above.")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def main():
    """Main test function."""
    setup_environment()

    try:
        success = asyncio.run(test_conversation_persistence())

        if success:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
