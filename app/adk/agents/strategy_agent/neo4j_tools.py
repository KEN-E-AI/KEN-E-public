"""
Neo4j connection utilities for strategy knowledge graph.
Handles connection management, transactions, and error handling.
"""

import logging
import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

logger = logging.getLogger(__name__)


def _get_secret(secret_name: str) -> str | None:
    """Load secret using universal secret resolution.

    Args:
        secret_name: Environment variable name to resolve

    Returns:
        The secret value or None if not found
    """
    try:
        # Import here to avoid deployment issues if API module not available
        import sys
        from pathlib import Path
        api_path = Path(__file__).parent.parent.parent.parent.parent / "api" / "src"
        if str(api_path) not in sys.path:
            sys.path.insert(0, str(api_path))

        from kene_api.utils.secrets import get_env_or_secret

        return get_env_or_secret(secret_name)
    except ImportError:
        logger.warning(f"Could not import secrets utility for {secret_name}")
        return None
    except Exception as e:
        logger.warning(f"Could not load secret {secret_name}: {e}")
        return None


class Neo4jConnection:
    """Manages Neo4j database connections with retry logic and connection pooling."""

    def __init__(self, uri: str = None, username: str = None, password: str = None):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (defaults to env variable)
            username: Neo4j username (defaults to env variable)
            password: Neo4j password (defaults to env variable)
        """
        self.uri = uri or os.getenv("NEO4J_URI") or _get_secret("NEO4J_URI")
        self.username = (
            username
            or os.getenv("NEO4J_USERNAME")
            or os.getenv("NEO4J_USER")
            or _get_secret("NEO4J_USERNAME")
        )
        self.password = (
            password or os.getenv("NEO4J_PASSWORD") or _get_secret("NEO4J_PASSWORD")
        )

        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Neo4j credentials not provided. Set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD environment variables or add to Secret Manager"
            )

        self.driver = None
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    @contextmanager
    def session(self, database: str = None):
        """
        Create a Neo4j session with automatic cleanup.

        Args:
            database: Database name (defaults to default database)

        Yields:
            Neo4j session object
        """
        session = None
        try:
            session = self.driver.session(database=database)
            yield session
        finally:
            if session:
                session.close()

    def execute_query(
        self, query: str, parameters: dict = None, database: str = None
    ) -> list[dict]:
        """
        Execute a Cypher query with retry logic.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name

        Returns:
            List of result records as dictionaries
        """
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                with self.session(database) as session:
                    result = session.run(query, parameters or {})
                    return [record.data() for record in result]
            except (ServiceUnavailable, SessionExpired) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Query failed (attempt {attempt + 1}), retrying: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Query failed after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise

    def execute_write_transaction(self, transaction_func, **kwargs):
        """
        Execute a write transaction with automatic retry.

        Args:
            transaction_func: Function that takes a transaction object
            **kwargs: Additional arguments for transaction function

        Returns:
            Transaction result
        """
        with self.session() as session:
            return session.execute_write(transaction_func, **kwargs)

    def execute_read_transaction(self, transaction_func, **kwargs):
        """
        Execute a read transaction with automatic retry.

        Args:
            transaction_func: Function that takes a transaction object
            **kwargs: Additional arguments for transaction function

        Returns:
            Transaction result
        """
        with self.session() as session:
            return session.execute_read(transaction_func, **kwargs)


class Neo4jOperations:
    """High-level Neo4j operations for strategy management."""

    def __init__(self, connection: Neo4jConnection = None):
        """
        Initialize with a Neo4j connection.

        Args:
            connection: Existing Neo4jConnection instance (creates new if None)
        """
        self.connection = connection or Neo4jConnection()

    def create_indexes(self):
        """Create necessary indexes for optimal performance."""
        indexes = [
            # Vector index for semantic search
            """
            CREATE VECTOR INDEX strategy_search IF NOT EXISTS
            FOR (n:Strategy) ON (n.embedding)
            OPTIONS { indexConfig: {
              `vector.dimensions`: 768,
              `vector.similarity_function`: 'cosine'
            }}
            """,
            # Regular indexes for lookups
            "CREATE INDEX account_name IF NOT EXISTS FOR (n:Account) ON (n.account_name)",
            "CREATE INDEX account_id IF NOT EXISTS FOR (n:Account) ON (n.account_id)",
            "CREATE INDEX strategy_modified IF NOT EXISTS FOR (n:Strategy) ON (n.last_modified)",
        ]

        for index_query in indexes:
            try:
                self.connection.execute_query(index_query)
                logger.info(f"Index created or verified: {index_query[:50]}...")
            except Exception as e:
                logger.warning(f"Index creation warning (may already exist): {e}")

    def merge_account(self, account_data: dict) -> dict:
        """
        Create or update an Account node.

        IMPORTANT: Protects user-provided data from being overwritten.
        - ON CREATE: Sets all fields (new account)
        - ON MATCH: Only updates company_name and company_overview (agent-derived fields)
        - NEVER overwrites: account_name, websites, industry, regions, budget

        Args:
            account_data: Dictionary with account information

        Returns:
            Created/updated account data
        """
        # Build dynamic SET clauses based on what parameters are provided
        # This allows both full account creation AND partial updates from graph builders

        # ON CREATE: Only set fields that are provided in account_data
        create_fields = []
        if "account_name" in account_data:
            create_fields.append("acc.account_name = $account_name")
        if "company_name" in account_data:
            create_fields.append("acc.company_name = $company_name")
        elif "account_name" in account_data:
            create_fields.append("acc.company_name = $account_name")  # Fallback
        if "company_overview" in account_data:
            create_fields.append("acc.company_overview = $company_overview")
        if "industry" in account_data:
            create_fields.append("acc.industry = $industry")
        if "websites" in account_data:
            create_fields.append("acc.websites = $websites")
        if "customer_regions" in account_data:
            create_fields.append("acc.customer_regions = $customer_regions")
        if "data_region" in account_data:
            create_fields.append("acc.data_region = $data_region")
        if "organization_id" in account_data:
            create_fields.append("acc.organization_id = $organization_id")
        if "status" in account_data:
            create_fields.append("acc.status = $status")
        if "timezone" in account_data:
            create_fields.append("acc.timezone = $timezone")

        create_fields.append("acc.created_time = datetime()")
        create_fields.append("acc.created_by = 'System'")

        # ON MATCH: Only update agent-derived fields if provided
        match_fields = []
        if "company_name" in account_data:
            match_fields.append("acc.company_name = $company_name")
        if "company_overview" in account_data:
            match_fields.append("acc.company_overview = $company_overview")
        match_fields.append("acc.last_modified = datetime()")
        match_fields.append("acc.last_modified_by = 'System'")

        query = f"""
        MERGE (acc:Account {{account_id: $account_id}})
        ON CREATE SET
            {", ".join(create_fields)}
        ON MATCH SET
            {", ".join(match_fields)}
        RETURN acc
        """

        result = self.connection.execute_query(query, account_data)
        return result[0]["acc"] if result else None

    def create_strategy_node(
        self, node_type: str, node_data: dict, account_id: str
    ) -> dict:
        """
        Create or merge a strategy node with proper labels and relationships.
        Uses MERGE to prevent duplicates based on unique identifiers.

        Args:
            node_type: Type of node (e.g., 'Strength', 'Goal', 'Product')
            node_data: Node properties (must include unique identifier)
            account_id: Account to link to

        Returns:
            Created/merged node data
        """
        # All nodes now use 'node_id' as the unique identifier (no backward compatibility with old type-specific IDs)
        id_field = "node_id"

        if id_field in node_data:
            # Use MERGE with unique identifier
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MERGE (n:{node_type}:Strategy {{{id_field}: $unique_id}})
            ON CREATE SET
                n += $node_data,
                n.created_time = datetime(),
                n.created_by = 'System'
            ON MATCH SET
                n += $node_data,
                n.last_modified = datetime()
            MERGE (n)-[:BELONGS_TO]->(acc)
            RETURN n
            """
            params = {
                "account_id": account_id,
                "unique_id": node_data[id_field],
                "node_data": node_data,
            }
        else:
            # Fallback to CREATE if no unique identifier (shouldn't happen)
            logger.warning(f"No unique identifier for {node_type}, using CREATE")
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            CREATE (n:{node_type}:Strategy)
            SET n += $node_data,
                n.created_time = datetime(),
                n.last_modified = datetime(),
                n.created_by = 'System'
            CREATE (n)-[:BELONGS_TO]->(acc)
            RETURN n
            """
            params = {"account_id": account_id, "node_data": node_data}

        result = self.connection.execute_query(query, params)
        return result[0]["n"] if result else None

    def update_strategy_node(
        self, node_id: str, updates: dict, user: str = "System"
    ) -> dict:
        """
        Update an existing strategy node with versioning.

        Args:
            node_id: ID of node to update
            updates: Properties to update
            user: User making the update

        Returns:
            Updated node data
        """
        # First, create a version snapshot
        version_query = """
        MATCH (n:Strategy)
        WHERE elementId(n) = $node_id
        CREATE (v:Version:Strategy)
        SET v = properties(n),
            v.version_created = datetime(),
            v.version_number = COALESCE(n.version_number, 1)
        CREATE (n)-[:PREVIOUS_VERSION]->(v)
        """

        # Then update the node
        update_query = """
        MATCH (n:Strategy)
        WHERE elementId(n) = $node_id
        SET n += $updates,
            n.last_modified = datetime(),
            n.last_modified_by = $user,
            n.version_number = COALESCE(n.version_number, 1) + 1
        RETURN n
        """

        # Execute in transaction
        def update_with_version(tx):
            tx.run(version_query, node_id=node_id)
            result = tx.run(update_query, node_id=node_id, updates=updates, user=user)
            return [record.data() for record in result]

        result = self.connection.execute_write_transaction(update_with_version)
        return result[0]["n"] if result else None

    def get_account_strategies(
        self, account_id: str, include_versions: bool = False
    ) -> dict:
        """
        Retrieve all strategy nodes for an account.

        Args:
            account_id: Account identifier
            include_versions: Whether to include version history

        Returns:
            Dictionary of strategy components
        """
        query = """
        MATCH (acc:Account {account_id: $account_id})
        OPTIONAL MATCH (acc)<-[:BELONGS_TO]-(n:Strategy)
        WHERE NOT 'Version' IN labels(n)
        RETURN acc,
               collect(DISTINCT {
                   type: [label IN labels(n) WHERE label <> 'Strategy'][0],
                   properties: properties(n)
               }) as strategies
        """

        if include_versions:
            query += """
            UNION
            MATCH (acc:Account {account_id: $account_id})
            OPTIONAL MATCH (acc)<-[:BELONGS_TO]-(n:Strategy)-[:PREVIOUS_VERSION*]->(v:Version)
            RETURN acc,
                   collect(DISTINCT {
                       type: 'Version',
                       properties: properties(v)
                   }) as strategies
            """

        result = self.connection.execute_query(query, {"account_id": account_id})
        return result[0] if result else None

    def search_strategies(
        self, query_embedding: list[float], account_id: str, top_k: int = 5
    ) -> list[dict]:
        """
        Perform vector similarity search on strategy nodes.

        Args:
            query_embedding: Query vector embedding
            account_id: Filter by account
            top_k: Number of results

        Returns:
            List of similar strategy nodes
        """
        query = """
        CALL db.index.vector.queryNodes('strategy_search', $top_k, $embedding)
        YIELD node, score
        WHERE (node)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        RETURN node, score,
               [label IN labels(node) WHERE label <> 'Strategy'][0] as type
        ORDER BY score DESC
        """

        return self.connection.execute_query(
            query,
            {"embedding": query_embedding, "account_id": account_id, "top_k": top_k},
        )

    def close(self):
        """Close the connection."""
        self.connection.close()


# Singleton instance for reuse
_neo4j_ops = None


def get_neo4j_operations() -> Neo4jOperations:
    """Get or create a singleton Neo4jOperations instance."""
    global _neo4j_ops
    if _neo4j_ops is None:
        _neo4j_ops = Neo4jOperations()
    return _neo4j_ops
