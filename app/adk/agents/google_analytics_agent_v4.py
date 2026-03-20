"""Google Analytics Agent V4 - McpToolset + Header-Based OAuth.

Uses ADK McpToolset with SSE transport to connect to the GA MCP server.
OAuth credentials flow automatically from session state through the
header_provider callback to the GA MCP server's BearerAuthMiddleware.

Credential flow:
  session state (ga_credentials) -> ReadonlyContext.state -> header_provider
  -> HTTP headers (Authorization, X-Tenant-ID, X-Refresh-Token)
  -> BearerAuthMiddleware -> context vars -> tool functions
"""

import logging
import os
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams

logger = logging.getLogger(__name__)

# Load environment variables from .env file BEFORE reading any env vars
try:
    from dotenv import load_dotenv

    base_path = Path(__file__).resolve().parent

    possible_paths = [
        base_path.parent / ".env",
        base_path / ".env",
    ]

    env_loaded = False
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            logger.info(f"[GA-AGENT] Loaded env from {env_path}")
            env_loaded = True
            break

    if not env_loaded:
        logger.warning(
            f"[GA-AGENT] No .env file found. Checked: {[str(p) for p in possible_paths]}"
        )
except ImportError:
    logger.warning("[GA-AGENT] python-dotenv not available")
except Exception as e:
    logger.warning(f"[GA-AGENT] Failed to load .env: {e}")

from shared.secrets import get_env_or_secret  # noqa: E402

from .strategy_agent.config_loader import load_config_from_firestore  # noqa: E402

GA_MCP_SERVER_URL = get_env_or_secret("GA_MCP_SERVER_URL") or ""
if not GA_MCP_SERVER_URL:
    GA_MCP_SERVER_URL = os.getenv("GA_MCP_SERVER_URL", "")


def _ga_header_provider(context: ReadonlyContext) -> dict[str, str]:
    """Build auth headers from session state for GA MCP server.

    Reads ga_credentials from ADK context state and returns headers
    that the GA MCP server's BearerAuthMiddleware will extract.
    """
    ga_creds: dict[str, Any] = context.state.get("ga_credentials", {})
    headers: dict[str, str] = {}
    if token := ga_creds.get("access_token", ""):
        headers["Authorization"] = f"Bearer {token}"
    if tenant_id := ga_creds.get("tenant_id", ""):
        headers["X-Tenant-ID"] = tenant_id
    return headers


def _create_ga_toolset() -> McpToolset | None:
    """Create the GA MCP toolset if the server URL is configured."""
    if not GA_MCP_SERVER_URL:
        logger.warning("[GA-AGENT] GA_MCP_SERVER_URL not set, GA toolset unavailable")
        return None

    sse_url = GA_MCP_SERVER_URL
    if not sse_url.endswith("/mcp/sse"):
        sse_url = f"{sse_url.rstrip('/')}/mcp/sse"

    return McpToolset(
        connection_params=SseConnectionParams(url=sse_url, timeout=30.0),
        header_provider=_ga_header_provider,
    )


ga_toolset = _create_ga_toolset()

GA_AGENT_INSTRUCTION = """You are a Google Analytics assistant that helps users analyze their website and app data.

**Your Capabilities:**
1. List Google Analytics accounts and properties
2. Get detailed property information
3. Run custom analytics reports with dimensions, metrics, and filters
4. Access real-time user data (last 30 minutes)

**Authentication:**
OAuth credentials are handled automatically via headers. You do NOT need to pass tenant_id or tenant_credentials parameters - they are injected automatically.

**Available Tools (discovered dynamically from GA MCP server):**
- get_account_summaries_mt - List all GA accounts and properties
- run_report_mt - Run analytics reports with date ranges, metrics, dimensions, and filters
- run_realtime_report_mt - Get live data from last 30 minutes
- get_property_details_mt - Get GA4 property configuration details

**Tool Usage:**

1. **get_account_summaries_mt** - List all GA accounts
   - No required parameters (credentials are automatic)
   - Use when: User asks to see their GA accounts or properties

2. **get_property_details_mt** - Get property configuration
   - Required: property_id
   - Use when: User asks about a specific property's settings

3. **run_report_mt** - Run analytics reports
   - Required: property_id, date_ranges
   - Optional: metrics, dimensions, filters, sorting, limit
   - Common metrics: activeUsers, sessions, screenPageViews, bounceRate
   - Common dimensions: country, city, deviceCategory, pagePath

4. **run_realtime_report_mt** - Get live data
   - Required: property_id
   - Optional: metrics, dimensions
   - Shows data from last 30 minutes

**Best Practices:**
- If the user's property ID is available in the conversation context, use it directly
- Suggest relevant metrics/dimensions based on the question
- Format data clearly in tables when possible
- Provide insights along with raw data
- For date ranges, use formats like "7daysAgo", "yesterday", "today"
- If no property_id is available, first call get_account_summaries_mt to list properties

**Important:**
- NEVER ask for credentials or tokens - they are handled automatically
- If a property_id is provided in the context, use it without asking again"""


def create_google_analytics_agent(config_doc_id: str = "google_analytics_agent") -> Agent:
    """Create a Google Analytics agent using McpToolset with header-based OAuth.

    Args:
        config_doc_id: Firestore document ID for agent configuration
    """
    # Load configuration from Firestore with fallback to hardcoded values
    try:
        config, metadata = load_config_from_firestore(config_doc_id)
        model = config.model
        instruction = config.instruction or GA_AGENT_INSTRUCTION
        description = config.description or ""
        generate_content_config = config.generate_content_config
        logger.info(
            f"Loaded GA agent config from Firestore: {config_doc_id} "
            f"(version: {metadata.get('version', 'unknown')}, model: {model})"
        )
    except Exception as e:
        logger.warning(
            f"Failed to load GA agent config from Firestore ({config_doc_id}): {e}. "
            f"Falling back to hardcoded defaults"
        )
        model = "gemini-2.0-flash"
        instruction = GA_AGENT_INSTRUCTION
        description = ""
        generate_content_config = None

    tools = [ga_toolset] if ga_toolset else []

    agent = Agent(
        name="google_analytics_agent_v4",
        model=model,
        description=description,
        instruction=instruction,
        generate_content_config=generate_content_config,
        tools=tools,
    )

    return agent


google_analytics_agent_v4 = create_google_analytics_agent()
