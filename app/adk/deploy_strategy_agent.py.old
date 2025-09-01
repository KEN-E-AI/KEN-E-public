#!/usr/bin/env python3
"""
Deploy the new strategy agent orchestrator to Agent Engine.
This replaces the old multi-agent supervisor v2.
"""

import os
import sys
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Deploy the strategy agent orchestrator to Agent Engine."""
    
    # Import the deployment module
    try:
        from agents.strategy_agent.deploy import deploy_to_agent_engine
    except ImportError:
        logger.error("Failed to import deployment module. Make sure you're in the app/adk directory")
        sys.exit(1)
    
    # Get environment
    environment = os.getenv("ENVIRONMENT", "development")
    
    logger.info(f"Deploying strategy agent orchestrator to {environment} environment")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Deploy the agent
        engine_id = deploy_to_agent_engine(environment)
        
        if engine_id:
            logger.info(f"✅ Successfully deployed strategy agent orchestrator")
            logger.info(f"Engine ID: {engine_id}")
            logger.info("\nIMPORTANT: Update your VERTEX_AI_AGENT_ENGINE_ID environment variable:")
            logger.info(f"export VERTEX_AI_AGENT_ENGINE_ID={engine_id}")
            
            # Also write to a file for easy reference
            with open("deployed_engine_id.txt", "w") as f:
                f.write(f"{engine_id}\n")
                f.write(f"Deployed at: {datetime.now().isoformat()}\n")
                f.write(f"Environment: {environment}\n")
            
            return 0
        else:
            logger.error("Deployment failed - no engine ID returned")
            return 1
            
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())