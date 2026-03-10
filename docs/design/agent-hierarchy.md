# Agent Hierarchy & Registry

**Version:** 1.0
**Date:** March 2026
**Status:** Canonical — reflects Sprints 1-4 implementation

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

Its role is **evolving from primary tool loading mechanism to supplementary discovery index**. Specialist routing is the primary mechanism for tool assignment; the ToolRegistry provides searchable catalog for on-the-fly tool identification.

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

The agent factory (Sprint 5-6) reads Firestore config and dynamically constructs the agent hierarchy:

1. Reads MCP server config from Firestore
2. Creates `McpToolset` per enabled server (with `tool_filter`, `header_provider`)
3. Creates `Agent` per server (with instruction, model, description from config)
4. Generates dispatch functions (with `@weave.op()`) for KEN-E root
5. Builds lightweight tool search index (~2,000 tokens)

This replaces the current hardcoded agent definitions with config-driven assembly.

## References

- Agent registry: `app/adk/agents/registry.py`
- Root agent: `app/adk/agents/ken_e_agent.py`
- Dispatch handlers: `app/adk/agents/utils/dispatch_handlers.py`
- Context loader: `app/adk/agents/utils/context_loader.py`
- Tool registry: `app/adk/tools/registry/tool_registry.py`
- MCP architecture: `docs/design/mcp-architecture.md`
