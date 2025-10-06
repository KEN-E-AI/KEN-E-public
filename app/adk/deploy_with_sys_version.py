#!/usr/bin/env python3
"""
Deploy strategy agent using Python API with sys_version="3.12".

This bypasses the ADK CLI which doesn't support sys_version parameter.
Uses ReasoningEngine.create() Python API directly.
"""

import os
import sys
import logging
from pathlib import Path

import vertexai
from vertexai.preview import reasoning_engines
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - EXPLICITLY SET TO ken-e-dev
PROJECT_ID = "ken-e-dev"
PROJECT_NUMBER = "525657242938"  # Explicit project number for ken-e-dev
LOCATION = "us-central1"
STAGING_BUCKET = f"gs://{PROJECT_ID}-adk-staging"
PYTHON_VERSION = "3.12"

# Force correct project in environment
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["VERTEX_AI_PROJECT_ID"] = PROJECT_ID

logger.info(f"=" * 70)
logger.info(f"Deploying Strategy Agent with Python {PYTHON_VERSION}")
logger.info(f"Project: {PROJECT_ID} ({PROJECT_NUMBER}), Location: {LOCATION}")
logger.info(f"=" * 70)

# Initialize Vertex AI with explicit project
vertexai.init(
    project=PROJECT_ID,  # MUST be ken-e-dev
    location=LOCATION,
    staging_bucket=STAGING_BUCKET
)

# Verify project
import google.auth
credentials, project = google.auth.default()
logger.info(f"Using credentials for project: {project}")
if project != PROJECT_ID and project != PROJECT_NUMBER:
    logger.warning(f"⚠️  Credentials project {project} doesn't match {PROJECT_ID}!")

# Import the app from orchestrator
sys.path.insert(0, str(Path.cwd()))
from agents.strategy_agent.orchestrator import app

if app is None:
    logger.error("❌ Failed to import app from orchestrator")
    sys.exit(1)

logger.info(f"✅ Loaded app: {type(app)}")

# Deploy using Python API with sys_version parameter
logger.info(f"📦 Deploying to Agent Engine with sys_version='{PYTHON_VERSION}'...")

try:
    deployed_engine = reasoning_engines.ReasoningEngine.create(
        reasoning_engine=app,
        requirements="requirements.txt",
        display_name=f"strategy-supervisor-py{PYTHON_VERSION.replace('.', '')}",
        description=f"Strategy supervisor with Python {PYTHON_VERSION}, split agents, Neo4j",
        sys_version=PYTHON_VERSION,  # ⭐ THIS FORCES PYTHON 3.12
        extra_packages=["agents"],  # Include agents directory
    )

    logger.info(f"✅ Deployment successful!")
    logger.info(f"Engine ID: {deployed_engine.resource_name}")

    # Save to log file
    log_file = Path("agents/logs/strategy_supervisor_deployment.txt")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "w") as f:
        f.write(f"Deployment: strategy-supervisor-py{PYTHON_VERSION.replace('.', '')}\n")
        f.write(f"Python Version: {PYTHON_VERSION}\n")
        f.write(f"Engine ID: {deployed_engine.resource_name}\n")
        f.write(f"Project: {PROJECT_ID}\n")
        f.write(f"Location: {LOCATION}\n")

    # Update Secret Manager
    try:
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{PROJECT_ID}/secrets/strategy-supervisor-engine-id"
        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": deployed_engine.resource_name.encode("UTF-8")}
            }
        )
        logger.info(f"✅ Updated Secret Manager: {response.name}")
    except Exception as e:
        logger.warning(f"⚠️  Could not update Secret Manager: {e}")

    print("\n" + "="*70)
    print(f"🎉 DEPLOYMENT SUCCESSFUL WITH PYTHON {PYTHON_VERSION}!")
    print("="*70)
    print(f"Engine ID: {deployed_engine.resource_name}")
    print(f"Python Version: {PYTHON_VERSION}")
    print("="*70 + "\n")

except Exception as e:
    logger.error(f"❌ Deployment failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
