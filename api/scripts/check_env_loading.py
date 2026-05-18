#!/usr/bin/env python3
"""Test that environment variables are loaded correctly."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_environment():
    """Check if all required environment variables are set."""
    
    print("🔍 Checking environment configuration...")
    print("=" * 60)
    
    # Critical variables
    critical_vars = {
        "GOOGLE_CLOUD_PROJECT_ID": "Google Cloud Project ID",
        "NEO4J_URI": "Neo4j Database URI",
        "NEO4J_USERNAME": "Neo4j Username",
        "NEO4J_PASSWORD": "Neo4j Password",
        "RECAPTCHA_SECRET_KEY": "ReCAPTCHA Secret Key",
    }
    
    # Optional but good to have
    optional_vars = {
        "GOOGLE_APPLICATION_CREDENTIALS": "Service Account File",
        "FIRESTORE_DATABASE_ID": "Firestore Database ID",
        "SENDGRID_API_KEY": "SendGrid API Key",
        "VERTEX_AI_AGENT_ENGINE_ID": "Vertex AI Agent Engine ID",
    }
    
    all_good = True
    
    print("✅ CRITICAL Environment Variables:")
    for var, description in critical_vars.items():
        value = os.getenv(var)
        if value:
            if "PASSWORD" in var or "SECRET" in var or "KEY" in var:
                print(f"   {var}: [REDACTED - {len(value)} chars]")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   ❌ {var}: NOT SET ({description})")
            all_good = False
    
    print("\n📋 OPTIONAL Environment Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            if "KEY" in var:
                print(f"   {var}: [REDACTED - {len(value)} chars]")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   ⚠️  {var}: NOT SET ({description})")
    
    print("\n" + "=" * 60)
    
    if all_good:
        print("✅ All critical environment variables are configured!")
        print("   The API should start without connection errors.")
    else:
        print("❌ Some critical variables are missing.")
        print("   Run: ./scripts/set_environment.sh development")
    
    return all_good

def test_neo4j_connection():
    """Test if we can connect to Neo4j."""
    try:
        from neo4j import AsyncGraphDatabase
        import asyncio
        
        async def test():
            uri = os.getenv("NEO4J_URI")
            username = os.getenv("NEO4J_USERNAME")
            password = os.getenv("NEO4J_PASSWORD")
            
            if not all([uri, username, password]):
                return False
                
            driver = AsyncGraphDatabase.driver(uri, auth=(username, password))
            try:
                async with driver.session() as session:
                    result = await session.run("RETURN 1 as test")
                    data = await result.single()
                    return data["test"] == 1
            finally:
                await driver.close()
        
        result = asyncio.run(test())
        if result:
            print("✅ Neo4j connection successful!")
        else:
            print("❌ Neo4j connection failed!")
        return result
        
    except Exception as e:
        print(f"❌ Error testing Neo4j: {e}")
        return False

if __name__ == "__main__":
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check environment
    env_ok = check_environment()
    
    # Test Neo4j connection if environment is OK
    if env_ok:
        print("\n🔄 Testing Neo4j connection...")
        test_neo4j_connection()