#!/usr/bin/env python3
"""
Deploy strategy agents with Pydantic schemas to Agent Engine
"""
import os
import sys
import subprocess
import tempfile
import shutil
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Create a temporary directory for deployment
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Copy the agents directory
        agents_src = "agents"
        agents_dst = os.path.join(temp_dir, "agents")
        shutil.copytree(agents_src, agents_dst)
        logger.info("Copied agents directory")
        
        # Create the agent.py wrapper
        agent_py_content = """
from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor

# Create the agent that will be deployed
agent = create_strategy_docs_supervisor()
"""
        with open(os.path.join(temp_dir, "agent.py"), "w") as f:
            f.write(agent_py_content)
        logger.info("Created agent.py wrapper")
        
        # Create agent_engine_app.py
        app_content = """
from agent import agent

def agent_fn():
    return agent
"""
        with open(os.path.join(temp_dir, "agent_engine_app.py"), "w") as f:
            f.write(app_content)
        logger.info("Created agent_engine_app.py")
        
        # Copy requirements.txt
        if os.path.exists("requirements.txt"):
            shutil.copy("requirements.txt", os.path.join(temp_dir, "requirements.txt"))
            logger.info("Copied requirements.txt")
        
        # Copy .env if it exists
        if os.path.exists(".env"):
            shutil.copy(".env", os.path.join(temp_dir, ".env"))
            logger.info("Copied .env file")
        
        # Generate deployment name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"strategy-agents-pydantic-{timestamp}"
        
        logger.info(f"Deploying as: {deployment_name}")
        
        # List the files for debugging
        logger.info("Deployment directory structure:")
        for root, dirs, files in os.walk(temp_dir):
            level = root.replace(temp_dir, "").count(os.sep)
            indent = " " * 2 * level
            logger.info(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in files:
                logger.info(f"{subindent}{file}")
        
        # Run the deployment command
        cmd = [
            "uv", "run", "adk", "deploy", "agent_engine",
            "--project", "ken-e-dev",
            "--region", "us-central1", 
            "--staging_bucket", "gs://ken-e-dev-adk-staging",
            "--display_name", deployment_name,
            "--description", "Strategy agents with Pydantic schemas replacing Firestore best practices",
            "--trace_to_cloud", temp_dir  # Deploy from temp directory
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Run the deployment
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        logger.info("Deployment stdout:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.info("Deployment stderr:")
            logger.info(result.stderr)
        
        if result.returncode != 0:
            logger.error(f"Deployment failed with return code {result.returncode}")
            sys.exit(1)
        
        # Extract the engine ID from the output
        lines = result.stdout.split('\n')
        engine_id = None
        for line in lines:
            if "AgentEngine created. Resource name:" in line:
                engine_id = line.split("Resource name:")[-1].strip()
                break
        
        if not engine_id:
            logger.error("Could not extract engine ID from deployment output")
            sys.exit(1)
        
        logger.info(f"✅ Deployment successful!")
        logger.info(f"Engine ID: {engine_id}")
        
        # Save the deployment info
        with open("pydantic_deployment.txt", "w") as f:
            f.write(f"Deployment Name: {deployment_name}\n")
            f.write(f"Engine ID: {engine_id}\n")
            f.write(f"Timestamp: {timestamp}\n")
        
        logger.info(f"Deployment info saved to: pydantic_deployment.txt")
        
        print("\n" + "="*60)
        print("🎉 DEPLOYMENT SUCCESSFUL!")
        print("="*60)
        print(f"\nDeployment Name: {deployment_name}")
        print(f"Engine ID: {engine_id}")
        print(f"\n⚠️  Update your .env files with:")
        print(f"SUPERVISOR_ENHANCED_ENGINE_ID={engine_id}")
        print(f"CREATE_STRATEGY_DOCS_ENGINE_ID={engine_id}")
        print("="*60 + "\n")

if __name__ == "__main__":
    main()