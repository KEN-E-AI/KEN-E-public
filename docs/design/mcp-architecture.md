# MCP Server Architecture

**Version:** 1.1
**Date:** March 2026
**Status:** Canonical — reflects decisions from Sprint 3b architecture review + design review (March 10, 2026)
**Canonical Source:** [Notion Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463)

---

## 1. Context

KEN-E needs to support ~400 tools across 20-40 MCP servers per account for marketing CMOs. This document captures verified architectural decisions based on ADK internals research, MCP ecosystem analysis, and platform-by-platform integration evaluation.

## 2. ADK Internals: Verified Behavior

We read the ADK source code (`mcp_toolset.py`, `mcp_session_manager.py`, `base_llm_flow.py`, `base_toolset.py`, `llm_agent.py`) and confirmed:

| Behavior | Detail | Verified Against |
|----------|--------|-----------------|
| **Agent objects are singletons** | Reused across all requests per deployment | Agent Engine runtime |
| **`McpToolset.get_tools()` called every LLM turn** | Tools re-resolved per invocation context, not cached across turns. This is intentional — `get_tools(readonly_context)` is designed for per-user permissions so different users can see different tools. | ADK team comment on [#3237](https://github.com/google/adk-python/issues/3237) |
| **SSE sessions pooled by connection params** | `MCPSessionManager` caches sessions keyed by connection parameters. Same params reuse connection; different params get separate connections. | `mcp_session_manager.py` |
| **`tool_filter` evaluated per turn** | `BaseToolset._is_tool_selected(tool, ctx)` applies filters on every `get_tools()` call, receiving `ReadonlyContext`. Supports callable predicates or static name lists. | `base_toolset.py` |
| **`canonical_tools` cached per invocation** | Since ADK v1.26.0 ([commit 8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8)), `base_llm_flow.py` caches resolved tools on `invocation_context.canonical_tools_cache` to avoid redundant calls within a single response. Pre-1.26, `get_tools()` was called 4-5x per response. | PR [#3299](https://github.com/google/adk-python/pull/3299) |

> **ADK version note:** We are currently on `google-adk==1.23.0` (`>=1.23.0` floor). The per-invocation caching fix landed in `1.26.0`. We should bump to `>=1.26.0` to avoid the redundant `get_tools()` calls. Between 1.23 and 1.26, ADK also added toolset authentication hooks and parallelized tool resolution.

### What `get_tools()` Does and Does Not Do

**Does:** Re-query connected MCP servers for their current tool list each turn. If an MCP server adds or removes a tool, the agent sees the change on the next turn without redeployment.

**Does not:** Connect to new MCP servers mid-conversation. The set of `McpToolset` instances on an agent is fixed at construction time. Discovering and connecting to a server the agent wasn't wired to requires either redeployment or a dynamic tool selection mechanism (see Section 5a).

**Implication:** `McpToolset` handles connection management, per-user auth, and tool resolution natively. No custom toolset wrapper is needed. However, for a system with ~400 tools across 20-40 servers, we need a mechanism to control which tools are exposed to the LLM on any given turn — this is where `tool_filter` and the ToolRegistry become critical (see Section 5a).

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

## 5. Token Budget Solution: Specialist Routing + Dynamic Tool Filtering

Token budget is addressed at two levels:

1. **Specialist routing (structural)** — Each specialist agent has 2-5 tool sources (~10-30 tools). The root agent routes to the right specialist — it never sees all 400 tools.
2. **`tool_filter` (per-turn)** — Even within a specialist, not all tools need to be exposed on every turn. ADK's `tool_filter` on `BaseToolset` can dynamically select which tools the LLM sees, reducing context usage further.

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

## 5a. Dynamic Tool Selection via `tool_filter` + ToolRegistry

### The Problem

Specialist routing reduces tools from ~400 to ~10-30 per specialist, but as specialists grow (more MCP servers per domain, more tools per server), even a specialist could accumulate enough tools to waste context. Additionally, the v1.0 design included a `ToolDiscoveryAgent` that could search a tool catalog and load tools on-demand — specialist routing alone does not preserve this capability.

### The Mechanism

ADK's `BaseToolset` (parent of `McpToolset`) accepts a `tool_filter` parameter:

```python
# Static filter — always expose only these tools
McpToolset(
    connection_params=SseConnectionParams(url="..."),
    tool_filter=["run_report_mt", "get_account_summaries_mt"],
)

# Dynamic filter — decide per-turn based on context
McpToolset(
    connection_params=SseConnectionParams(url="..."),
    tool_filter=lambda tool, ctx: tool.name in ctx.state.get("relevant_tools", []),
)
```

The dynamic form receives `ReadonlyContext` and is evaluated on every `get_tools()` call (i.e., every LLM turn). This enables per-turn, per-user tool selection without loading/unloading MCP server connections.

### Proposed Architecture: ToolRegistry as `tool_filter` Driver

The ToolRegistry (`app/adk/tools/registry/tool_registry.py`) already provides keyword search, category matching, and relevance scoring across the full tool catalog (~2,000 token index). It can drive `tool_filter` decisions:

```
Each LLM turn:
  1. ToolRegistry.search(user_query) → relevant tool names (lightweight, ~ms)
  2. Write relevant_tools to session state
  3. McpToolset.get_tools(ctx) → _is_tool_selected() checks ctx.state["relevant_tools"]
  4. Only matching tools sent to LLM
```

| Approach | MCP Servers | Tools in Context | Context Cost |
|----------|-------------|------------------|-------------|
| No filtering (all tools on specialist) | Fixed at deploy | All tools on connected servers | Up to ~30 tools × 150 tokens = 4,500 tokens |
| `tool_filter` + ToolRegistry | Fixed at deploy | Only relevant tools per turn | ~5-10 tools × 150 tokens = 750-1,500 tokens |

### What This Preserves from v1.0

The v1.0 design had a `ToolDiscoveryAgent` with `search_tools()` and `load_tools()` capabilities. The `tool_filter` + ToolRegistry approach preserves the search/discovery capability while dropping the runtime server connection management:

| v1.0 Capability | Preserved? | How |
|-----------------|-----------|-----|
| Search ~400 tool catalog by keyword | Yes | ToolRegistry.search() |
| Expose only relevant tools per turn | Yes | `tool_filter` predicate using ToolRegistry results |
| Token budget awareness | Yes | Fewer tools = fewer tokens in context |
| Load new MCP servers mid-conversation | **No** | Server set fixed at deploy; mitigated by config-driven agent factory |
| Unload MCP servers to free context | **No longer needed** | `tool_filter` hides tools without disconnecting — no context cost for filtered tools |

### Open Design Question

The ToolRegistry search needs to happen *before* or *during* each turn's tool resolution. Options:

1. **Pre-processing in InstructionProvider** — The `InstructionProvider` closure already runs each turn. It could query the ToolRegistry and write results to session state before tool resolution happens.
2. **Root agent writes to state before dispatch** — The root agent interprets intent, writes relevant tool categories to session state, then dispatches to specialist.
3. **Specialist agent's first tool call** — Each specialist has a `search_tools` function tool that the LLM calls to narrow its own toolset for subsequent turns.

Option 2 is the most natural fit with the existing dispatch pattern. The root agent already interprets intent to choose a specialist — it can also write which tool categories/keywords are relevant.

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

The Sprint 3 `MCPServerManager` (`app/adk/mcp_config/manager.py`) was built as an in-process Python singleton. Its connection pooling and LRU eviction are redundant — ADK's `MCPSessionManager` already pools connections, and `tool_filter` replaces LRU eviction (tools are hidden from context rather than disconnected).

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin status endpoints | **Keep** — operational tooling at API layer |
| Connection pooling | **Remove** — ADK handles natively via `MCPSessionManager` |
| LRU eviction logic | **Remove** — replaced by `tool_filter` (hides tools from context without disconnecting) |
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
4. **ADK version bump** — Bump `google-adk>=1.26.0` to get per-invocation tool caching fix and toolset auth hooks. Current `>=1.23.0` hits the redundant `get_tools()` bug (4-5x per response instead of 1x).
5. **`tool_filter` integration pattern** — Decide which option from Section 5a (InstructionProvider, root agent state write, or specialist self-search) best fits the dispatch pattern. Prototype needed before Sprint 5-6 agent factory work.
6. **Dynamic MCP server connection** — Specialist routing + `tool_filter` covers tool-level dynamism but not server-level dynamism. If different accounts need different MCP server sets, the agent factory must assemble per-account specialist configurations at session creation time (not just at deploy time). This needs scoping.

## References

- [Notion Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463)
- [Google Ads MCP (Official)](https://github.com/googleads/google-ads-mcp)
- [HubSpot MCP Server (Official)](https://developers.hubspot.com/mcp)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-api)
- ADK source verified: `mcp_toolset.py`, `mcp_session_manager.py`, `base_toolset.py`, `base_llm_flow.py`, `llm_agent.py`
- ADK issue [#3237](https://github.com/google/adk-python/issues/3237) — `get_tools()` redundant calls (fixed in v1.26.0 via [#3299](https://github.com/google/adk-python/pull/3299))
- ADK commit [8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8) — canonical tools caching
- MCP server config: `app/adk/mcp_config/config/mcp_servers.yaml`
- MCPServerManager: `app/adk/mcp_config/manager.py`
- ToolRegistry: `app/adk/tools/registry/tool_registry.py`
- Design review log: `docs/design/DESIGN-REVIEW-LOG.md`
