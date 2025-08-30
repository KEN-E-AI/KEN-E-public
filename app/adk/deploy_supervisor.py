#!/usr/bin/env python3
"""
Deploy the multi-agent supervisor v2 to Agent Engine.
This supervisor routes between Company News, Google Analytics, and Strategy agents.
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

def deploy_supervisor():
    """Deploy the multi-agent supervisor v2 to Agent Engine."""
    
    # Create temporary deployment directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Created temporary directory: {temp_path}")
        
        # Copy multi_agent_supervisor_v2.py as agent.py (required by ADK)
        supervisor_file = Path("agents/multi_agent_supervisor_v2.py")
        if not supervisor_file.exists():
            logger.error(f"Supervisor file not found: {supervisor_file}")
            return None
            
        shutil.copy2(supervisor_file, temp_path / "agent.py")
        logger.info("Copied multi_agent_supervisor_v2.py to agent.py")
        
        # Copy agent_engine_app.py
        app_file = Path("agents/agent_engine_app.py")
        if app_file.exists():
            shutil.copy2(app_file, temp_path / "agent_engine_app.py")
            logger.info("Copied agent_engine_app.py")
        else:
            # Create a minimal agent_engine_app.py if it doesn't exist
            app_content = """from vertexai.preview import reasoning_engines
from agents.multi_agent_supervisor_v2 import supervisor_agent_v2

app = reasoning_engines.AdkApp(
    agent=supervisor_agent_v2,
    enable_tracing=True
)
"""
            with open(temp_path / "agent_engine_app.py", "w") as f:
                f.write(app_content)
            logger.info("Created agent_engine_app.py")
        
        # Copy the entire agents directory (supervisor needs all sub-agents)
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
        deployment_name = f"multi-agent-supervisor-v2-{timestamp}"
        
        logger.info(f"Deploying as: {deployment_name}")
        
        # Change to temp directory for deployment
        os.chdir(temp_path)
        
        # Deploy using ADK CLI through uv
        # Create or use staging bucket
        project_id = os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev")
        staging_bucket = f"gs://{project_id}-adk-staging"
        
        cmd = [
            "uv", "run", "adk", "deploy", "agent_engine",
            "--project", project_id,
            "--region", os.getenv("VERTEX_AI_LOCATION", "us-central1"),
            "--staging_bucket", staging_bucket,
            "--display_name", deployment_name,
            "--description", "Multi-agent supervisor that routes between News, Analytics, and Strategy agents",
            "--trace_to_cloud",
            "."  # Current directory as agent path
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("Deployment output:")
            logger.info(result.stdout)
            
            # Extract the engine ID from output
            engine_id_match = re.search(
                r'projects/\d+/locations/[^/]+/reasoningEngines/\d+',
                result.stdout
            )
            
            if engine_id_match:
                engine_id = engine_id_match.group()
                logger.info(f"✅ Deployment successful!")
                logger.info(f"Engine ID: {engine_id}")
                
                # Save deployment info
                deployment_info = f"""Deployment: {deployment_name}
Timestamp: {timestamp}
Engine ID: {engine_id}

"""
                
                # Write to deployment log
                log_file = Path(__file__).parent / "supervisor_deployment.txt"
                with open(log_file, "w") as f:
                    f.write(deployment_info)
                
                logger.info(f"Deployment info saved to: {log_file}")
                
                # Print instructions for updating .env
                print("\n" + "="*60)
                print("🎉 DEPLOYMENT SUCCESSFUL!")
                print("="*60)
                print(f"\nDeployment Name: {deployment_name}")
                print(f"Engine ID: {engine_id}")
                print("\n⚠️  IMPORTANT: Update your .env files with the new engine ID:")
                print("\nFor api/.env and api/.env.development:")
                print(f"SUPERVISOR_ENHANCED_ENGINE_ID={engine_id}")
                print("\nFor app/adk/.env (if exists):")
                print(f"SUPERVISOR_ENGINE_ID={engine_id}")
                print("\n" + "="*60)
                
                return engine_id
            else:
                logger.error("Could not extract engine ID from deployment output")
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Deployment failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None


if __name__ == "__main__":
    # Change to the app/adk directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Run deployment
    engine_id = deploy_supervisor()
    
    if engine_id:
        sys.exit(0)
    else:
        sys.exit(1)