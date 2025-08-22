#!/usr/bin/env python3
"""
Script to remove defaultSettings, name, and recommendedSettings fields 
from all industry template documents in Firestore.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService
from google.cloud.firestore import DELETE_FIELD


def main():
    """Remove specified fields from all industry templates."""
    
    # Initialize Firestore
    firestore_service = FirestoreService()
    
    if not firestore_service.health_check():
        print("Error: Could not connect to Firestore")
        return 1
    
    print("Connected to Firestore")
    
    # Get all industry templates
    templates = firestore_service.list_documents(
        collection="industry-templates",
        limit=100
    )
    
    print(f"Found {len(templates)} industry templates")
    print("-" * 80)
    
    updated_count = 0
    fields_to_remove = ["defaultSettings", "name", "recommendedSettings"]
    
    for template in templates:
        template_id = template.get("id", "")
        industry_name = template.get("industry", "")
        
        # Check which fields exist in this document
        existing_fields = [field for field in fields_to_remove if field in template]
        
        if existing_fields:
            print(f"\n🗑️  {industry_name} (ID: {template_id})")
            print(f"   Removing fields: {', '.join(existing_fields)}")
            
            # Build update data to remove the fields
            update_data = {}
            for field in existing_fields:
                update_data[field] = DELETE_FIELD
            
            # Update the document to remove the fields
            try:
                firestore_service._db.collection("industry-templates").document(template_id).update(update_data)
                success = True
            except Exception as e:
                print(f"   Error: {e}")
                success = False
            
            if success:
                print(f"   ✓ Fields removed successfully")
                updated_count += 1
            else:
                print(f"   ✗ Failed to remove fields")
        else:
            print(f"\n⏭️  {industry_name} (ID: {template_id})")
            print(f"   No target fields to remove")
    
    print("\n" + "=" * 80)
    print(f"✅ Completed: Updated {updated_count} of {len(templates)} templates")
    
    # Verify by checking one template
    if updated_count > 0:
        print("\n🔍 Verification - Checking first template:")
        first_template = firestore_service.get_document(
            collection="industry-templates",
            document_id=templates[0].get("id", "")
        )
        if first_template:
            print(f"   Template: {first_template.get('industry', 'Unknown')}")
            print(f"   Fields present: {', '.join(sorted(first_template.keys()))}")
            for field in fields_to_remove:
                if field in first_template:
                    print(f"   ⚠️  Warning: Field '{field}' still exists!")
                else:
                    print(f"   ✓ Field '{field}' removed")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())