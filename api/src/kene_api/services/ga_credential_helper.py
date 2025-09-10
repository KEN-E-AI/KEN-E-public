"""
Helper service for managing Google Analytics OAuth credentials.
Handles retrieval, formatting, and refresh of OAuth tokens for GA integration.
"""

import base64
import json
import logging
from datetime import datetime
from typing import Any

import httpx
from google.cloud import firestore

from ..services.encryption_service import IntegrationCredentialsService

logger = logging.getLogger(__name__)


class GACredentialHelper:
    """Helper class for managing Google Analytics OAuth credentials."""

    def __init__(self, db: firestore.Client):
        """Initialize the GA credential helper.
        
        Args:
            db: Firestore client instance
        """
        self.db = db
        self.creds_service = IntegrationCredentialsService(db)

    async def get_oauth_credentials(
        self,
        account_id: str
    ) -> dict[str, Any] | None:
        """
        Retrieve Google Analytics OAuth credentials for an account.
        
        Args:
            account_id: The account ID to retrieve credentials for
            
        Returns:
            Dictionary containing OAuth tokens or None if not found
        """
        try:
            # Retrieve stored OAuth credentials
            credentials = await self.creds_service.get_credentials(
                account_id=account_id,
                integration_type="google_analytics"
            )

            if not credentials:
                logger.info(f"No GA OAuth credentials found for account {account_id}")
                return None

            # Check if access token is present
            if not credentials.get("access_token"):
                logger.error(f"Missing access_token for account {account_id}")
                return None

            return credentials

        except Exception as e:
            logger.error(f"Failed to retrieve GA OAuth credentials: {e}")
            return None

    async def refresh_if_expired(
        self,
        account_id: str,
        credentials: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Check if access token is expired and refresh if needed.
        
        Args:
            account_id: The account ID
            credentials: Current OAuth credentials
            
        Returns:
            Updated credentials with new access token or None if refresh fails
        """
        try:
            # Check if token is expired
            expires_at = credentials.get("expires_at", 0)
            current_time = datetime.now().timestamp()

            # Log full credentials structure (without sensitive data) for debugging
            cred_keys = list(credentials.keys()) if credentials else []
            logger.info(f"Credentials structure for account {account_id}: keys={cred_keys}")
            logger.info(f"Token expiry check for account {account_id}: expires_at={expires_at}, current_time={current_time}, diff={(expires_at - current_time) if expires_at else 'N/A'}")

            # If expires_at is 0 or missing, consider token expired
            if expires_at == 0:
                logger.warning(f"No expires_at timestamp for account {account_id}, treating as expired")

            # Add 5-minute buffer before expiry
            if expires_at == 0 or current_time >= (expires_at - 300):
                logger.info(f"Access token expired or expiring soon for account {account_id} (expires_at: {expires_at}, current: {current_time})")

                # Check if we have a refresh token
                refresh_token = credentials.get("refresh_token")
                if not refresh_token:
                    logger.error(f"No refresh token available for account {account_id}")
                    return None

                # Get OAuth client configuration from environment
                import os
                client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

                logger.info(f"OAuth client ID found: {bool(client_id)}, Secret found: {bool(client_secret)}")

                if not client_id or not client_secret:
                    logger.error(f"OAuth client configuration not found. CLIENT_ID present: {bool(client_id)}, SECRET present: {bool(client_secret)}")
                    return None

                # Refresh the token
                async with httpx.AsyncClient() as client:
                    refresh_response = await client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        },
                    )

                    if refresh_response.status_code != 200:
                        logger.error(f"Token refresh failed: {refresh_response.text}")
                        return None

                    new_tokens = refresh_response.json()

                    # Update credentials with new access token
                    credentials["access_token"] = new_tokens.get("access_token")
                    credentials["expires_at"] = datetime.now().timestamp() + new_tokens.get("expires_in", 3600)

                    # Store updated credentials
                    await self.creds_service.update_credentials(
                        account_id=account_id,
                        integration_type="google_analytics",
                        credentials=credentials,
                        user_id="system"  # System-initiated refresh
                    )

                    logger.info(f"Successfully refreshed access token for account {account_id}")

            return credentials

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None

    def format_for_agent(
        self,
        credentials: dict[str, Any],
        account_id: str
    ) -> str:
        """
        Format OAuth credentials for consumption by the GA agent.
        
        Args:
            credentials: OAuth credentials dictionary
            account_id: The account ID (used as tenant_id)
            
        Returns:
            Base64-encoded JSON string containing OAuth tokens
        """
        try:
            # Prepare credentials in the format expected by the MCP server
            agent_credentials = {
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
                "tenant_id": account_id
            }

            # Convert to JSON and encode to base64
            creds_json = json.dumps(agent_credentials)
            creds_base64 = base64.b64encode(creds_json.encode()).decode()

            return creds_base64

        except Exception as e:
            logger.error(f"Failed to format credentials for agent: {e}")
            raise

    async def get_and_format_credentials(
        self,
        account_id: str
    ) -> dict[str, str] | None:
        """
        Retrieve, refresh if needed, and format GA OAuth credentials.
        
        Args:
            account_id: The account ID
            
        Returns:
            Dictionary with tenant_id and formatted credentials, or None if not available
        """
        try:
            # Get OAuth credentials
            credentials = await self.get_oauth_credentials(account_id)
            if not credentials:
                return None

            # Refresh if expired
            credentials = await self.refresh_if_expired(account_id, credentials)
            if not credentials:
                return None

            # Format for agent
            formatted_creds = self.format_for_agent(credentials, account_id)

            return {
                "tenant_id": account_id,
                "tenant_credentials": formatted_creds
            }

        except Exception as e:
            logger.error(f"Failed to get and format GA credentials: {e}")
            return None
