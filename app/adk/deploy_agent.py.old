#!/usr/bin/env python3
"""
Universal Agent Deployment Script for KEN-E
Handles creation, updates, and management of Vertex AI Agent Engines
"""

import os
import json
import argparse
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from vertexai.preview import reasoning_engines
import vertexai
from google.cloud import storage

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AgentDeployer:
    """Reusable agent deployment and management utility."""
    
    def __init__(self, project_id: Optional[str] = None, location: Optional[str] = None):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        self.location = location or os.getenv("VERTEX_AI_LOCATION", "us-central1")
        # Use a bucket name that follows Google Cloud best practices for AI Platform
        self.staging_bucket = f"gs://{self.project_id}-vertex-ai-staging"
        
    def ensure_staging_bucket(self) -> bool:
        """Create staging bucket if it doesn't exist."""
        try:
            storage_client = storage.Client(project=self.project_id)
            bucket_name = self.staging_bucket.replace("gs://", "")
            
            try:
                storage_client.get_bucket(bucket_name)
                print(f"✅ Staging bucket {self.staging_bucket} exists")
                return True
            except Exception:
                print(f"📦 Creating staging bucket {self.staging_bucket}...")
                storage_client.create_bucket(bucket_name, location=self.location.lower())
                print(f"✅ Created staging bucket {self.staging_bucket}")
                return True
        except Exception as e:
            print(f"⚠️  Warning: Could not verify/create staging bucket: {e}")
            return False
    
    def initialize_vertex_ai(self):
        """Initialize Vertex AI with project and staging bucket."""
        print(f"🔧 Initializing Vertex AI:")
        print(f"   Project: {self.project_id}")
        print(f"   Location: {self.location}")
        print(f"   Staging bucket: {self.staging_bucket}")
        
        self.ensure_staging_bucket()
        vertexai.init(
            project=self.project_id, 
            location=self.location, 
            staging_bucket=self.staging_bucket
        )
    
    def deploy_agent(
        self,
        display_name: str,
        description: str,
        requirements: list,
        agent_module: str = "agent",
        save_metadata: bool = True
    ) -> reasoning_engines.ReasoningEngine:
        """Deploy a new agent or update existing one."""
        
        logger.info(f"Starting deployment of {display_name}")
        logger.info(f"Requirements: {requirements}")
        
        self.initialize_vertex_ai()
        
        # Import the agent
        logger.info(f"Importing agent from {agent_module}...")
        print(f"📦 Importing agent from {agent_module}...")
        if agent_module == "agent":
            from agent import app
        else:
            # Support for other agent modules
            module = __import__(agent_module)
            app = getattr(module, 'app')
        
        logger.info("Agent imported successfully")
        print("✅ Agent imported successfully")
        
        # Deploy the reasoning engine
        logger.info("Starting ReasoningEngine.create()...")
        print("🚀 Starting deployment...")
        
        try:
            reasoning_engine = reasoning_engines.ReasoningEngine.create(
                app,
                requirements=requirements,
                display_name=display_name,
                description=description,
            )
            
            logger.info(f"Deployment successful! Engine ID: {reasoning_engine.name}")
            print(f"✅ Deployment successful!")
            print(f"🎯 Engine ID: {reasoning_engine.name}")
            
            if save_metadata:
                self.save_deployment_metadata(reasoning_engine, display_name)
            
            return reasoning_engine
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            logger.error(f"Error type: {type(e)}")
            raise
    
    def save_deployment_metadata(
        self, 
        reasoning_engine: reasoning_engines.ReasoningEngine,
        display_name: str
    ):
        """Save deployment metadata to JSON file."""
        metadata = {
            "remote_agent_engine_id": reasoning_engine.name,
            "deployment_timestamp": datetime.utcnow().isoformat(),
            "project": self.project_id,
            "location": self.location,
            "display_name": display_name,
            "deployment_method": "reasoning_engines_api"
        }
        
        filename = f"deployment_metadata_{display_name.replace('-', '_')}.json"
        with open(filename, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Metadata saved to {filename}")
        print(f"📝 Update your .env with:")
        print(f"VERTEX_AI_AGENT_ENGINE_ID={reasoning_engine.name}")
    
    def list_agents(self):
        """List existing deployed agents."""
        self.initialize_vertex_ai()
        
        print("📋 Listing deployed reasoning engines...")
        try:
            engines = reasoning_engines.ReasoningEngine.list()
            if not engines:
                print("No reasoning engines found.")
                return
            
            for engine in engines:
                print(f"  🤖 {engine.display_name} ({engine.name})")
                print(f"     Created: {engine.create_time}")
                print(f"     Updated: {engine.update_time}")
                print()
        except Exception as e:
            print(f"❌ Error listing agents: {e}")
    
    def delete_agent(self, agent_name: str):
        """Delete a deployed agent."""
        self.initialize_vertex_ai()
        
        print(f"🗑️  Deleting reasoning engine: {agent_name}")
        try:
            engine = reasoning_engines.ReasoningEngine(agent_name)
            engine.delete()
            print(f"✅ Deleted reasoning engine: {agent_name}")
        except Exception as e:
            print(f"❌ Error deleting agent: {e}")


def deploy_strategy_supervisor_adk():
    """Deploy the strategy-enhanced supervisor agent using ADK CLI."""
    import subprocess
    import sys
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = f"gs://{project_id}-vertex-ai-staging"
    
    logger.info(f"Deploying using ADK CLI to project: {project_id}, location: {location}")
    
    cmd = [
        sys.executable, "-m", "google.adk.cli", "deploy", "agent_engine",
        "--project", project_id,
        "--region", location,
        "--staging_bucket", staging_bucket,
        "--display_name", "multi-agent-supervisor-with-strategy",
        "--description", "Multi-agent supervisor with company news, Google Analytics, and strategy capabilities",
        "."
    ]
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Extract agent engine ID from output
        for line in result.stdout.split('\n'):
            if 'Resource name:' in line:
                agent_engine_id = line.split('Resource name: ')[-1].strip()
                logger.info(f"Deployment successful! Agent Engine ID: {agent_engine_id}")
                
                # Save metadata
                metadata = {
                    "agent_engine_id": agent_engine_id,
                    "deployment_timestamp": datetime.utcnow().isoformat(),
                    "project": project_id,
                    "location": location,
                    "deployment_method": "adk_cli",
                    "display_name": "multi-agent-supervisor-with-strategy"
                }
                
                with open("adk_deployment_metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)
                
                print(f"✅ Deployment successful!")
                print(f"🎯 Agent Engine ID: {agent_engine_id}")
                print(f"📝 Update your .env with:")
                print(f"VERTEX_AI_AGENT_ENGINE_ID={agent_engine_id}")
                
                return agent_engine_id
        
        logger.error("Could not extract agent engine ID from output")
        print("❌ Could not extract agent engine ID")
        return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ADK deployment failed: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        print(f"❌ ADK deployment failed: {e}")
        return None

def deploy_strategy_supervisor():
    """Deploy the strategy-enhanced supervisor agent (legacy method)."""
    deployer = AgentDeployer()
    
    return deployer.deploy_agent(
        display_name="multi-agent-supervisor-with-strategy",
        description="Multi-agent supervisor with company news, Google Analytics, and strategy capabilities",
        requirements=[
            "google-adk",
            "newsapi-python>=0.2.7", 
            "pypdf2>=3.0.1",
            "python-dotenv",
            "requests>=2.32.4",
            "pydantic>=2.0",
            "google-cloud-discoveryengine",
            "google-cloud-aiplatform",
        ]
    )


def main():
    """Command-line interface for agent deployment."""
    parser = argparse.ArgumentParser(description="KEN-E Agent Deployment Tool")
    parser.add_argument("action", choices=["deploy", "list", "delete"], 
                       help="Action to perform")
    parser.add_argument("--name", help="Agent name for delete action")
    parser.add_argument("--project", help="Google Cloud project ID")
    parser.add_argument("--location", default="us-central1", help="Vertex AI location")
    
    args = parser.parse_args()
    
    try:
        deployer = AgentDeployer(project_id=args.project, location=args.location)
        
        if args.action == "deploy":
            # Use ADK CLI method by default
            engine = deploy_strategy_supervisor_adk()
            if engine:
                print("🎉 Deployment completed successfully!")
            else:
                print("❌ Deployment failed!")
        elif args.action == "list":
            deployer.list_agents()
        elif args.action == "delete":
            if not args.name:
                print("❌ --name is required for delete action")
                return
            deployer.delete_agent(args.name)
    
    except Exception as e:
        error_msg = str(e)
        if "Reauthentication is needed" in error_msg:
            print("\n❌ Authentication Error!")
            print("🔐 You need to authenticate with Google Cloud:")
            print("   Run: gcloud auth application-default login")
            print("   Then try the deployment again.")
            print()
            print("💡 For production deployments:")
            print("   Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            print("   to point to your service account key file.")
            return
        elif "doesn't have sufficient permission" in error_msg and "storage.objects.get" in error_msg:
            print("\n❌ Permissions Error!")
            print("🔐 The Vertex AI service account needs access to the staging bucket.")
            print()
            print("🛠️  To fix this, run:")
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
            print(f"   gcloud projects add-iam-policy-binding {project_id} \\")
            print("     --member=serviceAccount:service-391472102753@gcp-sa-aiplatform.iam.gserviceaccount.com \\")
            print("     --role=roles/storage.objectViewer")
            print()
            print("   Then retry the deployment.")
            return
        else:
            print(f"❌ Deployment failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()