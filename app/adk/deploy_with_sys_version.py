#!/usr/bin/env python3
"""
Deploy strategy agent using Python API with sys_version="3.12".

This script:
1. Creates temp directory
2. Copies agents/ and requirements.txt
3. Processes .env to resolve sm:// references
4. Deploys from temp directory with Python 3.12

Usage:
    python deploy_with_sys_version.py --env dev
    python deploy_with_sys_version.py --env staging
    python deploy_with_sys_version.py --env prod
"""

import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import vertexai
from google.cloud import secretmanager
from vertexai.preview import reasoning_engines

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add shared package to path for secret resolution
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from shared.secrets import get_env_or_secret
except ImportError:
    logger.error("❌ Could not import shared secrets utility")
    sys.exit(1)

# Default Configuration
PYTHON_VERSION = "3.12"
DEFAULT_LOCATION = "us-central1"

# Environment to GCP project mapping
ENV_CONFIG = {
    "dev": {
        "project_id": "ken-e-dev",
        "project_number": "525657242938",
    },
    "staging": {
        "project_id": "ken-e-staging",
        "project_number": "391472102753",
    },
    "prod": {
        "project_id": "ken-e-production",
        "project_number": "395770269870",
    },
}


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Deploy Strategy Supervisor to Vertex AI Agent Engine"
    )
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Target environment (dev, staging, or prod). Default: dev",
    )
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help=f"Vertex AI location (default: {DEFAULT_LOCATION})",
    )
    return parser.parse_args()


def process_env_file(source_path: Path, dest_path: Path) -> None:
    """Process .env file to resolve Secret Manager references.

    Args:
        source_path: Path to source .env file
        dest_path: Path to write processed .env file

    Raises:
        SystemExit: If critical secrets cannot be resolved
    """
    logger.info("Processing .env file to resolve Secret Manager references...")
    processed_lines = []

    # Critical secrets that MUST be resolved
    CRITICAL_SECRETS = [
        "NEO4J_URI",
        "NEO4J_PASSWORD",
        "WANDB_API_KEY",
        "OPENAI_API_KEY"
    ]

    failed_secrets = []

    with open(source_path) as f:
        for line in f:
            if line.strip().startswith("#") or not line.strip():
                processed_lines.append(line)
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Use get_env_or_secret which handles sm:// automatically
                os.environ[key] = value
                resolved_value = get_env_or_secret(key)

                if resolved_value:
                    # Debug: Show what we're resolving
                    if key in CRITICAL_SECRETS:
                        logger.info(f"✅ {key}: {value} → resolved (length: {len(resolved_value)})")
                    processed_lines.append(f"{key}={resolved_value}\n")
                else:
                    # Check if this is a critical secret
                    if key in CRITICAL_SECRETS:
                        logger.error(f"❌ CRITICAL: {key}: {value} → NOT resolved (got None)")
                        failed_secrets.append(key)
                    else:
                        logger.debug(f"⚠️ {key}: {value} → NOT resolved (got None)")
                    processed_lines.append(line)
            else:
                processed_lines.append(line)

    # Fail deployment if any critical secrets weren't resolved
    if failed_secrets:
        logger.error("=" * 70)
        logger.error("❌ DEPLOYMENT ABORTED: Critical secrets not resolved")
        logger.error(f"Failed secrets: {', '.join(failed_secrets)}")
        logger.error("=" * 70)
        logger.error("Possible causes:")
        logger.error("  1. GOOGLE_CLOUD_PROJECT not set in .env")
        logger.error("  2. Missing Secret Manager permissions")
        logger.error("  3. Secrets don't exist in Secret Manager")
        logger.error("  4. Not authenticated with gcloud")
        sys.exit(1)

    # Write with restrictive permissions (owner read/write only)
    # This minimizes the exposure window for plaintext secrets
    dest_path.touch(mode=0o600)
    with open(dest_path, "w") as f:
        f.writelines(processed_lines)

    logger.info(f"Processed .env written to {dest_path} with mode 0o600")


# Parse command-line arguments
args = parse_args()

# Get configuration for target environment
env_config = ENV_CONFIG[args.env]
PROJECT_ID = env_config["project_id"]
PROJECT_NUMBER = env_config["project_number"]
LOCATION = args.location
STAGING_BUCKET = f"gs://{PROJECT_ID}-adk-staging"

# Save current directory
original_dir = os.getcwd()

logger.info("=" * 70)
logger.info(f"Deploying Strategy Agent with Python {PYTHON_VERSION}")
logger.info(f"Environment: {args.env.upper()}")
logger.info(f"Project: {PROJECT_ID} ({PROJECT_NUMBER})")
logger.info(f"Location: {LOCATION}")
logger.info("=" * 70)

# Create temporary deployment directory
with tempfile.TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)
    logger.info(f"Created temporary directory: {temp_path}")

    # Copy agents directory
    agents_src = Path("agents")
    if agents_src.exists():
        shutil.copytree(agents_src, temp_path / "agents")
        logger.info("Copied agents directory")
    else:
        logger.error("❌ agents directory not found")
        sys.exit(1)

    # Copy shared package (contains secrets utility and other shared code)
    shared_src = Path(__file__).parent.parent.parent / "shared"
    if shared_src.exists():
        shutil.copytree(shared_src, temp_path / "shared")
        logger.info("Copied shared package")
    else:
        logger.warning("⚠️  shared package not found")

    # Copy requirements.txt
    if Path("requirements.txt").exists():
        shutil.copy2("requirements.txt", temp_path / "requirements.txt")
        logger.info("Copied requirements.txt")

    # Process environment-specific .env file (resolve sm:// references)
    # Use .env.{environment} file, fallback to .env
    env_mapping = {"dev": "development", "staging": "staging", "prod": "production"}
    env_name = env_mapping.get(args.env, args.env)
    env_file = Path(f".env.{env_name}")

    if not env_file.exists():
        logger.warning(f"⚠️  {env_file} not found, trying .env")
        env_file = Path(".env")

    if env_file.exists():
        logger.info(f"Using {env_file} for {args.env} environment")
        process_env_file(env_file, temp_path / ".env")
        logger.info("Processed and copied .env file to root")
        # Also copy to agents directory for runtime loading
        process_env_file(env_file, temp_path / "agents" / ".env")
        logger.info("Copied .env file to agents/ directory for runtime loading")
    else:
        logger.error("❌ No .env file found")
        sys.exit(1)

    # Change to temp directory for deployment
    os.chdir(temp_path)

    # Force correct project in environment
    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
    os.environ["VERTEX_AI_PROJECT_ID"] = PROJECT_ID

    # Initialize Vertex AI
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )

    # Import the app from orchestrator
    sys.path.insert(0, str(Path.cwd()))
    from agents.strategy_agent.orchestrator import app

    if app is None:
        logger.error("❌ Failed to import app from orchestrator")
        sys.exit(1)

    logger.info(f"✅ Loaded app: {type(app)}")

    # Deploy using Python API
    logger.info(f"📦 Deploying with sys_version='{PYTHON_VERSION}'...")

    try:
        deployed_engine = reasoning_engines.ReasoningEngine.create(
            reasoning_engine=app,
            requirements="requirements.txt",
            display_name=f"strategy-supervisor-py{PYTHON_VERSION.replace('.', '')}",
            description=(
                f"Strategy supervisor with Python {PYTHON_VERSION}, "
                "split agents, Neo4j, W&B"
            ),
            sys_version=PYTHON_VERSION,
            extra_packages=["agents", "shared"],
        )

        logger.info("✅ Deployment successful!")
        logger.info(f"Engine ID: {deployed_engine.resource_name}")

        # Save to log file (in original directory)
        log_file = Path(original_dir) / "agents/logs/strategy_supervisor_deployment.txt"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w") as f:
            f.write(
                f"Deployment: strategy-supervisor-py{PYTHON_VERSION.replace('.', '')}\n"
            )
            f.write(f"Python Version: {PYTHON_VERSION}\n")
            f.write(f"Engine ID: {deployed_engine.resource_name}\n")
            f.write(f"Project: {PROJECT_ID}\n")
            f.write(f"Location: {LOCATION}\n")

        # Update Secret Manager with new engine ID
        try:
            client = secretmanager.SecretManagerServiceClient()
            # Use project number (not ID) for Secret Manager
            parent = f"projects/{PROJECT_NUMBER}/secrets/strategy-supervisor-engine-id"
            response = client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": deployed_engine.resource_name.encode("UTF-8")},
                }
            )
            logger.info(f"✅ Updated Secret Manager: {response.name}")
        except Exception as e:
            logger.warning(f"⚠️  Could not update Secret Manager: {e}")

        print("\n" + "=" * 70)
        print(f"🎉 DEPLOYMENT SUCCESSFUL WITH PYTHON {PYTHON_VERSION}!")
        print("=" * 70)
        print(f"Engine ID: {deployed_engine.resource_name}")
        print(f"Python Version: {PYTHON_VERSION}")
        print("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        # Return to original directory
        os.chdir(original_dir)
