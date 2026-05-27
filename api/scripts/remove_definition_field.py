#!/usr/bin/env python3
"""
Script to remove the definition field from all industry template documents in Firestore.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud.firestore import DELETE_FIELD
from src.kene_api.firestore import FirestoreService


def main():
    """Remove definition field from all industry templates."""

    # Initialize Firestore
    firestore_service = FirestoreService()

    if not firestore_service.health_check():
        print("Error: Could not connect to Firestore")
        return 1

    print("Connected to Firestore")

    # Get all industry templates
    templates = firestore_service.list_documents(
        collection="industry-templates", limit=100
    )

    print(f"Found {len(templates)} industry templates")
    print("-" * 80)

    updated_count = 0

    for template in templates:
        template_id = template.get("id", "")
        industry_name = template.get("industry", "")
        has_definition = "definition" in template

        if has_definition:
            print(f"\n🗑️  {industry_name}")
            print("   Removing definition field...")

            # Update the document to remove the definition field
            update_data = {"definition": DELETE_FIELD}

            # Use set with merge to remove the field
            try:
                firestore_service._db.collection("industry-templates").document(
                    template_id
                ).update(update_data)
                success = True
            except Exception as e:
                print(f"   Error: {e}")
                success = False

            if success:
                print("   ✓ Definition field removed")
                updated_count += 1
            else:
                print("   ✗ Failed to remove definition field")
        else:
            print(f"\n⏭️  {industry_name}")
            print("   No definition field to remove")

    print("\n" + "=" * 80)
    print(
        f"✅ Completed: Removed definition field from {updated_count} of {len(templates)} templates"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
