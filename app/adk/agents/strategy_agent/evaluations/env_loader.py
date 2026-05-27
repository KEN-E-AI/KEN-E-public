"""
Environment loader for strategy agent evaluations.

Loads environment variables from .env files for evaluation scripts.
Handles Google Cloud Secret Manager references.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv


def _fetch_secret_from_gcp(secret_path: str) -> str | None:
    """
    Fetch secret from Google Cloud Secret Manager.

    Args:
        secret_path: Path like 'projects/PROJECT_ID/secrets/SECRET_NAME'

    Returns:
        Secret value or None if fetch fails
    """
    try:
        from google.cloud import secretmanager

        # Parse the secret path
        match = re.match(r"projects/([^/]+)/secrets/([^/]+)", secret_path)
        if not match:
            return None

        project_id, secret_name = match.groups()

        # Create client and fetch secret
        client = secretmanager.SecretManagerServiceClient()
        name = f"{secret_path}/versions/latest"
        response = client.access_secret_version(request={"name": name})

        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Warning: Failed to fetch secret from {secret_path}: {e}")
        return None


def load_env() -> None:
    """
    Load environment variables for evaluation.

    Looks for .env in app directories or uses environment defaults.
    Resolves Secret Manager references (projects/*/secrets/*) to actual values.
    """
    # Find .env file in app directories
    current_dir = Path(__file__).resolve()

    # Try app/simple_company_chatbot/.env
    simple_chatbot_env = (
        current_dir.parent.parent.parent.parent.parent
        / "simple_company_chatbot"
        / ".env"
    )

    env_file = None
    if simple_chatbot_env.exists():
        env_file = simple_chatbot_env

    if env_file:
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
    else:
        print("No .env file found, using existing environment variables")

    # Set project ID if not already set
    if not os.getenv("GOOGLE_CLOUD_PROJECT_ID"):
        os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-dev"
        print("Set GOOGLE_CLOUD_PROJECT_ID=ken-e-dev")

    # Resolve Secret Manager references
    wandb_key = os.getenv("WANDB_API_KEY")
    if wandb_key and wandb_key.startswith("projects/"):
        print("Fetching WANDB_API_KEY from Secret Manager...")
        actual_key = _fetch_secret_from_gcp(wandb_key)
        if actual_key:
            os.environ["WANDB_API_KEY"] = actual_key
            print("✓ WANDB_API_KEY loaded from Secret Manager")
        else:
            print("✗ Failed to load WANDB_API_KEY from Secret Manager")
