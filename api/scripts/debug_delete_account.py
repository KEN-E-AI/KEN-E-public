#!/usr/bin/env python3
"""Debug version of account deletion to trace the issue."""

import asyncio
import os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j connection
uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

async def debug_delete_account(account_id: str):
    """Debug the account deletion process step by step."""
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    try:
        async with driver.session() as session:
            print(f"🔍 Debugging deletion of account: {account_id}")
            
            # Step 1: Check if account exists
            print("\n1. Checking if account exists...")
            check_query = "MATCH (acc:Account {account_id: $account_id}) RETURN count(acc) as count"
            result = await session.run(check_query, account_id=account_id)
            data = await result.single()
            if data["count"] == 0:
                print("❌ Account not found!")
                return
            print("✓ Account exists")
            
            # Step 2: Count ActivityLogs
            print("\n2. Counting ActivityLogs...")
            count_logs_query = """
            MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)-[:LOGGED]->(log:ActivityLog)
            RETURN count(log) as count
            """
            result = await session.run(count_logs_query, account_id=account_id)
            data = await result.single()
            print(f"  Found {data['count']} ActivityLogs")
            
            # Step 3: Try to delete ActivityLogs
            print("\n3. Attempting to delete ActivityLogs...")
            delete_logs_query = """
            MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)-[:LOGGED]->(log:ActivityLog)
            DETACH DELETE log
            """
            
            async def write_transaction(tx):
                result = await tx.run(delete_logs_query, account_id=account_id)
                summary = await result.consume()
                return summary
            
            summary = await session.execute_write(write_transaction)
            print(f"  Deleted {summary.counters.nodes_deleted} nodes")
            print(f"  Deleted {summary.counters.relationships_deleted} relationships")
            
            # Step 4: Count entities
            print("\n4. Counting all entities...")
            count_query = """
            MATCH (acc:Account {account_id: $account_id})
            OPTIONAL MATCH (acc)<-[:BELONGS_TO]-(entity)
            WITH acc, collect(entity) as entities
            RETURN 
                size([e IN entities WHERE e:Activity]) as activities_count,
                size([e IN entities WHERE e:Metric]) as metrics_count,
                size([e IN entities WHERE e:Insight]) as insights_count,
                size([e IN entities WHERE e:Intuition]) as intuitions_count,
                size([e IN entities WHERE e:Item]) as items_count,
                size([e IN entities WHERE e:Dataset]) as datasets_count,
                size(entities) as total_entities
            """
            result = await session.run(count_query, account_id=account_id)
            counts = await result.single()
            print(f"  Activities: {counts['activities_count']}")
            print(f"  Metrics: {counts['metrics_count']}")
            print(f"  Insights: {counts['insights_count']}")
            print(f"  Intuitions: {counts['intuitions_count']}")
            print(f"  Items: {counts['items_count']}")
            print(f"  Datasets: {counts['datasets_count']}")
            print(f"  Total: {counts['total_entities']}")
            
            # Step 5: Delete everything
            print("\n5. Attempting to delete account and all entities...")
            delete_all_query = """
            MATCH (acc:Account {account_id: $account_id})
            OPTIONAL MATCH (acc)<-[:BELONGS_TO]-(entity)
            DETACH DELETE entity, acc
            """
            
            async def delete_all_transaction(tx):
                result = await tx.run(delete_all_query, account_id=account_id)
                summary = await result.consume()
                return summary
            
            summary = await session.execute_write(delete_all_transaction)
            print(f"  Deleted {summary.counters.nodes_deleted} nodes")
            print(f"  Deleted {summary.counters.relationships_deleted} relationships")
            
            print("\n✅ Debug complete!")
            
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await driver.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python debug_delete_account.py <account_id>")
        sys.exit(1)
    
    asyncio.run(debug_delete_account(sys.argv[1]))