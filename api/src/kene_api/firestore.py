"""Firestore service for database operations."""

import os
from typing import Any

from dotenv import load_dotenv
from google.auth import default
from google.cloud import firestore
from google.cloud.exceptions import NotFound
from google.cloud.firestore_v1 import DELETE_FIELD
from google.cloud.firestore_v1.base_query import FieldFilter
from google.oauth2 import service_account

from .secret_manager import get_env_var_or_secret_json

# Load environment variables
load_dotenv()

# Constants
FIRESTORE_NOT_INITIALIZED = "Firestore not initialized"
CUSTOMER_DATABASE = "(default)"
ORGANIZATIONS_COLLECTION = "organizations"


class FirestoreService:
    """Firestore service for database operations."""

    def __init__(self):
        """Initialize Firestore service with credentials."""
        self._db: firestore.Client | None = None
        self._initialized = False

    def get_client(self) -> firestore.Client:
        """Get the Firestore client instance.

        Returns:
            firestore.Client: The Firestore client

        Raises:
            RuntimeError: If Firestore is not initialized
        """
        if not self._initialized:
            self.initialize()
        if self._db is None:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)
        return self._db

    def initialize(self) -> bool:
        """
        Initialize Firestore client with service account credentials.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            if self._initialized:
                return True

            # Get Firestore configuration from environment
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            database_id = os.getenv("FIRESTORE_DATABASE_ID", CUSTOMER_DATABASE)
            use_adc = (
                os.getenv("USE_APPLICATION_DEFAULT_CREDENTIALS", "false").lower()
                == "true"
            )
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

            if not project_id:
                raise ValueError(
                    "Firestore configuration missing. Check GOOGLE_CLOUD_PROJECT_ID"
                )

            # Method 1: Use Application Default Credentials (recommended for Cloud Run)
            if use_adc or not credentials_path:
                print("Using Application Default Credentials for Firestore")
                try:
                    credentials, detected_project = default()
                    self._db = firestore.Client(
                        project=project_id,
                        database=database_id,
                        credentials=credentials,
                    )
                    print(
                        f"Successfully initialized Firestore with ADC for project: {project_id}"
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

                    print(f"Using Firestore credentials from file: {credentials_path}")
                    credentials = service_account.Credentials.from_service_account_file(
                        credentials_path
                    )

                # Initialize Firestore client with explicit credentials
                self._db = firestore.Client(
                    project=project_id, database=database_id, credentials=credentials
                )

                print(
                    f"Successfully initialized Firestore with service account credentials for project: {project_id}"
                )
                self._initialized = True
                return True

            raise ValueError(
                "No valid authentication method found. Set USE_APPLICATION_DEFAULT_CREDENTIALS=true for Cloud Run or provide GOOGLE_APPLICATION_CREDENTIALS file path."
            )

        except Exception as e:
            print(f"Error initializing Firestore: {e}")
            return False

    def health_check(self) -> bool:
        """
        Check if Firestore service is available.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        try:
            if not self._initialized:
                print("Firestore not initialized, attempting to initialize...")
                if not self.initialize():
                    print("Failed to initialize Firestore during health check")
                    return False

            # Try a simple Firestore operation
            if self._db:
                self._db.collection("health_check").limit(1).get()
                print("Firestore health check successful")
                return True
            else:
                print("Firestore database client is None")
                return False
        except Exception as e:
            print(f"Firestore health check failed: {e}")
            return False

    # Firestore Operations

    def create_document(
        self,
        collection: str,
        document_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a document in Firestore.

        Args:
            collection: Collection name
            document_id: Document ID (optional, auto-generated if None)
            data: Document data

        Returns:
            str: Document ID
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        if data is None:
            data = {}

        collection_ref = self._db.collection(collection)

        if document_id:
            doc_ref = collection_ref.document(document_id)
            doc_ref.set(data)
            return document_id
        else:
            doc_ref = collection_ref.add(data)[1]
            return doc_ref.id

    def get_document(self, collection: str, document_id: str) -> dict[str, Any] | None:
        """
        Get a document from Firestore.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            Optional[Dict[str, Any]]: Document data or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        doc_ref = self._db.collection(collection).document(document_id)
        doc = doc_ref.get()

        if doc.exists:
            return doc.to_dict()
        return None

    def update_document(
        self, collection: str, document_id: str, data: dict[str, Any]
    ) -> bool:
        """
        Update a document in Firestore.

        Args:
            collection: Collection name
            document_id: Document ID
            data: Update data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(collection).document(document_id)
            doc_ref.update(data)
            return True
        except NotFound:
            return False

    def delete_document(self, collection: str, document_id: str) -> bool:
        """
        Delete a document from Firestore.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(collection).document(document_id)
            doc_ref.delete()
            return True
        except Exception:
            return False

    def list_documents(
        self,
        collection: str,
        limit: int | None = None,
        where_filters: list[tuple] | None = None,
    ) -> list[dict[str, Any]]:
        """
        List documents from a collection.

        Args:
            collection: Collection name
            limit: Maximum number of documents to return
            where_filters: List of (field, operator, value) tuples for filtering

        Returns:
            List[Dict[str, Any]]: List of documents
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        collection_ref = self._db.collection(collection)

        # Apply filters
        if where_filters:
            for field, operator, value in where_filters:
                collection_ref = collection_ref.where(
                    filter=FieldFilter(field, operator, value)
                )

        # Apply limit
        if limit:
            collection_ref = collection_ref.limit(limit)

        docs = collection_ref.get()

        result = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data is not None:
                doc_data["id"] = doc.id  # Include document ID
                result.append(doc_data)

        return result

    def query_documents(
        self,
        collection: str,
        field: str,
        operator: str,
        value: Any,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query documents from a collection.

        Args:
            collection: Collection name
            field: Field to query
            operator: Query operator ('==', '!=', '<', '<=', '>', '>=', 'in', 'not-in', 'array-contains', 'array-contains-any')
            value: Value to compare against
            limit: Maximum number of documents to return

        Returns:
            List[Dict[str, Any]]: List of matching documents
        """
        return self.list_documents(collection, limit, [(field, operator, value)])

    # KPI Operations

    def get_kpi_setting(
        self, organization_id: str, account_id: str, kpi_name: str
    ) -> str | None:
        """
        Get a specific KPI setting for an account.

        Args:
            organization_id: The organization document identifier
            account_id: The account identifier
            kpi_name: The KPI name (income_kpi, marketing_cost_kpi, or net_income_kpi)

        Returns:
            Optional[str]: The metric_id associated with the KPI, or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            if not doc_data:
                return None

            # Navigate the nested path: accounts[account_id].account_settings.overview_kpis[kpi_name]
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            account_settings = account_data.get("account_settings", {})
            overview_kpis = account_settings.get("overview_kpis", {})

            return overview_kpis.get(kpi_name)

        except Exception as e:
            print(f"Error getting KPI setting: {e}")
            return None

    def update_kpi_setting(
        self, organization_id: str, account_id: str, kpi_name: str, metric_id: str
    ) -> bool:
        """
        Update a specific KPI setting for an account.

        Args:
            organization_id: The organization document identifier
            account_id: The account identifier
            kpi_name: The KPI name (income_kpi, marketing_cost_kpi, or net_income_kpi)
            metric_id: The metric identifier to associate with the KPI

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )

            # Use Firestore's field path notation for nested updates
            field_path = (
                f"accounts.{account_id}.account_settings.overview_kpis.{kpi_name}"
            )

            doc_ref.update({field_path: metric_id})
            return True

        except NotFound:
            # If the document doesn't exist, we might need to create the nested structure
            try:
                # Create the nested structure if it doesn't exist
                doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                    organization_id
                )
                doc_ref.set(
                    {
                        "accounts": {
                            account_id: {
                                "account_settings": {
                                    "overview_kpis": {kpi_name: metric_id}
                                }
                            }
                        }
                    },
                    merge=True,
                )
                return True
            except Exception as e:
                print(f"Error creating KPI setting structure: {e}")
                return False
        except Exception as e:
            print(f"Error updating KPI setting: {e}")
            return False

    def get_all_kpi_settings(
        self, organization_id: str, account_id: str
    ) -> dict[str, str] | None:
        """
        Get all KPI settings for an account.

        Args:
            organization_id: The organization document identifier
            account_id: The account identifier

        Returns:
            Optional[Dict[str, str]]: Dictionary of KPI names to metric IDs, or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            if not doc_data:
                return None

            # Navigate the nested path: accounts[account_id].account_settings.overview_kpis
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            account_settings = account_data.get("account_settings", {})
            overview_kpis = account_settings.get("overview_kpis", {})

            return overview_kpis

        except Exception as e:
            print(f"Error getting all KPI settings: {e}")
            return None

    # Funnel Step Operations

    def create_funnel_step(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        funnel_step_data: dict[str, Any],
    ) -> bool:
        """
        Create a funnel step, handling step number conflicts by incrementing subsequent steps.

        Args:
            organization_id: The organization document identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number to insert
            funnel_step_data: The funnel step data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            # Get current funnel steps
            if doc.exists:
                doc_data = doc.to_dict() or {}
            else:
                doc_data = {}

            # Navigate to the funnel path
            accounts = doc_data.setdefault("accounts", {})
            account_data = accounts.setdefault(account_id, {})
            funnels = account_data.setdefault("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.setdefault("organization", {})
            else:  # big_bet
                big_bets = funnels.setdefault("big_bets", {})
                funnel_steps = big_bets.setdefault(big_bet_name, {})

            # If the step number already exists, increment all subsequent steps
            if str(funnel_step_num) in funnel_steps:
                # Create a list of step numbers to increment
                steps_to_increment = []
                for step_num_str in funnel_steps.keys():
                    step_num = int(step_num_str)
                    if step_num >= funnel_step_num:
                        steps_to_increment.append(step_num)

                # Sort in descending order to avoid conflicts during increment
                steps_to_increment.sort(reverse=True)

                # Increment step numbers
                for step_num in steps_to_increment:
                    step_data = funnel_steps.pop(str(step_num))
                    funnel_steps[str(step_num + 1)] = step_data

            # Add the new step
            funnel_steps[str(funnel_step_num)] = funnel_step_data

            # Update the document
            doc_ref.set(doc_data, merge=True)
            return True

        except Exception as e:
            print(f"Error creating funnel step: {e}")
            return False

    def get_funnel_step(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
    ) -> dict[str, Any] | None:
        """
        Get a specific funnel step.

        Args:
            organization_id: The organization document identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number

        Returns:
            Optional[Dict[str, Any]]: Funnel step data or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            if not doc_data:
                return None

            # Navigate to the funnel step
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            return funnel_steps.get(str(funnel_step_num))

        except Exception as e:
            print(f"Error getting funnel step: {e}")
            return None

    def list_funnel_steps(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all funnel steps for a specific funnel.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')

        Returns:
            List[Dict[str, Any]]: List of funnel steps with step numbers
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return []

            doc_data = doc.to_dict()
            if not doc_data:
                return []

            # Navigate to the funnel steps
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            # Convert to list with step numbers
            result = []
            for step_num_str, step_data in funnel_steps.items():
                step_with_num = dict(step_data)
                step_with_num["funnel_step_num"] = int(step_num_str)
                result.append(step_with_num)

            # Sort by step number
            result.sort(key=lambda x: x["funnel_step_num"])
            return result

        except Exception as e:
            print(f"Error listing funnel steps: {e}")
            return []

    def update_funnel_step(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        funnel_step_data: dict[str, Any],
    ) -> bool:
        """
        Update a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            funnel_step_data: The updated funnel step data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # Check if the step exists first
            existing_step = self.get_funnel_step(
                organization_id, account_id, funnel_type, big_bet_name, funnel_step_num
            )
            if existing_step is None:
                return False

            # Build the field path for the update
            if funnel_type == "organization":
                field_path = (
                    f"accounts.{account_id}.funnels.organization.{funnel_step_num}"
                )
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: funnel_step_data})
            return True

        except Exception as e:
            print(f"Error updating funnel step: {e}")
            return False

    def delete_funnel_step(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
    ) -> bool:
        """
        Delete a funnel step and shift subsequent steps down.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number to delete

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return False

            doc_data = doc.to_dict()
            if not doc_data:
                return False

            # Navigate to the funnel steps
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            # Check if the step exists
            if str(funnel_step_num) not in funnel_steps:
                return False

            # Remove the step
            del funnel_steps[str(funnel_step_num)]

            # Shift subsequent steps down
            steps_to_shift = []
            for step_num_str in funnel_steps.keys():
                step_num = int(step_num_str)
                if step_num > funnel_step_num:
                    steps_to_shift.append(step_num)

            # Sort in ascending order
            steps_to_shift.sort()

            # Shift step numbers down
            for step_num in steps_to_shift:
                step_data = funnel_steps.pop(str(step_num))
                funnel_steps[str(step_num - 1)] = step_data

            # Update the document
            doc_ref.set(doc_data, merge=True)
            return True

        except Exception as e:
            print(f"Error deleting funnel step: {e}")
            return False

    # Channel Operations

    def create_channel(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        channel_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Create a channel within a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            channel_data: The channel data

        Returns:
            Optional[Dict[str, Any]]: The created channel data or None if creation failed
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # First check if the funnel step exists
            funnel_step = self.get_funnel_step(
                organization_id, account_id, funnel_type, big_bet_name, funnel_step_num
            )
            if funnel_step is None:
                return None

            # Check if channel already exists
            existing_channel = self.get_channel(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
            )
            if existing_channel is not None:
                return None  # Channel already exists

            # Build the field path for the channel
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: channel_data})

            # Return the created data
            return channel_data

        except Exception as e:
            print(f"Error creating channel: {e}")
            return None

    def get_channel(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
    ) -> dict[str, Any] | None:
        """
        Get a specific channel from a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel

        Returns:
            Optional[Dict[str, Any]]: Channel data or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            if not doc_data:
                return None

            # Navigate to the channel
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            funnel_step = funnel_steps.get(str(funnel_step_num), {})
            channels = funnel_step.get("channels", {})

            return channels.get(channel_name)

        except Exception as e:
            print(f"Error getting channel: {e}")
            return None

    def list_channels(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
    ) -> list[dict[str, Any]]:
        """
        List all channels in a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number

        Returns:
            List[Dict[str, Any]]: List of channels with channel names
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return []

            doc_data = doc.to_dict()
            if not doc_data:
                return []

            # Navigate to the channels
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            funnel_step = funnel_steps.get(str(funnel_step_num), {})
            channels = funnel_step.get("channels", {})

            # Convert to list with channel names
            result = []
            for channel_name, channel_data in channels.items():
                channel_with_name = dict(channel_data)
                channel_with_name["channel_name"] = channel_name
                result.append(channel_with_name)

            # Sort by channel name
            result.sort(key=lambda x: x["channel_name"])
            return result

        except Exception as e:
            print(f"Error listing channels: {e}")
            return []

    def update_channel(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        channel_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Update a channel in a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            channel_data: The updated channel data

        Returns:
            Optional[Dict[str, Any]]: The updated channel data or None if update failed
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # Check if the channel exists first
            existing_channel = self.get_channel(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
            )
            if existing_channel is None:
                return None

            # Merge with existing data
            updated_data = {**existing_channel, **channel_data}

            # Build the field path for the update
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: updated_data})

            # Return the updated data
            return updated_data

        except Exception as e:
            print(f"Error updating channel: {e}")
            return None

    def delete_channel(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
    ) -> bool:
        """
        Delete a channel from a funnel step.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # Check if the channel exists first
            existing_channel = self.get_channel(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
            )
            if existing_channel is None:
                return False

            # Build the field path for deletion
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}"

            from google.cloud.firestore_v1 import DELETE_FIELD

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: DELETE_FIELD})
            return True

        except Exception as e:
            print(f"Error deleting channel: {e}")
            return False

    # Tactic Operations

    def create_tactic(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        tactic_name: str,
        tactic_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Create a tactic within a channel.

        Args:
            organization_id: The organization identifier
            account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            tactic_name: Name of the tactic
            tactic_data: The tactic data

        Returns:
            Optional[Dict[str, Any]]: The created tactic data or None if creation failed
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # First check if the channel exists
            channel = self.get_channel(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
            )
            if channel is None:
                return None

            # Check if tactic already exists
            existing_tactic = self.get_tactic(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
                tactic_name,
            )
            if existing_tactic is not None:
                return None  # Tactic already exists

            # Build the field path for the tactic
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: tactic_data})

            # Return the created data
            return tactic_data

        except Exception as e:
            print(f"Error creating tactic: {e}")
            return None

    def get_tactic(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        tactic_name: str,
    ) -> dict[str, Any] | None:
        """
        Get a specific tactic from a channel.

        Args:
            organization_id: The organization identifier
                        account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            tactic_name: Name of the tactic

        Returns:
            Optional[Dict[str, Any]]: Tactic data or None if not found
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            if not doc_data:
                return None

            # Navigate to the tactic
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            funnel_step = funnel_steps.get(str(funnel_step_num), {})
            channels = funnel_step.get("channels", {})
            channel = channels.get(channel_name, {})
            tactics = channel.get("tactics", {})

            return tactics.get(tactic_name)

        except Exception as e:
            print(f"Error getting tactic: {e}")
            return None

    def list_tactics(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
    ) -> list[dict[str, Any]]:
        """
        List all tactics in a channel.

        Args:
            organization_id: The organization identifier
                        account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel

        Returns:
            List[Dict[str, Any]]: List of tactics with tactic names
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc = doc_ref.get()

            if not doc.exists:
                return []

            doc_data = doc.to_dict()
            if not doc_data:
                return []

            # Navigate to the tactics
            accounts = doc_data.get("accounts", {})
            account_data = accounts.get(account_id, {})
            funnels = account_data.get("funnels", {})

            if funnel_type == "organization":
                funnel_steps = funnels.get("organization", {})
            else:  # big_bet
                big_bets = funnels.get("big_bets", {})
                funnel_steps = big_bets.get(big_bet_name, {})

            funnel_step = funnel_steps.get(str(funnel_step_num), {})
            channels = funnel_step.get("channels", {})
            channel = channels.get(channel_name, {})
            tactics = channel.get("tactics", {})

            # Return list of tactics with their names included
            result = []
            for tactic_name, tactic_data in tactics.items():
                tactic_with_name = dict(tactic_data)
                tactic_with_name["tactic_name"] = tactic_name
                result.append(tactic_with_name)

            return result

        except Exception as e:
            print(f"Error listing tactics: {e}")
            return []

    def update_tactic(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        tactic_name: str,
        tactic_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Update a tactic in a channel.

        Args:
            organization_id: The organization identifier
                        account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            tactic_name: Name of the tactic
            tactic_data: The updated tactic data

        Returns:
            Optional[Dict[str, Any]]: The updated tactic data or None if update failed
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # Check if the tactic exists first
            existing_tactic = self.get_tactic(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
                tactic_name,
            )
            if existing_tactic is None:
                return None

            # Merge with existing data
            updated_data = {**existing_tactic, **tactic_data}

            # Build the field path for the update
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: updated_data})

            # Return the updated data
            return updated_data

        except Exception as e:
            print(f"Error updating tactic: {e}")
            return None

    def delete_tactic(
        self,
        organization_id: str,
        account_id: str,
        funnel_type: str,
        big_bet_name: str | None,
        funnel_step_num: int,
        channel_name: str,
        tactic_name: str,
    ) -> bool:
        """
        Delete a tactic from a channel.

        Args:
            organization_id: The organization identifier
                        account_id: The account identifier
            funnel_type: Type of funnel ('organization' or 'big_bet')
            big_bet_name: Big bet name (required if funnel_type is 'big_bet')
            funnel_step_num: The step number
            channel_name: Name of the channel
            tactic_name: Name of the tactic

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            # Check if the tactic exists first
            existing_tactic = self.get_tactic(
                organization_id,
                account_id,
                funnel_type,
                big_bet_name,
                funnel_step_num,
                channel_name,
                tactic_name,
            )
            if existing_tactic is None:
                return False

            # Build the field path for the delete
            if funnel_type == "organization":
                field_path = f"accounts.{account_id}.funnels.organization.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"
            else:  # big_bet
                field_path = f"accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}.channels.{channel_name}.tactics.{tactic_name}"

            doc_ref = self._db.collection(ORGANIZATIONS_COLLECTION).document(
                organization_id
            )
            doc_ref.update({field_path: DELETE_FIELD})
            return True

        except Exception as e:
            print(f"Error deleting tactic: {e}")
            return False

    # Array Operations

    def array_union_document(
        self, collection: str, document_id: str, field: str, value: Any
    ) -> bool:
        """
        Add a value to an array field in a document using arrayUnion operation.

        Args:
            collection: Collection name
            document_id: Document ID
            field: Field name (must be an array field)
            value: Value to add to the array

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(collection).document(document_id)
            # Use Firestore's arrayUnion operation
            doc_ref.update({field: firestore.ArrayUnion([value])})
            return True
        except NotFound:
            return False

    def replace_array_element(
        self,
        collection: str,
        document_id: str,
        field: str,
        match_field: str,
        match_value: Any,
        new_value: dict[str, Any],
    ) -> bool:
        """
        Replace an element in an array field where a sub-field matches a value.

        Args:
            collection: Collection name
            document_id: Document ID
            field: Field name (must be an array field)
            match_field: Sub-field to match within array elements
            match_value: Value to match in the sub-field
            new_value: New value to replace the matched element

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(collection).document(document_id)
            doc = doc_ref.get()

            if not doc.exists:
                return False

            doc_data = doc.to_dict()
            if (
                not doc_data
                or field not in doc_data
                or not isinstance(doc_data[field], list)
            ):
                return False

            # Find and replace the matching element
            array_field = doc_data[field]
            found = False

            for i, item in enumerate(array_field):
                if isinstance(item, dict) and item.get(match_field) == match_value:
                    array_field[i] = new_value
                    found = True
                    break

            if not found:
                return False

            # Update the document with the modified array
            doc_ref.update({field: array_field})
            return True

        except NotFound:
            return False

    # Subcollection Operations

    def get_subcollection_document(
        self, collection: str, document_id: str, subcollection: str, subdocument_id: str
    ) -> dict[str, Any] | None:
        """
        Get a document from a subcollection.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID

        Returns:
            Optional[Dict[str, Any]]: Document data if found, None otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()
            else:
                return None

        except Exception:
            return None

    def update_subcollection_document(
        self,
        collection: str,
        document_id: str,
        subcollection: str,
        subdocument_id: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Update a document in a subcollection.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID
            data: Update data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            doc_ref.update(data)
            return True
        except NotFound:
            return False

    def create_subcollection_document(
        self,
        collection: str,
        document_id: str,
        subcollection: str,
        subdocument_id: str | None,
        data: dict[str, Any],
    ) -> str:
        """
        Create a document in a subcollection.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID (auto-generated if None)
            data: Document data

        Returns:
            str: Document ID of created document
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        subcollection_ref = (
            self._db.collection(collection)
            .document(document_id)
            .collection(subcollection)
        )

        if subdocument_id:
            doc_ref = subcollection_ref.document(subdocument_id)
            doc_ref.set(data)
            return subdocument_id
        else:
            doc_ref = subcollection_ref.add(data)
            return doc_ref[1].id  # doc_ref[1] is the DocumentReference

    def delete_subcollection_document(
        self, collection: str, document_id: str, subcollection: str, subdocument_id: str
    ) -> bool:
        """
        Delete a document from a subcollection.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            doc_ref.delete()
            return True
        except Exception:
            return False

    def array_union_subcollection_document(
        self,
        collection: str,
        document_id: str,
        subcollection: str,
        subdocument_id: str,
        field: str,
        value: Any,
    ) -> bool:
        """
        Add a value to an array field in a subcollection document using arrayUnion.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID
            field: Array field name
            value: Value to add to the array

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            doc_ref.update({field: firestore.ArrayUnion([value])})
            return True
        except NotFound:
            return False

    def replace_array_element_subcollection(
        self,
        collection: str,
        document_id: str,
        subcollection: str,
        subdocument_id: str,
        field: str,
        match_field: str,
        match_value: Any,
        new_value: Any,
    ) -> bool:
        """
        Replace an element in an array field of a subcollection document by matching a subfield.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID
            field: Array field name
            match_field: Field within array objects to match against
            match_value: Value to match in the match_field
            new_value: New value to replace the matched element

        Returns:
            bool: True if successful, False if not found or no match
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            doc = doc_ref.get()

            if not doc.exists:
                return False

            doc_data = doc.to_dict()
            if field not in doc_data or not isinstance(doc_data[field], list):
                return False

            # Find and replace the matching element
            array_field = doc_data[field]
            found = False

            for i, item in enumerate(array_field):
                if isinstance(item, dict) and item.get(match_field) == match_value:
                    array_field[i] = new_value
                    found = True
                    break

            if not found:
                return False

            # Update the document with the modified array
            doc_ref.update({field: array_field})
            return True

        except NotFound:
            return False

    def set_nested_field(
        self, collection: str, document_id: str, field_path: str, value: Any
    ) -> bool:
        """
        Set a nested field in a document using dot notation.

        This operation will create the nested structure if it doesn't exist,
        or update the field if it already exists.

        Args:
            collection: Collection name
            document_id: Document ID
            field_path: Dot-separated field path (e.g., "permissions.accounts.newAccountId")
            value: Value to set at the field path

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = self._db.collection(collection).document(document_id)
            # Use Firestore's field path notation for nested updates
            doc_ref.update({field_path: value})
            return True
        except NotFound:
            # If the document doesn't exist, create it with the nested structure
            try:
                doc_ref = self._db.collection(collection).document(document_id)
                doc_ref.set({field_path: value}, merge=True)
                return True
            except Exception as e:
                print(f"Error creating document with nested field: {e}")
                return False
        except Exception as e:
            print(f"Error setting nested field: {e}")
            return False

    def set_nested_field_subcollection(
        self,
        collection: str,
        document_id: str,
        subcollection: str,
        subdocument_id: str,
        field_path: str,
        value: Any,
    ) -> bool:
        """
        Set a nested field in a subcollection document using dot notation.

        This operation will create the nested structure if it doesn't exist,
        or update the field if it already exists.

        Args:
            collection: Parent collection name
            document_id: Parent document ID
            subcollection: Subcollection name
            subdocument_id: Subdocument ID
            field_path: Dot-separated field path (e.g., "permissions.accounts.newAccountId")
            value: Value to set at the field path

        Returns:
            bool: True if successful, False otherwise
        """
        if not self._initialized or not self._db:
            raise RuntimeError(FIRESTORE_NOT_INITIALIZED)

        try:
            doc_ref = (
                self._db.collection(collection)
                .document(document_id)
                .collection(subcollection)
                .document(subdocument_id)
            )
            # Use Firestore's field path notation for nested updates
            doc_ref.update({field_path: value})
            return True
        except NotFound:
            # If the document doesn't exist, create it with the nested structure
            try:
                doc_ref = (
                    self._db.collection(collection)
                    .document(document_id)
                    .collection(subcollection)
                    .document(subdocument_id)
                )
                doc_ref.set({field_path: value}, merge=True)
                return True
            except Exception as e:
                print(f"Error creating subcollection document with nested field: {e}")
                return False
        except Exception as e:
            print(f"Error setting nested field in subcollection: {e}")
            return False


# Global service instance
_firestore_service: FirestoreService | None = None


def get_firestore_service() -> FirestoreService:
    """
    Get the global FirestoreService instance.

    Returns:
        FirestoreService: The global Firestore service instance
    """
    global _firestore_service

    if _firestore_service is None:
        _firestore_service = FirestoreService()
        _firestore_service.initialize()

    return _firestore_service
