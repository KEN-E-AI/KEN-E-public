#!/usr/bin/env python3
"""Script to populate industry keywords in Firestore for monitoring topics feature."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from google.cloud import firestore

# Load environment variables
load_dotenv()

# Comprehensive industry keywords mapping
INDUSTRY_KEYWORDS = {
    "Agriculture, Forestry, Fishing and Hunting": [
        "agriculture",
        "farming",
        "forestry",
        "fishing",
        "hunting",
        "crops",
        "livestock",
        "harvest",
        "agricultural",
        "farm",
        "ranching",
        "aquaculture",
        "timber",
        "logging",
        "nursery",
        "greenhouse",
        "organic farming",
        "sustainable agriculture",
    ],
    "Utilities": [
        "utilities",
        "electricity",
        "power generation",
        "natural gas",
        "water supply",
        "sewage",
        "waste management",
        "energy",
        "power grid",
        "renewable energy",
        "solar power",
        "wind power",
        "hydroelectric",
        "nuclear power",
        "utility services",
    ],
    "Construction": [
        "construction",
        "building",
        "contractor",
        "renovation",
        "infrastructure",
        "residential construction",
        "commercial construction",
        "civil engineering",
        "demolition",
        "excavation",
        "concrete",
        "steel construction",
        "green building",
        "construction management",
    ],
    "Manufacturing": [
        "manufacturing",
        "production",
        "factory",
        "assembly",
        "industrial",
        "fabrication",
        "supply chain",
        "lean manufacturing",
        "quality control",
        "automation",
        "robotics",
        "3d printing",
        "mass production",
        "custom manufacturing",
        "industrial design",
    ],
    "Wholesale Trade [B2B]": [
        "wholesale",
        "b2b",
        "distribution",
        "wholesale trade",
        "business to business",
        "bulk sales",
        "trade",
        "distributor",
        "supply chain",
        "merchant wholesaler",
        "wholesale distribution",
        "trade shows",
        "wholesale market",
        "b2b commerce",
    ],
    "Retail Trade": [
        "retail",
        "ecommerce",
        "shopping",
        "consumer",
        "merchandise",
        "store",
        "sales",
        "online retail",
        "brick and mortar",
        "customer experience",
        "point of sale",
        "inventory management",
        "retail technology",
        "omnichannel",
        "direct to consumer",
    ],
    "Transportation and Warehousing": [
        "transportation",
        "logistics",
        "shipping",
        "freight",
        "warehousing",
        "supply chain",
        "trucking",
        "rail transport",
        "air cargo",
        "maritime shipping",
        "last mile delivery",
        "fleet management",
        "cold chain",
        "distribution center",
    ],
    "Information": [
        "information",
        "media",
        "publishing",
        "broadcasting",
        "telecommunications",
        "data processing",
        "streaming",
        "digital media",
        "news media",
        "content creation",
        "information technology",
        "telecom",
        "5g",
        "broadband",
    ],
    "Finance and Insurance": [
        "finance",
        "banking",
        "insurance",
        "investment",
        "financial services",
        "fintech",
        "capital markets",
        "wealth management",
        "credit",
        "loans",
        "mortgage",
        "cryptocurrency",
        "blockchain",
        "insurtech",
        "risk management",
    ],
    "Real Estate and Rental and Leasing": [
        "real estate",
        "property",
        "rental",
        "leasing",
        "commercial real estate",
        "residential real estate",
        "property management",
        "real estate investment",
        "reit",
        "vacation rental",
        "equipment leasing",
        "proptech",
        "real estate development",
        "property technology",
    ],
    "Professional, Scientific, and Technical Services": [
        "consulting",
        "professional services",
        "technical services",
        "engineering",
        "research",
        "development",
        "r&d",
        "management consulting",
        "it consulting",
        "legal services",
        "accounting",
        "architecture",
        "scientific research",
        "technical consulting",
        "design services",
    ],
    "Management of Companies and Enterprises": [
        "management",
        "corporate",
        "headquarters",
        "holding company",
        "enterprise management",
        "corporate management",
        "business management",
        "executive management",
        "strategic planning",
        "corporate strategy",
        "mergers and acquisitions",
        "corporate governance",
        "portfolio management",
    ],
    "Administrative and Support and Waste Management and Remediation Services": [
        "administrative services",
        "support services",
        "waste management",
        "remediation",
        "staffing",
        "cleaning services",
        "security services",
        "call center",
        "business support",
        "facilities management",
        "document management",
        "payroll services",
        "temp agency",
        "environmental remediation",
        "recycling",
    ],
    "Educational Services": [
        "education",
        "schools",
        "university",
        "college",
        "training",
        "e-learning",
        "online education",
        "k-12",
        "higher education",
        "vocational training",
        "professional development",
        "edtech",
        "curriculum",
        "distance learning",
        "educational technology",
    ],
    "Health Care and Social Assistance": [
        "healthcare",
        "medical",
        "hospital",
        "patient care",
        "telemedicine",
        "health services",
        "clinical",
        "nursing",
        "mental health",
        "social services",
        "eldercare",
        "childcare",
        "health technology",
        "medical devices",
        "pharmaceuticals",
    ],
    "Arts, Entertainment, and Recreation": [
        "arts",
        "entertainment",
        "recreation",
        "sports",
        "gaming",
        "music",
        "theater",
        "film",
        "television",
        "streaming entertainment",
        "live events",
        "amusement parks",
        "fitness",
        "leisure",
        "cultural events",
        "entertainment technology",
    ],
    "Accommodation and Food Services": [
        "hospitality",
        "hotel",
        "restaurant",
        "food service",
        "accommodation",
        "lodging",
        "catering",
        "tourism",
        "travel",
        "quick service restaurant",
        "fine dining",
        "food delivery",
        "hospitality technology",
        "vacation",
        "bed and breakfast",
        "resort",
    ],
    "Other Services (except Public Administration)": [
        "services",
        "repair services",
        "maintenance",
        "personal services",
        "laundry",
        "dry cleaning",
        "automotive repair",
        "beauty services",
        "salon",
        "spa",
        "pet services",
        "funeral services",
        "religious organizations",
        "civic organizations",
        "trade associations",
    ],
    "Public Administration": [
        "government",
        "public administration",
        "federal government",
        "state government",
        "local government",
        "municipal",
        "public policy",
        "government services",
        "public sector",
        "regulatory",
        "legislation",
        "public safety",
        "emergency services",
        "government technology",
        "civic tech",
    ],
}


async def populate_industry_keywords():
    """Populate industry keywords in Firestore."""
    # Initialize Firestore client
    db = firestore.Client()

    print("Starting to populate industry keywords...")
    print(f"Total industries to process: {len(INDUSTRY_KEYWORDS)}")

    success_count = 0
    error_count = 0

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        try:
            # Create document ID by converting industry name
            doc_id = (
                industry.lower()
                .replace(" ", "_")
                .replace(",", "")
                .replace("(", "")
                .replace(")", "")
            )

            # Prepare document data
            doc_data = {
                "industry": industry,
                "keywords": keywords,
                "updated_by": "system",
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Set document in Firestore
            doc_ref = db.collection("industry_keywords").document(doc_id)
            doc_ref.set(doc_data)

            success_count += 1
            print(f"✓ Created keywords for: {industry} ({len(keywords)} keywords)")

        except Exception as e:
            error_count += 1
            print(f"✗ Error creating keywords for {industry}: {e!s}")

    print("\n" + "=" * 50)
    print("Population complete!")
    print(f"Successfully created: {success_count} industry keyword documents")
    print(f"Errors: {error_count}")

    # Verify by reading back one document
    if success_count > 0:
        print("\nVerifying by reading sample document...")
        try:
            sample_doc = (
                db.collection("industry_keywords").document("manufacturing").get()
            )
            if sample_doc.exists:
                data = sample_doc.to_dict()
                print(
                    f"✓ Sample verification successful: {data['industry']} has {len(data['keywords'])} keywords"
                )
            else:
                print("✗ Sample document not found")
        except Exception as e:
            print(f"✗ Verification error: {e!s}")


def main():
    """Main function to run the script."""
    print("Industry Keywords Population Script")
    print("==================================")

    # Check for required environment variables
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT_ID environment variable not set")
        print("Please set it in your .env file or environment")
        sys.exit(1)

    print(f"Using Google Cloud Project: {project_id}")

    # Check for credentials
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set")
        print("Make sure you have proper authentication configured")
    else:
        print(f"Using credentials from: {credentials_path}")

    print("\nThis script will create/update industry keywords in Firestore.")
    response = input("Do you want to continue? (yes/no): ")

    if response.lower() != "yes":
        print("Script cancelled.")
        sys.exit(0)

    # Run the async function
    asyncio.run(populate_industry_keywords())


if __name__ == "__main__":
    main()
