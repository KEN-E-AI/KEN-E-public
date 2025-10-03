"""
Embedding generation and management for Neo4j strategy nodes.
Uses Vertex AI embeddings for semantic search capabilities.
"""

import os
import logging
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import time
import vertexai
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

from .neo4j_tools import Neo4jOperations, get_neo4j_operations

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates and manages embeddings for strategy nodes in Neo4j using Vertex AI."""

    def __init__(self, neo4j_ops: Neo4jOperations = None):
        """
        Initialize the embedding generator with Vertex AI.

        Args:
            neo4j_ops: Neo4j operations instance
        """
        self.neo4j_ops = neo4j_ops or get_neo4j_operations()

        # Initialize Vertex AI
        project = os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev')
        location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

        vertexai.init(project=project, location=location)

        # Use Vertex AI's text embedding model
        # text-embedding-004 is the latest and most performant
        # Alternative: textembedding-gecko@003 for backward compatibility
        self.embedding_model_name = "text-embedding-004"
        self.embedding_model = TextEmbeddingModel.from_pretrained(self.embedding_model_name)
        self.embedding_dimension = 768  # Dimension for text-embedding-004

        logger.info(f"Initialized Vertex AI embeddings with model: {self.embedding_model_name}")

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """
        Generate embedding for a given text using Vertex AI.

        Args:
            text: Text to generate embedding for
            task_type: Type of task - RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search

        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Create embedding input
            embedding_input = TextEmbeddingInput(
                text=text,
                task_type=task_type
            )

            # Generate embedding
            embeddings = self.embedding_model.get_embeddings([embedding_input])

            if embeddings and len(embeddings) > 0:
                return embeddings[0].values
            else:
                raise ValueError("No embedding generated")

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_batch_embeddings(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to generate embeddings for
            task_type: Type of task

        Returns:
            List of embedding vectors
        """
        try:
            # Create embedding inputs
            embedding_inputs = [
                TextEmbeddingInput(text=text, task_type=task_type)
                for text in texts
            ]

            # Generate embeddings in batch (Vertex AI handles batching efficiently)
            embeddings = self.embedding_model.get_embeddings(embedding_inputs)

            return [emb.values for emb in embeddings]

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def get_nodes_needing_embeddings(self, account_id: str = None) -> List[Dict]:
        """
        Get all Strategy nodes that need embeddings.

        Args:
            account_id: Optional filter by account

        Returns:
            List of nodes needing embeddings
        """
        query = """
        MATCH (n:Strategy)
        WHERE n.embedding IS NULL
        AND n.description IS NOT NULL
        AND (n.deleted IS NULL OR n.deleted = false)
        """

        if account_id:
            query += """
            AND (n)-[:BELONGS_TO]->(:Account {account_id: $account_id})
            """

        query += """
        RETURN id(n) AS node_id,
               n.description AS text,
               COALESCE(n.display_name, n.product_name, '') AS name,
               labels(n) AS types
        """

        return self.neo4j_ops.connection.execute_query(
            query,
            {'account_id': account_id} if account_id else {}
        )

    def get_modified_nodes_needing_embeddings(
        self,
        account_id: str = None,
        since_timestamp: str = None
    ) -> List[Dict]:
        """
        Get nodes that have been modified and need embedding updates.

        Args:
            account_id: Optional filter by account
            since_timestamp: Get nodes modified after this timestamp

        Returns:
            List of modified nodes needing new embeddings
        """
        query = """
        MATCH (n:Strategy)
        WHERE n.description IS NOT NULL
        AND (n.deleted IS NULL OR n.deleted = false)
        AND (n.embedding_generated_at IS NULL
             OR n.last_modified > n.embedding_generated_at)
        """

        if account_id:
            query += """
            AND (n)-[:BELONGS_TO]->(:Account {account_id: $account_id})
            """

        if since_timestamp:
            query += """
            AND n.last_modified > datetime($since_timestamp)
            """

        query += """
        RETURN id(n) AS node_id,
               n.description AS text,
               COALESCE(n.display_name, n.product_name, '') AS name,
               labels(n) AS types,
               n.last_modified AS modified_at
        """

        params = {}
        if account_id:
            params['account_id'] = account_id
        if since_timestamp:
            params['since_timestamp'] = since_timestamp

        return self.neo4j_ops.connection.execute_query(query, params)

    def update_node_embedding(self, node_id: int, embedding: List[float]):
        """
        Update a node's embedding in Neo4j.

        Args:
            node_id: Neo4j node ID
            embedding: Embedding vector
        """
        query = """
        MATCH (n)
        WHERE id(n) = $node_id
        SET n.embedding = $embedding,
            n.embedding_generated_at = datetime(),
            n.embedding_model = $model
        """

        self.neo4j_ops.connection.execute_query(query, {
            'node_id': node_id,
            'embedding': embedding,
            'model': self.embedding_model_name
        })

    def update_batch_node_embeddings(self, node_embeddings: List[Dict]):
        """
        Update multiple nodes' embeddings in a single transaction.

        Args:
            node_embeddings: List of dicts with 'node_id' and 'embedding' keys
        """
        query = """
        UNWIND $updates AS update
        MATCH (n)
        WHERE id(n) = update.node_id
        SET n.embedding = update.embedding,
            n.embedding_generated_at = datetime(),
            n.embedding_model = $model
        """

        self.neo4j_ops.connection.execute_query(query, {
            'updates': node_embeddings,
            'model': self.embedding_model_name
        })

    def generate_embeddings_for_account(
        self,
        account_id: str,
        batch_size: int = 20,
        delay_seconds: float = 0.05
    ) -> Dict[str, Any]:
        """
        Generate embeddings for all nodes in an account using batch processing.

        Args:
            account_id: Account identifier
            batch_size: Number of embeddings to generate in each batch
            delay_seconds: Delay between batches (Vertex AI has generous limits)

        Returns:
            Summary of embedding generation
        """
        logger.info(f"Generating embeddings for account {account_id}")

        nodes = self.get_nodes_needing_embeddings(account_id)
        total_nodes = len(nodes)
        success_count = 0
        error_count = 0
        errors = []

        logger.info(f"Found {total_nodes} nodes needing embeddings")

        # Process in batches for efficiency
        for i in range(0, total_nodes, batch_size):
            batch = nodes[i:i + batch_size]
            batch_texts = [self._create_embedding_text(node) for node in batch]

            try:
                # Generate embeddings for batch
                embeddings = self.generate_batch_embeddings(batch_texts)

                # Prepare updates
                updates = [
                    {'node_id': node['node_id'], 'embedding': embedding}
                    for node, embedding in zip(batch, embeddings)
                ]

                # Update all nodes in batch
                self.update_batch_node_embeddings(updates)

                success_count += len(batch)
                logger.debug(f"Batch {i//batch_size + 1}: Generated {len(batch)} embeddings")

                # Small delay between batches (Vertex AI has generous quotas)
                if i + batch_size < total_nodes:
                    time.sleep(delay_seconds)

            except Exception as e:
                error_count += len(batch)
                error_msg = f"Failed batch {i//batch_size + 1}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        result = {
            'total_nodes': total_nodes,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        }

        logger.info(f"Embedding generation complete: {success_count}/{total_nodes} successful")
        return result

    def update_embeddings_incremental(
        self,
        account_id: str = None,
        since_timestamp: str = None,
        batch_size: int = 20
    ) -> Dict[str, Any]:
        """
        Update embeddings for modified nodes only using batch processing.

        Args:
            account_id: Optional account filter
            since_timestamp: Update nodes modified after this time
            batch_size: Number of embeddings per batch

        Returns:
            Summary of updates
        """
        logger.info("Running incremental embedding update")

        nodes = self.get_modified_nodes_needing_embeddings(account_id, since_timestamp)
        total_nodes = len(nodes)
        success_count = 0

        # Process in batches
        for i in range(0, total_nodes, batch_size):
            batch = nodes[i:i + batch_size]
            batch_texts = [self._create_embedding_text(node) for node in batch]

            try:
                embeddings = self.generate_batch_embeddings(batch_texts)
                updates = [
                    {'node_id': node['node_id'], 'embedding': embedding}
                    for node, embedding in zip(batch, embeddings)
                ]
                self.update_batch_node_embeddings(updates)
                success_count += len(batch)

            except Exception as e:
                logger.error(f"Failed to update batch: {e}")

        logger.info(f"Updated {success_count}/{total_nodes} embeddings")

        return {
            'updated_count': success_count,
            'total_modified': total_nodes
        }

    def _create_embedding_text(self, node: Dict) -> str:
        """
        Create text for embedding from node properties.

        Args:
            node: Node dictionary with properties

        Returns:
            Text string for embedding
        """
        # Combine name and description for richer embeddings
        name = node.get('name', '')
        description = node.get('text', '')
        types = [t for t in node.get('types', []) if t != 'Strategy']

        # Format: "Type: Name. Description"
        type_str = types[0] if types else 'Strategy'

        if name:
            return f"{type_str}: {name}. {description}"
        else:
            return f"{type_str}: {description}"

    def verify_embeddings(self, account_id: str) -> Dict[str, Any]:
        """
        Verify that all strategy nodes have embeddings.

        Args:
            account_id: Account to verify

        Returns:
            Verification results
        """
        query = """
        MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        WHERE n.deleted IS NULL OR n.deleted = false
        RETURN
            COUNT(n) AS total_nodes,
            COUNT(n.embedding) AS nodes_with_embeddings,
            COUNT(CASE WHEN n.embedding IS NULL THEN 1 END) AS nodes_without_embeddings
        """

        result = self.neo4j_ops.connection.execute_query(query, {'account_id': account_id})

        if result:
            data = result[0]
            data['complete'] = data['nodes_without_embeddings'] == 0
            data['completion_percentage'] = (
                (data['nodes_with_embeddings'] / data['total_nodes'] * 100)
                if data['total_nodes'] > 0 else 0
            )
            return data

        return {
            'total_nodes': 0,
            'nodes_with_embeddings': 0,
            'nodes_without_embeddings': 0,
            'complete': True,
            'completion_percentage': 100
        }


class EmbeddingSearch:
    """Performs semantic search using embeddings."""

    def __init__(self, neo4j_ops: Neo4jOperations = None, embedding_generator: EmbeddingGenerator = None):
        """
        Initialize the search module.

        Args:
            neo4j_ops: Neo4j operations instance
            embedding_generator: Embedding generator instance
        """
        self.neo4j_ops = neo4j_ops or get_neo4j_operations()
        self.embedding_generator = embedding_generator or EmbeddingGenerator(neo4j_ops=self.neo4j_ops)

    def search(
        self,
        query_text: str,
        account_id: str,
        top_k: int = 5,
        min_score: float = 0.7
    ) -> List[Dict]:
        """
        Perform semantic search for strategies.

        Args:
            query_text: Natural language query
            account_id: Account to search within
            top_k: Number of results to return
            min_score: Minimum similarity score

        Returns:
            List of matching strategy nodes
        """
        # Generate query embedding (use RETRIEVAL_QUERY task type for search)
        query_embedding = self.embedding_generator.generate_embedding(
            query_text,
            task_type="RETRIEVAL_QUERY"
        )

        # Search in Neo4j
        results = self.neo4j_ops.search_strategies(query_embedding, account_id, top_k)

        # Filter by minimum score and format results
        formatted_results = []
        for result in results:
            if result['score'] >= min_score:
                formatted_results.append({
                    'name': result['node'].get('display_name', result['node'].get('product_name', 'N/A')),
                    'description': result['node'].get('description', ''),
                    'type': result['type'],
                    'score': round(result['score'], 3),
                    'node_id': result['node'].get('id')
                })

        return formatted_results