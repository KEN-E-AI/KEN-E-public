#!/usr/bin/env python3
"""
Migration script to add industry definitions to Firestore templates.
This copies the definitions from the frontend organizationTypes.ts to Firestore.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

# Industry definitions from frontend/src/data/organizationTypes.ts
INDUSTRY_DEFINITIONS = {
    "Agriculture, Forestry, Fishing and Hunting": 
        "Growing crops, raising livestock, logging, and harvesting wild resources (fish, game, sap, etc.).",
    
    "Utilities": 
        "Providing electric power, natural gas, steam supply, water supply, and sewage removal services.",
    
    "Construction": 
        "Building homes, offices, infrastructure (bridges, roads, utility systems), and specialized trade work.",
    
    "Manufacturing": 
        "Transforming raw materials into new products through mechanical, physical, or chemical processes.",
    
    "Wholesale Trade [B2B]": 
        "Buying and selling goods in bulk—typically to retailers, other merchants, or institutional users.",
    
    "Retail Trade [B2C]": 
        "Selling goods directly to consumers through stores, online, or other direct channels.",
    
    "Transportation and Warehousing": 
        "Moving people or goods by road, rail, air, or water, plus storage and logistics services.",
    
    "Finance and Insurance": 
        "Facilitating financial transactions: banking, investment, securities, insurance carriers, and related services.",
    
    "Real Estate and Rental and Leasing": 
        "Selling, renting, and managing real property (land and buildings) and leasing machinery, equipment, and vehicles.",
    
    "Professional, Scientific, and Technical Services [B2B]": 
        "Specialized services provided to businesses. Services require high intellectual effort and training: legal, accounting, engineering, design, consulting, R&D, and advertising.",
    
    "Professional, Scientific, and Technical Services [B2C]": 
        "Specialized services provided to consumers. Services require high intellectual effort and training: legal, accounting, engineering, design, consulting, R&D, and advertising.",
    
    "Educational Services": 
        "Providing instruction and training at the high school level or below: schools or tutoring centers.",
    
    "Higher Educational Services": 
        "Providing instruction and training at the postsecondary level: colleges, universities, and professional schools.",
    
    "Health Care and Social Assistance": 
        "Providing medical care, social services, and assistance for individuals with healthcare and welfare needs.",
    
    "Enterprise Software and SaaS [B2B]": 
        "Software solutions designed for businesses and organizations, delivered via cloud-based subscription models.",
    
    "Arts, Entertainment, and Recreation": 
        "Providing cultural, entertainment, or recreational experiences for audiences and participants.",
    
    "Accommodation and Food Services": 
        "Providing lodging, meal preparation, snacks, and beverages for immediate consumption.",
    
    "Other Services (except Public Administration)": 
        "Personal services, repair services, religious organizations, advocacy groups, and other services not elsewhere classified.",
    
    "Public Administration": 
        "Government agencies administering public programs, enforcing regulations, and providing public services.",
    
    "Administrative and Support and Waste Management and Remediation Services": 
        "Support activities for other organizations, plus waste collection and disposal services.",
    
    "Information": 
        "Producing and distributing information and cultural products, plus data processing and telecommunications.",
    
    "Management of Companies and Enterprises": 
        "Managing companies and enterprises, including holding companies and corporate headquarters.",
}


def main():
    """Update industry templates with definitions."""
    
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
    
    updated_count = 0
    
    for template in templates:
        industry_name = template.get("industry", "")
        template_id = template.get("id", "")
        
        if industry_name in INDUSTRY_DEFINITIONS:
            definition = INDUSTRY_DEFINITIONS[industry_name]
            
            # Update the template with the definition
            update_data = {
                "definition": definition
            }
            
            success = firestore_service.update_document(
                collection="industry-templates",
                document_id=template_id,
                data=update_data
            )
            
            if success:
                print(f"✓ Updated {industry_name} with definition")
                updated_count += 1
            else:
                print(f"✗ Failed to update {industry_name}")
        else:
            print(f"⚠ No definition found for {industry_name}")
    
    print(f"\nCompleted: Updated {updated_count} of {len(templates)} templates")
    return 0


if __name__ == "__main__":
    sys.exit(main())