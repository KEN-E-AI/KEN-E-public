"""Storage service for managing Google Cloud Storage operations."""

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import UploadFile
from google.api_core import exceptions
from google.cloud import storage

logger = logging.getLogger(__name__)


class StorageService:
    """Service for Google Cloud Storage operations."""

    def __init__(self, project_id: str | None = None):
        """
        Initialize storage service.

        Args:
            project_id: Google Cloud project ID (defaults to environment variable)
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        self.environment = os.getenv("ENVIRONMENT", "development").lower()
        self.client = storage.Client(project=self.project_id)
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID must be set")

    def _get_bucket_config(self, data_region: str) -> tuple[str, str]:
        """
        Get bucket name and location based on environment and data region.

        Args:
            data_region: User's selected data region ("US" or "EU")

        Returns:
            tuple: (bucket_name, location)
        """
        # Normalize data region
        region = data_region.upper() if data_region else "US"
        if region not in ["US", "EU"]:
            logger.warning(f"Invalid data region '{data_region}', defaulting to US")
            region = "US"

        # Map environment and region to bucket name and GCS location
        bucket_configs = {
            "production": {
                "US": ("ken-e-files-us", "us-central1"),
                "EU": ("ken-e-files-eu", "europe-west1"),
            },
            "staging": {
                "US": ("ken-e-staging-files-us", "us-central1"),
                "EU": ("ken-e-staging-files-eu", "europe-west1"),
            },
            "development": {
                "US": ("ken-e-dev-files-us", "us-central1"),
                "EU": ("ken-e-dev-files-eu", "europe-west1"),
            },
        }

        # Get configuration or default to development US
        env_config = bucket_configs.get(self.environment, bucket_configs["development"])
        bucket_name, location = env_config.get(region, env_config["US"])

        logger.info(
            f"Bucket config for env={self.environment}, region={region}: "
            f"bucket={bucket_name}, location={location}"
        )

        return bucket_name, location

    async def ensure_bucket_exists(self, data_region: str) -> tuple[str, str]:
        """
        Ensure the appropriate bucket exists for the environment and data region.

        Args:
            data_region: User's selected data region ("US" or "EU")

        Returns:
            tuple: (bucket_name, location)

        Raises:
            Exception: If bucket creation fails
        """
        bucket_name, location = self._get_bucket_config(data_region)

        try:
            # Check if bucket already exists
            try:
                bucket = self.client.get_bucket(bucket_name)
                logger.info(f"Bucket {bucket_name} already exists")
                return bucket_name, location
            except exceptions.NotFound:
                pass

            # Create new bucket
            bucket = self.client.create_bucket(
                bucket_name,
                location=location,
                project=self.project_id,
            )

            logger.info(
                f"Created bucket {bucket.name} in {bucket.location} "
                f"for environment {self.environment} and region {data_region}"
            )
            return bucket_name, location

        except Exception as e:
            logger.error(
                f"Failed to create bucket {bucket_name} for env={self.environment}, "
                f"region={data_region}: {e}"
            )
            raise Exception(f"Failed to create storage bucket: {e}") from e

    async def upload_business_documents(
        self, account_id: str, data_region: str, files: list[UploadFile]
    ) -> list[dict[str, Any]]:
        """
        Upload business strategy documents to the appropriate bucket.

        Args:
            account_id: Account ID
            data_region: User's selected data region ("US" or "EU")
            files: List of files to upload

        Returns:
            list[dict]: List of uploaded file information

        Raises:
            Exception: If upload fails
        """
        if not files:
            return []

        # Ensure bucket exists for the environment and data region
        bucket_name, location = await self.ensure_bucket_exists(data_region)

        try:
            bucket = self.client.get_bucket(bucket_name)
        except exceptions.NotFound as e:
            # This shouldn't happen since we ensured bucket exists, but handle it
            raise Exception(
                f"Bucket {bucket_name} not found after ensuring it exists"
            ) from e

        uploaded_files = []

        for file in files:
            try:
                # Read file content
                file_content = await file.read()

                # Create blob path: accounts/{account_id}/{filename}
                blob_path = f"accounts/{account_id}/{file.filename}"
                blob = bucket.blob(blob_path)

                # Set content type if available
                if file.content_type:
                    blob.content_type = file.content_type

                # Upload file
                blob.upload_from_string(file_content)

                file_info = {
                    "filename": file.filename,
                    "blob_path": blob_path,
                    "size": len(file_content),
                    "content_type": file.content_type,
                    "bucket": bucket_name,
                    "gcs_url": f"gs://{bucket_name}/{blob_path}",
                    "public_url": blob.public_url
                    if hasattr(blob, "public_url")
                    else None,
                }

                uploaded_files.append(file_info)
                logger.info(
                    f"Uploaded {file.filename} to {blob_path} for account {account_id}"
                )

                # Reset file pointer for potential reuse
                await file.seek(0)

            except Exception as e:
                logger.error(
                    f"Failed to upload file {file.filename} for account {account_id}: {e}"
                )
                # Continue with other files but record the error
                uploaded_files.append(
                    {
                        "filename": file.filename,
                        "error": str(e),
                        "status": "failed",
                    }
                )

        return uploaded_files

    async def delete_account_documents(self, account_id: str, data_region: str) -> bool:
        """
        Delete all documents for an account from the appropriate bucket.

        Args:
            account_id: Account ID
            data_region: User's selected data region ("US" or "EU")

        Returns:
            bool: True if deletion successful, False otherwise
        """
        bucket_name, _ = self._get_bucket_config(data_region)

        try:
            bucket = self.client.get_bucket(bucket_name)

            # Delete all blobs for this account
            prefix = f"accounts/{account_id}/"
            blobs = bucket.list_blobs(prefix=prefix)
            deleted_count = 0

            for blob in blobs:
                blob.delete()
                deleted_count += 1
                logger.debug(f"Deleted blob {blob.name} from bucket {bucket_name}")

            logger.info(
                f"Deleted {deleted_count} documents for account {account_id} "
                f"from bucket {bucket_name}"
            )
            return True

        except exceptions.NotFound:
            logger.info(f"Bucket {bucket_name} for account {account_id} does not exist")
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete documents for account {account_id} "
                f"from bucket {bucket_name}: {e}"
            )
            return False

    async def list_account_documents(
        self, account_id: str, data_region: str
    ) -> list[dict[str, Any]]:
        """
        List all documents for an account.

        Args:
            account_id: Account ID
            data_region: User's selected data region ("US" or "EU")

        Returns:
            list[dict]: List of document information
        """
        bucket_name, _ = self._get_bucket_config(data_region)

        try:
            bucket = self.client.get_bucket(bucket_name)
            prefix = f"accounts/{account_id}/"

            documents = []
            for blob in bucket.list_blobs(prefix=prefix):
                documents.append(
                    {
                        "filename": blob.name.split("/")[-1],
                        "blob_path": blob.name,
                        "size": blob.size,
                        "content_type": blob.content_type,
                        "created": blob.time_created.isoformat()
                        if blob.time_created
                        else None,
                        "updated": blob.updated.isoformat() if blob.updated else None,
                        "gcs_url": f"gs://{bucket_name}/{blob.name}",
                        "bucket": bucket_name,
                        "environment": self.environment,
                        "data_region": data_region,
                    }
                )

            return documents

        except exceptions.NotFound:
            logger.info(f"Bucket {bucket_name} for account {account_id} does not exist")
            return []
        except Exception as e:
            logger.error(
                f"Failed to list documents for account {account_id} "
                f"from bucket {bucket_name}: {e}"
            )
            return []

    async def ensure_account_folder(self, account_id: str, data_region: str) -> bool:
        """
        Ensure that a Google Cloud Storage folder exists for the account.

        This creates a placeholder file in the account's folder to ensure the folder
        structure exists, even when no documents have been uploaded yet.

        Args:
            account_id: Account ID
            data_region: User's selected data region ("US" or "EU")

        Returns:
            bool: True if folder was created/exists, False if creation failed
        """
        try:
            # Ensure bucket exists for the environment and data region
            bucket_name, location = await self.ensure_bucket_exists(data_region)
            bucket = self.client.get_bucket(bucket_name)

            # Create a placeholder file to ensure the folder exists
            placeholder_path = f"accounts/{account_id}/.placeholder"
            placeholder_blob = bucket.blob(placeholder_path)

            # Check if placeholder already exists
            if placeholder_blob.exists():
                logger.debug(f"Account folder for {account_id} already exists in {bucket_name}")
                return True

            # Create placeholder file with minimal content
            placeholder_content = f"Account folder created for {account_id}\nCreated at: {datetime.now().isoformat()}"
            placeholder_blob.upload_from_string(
                placeholder_content,
                content_type="text/plain"
            )

            logger.info(
                f"Created account folder for {account_id} in bucket {bucket_name} "
                f"(region: {data_region})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to create account folder for {account_id} in region {data_region}: {e}"
            )
            return False


def get_storage_service() -> StorageService:
    """Dependency injection for StorageService."""
    return StorageService()
