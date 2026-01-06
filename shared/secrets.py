"""Universal Secret Manager integration for environment variables.

Shared utility for API, agents, and deployment scripts.

Environment variables can contain:
1. Raw values: Returned as-is (e.g., "my_password", "true", "8000")
2. sm:// format: sm://project_id/secret_name or sm://secret_name
3. Full GCP paths: projects/{project_id}/secrets/{secret_name}/versions/{version}

All three formats are automatically detected and handled by get_env_or_secret().

MIGRATION NOTE:
This module replaces the deprecated secret_manager.py module.

Key differences:
- Old: get_env_var_or_secret(key, allow_failure=True) - only supported full GCP paths
- New: get_env_or_secret(key, default=None) - supports all 3 formats

Error handling changes:
- Old: allow_failure parameter controlled exception raising
- New: Returns None (or default) on failure, logs error
- Callers should check for None return value instead of catching exceptions

Example migration:
  Old: api_key = get_env_var_or_secret("API_KEY", allow_failure=False)
  New: api_key = get_env_or_secret("API_KEY")
       if not api_key:
           raise ValueError("API_KEY not found")

Format examples:
  Raw value: NEO4J_PASSWORD=my_actual_password
  sm:// format: NEO4J_PASSWORD=sm://525657242938/NEO4J_PASSWORD
  Full GCP path:
    NEO4J_PASSWORD=projects/525657242938/secrets/NEO4J_PASSWORD/versions/latest
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# Cache secrets for the lifetime of the application
_secret_cache = {}


def get_env_or_secret(key: str, default: str | None = None) -> str | None:
    """Get environment variable value, fetching from Secret Manager if needed.

    Supports three formats:
    1. Raw values: Returned as-is (e.g., "my_password", "true", "8000")
    2. sm:// format: sm://project_id/secret_name or sm://secret_name
    3. Full GCP paths: projects/{project_id}/secrets/{secret_name}/versions/{version}

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        The actual value (from env or Secret Manager) or default

    Examples:
        >>> os.environ["PASSWORD"] = "raw_password"
        >>> get_env_or_secret("PASSWORD")
        'raw_password'

        >>> os.environ["PASSWORD"] = "sm://525657242938/NEO4J_PASSWORD"
        >>> get_env_or_secret("PASSWORD")
        '<value from Secret Manager>'

        >>> os.environ["PASSWORD"] = (
        ...     "projects/525657242938/secrets/NEO4J_PASSWORD/versions/latest"
        ... )
        >>> get_env_or_secret("PASSWORD")
        '<value from Secret Manager>'
    """
    value = os.getenv(key, default)

    if not value:
        return value

    # Check for sm:// format
    if value.startswith("sm://"):
        secret_path = value[5:]  # Remove 'sm://' prefix

        # Check cache first
        if secret_path in _secret_cache:
            return _secret_cache[secret_path]

        try:
            secret_value = _fetch_secret_from_sm_path(secret_path)
            _secret_cache[secret_path] = secret_value
            return secret_value
        except Exception as e:
            logger.error(f"Failed to fetch secret for {key}: {e}")
            return default

    # Check for full GCP Secret Manager path
    if value.startswith("projects/") and "/secrets/" in value and "/versions/" in value:
        # Check cache first
        if value in _secret_cache:
            return _secret_cache[value]

        try:
            secret_value = _fetch_secret_from_full_path(value)
            _secret_cache[value] = secret_value
            return secret_value
        except Exception as e:
            logger.error(f"Failed to fetch secret for {key}: {e}")
            return default

    # Not a secret reference, return raw value
    return value


def _fetch_secret_from_sm_path(secret_path: str) -> str:
    """Fetch secret from sm:// style path (project_id/secret_name or secret_name).

    Args:
        secret_path: Either 'project_id/secret_name' or just 'secret_name'

    Returns:
        The secret value

    Examples:
        >>> _fetch_secret_from_sm_path("525657242938/NEO4J_PASSWORD")
        >>> _fetch_secret_from_sm_path("NEO4J_PASSWORD")  # Uses GOOGLE_CLOUD_PROJECT
    """
    # Parse the secret path
    if "/" in secret_path:
        # Full path: project_id/secret_name
        project_id, secret_name = secret_path.split("/", 1)
    else:
        # Just secret name, use default project
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "ken-e-dev")
        secret_name = secret_path

    # Build the full resource name
    full_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    return _fetch_secret_from_full_path(full_path)


@lru_cache(maxsize=32)
def _fetch_secret_from_full_path(full_path: str) -> str:
    """Fetch a secret from Google Secret Manager using full resource path.

    Args:
        full_path: Full resource name like projects/123/secrets/name/versions/latest

    Returns:
        The secret value

    Raises:
        ImportError: If google-cloud-secret-manager is not installed
        Exception: If secret retrieval fails

    Examples:
        >>> _fetch_secret_from_full_path(
        ...     "projects/525657242938/secrets/NEO4J_PASSWORD/versions/latest"
        ... )
    """
    try:
        from google.cloud import secretmanager
    except ImportError as e:
        raise ImportError(
            "google-cloud-secret-manager is required for Secret Manager support. "
            "Install with: pip install google-cloud-secret-manager"
        ) from e

    client = secretmanager.SecretManagerServiceClient()

    # Access the secret
    response = client.access_secret_version(request={"name": full_path})

    # Return the decoded payload, stripping any trailing whitespace/newlines
    return response.payload.data.decode("UTF-8").strip()
