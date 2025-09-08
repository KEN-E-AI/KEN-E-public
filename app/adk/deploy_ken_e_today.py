#!/usr/bin/env python3
"""
Deployment script for KEN-E chat agent with forced new deployment.
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
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def deploy_ken_e(project: str = None, location: str = None) -> Optional[str]:
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
"""
        agent_file = temp_path / "agent.py"
        agent_file.write_text(agent_content.strip())
        logger.info("Created agent.py wrapper")

        # Create agent_engine_app.py with proper query wrapper
        app_content = """
from agents.ken_e_agent import ken_e_agent

# Export for Agent Engine
agent = ken_e_agent

def query(**kwargs):
    \"\"\"Agent Engine query endpoint.\"\"\"
    return agent.query(**kwargs)
"""
        app_file = temp_path / "agent_engine_app.py"
        app_file.write_text(app_content.strip())
        logger.info("Created agent_engine_app.py")

        # Copy requirements.txt
        req_src = Path("requirements.txt")
        if req_src.exists():
            shutil.copy(req_src, temp_path / "requirements.txt")
            logger.info("Copied requirements.txt")

        # Copy .env file
        env_src = Path(".env")
        if env_src.exists():
            shutil.copy(env_src, temp_path / ".env")
            logger.info("Copied .env file")

        # Change to deployment directory
        os.chdir(temp_path)

        # Generate unique deployment name with current timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"ken-e-chat-agent-{timestamp}"
        logger.info(f"Deploying as: {deployment_name}")

        # Log deployment directory structure
        logger.info("Deployment directory structure:")
        for root, dirs, files in os.walk("."):
            level = root.replace(".", "", 1).count(os.sep)
            indent = "  " * level
            logger.info(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for file in files:
                logger.info(f"{subindent}{file}")

        # Deploy using ADK CLI
        project_id = project or os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-staging")
        location = location or os.getenv("VERTEX_AI_LOCATION", "us-central1")
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
            "KEN-E chat agent for company news and analytics (updated)",
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

            # Try to extract engine ID
            engine_match = re.search(
                r"projects/\d+/locations/[^/]+/reasoningEngines/(\d+)",
                result.stdout + (result.stderr or ""),
            )

            if engine_match:
                engine_id = engine_match.group(0)
                logger.info(f"✅ Deployment successful!")
                logger.info(f"Engine ID: {engine_id}")

                # Save deployment info
                deployment_info_file = (
                    Path(original_dir) / "ken_e_deployment_today.txt"
                )
                with open(deployment_info_file, "w") as f:
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Engine ID: {engine_id}\n")
                    f.write(f"Deployment Name: {deployment_name}\n")

                logger.info(f"Deployment info saved to: {deployment_info_file}")
                return engine_id

            else:
                logger.error("Could not extract Engine ID from deployment output")
                logger.error("Full output:")
                logger.error(result.stdout)
                if result.stderr:
                    logger.error(result.stderr)
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed with error: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during deployment: {e}")
            return None
        finally:
            # Return to original directory
            os.chdir(original_dir)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Deploy KEN-E chat agent")
    parser.add_argument("--project", help="GCP project ID")
    parser.add_argument("--location", help="GCP location/region")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("🚀 DEPLOYING KEN-E CHAT AGENT")
    print("=" * 60)
    print()

    engine_id = deploy_ken_e(args.project, args.location)

    if engine_id:
        print()
        print("=" * 60)
        print("🎉 KEN-E DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        print()
        print(f"Engine ID: {engine_id}")
        print()
        print("⚠️  Update your .env files with:")
        print(f"KEN_E_ENGINE_ID={engine_id}")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ KEN-E DEPLOYMENT FAILED")
        print("=" * 60)
        print("Check the logs above for details")
        sys.exit(1)


if __name__ == "__main__":
    main()