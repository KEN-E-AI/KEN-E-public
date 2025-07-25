#!/usr/bin/env python3
"""Test script to debug the sync holiday activity logs endpoint."""

import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.kene_api.bigquery import BigQueryService
from src.kene_api.database import Neo4jService

# Set up logging to see all logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def test_sync():
    """Test the sync logic directly."""
    # Initialize services
    neo4j = Neo4jService()
    bigquery = BigQueryService()
    
    account_id = input("Enter account ID to test: ")
    
    try:
        # Get account and regions
        account_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc.region as regions
        """
        account_result = await neo4j.execute_query(
            account_query, {"account_id": account_id}
        )
        
        if not account_result:
            print(f"Account {account_id} not found")
            return
            
        regions = account_result[0].get("regions", [])
        print(f"Account regions: {regions}")
        
        # Get existing activity logs
        existing_logs_query = """
        MATCH (al:ActivityLog)-[:LOGGED]->(a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        OPTIONAL MATCH (al)-[r:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(m:Metric)
        RETURN al.activity_log_id as log_id,
               al.description as description,
               al.start_date as start_date,
               al.end_date as end_date,
               count(m) > 0 as has_metric_relationship
        """
        existing_logs = await neo4j.execute_query(
            existing_logs_query, {"account_id": account_id}
        )
        
        print(f"\nExisting ActivityLogs in Neo4j: {len(existing_logs)}")
        for log in existing_logs:
            print(f"  - {log['description']} ({log['start_date']}) - Protected: {log['has_metric_relationship']}")
        
        # Query BigQuery
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            print("GOOGLE_CLOUD_PROJECT_ID not set")
            return
            
        holidays = bigquery.query_holiday_activities(project_id, regions)
        print(f"\nHolidays from BigQuery: {len(holidays)}")
        for holiday in holidays:
            print(f"  - {holiday['description']} ({holiday['start_date']})")
        
        # Show what would be deleted
        existing_keys = {
            (log["description"], log["start_date"], log["end_date"]): log["log_id"]
            for log in existing_logs
        }
        bigquery_keys = {
            (h["description"], h["start_date"], h["end_date"])
            for h in holidays
        }
        
        to_delete = []
        protected = []
        for key, log_id in existing_keys.items():
            if key not in bigquery_keys:
                log = next(l for l in existing_logs if l["log_id"] == log_id)
                if log["has_metric_relationship"]:
                    protected.append(key)
                else:
                    to_delete.append(key)
        
        print(f"\nWould delete {len(to_delete)} logs:")
        for key in to_delete:
            print(f"  - {key[0]} ({key[1]})")
            
        print(f"\nWould protect {len(protected)} logs:")
        for key in protected:
            print(f"  - {key[0]} ({key[1]})")
            
    finally:
        await neo4j.close()


if __name__ == "__main__":
    asyncio.run(test_sync())