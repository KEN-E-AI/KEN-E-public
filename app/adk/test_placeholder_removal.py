#!/usr/bin/env python3
"""
Test script to verify that the _placeholder document is removed
when all 5 strategy documents are created.
"""

import os
import sys
import time
from datetime import datetime, timezone
from google.cloud import firestore

# Add the parent directory to the path so we can import the FirestoreClient
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.strategy_agent.firestore import FirestoreClient

def test_placeholder_removal():
    """Test the placeholder removal functionality."""
    
    # Initialize Firestore client
    print("Initializing Firestore client...")
    client = FirestoreClient(project_id="ken-e-dev")
    
    if not client.is_initialized():
        print("Failed to initialize Firestore client")
        return False
    
    # Create a test account ID
    test_account_id = f"test_account_{int(time.time())}"
    collection_name = f"strategy_docs_{test_account_id}"
    
    print(f"\nTesting with account ID: {test_account_id}")
    print(f"Collection name: {collection_name}")
    
    # Step 1: Create the placeholder document (simulating account creation)
    print("\n1. Creating placeholder document...")
    placeholder_data = {
        "account_id": test_account_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "test_script",
        "type": "placeholder",
        "description": "Initial placeholder document - collection ready for business strategy documents",
        "organization_id": "test_org",
    }
    
    placeholder_ref = client.db.collection(collection_name).document("_placeholder")
    placeholder_ref.set(placeholder_data)
    print("   ✓ Placeholder document created")
    
    # Verify placeholder exists
    if placeholder_ref.get().exists:
        print("   ✓ Verified placeholder exists")
    else:
        print("   ✗ Placeholder not found after creation")
        return False
    
    # Step 2: Add 4 strategy documents (placeholder should remain)
    print("\n2. Adding 4 strategy documents (placeholder should remain)...")
    docs_to_add = [
        'business_strategy',
        'competitive_analysis',
        'customer_journey',
        'marketing_strategy'
    ]
    
    for doc_type in docs_to_add:
        print(f"   - Saving {doc_type}...")
        success = client.save_strategy_document_sync(
            account_id=test_account_id,
            doc_type=doc_type,
            content={"test": f"Content for {doc_type}", "timestamp": datetime.now(timezone.utc).isoformat()},
            user_id="test_script"
        )
        if success:
            print(f"     ✓ {doc_type} saved")
        else:
            print(f"     ✗ Failed to save {doc_type}")
            return False
    
    # Verify placeholder still exists
    if placeholder_ref.get().exists:
        print("   ✓ Placeholder still exists (only 4/5 documents)")
    else:
        print("   ✗ Placeholder was removed too early!")
        return False
    
    # Step 3: Add the 5th document (placeholder should be removed)
    print("\n3. Adding the 5th strategy document (brand_guidelines)...")
    success = client.save_strategy_document_sync(
        account_id=test_account_id,
        doc_type='brand_guidelines',
        content={"test": "Content for brand_guidelines", "timestamp": datetime.now(timezone.utc).isoformat()},
        user_id="test_script"
    )
    
    if success:
        print("   ✓ brand_guidelines saved")
    else:
        print("   ✗ Failed to save brand_guidelines")
        return False
    
    # Verify placeholder is now removed
    time.sleep(1)  # Give Firestore a moment to process
    if not placeholder_ref.get().exists:
        print("   ✓ Placeholder has been removed (all 5 documents complete)")
    else:
        print("   ✗ Placeholder still exists after all 5 documents!")
        return False
    
    # Step 4: Verify all 5 documents exist
    print("\n4. Verifying all 5 strategy documents exist...")
    all_docs = [
        'business_strategy',
        'competitive_analysis',
        'customer_journey',
        'marketing_strategy',
        'brand_guidelines'
    ]
    
    for doc_type in all_docs:
        doc_ref = client.db.collection(collection_name).document(doc_type)
        if doc_ref.get().exists:
            print(f"   ✓ {doc_type} exists")
        else:
            print(f"   ✗ {doc_type} not found")
            return False
    
    # Step 5: Clean up test data
    print("\n5. Cleaning up test data...")
    for doc_type in all_docs:
        doc_ref = client.db.collection(collection_name).document(doc_type)
        doc_ref.delete()
        print(f"   - Deleted {doc_type}")
    
    # Also try to delete placeholder in case it still exists
    placeholder_ref.delete()
    
    print("\n✅ Test completed successfully!")
    print("The placeholder document was correctly removed when all 5 strategy documents were created.")
    return True

if __name__ == "__main__":
    # Set up environment
    os.environ['GOOGLE_CLOUD_PROJECT_ID'] = 'ken-e-dev'
    
    print("=" * 60)
    print("Testing Placeholder Document Removal")
    print("=" * 60)
    
    try:
        success = test_placeholder_removal()
        if success:
            sys.exit(0)
        else:
            print("\n❌ Test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)