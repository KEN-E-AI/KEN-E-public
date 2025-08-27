"""
Multi-Agent Company Chatbot - Combines News and Analytics
Following ADK best practices for multi-agent systems
"""

import os
import vertexai

# Import the supervisor agent that coordinates everything
from ..multi_agent_supervisor import supervisor_agent

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "ken-e-staging")
VERTEX_LOCATION = "us-central1"

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=VERTEX_LOCATION)

# Export the supervisor as the root agent for ADK
# This follows the ADK pattern where root_agent is what gets deployed
root_agent = supervisor_agent

# Also export with a more descriptive name
multi_capability_agent = supervisor_agent