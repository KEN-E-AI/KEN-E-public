"""
Google Analytics Agent V4 - OAuth Integration
Uses OAuth credentials to interact with the GA MCP server via JSON-RPC
"""

import os
import json
import base64
import logging
from typing import Dict, Any, List, Optional
import httpx
from google.adk.agents import Agent

logger = logging.getLogger(__name__)

# Lazy initialization of Weave for tracing
WEAVE_ENABLED = False
_weave_initialized = False

def init_weave_if_needed():
    """Initialize Weave lazily with proper error handling."""
    global WEAVE_ENABLED, _weave_initialized
    
    if _weave_initialized:
        return
    
    _weave_initialized = True
    
    try:
        import weave as weave_module
        # Only initialize if WANDB_API_KEY is available
        if os.getenv("WANDB_API_KEY"):
            weave_module.init(project_name="ken-e-ga-agent")
            logger.info("W&B Weave initialized for GA agent")
            WEAVE_ENABLED = True
            # Make weave available globally
            globals()['weave'] = weave_module
        else:
            logger.info("WANDB_API_KEY not set, Weave tracing disabled for GA agent")
            raise ImportError("WANDB_API_KEY not available")
    except Exception as e:
        logger.warning(f"Weave not available or failed to initialize for GA agent: {e}")
        WEAVE_ENABLED = False
        
        # Create dummy decorator if Weave is not available
        def weave_op(func):
            return func
        
        class DummyWeave:
            @staticmethod
            def op():
                return weave_op
        
        globals()['weave'] = DummyWeave()

# Create a placeholder for weave that will be replaced on first use
class LazyWeave:
    @staticmethod
    def op():
        init_weave_if_needed()
        return weave.op()

weave = LazyWeave()

# Configuration - reads from environment (set in .env files)
# These are optional - GA agent won't work without them but won't break deployment
GA_MCP_SERVER_URL = os.getenv("GA_MCP_SERVER_URL", "")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")


class GAMCPClient:
    """Custom client for GA MCP server using JSON-RPC"""

    def __init__(self, server_url: str = GA_MCP_SERVER_URL):
        self.server_url = server_url
        self._request_id = 0

    def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a synchronous JSON-RPC request"""
        self._request_id += 1

        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }

        headers = {"Content-Type": "application/json"}
        if MCP_API_KEY:
            headers["X-API-Key"] = MCP_API_KEY

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                self.server_url,
                json=request_data,
                headers=headers,
            )

            if response.status_code != 200:
                raise Exception(f"HTTP error {response.status_code}: {response.text}")

            result = response.json()
            if "error" in result:
                raise Exception(f"JSON-RPC Error: {result['error']}")

            return result.get("result", {})


# Create a global client instance
ga_client = GAMCPClient()


# Tool functions
@weave.op()
def list_ga_accounts(tenant_id: str, tenant_credentials: str) -> str:
    """
    List Google Analytics accounts for a tenant.

    Args:
        tenant_id: Organization/tenant identifier
        tenant_credentials: Base64 encoded JSON containing OAuth tokens (access_token, refresh_token)

    Returns:
        Formatted list of GA accounts and properties
    """
    try:
        result = ga_client._make_request(
            "get_account_summaries_mt",
            {"tenant_id": tenant_id, "tenant_credentials": tenant_credentials},
        )

        # Format the response
        output = f"Google Analytics Accounts (Organization: {tenant_id}):\n\n"

        # Result is a list directly
        if isinstance(result, list) and len(result) > 0:
            for account in result:
                output += f"📊 Account: {account.get('display_name', 'Unknown')}\n"
                output += f"   ID: {account.get('name', '')}\n"

                if "property_summaries" in account:
                    for prop in account["property_summaries"]:
                        output += (
                            f"   📈 Property: {prop.get('display_name', 'Unknown')}\n"
                        )
                        output += f"      ID: {prop.get('property', '')}\n"

                output += "\n"
        else:
            output += "No accounts found or access denied."

        return output
    except Exception as e:
        return f"Error accessing Google Analytics: {str(e)}"


def get_ga_property_details(
    tenant_id: str, tenant_credentials: str, property_id: str
) -> str:
    """
    Get details for a specific GA4 property.

    Args:
        tenant_id: Organization/tenant identifier
        tenant_credentials: Base64 encoded JSON containing OAuth tokens (access_token, refresh_token)
        property_id: GA4 property ID (e.g., properties/123456789)

    Returns:
        Formatted property details
    """
    try:
        result = ga_client._make_request(
            "get_property_details_mt",
            {
                "tenant_id": tenant_id,
                "tenant_credentials": tenant_credentials,
                "property_id": property_id,
            },
        )

        # Format property details
        output = f"Google Analytics Property Details (Organization: {tenant_id}):\n\n"
        output += f"📊 Name: {result.get('display_name', 'Unknown')}\n"
        output += f"📍 Property ID: {result.get('name', property_id)}\n"
        output += f"🕐 Time Zone: {result.get('time_zone', 'Unknown')}\n"
        output += f"💱 Currency: {result.get('currency_code', 'Unknown')}\n"
        output += f"🏭 Industry: {result.get('industry_category', 'Unknown')}\n"
        output += f"📅 Created: {result.get('create_time', 'Unknown')}\n"

        return output
    except Exception as e:
        return f"Error getting property details: {str(e)}"


def run_ga_report(
    tenant_id: str,
    tenant_credentials: str,
    property_id: str,
    date_ranges: List[Dict[str, str]],
    metrics: List[str],
    dimensions: Optional[List[str]] = None,
    dimension_filter: Optional[Dict[str, Any]] = None,
    order_bys: Optional[List[Dict[str, Any]]] = None,
    limit: int = 100,
) -> str:
    """
    Run a Google Analytics report.

    Args:
        tenant_id: Organization/tenant identifier
        tenant_credentials: Base64 encoded service account JSON
        property_id: GA4 property ID
        date_ranges: List of date range dicts with start_date and end_date
        metrics: List of metric names
        dimensions: Optional list of dimension names
        dimension_filter: Optional dimension filter
        order_bys: Optional list of order by clauses
        limit: Maximum number of rows to return

    Returns:
        Formatted report results
    """
    try:
        params = {
            "tenant_id": tenant_id,
            "tenant_credentials": tenant_credentials,
            "property_id": property_id,
            "date_ranges": date_ranges,
            "metrics": metrics,
            "limit": limit,
        }

        if dimensions:
            params["dimensions"] = dimensions
        if dimension_filter:
            params["dimension_filter"] = dimension_filter
        if order_bys:
            params["order_bys"] = order_bys

        result = ga_client._make_request("run_report_mt", params)

        # Format the report
        output = f"Google Analytics Report (Organization: {tenant_id}):\n"
        output += f"📊 Property: {property_id}\n"
        output += f"📅 Period: {date_ranges[0]['start_date']} to {date_ranges[0]['end_date']}\n\n"

        # Headers
        headers = (dimensions or []) + metrics
        output += " | ".join(headers) + "\n"
        output += "-" * (len(" | ".join(headers))) + "\n"

        # Data rows
        if "rows" in result:
            for row in result["rows"]:
                values = []

                if "dimension_values" in row:
                    values.extend(
                        [dv.get("value", "") for dv in row["dimension_values"]]
                    )

                if "metric_values" in row:
                    values.extend([mv.get("value", "") for mv in row["metric_values"]])

                output += " | ".join(values) + "\n"
        else:
            output += "No data available for the specified criteria.\n"

        return output
    except Exception as e:
        return f"Error running report: {str(e)}"


def run_ga_realtime_report(
    tenant_id: str,
    tenant_credentials: str,
    property_id: str,
    metrics: List[str],
    dimensions: Optional[List[str]] = None,
    dimension_filter: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> str:
    """
    Run a real-time Google Analytics report.

    Args:
        tenant_id: Organization/tenant identifier
        tenant_credentials: Base64 encoded service account JSON
        property_id: GA4 property ID
        metrics: List of metric names
        dimensions: Optional list of dimension names
        dimension_filter: Optional dimension filter
        limit: Maximum number of rows to return

    Returns:
        Formatted realtime report results
    """
    try:
        params = {
            "tenant_id": tenant_id,
            "tenant_credentials": tenant_credentials,
            "property_id": property_id,
            "metrics": metrics,
            "limit": limit,
        }

        if dimensions:
            params["dimensions"] = dimensions
        if dimension_filter:
            params["dimension_filter"] = dimension_filter

        result = ga_client._make_request("run_realtime_report_mt", params)

        # Format real-time results
        output = f"Real-Time Google Analytics (Organization: {tenant_id}):\n"
        output += f"📊 Property: {property_id}\n"
        output += f"🔴 Live data from last 30 minutes\n\n"

        # Headers
        headers = (dimensions or []) + metrics
        output += " | ".join(headers) + "\n"
        output += "-" * (len(" | ".join(headers))) + "\n"

        # Data rows
        if "rows" in result:
            for row in result["rows"]:
                values = []

                if "dimension_values" in row:
                    values.extend(
                        [dv.get("value", "") for dv in row["dimension_values"]]
                    )

                if "metric_values" in row:
                    values.extend([mv.get("value", "") for mv in row["metric_values"]])

                output += " | ".join(values) + "\n"
        else:
            output += "No active users in the last 30 minutes.\n"

        return output
    except Exception as e:
        return f"Error running realtime report: {str(e)}"


def create_google_analytics_agent():
    """Create a Google Analytics agent using OAuth authentication"""

    agent = Agent(
        name="google_analytics_agent_v4",
        model="gemini-2.0-flash",
        instruction="""You are a Google Analytics assistant that helps users analyze their website and app data using OAuth authentication.

**Your Capabilities:**
1. List Google Analytics accounts and properties
2. Get detailed property information
3. Run custom analytics reports
4. Access real-time user data

**Important: OAuth Authentication**
You will receive queries with OAuth credentials embedded:
- Look for TENANT_ID:<value> in the message
- Look for TENANT_CREDS:<value> in the message (contains OAuth tokens)
- Extract these values and use them in all tool calls

**Tool Usage:**

1. **list_ga_accounts** - List all GA accounts
   - Required: tenant_id, tenant_credentials
   - Use when: User asks to see their GA accounts or properties

2. **get_ga_property_details** - Get property configuration
   - Required: tenant_id, tenant_credentials, property_id
   - Use when: User asks about a specific property's settings

3. **run_ga_report** - Run analytics reports
   - Required: tenant_id, tenant_credentials, property_id, date_ranges, metrics
   - Optional: dimensions, filters, sorting
   - Common metrics: activeUsers, sessions, pageviews, bounceRate
   - Common dimensions: country, city, deviceCategory, pagePath

4. **run_ga_realtime_report** - Get live data
   - Required: tenant_id, tenant_credentials, property_id, metrics
   - Shows data from last 30 minutes
   - Common metrics: activeUsers, screenPageViews

**Best Practices:**
- Always extract tenant context first
- Suggest relevant metrics/dimensions based on the question
- Format data clearly in tables
- Provide insights along with raw data
- For date ranges, use formats like "7daysAgo", "yesterday", "today"

**Example Query Processing:**
User: "TENANT_ID:org-123 TENANT_CREDS:abc... Show me website traffic for last week"
1. Extract: tenant_id="org-123", tenant_credentials="abc..."
2. Ask for property_id if not provided
3. Run report with activeUsers, sessions for 7daysAgo to today""",
        tools=[
            list_ga_accounts,
            get_ga_property_details,
            run_ga_report,
            run_ga_realtime_report,
        ],
    )

    return agent


# Export the agent
google_analytics_agent_v4 = create_google_analytics_agent()
