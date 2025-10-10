#!/usr/bin/env python3
"""
Deploy strategy agent using Python API with sys_version="3.12".

This script:
1. Creates temp directory
2. Copies agents/ and requirements.txt
3. Processes .env to resolve sm:// references
4. Deploys from temp directory with Python 3.12
"""

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

# Add API source to path to access the secrets utility
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "api" / "src"))

try:
    from kene_api.utils.secrets import get_env_or_secret
except ImportError:
    logger.error("❌ Could not import secrets utility")
    sys.exit(1)

# Configuration
PROJECT_ID = "ken-e-dev"
PROJECT_NUMBER = "525657242938"
LOCATION = "us-central1"
STAGING_BUCKET = f"gs://{PROJECT_ID}-adk-staging"
PYTHON_VERSION = "3.12"


def process_env_file(source_path: Path, dest_path: Path) -> None:
    """Process .env file to resolve Secret Manager references.

    Args:
        source_path: Path to source .env file
        dest_path: Path to write processed .env file
    """
    logger.info("Processing .env file to resolve Secret Manager references...")
    processed_lines = []

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
                    processed_lines.append(f"{key}={resolved_value}\n")
                    if key == "WANDB_API_KEY":
                        logger.info("✅ WANDB_API_KEY resolved from Secret Manager")
                else:
                    processed_lines.append(line)
            else:
                processed_lines.append(line)

    with open(dest_path, "w") as f:
        f.writelines(processed_lines)

    logger.info(f"Processed .env written to {dest_path}")


# Save current directory
original_dir = os.getcwd()

logger.info("=" * 70)
logger.info(f"Deploying Strategy Agent with Python {PYTHON_VERSION}")
logger.info(f"Project: {PROJECT_ID} ({PROJECT_NUMBER}), Location: {LOCATION}")
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

    # Copy requirements.txt
    if Path("requirements.txt").exists():
        shutil.copy2("requirements.txt", temp_path / "requirements.txt")
        logger.info("Copied requirements.txt")

    # Process .env file (resolve sm:// references)
    env_file = Path(".env")
    if env_file.exists():
        process_env_file(env_file, temp_path / ".env")
        logger.info("Processed and copied .env file")
    else:
        logger.warning("⚠️  .env file not found")

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
            description=f"Strategy supervisor with Python {PYTHON_VERSION}, split agents, Neo4j, W&B",
            sys_version=PYTHON_VERSION,
            extra_packages=["agents"],
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

        # Update Secret Manager
        try:
            client = secretmanager.SecretManagerServiceClient()
            parent = f"projects/{PROJECT_ID}/secrets/strategy-supervisor-engine-id"
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
