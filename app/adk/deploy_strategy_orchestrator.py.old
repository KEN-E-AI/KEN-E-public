#!/usr/bin/env python3
"""
Deploy the new strategy agent orchestrator to Vertex AI Agent Engine.
This replaces the old multi-agent supervisor v2 with the new orchestrator.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_deployment_package(temp_dir: Path) -> bool:
    """
    Create a deployment package with the strategy orchestrator.

    Args:
        temp_dir: Temporary directory for deployment files

    Returns:
        bool: True if package created successfully
    """
    try:
        # Copy the agents directory
        agents_src = Path("agents")
        if not agents_src.exists():
            logger.error(f"agents directory not found at {agents_src.absolute()}")
            return False

        shutil.copytree(agents_src, temp_dir / "agents")
        logger.info("Copied agents directory")

        # Create the main agent.py that imports the orchestrator
        agent_content = '''"""
Agent module for Vertex AI deployment.
This module imports and exposes the strategy orchestrator.
"""

import sys
import os
from pathlib import Path

# Add the agents directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the orchestrator
from agents.strategy_agent.orchestrator import app, strategy_agent

# Export for ADK
__all__ = ['app', 'strategy_agent']

# ADK looks for 'app' or 'root_agent'
root_agent = strategy_agent

print("✅ Strategy orchestrator loaded successfully")
'''

        agent_file = temp_dir / "agent.py"
        agent_file.write_text(agent_content)
        logger.info("Created agent.py wrapper")

        # Create requirements.txt with necessary dependencies
        requirements = [
            "google-cloud-aiplatform>=1.38.0",
            "google-cloud-storage>=2.10.0",
            "google-cloud-firestore>=2.11.0",
            "google-generativeai>=0.3.0",
            "pydantic>=2.0.0",
            "weave>=0.50.0",
            "wandb>=0.16.0",
        ]

        req_file = temp_dir / "requirements.txt"
        req_file.write_text("\n".join(requirements))
        logger.info("Created requirements.txt")

        # Create a simple test to verify imports
        test_content = '''"""Test that the agent can be imported."""
try:
    from agent import app, strategy_agent
    print("✅ Import test passed")
except Exception as e:
    print(f"❌ Import test failed: {e}")
    raise
'''

        test_file = temp_dir / "test_import.py"
        test_file.write_text(test_content)

        # Run the import test
        result = subprocess.run(
            [sys.executable, str(test_file)],
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Import test failed: {result.stderr}")
            return False

        logger.info("Import test passed")
        return True

    except Exception as e:
        logger.error(f"Failed to create deployment package: {e}")
        return False


def deploy_with_adk_cli(
    deployment_dir: Path, environment: str = "development"
) -> Optional[str]:
    """
    Deploy using ADK CLI.

    Args:
        deployment_dir: Directory containing the deployment package
        environment: Environment to deploy to

    Returns:
        Optional[str]: Engine ID if successful, None otherwise
    """
    # Get configuration from environment
    env_suffix = {"development": "dev", "staging": "staging", "production": "prod"}.get(
        environment, "dev"
    )

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", f"ken-e-{env_suffix}")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = f"gs://{project_id}-vertex-ai-staging"

    logger.info(f"Deploying to {environment} environment")
    logger.info(f"Project: {project_id}")
    logger.info(f"Location: {location}")
    logger.info(f"Staging bucket: {staging_bucket}")

    # Build the ADK command
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    display_name = f"strategy-orchestrator-{env_suffix}-{timestamp}"

    cmd = [
        sys.executable,
        "-m",
        "google.adk.cli",
        "deploy",
        "agent_engine",
        "--project",
        project_id,
        "--region",
        location,
        "--staging_bucket",
        staging_bucket,
        "--display_name",
        display_name,
        "--description",
        "Strategy Document Generation Orchestrator with artifact support",
        "--trace_to_cloud",
        str(deployment_dir),
    ]

    logger.info(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=str(deployment_dir)
        )

        # Extract engine ID from output
        engine_id = None
        for line in result.stdout.split("\n"):
            if "Resource name:" in line:
                # Extract the full resource name
                resource_name = line.split("Resource name:")[-1].strip()
                # Extract just the ID from the full path
                if "/reasoningEngines/" in resource_name:
                    engine_id = resource_name.split("/reasoningEngines/")[-1].strip()
                    break

        if engine_id:
            logger.info(f"✅ Deployment successful!")
            logger.info(f"Engine ID: {engine_id}")

            # Save deployment metadata
            metadata = {
                "engine_id": engine_id,
                "display_name": display_name,
                "environment": environment,
                "project_id": project_id,
                "location": location,
                "deployment_timestamp": datetime.utcnow().isoformat(),
                "deployment_method": "adk_cli",
            }

            metadata_file = f"strategy_orchestrator_deployment_{env_suffix}.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved metadata to {metadata_file}")

            return engine_id
        else:
            logger.error("Could not extract engine ID from deployment output")
            logger.error(f"Output: {result.stdout}")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        return None


def main() -> int:
    """Main deployment function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy strategy orchestrator to Vertex AI"
    )
    parser.add_argument(
        "--environment",
        choices=["development", "staging", "production"],
        default="development",
        help="Deployment environment",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Create package but don't deploy"
    )

    args = parser.parse_args()

    logger.info(f"Starting deployment for {args.environment} environment")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    # Save current directory
    original_dir = os.getcwd()

    # Create temporary directory for deployment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Created temporary directory: {temp_path}")

        # Create deployment package
        if not create_deployment_package(temp_path):
            logger.error("Failed to create deployment package")
            return 1

        logger.info("✅ Deployment package created successfully")

        if args.dry_run:
            logger.info("Dry run complete - skipping actual deployment")
            return 0

        # Deploy with ADK CLI
        engine_id = deploy_with_adk_cli(temp_path, args.environment)

        if engine_id:
            print("\n" + "=" * 60)
            print("🎉 DEPLOYMENT SUCCESSFUL!")
            print("=" * 60)
            print(f"Engine ID: {engine_id}")
            print(f"Environment: {args.environment}")
            print("\n📝 Next steps:")
            print("1. Update your .env file:")
            print(f"   VERTEX_AI_AGENT_ENGINE_ID={engine_id}")
            print("2. Restart your API server")
            print("3. Test account creation with file upload")
            print("=" * 60)
            return 0
        else:
            logger.error("Deployment failed")
            return 1


if __name__ == "__main__":
    sys.exit(main())
