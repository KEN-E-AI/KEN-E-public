#!/usr/bin/env python3
"""Check if ActivityLog nodes were created for an account."""

import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()


def check_activity_logs(account_id):
    """Check ActivityLog nodes for a given account."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # Check if act_00 exists for the account
        act_00_query = """
        MATCH (a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        RETURN a.activity_id as activity_id, a.activity_name as name
        """
        act_00_result = session.run(act_00_query, account_id=account_id)
        act_00_record = act_00_result.single()

        if act_00_record:
            print(f"✓ Found act_00 activity: {act_00_record['name']}")
        else:
            print("✗ No act_00 activity found for this account")
            return

        # Check ActivityLog nodes
        logs_query = """
        MATCH (al:ActivityLog)-[:LOGGED]->(a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        RETURN al.activity_log_id as id, al.description as description, al.start_date as start_date, al.end_date as end_date
        ORDER BY al.start_date
        """

        logs_result = session.run(logs_query, account_id=account_id)
        logs = list(logs_result)

        if logs:
            print(f"\n✓ Found {len(logs)} ActivityLog nodes for act_00:")
            for log in logs:
                print(
                    f"  - {log['description']} ({log['start_date']} to {log['end_date']})"
                )
        else:
            print("\n✗ No ActivityLog nodes found for act_00")

    driver.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_activity_logs.py <account_id>")
        print(
            "Example: python check_activity_logs.py acc_56a8acfa9ed24858b7a93a283713b6b7"
        )
        sys.exit(1)

    check_activity_logs(sys.argv[1])
