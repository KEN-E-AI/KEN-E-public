#!/usr/bin/env python3
"""
Deploy the strategy supervisor with proper package structure.
This ensures all modules are correctly packaged and importable.
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


def create_proper_package_structure():
    """
    Create a proper Python package structure for deployment.
    This ensures all imports work correctly in the deployed environment.
    """
    
    # Create a deployment directory
    deploy_dir = Path("deployment_package")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    
    deploy_dir.mkdir()
    logger.info(f"Creating deployment package in {deploy_dir}")
    
    # Create the main module as agent.py (expected by ADK CLI)
    shutil.copy2("strategy_supervisor.py", deploy_dir / "agent.py")
    logger.info("Copied strategy_supervisor.py as agent.py")
    
    # Copy ONLY the strategy_agent directory (not the entire agents directory)
    agents_dst = deploy_dir / "agents"
    agents_dst.mkdir()
    
    strategy_src = Path("agents/strategy_agent")
    strategy_dst = agents_dst / "strategy_agent"
    
    if strategy_src.exists():
        shutil.copytree(strategy_src, strategy_dst)
        logger.info(f"Copied strategy_agent directory")
        
        # Create clean __init__.py files (overwrite existing ones)
        init_files = [
            (agents_dst / "__init__.py", "# Agents package"),
            (strategy_dst / "__init__.py", "# Strategy agent package - no imports to avoid circular dependencies"),
        ]
        
        for init_file, content in init_files:
            init_file.write_text(content)
            logger.info(f"Created {init_file}")
        
        # List strategy files to verify
        strategy_dir = agents_dst / "strategy_agent"
        if strategy_dir.exists():
            strategy_files = list(strategy_dir.glob("*.py"))
            logger.info(f"Strategy agent files included: {len(strategy_files)}")
            for f in strategy_files:
                logger.info(f"  ✓ {f.name}")
    
    # Copy requirements.txt
    if Path("requirements.txt").exists():
        shutil.copy2("requirements.txt", deploy_dir / "requirements.txt")
        logger.info("Copied requirements.txt")
    else:
        # Create a requirements file with necessary packages
        requirements = [
            "google-cloud-aiplatform[adk,agent_engines]",
            "google-adk",
            "google-cloud-firestore>=2.11.0",
            "weave>=0.51.0",
            "wandb",
            "pydantic>=2.0.0",
        ]
        (deploy_dir / "requirements.txt").write_text("\n".join(requirements))
        logger.info("Created requirements.txt")
    
    # Create a proper __main__.py for the package
    main_content = """#!/usr/bin/env python3
from agent import app, strategy_supervisor, root_agent

# This makes the module executable
if __name__ == "__main__":
    print("Strategy Supervisor Module")
    print(f"Agent: {root_agent.name}")
"""
    (deploy_dir / "__main__.py").write_text(main_content)
    logger.info("Created __main__.py")
    
    # Create the root __init__.py
    (deploy_dir / "__init__.py").write_text("")
    logger.info("Created root __init__.py")
    
    # Create a setup file that sets W&B environment variables
    # This will be imported by the agent module
    wandb_api_key = os.getenv("WANDB_API_KEY", "")
    if wandb_api_key:
        setup_content = f"""# Auto-generated W&B configuration
import os
os.environ["WANDB_API_KEY"] = "{wandb_api_key}"
os.environ["WEAVE_PROJECT_NAME"] = "ken-e-strategy-agent"
"""
        (deploy_dir / "wandb_setup.py").write_text(setup_content)
        logger.info("Created wandb_setup.py with API key")
    
    return deploy_dir


def deploy_with_adk_cli(deploy_dir: Path):
    """
    Deploy using ADK CLI with the properly structured package.
    """
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = f"gs://{project_id}-vertex-ai-staging"
    
    # Get W&B API key from environment
    wandb_api_key = os.getenv("WANDB_API_KEY", "")
    if not wandb_api_key:
        logger.warning("WANDB_API_KEY not found in environment, W&B tracking will be disabled")
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    display_name = f"strategy-supervisor-{timestamp}"
    
    # Set environment variables for the deployment
    env = os.environ.copy()
    if wandb_api_key:
        env["WANDB_API_KEY"] = wandb_api_key
        env["WANDB_PROJECT"] = "ken-e-strategy-agent"
    
    # Use uv run to ensure we have the right environment
    cmd = [
        "uv", "run", "--", "python", "-m", "google.adk.cli", "deploy", "agent_engine",
        "--project", project_id,
        "--region", location,
        "--staging_bucket", staging_bucket,
        "--display_name", display_name,
        "--description", "Strategy generation supervisor with W&B tracking and tracing enabled",
        str(deploy_dir)
    ]
    
    logger.info(f"Running deployment command: {' '.join(cmd)}")
    if wandb_api_key:
        logger.info("W&B API key will be passed to deployment")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        logger.info(result.stdout)
        
        # Extract agent ID from output
        for line in result.stdout.split('\n'):
            if 'reasoningEngines/' in line:
                # Parse the agent ID from various possible output formats
                if 'Resource name:' in line:
                    agent_id = line.split('Resource name: ')[-1].strip()
                elif 'projects/' in line and 'reasoningEngines/' in line:
                    # Extract the full resource name
                    import re
                    match = re.search(r'projects/\d+/locations/[\w-]+/reasoningEngines/\d+', line)
                    if match:
                        agent_id = match.group()
                    else:
                        agent_id = line.strip()
                else:
                    agent_id = line.strip()
                    
                if agent_id and 'reasoningEngines/' in agent_id:
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


def main():
    """Main deployment function."""
    print("🚀 Starting Strategy Supervisor deployment...")
    print("=" * 60)
    
    # Create proper package structure
    deploy_dir = create_proper_package_structure()
    
    print("\n📦 Package structure created. Contents:")
    for item in deploy_dir.rglob("*"):
        if item.is_file():
            relative_path = item.relative_to(deploy_dir)
            print(f"  {relative_path}")
    
    print("\n🚀 Deploying to Agent Engine...")
    
    # Deploy with ADK CLI
    agent_id = deploy_with_adk_cli(deploy_dir)
    
    if agent_id:
        print("\n" + "=" * 60)
        print("✅ DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print(f"\n📝 Update your .env files with:")
        print(f"VERTEX_AI_AGENT_ENGINE_ID={agent_id}")
        print("\n🎯 The strategy supervisor is now deployed with proper module structure.")
    else:
        print("\n❌ Deployment failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()