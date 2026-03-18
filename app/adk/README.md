# KEN-E ADK Agent System

Multi-agent system built on [Google ADK](https://google.github.io/adk-docs/) for marketing analysis. KEN-E acts as a router agent, dispatching queries to specialized sub-agents for company news, Google Analytics, and strategy document generation.

## Architecture

```
KEN-E Router (agents/ken_e_agent.py)
├── CompanyNews Agent    — Vertex AI Search for news & company intelligence
├── GoogleAnalytics Agent — GA4 data via MCP (SSE transport + OAuth)
└── StrategyDocs Supervisor — Programmatic multi-doc generation (account creation)

Middleware (callbacks registered on the ADK Agent):
  before_tool → security/hooks.py   (OAuth permission check, token refresh)
  after_tool  → tracking/callbacks.py (usage tracking)
  before/after_agent → tracking/callbacks.py (Weave distributed tracing)
```

Agents are **lazy-loaded** via `agents/__init__.py` so only the requested agent initializes at runtime.

## Module Overview

| Directory | Purpose |
|-----------|---------|
| `agents/` | Agent definitions, dispatch handlers, strategy suite |
| `tools/` | Tool registry and discovery (schema, permissions, search) |
| `security/` | OAuth permission verification and pre-execution hooks |
| `session/` | Session recovery for returning users, timeout management |
| `mcp_config/` | YAML-based MCP server config with env var / Secret Manager substitution |
| `tracking/` | ADK callbacks for Weave tracing and usage analytics |

## Setup

1. **Configure environment** (see [root README](../../README.md#2-configure-environment) for unified switching):

   ```bash
   # From project root
   ./set-environment.sh development   # or: make env-dev
   ```

   Or configure agents only:

   ```bash
   cp .env.development .env   # or .env.staging, .env.production
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

3. **Run locally:**

   ```bash
   adk run .     # CLI interactive mode
   adk web       # Web interface
   ```

## Deployment

Deploy to Vertex AI Agent Engine using the Makefile targets:

```bash
make deploy-ken-e              # Development
make deploy-ken-e-staging      # Staging
make deploy-ken-e-production   # Production
```

Strategy supervisor (used during account creation):

```bash
make deploy          # Development
make deploy-staging  # Staging
make deploy-production # Production
```

Other useful targets: `make test-local`, `make test-deployed`, `make clean`.

## MCP Servers

Configured in `mcp_config/config/mcp_servers.yaml`. Currently enabled:

- **google_analytics_mcp** — GA4 queries via SSE with OAuth

Pending (disabled): HubSpot, Meta Ads, Google Ads, Slack, Notion.

## Authentication

- **Local dev:** `gcloud auth application-default login`
- **Production:** Set `GOOGLE_APPLICATION_CREDENTIALS` to your service account key file.
- **OAuth tokens** flow through ADK session state; the security hooks handle refresh automatically.
