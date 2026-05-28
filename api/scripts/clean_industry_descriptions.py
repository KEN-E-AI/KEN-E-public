#!/usr/bin/env python3
"""
Script to clean up industry template descriptions in Firestore.
Removes the "Optimized template for ...<industry name> - " prefix from descriptions.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService


def clean_description(description: str, industry_name: str) -> str:
    """
    Clean the description by removing the "Optimized template for ... - " prefix.

    Args:
        description: The current description
        industry_name: The industry name for this template

    Returns:
        The cleaned description
    """
    if not description:
        return description

    # Pattern 1: "Optimized template for <exact industry name> - "
    prefix1 = f"Optimized template for {industry_name} - "
    if description.startswith(prefix1):
        return description[len(prefix1) :]

    # Pattern 2: "Optimized template for" followed by any text until " - "
    prefix2 = "Optimized template for "
    if description.startswith(prefix2):
        # Find the " - " separator
        separator = " - "
        separator_index = description.find(separator)
        if separator_index != -1:
            # Return everything after the separator
            return description[separator_index + len(separator) :]

    # If no pattern matches, return original
    return description


def main():
    """Update all industry template descriptions to remove the prefix."""

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
        current_description = template.get("description", "")

        # Clean the description
        cleaned_description = clean_description(current_description, industry_name)

        # Check if description changed
        if cleaned_description != current_description:
            print(f"\n📝 {industry_name}")
            print(f"   Before: {current_description[:100]}...")
            print(f"   After:  {cleaned_description[:100]}...")

            # Update the template
            update_data = {"description": cleaned_description}

            success = firestore_service.update_document(
                collection="industry-templates",
                document_id=template_id,
                data=update_data,
            )

            if success:
                print("   ✓ Updated successfully")
                updated_count += 1
            else:
                print("   ✗ Failed to update")
        else:
            print(f"\n⏭️  {industry_name}")
            print("   Description already clean or doesn't match pattern")

    print("\n" + "=" * 80)
    print(f"✅ Completed: Updated {updated_count} of {len(templates)} templates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
