#!/usr/bin/env python3
"""
Deployment script for KEN-E chat agent.
Deploys the frontend-facing agent for company news and analytics.
"""

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


def deploy_ken_e():
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

        # Copy .env file if exists
        env_file = Path(".env")
        if env_file.exists():
            shutil.copy2(env_file, temp_path / ".env")
            logger.info("Copied .env file")

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

                # Write to deployment log
                log_file = Path(original_dir) / "ken_e_deployment.txt"
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
    # Set environment variables if provided as arguments
    if len(sys.argv) > 1:
        import argparse

        parser = argparse.ArgumentParser(description="Deploy KEN-E agent to Vertex AI")
        parser.add_argument("--project", help="GCP project ID")
        parser.add_argument("--location", help="Vertex AI location")
        args = parser.parse_args()

        if args.project:
            os.environ["VERTEX_AI_PROJECT_ID"] = args.project
            os.environ["GOOGLE_CLOUD_PROJECT_ID"] = args.project
        if args.location:
            os.environ["VERTEX_AI_LOCATION"] = args.location

    result = deploy_ken_e()
    sys.exit(0 if result else 1)
