"""Google Secret Manager utilities for KEN-E API."""

import json
import os
from typing import Any

from google.cloud import secretmanager


def get_secret(secret_path: str) -> str:
    """
    Get a secret from Google Cloud Secret Manager.

    Args:
        secret_path: Full secret path in format: projects/{project_id}/secrets/{secret_name}/versions/{version}
                    e.g., "projects/123456/secrets/neo4j-password/versions/latest"

    Returns:
        str: The secret value

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        # Initialize the Secret Manager client
        client = secretmanager.SecretManagerServiceClient()

        # Access the secret version
        response = client.access_secret_version(request={"name": secret_path})

        # Decode and return the secret value
        secret_value = response.payload.data.decode("UTF-8")
        return secret_value

    except Exception as e:
        raise Exception(f"Failed to retrieve secret from {secret_path}: {e}")


def get_secret_json(secret_path: str) -> dict[str, Any]:
    """
    Get a JSON secret from Google Cloud Secret Manager and parse it.

    Args:
        secret_path: Full secret path in format: projects/{project_id}/secrets/{secret_name}/versions/{version}

    Returns:
        dict[str, Any]: The parsed JSON secret

    Raises:
        Exception: If secret retrieval or JSON parsing fails
    """
    try:
        secret_value = get_secret(secret_path)
        return json.loads(secret_value)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON from secret {secret_path}: {e}")
    except Exception as e:
        raise Exception(f"Failed to retrieve JSON secret from {secret_path}: {e}")


def get_env_var_or_secret(env_var: str, default: str = "") -> str:
    """
    Get a value from environment variable. If the env var value looks like a secret path,
    fetch it from Secret Manager. Otherwise, return the env var value directly.

    Args:
        env_var: Environment variable name
        default: Default value if env var is not set

    Returns:
        str: The resolved value (either from env var directly or from Secret Manager)
    """
    env_value = os.getenv(env_var, default)
    
    # Check if the environment variable value looks like a Secret Manager path
    if env_value.startswith("projects/") and "/secrets/" in env_value and "/versions/" in env_value:
        try:
            return get_secret(env_value)
        except Exception as e:
            print(f"Warning: Failed to get secret for {env_var}: {e}")
            # Fall back to the original env value in case of error
            return env_value
    
    return env_value


def get_env_var_or_secret_json(env_var: str) -> dict[str, Any] | None:
    """
    Get a JSON value from environment variable. If the env var value looks like a secret path,
    fetch it from Secret Manager and parse as JSON. Otherwise, return None.

    Args:
        env_var: Environment variable name

    Returns:
        dict[str, Any] | None: The parsed JSON value or None if not available
    """
    env_value = os.getenv(env_var)
    
    if not env_value:
        return None
    
    # Check if the environment variable value looks like a Secret Manager path
    if env_value.startswith("projects/") and "/secrets/" in env_value and "/versions/" in env_value:
        try:
            return get_secret_json(env_value)
        except Exception as e:
            print(f"Warning: Failed to get JSON secret for {env_var}: {e}")
            return None
    
    return None