"""Neo4j database connection and query utilities."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

from .config import settings

logger = logging.getLogger(__name__)


class Neo4jService:
    """Neo4j database service for managing connections and queries."""

    def __init__(self):
        """Initialize the Neo4j service."""
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            # Verify connectivity
            await self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j database")
        except Neo4jError as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self) -> None:
        """Close the database connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    @asynccontextmanager
    async def get_session(self):
        """Get an async session for database operations."""
        if not self.driver:
            raise RuntimeError("Database driver not initialized. Call connect() first.")

        session = self.driver.session(database=settings.neo4j_database)
        try:
            yield session
        finally:
            await session.close()

    async def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of dictionaries representing query results
        """
        if parameters is None:
            parameters = {}

        try:
            async with self.get_session() as session:
                # Use session.execute_read for read queries
                async def _execute_query(tx):
                    result = await tx.run(query, parameters)
                    data = await result.data()
                    
                    # Debug logging for account queries
                    if "Account" in query and data:
                        logger.info(f"[DEBUG Neo4j] Query contains 'Account', checking data structure")
                        for i, record in enumerate(data[:1]):  # Just log first record
                            if 'acc' in record:
                                acc = record['acc']
                                logger.info(f"[DEBUG Neo4j] Account properties present: {list(acc.keys()) if isinstance(acc, dict) else 'not a dict'}")
                                if isinstance(acc, dict) and 'marketing_channels' in acc:
                                    mc = acc['marketing_channels']
                                    logger.info(f"[DEBUG Neo4j] marketing_channels value: {mc}, type: {type(mc)}")
                    
                    return data

                records = await session.execute_read(_execute_query)
                return records
        except Neo4jError as e:
            logger.error(f"Query execution failed: {e}")
            raise

    async def execute_write_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Execute a write query that returns data (CREATE/MERGE with RETURN).

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of dictionaries representing query results
        """
        if parameters is None:
            parameters = {}

        try:
            async with self.get_session() as session:
                # Use session.execute_write for write queries
                async def _execute_write_query(tx):
                    result = await tx.run(query, parameters)
                    return await result.data()

                return await session.execute_write(_execute_write_query)
        except Neo4jError as e:
            logger.error(f"Write query execution failed: {e}")
            raise

    async def execute_write_operation(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> dict[str, int]:
        """
        Execute a write operation that returns summary (DELETE/UPDATE without RETURN).

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Dictionary with operation summary counters
            (nodes_created, nodes_deleted, relationships_created, relationships_deleted, properties_set)
        """
        if parameters is None:
            parameters = {}

        try:
            async with self.get_session() as session:
                # Use session.execute_write for write operations
                async def _execute_write_operation(tx):
                    result = await tx.run(query, parameters)
                    summary = await result.consume()
                    return {
                        "nodes_created": summary.counters.nodes_created,
                        "nodes_deleted": summary.counters.nodes_deleted,
                        "relationships_created": summary.counters.relationships_created,
                        "relationships_deleted": summary.counters.relationships_deleted,
                        "properties_set": summary.counters.properties_set,
                    }

                return await session.execute_write(_execute_write_operation)
        except Neo4jError as e:
            logger.error(f"Write operation execution failed: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            if not self.driver:
                return False
            await self.driver.verify_connectivity()
            return True
        except Neo4jError:
            return False


# Global instance
neo4j_service = Neo4jService()


async def get_neo4j_service() -> Neo4jService:
    """Dependency injection function for FastAPI endpoints."""
    return neo4j_service
