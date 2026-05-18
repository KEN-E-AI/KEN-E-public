#!/usr/bin/env python3
"""
Test script to directly test Neo4j account creation without authentication.
This helps isolate Neo4j connection issues.
"""

import asyncio
import logging
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.resolved')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_neo4j_account_creation():
    """Test creating an account directly in Neo4j."""
    
    # Import Neo4j service
    from src.kene_api.database import neo4j_service
    
    # Connect to Neo4j
    logger.info("Connecting to Neo4j...")
    try:
        await neo4j_service.connect()
        logger.info("✅ Successfully connected to Neo4j")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Neo4j: {e}")
        return
    
    # Test data
    account_id = f"acc_{uuid.uuid4().hex[:32]}"
    organization_id = "org_36e6691ccde243f1be1bdc9f61f59ec9"
    user_id = "test_user_123"
    
    logger.info(f"Creating test account: {account_id}")
    
    # Create account query
    create_query = """
    MERGE (org:Organization {organization_id: $organization_id})
    ON CREATE SET 
        org.created_at = datetime(),
        org.organization_name = 'Test Organization'
    
    CREATE (acc:Account {
        account_id: $account_id,
        account_name: $account_name,
        organization_id: $organization_id,
        industry: $industry,
        status: $status,
        websites: $websites,
        timezone: $timezone,
        created_at: datetime(),
        created_by: $created_by,
        updated_at: datetime(),
        updated_by: $created_by,
        data_region: $data_region,
        region: $region,
        marketing_channels: $marketing_channels,
        product_integrations: $product_integrations,
        estimated_annual_ad_budget: $estimated_annual_ad_budget
    })
    
    CREATE (acc)-[:BELONGS_TO]->(org)
    
    RETURN acc
    """
    
    parameters = {
        "account_id": account_id,
        "account_name": f"Test Account {datetime.now().strftime('%H:%M:%S')}",
        "organization_id": organization_id,
        "industry": "Technology",
        "status": "active",
        "websites": ["https://example.com"],
        "timezone": "America/New_York",
        "created_by": user_id,
        "data_region": "US",
        "region": ["North America"],
        "marketing_channels": ["social_media", "email"],
        "product_integrations": ["google_ads"],
        "estimated_annual_ad_budget": 100000
    }
    
    try:
        logger.info("Executing CREATE query...")
        result = await neo4j_service.execute_write_query(create_query, parameters)
        
        if result:
            logger.info(f"✅ Account created successfully: {result[0]['acc']['account_id']}")
        else:
            logger.error("❌ No result returned from CREATE query")
            
    except Exception as e:
        logger.error(f"❌ Failed to create account: {e}")
        import traceback
        traceback.print_exc()
    
    # Now try to fetch the account
    fetch_query = """
    MATCH (acc:Account {account_id: $account_id})
    MATCH (acc)-[:BELONGS_TO]->(org:Organization)
    RETURN acc, org
    """
    
    try:
        logger.info("Fetching created account...")
        result = await neo4j_service.execute_query(fetch_query, {"account_id": account_id})
        
        if result:
            logger.info(f"✅ Account fetched successfully: {result[0]['acc']['account_name']}")
        else:
            logger.error("❌ Account not found after creation")
            
    except Exception as e:
        logger.error(f"❌ Failed to fetch account: {e}")
    
    # List all accounts for the organization
    list_query = """
    MATCH (acc:Account)-[:BELONGS_TO]->(org:Organization {organization_id: $organization_id})
    RETURN acc
    ORDER BY acc.created_at DESC
    LIMIT 10
    """
    
    try:
        logger.info("Listing accounts for organization...")
        result = await neo4j_service.execute_query(list_query, {"organization_id": organization_id})
        
        if result:
            logger.info(f"✅ Found {len(result)} accounts in organization")
            for i, record in enumerate(result[:3]):
                logger.info(f"  - {record['acc']['account_name']} ({record['acc']['account_id']})")
        else:
            logger.info("No accounts found for organization")
            
    except Exception as e:
        logger.error(f"❌ Failed to list accounts: {e}")
    
    # Clean up - delete the test account
    delete_query = """
    MATCH (acc:Account {account_id: $account_id})
    DETACH DELETE acc
    """
    
    try:
        logger.info("Cleaning up test account...")
        await neo4j_service.execute_write_operation(delete_query, {"account_id": account_id})
        logger.info("✅ Test account deleted")
    except Exception as e:
        logger.error(f"❌ Failed to delete test account: {e}")
    
    # Close connection
    await neo4j_service.close()
    logger.info("Neo4j connection closed")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("NEO4J ACCOUNT CREATION TEST")
    logger.info("=" * 60)
    asyncio.run(test_neo4j_account_creation())
    logger.info("=" * 60)
    logger.info("TEST COMPLETED")
    logger.info("=" * 60)