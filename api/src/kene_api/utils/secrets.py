"""Simple Secret Manager integration for environment variables.

Environment variables can contain either:
- Actual values (for local development)
- Secret Manager references: sm://project_id/secret_name or sm://secret_name
"""

import os
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Cache secrets for the lifetime of the application
_secret_cache = {}


def get_env_or_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable value, fetching from Secret Manager if needed.
    
    If the environment variable starts with 'sm://', it's treated as a 
    Secret Manager reference and the actual value is fetched.
    
    Format: sm://project_id/secret_name or sm://secret_name (uses default project)
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        The actual value (from env or Secret Manager) or default
    """
    value = os.getenv(key, default)
    
    if not value or not value.startswith("sm://"):
        return value
    
    # Extract secret path from sm://project_id/secret_name or sm://secret_name
    secret_path = value[5:]  # Remove 'sm://' prefix
    
    # Check cache first
    if secret_path in _secret_cache:
        return _secret_cache[secret_path]
    
    try:
        secret_value = _fetch_secret(secret_path)
        _secret_cache[secret_path] = secret_value
        return secret_value
    except Exception as e:
        logger.error(f"Failed to fetch secret {secret_path}: {e}")
        # Fall back to the default value
        return default


@lru_cache(maxsize=32)
def _fetch_secret(secret_path: str) -> str:
    """Fetch a secret from Google Secret Manager.
    
    Args:
        secret_path: Either 'project_id/secret_name' or just 'secret_name'
        
    Returns:
        The secret value
    """
    try:
        from google.cloud import secretmanager
    except ImportError:
        raise ImportError(
            "google-cloud-secret-manager is required for Secret Manager support. "
            "Install with: pip install google-cloud-secret-manager"
        )
    
    client = secretmanager.SecretManagerServiceClient()
    
    # Parse the secret path
    if "/" in secret_path:
        # Full path: project_id/secret_name
        project_id, secret_name = secret_path.split("/", 1)
    else:
        # Just secret name, use default project
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "ken-e-dev")
        secret_name = secret_path
    
    # Build the resource name
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    
    # Access the secret
    response = client.access_secret_version(request={"name": name})
    
    # Return the decoded payload
    return response.payload.data.decode("UTF-8")