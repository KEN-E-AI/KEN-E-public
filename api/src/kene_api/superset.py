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
            backoff_factor=1
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
                "refresh": True
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/security/login",
                json=auth_payload,
                timeout=30
            )
            response.raise_for_status()
            
            auth_data = response.json()
            self.access_token = auth_data.get("access_token")
            
            if not self.access_token:
                raise SupersetClientError("Failed to obtain access token from Superset")
            
            # Set authorization header for future requests
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            })
            
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
                f"{self.base_url}/api/v1/dataset/{dataset_id}",
                timeout=30
            )
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            return response.json().get("result")
            
        except requests.RequestException as e:
            logger.error(f"Failed to get dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to get dataset: {e}")

    async def create_metric(self, dataset_id: int, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new metric in a Superset dataset."""
        await self._ensure_authenticated()
        
        try:
            # First verify the dataset exists
            dataset = await self.get_dataset(dataset_id)
            if not dataset:
                raise SupersetClientError(f"Dataset {dataset_id} not found")
            
            metric_payload = {
                "metric_name": metric_data.get("metric_name"),
                "verbose_name": metric_data.get("verbose_name"),
                "expression": metric_data.get("expression"),
                "description": metric_data.get("description", ""),
                "d3_format": metric_data.get("d3_format", ""),
                "is_restricted": False,
                "warning_text": "",
                "metric_type": "count"  # Default metric type
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/dataset/{dataset_id}/metric",
                json=metric_payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully created metric {metric_data.get('metric_name')} in dataset {dataset_id}")
            return result.get("result", {})
            
        except requests.RequestException as e:
            logger.error(f"Failed to create metric in dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to create metric: {e}")

    async def update_metric(self, dataset_id: int, metric_id: int, metric_data: Dict[str, Any]) -> Dict[str, Any]:
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
            
            response = self.session.put(
                f"{self.base_url}/api/v1/dataset/{dataset_id}/metric/{metric_id}",
                json=metric_payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Successfully updated metric {metric_id} in dataset {dataset_id}")
            return result.get("result", {})
            
        except requests.RequestException as e:
            logger.error(f"Failed to update metric {metric_id} in dataset {dataset_id}: {e}")
            raise SupersetClientError(f"Failed to update metric: {e}")

    async def delete_metric(self, dataset_id: int, metric_id: int) -> bool:
        """Delete a metric from a Superset dataset."""
        await self._ensure_authenticated()
        
        try:
            response = self.session.delete(
                f"{self.base_url}/api/v1/dataset/{dataset_id}/metric/{metric_id}",
                timeout=30
            )
            
            if response.status_code == 404:
                logger.warning(f"Metric {metric_id} not found in dataset {dataset_id}")
                return True  # Consider it successful if already deleted
                
            response.raise_for_status()
            logger.info(f"Successfully deleted metric {metric_id} from dataset {dataset_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to delete metric {metric_id} from dataset {dataset_id}: {e}")
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

    async def find_metric_by_name(self, dataset_id: int, metric_name: str) -> Optional[Dict[str, Any]]:
        """Find a metric by name within a dataset."""
        metrics = await self.get_metrics_for_dataset(dataset_id)
        
        for metric in metrics:
            if metric.get("metric_name") == metric_name:
                return metric
        
        return None

    async def health_check(self) -> bool:
        """Check if Superset is accessible."""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=10
            )
            return response.status_code == 200
        except requests.RequestException:
            return False


# Global instance
superset_client = SupersetClient()


async def get_superset_client() -> SupersetClient:
    """Dependency injection function for FastAPI endpoints."""
    return superset_client
