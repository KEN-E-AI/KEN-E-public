#!/usr/bin/env python3
"""
Deploy the standalone agent to Agent Engine.
"""

import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deploy_standalone():
    """Deploy the standalone agent to Agent Engine."""
    
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
        deployment_name = f"supervisor-strategy-complete-{timestamp}"
        
        logger.info(f"Deploying agent: {deployment_name}")
        
        # Deploy using ADK CLI
        cmd = [
            sys.executable, "-m", "google.adk.cli", "deploy", "agent_engine",
            "--project", "ken-e-dev",
            "--region", "us-central1",
            "--staging_bucket", "gs://ken-e-dev-vertex-ai-staging",
            "--display_name", deployment_name,
            "--description", "Supervisor with fixed W&B and response handling",
            str(temp_path)
        ]
        
        logger.info(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Deployment successful!")
            logger.info(result.stdout)
            
            # Extract engine ID from output
            for line in result.stdout.split('\n'):
                if 'reasoningEngines/' in line:
                    engine_id = line.strip()
                    if 'projects/' in engine_id:
                        logger.info(f"\n✅ New Engine ID: {engine_id}")
                        logger.info("\nUpdate your .env file with:")
                        logger.info(f"VERTEX_AI_AGENT_ENGINE_ID={engine_id}")
                        break
        else:
            logger.error(f"Deployment failed: {result.stderr}")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(deploy_standalone())