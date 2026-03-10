# Agent Hierarchy & Registry

**Version:** 1.1
**Date:** March 2026
**Status:** Canonical — reflects Sprints 1-4 implementation + design review (March 10, 2026)

---

## 1. Current Agent Tree

```
KEN-E Root Agent (LlmAgent)
├── Company News Agent (LlmAgent) — via dispatch_to_company_news()
├── Google Analytics Agent (LlmAgent) — via dispatch_to_google_analytics()
└── Strategy Supervisor (multi-agent) — separate entry point, not dispatched from root
    ├── Business Researcher + Formatter
    ├── Competitive Researcher + Formatter
    ├── Marketing Researcher + Formatter
    └── Brand Researcher + Formatter
```

### Key Files

| File | Role |
|------|------|
| `app/adk/agents/ken_e_agent.py` | Root KEN-E agent definition, InstructionProvider, tool wrappers |
| `app/adk/agents/registry.py` | Agent registry with lazy loading and Firestore config doc IDs |
| `app/adk/agents/utils/dispatch_handlers.py` | Router functions (news, GA, strategy) with `@safe_weave_op()` |
| `app/adk/agents/utils/context_loader.py` | HierarchicalContextManager, org + campaign context loading |
| `app/adk/agents/company_news_chatbot/agent.py` | Company news sub-agent |
| `app/adk/agents/google_analytics_agent_v4.py` | GA4 sub-agent with McpToolset |
| `app/adk/agents/create_strategy_docs_supervisor.py` | Strategy document generation supervisor |

## 2. Agent Registry

The agent registry (`app/adk/agents/registry.py`) provides:
- **Lazy loading** — agents are imported only on first access via `importlib`
- **Firestore config doc IDs** — each agent declares which Firestore document holds its configuration
- **Capability search** — `find_by_capability("analytics")` returns matching agents
- **Aliases** — backward-compatible names (`root_agent` → `ken_e`, `multi_agent_root` → `strategy`)

### Registered Agents

| Name | Module | Config Doc ID | Capabilities |
|------|--------|---------------|-------------|
| `ken_e` | `.ken_e_agent` | `ken_e_chatbot` | chat, marketing, news, analytics |
| `news` | `.company_news_chatbot.agent` | `company_news_agent` | news, financial |
| `google_analytics` | `.google_analytics_agent_v4` | `google_analytics_agent` | analytics, ga4 |
| `strategy` | `.create_strategy_docs_supervisor` | (8 sub-config docs) | strategy, documents |

The registry's `get_all_config_doc_ids()` method collects all config doc IDs for use by the API layer's allowlist validation.

## 3. Dispatch Pattern

KEN-E uses **function tools as trampolines** to route to sub-agents. The root agent is an `LlmAgent` with two function tools:

```python
# In ken_e_agent.py — simplified
def search_company_news(query: str, tool_context: ToolContext | None = None) -> str:
    result = dispatch_to_company_news(query, tool_context)
    return result.get("result", str(result))

def query_google_analytics(query: str, tool_context: ToolContext | None = None) -> str:
    result = dispatch_to_google_analytics(query, tool_context)
    return result.get("result", str(result))

ken_e = Agent(
    name="ken_e",
    model=model,
    instruction=_make_instruction_provider(base_instruction),
    tools=[search_company_news, query_google_analytics],
    before_agent_callback=weave_before_agent_callback,
    after_agent_callback=weave_after_agent_callback,
    before_tool_callback=adk_before_tool_callback,
    after_tool_callback=adk_after_tool_callback,
)
```

Dispatch handlers (`app/adk/agents/utils/dispatch_handlers.py`) handle:
- Tenant context injection (GA credentials from session state)
- Weave tracing via `@safe_weave_op()`
- Error handling and retry logic

## 4. InstructionProvider Pattern

ADK supports dynamic instruction injection via callables. KEN-E uses a closure-based pattern:

```python
def _make_instruction_provider(base_instruction: str) -> Callable[[ReadonlyContext], str]:
    def instruction_provider(context: ReadonlyContext) -> str:
        org_context = context.state.get("organization_context")
        if org_context:
            return f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{base_instruction}"
        return base_instruction
    return instruction_provider
```

This is called on every LLM turn, reading organization context from session state (stored at session creation time — no DB call per turn).

## 5. Firestore-Driven Configuration

Agent configuration is loaded from Firestore at agent creation time with fallback to hardcoded defaults:

```python
config, metadata = load_config_from_firestore(config_doc_id)
model = config.model
base_instruction = config.instruction or _BASE_INSTRUCTION
generate_content_config = config.generate_content_config
```

This enables changing agent behavior (instruction, model, temperature) without code deployment.

## 6. ToolRegistry's Role

The ToolRegistry (`app/adk/tools/registry/tool_registry.py`) provides a **metadata catalog** for tools:
- Load tool definitions from YAML (`app/adk/tools/registry/config/tools.yaml`)
- Query by name, category, keyword, or search string with relevance scoring
- Permission validation (required scopes)
- Generate compact ~2,000-token index via `get_index_for_context()`

### Current Role: Discovery Index

Specialist routing is the primary mechanism for tool assignment — each specialist agent has a fixed set of `McpToolset` instances. The ToolRegistry provides a searchable catalog across all tools.

### Planned Role: `tool_filter` Driver

The ToolRegistry becomes load-bearing as the driver for ADK's `tool_filter` mechanism. ADK's `BaseToolset` (parent of `McpToolset`) accepts a `tool_filter` that is evaluated on every LLM turn with `ReadonlyContext`:

```python
# Dynamic filter driven by ToolRegistry search results in session state
McpToolset(
    connection_params=SseConnectionParams(url="..."),
    tool_filter=lambda tool, ctx: tool.name in ctx.state.get("relevant_tools", []),
)
```

This enables per-turn tool selection: the root agent interprets user intent, queries the ToolRegistry for relevant tools, writes tool names to session state, and each specialist's `McpToolset` only exposes matching tools to the LLM. Tools not matching the filter are hidden from context without disconnecting from the MCP server.

This preserves the v1.0 design's `ToolDiscoveryAgent` search capability (semantic tool search across ~400 tools) while using ADK-native mechanisms instead of custom server load/unload logic.

See `docs/design/mcp-architecture.md` Section 5a for the full design.

## 7. [PLANNED] Specialist Agent Layer

The next expansion (Sprint 5-6) adds specialist agents below the root:

| Specialist | Tool Sources | Integration Type |
|-----------|-------------|-----------------|
| **Analytics** | GA MCP, Google Ads MCP | McpToolset |
| **Content** | HubSpot MCP, Mailchimp SDK | McpToolset + SDK function tools |
| **Execution** | Meta Ads SDK, Google Ads MCP | SDK function tools + McpToolset |
| **Automation** | n8n MCP | McpToolset |

See `docs/design/mcp-architecture.md` for platform integration decisions.

### Current vs Planned

| Aspect | Current | Planned |
|--------|---------|---------|
| Root agent tools | 2 function tools (news, GA) | N dispatch functions from agent factory |
| Sub-agents | Hardcoded in dispatch handlers | Config-driven via agent factory |
| Tool assignment | GA tools hardcoded on GA agent | Category-based routing from MCP config |
| Config source | YAML + Firestore (per agent) | Firestore config registry (all agents) |

## 8. [PLANNED] Agent Factory

> **Status:** No factory exists. Current agent construction is per-file factory functions (`create_ken_e_agent()`, `create_google_analytics_agent()`). `deploy_ken_e.py` imports the root agent singleton and wraps it with `App`. The factory generalizes this pattern to config-driven assembly.

### 8.1 Current Agent Construction Pattern

Each agent follows a consistent pattern today:

```python
# 1. Load config from Firestore (with hardcoded fallback)
config, metadata = load_config_from_firestore(config_doc_id)
model = config.model

# 2. Define tools (dispatch functions or McpToolset)
tools = [search_company_news, query_google_analytics]  # or [ga_toolset]

# 3. Create Agent
agent = Agent(
    name="agent_name",
    model=model,
    instruction=instruction_text_or_provider,
    tools=tools,
    before_agent_callback=weave_before_agent_callback,
    after_agent_callback=weave_after_agent_callback,
    before_tool_callback=adk_before_tool_callback,
    after_tool_callback=adk_after_tool_callback,
)
```

The factory must generalize this: config document → Agent instance, for N specialist agents.

### 8.2 Proposed Factory Assembly Flow

```
deploy_ken_e.py calls agent_factory.build_hierarchy()
  │
  ├── 1. Read specialist configs from Firestore
  │     mcp_servers/{server_id} → connection params, category, auth_type, enabled
  │     agents/{agent_id}       → instruction, model, temperature, description
  │
  ├── 2. Group MCP servers by specialist category
  │     analytics: [ga_mcp, google_ads_mcp]
  │     content:   [hubspot_mcp]
  │     execution: [google_ads_mcp]  (shared with analytics)
  │
  ├── 3. For each specialist category:
  │     ├── Create McpToolset per server
  │     │     McpToolset(
  │     │       connection_params=SseConnectionParams(url=config.url),
  │     │       header_provider=_make_header_provider(config.auth_type),
  │     │       tool_filter=_make_tool_filter(),  # reads ctx.state["relevant_tools"]
  │     │     )
  │     ├── Create SDK function tools (Meta Ads, Mailchimp) from config
  │     └── Create Agent with tools + config
  │
  ├── 4. Generate dispatch functions for root agent
  │     For each specialist: create dispatch_to_{name}() with @safe_weave_op()
  │
  ├── 5. Build root agent with dispatch functions as tools
  │
  └── 6. Build ToolRegistry index from all tool metadata (~2,000 tokens)
```

### 8.3 Config-to-Constructor Mapping

| Firestore Field | Agent Constructor Param | Notes |
|----------------|------------------------|-------|
| `agents/{id}.instruction` | `instruction=` | String or `InstructionProvider` callable |
| `agents/{id}.model` | `model=` | e.g., `gemini-2.0-flash` |
| `agents/{id}.temperature` | `generate_content_config=` | Wrapped in `GenerateContentConfig` |
| `agents/{id}.description` | `description=` | Used by ADK for routing descriptions |
| `mcp_servers/{id}.url` | `McpToolset(connection_params=SseConnectionParams(url=))` | SSE endpoint |
| `mcp_servers/{id}.auth_type` | `McpToolset(header_provider=)` | Maps to credential key in session state |
| `mcp_servers/{id}.enabled` | Include/exclude from specialist | Disabled servers are not wired |
| `mcp_servers/{id}.specialist_categories` | Groups server into specialist(s) | A server can belong to multiple specialists |

### 8.4 Header Provider Factory

Each `auth_type` maps to a session state key and header format:

```python
def _make_header_provider(auth_type: str) -> Callable[[ReadonlyContext], dict[str, str]]:
    """Create a header_provider closure for the given auth type."""
    # Maps auth_type → session state key
    CREDENTIAL_KEYS = {
        "ga_oauth": "ga_credentials",
        "google_ads_oauth": "google_ads_credentials",
        "hubspot_oauth": "hubspot_credentials",
    }
    state_key = CREDENTIAL_KEYS[auth_type]

    def header_provider(context: ReadonlyContext) -> dict[str, str]:
        creds = context.state.get(state_key, {})
        headers = {}
        if token := creds.get("access_token"):
            headers["Authorization"] = f"Bearer {token}"
        if tenant_id := creds.get("tenant_id"):
            headers["X-Tenant-ID"] = tenant_id
        return headers
    return header_provider
```

This generalizes the existing `_ga_header_provider()` pattern.

### 8.5 Limitations & Open Questions

| Concern | Current Answer |
|---------|---------------|
| **Assembly timing** | Deploy time (same as today). Factory runs in `deploy_ken_e.py`. |
| **Config changes without redeploy** | Agent instructions and model can change via Firestore (already implemented — `InstructionProvider` reads config each turn). MCP server URLs and enabled/disabled require redeploy. |
| **Hot-reload** | Not supported on Agent Engine. `agent_engines.update()` is the mechanism — preserves sessions but redeploys the agent. |
| **Per-account server sets** | Not supported in this design. All accounts see the same specialist hierarchy. If needed, factory must run at session creation time — needs separate design. |
| **Testing** | Config validation at factory build time (check all URLs resolve, auth_types map to known credential keys). Integration test: build hierarchy from test config, verify agent count and tool count. |
| **Failure at build time** | If Firestore is unreachable, fall back to bundled config snapshot (not yet implemented). |

## References

- Agent registry: `app/adk/agents/registry.py`
- Root agent: `app/adk/agents/ken_e_agent.py`
- Dispatch handlers: `app/adk/agents/utils/dispatch_handlers.py`
- Context loader: `app/adk/agents/utils/context_loader.py`
- Tool registry: `app/adk/tools/registry/tool_registry.py`
- MCP architecture: `docs/design/mcp-architecture.md`
