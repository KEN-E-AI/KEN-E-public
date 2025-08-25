#!/usr/bin/env python3
"""
Deploy supervisor with strategy agent modules properly included.
This ensures all dependencies are packaged correctly.
"""

import os
import sys
import shutil
import tempfile
import logging
from pathlib import Path
from vertexai.preview import reasoning_engines

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_deployment_package():
    """Create a deployment package with all necessary files."""
    
    # Create a temporary directory for the deployment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Creating deployment package in {temp_path}")
        
        # Copy main files
        files_to_copy = [
            "agent_standalone.py",
            "agent.py",
            "requirements.txt",
        ]
        
        for file in files_to_copy:
            src = Path(file)
            if src.exists():
                dst = temp_path / file
                shutil.copy2(src, dst)
                logger.info(f"Copied {file}")
        
        # Copy the entire agents directory with strategy_agent subdirectory
        agents_src = Path("agents")
        if agents_src.exists():
            agents_dst = temp_path / "agents"
            shutil.copytree(agents_src, agents_dst)
            logger.info(f"Copied agents directory with all subdirectories")
            
            # Verify strategy_agent files are included
            strategy_path = agents_dst / "strategy_agent"
            if strategy_path.exists():
                strategy_files = list(strategy_path.glob("*.py"))
                logger.info(f"Included {len(strategy_files)} strategy agent files:")
                for f in strategy_files:
                    logger.info(f"  - {f.name}")
        
        # Create the app module for deployment
        logger.info("Creating deployment app...")
        
        # Import the app from the copied files
        sys.path.insert(0, str(temp_path))
        from agent_standalone import app
        
        # Deploy using the reasoning engines API
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        
        logger.info(f"Deploying to project {project_id} in {location}")
        
        # Read requirements
        requirements_file = temp_path / "requirements.txt"
        requirements = []
        if requirements_file.exists():
            with open(requirements_file) as f:
                requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        # Add required packages for strategy agent
        strategy_requirements = [
            "google-cloud-firestore>=2.11.0",
            "google-cloud-aiplatform>=1.90.0",
            "weave>=0.51.0",
            "opentelemetry-sdk>=1.20.0",
            "pydantic>=2.0.0",
        ]
        
        for req in strategy_requirements:
            if not any(req.split(">=")[0] in r for r in requirements):
                requirements.append(req)
        
        logger.info(f"Requirements: {requirements}")
        
        # Deploy with all files included
        reasoning_engine = reasoning_engines.ReasoningEngine.create(
            app,
            requirements=requirements,
            display_name="supervisor-v3-with-strategy-complete",
            description="Multi-agent supervisor with complete strategy agent implementation",
            extra_packages=[str(temp_path)],  # Include the entire package directory
        )
        
        logger.info(f"✅ Deployment successful!")
        logger.info(f"🎯 Agent Engine ID: {reasoning_engine.name}")
        
        return reasoning_engine.name


def deploy_with_adk_cli_complete():
    """Deploy using ADK CLI with proper packaging."""
    import subprocess
    import shutil
    from datetime import datetime
    
    # Create a deployment directory with all files
    deploy_dir = Path("deployment_package")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    
    deploy_dir.mkdir()
    logger.info(f"Creating deployment package in {deploy_dir}")
    
    # Copy main files
    files = ["agent_standalone.py", "agent.py", "requirements.txt", "pyproject.toml"]
    for file in files:
        src = Path(file)
        if src.exists():
            shutil.copy2(src, deploy_dir / file)
            logger.info(f"Copied {file}")
    
    # Copy entire agents directory
    agents_src = Path("agents")
    agents_dst = deploy_dir / "agents"
    if agents_src.exists():
        shutil.copytree(agents_src, agents_dst)
        logger.info(f"Copied agents directory")
        
        # List strategy files to verify
        strategy_files = list((agents_dst / "strategy_agent").glob("*.py"))
        logger.info(f"Strategy agent files included: {len(strategy_files)}")
        for f in strategy_files:
            logger.info(f"  ✓ {f.name}")
    
    # Copy utils if exists
    utils_src = Path("utils")
    if utils_src.exists():
        utils_dst = deploy_dir / "utils"
        shutil.copytree(utils_src, utils_dst)
        logger.info(f"Copied utils directory")
    
    # Create __init__.py files if needed
    init_files = [
        deploy_dir / "__init__.py",
        deploy_dir / "agents" / "__init__.py",
        deploy_dir / "agents" / "strategy_agent" / "__init__.py",
    ]
    
    for init_file in init_files:
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.write_text("")
            logger.info(f"Created {init_file}")
    
    # Deploy from the package directory
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = f"gs://{project_id}-vertex-ai-staging"
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    display_name = f"supervisor-strategy-complete-{timestamp}"
    
    cmd = [
        sys.executable, "-m", "google.adk.cli", "deploy", "agent_engine",
        "--project", project_id,
        "--region", location,
        "--staging_bucket", staging_bucket,
        "--display_name", display_name,
        "--description", "Supervisor with complete strategy agent modules",
        str(deploy_dir)  # Deploy from the package directory
    ]
    
    logger.info(f"Running deployment command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(result.stdout)
        
        # Extract agent ID from output
        for line in result.stdout.split('\n'):
            if 'reasoningEngines/' in line:
                agent_id = line.strip()
                logger.info(f"✅ Deployment successful!")
                logger.info(f"🎯 Agent Engine ID: {agent_id}")
                print(f"\nVERTEX_AI_AGENT_ENGINE_ID={agent_id}")
                return agent_id
                
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        raise
    
    finally:
        # Clean up deployment directory
        if deploy_dir.exists():
            shutil.rmtree(deploy_dir)
            logger.info(f"Cleaned up {deploy_dir}")


if __name__ == "__main__":
    print("🚀 Starting deployment with complete strategy agent modules...")
    print("="*60)
    
    # Use ADK CLI deployment with proper packaging
    agent_id = deploy_with_adk_cli_complete()
    
    if agent_id:
        print("\n" + "="*60)
        print("✅ DEPLOYMENT COMPLETE!")
        print("="*60)
        print(f"\n📝 Update your .env files with:")
        print(f"VERTEX_AI_AGENT_ENGINE_ID={agent_id}")
        print("\n🎯 The supervisor now includes all strategy agent modules.")
        print("📦 All dependencies have been properly packaged.")
    else:
        print("\n❌ Deployment failed. Check logs for details.")
        sys.exit(1)