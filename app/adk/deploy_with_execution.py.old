#!/usr/bin/env python3
"""
Deploy the standalone agent with actual strategy execution to Agent Engine.
"""

import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deploy_with_execution():
    """Deploy the standalone agent with strategy execution to Agent Engine."""
    
    # Create temporary deployment directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Created temporary directory: {temp_path}")
        
        # Copy create_strategy_docs.py as agent.py (required by ADK)
        shutil.copy2("create_strategy_docs.py", temp_path / "agent.py")
        logger.info("Copied create_strategy_docs.py to agent.py")
        
        # Copy the agents directory
        agents_src = Path("agents")
        if agents_src.exists():
            shutil.copytree(agents_src, temp_path / "agents")
            logger.info("Copied agents directory")
        
        # Copy requirements.txt
        shutil.copy2("requirements.txt", temp_path / "requirements.txt")
        logger.info("Copied requirements.txt")
        
        # Copy .env file to ensure environment variables are available
        env_file = Path(".env")
        if env_file.exists():
            shutil.copy2(env_file, temp_path / ".env")
            logger.info("Copied .env file")
        
        # Generate deployment name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"create-strategy-docs-{timestamp}"
        
        logger.info(f"Deploying agent: {deployment_name}")
        
        # Deploy using ADK CLI
        cmd = [
            sys.executable, "-m", "google.adk.cli", "deploy", "agent_engine",
            "--project", "ken-e-dev",
            "--region", "us-central1",
            "--staging_bucket", "gs://ken-e-dev-vertex-ai-staging",
            "--display_name", deployment_name,
            "--description", "Create Strategy Documents - Orchestrated execution of all 5 strategy agents",
            str(temp_path)
        ]
        
        logger.info(f"Command: {' '.join(cmd)}")
        
        # Run deployment and capture output
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Print all output for debugging
        print("\n=== DEPLOYMENT OUTPUT ===")
        print(result.stdout)
        if result.stderr:
            print("\n=== ERRORS ===")
            print(result.stderr)
        
        if result.returncode == 0:
            logger.info("Deployment command completed!")
            
            # Try multiple patterns to extract engine ID
            patterns = [
                r'Resource name: (projects/\d+/locations/[\w-]+/reasoningEngines/\d+)',
                r'(projects/\d+/locations/[\w-]+/reasoningEngines/\d+)',
                r'reasoningEngines/(\d+)'
            ]
            
            engine_id = None
            for pattern in patterns:
                match = re.search(pattern, result.stdout)
                if match:
                    if 'projects/' in match.group(0):
                        engine_id = match.group(0)
                    else:
                        # Construct full ID
                        engine_id = f"projects/525657242938/locations/us-central1/reasoningEngines/{match.group(1)}"
                    break
            
            if engine_id:
                logger.info(f"\n✅ New Engine ID: {engine_id}")
                logger.info("\nUpdate your .env files with:")
                logger.info(f"VERTEX_AI_AGENT_ENGINE_ID={engine_id}")
                
                # Also save to a file for easy reference
                with open("latest_deployment.txt", "w") as f:
                    f.write(f"Deployment: {deployment_name}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Engine ID: {engine_id}\n")
                logger.info("\nEngine ID also saved to latest_deployment.txt")
            else:
                logger.warning("Could not extract engine ID from output")
                logger.info("Check the Google Cloud Console for the deployment")
        else:
            logger.error(f"Deployment failed with return code: {result.returncode}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(deploy_with_execution())