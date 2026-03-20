# MCP Server Architecture

**Version:** 1.4
**Date:** March 2026
**Status:** Canonical — reflects decisions from Sprint 3b architecture review + design review (March 10, 2026) + Gemini code execution taxonomy (March 18, 2026)
**Canonical Source:** [Notion Design Brief](https://www.notion.so/31e30fd653028118bd11f4a3270e3463)

---

## 1. Context

KEN-E needs to support ~400 tools across 20-40 MCP servers per account for marketing CMOs. This document captures verified architectural decisions based on ADK internals research, MCP ecosystem analysis, and platform-by-platform integration evaluation.

## 2. ADK Internals: Verified Behavior

We read the ADK source code (`mcp_toolset.py`, `mcp_session_manager.py`, `base_llm_flow.py`, `base_toolset.py`, `llm_agent.py`) and confirmed:

| Behavior | Detail |
|----------|--------|
| **Agent objects are singletons** | Reused across all requests per deployment |
| **`McpToolset.get_tools()` called every LLM turn** | Tools re-resolved per invocation context, not cached across turns. Intentional for per-user permissions — different users can see different tools. |
| **SSE sessions pooled by connection params** | `MCPSessionManager` caches sessions keyed by connection parameters. Same params reuse connection; different params get separate connections. |
| **`tool_filter` evaluated per turn** | `BaseToolset._is_tool_selected(tool, ctx)` applies filters on every `get_tools()` call, receiving `ReadonlyContext`. Supports callable predicates or static name lists. |
| **`canonical_tools` cached per invocation** | Since ADK v1.26.0 ([commit 8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8)), `base_llm_flow.py` caches resolved tools on `invocation_context.canonical_tools_cache` to avoid redundant calls within a single response. Pre-1.26, `get_tools()` was called 4-5x per response. |

> **ADK version note:** We are currently on `google-adk==1.23.0` (`>=1.23.0` floor). The per-invocation caching fix landed in `1.26.0`. We should bump to `>=1.26.0` to avoid the redundant `get_tools()` calls. Between 1.23 and 1.26, ADK also added toolset authentication hooks and parallelized tool resolution.

### What `get_tools()` Does and Does Not Do

**Does:** Re-query connected MCP servers for their current tool list each turn. If an MCP server adds or removes a tool, the agent sees the change on the next turn without redeployment.

**Does not:** Connect to new MCP servers mid-conversation. The set of `McpToolset` instances on an agent is fixed at construction time. Discovering and connecting to a server the agent wasn't wired to requires either redeployment or a dynamic tool selection mechanism (see Section 5a).

**Implication:** `McpToolset` handles connection management, per-user auth, and tool resolution natively. No custom toolset wrapper is needed. However, for a system with ~400 tools across 20-40 servers, we need a mechanism to control which tools are exposed to the LLM on any given turn — this is where `tool_filter` and the ToolRegistry become critical (see Section 5a).

## 3. Multi-Tenancy Model

Every major marketing platform API authenticates via OAuth 2.0 per-user tokens. MCP servers pass the token through to the platform API. **One MCP server instance serves all accounts** — the API call is scoped to whoever's token is in the header.

We do not need per-account MCP server instances. The only potential exception is account-specific automation (e.g., custom n8n workflows).

> For the full credential lifecycle (OAuth flow, encrypted storage, token refresh, reauth signaling), see [`docs/KEN-E-Agentic-Harness-Design.md`](../KEN-E-Agentic-Harness-Design.md) Section 11.2.

## 4. Platform Integration Decisions

> **Roadmap:** [Feature 2.3: Analytics Specialist](../product-roadmap.md#feature-23-analytics-specialist--phase-1), [Feature 3.1: Content Specialist](../product-roadmap.md#feature-31-content-specialist), [Feature 3.2: Execution Specialist](../product-roadmap.md#feature-32-execution-specialist) — Releases 2.0, 3.0

| Platform | Decision | Integration Type |
|----------|----------|------------------|
| **HubSpot** | Use provider MCP | Provider-hosted at `mcp.hubspot.com` (OAuth 2.1, read-only CRM, zero deployment) |
| **Google Ads** | Hybrid: MCP reads + SDK writes | Self-host MCP on Cloud Run + `google-ads` SDK function tools for campaign CRUD |
| **Meta Ads** | SDK function tools | `facebook-business` Python SDK — shared: Analytics (reads) + Execution (reads + writes) |
| **Mailchimp** | SDK function tools | `mailchimp-marketing` Python SDK |
| **Microsoft Ads** | Defer | Revisit when there's client demand |
| **Gemini Code Execution** | Built-in model capability | `GenerateContentConfig.tools` — Analytics Specialist primary. No infrastructure — Google-managed sandbox. |

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

> **`create_visualization()` follows this same pattern** — it is a Python function tool (not MCP) available to all specialist agents. It produces Vega-Lite chart specs and writes them to `response_artifacts` session state. See [`data-visualization.md`](data-visualization.md) for the full design.

## 5. Token Budget Solution: Specialist Routing + Dynamic Tool Filtering

Token budget is addressed at two levels:

1. **Specialist routing (structural)** — Each specialist agent has 2-5 tool sources (~10-30 tools). The root agent routes to the right specialist — it never sees all 400 tools.
2. **`tool_filter` (per-turn)** — Even within a specialist, not all tools need to be exposed on every turn. ADK's `tool_filter` on `BaseToolset` can dynamically select which tools the LLM sees, reducing context usage further.

Built-in model capabilities are orthogonal to both levels of the token budget. They are not MCP tools, not subject to `tool_filter`, and carry zero context overhead. They are configured at agent construction via `GenerateContentConfig`, not through `McpToolset` or function tools. Currently, only Gemini code execution is planned (Analytics Specialist, Sprint 5-6).

```
User -> API -> Agent Engine
                |-- KEN-E Root Agent (router, no tools)
                |     |-- Analytics Specialist
                |     |     |-- McpToolset -> Google Ads MCP (self-hosted, Cloud Run)
                |     |     |-- McpToolset -> GA MCP (self-hosted, exists today)
                |     |     |-- SDK tools -> Meta Ads reads (facebook-business SDK)
                |     |     |-- Built-in -> Gemini code execution (GenerateContentConfig)
                |     |
                |     |-- Content Specialist
                |     |     |-- McpToolset -> HubSpot MCP (provider-hosted)
                |     |     |-- SDK tools -> Mailchimp (mailchimp-marketing SDK)
                |     |
                |     |-- Execution Specialist
                |     |     |-- SDK tools -> Meta Ads reads + writes (facebook-business SDK)
                |     |     |-- SDK tools -> Google Ads writes (google-ads SDK)
                |     |     |-- McpToolset -> Google Ads MCP (shared, read-only)
                |     |
                |     |-- Automation Specialist
                |           |-- McpToolset -> n8n MCP (self-hosted, TBD)
```

> **Review loops:** Every specialist delegation is wrapped in a review loop (generator-critic pattern using ADK `LoopAgent`) that enforces acceptance criteria before returning results. See [`docs/KEN-E-Agentic-Harness-Design.md`](../KEN-E-Agentic-Harness-Design.md) Section 4.6 for the review loop design and Section 8 for multi-step workflow composition.
>
> **Skills complement `tool_filter`:** ADK Skills provide procedural instructions for HOW to use tools (step-by-step workflows, best practices), while `tool_filter` controls WHICH tools are visible. A skill's `allowed-tools` field documents referenced tools, but visibility is still governed by `tool_filter`. See [`docs/KEN-E-Agentic-Harness-Design.md`](../KEN-E-Agentic-Harness-Design.md) Section 6.

## 5a. Dynamic Tool Selection via `tool_filter` + ToolRegistry

> **Roadmap:** [Feature 2.2: Agent Factory](../product-roadmap.md#feature-22-agent-factory--phase-1) — Release 2.0

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

### Resolved: How ToolRegistry Search Drives `tool_filter`

Experiment #4 (ADK v1.26.0) tested four options for triggering ToolRegistry search to populate `tool_filter_state`:

| Option | Mechanism | State Access | Timing vs `tool_filter` | Verdict |
|--------|-----------|-------------|------------------------|---------|
| 1: InstructionProvider | Runs per-turn | `ReadonlyContext` (read-only) | Same phase — but cannot write state | **Cannot write state** |
| 2: Root agent writes state | Root's LLM turn sets state before dispatch | `ToolContext` (mutable) | Before specialist's first turn only | **Works for dispatch, not per-turn within specialist** |
| 3: Specialist tool call | LLM calls `search_tools` function tool | `ToolContext` (mutable) | One turn late — tools already resolved for current turn | **One-turn delay; wastes an LLM call** |
| **4: `before_agent_callback`** | **Fires before each LLM turn** | **`CallbackContext` (mutable)** | **Before tool resolution** | **Recommended — per-turn, pre-resolution** |

**Key insight:** `ReadonlyContext.state` is a `MappingProxyType` wrapping the same `session.state` dict. Writes from `CallbackContext` in `before_agent_callback` are immediately visible to `InstructionProvider` and `tool_filter` — no copy, no propagation delay.

#### Production Code Pattern

```python
# Specialist agent's before_agent_callback — writes tool_filter_state
async def toolregistry_before_agent_callback(
    callback_context: CallbackContext,
) -> None:
    user_query = _extract_latest_user_message(callback_context)
    results = tool_registry.search(user_query)
    callback_context.state["tool_filter_state"] = [r.name for r in results]

# McpToolset reads tool_filter_state via tool_filter lambda
McpToolset(
    connection_params=SseConnectionParams(url="..."),
    tool_filter=lambda tool, ctx: tool.name in ctx.state.get("tool_filter_state", []),
)
```

#### Execution Order per LLM Turn

```
1. before_agent_callback  → writes state["tool_filter_state"] via CallbackContext (mutable)
2. InstructionProvider     → reads state via ReadonlyContext (live view of same dict)
3. tool_filter             → reads state via ReadonlyContext (live view of same dict)
4. before_model_callback   → final pre-LLM hook
5. LLM call                → sees only filtered tools in context
```

All share the same `session.state` dict — `ReadonlyContext.state` is a `MappingProxyType` (read-only live view), so `CallbackContext` writes are immediately visible.

#### Anti-Patterns

1. **Do not write state via `ReadonlyContext`** — `MappingProxyType` raises `TypeError` on write. Only `CallbackContext` and `ToolContext` can mutate state.
2. **Set `bypass_state_injection=True`** when `instruction` is a callable `InstructionProvider` — otherwise ADK injects a state dump into the instruction, wasting tokens.
3. **Avoid `temp:` state prefix** — keys prefixed `temp:` are excluded from state delta tracking and may not persist across turns.

#### Note on Option 2

Option 2 (root agent writes state before dispatch) remains valid for the root→specialist handoff: the root interprets intent and writes initial tool categories to state. However, it does not cover per-turn updates within a multi-turn specialist conversation. Option 4 handles both cases.

> Validated in Experiment #4 (`adk_experiments/experiment/instruction-tool-coordination`), ADK v1.26.0. See [Decision 23: tool_filter Integration Pattern](https://www.notion.so/32730fd6530281999389eb3116e7585c) for full rationale.

## 6. MCP Server Config Registry

> **Roadmap:** [Feature 1.1.4: Firestore Config Registry](../product-roadmap.md#feature-114-firestore-config-registry-preparation-for-agent-factory), [Feature 2.2: Agent Factory](../product-roadmap.md#feature-22-agent-factory--phase-1) — Releases 1.1, 2.0

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

> **Roadmap:** [Feature 2.2: Agent Factory](../product-roadmap.md#feature-22-agent-factory--phase-1) — Release 2.0

The `MCPServerManager` (`app/adk/mcp_config/manager.py`) is a Sprint 3 in-process Python singleton.

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin status endpoints | **Keep** |
| Connection pooling | **Deprecated** → remove in Sprint 5-6 |
| LRU eviction logic | **Deprecated** → remove in Sprint 5-6 |
| Config loading + auth helpers | **Reuse** — move to agent factory |
| YAML config | **Evolve** — extend schema, migrate to Firestore |

## 8. Read-Only Limitations and CMO Impact

> **Roadmap:** [Feature 3.2: Execution Specialist](../product-roadmap.md#feature-32-execution-specialist) — Release 3.0

HubSpot MCP is currently read-only. Google Ads uses a **hybrid approach** (MCP for reads, SDK for writes). This means:

For a CMO saying "shift 20% of budget to Campaign X":
- **Meta Ads**: Can execute directly (SDK has full CRUD)
- **Google Ads**: Can execute directly via `google-ads` SDK function tools (campaign CRUD, budget changes, bid adjustments). Reporting and analytics use the MCP server (read-only).
- **HubSpot**: Can pull CRM data for analysis, but workflow creation requires manual action until HubSpot expands MCP write capabilities

The Analytics Specialist uses MCP servers and read-only SDK tools for reporting across GA, Google Ads, and Meta Ads. The Execution Specialist uses SDK function tools for write operations on Meta Ads and Google Ads. The `facebook-business` SDK is available to both specialists with different tool subsets controlled by `tool_filter` — Analytics sees read-only tools (get campaigns, get spend, get metrics) while Execution sees the full CRUD set.

> For the full specialist tool source mapping and planned agent factory, see [`docs/KEN-E-Agentic-Harness-Design.md`](../KEN-E-Agentic-Harness-Design.md) Section 4.4.

## 9. Infrastructure Summary

| Component | Count | What |
|-----------|-------|------|
| Cloud Run deployments | 2 | Google Ads MCP + GA MCP (existing) |
| Provider-hosted MCP | 1 | HubSpot (`mcp.hubspot.com`) |
| SDK dependencies | 3 | `google-ads`, `facebook-business`, `mailchimp-marketing` |
| Built-in model capabilities | 1 | Gemini code execution (no infrastructure — Google-managed) |
| Total infrastructure to maintain | 2 servers | Everything else is provider-maintained, SDK-based, or built-in |

## 10. Open Questions

1. **n8n MCP** — Account-specific automation workflows may need per-account isolation. Needs investigation.
2. **Google Ads write access timeline** — Monitor Google's roadmap. If no progress by Sprint 6, evaluate building write-capable tools as SDK function tools instead.
3. **Agent factory timeline** — Config-driven specialist assembly (Sprint 5-6) is the prerequisite for scaling beyond current hardcoded agents.
4. **ADK version bump** — Bump `google-adk>=1.26.0` to get per-invocation tool caching fix and toolset auth hooks. Current `>=1.23.0` hits the redundant `get_tools()` bug (4-5x per response instead of 1x).
5. ~~**`tool_filter` integration pattern** — Decide which option from Section 5a (InstructionProvider, root agent state write, or specialist self-search) best fits the dispatch pattern. Prototype needed before Sprint 5-6 agent factory work.~~ **Resolved (Experiment #4, March 2026):** Use `before_agent_callback` (Option 4). See Section 5a.
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
