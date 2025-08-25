#!/usr/bin/env python3
"""
Test account creation and strategy document generation.
"""

import asyncio
import json
import time
from datetime import datetime
from google.cloud import firestore
import requests

async def test_account_creation_and_strategy():
    """Test full account creation flow and check strategy documents."""
    
    # Read the test token
    try:
        with open('/tmp/test_token.txt', 'r') as f:
            token = f.read().strip()
    except:
        print("ERROR: No test token found. Please login first.")
        return
    
    # Generate unique account name
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    account_name = f"TestAccount_{timestamp}"
    account_id = f"acc_test_{timestamp}"
    
    print(f"Creating account: {account_name}")
    print(f"Expected account_id pattern: acc_*")
    
    # Create account via API
    url = "http://localhost:8000/api/v1/accounts/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "account_name": account_name,
        "organization_id": "org_7a25827d222842fea0658f64db7d6aad",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://testcompany.com", "https://testcompany.io"],
        "timezone": "America/New_York",
        "region": ["United States", "Canada"],
        "estimated_annual_ad_budget": 250000
    }
    
    print(f"\nRequest data:")
    print(json.dumps(data, indent=2))
    
    print(f"\nSending POST request to {url}...")
    response = requests.post(url, json=data, headers=headers)
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        account_data = response.json()
        actual_account_id = account_data.get('account_id')
        print(f"✅ Account created successfully")
        print(f"Account ID: {actual_account_id}")
        print(f"Setup Status: {account_data.get('setup_status', 'unknown')}")
    else:
        print(f"❌ Failed to create account: {response.text}")
        return
    
    # Wait a bit for strategy generation to start
    print("\nWaiting 10 seconds for strategy generation to start...")
    await asyncio.sleep(10)
    
    # Check strategy documents
    print(f"\nChecking strategy documents for account {actual_account_id}...")
    
    db = firestore.Client()
    collection_name = f"strategy_docs_{actual_account_id}"
    
    expected_docs = [
        'business_strategy',
        'competitive_strategy',
        'customer_strategy',
        'marketing_strategy',
        'brand_guidelines'
    ]
    
    print(f"Checking collection: {collection_name}")
    
    # Check multiple times to see if documents appear
    max_attempts = 6  # Check for up to 1 minute
    for attempt in range(max_attempts):
        print(f"\nAttempt {attempt + 1}/{max_attempts}...")
        
        found_docs = {}
        for doc_type in expected_docs:
            doc_ref = db.collection(collection_name).document(doc_type)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_data = doc.to_dict()
                found_docs[doc_type] = doc_data
                print(f"✅ Found {doc_type}")
                
                # Check document structure
                if 'content' in doc_data:
                    content = doc_data['content']
                    if isinstance(content, dict):
                        print(f"   - Content keys: {list(content.keys())[:5]}...")
                        print(f"   - Status: {doc_data.get('status', 'unknown')}")
                        print(f"   - Version: {doc_data.get('version', 'unknown')}")
                        
                        # Sample the content to check quality
                        if 'executive_summary' in content:
                            summary = str(content['executive_summary'])[:200]
                            print(f"   - Executive Summary: {summary}...")
                        elif 'text' in content:
                            text = str(content['text'])[:200]
                            print(f"   - Text: {text}...")
                    else:
                        print(f"   - Content type: {type(content).__name__}")
                else:
                    print(f"   - No content field found")
                    print(f"   - Document keys: {list(doc_data.keys())}")
            else:
                print(f"❌ {doc_type} not found")
        
        if len(found_docs) == len(expected_docs):
            print(f"\n🎉 All {len(expected_docs)} strategy documents found!")
            break
        elif len(found_docs) > 0:
            print(f"\n⚠️ Only {len(found_docs)}/{len(expected_docs)} documents found")
            
        if attempt < max_attempts - 1:
            print("Waiting 10 more seconds...")
            await asyncio.sleep(10)
    
    # Final summary
    print("\n" + "="*50)
    print("FINAL SUMMARY")
    print("="*50)
    print(f"Account Name: {account_name}")
    print(f"Account ID: {actual_account_id}")
    print(f"Documents Found: {len(found_docs)}/{len(expected_docs)}")
    
    if found_docs:
        print("\nDocument Quality Check:")
        for doc_type, doc_data in found_docs.items():
            content = doc_data.get('content', {})
            if isinstance(content, dict):
                # Check for actual strategy content vs placeholder
                has_real_content = False
                if 'executive_summary' in content and len(str(content['executive_summary'])) > 50:
                    has_real_content = True
                elif 'text' in content and len(str(content['text'])) > 100:
                    has_real_content = True
                elif any(len(str(v)) > 100 for v in content.values() if isinstance(v, str)):
                    has_real_content = True
                
                if has_real_content:
                    print(f"  ✅ {doc_type}: Has substantial content")
                else:
                    print(f"  ⚠️ {doc_type}: Appears to be placeholder/minimal content")
            else:
                print(f"  ❌ {doc_type}: Invalid content structure")
    
    # Check processing state
    print("\nChecking processing state...")
    state_collection = f"strategy_processing_state_{actual_account_id}"
    state_doc = db.collection(state_collection).document('current_state').get()
    
    if state_doc.exists:
        state_data = state_doc.to_dict()
        print(f"Processing State Found:")
        print(f"  - Current Stage: {state_data.get('current_stage', 'unknown')}")
        print(f"  - Stages Completed: {state_data.get('stages_completed', [])}")
        print(f"  - Stages Remaining: {state_data.get('stages_remaining', [])}")
        print(f"  - Errors: {state_data.get('processing_errors', [])}")
    else:
        print("No processing state found")

if __name__ == "__main__":
    asyncio.run(test_account_creation_and_strategy())