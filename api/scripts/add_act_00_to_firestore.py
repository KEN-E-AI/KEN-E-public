#!/usr/bin/env python3
"""
Script to add act_00 activity to Firestore initial-activities collection.
This activity is required for holiday ActivityLog creation.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.firestore import get_firestore_service


def main():
    """Add act_00 to initial-activities collection."""
    firestore = get_firestore_service()
    
    # Check if firestore is initialized
    if not firestore.health_check():
        print("Error: Firestore service is not available")
        return 1
    
    # Define the act_00 activity
    act_00_data = {
        "activity_id": "act_00",
        "activity_name": "Holidays",
        "activity_description": "Public holidays and observances",
        "expected_impact": "Low",
        "internal": True,
        "known_activity": True,
    }
    
    try:
        # Check if act_00 already exists
        existing_docs = firestore.list_documents("initial-activities")
        for doc in existing_docs:
            if doc.get("activity_id") == "act_00":
                print("act_00 already exists in initial-activities collection")
                return 0
        
        # Create the document
        doc_id = firestore.create_document("initial-activities", "act_00", act_00_data)
        print(f"Successfully created act_00 in initial-activities collection with ID: {doc_id}")
        return 0
        
    except Exception as e:
        print(f"Error creating act_00: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())