#!/usr/bin/env python3
"""Debug the sync functionality directly without going through the API."""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up environment
os.environ.setdefault("NEO4J_URI", os.getenv("NEO4J_URI", ""))
os.environ.setdefault("NEO4J_USER", os.getenv("NEO4J_USER", ""))
os.environ.setdefault("NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", ""))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT_ID", ""))


async def debug_sync(account_id: str):
    """Debug what would happen during sync."""
    import sys
    import os
    # Add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.kene_api.database import Neo4jService
    from src.kene_api.bigquery import BigQueryService
    
    db = Neo4jService()
    bigquery = BigQueryService()
    
    try:
        # Connect to database
        await db.connect()
        # Get account info
        print(f"\n=== Checking account {account_id} ===")
        account_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc.region as regions, acc.account_name as name
        """
        account_result = await db.execute_query(account_query, {"account_id": account_id})
        
        if not account_result:
            print(f"Account {account_id} not found!")
            return
            
        regions = account_result[0].get("regions", [])
        name = account_result[0].get("name", "Unknown")
        print(f"Account Name: {name}")
        print(f"Regions: {regions}")
        
        # Check if act_00 exists
        activity_query = """
        MATCH (a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        RETURN a
        """
        activity_result = await db.execute_query(activity_query, {"account_id": account_id})
        if not activity_result:
            print("WARNING: act_00 activity not found for this account!")
            return
        
        # Get existing activity logs
        print(f"\n=== Existing ActivityLogs in Neo4j ===")
        existing_logs_query = """
        MATCH (al:ActivityLog)-[:LOGGED]->(a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        OPTIONAL MATCH (al)-[r:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(m:Metric)
        RETURN al.activity_log_id as log_id,
               al.description as description,
               al.start_date as start_date,
               al.end_date as end_date,
               count(m) > 0 as has_metric_relationship
        ORDER BY al.description
        """
        existing_logs = await db.execute_query(existing_logs_query, {"account_id": account_id})
        
        print(f"Found {len(existing_logs)} existing logs:")
        existing_map = {}
        protected_logs = set()
        
        for log in existing_logs:
            key = (log["description"], log["start_date"], log["end_date"])
            existing_map[key] = log["log_id"]
            protected = "PROTECTED" if log["has_metric_relationship"] else ""
            print(f"  - {log['description']} ({log['start_date']}) {protected}")
            if log["has_metric_relationship"]:
                protected_logs.add(log["log_id"])
        
        # Query BigQuery
        print(f"\n=== Holidays from BigQuery ===")
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            print("ERROR: GOOGLE_CLOUD_PROJECT_ID not set!")
            return
            
        holidays = bigquery.query_holiday_activities(project_id, regions)
        print(f"Found {len(holidays)} holidays for regions {regions}:")
        
        bigquery_set = set()
        for holiday in holidays:
            key = (holiday["description"], holiday["start_date"], holiday["end_date"])
            bigquery_set.add(key)
            print(f"  - {holiday['description']} ({holiday['start_date']})")
        
        # Analyze differences
        print(f"\n=== Analysis ===")
        
        # Find logs to delete
        to_delete = []
        protected_from_deletion = []
        for key, log_id in existing_map.items():
            if key not in bigquery_set:
                if log_id in protected_logs:
                    protected_from_deletion.append(key)
                else:
                    to_delete.append((key, log_id))
        
        # Find logs to create
        to_create = []
        for key in bigquery_set:
            if key not in existing_map:
                to_create.append(key)
        
        print(f"\nLogs to DELETE ({len(to_delete)}):")
        for key, log_id in to_delete:
            print(f"  - {key[0]} ({key[1]}) [ID: {log_id}]")
        
        print(f"\nLogs PROTECTED from deletion ({len(protected_from_deletion)}):")
        for key in protected_from_deletion:
            print(f"  - {key[0]} ({key[1]})")
        
        print(f"\nLogs to CREATE ({len(to_create)}):")
        for key in to_create:
            print(f"  - {key[0]} ({key[1]})")
        
        # Show what the sync endpoint would report
        print(f"\n=== Sync Summary ===")
        print(f"Total holidays in BigQuery: {len(holidays)}")
        print(f"Existing logs before sync: {len(existing_logs)}")
        print(f"New logs to create: {len(to_create)}")
        print(f"Logs to delete: {len(to_delete)}")
        print(f"Logs protected from deletion: {len(protected_from_deletion)}")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/debug_sync_directly.py <account_id>")
        sys.exit(1)
    
    account_id = sys.argv[1]
    asyncio.run(debug_sync(account_id))