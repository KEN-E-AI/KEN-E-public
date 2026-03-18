# Subscription Plan Migration Guide

This guide explains how to migrate existing organizations from hardcoded subscription data to the new centralized subscription plans system.

## Overview

The subscription plan centralization feature moves subscription plan definitions from hardcoded values in the codebase to a centralized Firestore collection. This allows for easier management and updates of subscription plans without requiring code changes.

## Migration Strategy

### Phase 1: Initialize Subscription Plans (Completed)

1. **Create subscription plans in Firestore** ✅
   - Run `api/scripts/init_subscription_plans.py` in each environment
   - Creates 4 default plans: Free, Starter, Professional, Enterprise

2. **Update code to use centralized plans** ✅
   - Frontend fetches default plan when creating organizations
   - API provides endpoints for plan management

### Phase 2: Migrate Existing Organizations (To Do)

Existing organizations in Neo4j have subscription data stored directly on the organization node. This data needs to be mapped to the new subscription plan IDs.

#### Migration Script

Create and run the following migration script:

```python
"""Migrate existing organizations to use centralized subscription plans."""

import asyncio
from src.kene_api.neo4j import get_neo4j_service
from src.kene_api.firestore import get_firestore_service

async def migrate_organizations():
    neo4j_service = get_neo4j_service()
    firestore_service = get_firestore_service()
    
    # Get all subscription plans from Firestore
    plans = firestore_service.list_documents("subscription-plans")
    plan_map = {plan["plan_name"]: plan["plan_id"] for plan in plans}
    
    # Query all organizations from Neo4j
    query = """
    MATCH (o:Organization)
    RETURN o.organization_id as org_id, 
           o.plan as plan_name,
           o.subscription as subscription_data
    """
    
    organizations = await neo4j_service.execute_query(query)
    
    for org in organizations:
        # Map old plan name to new plan ID
        old_plan_name = org.get("plan_name", "Free Plan")
        new_plan_id = plan_map.get(old_plan_name, "free-plan")
        
        # Update organization with plan_id
        update_query = """
        MATCH (o:Organization {organization_id: $org_id})
        SET o.plan_id = $plan_id
        RETURN o
        """
        
        await neo4j_service.execute_query(
            update_query,
            parameters={
                "org_id": org["org_id"],
                "plan_id": new_plan_id
            }
        )
        
        print(f"Migrated {org['org_id']} from '{old_plan_name}' to plan_id '{new_plan_id}'")

if __name__ == "__main__":
    asyncio.run(migrate_organizations())
```

### Phase 3: Update Application Logic

1. **Update organization queries** to use `plan_id` instead of embedded subscription data
2. **Join with subscription plans** when displaying subscription information
3. **Remove hardcoded subscription data** from organization creation

### Phase 4: Data Cleanup (Optional)

After verifying the migration:

1. Remove the old `subscription` property from organization nodes
2. Keep only `plan_id` reference
3. Update any reports or analytics that relied on embedded subscription data

## Rollback Plan

If issues arise during migration:

1. **Keep original data intact** - Don't delete subscription data immediately
2. **Feature flag** - Add a flag to switch between old and new behavior
3. **Dual-write period** - Write both old format and new plan_id during transition

## Verification Steps

1. **Count organizations by plan**:
   ```cypher
   MATCH (o:Organization)
   RETURN o.plan_id, count(*) as count
   ORDER BY count DESC
   ```

2. **Find organizations without plan_id**:
   ```cypher
   MATCH (o:Organization)
   WHERE o.plan_id IS NULL
   RETURN o.organization_id, o.plan
   ```

3. **Verify plan features match**:
   - Compare organization's old subscription.features with new plan features
   - Ensure no loss of functionality

## Timeline

- **Week 1**: Run migration script in development environment
- **Week 2**: Run migration script in staging environment
- **Week 3**: Run migration script in production environment
- **Week 4**: Remove old subscription data fields

## Notes

- The migration is **idempotent** - can be run multiple times safely
- Organizations created after the feature launch already use plan_id
- No downtime required for migration
- Consider running during low-traffic periods for production

## Support

For questions or issues during migration:
1. Check logs in Cloud Logging
2. Review organization data in Neo4j Browser
3. Verify subscription plans in Firestore Console