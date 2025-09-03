"""
Encryption service for secure storage of integration credentials.
Uses Google Cloud KMS for encryption/decryption.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Any

from cryptography.fernet import Fernet
from google.cloud import firestore

# from google.cloud import kms  # TODO: Install when implementing KMS
# from google.cloud.kms import KeyManagementServiceClient

logger = logging.getLogger(__name__)

# For development, we'll use Fernet encryption
# In production, this should use Google Cloud KMS
USE_LOCAL_ENCRYPTION = os.getenv("USE_LOCAL_ENCRYPTION", "true").lower() == "true"


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize the encryption service."""
        if USE_LOCAL_ENCRYPTION:
            # For local development, use a fixed key (should be in env vars in production)
            encryption_key = os.getenv("ENCRYPTION_KEY")
            if not encryption_key:
                # Generate a new key for development
                encryption_key = Fernet.generate_key().decode()
                logger.warning(
                    f"No ENCRYPTION_KEY found, using generated key: {encryption_key}"
                )
            self.cipher = Fernet(encryption_key.encode())
            self.kms_client = None
        else:
            # Initialize Google Cloud KMS client
            # self.kms_client = KeyManagementServiceClient()  # TODO: Uncomment when KMS is available
            self.kms_client = None
            self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
            self.location_id = os.getenv("KMS_LOCATION_ID", "us-central1")
            self.key_ring_id = os.getenv("KMS_KEY_RING_ID", "integration-keys")
            self.key_id = os.getenv("KMS_KEY_ID", "integration-encryption-key")
            self.cipher = None

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64 encoded encrypted string
        """
        try:
            if USE_LOCAL_ENCRYPTION:
                # Use Fernet for local encryption
                encrypted = self.cipher.encrypt(plaintext.encode())
                return base64.b64encode(encrypted).decode()
            else:
                # Use Google Cloud KMS
                key_name = self.kms_client.crypto_key_path(
                    self.project_id, self.location_id, self.key_ring_id, self.key_id
                )

                # Convert string to bytes
                plaintext_bytes = plaintext.encode("utf-8")

                # Encrypt the data
                response = self.kms_client.encrypt(
                    request={
                        "name": key_name,
                        "plaintext": plaintext_bytes,
                    }
                )

                # Return base64 encoded ciphertext
                return base64.b64encode(response.ciphertext).decode()

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64 encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        try:
            if USE_LOCAL_ENCRYPTION:
                # Use Fernet for local decryption
                encrypted = base64.b64decode(ciphertext)
                decrypted = self.cipher.decrypt(encrypted)
                return decrypted.decode()
            else:
                # Use Google Cloud KMS
                key_name = self.kms_client.crypto_key_path(
                    self.project_id, self.location_id, self.key_ring_id, self.key_id
                )

                # Decode from base64
                ciphertext_bytes = base64.b64decode(ciphertext)

                # Decrypt the data
                response = self.kms_client.decrypt(
                    request={
                        "name": key_name,
                        "ciphertext": ciphertext_bytes,
                    }
                )

                return response.plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise


class IntegrationCredentialsService:
    """Service for managing integration credentials in Firestore."""

    def __init__(self, db: firestore.Client):
        """Initialize the service with a Firestore client."""
        self.db = db
        self.encryption_service = EncryptionService()
        self.collection_name = "integration_credentials"

    async def store_credentials(
        self,
        account_id: str,
        integration_type: str,
        credentials: dict[str, Any],
        user_id: str,
    ) -> None:
        """
        Store encrypted credentials for an integration.

        Args:
            account_id: The account ID
            integration_type: Type of integration (e.g., "google_analytics")
            credentials: The credentials to store
            user_id: ID of the user storing the credentials
        """
        try:
            # Convert credentials to JSON string
            credentials_json = json.dumps(credentials)

            # Encrypt the credentials
            encrypted_credentials = self.encryption_service.encrypt(credentials_json)

            # Create document ID
            doc_id = f"{account_id}_{integration_type}"

            # Store in Firestore
            doc_data = {
                "account_id": account_id,
                "integration_type": integration_type,
                "encrypted_credentials": encrypted_credentials,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "created_by": user_id,
                "updated_by": user_id,
            }

            # Run sync Firestore operation in thread pool
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            await loop.run_in_executor(None, doc_ref.set, doc_data)

            logger.info(
                f"Stored credentials for {integration_type} in account {account_id}"
            )

        except Exception as e:
            logger.error(f"Failed to store credentials: {e}")
            raise

    async def get_credentials(
        self, account_id: str, integration_type: str
    ) -> dict[str, Any] | None:
        """
        Retrieve and decrypt credentials for an integration.

        Args:
            account_id: The account ID
            integration_type: Type of integration

        Returns:
            Decrypted credentials or None if not found
        """
        try:
            doc_id = f"{account_id}_{integration_type}"
            # Run sync Firestore operation in thread pool
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            doc = await loop.run_in_executor(None, doc_ref.get)

            if not doc.exists:
                return None

            doc_data = doc.to_dict()
            encrypted_credentials = doc_data.get("encrypted_credentials")

            if not encrypted_credentials:
                return None

            # Decrypt the credentials
            credentials_json = self.encryption_service.decrypt(encrypted_credentials)
            return json.loads(credentials_json)

        except Exception as e:
            logger.error(f"Failed to retrieve credentials: {e}")
            raise

    async def update_credentials(
        self,
        account_id: str,
        integration_type: str,
        credentials: dict[str, Any],
        user_id: str,
    ) -> None:
        """
        Update encrypted credentials for an integration.

        Args:
            account_id: The account ID
            integration_type: Type of integration
            credentials: The new credentials
            user_id: ID of the user updating the credentials
        """
        try:
            # Convert credentials to JSON string
            credentials_json = json.dumps(credentials)

            # Encrypt the credentials
            encrypted_credentials = self.encryption_service.encrypt(credentials_json)

            # Create document ID
            doc_id = f"{account_id}_{integration_type}"

            # Update in Firestore
            update_data = {
                "encrypted_credentials": encrypted_credentials,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "updated_by": user_id,
            }

            # Run sync Firestore operation in thread pool
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            await loop.run_in_executor(None, doc_ref.update, update_data)

            logger.info(
                f"Updated credentials for {integration_type} in account {account_id}"
            )

        except Exception as e:
            logger.error(f"Failed to update credentials: {e}")
            raise

    async def delete_credentials(
        self, account_id: str, integration_type: str
    ) -> None:
        """
        Delete credentials for an integration.

        Args:
            account_id: The account ID
            integration_type: Type of integration
        """
        try:
            doc_id = f"{account_id}_{integration_type}"
            # Run sync Firestore operation in thread pool
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            await loop.run_in_executor(None, doc_ref.delete)

            logger.info(
                f"Deleted credentials for {integration_type} in account {account_id}"
            )

        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}")
            raise

    async def check_credentials_exist(
        self, account_id: str, integration_type: str
    ) -> bool:
        """
        Check if credentials exist for an integration.

        Args:
            account_id: The account ID
            integration_type: Type of integration

        Returns:
            True if credentials exist, False otherwise
        """
        try:
            doc_id = f"{account_id}_{integration_type}"
            # Run sync Firestore operation in thread pool
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection(self.collection_name).document(doc_id)
            doc = await loop.run_in_executor(None, doc_ref.get)
            return doc.exists

        except Exception as e:
            logger.error(f"Failed to check credentials existence: {e}")
            return False
