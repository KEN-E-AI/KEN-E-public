#!/usr/bin/env python3
"""Test Neo4j connection."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

print(f"Testing connection to: {uri}")
print(f"User: {user}")

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        result = session.run("RETURN 1 AS test")
        record = result.single()
        print(f"✓ Connection successful! Test query returned: {record['test']}")

        # Check if there are any nodes
        count_result = session.run("MATCH (n) RETURN count(n) AS count LIMIT 1")
        count = count_result.single()["count"]
        print(f"✓ Database has {count} nodes")

    driver.close()

except Exception as e:
    print(f"✗ Connection failed: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
