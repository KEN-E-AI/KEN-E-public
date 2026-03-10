# MCP Server Architecture

**Version:** 1.0
**Date:** March 2026
**Status:** Canonical — reflects decisions from Sprint 3b architecture review
**Canonical Source:** [Notion Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463)

---

## 1. Context

KEN-E needs to support ~400 tools across 20-40 MCP servers per account for marketing CMOs. This document captures verified architectural decisions based on ADK internals research, MCP ecosystem analysis, and platform-by-platform integration evaluation.

## 2. ADK Internals: Verified Behavior

We read the ADK source code (`mcp_toolset.py`, `mcp_session_manager.py`, `base_llm_flow.py`) and confirmed:

| Behavior | Detail |
|----------|--------|
| **Agent objects are singletons** | Reused across all requests per deployment |
| **`McpToolset.get_tools()` called every LLM turn** | Tools are re-resolved fresh, not cached across requests |
| **SSE connections pooled by header hash** | Same user reuses connection; different users get separate connections automatically |
| **Tool lists are always fresh** | If an MCP server adds/removes tools between turns, the agent picks it up on the next turn |

**Implication:** `McpToolset` works as-is. No custom toolset, wrapper, or MCP manager needed at the agent level. Each specialist agent gets its relevant `McpToolset` instances (or SDK function tools) with stable server URLs and a `header_provider` for per-user OAuth.

## 3. Multi-Tenancy Model

Every major marketing platform API authenticates via OAuth 2.0 per-user tokens. MCP servers pass the token through to the platform API. **One MCP server instance serves all accounts** — the API call is scoped to whoever's token is in the header.

We do not need per-account MCP server instances. The only potential exception is account-specific automation (e.g., custom n8n workflows).

## 4. Platform Integration Decisions

### Decision Framework (priority order)

1. **Provider-hosted multi-tenant MCP** — zero maintenance, use as-is
2. **Provider official MCP, self-hosted** — low maintenance, provider maintains code
3. **SDK function tools in the agent** — provider maintains SDK, we write thin wrappers, no MCP server to deploy
4. **Build our own MCP server** — last resort, ongoing API maintenance burden

### Platform Decisions

| Platform | Decision | Integration Type | Rationale |
|----------|----------|------------------|-----------|
| **HubSpot** | Use provider MCP | Provider-hosted at `mcp.hubspot.com` | Only platform offering a hosted multi-tenant MCP. OAuth 2.1, zero deployment. Currently read-only (CRM objects) but HubSpot is actively expanding. |
| **Google Ads** | Use official MCP, self-host | Self-host on Cloud Run | Google maintains the code. Read-only for now — sufficient for v1 reporting. Monitor for hosted option + write access. |
| **Meta Ads** | SDK function tools | `facebook-business` Python SDK | Highest CMO value (full campaign CRUD). Graph API changes frequently — better to let Meta handle SDK updates than maintain an MCP server. |
| **Mailchimp** | SDK function tools | `mailchimp-marketing` Python SDK | Simple REST API, official SDK. Not worth a standalone MCP server for email-only functionality. |
| **Microsoft Ads** | Defer | — | Lowest CMO value, no official MCP, weakest ecosystem. Revisit when there's actual client demand. |

### Why SDK Function Tools Over Third-Party MCP

For Meta Ads and Mailchimp, third-party MCP servers exist but have problems:
- **Licensing:** Pipeboard Meta Ads MCP uses BSL 1.1 (no competing hosted service)
- **Pricing/limits:** Many are paid or have account limits
- **Maintenance risk:** Community-maintained, could go stale

SDK function tools avoid both problems: provider maintains the SDK, no server to deploy, no licensing concerns.

**Tradeoff:** If we later need non-agent consumers (CLI, other products), we'd extract these into MCP servers. That's a straightforward future extraction.

### SDK Function Tools Pattern

```python
# In the Execution Specialist agent — no MCP server needed
@tool
async def update_meta_campaign_budget(
    campaign_id: str, daily_budget: float, tool_context: ToolContext
) -> dict:
    """Update a Meta Ads campaign's daily budget."""
    creds = tool_context.state.get("meta_credentials")
    api = FacebookAdsApi.init(access_token=creds["access_token"])
    campaign = Campaign(campaign_id)
    campaign.api_update(params={"daily_budget": int(daily_budget * 100)})
    return {"status": "updated", "campaign_id": campaign_id}
```

## 5. Token Budget Solution: Specialist Routing

Token budget is solved by specialist routing. Each specialist agent has 2-5 tool sources (~10-30 tools), well within context limits. The root agent routes to the right specialist — it never sees all 400 tools.

```
User -> API -> Agent Engine
                |-- KEN-E Root Agent (router, no tools)
                |     |-- Analytics Specialist
                |     |     |-- McpToolset -> Google Ads MCP (self-hosted, Cloud Run)
                |     |     |-- McpToolset -> GA MCP (self-hosted, exists today)
                |     |
                |     |-- Content Specialist
                |     |     |-- McpToolset -> HubSpot MCP (provider-hosted)
                |     |     |-- SDK tools -> Mailchimp (mailchimp-marketing SDK)
                |     |
                |     |-- Execution Specialist
                |     |     |-- SDK tools -> Meta Ads (facebook-business SDK)
                |     |     |-- McpToolset -> Google Ads MCP (shared instance)
                |     |
                |     |-- Automation Specialist
                |           |-- McpToolset -> n8n MCP (self-hosted, TBD)
```

## 6. MCP Server Config Registry

### Current: YAML Config

MCP server definitions are stored in `app/adk/mcp_config/config/mcp_servers.yaml`. Currently defines 6 servers (1 enabled: Google Analytics).

```yaml
# Example from mcp_servers.yaml
servers:
  google_analytics_mcp:
    description: "Google Analytics 4 data access, reports, and audiences"
    category: "analytics"
    tool_count: 4
    estimated_tokens: 1800
    keywords: [analytics, ga4, traffic, users, sessions, pageviews, metrics]
    connection:
      connection_type: sse
      url: "${GA_MCP_SERVER_URL}/mcp/sse"
      headers:
        Content-Type: "application/json"
      timeout_seconds: 30
    auth_type: "ga_oauth"
    enabled: true
```

### Planned: Firestore Config Registry (Sprint 5-6)

```
mcp_servers/{server_id}
  |-- name: "google_ads"
  |-- url: "https://google-ads-mcp.ken-e.ai/sse"
  |-- auth_type: "oauth2"
  |-- integration_type: "mcp" | "sdk" | "provider_mcp"
  |-- specialist_categories: ["analytics", "execution"]
  |-- hosting: "self" | "provider"
  |-- enabled: true
```

The **agent factory** (Sprint 5-6) reads this config to assemble specialist agents with the right `McpToolset` instances or SDK function tools. Config-driven agent assembly at deploy/startup time, not runtime tool swapping.

## 7. MCPServerManager Disposition

The Sprint 3 `MCPServerManager` (`app/adk/mcp_config/manager.py`) was built as an in-process Python singleton. Its connection pooling and LRU eviction are redundant — ADK's `MCPSessionManager` already pools connections by header hash, and specialist agents have fixed server sets.

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin status endpoints | **Keep** — operational tooling at API layer |
| Connection pooling | **Remove** — ADK handles natively |
| LRU eviction logic | **Remove** — not applicable on Agent Engine |
| Config loading + auth helpers | **Reuse** — move to agent factory |
| YAML config | **Evolve** — extend schema, migrate to Firestore |

## 8. Read-Only Limitations and CMO Impact

Google Ads and HubSpot MCP servers are currently read-only. This means KEN-E can **analyze and recommend** but cannot **execute** on those platforms.

For a CMO saying "shift 20% of budget to Campaign X":
- **Meta Ads**: Can execute directly (SDK has full CRUD)
- **Google Ads**: Can generate an action plan with specific steps, but execution requires manual action until write access is available
- **HubSpot**: Can pull CRM data for analysis, but workflow creation requires manual action

This informs the Execution Specialist's design — it generates action plans for read-only platforms and executes directly for write-capable ones.

## 9. Infrastructure Summary

| Component | Count | What |
|-----------|-------|------|
| Cloud Run deployments | 2 | Google Ads MCP + GA MCP (existing) |
| Provider-hosted MCP | 1 | HubSpot (`mcp.hubspot.com`) |
| SDK dependencies | 2 | `facebook-business`, `mailchimp-marketing` |
| Total infrastructure to maintain | 2 servers | Everything else is provider-maintained |

## 10. Open Questions

1. **n8n MCP** — Account-specific automation workflows may need per-account isolation. Needs investigation.
2. **Google Ads write access timeline** — Monitor Google's roadmap. If no progress by Sprint 6, evaluate building write-capable tools as SDK function tools instead.
3. **Agent factory timeline** — Config-driven specialist assembly (Sprint 5-6) is the prerequisite for scaling beyond current hardcoded agents.

## References

- [Notion Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463)
- [Google Ads MCP (Official)](https://github.com/googleads/google-ads-mcp)
- [HubSpot MCP Server (Official)](https://developers.hubspot.com/mcp)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-api)
- ADK source verified: `google/adk/tools/mcp_tool/mcp_toolset.py`, `mcp_session_manager.py`
- MCP server config: `app/adk/mcp_config/config/mcp_servers.yaml`
- MCPServerManager: `app/adk/mcp_config/manager.py`
