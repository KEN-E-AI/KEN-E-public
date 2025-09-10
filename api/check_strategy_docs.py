#!/usr/bin/env python3
"""Quick script to check strategy documents in Firestore"""

import os
from google.cloud import firestore
from google.oauth2 import service_account

# Set up credentials
os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-dev"

# Initialize Firestore with default credentials
db = firestore.Client(project="ken-e-dev")

account_id = "acc_dc291ae14bb74219b7882c1b13c2161d"
collection_name = f"strategy_docs_{account_id}"

print(f"Checking Firestore collection: {collection_name}")
print("=" * 50)

# Get all documents
docs = db.collection(collection_name).stream()

doc_count = 0
strategy_types = []

for doc in docs:
    doc_count += 1
    doc_data = doc.to_dict()
    doc_type = doc_data.get("doc_type", "unknown")
    strategy_types.append(doc_type)
    
    print(f"Document ID: {doc.id}")
    print(f"  Type: {doc_type}")
    print(f"  Version: {doc_data.get('version', 'unknown')}")
    print(f"  Created: {doc_data.get('created_at', 'unknown')}")
    
    if "content" in doc_data:
        content = doc_data["content"]
        if isinstance(content, dict):
            print(f"  Content keys: {list(content.keys())[:5]}...")
        else:
            print(f"  Content length: {len(str(content))} chars")
    print()

print("=" * 50)

if doc_count == 0:
    print("❌ No documents found yet - strategy generation may still be in progress")
else:
    print(f"✅ Total documents found: {doc_count}")
    print(f"Strategy types: {strategy_types}")
    
    expected = [
        "business_strategy",
        "competitive_strategy", 
        "customer_strategy",
        "marketing_strategy",
        "brand_guidelines"
    ]
    missing = [s for s in expected if s not in strategy_types]
    
    if missing:
        print(f"⚠️  Missing strategies: {missing}")
    else:
        print("✅ All 5 strategy documents are present!")