# Simple Company News Chatbot

A minimal ADK agent with Vertex AI Search integration - following official ADK patterns.

## What This Demonstrates

✅ **Proper ADK Usage**: Uses official ADK patterns from sample agents  
✅ **Minimal Code**: ~50 lines vs 400+ in the overengineered version  
✅ **Native Interactive Mode**: Built-in CLI and web interfaces  
✅ **First-Class Vertex AI Search**: No manual session management

## Setup

1. **Copy environment variables**:

   ```bash
   cp .env.example .env
   # Update .env with your actual Vertex AI Search IDs
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Run the agent**:

   ```bash
   # CLI interactive mode
   adk run .

   # Web interface
   adk web
   ```

## Usage

Ask questions like:

- "What's the latest Apple news?"
- "Tell me about recent Apple developments"
- "Apple stock updates"
- "Create a business strategy for our company"
- "Update our marketing strategy with new insights"

The agent will automatically:

1. Search your Vertex AI Search datastore
2. Analyze and synthesize results
3. Provide sourced responses with business insights
4. Create and manage strategy documents

## Agent Deployment

### Recommended: ADK CLI Deployment

Use the official ADK CLI for robust deployment:

```bash
# Deploy using ADK CLI (recommended)
uv run -- python -m google.adk.cli deploy agent_engine \
  --project=ken-e-dev \
  --region=us-central1 \
  --staging_bucket=gs://ken-e-dev-vertex-ai-staging \
  --display_name="multi-agent-supervisor-with-strategy" \
  --description="Multi-agent supervisor with company news, Google Analytics, and strategy capabilities" \
  .

# Or use the deployment script (uses ADK CLI internally)
uv run -- python deploy_agent.py deploy
```

### Alternative: Legacy Deployment Script

```bash
# List currently deployed agents
uv run -- python deploy_agent.py list

# Delete a specific agent
uv run -- python deploy_agent.py delete --name "projects/PROJECT/locations/LOCATION/reasoningEngines/ID"

# Deploy to a specific project
uv run -- python deploy_agent.py deploy --project ken-e-production --location us-central1
```

### Authentication Requirements

**For local development:**

```bash
gcloud auth application-default login
```

**For production deployments:**
Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your service account key file.

## Key Differences from Overengineered Version

| Overengineered            | Proper ADK              |
| ------------------------- | ----------------------- |
| 400+ lines                | ~50 lines               |
| Manual session management | ADK handles it          |
| Custom event processing   | ADK abstracts it        |
| Complex Runner setup      | `adk run .`             |
| Dispatcher pattern        | Direct tool integration |
| Custom invoke functions   | ADK built-in execution  |

## Architecture

```
Agent (agent.py)
├── Instruction (how to behave)
├── Tools (VertexAiSearchTool)
└── ADK handles everything else!
```

ADK provides:

- ✅ Interactive CLI mode
- ✅ Web interface
- ✅ Session management
- ✅ Tool execution
- ✅ Event handling
- ✅ Response streaming
