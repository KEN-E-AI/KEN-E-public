"""Firebase Admin SDK initialization and management."""

import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials
from google.auth import default

logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None


def initialize_firebase_admin() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK.

    Uses Application Default Credentials (ADC) in production,
    or service account key file in development.

    Returns:
        firebase_admin.App: The initialized Firebase app instance
    """
    global _firebase_app

    # Check if already initialized
    if _firebase_app is not None:
        return _firebase_app

    try:
        # Try to use existing app if available
        _firebase_app = firebase_admin.get_app()
        logger.info("Using existing Firebase Admin app")
        return _firebase_app
    except ValueError:
        # App not initialized yet
        pass

    try:
        # Method 1: Use Application Default Credentials (recommended for Cloud Run)
        use_adc = (
            os.getenv("USE_APPLICATION_DEFAULT_CREDENTIALS", "false").lower() == "true"
        )
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if use_adc or not credentials_path:
            logger.info(
                "Initializing Firebase Admin with Application Default Credentials"
            )
            cred, project = default()
            _firebase_app = firebase_admin.initialize_app(
                credentials.ApplicationDefault(),
                options={
                    "projectId": os.getenv("GOOGLE_CLOUD_PROJECT_ID"),
                },
            )
        else:
            # Method 2: Use service account key file (for local development)
            logger.info(
                f"Initializing Firebase Admin with service account from: {credentials_path}"
            )
            cred = credentials.Certificate(credentials_path)
            _firebase_app = firebase_admin.initialize_app(cred)

        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app

    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise


def get_firebase_auth() -> auth:
    """
    Get Firebase Auth instance.

    Returns:
        auth: Firebase Auth module
    """
    initialize_firebase_admin()
    return auth


def verify_id_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token.

    Args:
        id_token: The Firebase ID token to verify

    Returns:
        dict: Decoded token containing user information

    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"Failed to verify ID token: {e}")
        raise ValueError(f"Invalid token: {str(e)}")


def get_user(uid: str) -> auth.UserRecord:
    """
    Get user record by UID.

    Args:
        uid: The user's UID

    Returns:
        auth.UserRecord: The user record

    Raises:
        ValueError: If user not found
    """
    try:
        user = auth.get_user(uid)
        return user
    except Exception as e:
        logger.error(f"Failed to get user {uid}: {e}")
        raise ValueError(f"User not found: {str(e)}")
