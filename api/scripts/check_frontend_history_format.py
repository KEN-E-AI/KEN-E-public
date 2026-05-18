#!/usr/bin/env python3
"""
Test script to verify the frontend history format matches what our frontend expects.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kene_api.routers.chat import AgentEngineClient
from kene_api.auth.models import UserContext

def setup_environment():
    """Set up environment variables for testing."""
    print("🔧 Testing frontend history format...")
    
    # Set staging environment variables
    os.environ['GOOGLE_CLOUD_PROJECT_ID'] = 'ken-e-staging'
    os.environ['VERTEX_AI_LOCATION'] = 'us-central1'
    os.environ['VERTEX_AI_AGENT_ENGINE_ID'] = 'projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232'
    
    # Remove service account to use user credentials
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    
    print("  ✅ Environment configured")

async def test_frontend_history_format():
    """Test that the history format matches frontend expectations."""
    
    print("🧪 Testing Frontend History Format")
    print("=" * 50)
    
    # Create test user context
    test_user = UserContext(
        user_id="test_frontend_user",
        email="test@example.com",
        accessible_accounts=["test_account"],
        permissions={},
        organization_permissions={},
        account_permissions={}
    )
    
    try:
        # Initialize the client
        client = AgentEngineClient()
        
        # Get existing conversations to test with
        conversations = await client.get_user_conversations(test_user.user_id)
        
        if not conversations:
            print("❌ No conversations found to test with")
            return False
            
        # Test with the first conversation
        test_conversation = conversations[0]
        print(f"📋 Testing with conversation: {test_conversation.conversation_name}")
        print(f"🆔 Session ID: {test_conversation.session_id}")
        
        # Get conversation history
        history = await client.get_conversation_history(
            user_id=test_user.user_id,
            session_id=test_conversation.session_id
        )
        
        if not history:
            print("❌ No history returned")
            return False
            
        print(f"✅ History retrieved: {type(history)}")
        print(f"📊 History keys: {list(history.keys())}")
        
        # Test frontend parsing logic
        if history and (history.get('messages') or history.get('events')):
            events = history.get('events', []) or history.get('messages', [])
            print(f"📈 Found {len(events)} events to parse")
            
            # Simulate frontend parsing
            parsed_messages = []
            for index, event in enumerate(events):
                print(f"\n🔍 Event {index + 1}:")
                print(f"   Raw event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
                
                # Frontend parsing logic
                content = 'Empty message'
                role = 'assistant'
                
                if isinstance(event, dict):
                    if event.get('content') and isinstance(event['content'], dict):
                        content_obj = event['content']
                        if content_obj.get('parts') and isinstance(content_obj['parts'], list):
                            for part in content_obj['parts']:
                                if isinstance(part, dict) and part.get('text'):
                                    content = part['text']
                                    break
                        role = event.get('role', content_obj.get('role', 'assistant'))
                    elif event.get('content'):
                        content = str(event['content'])
                        role = event.get('role', 'assistant')
                
                parsed_message = {
                    'id': str(index),
                    'content': content[:100] + ('...' if len(content) > 100 else ''),
                    'isUser': role == 'user',
                    'role': role,
                    'timestamp': event.get('timestamp', '')
                }
                
                parsed_messages.append(parsed_message)
                print(f"   ✅ Parsed: [{role}] {content[:50]}...")
            
            print(f"\n📊 Successfully parsed {len(parsed_messages)} messages")
            print("🎉 Frontend parsing test PASSED!")
            
            # Show summary
            user_messages = [m for m in parsed_messages if m['isUser']]
            assistant_messages = [m for m in parsed_messages if not m['isUser']]
            print(f"   👤 User messages: {len(user_messages)}")
            print(f"   🤖 Assistant messages: {len(assistant_messages)}")
            
            return True
        else:
            print("❌ No events found in history")
            return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    setup_environment()
    
    try:
        success = asyncio.run(test_frontend_history_format())
        
        if success:
            print("\n✅ Frontend history format test completed successfully!")
            print("🎯 The frontend should now be able to parse conversation history properly")
        else:
            print("\n❌ Frontend history format test failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()