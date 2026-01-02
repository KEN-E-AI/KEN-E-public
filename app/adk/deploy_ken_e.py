#!/usr/bin/env python3
"""
Deployment script for KEN-E chat agent.
Deploys the frontend-facing agent for company news and analytics.

Usage:
    python deploy_ken_e.py --env dev
    python deploy_ken_e.py --env staging
    python deploy_ken_e.py --env prod
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add shared package to path for secret resolution
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from shared.secrets import get_env_or_secret
except ImportError:
    logger.warning("Could not import shared secrets utility, will copy .env as-is")
    get_env_or_secret = None

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


def update_secret_manager(secret_name: str, secret_value: str, project_id: str) -> bool:
    """Update a secret in Google Secret Manager with a new value.

    Args:
        secret_name: Name of the secret (without project path)
        secret_value: New value for the secret
        project_id: GCP project ID

    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()

        # Build the secret name
        secret_path = f"projects/{project_id}/secrets/{secret_name}"

        # Add a new version with the updated value
        parent = secret_path
        payload = secret_value.encode("UTF-8")

        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": payload},
            }
        )

        logger.info(f"✅ Updated secret {secret_name} in Secret Manager")
        logger.info(f"   New version: {response.name}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to update secret {secret_name}: {e}")
        return False


def process_env_file(source_path: Path, dest_path: Path) -> None:
    """Process .env file to resolve Secret Manager references.

    Args:
        source_path: Path to source .env file
        dest_path: Path to write processed .env file
    """
    if not get_env_or_secret:
        # If we can't import the secrets utility, just copy as-is
        shutil.copy2(source_path, dest_path)
        logger.warning("Copying .env file without processing Secret Manager references")
        return

    logger.info("Processing .env file to resolve Secret Manager references")
    processed_lines = []

    with open(source_path) as f:
        for line in f:
            # Skip comments and empty lines
            if line.strip().startswith("#") or not line.strip():
                processed_lines.append(line)
                continue

            # Parse key=value pairs
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Check if this value needs Secret Manager resolution
                if value.startswith("sm://"):
                    try:
                        # Set env var temporarily to use get_env_or_secret
                        os.environ[key] = value
                        resolved_value = get_env_or_secret(key)
                        if resolved_value:
                            processed_lines.append(f"{key}={resolved_value}\n")
                            logger.info(f"Resolved Secret Manager reference for {key}")
                        else:
                            # Keep original if resolution failed
                            processed_lines.append(line)
                            logger.warning(
                                f"Failed to resolve Secret Manager reference for {key}"
                            )
                    except Exception as e:
                        logger.error(f"Error resolving {key}: {e}")
                        processed_lines.append(line)
                else:
                    # Keep non-secret values as-is
                    processed_lines.append(line)
            else:
                processed_lines.append(line)

    # Write processed .env file
    with open(dest_path, "w") as f:
        f.writelines(processed_lines)

    logger.info(f"Processed .env file written to {dest_path}")


def deploy_ken_e() -> str | None:
    """Deploy the KEN-E chat agent to Agent Engine."""

    # Save current directory
    original_dir = os.getcwd()

    # Create temporary deployment directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Created temporary directory: {temp_path}")

        # Copy the entire agents directory
        agents_src = Path("agents")
        if agents_src.exists():
            shutil.copytree(agents_src, temp_path / "agents")
            logger.info("Copied agents directory")
        else:
            logger.error("agents directory not found")
            return None

        # Create a proper agent.py that imports and exports the KEN-E agent
        agent_content = """
# This file makes the KEN-E agent available for deployment
from agents.ken_e_agent import ken_e_agent

# ADK looks for 'root_agent' or the agent name directly
root_agent = ken_e_agent

# Also export with the original name
__all__ = ['ken_e_agent', 'root_agent']
"""
        with open(temp_path / "agent.py", "w") as f:
            f.write(agent_content)
        logger.info("Created agent.py wrapper")

        # Create agent_engine_app.py that imports from agent.py
        app_content = """from vertexai.preview import reasoning_engines
from agent import root_agent

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True
)
"""
        with open(temp_path / "agent_engine_app.py", "w") as f:
            f.write(app_content)
        logger.info("Created agent_engine_app.py")

        # Copy requirements.txt
        if Path("requirements.txt").exists():
            shutil.copy2("requirements.txt", temp_path / "requirements.txt")
            logger.info("Copied requirements.txt")

        # Copy shared package (contains secrets utility and other shared code)
        shared_src = Path(__file__).parent.parent.parent / "shared"
        if shared_src.exists():
            shutil.copytree(shared_src, temp_path / "shared")
            logger.info("Copied shared package")
        else:
            logger.warning("⚠️  shared package not found")

        # Process environment-specific .env file (resolve sm:// references)
        env_mapping = {"dev": "development", "staging": "staging", "prod": "production"}
        env_name = env_mapping.get(os.getenv("_TARGET_ENV", "dev"), "dev")
        env_file = Path(f".env.{env_name}")

        if not env_file.exists():
            logger.warning(f"⚠️  {env_file} not found, trying .env")
            env_file = Path(".env")

        if env_file.exists():
            logger.info(f"Using {env_file} for {os.getenv('_TARGET_ENV', 'dev')} environment")
            process_env_file(env_file, temp_path / ".env")
            logger.info("Processed and copied .env file to root")
            # Also copy to agents directory for runtime loading
            process_env_file(env_file, temp_path / "agents" / ".env")
            logger.info("Copied .env file to agents/ directory for runtime loading")
        else:
            logger.error("❌ No .env file found")
            sys.exit(1)

        # Generate deployment name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"ken-e-chat-agent-{timestamp}"

        logger.info(f"Deploying as: {deployment_name}")

        # Change to temp directory for deployment
        os.chdir(temp_path)

        # Log the directory structure
        logger.info("Deployment directory structure:")
        for root, _dirs, files in os.walk("."):
            level = root.replace(".", "", 1).count(os.sep)
            indent = " " * 2 * level
            logger.info(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files[:10]:  # Limit to first 10 files per directory
                logger.info(f"{subindent}{file}")

        # Deploy using ADK CLI
        project_id = os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        staging_bucket = f"gs://{project_id}-adk-staging"

        cmd = [
            "uv",
            "run",
            "adk",
            "deploy",
            "agent_engine",
            "--project",
            project_id,
            "--region",
            location,
            "--staging_bucket",
            staging_bucket,
            "--display_name",
            deployment_name,
            "--description",
            "KEN-E chat agent for company news and analytics",
            "--trace_to_cloud",
            ".",  # Deploy from current directory
        ]

        logger.info(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
            )

            logger.info("Deployment stdout:")
            logger.info(result.stdout)

            if result.stderr:
                logger.info("Deployment stderr:")
                logger.info(result.stderr)

            # Try to extract engine ID or operation name
            # Look for operation pattern first
            operation_match = re.search(
                r"operations/(\d+)", result.stdout + (result.stderr or "")
            )

            if operation_match:
                operation_id = operation_match.group(0)
                logger.info(f"Deployment operation started: {operation_id}")

                # Try to get the operation status
                check_cmd = [
                    "gcloud",
                    "ai",
                    "operations",
                    "describe",
                    operation_id,
                    "--project",
                    project_id,
                    "--region",
                    location,
                ]

                logger.info(f"Checking operation status: {' '.join(check_cmd)}")
                check_result = subprocess.run(
                    check_cmd, capture_output=True, text=True, check=False
                )

                if check_result.stdout:
                    logger.info("Operation status:")
                    logger.info(check_result.stdout)

            # Look for engine ID
            engine_id_match = re.search(
                r"projects/\d+/locations/[^/]+/reasoningEngines/\d+", result.stdout
            )

            if engine_id_match:
                engine_id = engine_id_match.group()
                logger.info("✅ Deployment successful!")
                logger.info(f"Engine ID: {engine_id}")

                # Save deployment info
                deployment_info = f"""Deployment: {deployment_name}
Timestamp: {timestamp}
Engine ID: {engine_id}
Project: {project_id}
Location: {location}
"""

                # Write to deployment log in logs directory
                logs_dir = Path(original_dir) / "agents" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                log_file = logs_dir / "ken_e_deployment.txt"
                with open(log_file, "w") as f:
                    f.write(deployment_info)

                logger.info(f"Deployment info saved to: {log_file}")

                # Print instructions
                print("\n" + "=" * 60)
                print("🎉 KEN-E DEPLOYMENT SUCCESSFUL!")
                print("=" * 60)
                print(f"\nDeployment Name: {deployment_name}")
                print(f"Engine ID: {engine_id}")
                print("\n⚠️  Update your .env files with:")
                print(f"KEN_E_ENGINE_ID={engine_id}")

                # Update Secret Manager with the new engine ID
                print("\n📝 Updating Secret Manager...")
                # Get project number from environment (set in main)
                project_number = os.getenv("_PROJECT_NUMBER", "525657242938")
                secret_updated = update_secret_manager(
                    secret_name="ken-e-engine-id",
                    secret_value=engine_id,
                    project_id=project_number,
                )

                if secret_updated:
                    print("✅ Secret Manager updated with new engine ID")
                else:
                    print("⚠️  Failed to update Secret Manager - please update manually")

                print("=" * 60)

                return engine_id
            else:
                logger.warning(
                    "Deployment may have started but no engine ID found in output"
                )
                logger.info("Check the GCP console for deployment status")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment command failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
        finally:
            # Return to original directory
            os.chdir(original_dir)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Deploy KEN-E agent to Vertex AI")
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Target environment (dev, staging, or prod). Default: dev",
    )
    parser.add_argument(
        "--location",
        default="us-central1",
        help="Vertex AI location (default: us-central1)",
    )
    args = parser.parse_args()

    # Get configuration for target environment
    env_config = ENV_CONFIG[args.env]

    # Set environment variables from config
    os.environ["VERTEX_AI_PROJECT_ID"] = env_config["project_id"]
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = env_config["project_id"]
    os.environ["VERTEX_AI_LOCATION"] = args.location
    os.environ["_TARGET_ENV"] = args.env
    os.environ["_PROJECT_NUMBER"] = env_config["project_number"]

    logger.info("=" * 70)
    logger.info("Deploying KEN-E Chat Agent")
    logger.info(f"Environment: {args.env.upper()}")
    logger.info(f"Project: {env_config['project_id']} ({env_config['project_number']})")
    logger.info(f"Location: {args.location}")
    logger.info("=" * 70)

    result = deploy_ken_e()
    sys.exit(0 if result else 1)
