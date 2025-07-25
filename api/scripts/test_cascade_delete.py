#!/usr/bin/env python3
"""Test account cascade deletion functionality."""

import sys
import os
import requests
import json
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API endpoint
base_url = "http://localhost:8000/api/v1"

# Neo4j connection
uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(uri, auth=(user, password))

def check_entities_before_deletion(account_id):
    """Check all entities related to the account before deletion."""
    print(f"\n🔍 Checking entities for account {account_id}...")
    
    with driver.session() as session:
        # Check activities
        activities_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(a:Activity)
        RETURN count(a) as count
        """
        activities_count = session.run(activities_query, account_id=account_id).single()["count"]
        print(f"  - Activities: {activities_count}")
        
        # Check activity logs
        logs_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(a:Activity)-[:LOGGED]->(al:ActivityLog)
        RETURN count(al) as count
        """
        logs_count = session.run(logs_query, account_id=account_id).single()["count"]
        print(f"  - Activity Logs: {logs_count}")
        
        # Check metrics
        metrics_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(m:Metric)
        RETURN count(m) as count
        """
        metrics_count = session.run(metrics_query, account_id=account_id).single()["count"]
        print(f"  - Metrics: {metrics_count}")
        
        # Check insights
        insights_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(i:Insight)
        RETURN count(i) as count
        """
        insights_count = session.run(insights_query, account_id=account_id).single()["count"]
        print(f"  - Insights: {insights_count}")
        
        # Check intuitions
        intuitions_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(i:Intuition)
        RETURN count(i) as count
        """
        intuitions_count = session.run(intuitions_query, account_id=account_id).single()["count"]
        print(f"  - Intuitions: {intuitions_count}")
        
        # Check items
        items_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(i:Item)
        RETURN count(i) as count
        """
        items_count = session.run(items_query, account_id=account_id).single()["count"]
        print(f"  - Items: {items_count}")
        
        # Total entities
        total_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(e)
        RETURN count(e) as count
        """
        total_count = session.run(total_query, account_id=account_id).single()["count"]
        print(f"  - Total entities with BELONGS_TO relationship: {total_count}")
        
        return {
            "activities": activities_count,
            "activity_logs": logs_count,
            "metrics": metrics_count,
            "insights": insights_count,
            "intuitions": intuitions_count,
            "items": items_count,
            "total": total_count
        }

def check_entities_after_deletion(account_id):
    """Check that all entities were deleted."""
    print(f"\n🔍 Checking entities after deletion...")
    
    with driver.session() as session:
        # Check if account exists
        account_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN count(acc) as count
        """
        account_exists = session.run(account_query, account_id=account_id).single()["count"] > 0
        
        if account_exists:
            print(f"  ❌ Account still exists!")
            return False
        
        print(f"  ✓ Account deleted")
        
        # Check for orphaned entities (should be none)
        orphaned_query = """
        MATCH (e)
        WHERE NOT (e)<-[:BELONGS_TO]-(:Account)
        AND (e:Activity OR e:ActivityLog OR e:Metric OR e:Insight OR e:Intuition OR e:Item)
        RETURN count(e) as count
        """
        orphaned_count = session.run(orphaned_query).single()["count"]
        
        if orphaned_count > 0:
            print(f"  ❌ Found {orphaned_count} orphaned entities!")
            return False
        
        print(f"  ✓ No orphaned entities found")
        return True

def delete_account(account_id):
    """Call the delete account API endpoint."""
    print(f"\n🗑️  Deleting account {account_id}...")
    
    try:
        response = requests.delete(f"{base_url}/accounts/{account_id}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Account deleted successfully!")
            print(f"  Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Failed to delete account: {response.status_code}")
            print(f"  Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_cascade_delete.py <account_id>")
        print("Example: python test_cascade_delete.py acc_56a8acfa9ed24858b7a93a283713b6b7")
        sys.exit(1)
    
    account_id = sys.argv[1]
    
    print(f"🧪 Testing cascade delete for account: {account_id}")
    
    # Check entities before deletion
    before_counts = check_entities_before_deletion(account_id)
    
    if before_counts["total"] == 0:
        print("\n⚠️  No entities found for this account. Nothing to test.")
        sys.exit(0)
    
    # Delete the account
    if delete_account(account_id):
        # Check entities after deletion
        if check_entities_after_deletion(account_id):
            print("\n✅ Cascade delete test passed!")
        else:
            print("\n❌ Cascade delete test failed!")
    
    driver.close()