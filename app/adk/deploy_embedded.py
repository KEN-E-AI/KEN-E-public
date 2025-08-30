#!/usr/bin/env python3
"""
Deploy the embedded strategy agent version.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deploy_embedded_agent():
    """Deploy the embedded agent using ADK CLI."""
    import shutil
    import tempfile
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = f"gs://{project_id}-vertex-ai-staging"
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    display_name = f"supervisor-embedded-strategy-{timestamp}"
    
    # Create a temporary directory for deployment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Copy the embedded file as agent.py
        src_file = Path("agent_standalone_embedded.py")
        if not src_file.exists():
            logger.error(f"Agent file {src_file} not found!")
            return None
        
        dst_file = temp_path / "agent.py"
        shutil.copy2(src_file, dst_file)
        logger.info(f"Copied {src_file} to {dst_file}")
        
        # Copy requirements.txt if it exists
        req_file = Path("requirements.txt")
        if req_file.exists():
            shutil.copy2(req_file, temp_path / "requirements.txt")
            logger.info("Copied requirements.txt")
        
        cmd = [
            sys.executable, "-m", "google.adk.cli", "deploy", "agent_engine",
            "--project", project_id,
            "--region", location,
            "--staging_bucket", staging_bucket,
            "--display_name", display_name,
            "--description", "Supervisor with embedded strategy agents for reliable deployment",
            str(temp_path)  # Deploy the directory
        ]
        
        logger.info(f"Deploying embedded agent: {display_name}")
        logger.info(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(result.stdout)
            
            # Extract agent ID from output
            for line in result.stdout.split('\n'):
                if 'projects/' in line and 'reasoningEngines/' in line:
                    # Extract the full agent ID
                    import re
                    match = re.search(r'projects/\d+/locations/[\w-]+/reasoningEngines/\d+', line)
                    if match:
                        agent_id = match.group(0)
                        logger.info(f"✅ Deployment successful!")
                        logger.info(f"🎯 Agent Engine ID: {agent_id}")
                        return agent_id
                    
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            raise
        
        return None


if __name__ == "__main__":
    print("🚀 Deploying embedded strategy agent...")
    print("=" * 60)
    
    agent_id = deploy_embedded_agent()
    
    if agent_id:
        print("\n" + "=" * 60)
        print("✅ DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print(f"\n📝 Update your .env files with:")
        print(f"VERTEX_AI_AGENT_ENGINE_ID={agent_id}")
        print("\n🎯 This version has all strategy agent code embedded directly.")
        print("📦 No external dependencies on the agents directory.")
    else:
        print("\n❌ Deployment failed. Check logs for details.")
        sys.exit(1)