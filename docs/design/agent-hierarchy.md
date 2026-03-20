# Agent Hierarchy & Registry

**Version:** 1.8
**Date:** March 2026
**Status:** Canonical — reflects Sprints 1-4 implementation + design review (March 10-11, 2026) + ADK experiment corrections (March 18, 2026) + harness doc alignment pass (March 18, 2026) + data visualization cross-references (March 18, 2026) + Gemini code execution capability (March 18, 2026)

> **Convention:** Agents marked `[TRANSITIONAL]` exist in the current implementation but will be subsumed by a specialist agent or automation when the specialist layer is built (Sprint 5-6). `[PLANNED]` marks features not yet built.

> For a unified summary of all component responsibilities (Root Agent, InstructionProvider, Agent Registry, HierarchicalContextManager, ToolRegistry, Dispatch Handlers), see harness design doc Section 2.2.

---

## 1. Current Agent Tree

```
KEN-E Root Agent (LlmAgent)
├── Company News Agent (LlmAgent) [TRANSITIONAL] — via dispatch_to_company_news()
│     Successor: Automation Specialist (scheduled n8n workflow) + research-company-news Skill
├── Google Analytics Agent (LlmAgent) [TRANSITIONAL] — via dispatch_to_google_analytics()
│     Successor: Analytics Specialist
└── Strategy Supervisor (multi-agent) — separate entry point, not dispatched from root
    ├── Business Researcher + Formatter
    ├── Competitive Researcher + Formatter
    ├── Marketing Researcher + Formatter
    └── Brand Researcher + Formatter
```

### Key Files

| File | Role | Lifecycle |
|------|------|-----------|
| `app/adk/agents/ken_e_agent.py` | Root KEN-E agent definition, InstructionProvider, tool wrappers | Permanent |
| `app/adk/agents/registry.py` | Agent registry with lazy loading and Firestore config doc IDs | Permanent |
| `app/adk/agents/utils/dispatch_handlers.py` | Router functions (news, GA, strategy) with `@safe_weave_op()` | Permanent (dispatch targets change) |
| `app/adk/agents/utils/context_loader.py` | HierarchicalContextManager, org context loading, agent-driven section loading via `load_context_section` tool | Permanent |
| `app/adk/agents/company_news_chatbot/agent.py` | Company news sub-agent | Transitional → Automation Specialist + Skill |
| `app/adk/agents/google_analytics_agent_v4.py` | GA4 sub-agent with McpToolset | Transitional → Analytics Specialist |
| `app/adk/agents/create_strategy_docs_supervisor.py` | Strategy document generation supervisor | Permanent |

## 2. Agent Registry

The agent registry (`app/adk/agents/registry.py`) provides:
- **Lazy loading** — agents are imported only on first access via `importlib`
- **Firestore config doc IDs** — each agent declares which Firestore document holds its configuration
- **Capability search** — `find_by_capability("analytics")` returns matching agents
- **Aliases** — backward-compatible names (`root_agent` → `ken_e`, `multi_agent_root` → `strategy`)

### Registered Agents

| Name | Module | Config Doc ID | Capabilities | Lifecycle |
|------|--------|---------------|-------------|-----------|
| `ken_e` | `.ken_e_agent` | `ken_e_chatbot` | chat, marketing, news, analytics | Permanent |
| `news` | `.company_news_chatbot.agent` | `company_news_agent` | news, financial | Transitional → Automation Specialist + `research-company-news` Skill |
| `google_analytics` | `.google_analytics_agent_v4` | `google_analytics_agent` | analytics, ga4 | Transitional → Analytics Specialist |
| `strategy` | `.create_strategy_docs_supervisor` | (8 sub-config docs) | strategy, documents | Permanent |

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

> **Roadmap:** [Feature 1.1.1: Agent Config Optimization](../product-roadmap.md#feature-111-agent-config-optimization-sprint-3b-merge) — Release 1.1

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

> **Roadmap:** [Feature 1.1.4: Firestore Config Registry](../product-roadmap.md#feature-114-firestore-config-registry-preparation-for-agent-factory) — Release 1.1

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

Tool management operates at two levels. **Level 1 — Specialist Routing** (structural, deploy-time) assigns domain MCP servers to each specialist, reducing the tool space from ~400 to ~10-30. **Level 2 — `tool_filter` + ToolRegistry** (dynamic, per-turn) selects the relevant subset per turn. See harness design doc Section 4.3 for the high-level description; this section covers Level 2 internals.

### 6.1 Current: Discovery Index

Specialist routing is the primary mechanism for tool assignment — each specialist agent has a fixed set of `McpToolset` instances. The ToolRegistry provides a searchable catalog across all tools.

### 6.2 Resolved: `tool_filter` Driver

The ToolRegistry becomes load-bearing as the driver for ADK's `tool_filter` mechanism. ADK's `BaseToolset` (parent of `McpToolset`) accepts a `tool_filter` that is evaluated on every LLM turn with `ReadonlyContext`:

```python
# Dynamic filter driven by ToolRegistry search results in session state
McpToolset(
    connection_params=SseConnectionParams(url="..."),
    tool_filter=lambda tool, ctx: tool.name in ctx.state.get("relevant_tools", []),
)
```

This enables per-turn tool selection: each specialist's `before_agent_callback` runs a ToolRegistry search, writes relevant tool names to session state, and each specialist's `McpToolset` only exposes matching tools to the LLM. Tools not matching the filter are hidden from context without disconnecting from the MCP server.

> **Revised March 18, 2026** — The mechanism for writing ToolRegistry results to state is `before_agent_callback` on each specialist (not root agent dispatch alone). This fires per-turn, ensuring `tool_filter_state` stays current within multi-turn specialist conversations. See `mcp-architecture.md` Section 5a and Experiment #4. [Decision 23](https://www.notion.so/32730fd6530281999389eb3116e7585c).

See `docs/design/mcp-architecture.md` Section 5a for the full design.

## 7. [PLANNED] Specialist Agent Layer

> **Roadmap:** [Feature 2.2: Agent Factory](../product-roadmap.md#feature-22-agent-factory--phase-1), [Feature 2.3: Analytics Specialist](../product-roadmap.md#feature-23-analytics-specialist--phase-1), [Feature 3.1: Content Specialist](../product-roadmap.md#feature-31-content-specialist), [Feature 3.2: Execution Specialist](../product-roadmap.md#feature-32-execution-specialist) — Releases 2.0, 3.0

The next expansion (Sprint 5-6) adds specialist agents below the root:

| Specialist | Tool Sources | Integration Type |
|-----------|-------------|-----------------|
| **Analytics** | GA MCP, Google Ads MCP, Meta Ads SDK (reads), Gemini code execution | McpToolset + SDK function tools + built-in code execution |
| **Content** | HubSpot MCP, Mailchimp SDK | McpToolset + SDK function tools |
| **Execution** | Meta Ads SDK (reads + writes), Google Ads SDK (writes), Google Ads MCP (reads) | SDK function tools + McpToolset |
| **Automation** | n8n MCP | McpToolset |

> **Note:** The `facebook-business` SDK is available to both Analytics (read-only tools: get campaigns, get spend, get metrics) and Execution (full CRUD). `tool_filter` controls which tools each specialist sees — see `docs/design/mcp-architecture.md` Section 5a.

See `docs/design/mcp-architecture.md` for platform integration decisions.

> **Visualization artifacts:** All specialist agents have the `create_visualization()` function tool (not MCP) — a Python function tool that produces Vega-Lite chart specs and writes them to `response_artifacts` session state. See [`data-visualization.md`](data-visualization.md) Section 4 for the tool signature and implementation pattern.

> **[PLANNED] Gemini code execution:** The Analytics Specialist uses Gemini's built-in code execution — a third tool type distinct from MCP and SDK function tools. Enabled via `GenerateContentConfig.tools = [Tool(code_execution=ToolCodeExecution())]` at agent construction. Not subject to `tool_filter` (no tool definition in context). Google manages the sandbox; no infrastructure required. The Content Specialist may receive this capability later. See harness design doc Section 4.3 Tool Type Taxonomy and Section 4.4 for the full description.

### Current vs Planned

| Aspect | Current | Planned |
|--------|---------|---------|
| Root agent tools | 2 function tools (news, GA) | N dispatch functions from agent factory |
| Sub-agents | Hardcoded in dispatch handlers | Config-driven via agent factory |
| Tool assignment | GA tools hardcoded on GA agent | Category-based routing from MCP config |
| Config source | YAML + Firestore (per agent) | Firestore config registry (all agents) |

## 8. [PLANNED] Agent Factory

> **Roadmap:** [Feature 2.2: Agent Factory](../product-roadmap.md#feature-22-agent-factory--phase-1) — Release 2.0

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
  │     ├── Configure GenerateContentConfig with code execution if specialist
  │     │     config specifies code_execution_enabled=true
  │     └── Create Agent with tools + config + generate_content_config
  │
  ├── 4. Generate dispatch functions for root agent
  │     For each specialist: create dispatch_to_{name}() with @safe_weave_op()
  │     (dispatch functions build review pipelines at runtime when
  │      acceptance_criteria is provided — see Section 9.1)
  │
  ├── 5. Build root agent with dispatch functions as tools
  │
  ├── 6. Build ToolRegistry index from all tool metadata (~2,000 tokens)
  │
  └── 7. [PLANNED] Load Skills via SkillToolset
        ├── Load predefined skills from app/adk/skills/ (bundled)
        ├── Load org custom skills from GCS + Firestore (per-org)
        └── Attach SkillToolset to each specialist agent
            See harness design doc Section 6 for Skills Architecture
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
| `agents/{id}.code_execution_enabled` | `generate_content_config.tools` | If true, adds `Tool(code_execution=ToolCodeExecution())` to `GenerateContentConfig.tools` |
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

## 9. [PLANNED] Review Loop & Workflow Orchestration

> **Roadmap:** [Feature 2.1: Review Loop Framework](../product-roadmap.md#feature-21-review-loop-framework), [Feature 3.4: Multi-Step Workflows](../product-roadmap.md#feature-34-multi-step-workflows--phase-1) — Releases 2.0, 3.0

Every specialist delegation is wrapped in a **review loop** using ADK's native workflow agents. This is the execution-time complement to the structural routing described in Section 7.

> **Revised March 18, 2026** — Structural corrections based on ADK 1.26.0 experiments. Removed `SequentialAgent` wrappers inside `LoopAgent`, added `include_contents='none'` on reviewers and synthesizers, added pipeline wrappers for `ParallelAgent` branches.

### 9.1 Review Loop Pattern (Single-Step)

Uses the Generator-Critic pattern with ADK's `LoopAgent`:

```
Root Agent (LlmAgent)
│   Generates acceptance criteria, passes to tool
│
└── dispatch handler builds:

    review_loop (LoopAgent, max_iterations=3)
    ├── specialist (LlmAgent, output_key="draft")
    │     instruction: task + criteria + {review_feedback?}
    │     tools: [specialist MCP/SDK tools]
    └── reviewer (LlmAgent, output_key="review_feedback",
          include_contents='none')
          instruction: evaluate {draft} vs criteria
          tools: [exit_loop]
```

Key details:
- **No `SequentialAgent` wrapper** — `LoopAgent` iterates sub-agents sequentially and checks `escalate` between each. A `SequentialAgent` wrapper would swallow the `escalate` signal from `exit_loop`.
- **`include_contents='none'` on reviewer** — reviewer evaluates only the template-injected `{draft}`, not conversation history, for consistent evaluations.
- **`{review_feedback?}` (optional)** — on first iteration, no feedback exists. The `?` suffix resolves to empty string instead of `KeyError`.
- **Artifact evaluation** — when a specialist calls `create_visualization()`, the reviewer evaluates visualization quality alongside the text draft. Acceptance criteria can require specific chart types or data dimensions. See [`data-visualization.md`](data-visualization.md) Section 6 for the reviewer instruction template and acceptance criteria patterns.

**LLM call cost:** Each iteration makes 2 LLM calls (specialist + reviewer), yielding 2-6 calls per loop. See harness design doc Section 4.6 for the full cost table and Section 8.4 for parallel execution cost analysis.

The `build_review_pipeline()` factory in `app/adk/agents/utils/review_pipeline.py` constructs this structure. See harness design doc Section 8.2 for the `build_review_pipeline()` and `build_workflow_pipeline()` factory implementations.

### 9.2 Multi-Step Workflow Pattern

Multiple review loops compose into parallel and sequential structures. Each `LoopAgent` is wrapped in a pipeline `SequentialAgent` inside `ParallelAgent` for extensibility:

```
data_gathering (ParallelAgent)
├── step_1a_pipeline (SequentialAgent)
│   └── step_1a_loop (LoopAgent)
│       ├── analytics_specialist (output_key="step_1a_draft")
│       │     instruction: task + criteria + {step_1a_feedback?}
│       └── reviewer (include_contents='none', output_key="step_1a_feedback")
│
└── step_1b_pipeline (SequentialAgent)
    └── step_1b_loop (LoopAgent)
        ├── execution_specialist (output_key="step_1b_draft")
        │     instruction: task + criteria + {step_1b_feedback?}
        └── reviewer (include_contents='none', output_key="step_1b_feedback")

synthesizer (LlmAgent, include_contents='none')
  instruction: "You are given completed research from parallel analyses.
                Analytics findings: {step_1a_draft}
                Spend data: {step_1b_draft}"

→ Root Agent presents synthesis to user for approval

step_3_pipeline (SequentialAgent)  — runs after user approval
└── step_3_loop (LoopAgent)
    ├── execution_specialist (output_key="step_3_draft")
    │     instruction: approved plan + {step_3_feedback?}
    └── reviewer (include_contents='none', output_key="step_3_feedback")
```

Key details:
- **Pipeline wrappers** — each `LoopAgent` is wrapped in a `SequentialAgent` inside `ParallelAgent`, allowing future pre/post steps per branch.
- **Dedicated synthesizer** — uses `include_contents='none'` with a strong instruction framing injected data as "completed research." Without this, the synthesizer sees all conversation history from parallel branches.
- **`SequentialAgent` only outside `LoopAgent`** — used for pipeline wrapping and phase chaining, never inside `LoopAgent` (which handles sequential iteration natively).

The `build_workflow_pipeline()` factory reads a dependency graph to construct the appropriate `ParallelAgent` / `SequentialAgent` composition. See harness design doc Section 8.2 for the full factory implementation and Section 8.3 for validated ADK pitfalls.

### 9.3 Key Files

| File | Role |
|------|------|
| `app/adk/agents/utils/review_pipeline.py` | [PLANNED] Pipeline factories: `build_review_pipeline()`, `build_workflow_pipeline()` |
| `app/adk/agents/utils/dispatch_handlers.py` | [MODIFY] Add `acceptance_criteria` parameter, build review pipelines |
| `app/adk/agents/utils/supervisor_utils.py` | [MODIFY] Extract `output_key` values from session state after pipeline runs |
| `app/adk/agents/ken_e_agent.py` | [MODIFY] Add `acceptance_criteria` to tool functions, add `execute_workflow` tool |

See [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e) and the harness design doc Sections 4.6 and 8 for full details.

## References

- Agent registry: `app/adk/agents/registry.py`
- Root agent: `app/adk/agents/ken_e_agent.py`
- Dispatch handlers: `app/adk/agents/utils/dispatch_handlers.py`
- Context loader: `app/adk/agents/utils/context_loader.py`
- Tool registry: `app/adk/tools/registry/tool_registry.py`
- MCP architecture: `docs/design/mcp-architecture.md`
