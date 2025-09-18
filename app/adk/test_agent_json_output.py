#!/usr/bin/env python
"""Test script to directly call the deployed agent and check its JSON output."""

import os
import json
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport import requests as google_requests
from vertexai.preview import reasoning_engines

# Load environment variables
load_dotenv("../../api/.env")

# Get the project and location
PROJECT_ID = "525657242938"
LOCATION = "us-central1"
ENGINE_ID = "1315935098540916736"  # Latest deployment with state placeholders

# Initialize Vertex AI
import vertexai
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Get the reasoning engine
engine_resource_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"
print(f"Testing engine: {engine_resource_name}")

# Create the client
client = reasoning_engines.ReasoningEngine(engine_resource_name)

# Test with a simple strategy request
test_input = {
    "messages": [
        {
            "role": "user",
            "content": "Generate a business strategy for a technology company focused on AI solutions."
        }
    ],
    "session_id": "test_json_output_123"
}

print("\n=== Sending test request to check JSON output ===")
print(f"Input: {json.dumps(test_input, indent=2)}")

try:
    # Check available methods
    print(f"Available methods: {[m for m in dir(client) if not m.startswith('_')]}")

    # Query the engine - try different methods
    if hasattr(client, 'execute'):
        response = client.execute(
            messages=test_input["messages"],
            session_id=test_input["session_id"]
        )
    elif hasattr(client, 'invoke'):
        response = client.invoke(
            messages=test_input["messages"],
            session_id=test_input["session_id"]
        )
    else:
        # Try direct execution
        response = client.query(
            input=test_input
        )
    
    print(f"\n=== Raw Response Type: {type(response)} ===")
    print(f"Raw Response: {response}")
    
    # Check if response is a dict
    if isinstance(response, dict):
        # Check if it has 'content' key
        if 'content' in response:
            content = response['content']
            print(f"\n=== Content Type: {type(content)} ===")
            print(f"Content (first 500 chars): {str(content)[:500]}")
            
            # Check if content starts with ```json
            if isinstance(content, str):
                if content.strip().startswith("```json"):
                    print("\n❌ ERROR: Agent is still wrapping JSON in markdown code blocks!")
                    print("The agent output starts with: ```json")
                    
                    # Try to extract the JSON
                    if "```json" in content and "```" in content[7:]:
                        json_str = content[content.index("```json")+7:content.rindex("```")].strip()
                        try:
                            parsed = json.loads(json_str)
                            print(f"\n✅ JSON is valid after removing markdown wrapper")
                            print(f"Parsed keys: {list(parsed.keys())}")
                        except json.JSONDecodeError as e:
                            print(f"\n❌ JSON is invalid even after removing wrapper: {e}")
                else:
                    # Try to parse as direct JSON
                    try:
                        parsed = json.loads(content)
                        print(f"\n✅ SUCCESS: Agent returned pure JSON without markdown wrapper!")
                        print(f"Parsed keys: {list(parsed.keys())}")
                    except json.JSONDecodeError:
                        print(f"\n⚠️ Content is not JSON and doesn't have markdown wrapper")
                        print(f"Content preview: {content[:200]}")
            else:
                print(f"\n⚠️ Content is not a string, it's a {type(content)}")
        else:
            print(f"\n⚠️ Response doesn't have 'content' key. Keys: {list(response.keys())}")
    else:
        print(f"\n⚠️ Response is not a dict, it's a {type(response)}")
        
except Exception as e:
    print(f"\n❌ Error calling engine: {e}")
    import traceback
    traceback.print_exc()