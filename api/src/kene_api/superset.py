"""Apache Superset client for managing datasets and metrics."""

import logging
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import settings

logger = logging.getLogger(__name__)


class SupersetClientError(Exception):
    """Custom exception for Superset client errors."""

    pass


class SupersetClient:
    """Client for interacting with Apache Superset REST API."""

    def __init__(self):
        """Initialize the Superset client."""
        self.base_url = settings.superset_base_url.rstrip("/")
        self.username = settings.superset_username
        self.password = settings.superset_password
        self.session = requests.Session()
        self.access_token = None

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    async def authenticate(self) -> None:
        """Authenticate with Superset and obtain access token."""
        try:
            auth_payload = {
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": True,
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/security/login", json=auth_payload, timeout=30
            )
            response.raise_for_status()

            auth_data = response.json()
            self.access_token = auth_data.get("access_token")

            if not self.access_token:
                raise SupersetClientError("Failed to obtain access token from Superset")

            # Set authorization header for future requests
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
            )

            logger.info("Successfully authenticated with Superset")

        except requests.RequestException as e:
            logger.error(f"Failed to authenticate with Superset: {e}")
            raise SupersetClientError(f"Authentication failed: {e}")

    async def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated."""
        if not self.access_token:
            await self.authenticate()

    async def get_dataset(self, dataset_id: int) -> Optional[Dict[str, Any]]:
        """Get dataset information by ID."""
        await self._ensure_authenticated()

        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/dataset/{dataset_id}", timeout=30
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.json().get("result")

        except requests.RequestException as e:
            logger.error(f"Failed to get dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to get dataset: {e}")

    async def create_metric(
        self, dataset_id: int, metric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new metric in a Superset dataset by updating the dataset."""
        await self._ensure_authenticated()

        try:
            # Get the current dataset with all its metrics
            response = self.session.get(
                f"{self.base_url}/api/v1/dataset/{dataset_id}", timeout=30
            )
            response.raise_for_status()

            dataset_response = response.json()
            dataset = dataset_response.get("result", {})

            if not dataset:
                raise SupersetClientError(f"Dataset {dataset_id} not found")

            # Get existing metrics and clean them for the update
            existing_metrics = dataset.get("metrics", [])

            # Remove read-only fields from existing metrics - keep only the minimal required fields
            cleaned_existing_metrics = []
            for metric in existing_metrics:
                cleaned_metric = {
                    "metric_name": metric.get("metric_name"),
                    "verbose_name": metric.get("verbose_name"),
                    "expression": metric.get("expression"),
                }
                # Add optional fields only if they exist and are not empty
                if metric.get("description"):
                    cleaned_metric["description"] = metric.get("description")
                if metric.get("d3format"):
                    cleaned_metric["d3format"] = metric.get("d3format")
                if metric.get("currency"):
                    cleaned_metric["currency"] = metric.get("currency")

                cleaned_existing_metrics.append(cleaned_metric)

            # Create new metric payload with minimal required fields
            new_metric = {
                "metric_name": metric_data.get("metric_name"),
                "verbose_name": metric_data.get("verbose_name"),
                "expression": metric_data.get("expression"),
            }

            # Add optional fields only if they have values
            if metric_data.get("description"):
                new_metric["description"] = metric_data.get("description")
            if metric_data.get("d3_format"):
                new_metric["d3format"] = metric_data.get("d3_format")
            if metric_data.get("currency"):
                new_metric["currency"] = metric_data.get("currency")

            # Add new metric to cleaned existing metrics
            all_metrics = cleaned_existing_metrics + [new_metric]

            # Update the dataset with all metrics
            update_payload = {"metrics": all_metrics}

            response = self.session.put(
                f"{self.base_url}/api/v1/dataset/{dataset_id}",
                json=update_payload,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Successfully created metric {metric_data.get('metric_name')} in dataset {dataset_id}"
            )

            # Get the created metric from the response
            updated_metrics = result.get("result", {}).get("metrics", [])
            created_metric = None
            for metric in updated_metrics:
                if metric.get("metric_name") == metric_data.get("metric_name"):
                    created_metric = metric
                    break

            return created_metric or {}

        except requests.RequestException as e:
            logger.error(f"Failed to create metric in dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to create metric: {e}")

    async def update_metric(
        self, dataset_id: int, metric_id: int, metric_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing metric in a Superset dataset."""
        await self._ensure_authenticated()

        try:
            metric_payload = {}

            # Only include non-None values in the update payload
            if metric_data.get("metric_name") is not None:
                metric_payload["metric_name"] = metric_data["metric_name"]
            if metric_data.get("verbose_name") is not None:
                metric_payload["verbose_name"] = metric_data["verbose_name"]
            if metric_data.get("expression") is not None:
                metric_payload["expression"] = metric_data["expression"]
            if metric_data.get("description") is not None:
                metric_payload["description"] = metric_data["description"]
            if metric_data.get("d3_format") is not None:
                metric_payload["d3_format"] = metric_data["d3_format"]
            if metric_data.get("currency") is not None:
                metric_payload["currency"] = metric_data["currency"]

            response = self.session.put(
                f"{self.base_url}/api/v1/dataset/{dataset_id}/metric/{metric_id}",
                json=metric_payload,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Successfully updated metric {metric_id} in dataset {dataset_id}"
            )
            return result.get("result", {})

        except requests.RequestException as e:
            logger.error(
                f"Failed to update metric {metric_id} in dataset {dataset_id}: {e}"
            )
            raise SupersetClientError(f"Failed to update metric: {e}")

    async def delete_metric(self, dataset_id: int, metric_id: int) -> bool:
        """Delete a metric from a Superset dataset."""
        await self._ensure_authenticated()

        try:
            response = self.session.delete(
                f"{self.base_url}/api/v1/dataset/{dataset_id}/metric/{metric_id}",
                timeout=30,
            )

            if response.status_code == 404:
                logger.warning(f"Metric {metric_id} not found in dataset {dataset_id}")
                return True  # Consider it successful if already deleted

            response.raise_for_status()
            logger.info(
                f"Successfully deleted metric {metric_id} from dataset {dataset_id}"
            )
            return True

        except requests.RequestException as e:
            logger.error(
                f"Failed to delete metric {metric_id} from dataset {dataset_id}: {e}"
            )
            return False

    async def get_metrics_for_dataset(self, dataset_id: int) -> List[Dict[str, Any]]:
        """Get all metrics for a specific dataset."""
        await self._ensure_authenticated()

        try:
            dataset = await self.get_dataset(dataset_id)
            if not dataset:
                return []

            metrics = dataset.get("metrics", [])
            logger.info(f"Retrieved {len(metrics)} metrics for dataset {dataset_id}")
            return metrics

        except requests.RequestException as e:
            logger.error(f"Failed to get metrics for dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to get metrics: {e}")

    async def find_metric_by_name(
        self, dataset_id: int, metric_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find a metric by name within a dataset."""
        metrics = await self.get_metrics_for_dataset(dataset_id)

        for metric in metrics:
            if metric.get("metric_name") == metric_name:
                return metric

        return None

    async def health_check(self) -> bool:
        """Check if Superset is accessible."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False

    # Saved Queries Operations

    async def get_saved_queries_by_schema_pattern(
        self, schema_pattern: str
    ) -> List[Dict[str, Any]]:
        """
        Get all saved queries where the schema name matches the given pattern.

        Args:
            schema_pattern: Pattern to match schema names (e.g., "account123_output")

        Returns:
            List[Dict[str, Any]]: List of saved queries matching the pattern
        """
        await self._ensure_authenticated()

        try:
            # Get all saved queries
            response = self.session.get(
                f"{self.base_url}/api/v1/saved_query/", timeout=30
            )
            response.raise_for_status()

            result = response.json()
            all_queries = result.get("result", [])

            # Filter queries by schema pattern
            matching_queries = []
            for query in all_queries:
                schema = query.get("schema", "")
                if schema_pattern in schema:
                    matching_queries.append(query)

            logger.info(
                f"Found {len(matching_queries)} saved queries matching pattern '{schema_pattern}'"
            )
            return matching_queries

        except requests.RequestException as e:
            logger.error(f"Failed to get saved queries: {e}")
            raise SupersetClientError(f"Failed to get saved queries: {e}")

    async def create_saved_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new saved query in Superset.

        Args:
            query_data: Dictionary containing saved query data

        Returns:
            Dict[str, Any]: Created saved query data
        """
        await self._ensure_authenticated()

        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/saved_query/", json=query_data, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Successfully created saved query '{query_data.get('label', 'unknown')}'"
            )
            return result.get("result", {})

        except requests.RequestException as e:
            logger.error(f"Failed to create saved query: {e}")
            raise SupersetClientError(f"Failed to create saved query: {e}")

    async def update_saved_query(
        self, query_id: int, query_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing saved query in Superset.

        Args:
            query_id: ID of the saved query to update
            query_data: Dictionary containing updated saved query data

        Returns:
            Dict[str, Any]: Updated saved query data
        """
        await self._ensure_authenticated()

        try:
            response = self.session.put(
                f"{self.base_url}/api/v1/saved_query/{query_id}",
                json=query_data,
                timeout=30,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Successfully updated saved query {query_id}")
            return result.get("result", {})

        except requests.RequestException as e:
            logger.error(f"Failed to update saved query {query_id}: {e}")
            raise SupersetClientError(f"Failed to update saved query: {e}")

    async def delete_saved_query(self, query_id: int) -> bool:
        """
        Delete a saved query from Superset.

        Args:
            query_id: ID of the saved query to delete

        Returns:
            bool: True if deletion was successful
        """
        await self._ensure_authenticated()

        try:
            response = self.session.delete(
                f"{self.base_url}/api/v1/saved_query/{query_id}", timeout=30
            )
            response.raise_for_status()

            logger.info(f"Successfully deleted saved query {query_id}")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to delete saved query {query_id}: {e}")
            raise SupersetClientError(f"Failed to delete saved query: {e}")

    async def get_saved_query_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        """
        Get a saved query by its label.

        Args:
            label: Label of the saved query to find

        Returns:
            Optional[Dict[str, Any]]: Saved query data or None if not found
        """
        await self._ensure_authenticated()

        try:
            # Use the direct endpoint with label parameter
            response = self.session.get(
                f"{self.base_url}/api/v1/saved_query/?label={label}", timeout=30
            )
            response.raise_for_status()

            result = response.json()
            queries = result.get("result", [])

            # Return the first matching query or None if not found
            if queries:
                return queries[0]

            return None

        except requests.RequestException as e:
            logger.error(f"Failed to get saved query by label '{label}': {e}")
            raise SupersetClientError(f"Failed to get saved query: {e}")

    async def execute_saved_query(self, query_label: str) -> Dict[str, Any]:
        """
        Execute a saved query and return the results.

        Args:
            query_label: Label of the saved query to execute

        Returns:
            Dict[str, Any]: Query execution results
        """
        await self._ensure_authenticated()

        try:
            # First find the saved query by label
            saved_query = await self.get_saved_query_by_label(query_label)
            if not saved_query:
                raise SupersetClientError(
                    f"Saved query with label '{query_label}' not found"
                )

            # Use the configured database ID from settings
            from .config import settings

            database_id = settings.superset_database_id

            logger.info(
                f"Executing saved query '{query_label}' with database_id={database_id}"
            )

            # Execute the query via SQL Lab
            query_payload = {
                "database_id": database_id,
                "sql": saved_query.get("sql"),
                "schema": saved_query.get("schema", ""),
            }

            response = self.session.post(
                f"{self.base_url}/api/v1/sqllab/execute/",
                json=query_payload,
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully executed saved query '{query_label}'")
                return result
            else:
                # Get detailed error information
                error_text = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", error_json)
                except:
                    error_detail = error_text

                raise SupersetClientError(
                    f"Query execution failed: {response.status_code} - {error_detail}"
                )

        except SupersetClientError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing saved query '{query_label}': {e}")
            raise SupersetClientError(f"Unexpected error during query execution: {e}")


# Global instance
superset_client = SupersetClient()


async def get_superset_client() -> SupersetClient:
    """Dependency injection function for FastAPI endpoints."""
    return superset_client
