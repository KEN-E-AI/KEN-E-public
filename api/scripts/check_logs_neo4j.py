#!/usr/bin/env python3
"""Check activity logs directly in Neo4j."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

# Neo4j connection
uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")


def check_logs(account_id):
    """Check logs in Neo4j."""
    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        # Check account
        result = session.run(
            """
            MATCH (acc:Account {account_id: $account_id})
            RETURN acc.region as regions, acc.account_name as name
        """,
            account_id=account_id,
        )

        record = result.single()
        if not record:
            print(f"Account {account_id} not found!")
            return

        print(f"Account: {record['name']}")
        print(f"Regions: {record['regions']}")

        # Count all ActivityLogs for act_00
        result = session.run(
            """
            MATCH (al:ActivityLog)-[:LOGGED]->(a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
            RETURN count(al) as total_logs
        """,
            account_id=account_id,
        )

        total = result.single()["total_logs"]
        print(f"\nTotal ActivityLogs for act_00: {total}")

        # Show first 10 logs
        result = session.run(
            """
            MATCH (al:ActivityLog)-[:LOGGED]->(a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
            RETURN al.description as description, al.start_date as start_date
            ORDER BY al.description
            LIMIT 10
        """,
            account_id=account_id,
        )

        print("\nFirst 10 logs:")
        for record in result:
            print(f"  - {record['description']} ({record['start_date']})")

    driver.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python check_logs_neo4j.py <account_id>")
        sys.exit(1)

    check_logs(sys.argv[1])
