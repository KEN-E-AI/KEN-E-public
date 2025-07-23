#!/usr/bin/env python3
"""Initialize subscription plans in Firestore."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import get_firestore_service

SUBSCRIPTION_PLANS_COLLECTION = "subscription-plans"


async def create_initial_plans():
    """Create initial subscription plans in Firestore."""
    firestore_service = get_firestore_service()
    
    if not firestore_service.health_check():
        print("Error: Firestore service is not available")
        return False
    
    # Define initial plans
    plans = [
        {
            "plan_id": "free-plan",
            "plan_name": "Free Plan",
            "plan_description": "Basic features for getting started",
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": {
                "max_users": 1,
                "max_reports": 10,
                "features": ["Basic Reports", "1 User", "Email Support"],
            },
            "is_default": True,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "plan_id": "starter-plan",
            "plan_name": "Starter Plan",
            "plan_description": "Perfect for small teams",
            "price": 49.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": {
                "max_users": 5,
                "max_reports": 50,
                "features": [
                    "Advanced Reports",
                    "Up to 5 Users",
                    "Priority Email Support",
                    "API Access",
                ],
            },
            "is_default": False,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "plan_id": "professional-plan",
            "plan_name": "Professional Plan",
            "plan_description": "For growing businesses",
            "price": 149.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": {
                "max_users": 20,
                "max_reports": 200,
                "features": [
                    "Premium Reports",
                    "Up to 20 Users",
                    "24/7 Phone Support",
                    "Advanced API Access",
                    "Custom Integrations",
                    "Data Export",
                ],
            },
            "is_default": False,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "plan_id": "enterprise-plan",
            "plan_name": "Enterprise Plan",
            "plan_description": "For large organizations",
            "price": 499.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "features": {
                "max_users": 100,
                "max_reports": 1000,
                "features": [
                    "Enterprise Reports",
                    "Unlimited Users",
                    "Dedicated Account Manager",
                    "Custom SLA",
                    "Advanced Security",
                    "White-label Options",
                    "Priority Development",
                ],
            },
            "is_default": False,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    
    # Create plans in Firestore
    created_count = 0
    for plan in plans:
        try:
            # Check if plan already exists
            existing_plan = firestore_service.get_document(
                collection=SUBSCRIPTION_PLANS_COLLECTION,
                document_id=plan["plan_id"],
            )
            
            if existing_plan:
                print(f"Plan '{plan['plan_name']}' already exists, skipping...")
                continue
            
            # Create the plan
            firestore_service.create_document(
                collection=SUBSCRIPTION_PLANS_COLLECTION,
                document_id=plan["plan_id"],
                data=plan,
            )
            print(f"Created plan: {plan['plan_name']}")
            created_count += 1
            
        except Exception as e:
            print(f"Error creating plan '{plan['plan_name']}': {str(e)}")
            return False
    
    print(f"\nSuccessfully created {created_count} subscription plans")
    return True


async def main():
    """Main function."""
    print("Initializing subscription plans in Firestore...")
    success = await create_initial_plans()
    
    if success:
        print("\nSubscription plans initialization completed successfully!")
        sys.exit(0)
    else:
        print("\nSubscription plans initialization failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())