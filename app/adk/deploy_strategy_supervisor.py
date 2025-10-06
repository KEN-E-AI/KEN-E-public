#!/usr/bin/env python3
"""
Deployment script for Strategy Documents Supervisor.
Deploys the backend agent for strategy generation during account creation.
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

# Add API source to path to access the secrets utility
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "api" / "src"))

try:
    from kene_api.utils.secrets import get_env_or_secret
except ImportError:
    logger.warning("Could not import secrets utility, will copy .env as-is")
    get_env_or_secret = None


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
    
    with open(source_path, 'r') as f:
        for line in f:
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                processed_lines.append(line)
                continue
            
            # Parse key=value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Check if this value needs Secret Manager resolution
                if value.startswith('sm://'):
                    try:
                        # Set the environment variable temporarily to use get_env_or_secret
                        os.environ[key] = value
                        resolved_value = get_env_or_secret(key)
                        if resolved_value:
                            processed_lines.append(f"{key}={resolved_value}\n")
                            logger.info(f"Resolved Secret Manager reference for {key}")
                        else:
                            # Keep original if resolution failed
                            processed_lines.append(line)
                            logger.warning(f"Failed to resolve Secret Manager reference for {key}")
                    except Exception as e:
                        logger.error(f"Error resolving {key}: {e}")
                        processed_lines.append(line)
                else:
                    # Keep non-secret values as-is
                    processed_lines.append(line)
            else:
                processed_lines.append(line)
    
    # Write processed .env file
    with open(dest_path, 'w') as f:
        f.writelines(processed_lines)
    
    logger.info(f"Processed .env file written to {dest_path}")


def deploy_strategy_supervisor() -> Optional[str]:
    """Deploy the Strategy Documents Supervisor to Agent Engine."""

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

        # Create a proper agent.py that imports and exports the supervisor
        agent_content = """
# This file makes the strategy supervisor agent available for deployment
import logging
import sys
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.info("Loading agent.py for deployment")

# Add current directory to Python path to help with imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor
    logger.info("Successfully imported create_strategy_docs_supervisor")
except ImportError as e:
    logger.error(f"Failed to import create_strategy_docs_supervisor: {e}")
    logger.error(f"Current directory: {os.getcwd()}")
    logger.error(f"Directory contents: {os.listdir('.')}")
    logger.error(f"Python path: {sys.path}")
    if os.path.exists('agents'):
        logger.error(f"agents/ directory contents: {os.listdir('agents')}")
    raise

# ADK looks for 'root_agent' or the agent name directly
root_agent = create_strategy_docs_supervisor
logger.info(f"root_agent type: {type(root_agent)}")

# Also export with the original name
__all__ = ['create_strategy_docs_supervisor', 'root_agent']
"""
        with open(temp_path / "agent.py", "w") as f:
            f.write(agent_content)
        logger.info("Created agent.py wrapper with debug logging")

        # Create agent_engine_app.py that imports from agent.py
        app_content = """import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.info("Loading agent_engine_app.py")

try:
    from vertexai.preview import reasoning_engines
    logger.info("Successfully imported reasoning_engines")
except Exception as e:
    logger.error(f"Failed to import reasoning_engines: {e}")
    raise

try:
    from agent import root_agent
    logger.info(f"Successfully imported root_agent, type: {type(root_agent)}")
except Exception as e:
    logger.error(f"Failed to import root_agent: {e}")
    raise

logger.info("Creating AdkApp...")
try:
    app = reasoning_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True
    )
    logger.info(f"Successfully created AdkApp: {type(app)}")
except Exception as e:
    logger.error(f"Failed to create AdkApp: {e}")
    logger.error(f"Error type: {type(e).__name__}")
    logger.error(f"Error args: {e.args}")
    raise

logger.info("agent_engine_app.py loaded successfully")
"""
        with open(temp_path / "agent_engine_app.py", "w") as f:
            f.write(app_content)
        logger.info("Created agent_engine_app.py with debug logging")

        # Copy requirements.txt
        if Path("requirements.txt").exists():
            shutil.copy2("requirements.txt", temp_path / "requirements.txt")
            logger.info("Copied requirements.txt")

        # Process .env file if exists (resolve Secret Manager references)
        env_file = Path(".env")
        if env_file.exists():
            process_env_file(env_file, temp_path / ".env")
            logger.info("Processed .env file with Secret Manager resolution")

        # Generate deployment name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"strategy-docs-supervisor-{timestamp}"

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
            "Strategy documents supervisor for account creation",
            "--agent_engine_config_file",
            ".agent_engine_config.json",  # THIS ACTUALLY USES THE CONFIG FILE
            "--trace_to_cloud",
            ".",  # Deploy from current directory
        ]
        # Note: Resource configuration and sys_version specified in .agent_engine_config.json

        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Command working directory: {os.getcwd()}")
        logger.info(f"Environment PROJECT_ID: {os.getenv('VERTEX_AI_PROJECT_ID')}")
        logger.info(f"Environment LOCATION: {os.getenv('VERTEX_AI_LOCATION')}")

        try:
            logger.info("Starting subprocess.run()...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
            )
            logger.info(f"subprocess.run() completed with return code: {result.returncode}")

            logger.info("Deployment stdout:")
            logger.info(result.stdout)

            if result.stderr:
                logger.info("Deployment stderr:")
                logger.info(result.stderr)

            # Check if the error is in stdout (some errors go there)
            if "ModuleAgent.__init__() got an unexpected keyword argument" in result.stdout:
                logger.error("ERROR: ModuleAgent initialization failed - found in stdout")
            if result.stderr and "ModuleAgent.__init__() got an unexpected keyword argument" in result.stderr:
                logger.error("ERROR: ModuleAgent initialization failed - found in stderr")

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
                log_file = logs_dir / "strategy_supervisor_deployment.txt"
                with open(log_file, "w") as f:
                    f.write(deployment_info)

                logger.info(f"Deployment info saved to: {log_file}")

                # Print instructions
                print("\n" + "=" * 60)
                print("🎉 STRATEGY SUPERVISOR DEPLOYMENT SUCCESSFUL!")
                print("=" * 60)
                print(f"\nDeployment Name: {deployment_name}")
                print(f"Engine ID: {engine_id}")
                
                # Update Secret Manager with the new engine ID
                print("\n📝 Updating Secret Manager...")
                secret_updated = update_secret_manager(
                    secret_name="strategy-supervisor-engine-id",
                    secret_value=engine_id,
                    project_id="525657242938"  # Using the project ID from the secrets
                )
                
                if secret_updated:
                    print("✅ Secret Manager updated with new engine ID")
                    print("\n📌 Your .env files should use the Secret Manager reference:")
                    print("   STRATEGY_SUPERVISOR_ENGINE_ID=sm://strategy-supervisor-engine-id")
                    print("\n   The actual engine ID is now stored in Secret Manager.")
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
    # Set environment variables if provided as arguments
    if len(sys.argv) > 1:
        import argparse

        parser = argparse.ArgumentParser(
            description="Deploy Strategy Supervisor to Vertex AI"
        )
        parser.add_argument("--project", help="GCP project ID")
        parser.add_argument("--location", help="Vertex AI location")
        args = parser.parse_args()

        if args.project:
            os.environ["VERTEX_AI_PROJECT_ID"] = args.project
            os.environ["GOOGLE_CLOUD_PROJECT_ID"] = args.project
        if args.location:
            os.environ["VERTEX_AI_LOCATION"] = args.location

    result = deploy_strategy_supervisor()
    sys.exit(0 if result else 1)
