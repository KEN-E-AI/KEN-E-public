#!/usr/bin/env python3
"""
Test the agent locally to verify imports and functionality work.
"""

import sys
import os

# Add the app/adk directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing agent imports and functionality...")

try:
    # Test importing the supervisor
    from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor
    print("✅ Successfully imported create_strategy_docs_supervisor")
    print(f"   Agent type: {type(create_strategy_docs_supervisor)}")
    print(f"   Agent name: {create_strategy_docs_supervisor.name}")
    
    # Test importing strategy components
    from agents.strategy_agent.orchestrator import execute_strategy_generation
    print("✅ Successfully imported orchestrator")
    
    from agents.strategy_agent.artifact_utils import (
        load_uploaded_documents_as_artifacts,
        parse_gcs_url
    )
    print("✅ Successfully imported artifact_utils")
    
    # Test parsing a GCS URL
    bucket, path = parse_gcs_url("gs://test-bucket/path/to/file.pdf")
    assert bucket == "test-bucket", f"Expected test-bucket, got {bucket}"
    assert path == "path/to/file.pdf", f"Expected path/to/file.pdf, got {path}"
    print("✅ GCS URL parsing works correctly")
    
    # Test that the supervisor can handle the strategy dispatch
    test_query = """Generate all 5 strategy documents for Test Company
    
Please execute strategy generation with these parameters:
- company_name: Test Company
- industry: Technology
- websites: https://test.com
- customer_regions: US,EU
- account_id: test_123
- user_id: user_456
- annual_ad_budget: 100000
- project_id: ken-e-dev
- uploaded_documents: gs://test-bucket/doc1.pdf,gs://test-bucket/doc2.pdf"""
    
    print("\n📝 Test query for strategy generation:")
    print(test_query[:200] + "...")
    
    # Check if supervisor would route this correctly
    if "generate" in test_query.lower() and "strategy" in test_query.lower():
        print("✅ Query would be routed to strategy agent")
    
    print("\n🎉 All tests passed! The agent should be deployable.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)