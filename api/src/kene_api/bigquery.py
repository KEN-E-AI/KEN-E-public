"""BigQuery service for data operations."""

import os
from typing import Any

from dotenv import load_dotenv
from google.auth import default
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

from .secret_manager import get_env_var_or_secret_json

# Load environment variables
load_dotenv() 

# Constants
BIGQUERY_NOT_INITIALIZED = "BigQuery not initialized"


class BigQueryService:
    """BigQuery service for data operations."""

    def __init__(self):
        """Initialize BigQuery service."""
        self._client: bigquery.Client | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize BigQuery client with service account credentials.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if self._initialized:
                return True

            # Get BigQuery configuration from environment
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            use_adc = (
                os.getenv("USE_APPLICATION_DEFAULT_CREDENTIALS", "false").lower()
                == "true"
            )
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

            if not project_id:
                raise ValueError(
                    "BigQuery configuration missing. Check GOOGLE_CLOUD_PROJECT_ID"
                )

            # Method 1: Use Application Default Credentials (recommended for Cloud Run)
            if use_adc or not credentials_path:
                print("Using Application Default Credentials for BigQuery")
                try:
                    credentials, detected_project = default()
                    self._client = bigquery.Client(
                        project=project_id,
                        credentials=credentials,
                    )
                    print(
                        f"Successfully initialized BigQuery with ADC for project: {project_id}"
                    )
                    self._initialized = True
                    return True
                except Exception as e:
                    print(
                        f"Failed to initialize with Application Default Credentials: {e}"
                    )
                    # Fall back to credentials file if ADC fails
                    if not credentials_path:
                        raise

            # Method 2: Use credentials from Secret Manager or file (fallback or local development)
            if credentials_path:
                credentials = None

                # Check if credentials_path is a Secret Manager path
                if (
                    credentials_path.startswith("projects/")
                    and "/secrets/" in credentials_path
                    and "/versions/" in credentials_path
                ):
                    print(
                        f"Loading service account credentials from Secret Manager: {credentials_path}"
                    )
                    try:
                        # Get service account JSON from Secret Manager
                        service_account_info = get_env_var_or_secret_json(
                            "GOOGLE_APPLICATION_CREDENTIALS"
                        )
                        if service_account_info:
                            credentials = (
                                service_account.Credentials.from_service_account_info(
                                    service_account_info
                                )
                            )
                            print(
                                "Successfully loaded service account credentials from Secret Manager"
                            )
                        else:
                            raise ValueError(
                                "Failed to retrieve service account JSON from Secret Manager"
                            )
                    except Exception as e:
                        print(f"Failed to load credentials from Secret Manager: {e}")
                        raise

                else:
                    # Traditional file-based credentials
                    # Ensure the credentials path is a file path, not raw JSON
                    if credentials_path.strip().startswith("{"):
                        raise ValueError(
                            "GOOGLE_APPLICATION_CREDENTIALS appears to be a raw JSON string. Expected a file path. This usually means it was incorrectly passed via --set-env-vars instead of --set-secrets."
                        )

                    if not os.path.isfile(credentials_path):
                        raise ValueError(
                            f"Credentials file not found at: {credentials_path}"
                        )

                    print(f"Using BigQuery credentials from file: {credentials_path}")
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path
                    )

                # Initialize BigQuery client with explicit credentials
                self._client = bigquery.Client(
                    project=project_id, credentials=credentials
                )

                print(
                    f"Successfully initialized BigQuery with service account credentials for project: {project_id}"
                )
                self._initialized = True
                return True

            raise ValueError(
                "No valid authentication method found. Set USE_APPLICATION_DEFAULT_CREDENTIALS=true for Cloud Run or provide GOOGLE_APPLICATION_CREDENTIALS file path."
            )

        except Exception as e:
            print(f"Error initializing BigQuery: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if BigQuery service is available.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            if not self._initialized:
                print("BigQuery not initialized, attempting to initialize...")
                if not self.initialize():
                    print("Failed to initialize BigQuery during health check")
                    return False

            # Try a simple BigQuery operation
            if self._client:
                # Query a small dataset to verify connectivity
                query = "SELECT 1"
                query_job = self._client.query(query)
                _ = query_job.result()  # Wait for query to complete
                print("BigQuery health check successful")
                return True
            else:
                print("BigQuery client is None")
                return False
        except Exception as e:
            print(f"BigQuery health check failed: {e}")
            return False

    def query(
        self,
        query: str,
        parameters: list[bigquery.ScalarQueryParameter] | None = None,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """
        Execute a BigQuery query and return results.

        Args:
            query: SQL query to execute
            parameters: Query parameters for parameterized queries
            timeout: Query timeout in seconds

        Returns:
            List[Dict[str, Any]]: Query results as list of dictionaries
        """
        if not self._initialized or not self._client:
            raise RuntimeError(BIGQUERY_NOT_INITIALIZED)

        try:
            # Configure query job
            job_config = bigquery.QueryJobConfig()
            if parameters:
                job_config.query_parameters = parameters

            # Execute query
            query_job = self._client.query(query, job_config=job_config)
            results = query_job.result(timeout=timeout)

            # Convert results to list of dictionaries
            return [dict(row) for row in results]

        except Exception as e:
            print(f"Error executing BigQuery query: {e}")
            raise

    def query_holiday_activities(
        self,
        project_id: str,
        regions: list[str],
    ) -> list[dict[str, Any]]:
        """
        Query holiday activities from BigQuery for specified regions.

        Args:
            project_id: GCP project ID
            regions: List of region codes

        Returns:
            List[Dict[str, Any]]: List of holiday activities with description, start_date, end_date
        """
        if not regions:
            return []

        # Build region list for SQL IN clause
        region_list = ", ".join([f"'{region}'" for region in regions])

        # Query holiday activities
        query = f"""
        SELECT
            description,
            start_date,
            end_date,
            region
        FROM `{project_id}.shared_activities.holiday-import`
        WHERE region IN ({region_list})
        GROUP BY ALL
        ORDER BY start_date
        """

        try:
            print(f"Executing BigQuery query for regions: {regions}")
            print(f"Query: {query}")
            results = self.query(query)
            print(f"BigQuery returned {len(results)} results")
            return results
        except NotFound as e:
            print(f"Table {project_id}.shared_activities.holiday-import not found: {e}")
            return []
        except Exception as e:
            print(f"Error querying holiday activities: {e}")
            print(f"Query was: {query}")
            raise  # Re-raise to see the actual error

    def get_existing_activity_logs(
        self,
        project_id: str,
        account_id: str,
        activity_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get existing activity logs from BigQuery to check what's already been created.

        This is a placeholder for future functionality if we want to track
        which activity logs have been created in BigQuery as well as Neo4j.

        Args:
            project_id: GCP project ID
            account_id: Account ID
            activity_id: Activity ID

        Returns:
            List[Dict[str, Any]]: List of existing activity logs
        """
        # For now, return empty list as we're tracking this in Neo4j
        # This method is here for future expansion if needed
        return []


# Global service instance
_bigquery_service: BigQueryService | None = None


def get_bigquery_service() -> BigQueryService:
    """
    Get the global BigQueryService instance.

    Returns:
        BigQueryService: The global BigQuery service instance
    """
    global _bigquery_service

    if _bigquery_service is None:
        _bigquery_service = BigQueryService()
        _bigquery_service.initialize()

    return _bigquery_service
