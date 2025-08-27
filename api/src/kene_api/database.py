"""Neo4j database connection and query utilities."""

import asyncio
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
                connection_timeout=10.0,  # 10 second timeout
                max_connection_lifetime=300,  # 5 minutes (reduced from 1 hour to avoid stale connections)
                max_connection_pool_size=25,  # Reduced from 50 to avoid overwhelming the server
                connection_acquisition_timeout=60.0,  # 60 second timeout for getting connection from pool
                keep_alive=True,  # Enable keep-alive to detect defunct connections earlier
            )
            # Verify connectivity with timeout
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
            logger.warning("Database driver not initialized. Attempting to connect...")
            try:
                await self.connect()
            except Exception as e:
                raise RuntimeError(f"Failed to connect to database: {e}")

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

        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                async with self.get_session() as session:
                    # Use session.execute_write for write queries
                    async def _execute_write_query(tx):
                        result = await tx.run(query, parameters)
                        return await result.data()

                    result = await session.execute_write(_execute_write_query)
                    if attempt > 0:
                        logger.info(f"Neo4j write query succeeded on retry {attempt + 1}")
                    return result
            except Neo4jError as e:
                if attempt < max_retries - 1 and "defunct connection" in str(e).lower():
                    # This is expected occasionally with connection pools - we'll retry
                    logger.debug(f"Neo4j connection issue (attempt {attempt + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    # Try to reconnect if driver exists
                    if self.driver:
                        try:
                            await self.driver.verify_connectivity()
                        except:
                            pass  # Continue with retry
                else:
                    logger.error(f"Write query execution failed after {attempt + 1} attempts: {e}")
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

        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
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

                    result = await session.execute_write(_execute_write_operation)
                    if attempt > 0:
                        logger.info(f"Neo4j write operation succeeded on retry {attempt + 1}")
                    return result
            except Neo4jError as e:
                if attempt < max_retries - 1 and "defunct connection" in str(e).lower():
                    logger.debug(f"Neo4j connection issue (attempt {attempt + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    if self.driver:
                        try:
                            await self.driver.verify_connectivity()
                        except:
                            pass  # Continue with retry
                else:
                    logger.error(f"Write operation execution failed after {attempt + 1} attempts: {e}")
                    raise

    async def health_check(self) -> bool:
        """
        Check if the database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # If no driver exists, try to connect
            if not self.driver:
                logger.warning("Neo4j driver not initialized, attempting to connect...")
                try:
                    await self.connect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to Neo4j: {e}")
                    return False
            
            # Verify connectivity
            await self.driver.verify_connectivity()
            return True
        except Neo4jError as e:
            logger.error(f"Neo4j health check failed: {e}")
            # Try to reconnect once
            try:
                await self.connect()
                await self.driver.verify_connectivity()
                logger.info("Neo4j reconnected successfully")
                return True
            except:
                return False


# Global instance
neo4j_service = Neo4jService()


async def get_neo4j_service() -> Neo4jService:
    """Dependency injection function for FastAPI endpoints."""
    return neo4j_service
