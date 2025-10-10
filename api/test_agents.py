#!/usr/bin/env python3
"""Test script to verify agents are working with Secret Manager integration."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Set required environment variables if not present
os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
os.environ.setdefault("VERTEX_AI_LOCATION", "us-central1")


async def test_agents():
    """Test both KEN-E and Strategy Supervisor agents."""

    print("=" * 60)
    print("Testing Agent Engine Integration with Secret Manager")
    print("=" * 60)

    # Test loading environment variables
    from src.kene_api.utils.secrets import get_env_or_secret

    print("\n1. Testing Secret Manager Integration:")
    print("-" * 40)

    # Test KEN-E engine ID
    ken_e_id = get_env_or_secret("KEN_E_ENGINE_ID")
    if ken_e_id:
        print("✅ KEN_E_ENGINE_ID loaded from Secret Manager")
        print(f"   Engine ID: {ken_e_id[:50]}...")
    else:
        print("❌ Failed to load KEN_E_ENGINE_ID")

    # Test Strategy Supervisor engine ID
    strategy_id = get_env_or_secret("STRATEGY_SUPERVISOR_ENGINE_ID")
    if strategy_id:
        print("✅ STRATEGY_SUPERVISOR_ENGINE_ID loaded from Secret Manager")
        print(f"   Engine ID: {strategy_id[:50]}...")
    else:
        print("❌ Failed to load STRATEGY_SUPERVISOR_ENGINE_ID")

    # Test WANDB API key (just verify it loads, don't print it)
    wandb_key = get_env_or_secret("WANDB_API_KEY")
    if wandb_key:
        print("✅ WANDB_API_KEY loaded from Secret Manager")
        print(f"   Key length: {len(wandb_key)} characters")
    else:
        print("❌ Failed to load WANDB_API_KEY")

    print("\n2. Testing Agent Engine Connectivity:")
    print("-" * 40)

    try:
        # Initialize Vertex AI
        import vertexai
        from vertexai.preview import reasoning_engines

        vertexai.init(project="ken-e-dev", location="us-central1")

        # Test KEN-E agent
        if ken_e_id:
            try:
                print("Connecting to KEN-E agent...")
                ken_e_agent = reasoning_engines.ReasoningEngine(ken_e_id)
                print("✅ Successfully connected to KEN-E agent")

                # Try a simple query
                print("   Testing agent response...")
                response = ken_e_agent.query(
                    messages=[{"role": "user", "content": "Hello, who are you?"}]
                )
                if response:
                    print("✅ Agent responded successfully")
                    print(f"   Response preview: {str(response)[:100]}...")
            except Exception as e:
                print(f"❌ Failed to connect to KEN-E agent: {e}")

        # Test Strategy Supervisor
        if strategy_id:
            try:
                print("\nConnecting to Strategy Supervisor...")
                strategy_agent = reasoning_engines.ReasoningEngine(strategy_id)
                print("✅ Successfully connected to Strategy Supervisor")
            except Exception as e:
                print(f"❌ Failed to connect to Strategy Supervisor: {e}")

    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agents())
