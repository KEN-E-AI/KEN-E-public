# MCP Server Architecture

**Version:** 2.0
**Date:** April 2026
**Status:** Canonical — reflects the narrow-per-platform specialist roadmap and the retirement of the per-turn `tool_filter` mechanism. Supersedes v1.4.
**Canonical Source:** This document. (Historical Notion design brief retained as archive: [Notion link](https://www.notion.so/31e30fd653028118bd11f4a3270e3463).)

> **v2.0 change summary (April 2026):** Deleted former §5a (`tool_filter` + ToolRegistry runtime driver) — that mechanism is retired. Rewrote §5 around specialist routing only — per-turn filtering is gone; each specialist is constructed with a fixed ≤30-tool roster. Replaced the Analytics / Content / Execution / Automation specialist tree with the narrow-per-platform roadmap (GA in R1; Google Ads / Meta Ads / Mailchimp in R5). Updated §8 and §10 accordingly. See [README §2.5](./README.md#25-tool-assignment--routing-model) for the current tool-assignment and routing model.

---

## 1. Context

KEN-E supports ~400 tools across 20–40 MCP servers per account for marketing CMOs. This document captures verified architectural decisions based on ADK internals research, MCP ecosystem analysis, and platform-by-platform integration evaluation. It is the MCP-specific reference for the agentic-harness component — the component-level architecture lives in [`./README.md`](./README.md); this file covers the MCP integration layer.

## 2. ADK Internals: Verified Behavior

We read the ADK source code (`mcp_toolset.py`, `mcp_session_manager.py`, `base_llm_flow.py`, `base_toolset.py`, `llm_agent.py`) and confirmed:

| Behavior | Detail |
|----------|--------|
| **Agent objects are singletons** | Reused across all requests per deployment |
| **`McpToolset.get_tools()` called every LLM turn** | Tools re-resolved per invocation context, not cached across turns. Intentional for per-user permissions — different users can see different tools. |
| **SSE sessions pooled by connection params** | `MCPSessionManager` caches sessions keyed by connection parameters. Same params reuse connection; different params get separate connections. |
| **`canonical_tools` cached per invocation** | Since ADK v1.26.0 ([commit 8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8)), `base_llm_flow.py` caches resolved tools on `invocation_context.canonical_tools_cache` to avoid redundant calls within a single response. Pre-1.26, `get_tools()` was called 4–5× per response. |

> **ADK version note:** We are currently on `google-adk==1.23.0` (`>=1.23.0` floor). The per-invocation caching fix landed in `1.26.0`. We should bump to `>=1.26.0` to avoid the redundant `get_tools()` calls. Between 1.23 and 1.26, ADK also added toolset authentication hooks and parallelized tool resolution.

### What `get_tools()` Does and Does Not Do

**Does:** Re-query connected MCP servers for their current tool list each turn. If an MCP server adds or removes a tool, the agent sees the change on the next turn without redeployment.

**Does not:** Connect to new MCP servers mid-conversation. The set of `McpToolset` instances on an agent is fixed at construction time. Discovering and connecting to a server the agent wasn't wired to requires redeployment.

**Implication:** `McpToolset` handles connection management, per-user auth, and tool resolution natively. No custom toolset wrapper is needed. Context-budget control comes from **specialist scope** (each specialist narrow enough to stay under 30 tools), not from per-turn filtering — see [README §2.5 Tool-assignment & routing model](./README.md#25-tool-assignment--routing-model).

## 3. Multi-Tenancy Model

Every major marketing platform API authenticates via OAuth 2.0 per-user tokens. MCP servers pass the token through to the platform API. **One MCP server instance serves all accounts** — the API call is scoped to whoever's token is in the header.

We do not need per-account MCP server instances. The only potential exception is account-specific automation (e.g., custom n8n workflows) — see §10 Q1.

> For the full credential lifecycle (OAuth flow, encrypted storage, token refresh, reauth signaling), see [`docs/KEN-E-System-Architecture.md`](../../../KEN-E-System-Architecture.md) §11.2.

## 4. Platform Integration Decisions

> **Roadmap:** Release 1 delivers Google Analytics ([AH-PRD-03](./projects/AH-PRD-03-google-analytics-specialist.md)). Release 5 delivers Google Ads, Meta Ads, and Mailchimp specialists — see [README §2.6 Specialist roadmap](./README.md#26-specialist-roadmap).

| Platform | Decision | Integration Type | Specialist |
|----------|----------|------------------|------------|
| **Google Analytics** | Self-host MCP | Self-hosted on Cloud Run (OAuth, reporting, audiences) | GA Specialist (R1) |
| **Google Ads** | Hybrid: MCP reads + SDK writes | Self-host MCP on Cloud Run + `google-ads` SDK function tools for campaign CRUD | Google Ads Specialist (R5, planned) |
| **Meta Ads** | SDK function tools | `facebook-business` Python SDK — read + write + CRUD | Meta Ads Specialist (R5, planned) |
| **Mailchimp** | SDK function tools | `mailchimp-marketing` Python SDK | Mailchimp Specialist (R5, planned) |
| **HubSpot** | Use provider MCP | Provider-hosted at `mcp.hubspot.com` (OAuth 2.1, read-only CRM, zero deployment) | Not yet assigned to a specialist |
| **Microsoft Ads** | Defer | Revisit when there's client demand | — |
| **n8n** | Self-host MCP | TBD — see §10 Q1 (account-specific automation may need per-account isolation) | Not yet assigned |
| **Gemini Code Execution** | Built-in model capability | `GenerateContentConfig.tools` — no infrastructure (Google-managed sandbox); zero context overhead | GA Specialist (R1); likely others later |

### SDK Function Tools Pattern

```python
# In a specialist agent — no MCP server needed for SDK tools
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

> **`create_visualization()` follows this same pattern** — a Python function tool (not MCP) available to all specialist agents. It produces Vega-Lite chart specs and writes them to `response_artifacts` session state. See [`./data-visualization.md`](./data-visualization.md) for the full design.

## 5. Specialist Routing

> **Roadmap:** [AH-PRD-03](./projects/AH-PRD-03-google-analytics-specialist.md) delivers the first specialist (Google Analytics) in R1. Additional narrow specialists ship in R5. See [README §2.5 Tool-assignment & routing model](./README.md#25-tool-assignment--routing-model) and [README §2.6 Specialist roadmap](./README.md#26-specialist-roadmap).

Token budget is managed by **specialist routing**, not per-turn filtering. Each narrow specialist is constructed by the agent factory with a **fixed curated tool roster of ≤30 tools**. The root agent routes to a specialist by LLM reasoning over each specialist's description — not via a tool-level index. Because specialists are narrow per-platform, most carry ~5–15 tools and stay well under the 30-tool cap; the root never sees the full ~400-tool catalog.

Built-in model capabilities (Gemini code execution) are orthogonal to the roster: configured at agent construction via `GenerateContentConfig`, not through `McpToolset` or function tools, carrying zero context overhead and not counted against the 30-tool cap.

```
User -> API -> Agent Engine
                |-- KEN-E Root Agent (description-based routing, no domain tools)
                |     |-- Google Analytics Specialist (R1)
                |     |     |-- McpToolset -> GA MCP (self-hosted, Cloud Run)
                |     |     |-- Built-in -> Gemini code execution
                |     |     |-- Function tool -> create_visualization()
                |     |
                |     |-- Google Ads Specialist (R5, planned)
                |     |     |-- McpToolset -> Google Ads MCP (self-hosted, reads)
                |     |     |-- SDK function tools -> google-ads (writes, CRUD)
                |     |     |-- Function tool -> create_visualization()
                |     |
                |     |-- Meta Ads Specialist (R5, planned)
                |     |     |-- SDK function tools -> facebook-business (reads + writes + CRUD)
                |     |     |-- Function tool -> create_visualization()
                |     |
                |     |-- Mailchimp Specialist (R5, planned)
                |           |-- SDK function tools -> mailchimp-marketing
                |           |-- Function tool -> create_visualization()
                |
                HubSpot (provider MCP) and n8n (self-hosted MCP) integrations
                are decided at the platform level (§4) but not yet mapped to
                a specialist. HubSpot is candidate for a future specialist
                when write capabilities expand; n8n is scoping per §10 Q1.
```

> **Review loops:** Every specialist delegation is wrapped in a review loop (Generator–Critic pattern via ADK `LoopAgent`) that enforces acceptance criteria before returning results. See [AH-PRD-01](./projects/AH-PRD-01-review-loop-framework.md) for the single-step execution plan and [`docs/design/review-loop-implementation-plan.md`](../../review-loop-implementation-plan.md) §3.3 + §Phase 4 for multi-step workflow composition (deferred to R3).

> **Skills:** ADK Skills provide procedural instructions for HOW to use tools (step-by-step workflows, best practices). A skill's `allowed-tools` field documents referenced tools and can narrow the specialist's roster — but only as a restriction, never granting a tool the specialist doesn't already have. See [Skills component](../skills/README.md) and [SK-PRD-02](../skills/projects/SK-PRD-02-agent-integration.md).

## 6. MCP Server Config Registry

> **Roadmap:** [AH-PRD-02 Agent Factory](./projects/AH-PRD-02-agent-factory.md) consumes this schema to assemble specialists at deploy time.

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

### Planned: Firestore Config Registry (AH-PRD-02)

```
mcp_servers/{server_id}
  |-- name: "google_ads"
  |-- url: "https://google-ads-mcp.ken-e.ai/sse"
  |-- auth_type: "oauth2"
  |-- integration_type: "mcp" | "sdk" | "provider_mcp"
  |-- specialist_categories: ["google_ads"]      # narrow per-platform; one server may
  |                                              # be referenced by multiple specialists
  |                                              # (e.g. Google Ads MCP read-only in
  |                                              # other specialists that need look-ups)
  |-- hosting: "self" | "provider"
  |-- enabled: true
```

The **agent factory** reads this config to assemble specialist agents with the right `McpToolset` instances or SDK function tools. Config-driven agent assembly happens at deploy time — see [AH-PRD-02 §5](./projects/AH-PRD-02-agent-factory.md#5-implementation-outline) for the factory build flow.

## 7. MCPServerManager Disposition

> **Roadmap:** [AH-PRD-02 Agent Factory](./projects/AH-PRD-02-agent-factory.md) — the factory absorbs what's kept from `MCPServerManager`.

The `MCPServerManager` (`app/adk/mcp_config/manager.py`) is a Sprint 3 in-process Python singleton.

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin status endpoints | **Keep** |
| Connection pooling | **Deprecated** — ADK's `MCPSessionManager` already handles pooling natively (§2). Remove when AH-PRD-02 lands. |
| LRU eviction logic | **Deprecated** — remove when AH-PRD-02 lands. |
| Config loading + auth helpers | **Reuse** — move into the agent factory. |
| YAML config | **Evolve** — extend schema, migrate to Firestore (§6). |

## 8. Read-Only Limitations and CMO Impact

> **Roadmap:** Writes require the specialists that ship in R5 (Google Ads, Meta Ads). See [README §2.6](./README.md#26-specialist-roadmap).

HubSpot MCP is currently read-only. Google Ads uses a **hybrid approach** (MCP for reads, SDK for writes). This means for a CMO saying "shift 20% of budget to Campaign X":

- **Meta Ads:** Meta Ads Specialist (R5) can execute directly — `facebook-business` SDK has full CRUD.
- **Google Ads:** Google Ads Specialist (R5) can execute directly via `google-ads` SDK function tools (campaign CRUD, budget changes, bid adjustments). Reporting and analytics use the MCP server (read-only).
- **HubSpot:** Read-only CRM pulls available via provider MCP today. Workflow creation requires manual action until HubSpot expands MCP write capabilities. Not currently assigned to a specialist.

**On SDK sharing between specialists.** The `facebook-business` SDK is a shared library dependency, not a shared tool source. If a later design needs another specialist to read Meta Ads metrics, it does so via its own curated set of SDK function tools (read-only signatures) — not via a tool-filter subset of Meta Ads Specialist's roster. Each specialist owns its own tool set; a shared SDK just means the Python package is installed once.

> For the full specialist tool source mapping, see [README §2.5](./README.md#25-tool-assignment--routing-model) and [README §2.6](./README.md#26-specialist-roadmap).

## 9. Infrastructure Summary

| Component | Count | What |
|-----------|-------|------|
| Cloud Run deployments | 2 | Google Ads MCP + GA MCP |
| Provider-hosted MCP | 1 | HubSpot (`mcp.hubspot.com`) |
| SDK dependencies | 3 | `google-ads`, `facebook-business`, `mailchimp-marketing` |
| Built-in model capabilities | 1 | Gemini code execution (no infrastructure — Google-managed) |
| Total infrastructure to maintain | 2 servers | Everything else is provider-maintained, SDK-based, or built-in |

## 10. Open Questions

1. **n8n MCP** — Account-specific automation workflows may need per-account isolation. No n8n specialist currently scoped; needs investigation before a specialist PRD can be authored.
2. **Google Ads write access timeline** — Monitor Google's roadmap. If no progress by R5 planning, the SDK-function-tools write path (`google-ads` Python library) remains the execution mechanism.
3. **ADK version bump** — Bump `google-adk>=1.26.0` to get per-invocation tool caching fix and toolset auth hooks. Current `>=1.23.0` hits the redundant `get_tools()` bug (4–5× per response instead of 1×).
4. **HubSpot specialist scoping** — Provider MCP is in place; a HubSpot Specialist would be a small R5/R6 PRD if write capabilities expand, or remain a candidate tool source that other specialists call into.
5. **Dynamic MCP server connection** — Specialist routing + factory-assembled rosters cover tool-level dynamism at deploy time, but not server-level dynamism at runtime. If different accounts need different MCP server sets, the agent factory must assemble per-account specialist configurations at session creation time (not just at deploy time). This remains out of scope — AH-PRD-02's overlay pattern covers per-account *customization* of existing specialists, not per-account *server rosters*.

### Resolved (historical)

- ~~**Per-turn `tool_filter` integration pattern** (resolved March 2026 via Experiment #4 Option 4 — `before_agent_callback` writes `tool_filter_state`).~~ **Superseded April 2026** — the entire per-turn `tool_filter` mechanism is retired. Specialists now receive a fixed ≤30-tool roster at construction. See [README §2.5](./README.md#25-tool-assignment--routing-model) for the current model.

## References

- Historical Notion Design Brief (archive): [Notion link](https://www.notion.so/31e30fd653028118bd11f4a3270e3463) — superseded by this document
- [Google Ads MCP (Official)](https://github.com/googleads/google-ads-mcp)
- [HubSpot MCP Server (Official)](https://developers.hubspot.com/mcp)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-api)
- Component README: [`./README.md`](./README.md)
- Agent factory PRD: [`./projects/AH-PRD-02-agent-factory.md`](./projects/AH-PRD-02-agent-factory.md)
- GA Specialist PRD: [`./projects/AH-PRD-03-google-analytics-specialist.md`](./projects/AH-PRD-03-google-analytics-specialist.md)
- ADK source verified: `mcp_toolset.py`, `mcp_session_manager.py`, `base_toolset.py`, `base_llm_flow.py`, `llm_agent.py`
- ADK issue [#3237](https://github.com/google/adk-python/issues/3237) — `get_tools()` redundant calls (fixed in v1.26.0 via [#3299](https://github.com/google/adk-python/pull/3299))
- ADK commit [8f3c3bf](https://github.com/google/adk-python/commit/8f3c3bfda5e14f6a37979ad3030d3f2bbc0ae1a8) — canonical tools caching
- MCP server config: `app/adk/mcp_config/config/mcp_servers.yaml`
- MCPServerManager: `app/adk/mcp_config/manager.py`
- ToolRegistry: `app/adk/tools/registry/tool_registry.py`
- Design review log: [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md)

---

## ADK 2.0 Compatibility

AH-99 probe-5 (2026-06-01) validated that `VertexAiSessionService` accepts ADK 2.0-shaped events — specifically the new `node_info` and `isolation_scope` fields introduced by task-mode and dynamic-graph dispatch — with no schema migration required. The `create`, `get`, `list`, and `delete` session operations all function correctly under ADK 2.0.

**Consequence for the MCP/toolset story:** The MCP architecture documented in this file is **unaffected by the ADK 2.0 supervisor-orchestration adoption**. `McpToolset` construction, `McpToolsetPool` lifecycle, the `cloud_run` / `zapier` `McpServerKind` paths, and OAuth header injection all continue to operate identically under the supervisor model. Per-task specialists (`mode='task'`) receive their `McpToolset` from the pool via the same `specialist_runtime.resolve_agent` path as single-specialist turns.
*Reference: `docs/spike-adk2-supervisor-orchestration-live.md` §1 probe-5 result; [AH-PRD-05](./projects/AH-PRD-05-multi-step-workflows.md) §3 Dependencies.*
