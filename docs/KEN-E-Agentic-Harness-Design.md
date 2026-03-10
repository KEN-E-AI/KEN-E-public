# KEN-E Agentic Harness Design Document

**Version:** 2.1
**Date:** March 10, 2026
**Author:** Development Team

> **v2.1 Revision Note (March 10, 2026):** Added `tool_filter` + ToolRegistry
> architecture for dynamic per-turn tool selection (Section 4.3). Updated ADK
> internals analysis with version-specific behavior. Added sprint-3b dependency
> note.

> **v2.0 Revision Note (March 2026):** This document has been updated to reflect
> 4 sprints of implementation. Fictional code examples have been replaced with
> references to actual implementations. Sections covering features not yet built
> are marked `[PLANNED]` with architectural concepts preserved but fictional code
> removed. See the Document History at the end for details.

> **Dependency Note:** Several features described in this document (InstructionProvider
> closure, agent registry, ReflectAndRetryToolPlugin, token_threshold in compaction
> config) exist on the `feat/sprint-3b-agent-config-optimization` branch (PR #217)
> but have not yet been merged to main. These are noted where relevant.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Context Management Strategy](#3-context-management-strategy)
4. [Agent Definitions](#4-agent-definitions)
5. [MCP Server Architecture](#5-mcp-server-architecture)
6. [Multi-Channel Support [PLANNED]](#6-multi-channel-support-planned)
7. [Workflow Management [PLANNED]](#7-workflow-management-planned)
8. [Integration with Evaluation Framework](#8-integration-with-evaluation-framework)
9. [Infrastructure Requirements](#9-infrastructure-requirements)
10. [Risks and Testing Requirements](#10-risks-and-testing-requirements)
11. [Sprint-Based Roadmap](#11-sprint-based-roadmap)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the comprehensive design for KEN-E's agentic harness — the software framework that enables KEN-E to function as an autonomous AI marketing agent. The harness orchestrates multiple specialized agents using Google's Agent Development Kit (ADK) to complete complex marketing tasks including strategy development, content creation, campaign execution, and performance optimization.

### 1.2 Critical Design Challenges

The agentic harness must solve three primary challenges:

| Challenge | Scale | Impact |
|-----------|-------|--------|
| **Massive Tool Inventory** | ~400 tools across 20-40 MCP servers | Tool definitions alone could consume 60,000+ tokens |
| **Large Context Requirements** | ~100,000 words of company knowledge | Leaves minimal room for conversation |
| **Multi-Step Autonomous Workflows** | Tasks spanning days/weeks | Requires persistent state and scheduled execution |

### 1.3 Solution Overview

The design implements a **Hierarchical Agent Architecture with Dynamic Context Loading**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       KEN-E AGENTIC HARNESS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                  ORCHESTRATOR LAYER                            │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │     │
│  │  │  KEN-E Root │  │   Context   │  │  Tool Registry      │   │     │
│  │  │   Agent     │  │   Loader    │  │  (Discovery Index)  │   │     │
│  │  │  (LlmAgent) │  │             │  │                     │   │     │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                │                                       │
│                                ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              CURRENT SUB-AGENT LAYER                          │     │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────────────────┐   │     │
│  │  │   News    │ │  Google   │ │  Strategy Supervisor      │   │     │
│  │  │   Agent   │ │ Analytics │ │  (multi-agent)            │   │     │
│  │  │           │ │   Agent   │ │                           │   │     │
│  │  └───────────┘ └───────────┘ └───────────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                │                                       │
│                                ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              [PLANNED] SPECIALIST LAYER (Sprint 5-6)          │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐    │     │
│  │  │Analytics │ │ Content  │ │Execution │ │  Automation  │    │     │
│  │  │Specialist│ │Specialist│ │Specialist│ │  Specialist  │    │     │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                │                                       │
│                                ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              TOOL & INTEGRATION LAYER                         │     │
│  │  ┌───────────────────────────────────────────────────────┐   │     │
│  │  │          MCP Servers (Lazy-Loaded via McpToolset)      │   │     │
│  │  │  GA MCP (Cloud Run) | Google Ads MCP | HubSpot MCP   │   │     │
│  │  └───────────────────────────────────────────────────────┘   │     │
│  │  ┌───────────────────────────────────────────────────────┐   │     │
│  │  │          SDK Function Tools                            │   │     │
│  │  │  Meta Ads (facebook-business) | Mailchimp SDK         │   │     │
│  │  └───────────────────────────────────────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Specialist routing for token budgets** | Each specialist agent sees only its domain tools (~10-30), not all 400 |
| **ADK native compaction** | `EventsCompactionConfig` with `gemini-2.5-flash` summarizer handles long sessions |
| **`McpToolset` for MCP connections** | ADK handles lazy loading, connection pooling, per-user auth natively |
| **SDK function tools for some platforms** | Meta Ads + Mailchimp use SDK directly — no MCP server to deploy/maintain |
| **Firestore-driven agent config** | Instructions, model, temperature stored in Firestore — change without redeployment |
| **Config-driven agent factory** | Sprint 5-6: reads config to dynamically assemble specialist agents with correct tools |

### 1.5 Expected Outcomes

| Metric | Target |
|--------|--------|
| Initial context consumption | <20% of available context |
| Tool discovery latency | <500ms |
| Task completion rate | >95% |
| Agent response (simple) | ~7-13s (measured) |

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT INTERFACES                               │
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐     │
│   │  Web UI     │     │   Slack     │     │     Voice           │     │
│   │app.ken-e.ai │     │ [PLANNED]  │     │   [PLANNED]         │     │
│   └──────┬──────┘     └──────┬──────┘     └─────────┬───────────┘     │
└──────────┼───────────────────┼──────────────────────┼─────────────────┘
           │                   │                      │
           └───────────────────┴──────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI (Cloud Run)                                   │
│                                                                         │
│   POST /api/v1/chat/completions                                        │
│   • Firebase Auth validation                                           │
│   • Session management (pending → ADK session resolution)              │
│   • GA credential injection into session state                         │
│   • Background post-response writes (session preview + Redis)          │
│                                                                         │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 VERTEX AI AGENT ENGINE                                   │
│                                                                         │
│   KEN-E Root Agent (LlmAgent)                                          │
│   ├── InstructionProvider (org context from session state)              │
│   ├── Firestore config (model, instruction, temperature)               │
│   ├── Weave callbacks (before/after agent, after tool)                 │
│   ├── Security hooks (before tool)                                     │
│   │                                                                     │
│   ├── search_company_news → News Agent (LlmAgent)                     │
│   ├── query_google_analytics → GA Agent (LlmAgent + McpToolset)       │
│   └── [Strategy Supervisor — separate entry point]                     │
│                                                                         │
│   EventsCompactionConfig: interval=5, overlap=1, threshold=50K tokens  │
│   ContextCacheConfig: enabled                                          │
│   ReflectAndRetryToolPlugin: enabled                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
             ┌───────────┐  ┌───────────┐  ┌───────────┐
             │  Neo4j    │  │ Firestore │  │   GA MCP  │
             │ Knowledge │  │  Config,  │  │  Server   │
             │   Graph   │  │   State   │  │(Cloud Run)│
             └───────────┘  └───────────┘  └───────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **KEN-E Root Agent** | LlmAgent that interprets user intent, routes via function tools to sub-agents |
| **InstructionProvider** | Closure that injects org context from session state on each LLM turn |
| **Agent Registry** | Lazy-loading registry with Firestore config doc IDs and capability search |
| **HierarchicalContextManager** | 3-level context loading from Neo4j with token budgeting |
| **ToolRegistry** | Searchable metadata catalog (~2,000 token index) for tool discovery |
| **Dispatch Handlers** | Function tool implementations with Weave tracing and tenant context injection |

### 2.3 Request Flow

```
User Request: "Show me website traffic for last week"

    ┌─────────────┐
    │   Web UI    │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 1. FASTAPI (Cloud Run)                                   │
    │    • Validate Firebase Auth token                        │
    │    • Resolve session (pending_* → ADK session)           │
    │    • Inject GA credentials into session state            │
    │    • Forward to Agent Engine                             │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 2. KEN-E ROOT AGENT                                      │
    │    • InstructionProvider loads org context from state    │
    │    • LLM interprets intent: "analytics" + "traffic"     │
    │    • Calls query_google_analytics(query)                 │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 3. DISPATCH TO GA AGENT                                  │
    │    • dispatch_to_google_analytics() in dispatch_handlers │
    │    • Injects GA credentials from session state           │
    │    • @safe_weave_op() records trace                      │
    │    • GA Agent uses McpToolset → GA MCP Server            │
    │    • MCP server queries GA4 API                          │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 4. RESPONSE                                              │
    │    • GA Agent returns formatted analytics data           │
    │    • KEN-E relays to user                                │
    │    • Background: update session preview + Redis cache    │
    └─────────────────────────────────────────────────────────┘
```

### 2.4 Agent Type Selection (Google ADK)

| Agent | ADK Type | Status | Rationale |
|-------|----------|--------|-----------|
| **KEN-E Root** | `LlmAgent` | Implemented | Flexible routing via function tools |
| **Company News** | `LlmAgent` | Implemented | Vertex AI Search integration |
| **Google Analytics** | `LlmAgent` + `McpToolset` | Implemented | GA MCP server via SSE |
| **Strategy Supervisor** | Multi-agent (custom) | Implemented | Orchestrates 8 researcher/formatter sub-agents |
| **Analytics Specialist** | `LlmAgent` | [PLANNED] | GA + Google Ads + Meta tools |
| **Content Specialist** | `LlmAgent` | [PLANNED] | HubSpot + Mailchimp tools |
| **Execution Specialist** | `LlmAgent` | [PLANNED] | Meta Ads SDK + Google Ads MCP |
| **Automation Specialist** | `LlmAgent` | [PLANNED] | n8n MCP |

---

## 3. Context Management Strategy

### 3.1 The Context Challenge

KEN-E faces an unprecedented context management challenge:

```
NAIVE APPROACH (No Optimization):
  Company knowledge graph (100k words)     ~ 133,000 tokens  (66.5%)
  Tool definitions (400 tools x 150 avg)   ~  60,000 tokens  (30.0%)
  System prompts & instructions            ~   5,000 tokens  ( 2.5%)
  TOTAL BEFORE CONVERSATION                ~ 198,000 tokens  (99.0%)
  Available for conversation               ~   2,000 tokens  ( 1.0%)

OPTIMIZED APPROACH (With HCL + Specialist Routing):
  Hierarchical context summary             ~  15,000 tokens  ( 7.5%)
  Tool registry index                      ~   2,000 tokens  ( 1.0%)
  System prompts & instructions            ~   5,000 tokens  ( 2.5%)
  Active tools (loaded on-demand)          ~   5,000 tokens  ( 2.5%)
  TOTAL BEFORE CONVERSATION                ~  27,000 tokens  (13.5%)
  Available for conversation               ~ 173,000 tokens  (86.5%)
```

### 3.2 Hierarchical Context Loading (HCL)

The company knowledge graph is organized into a three-level hierarchy:

```
LEVEL 1: EXECUTIVE SUMMARY (~5,000 tokens) - Always Loaded
  Company overview, mission, products, ICPs, competitors, active campaigns,
  current focus, key KPIs

LEVEL 2: SECTION SUMMARIES (~10,000 tokens each) - Loaded on Request
  [products] [icps] [competitors] [campaigns] [strategies] [brand]
  [performance] [calendar]

LEVEL 3: FULL DETAIL (~20,000+ tokens each) - Loaded for Specific Tasks
  Complete documentation for individual entities
```

### 3.3 Context Loading Implementation

The `HierarchicalContextManager` at `app/adk/agents/utils/context_loader.py` implements the 3-level hierarchy:

```python
class HierarchicalContextManager:
    """Manages hierarchical loading of company context to optimize token usage.

    Implements 3-level hierarchy:
    - Level 1: Executive Summary (~5,000 tokens) - Always loaded
    - Level 2: Section Summaries (~10,000 tokens each) - Loaded on request
    - Level 3: Full Detail (~20,000 tokens each) - Loaded for specific tasks
    """

    MAX_EXECUTIVE_TOKENS: ClassVar[int] = 5_000
    MAX_SECTION_TOKENS: ClassVar[int] = 10_000
    MAX_DETAIL_TOKENS: ClassVar[int] = 20_000
```

**Implementation status:**
- Level 1 (Executive Summary): Implemented — loads org + brand context from Neo4j
- Level 2 (Section Summaries): Implemented — campaign context loaded on-demand via keyword detection
- Level 3 (Full Detail): Not yet implemented

The canonical Neo4j query for org context is defined in `shared/context_utils.py` (`ORG_CONTEXT_QUERY`), shared between the API and agent layers. Section keyword detection uses `SECTION_KEYWORDS` and `CAMPAIGN_KEYWORDS` from the same module.

### 3.4 Context-Aware Agent Instructions

The KEN-E root agent uses an `InstructionProvider` pattern (see `app/adk/agents/ken_e_agent.py`):

```python
def _make_instruction_provider(base_instruction: str) -> Callable[[ReadonlyContext], str]:
    """Create a closure-based InstructionProvider."""
    def instruction_provider(context: ReadonlyContext) -> str:
        org_context = context.state.get("organization_context")
        if org_context:
            return f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{base_instruction}"
        return base_instruction
    return instruction_provider
```

This is called on every LLM turn, reading organization context from session state (stored at session creation time — no DB call per turn).

### 3.5 Session Compaction (ADK Native)

Long-running sessions are automatically compacted using ADK's `EventsCompactionConfig`, configured in `app/adk/deploy_ken_e.py`:

```python
compaction_summarizer = LlmEventSummarizer(
    llm=Gemini(model="gemini-2.5-flash")
)
compaction_config = EventsCompactionConfig(
    summarizer=compaction_summarizer,
    compaction_interval=5,        # Compact every 5 user invocations
    overlap_size=1,               # Include 1 prior invocation for context continuity
    token_threshold=50000,        # Also compact when session exceeds 50K tokens
    event_retention_size=10,      # Keep last 10 raw events un-compacted
)
```

This replaces the originally-planned custom `ContextCompressor` class. ADK handles summarization, retention, and token budgeting natively.

### 3.6 Session State Management

ADK session state is used for context tracking with key prefixes:

| Key | Purpose | Set By |
|-----|---------|--------|
| `organization_context` | Org + brand context text | API at session creation |
| `ga_credentials` | Google Analytics OAuth tokens | API from Firebase Auth |
| `user_id`, `account_id`, `org_id` | Identity context | API at session creation |

The API layer (`api/src/kene_api/routers/chat.py`) manages session state injection. The `InstructionProvider` reads from state per-turn. No custom `ContextStateManager` class was needed — ADK's native state management is sufficient.

---

## 4. Agent Definitions

### 4.1 Agent Hierarchy

The current agent hierarchy, dispatch patterns, and the planned specialist layer:

```
CURRENT (Sprints 1-4):

    KEN-E Root Agent (LlmAgent)
    ├── Company News Agent (LlmAgent) — dispatch_to_company_news()
    ├── Google Analytics Agent (LlmAgent + McpToolset) — dispatch_to_google_analytics()
    └── Strategy Supervisor (multi-agent) — separate entry point
        ├── Business Researcher + Formatter
        ├── Competitive Researcher + Formatter
        ├── Marketing Researcher + Formatter
        └── Brand Researcher + Formatter


[PLANNED] (Sprint 5-6 — Specialist Layer):

    KEN-E Root Agent
    ├── [current agents]
    ├── Analytics Specialist (GA MCP, Google Ads MCP)
    ├── Content Specialist (HubSpot MCP, Mailchimp SDK)
    ├── Execution Specialist (Meta Ads SDK, Google Ads MCP)
    └── Automation Specialist (n8n MCP)
```

### 4.2 KEN-E Root Agent

The root agent (`app/adk/agents/ken_e_agent.py`) is an ADK `LlmAgent` that:

1. **Loads config from Firestore** — model, instruction, temperature via `load_config_from_firestore(config_doc_id)`
2. **Uses InstructionProvider** — `_make_instruction_provider()` injects org context from session state per-turn
3. **Routes via function tools** — `search_company_news` and `query_google_analytics` are Python functions that dispatch to sub-agents
4. **Has ADK callbacks** — `weave_before_agent_callback`, `weave_after_agent_callback`, `adk_before_tool_callback`, `adk_after_tool_callback`

```python
ken_e = Agent(
    name="ken_e",
    model=model,                                        # From Firestore config
    description=description,
    instruction=_make_instruction_provider(base_instruction),
    generate_content_config=generate_content_config,    # From Firestore config
    before_agent_callback=weave_before_agent_callback,
    after_agent_callback=weave_after_agent_callback,
    before_tool_callback=adk_before_tool_callback,
    after_tool_callback=adk_after_tool_callback,
    tools=[search_company_news, query_google_analytics],
)
```

### 4.3 Tool Discovery & Dynamic Tool Selection

Tool management operates at two levels:

**Level 1 — Specialist Routing (structural, deploy-time):** Each specialist agent receives only its domain MCP servers via `McpToolset` instances, wired at agent construction. This reduces the tool space from ~400 to ~10-30 per specialist.

**Level 2 — `tool_filter` + ToolRegistry (dynamic, per-turn):** ADK's `BaseToolset` accepts a `tool_filter` predicate evaluated on every LLM turn. Combined with the ToolRegistry's search capabilities, this enables exposing only the relevant subset of a specialist's tools on any given turn.

The **ToolRegistry** (`app/adk/tools/registry/tool_registry.py`) provides:

- Tool metadata catalog loaded from YAML (`app/adk/tools/registry/config/tools.yaml`)
- Search by name, category, keyword with relevance scoring
- Compact ~2,000-token index via `get_index_for_context()`
- Permission validation (required OAuth scopes)
- **[PLANNED] `tool_filter` driver** — search results written to session state, read by `McpToolset` `tool_filter` predicates per-turn

This architecture preserves the v1.0 design's `ToolDiscoveryAgent` capability (semantic search across ~400 tools, per-turn tool selection, token budget awareness) using ADK-native mechanisms rather than custom server load/unload logic. The key limitation is that MCP server connections are fixed at deploy time — only *which tools* are visible is dynamic per-turn.

### 4.4 [PLANNED] Specialist Agents

The specialist layer (Sprint 5-6) partitions tools by domain.

| Specialist | Tool Sources | Integration Type | Key Capabilities |
|-----------|-------------|-----------------|------------------|
| **Analytics** | GA MCP, Google Ads MCP | McpToolset | Data queries, reporting, performance analysis |
| **Content** | HubSpot MCP, Mailchimp SDK | McpToolset + SDK | CRM data, email campaigns, content management |
| **Execution** | Meta Ads SDK, Google Ads MCP | SDK + McpToolset | Campaign deployment, budget management |
| **Automation** | n8n MCP | McpToolset | Workflow creation, scheduling |

Each specialist will be assembled by the config-driven agent factory, reading from Firestore config.

### 4.5 Agent Summary Table

| Agent | Type | Status | Config Doc ID | Key Files |
|-------|------|--------|---------------|-----------|
| KEN-E Root | LlmAgent | Implemented | `ken_e_chatbot` | `app/adk/agents/ken_e_agent.py` |
| Company News | LlmAgent | Implemented | `company_news_agent` | `app/adk/agents/company_news_chatbot/agent.py` |
| Google Analytics | LlmAgent + McpToolset | Implemented | `google_analytics_agent` | `app/adk/agents/google_analytics_agent_v4.py` |
| Strategy Supervisor | Multi-agent | Implemented | 8 sub-config docs | `app/adk/agents/create_strategy_docs_supervisor.py` |
| Analytics Specialist | LlmAgent | [PLANNED] | — | — |
| Content Specialist | LlmAgent | [PLANNED] | — | — |
| Execution Specialist | LlmAgent | [PLANNED] | — | — |
| Automation Specialist | LlmAgent | [PLANNED] | — | — |

---

## 5. MCP Server Architecture

### 5.1 Lazy-Loading

Lazy-loading MCP servers is the foundation of the token budget strategy:

| Approach | Initial Tokens | Load Time | Recommendation |
|----------|---------------|-----------|----------------|
| **Pre-load all** | ~60,000 tokens | 5-10s | Not recommended |
| **Lazy-load on demand** | ~2,000 tokens | 200-500ms per server | Recommended |

ADK's `McpToolset` handles lazy-loading natively — SSE connections open on first `get_tools()` call, not at deploy time. No custom lazy-loading code is needed.

### 5.2 Tool Registry

The ToolRegistry (`app/adk/tools/registry/tool_registry.py`) is implemented infrastructure from Sprint 2. It provides:

- **Metadata catalog** — tool definitions loaded from `app/adk/tools/registry/config/tools.yaml`
- **Search** — query by name, category, keyword with relevance scoring
- **Compact index** — `get_index_for_context()` generates ~2,000 token summary for agent context
- **Permission validation** — checks required OAuth scopes

Currently defines ~9 Google Analytics tools.

### 5.3 MCPServerManager

The `MCPServerManager` at `app/adk/mcp_config/manager.py` was built in Sprint 3 as an in-process Python singleton. After architecture review:

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin endpoints | **Keep** — operational tooling at API layer |
| Connection pooling | **Deprecated** — ADK `MCPSessionManager` pools by header hash |
| LRU eviction logic | **Deprecated** — not applicable on serverless Agent Engine |
| Config loading + auth helpers | **Reuse** — foundation for agent factory |

### 5.4 MCP Server Configuration

Server configs are defined in `app/adk/mcp_config/config/mcp_servers.yaml`:

```yaml
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

  hubspot_mcp:
    description: "HubSpot CRM contacts, deals, and marketing automation"
    category: "crm"
    tool_count: 18
    estimated_tokens: 2700
    keywords: [crm, contacts, deals, pipeline, marketing, hubspot]
    connection:
      connection_type: sse
      url: "${HUBSPOT_MCP_URL}"
      headers:
        Authorization: "Bearer ${HUBSPOT_API_KEY}"
      timeout_seconds: 30
    enabled: false
```

Currently defines 6 servers (1 enabled: Google Analytics). The schema will evolve to include agent config, tool_filter, and dispatch configuration for the agent factory.

---

## 6. Multi-Channel Support [PLANNED]

### 6.1 Architecture Overview

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│     WEB UI      │   │      SLACK      │   │     VOICE       │
│  app.ken-e.ai   │   │  [PLANNED]      │   │  [PLANNED]      │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         └─────────────────────┴──────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  KEN-E API (FastAPI)                          │
│            POST /api/v1/chat/completions                    │
│            (Channel-agnostic endpoint)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Vertex AI Agent Engine                           │
│            (Same agents for all channels)                    │
└─────────────────────────────────────────────────────────────┘
```

The current API is already channel-agnostic — any new channel only needs an auth adapter, input normalizer, and output formatter. The Agent Engine call path does not change.

### 6.2 Unified Message Format

The target design uses a channel-agnostic message format internally. All channel adapters convert to/from this format:

| Field | Purpose |
|-------|---------|
| `message_id` | Unique identifier |
| `channel` | web, slack, voice |
| `user_id` | Unified KEN-E user ID |
| `account_id` | KEN-E account |
| `text` | Message content |
| `attachments` | Files, images |
| `thread_id` | For threaded conversations |
| `channel_context` | Channel-specific metadata |

### 6.3 Channel Integration Plans

| Channel | Framework | Deployment | Timeline |
|---------|-----------|------------|----------|
| **Web** | React SPA | Firebase Hosting | Implemented |
| **Slack** | Bolt SDK | Separate Cloud Run | Sprint 8+ |
| **Voice** | Pipecat + Meeting BaaS | Dedicated service | Phase 4 |

### 6.4 Voice Channel Notes

Voice-enabled meeting participation is technically feasible using:
- **Meeting Bot API**: Recall.ai or Meeting BaaS
- **STT**: Deepgram (sub-300ms streaming latency)
- **TTS**: Cartesia (sub-100ms TTFB) or Deepgram Aura (sub-200ms TTFB)
- **Framework**: Pipecat for pipeline orchestration

Key considerations: voice responses must be concise (< 30s), target < 2s end-to-end latency, need speaker diarization. Estimated cost: ~$1.20/hour per meeting.

---

## 7. Workflow Management [PLANNED]

> **Status:** No workflow framework exists in the codebase today. The strategy agent's `execute_strategy_generation()` orchestrator is the closest pattern — it coordinates multiple sub-agents in sequence with Firestore persistence. No n8n, webhook, or cron infrastructure exists.

### 7.1 Multi-Step Workflow Pattern

KEN-E will handle complex, multi-step workflows with the pattern:
1. **Plan** the workflow with clear steps
2. **Track** progress visibly to the user
3. **Get approval** at decision points
4. **Resume** where left off if interrupted

Example: "Launch a Q2 campaign for Product X"
→ Research competitors (Analytics Specialist)
→ Generate campaign strategy (Strategy Supervisor)
→ Create ad copy variations (Content Specialist)
→ **[Approval checkpoint]** — user reviews strategy + copy
→ Deploy to Meta Ads (Execution Specialist)
→ Set up weekly performance reporting (Automation Specialist)

### 7.2 Workflow State Machine

```
        CREATED → PLANNING → AWAITING_APPROVAL → IN_PROGRESS → COMPLETED
            │         ↑              │                  │            │
            │         └──────────────┘                  │            │
            │        (User requests changes)            │            │
            │                                           ↓            │
            │                                 ┌─── Executing Step    │
            │                                 ├─── Awaiting Input    │
            │                                 └─── Step Failed       │
            │                                          │             │
            │                                          ▼             │
            └────────────────────────────────── FAILED ◄─────────────┘
                                              (after max retries)
```

### 7.3 Workflow Data Model

```
Firestore: workflows/{workflow_id}
  |-- account_id: str
  |-- user_id: str
  |-- title: str
  |-- status: CREATED | PLANNING | AWAITING_APPROVAL | IN_PROGRESS | COMPLETED | FAILED
  |-- created_at: timestamp
  |-- updated_at: timestamp
  |-- session_id: str  (ADK session for conversation context)
  |-- steps: [
  |     {
  |       step_id: str,
  |       title: str,
  |       specialist: "analytics" | "content" | "execution" | "automation",
  |       status: PENDING | IN_PROGRESS | COMPLETED | FAILED | SKIPPED,
  |       depends_on: [step_id, ...],
  |       inputs: dict,
  |       outputs: dict | null,
  |       error: str | null,
  |       attempts: int,
  |       started_at: timestamp | null,
  |       completed_at: timestamp | null,
  |     }
  |   ]
  |-- approval_checkpoints: [step_id, ...]  (steps requiring user approval before proceeding)
```

### 7.4 Persistence & Recovery

| Concern | Approach |
|---------|----------|
| **Crash recovery** | Workflow state persisted to Firestore after each step transition. On recovery, resume from last completed step. |
| **Idempotency** | Each step execution keyed by `(workflow_id, step_id, attempt)`. Before executing, check if output already exists for this attempt. |
| **Partial failure** | Individual step failure marks step as FAILED, increments `attempts`. If `attempts < max_retries`, re-queue. If exhausted, mark workflow as FAILED with last error. |
| **User interruption** | Steps in AWAITING_INPUT pause workflow. User response writes to `step.inputs` and transitions step to IN_PROGRESS. |
| **Long-running steps** | Steps that take >30s (e.g., strategy generation) execute asynchronously. Workflow polls step status. Frontend shows progress. |

### 7.5 [PLANNED] n8n Integration

> **Status:** No n8n infrastructure exists. This is Sprint 8+ work.

For scheduled/recurring tasks (e.g., "send me a weekly performance report every Monday"):

```
KEN-E creates workflow → n8n workflow created via n8n API
                          |-- Schedule trigger (cron)
                          |-- Webhook step → POST /api/v1/workflows/{id}/execute
                          |-- KEN-E executes workflow steps
                          |-- n8n sends notification on completion
```

| Concern | Approach |
|---------|----------|
| **Workflow templates** | n8n workflows created from KEN-E-defined templates (schedule → webhook → notify) |
| **Webhook authentication** | n8n webhook calls KEN-E API with service account token (not user OAuth) |
| **Callback mapping** | Webhook payload includes `workflow_id` and `step_id` → KEN-E looks up Firestore workflow and resumes |
| **Per-account isolation** | Each account's n8n workflows scoped by `account_id`. One n8n instance, workflows isolated by credential. |
| **Failure notification** | n8n error handler → Slack/email notification to user + mark workflow as FAILED in Firestore |

---

## 8. Integration with Evaluation Framework

### 8.1 Overview

The agentic harness integrates with the Self-Improving Evaluation Framework (MER-E) to enable:
1. **Automatic tracing** of all agent outputs via Weave
2. **Quality scoring** via LLM-based evaluation
3. **Human feedback collection** for alignment
4. **Continuous improvement** of agent prompts

### 8.2 Trace Instrumentation

Tracing is implemented using Weave SDK with ADK callbacks, defined in `app/adk/tracking/callbacks.py`:

- **`weave_before_agent_callback()`** — creates parent Weave span wrapping entire agent invocation
- **`weave_after_agent_callback()`** — finishes parent span with output metadata
- **`adk_after_tool_callback()`** — records tool execution status (SUCCESS, PERMISSION_DENIED, RATE_LIMITED, TIMEOUT, FAILURE)

Weave initialization is in `app/utils/weave_observability.py`:
- `init_weave_if_needed()` — thread-safe singleton initialization
- `safe_weave_op()` — conditional decorator (no-op if Weave unavailable)
- `sanitize_sensitive_data()` — hash-based redaction before logging

The trace hierarchy follows the contract in `docs/trace-structure-spec.md`:

```
Root: Session Invocation
├── L1: Orchestrator Agent Run (KEN-E)
│   ├── L2: Sub-Agent Run (e.g., google_analytics_agent)
│   │   ├── L3: LLM Call (Gemini)
│   │   ├── L3: Tool Call (adk.tool.run_report_mt)
│   │   └── L3: Tool Call (adk.tool.get_account_summaries_mt)
```

### 8.3 Output Type Classification

Output classification is implemented via `OUTPUT_CATEGORIES` in `app/adk/agents/strategy_agent/constants.py`. Each strategy type maps to semantic output categories for MER-E trace-rule matching:

```python
OUTPUT_CATEGORIES = {
    "business_strategy": {
        "research": "business_strategy.google_search",
        "report": "business_strategy.research_report",
    },
    # ... per strategy type
}
```

### 8.4 [PLANNED] Feedback Collection

A feedback collection system will enable human evaluation alignment:
- Queue feedback requests for users after agent outputs
- Store ratings (1-5) and factor-level ratings in Firestore
- Trigger alignment analysis when sufficient feedback is collected

### 8.5 [PLANNED] A/B Testing Support

The harness will support A/B testing of agent configurations:
- Consistent hash-based variant assignment per account
- Firestore-stored variant configurations
- Trace metadata includes `experiment_id` and `variant_name` for evaluation

---

## 9. Infrastructure Requirements

### 9.1 Compute Requirements

| Component | Specification | Scaling |
|-----------|--------------|---------|
| **API Server (Cloud Run)** | 4 vCPU, 8GB RAM | 2-10 instances based on load |
| **Agent Engine (Vertex AI)** | Managed by Google | Auto-scaled |
| **GA MCP Server (Cloud Run)** | 2 vCPU, 4GB RAM | On-demand |

### 9.2 Cost Estimates

#### Usage Tier Definitions

| Tier | Accounts | Requests/Day | Specialist Calls/Request | Tokens/Request (est.) |
|------|----------|-------------|-------------------------|----------------------|
| **Light** | 1-5 | 50-100 | 1-2 | ~5,000 |
| **Moderate** | 10-25 | 500-1,000 | 2-3 | ~8,000 |
| **Heavy** | 50+ | 5,000+ | 3-5 | ~15,000 |

#### Moderate Tier Cost Breakdown

| Resource | Unit Cost | Est. Monthly Usage | Monthly Cost |
|----------|-----------|-------------------|--------------|
| **Gemini 2.0 Flash** | $0.075/1M input, $0.30/1M output | ~240M tokens (1,000 req/day × 8K tokens × 30 days) | ~$90 |
| **Cloud Run (API)** | $0.00002400/vCPU-second | 10,000 CPU-hours | ~$864 |
| **Cloud Run (MCP servers)** | Same rate | 2 servers × 2,000 CPU-hours | ~$345 |
| **Firestore** | $0.18/100K reads | 50M reads | ~$90 |
| **Neo4j AuraDB** | $65/month (Professional) | 1 instance | $65 |
| **Redis (Memorystore)** | ~$0.049/GB-hour | 1GB instance | ~$36 |
| **Weave (W&B)** | $0/month (included) | Unlimited | $0 |

**Moderate tier total:** ~$1,490/month

#### Scaling Considerations

- **Token cost scales linearly** with requests × tools-per-request. With `tool_filter`, fewer tools in context reduces input tokens by ~30-50%.
- **MCP server costs scale with server count**, not user count (multi-tenant). Adding Google Ads MCP + HubSpot MCP adds ~$345/month in Cloud Run.
- **Voice channel** (Phase 4) adds: STT/TTS API costs (~$0.006/min for Deepgram) + Meeting BaaS ($50-100+/month per bot seat for Recall.ai). Not included in moderate tier estimate. Budget ~$500-1,500/month additional depending on meeting volume.
- **Voice latency gap:** Current Agent Engine response time is ~7-13s. Voice requires <2s end-to-end. Voice may need a lightweight agent path or a streaming-optimized serving strategy — this is an unsolved prerequisite for Phase 4.

#### Cost Monitoring

The `UsageTracker` (`app/adk/tracking/usage.py`) records per-tool-call events in Firestore with batched writes (100 events or 30s flush). Alert support: `AlertData` model supports threshold-based alerts. **Scalability concern:** At heavy usage, individual Firestore documents per tool call create expensive aggregation queries. A time-bucketed rollup strategy (hourly/daily pre-aggregated counters) is recommended before production scale.

### 9.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE CLOUD PLATFORM                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐     │
│  │  Cloud Run  │     │ Vertex AI           │     │  Cloud Run  │     │
│  │   API       │────▶│ Agent Engine        │────▶│  GA MCP     │     │
│  │  (FastAPI)  │     │ (KEN-E Agent)       │     │  Server     │     │
│  └──────┬──────┘     └─────────────────────┘     └─────────────┘     │
│         │                                                              │
│    ┌────┴──────────────────────────────────────────┐                  │
│    │                                                │                  │
│    ▼                    ▼                    ▼       │                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │                  │
│  │  Firestore  │  │   Neo4j     │  │   Redis     │ │                  │
│  │  (Config,   │  │   AuraDB    │  │  (Sessions) │ │                  │
│  │   State)    │  │  (Knowledge)│  │             │ │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘ │                  │
│                                                      │                  │
│  ┌───────────────────────────────────────────────────┘                  │
│  │                                                                      │
│  ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐      │
│  │                    Secret Manager                            │      │
│  │         (API keys, OAuth tokens, MCP credentials)           │      │
│  └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────┐  ┌───────────────────────┐                  │
│  │   Weave / W&B         │  │  [PLANNED] MCP Servers │                  │
│  │   (Tracing)           │  │  Google Ads MCP        │                  │
│  └───────────────────────┘  │  HubSpot MCP (hosted)  │                  │
│                              └───────────────────────┘                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Resilience, Error Handling & Security

### 10.1 Current Error Handling Patterns

The codebase has multi-layer error handling. This section documents what exists and identifies gaps.

#### 10.1.1 Implemented Patterns

| Layer | Pattern | Key Files |
|-------|---------|-----------|
| **Dispatch handlers** | Try/catch → return `{status: "error", error: str}`. Never raises. | `dispatch_handlers.py` |
| **Agent invocation** | Exponential backoff + jitter via `@retry_with_exponential_backoff()`. Retriable: `ConnectionError`, `TimeoutError`, `ValidationError`. 3 attempts, 1-30s delay. | `agent_retry.py` |
| **MCP health monitoring** | Background health checks every 30s. Auto-reconnect with backoff (1s, 2s, 4s) after 3 consecutive failures. | `mcp_config/manager.py` |
| **API context loading** | Parallel `asyncio.gather()` with per-source try/catch. Neo4j fails → skip org context. Firestore fails → skip GA creds. Redis miss → load from DB. | `routers/chat.py` |
| **API session creation** | ADK session fails → generate `manual_*` fallback ID. Non-blocking. | `routers/chat.py` |
| **Chat completion** | 1800s timeout on Agent Engine calls. `TimeoutError` → user-facing message. Stream errors caught and returned as text. | `routers/chat.py` |
| **Tool execution tracking** | `adk_after_tool_callback` records `ExecutionStatus`: SUCCESS, FAILURE, TIMEOUT, PERMISSION_DENIED, RATE_LIMITED. Never blocks. | `tracking/callbacks.py`, `tracking/usage.py` |
| **Security hooks** | `adk_before_tool_callback` checks token expiry (5-min buffer), refreshes via Google OAuth2 API. Permission denied → signals frontend reauth. | `security/hooks.py` |
| **Firestore operations** | Retry decorators with exponential backoff + jitter. Retriable: `Aborted`, `DeadlineExceeded`, `ResourceExhausted`, `ServiceUnavailable`. Config: 3-5 attempts, 0.5-2s initial delay. | `strategy_agent/retry_utils.py` |

#### 10.1.2 Gap: No Circuit Breaker Pattern

Current retry logic always attempts up to `max_retries` even if a service is clearly down. Missing:
- **Circuit breaker state machine** (CLOSED → OPEN → HALF-OPEN) for MCP servers and Agent Engine
- **Failure rate threshold** — e.g., if >50% of calls to an MCP server fail in 60s, stop sending for 30s
- **Cascading failure protection** — if GA MCP is down, GA agent should fail fast rather than retry 3x per dispatch

**Recommendation:** Implement circuit breaker at the `McpToolset` or dispatch handler level. ADK's `before_tool_callback` could check circuit state before allowing tool execution.

#### 10.1.3 Gap: Firestore Unavailability at Deploy Time

If Firestore is unreachable during `deploy_ken_e.py` execution, `load_config_from_firestore()` raises `FirestoreConnectionError`. The deployment fails — there are no bundled fallback configs.

**Recommendation:** Bundle last-known-good config snapshots in the deployment package. Deploy script should catch `FirestoreConnectionError` and fall back to bundled config with a warning.

### 10.2 Credential Lifecycle & Security Model

#### 10.2.1 Current OAuth Flow

| Step | Implementation | Key File |
|------|---------------|----------|
| **Authorization** | Frontend initiates `GET /api/oauth/authorize/google-analytics`. Generates state token (15-min TTL in Firestore). Redirects to Google with `offline` + `consent` prompts. Scopes: `analytics.readonly`, `analytics.edit`. | `routers/oauth_integrations.py` |
| **Callback** | Validates state token (CSRF protection). Exchanges auth code for tokens. Preserves existing refresh_token if Google doesn't return new one. Encrypts and stores in Firestore. | `routers/oauth_integrations.py` |
| **Storage** | Credentials encrypted via `EncryptionService` (Fernet-based). Stored in Firestore via `IntegrationCredentialsService`. Keys: `access_token`, `refresh_token`, `expires_at`, `tenant_id`, `selected_property_ids`. | `ga_credential_helper.py`, `encryption_service.py` |
| **Injection** | API loads creds from Firestore at session creation, refreshes if expired, writes to ADK session state as `ga_credentials`. Cached in Redis (10-min TTL). | `routers/chat.py` |
| **Per-request auth** | `_ga_header_provider()` reads `ga_credentials` from `context.state`, builds `Authorization: Bearer` + `X-Tenant-ID` headers. Called per turn by McpToolset. | `google_analytics_agent_v4.py` |
| **Token refresh** | On-demand: checks `expires_at` with 5-min buffer. Calls `https://oauth2.googleapis.com/token` with 10s timeout. Updates Firestore + returns refreshed creds. | `ga_credential_helper.py` |
| **Reauth signal** | `adk_before_tool_callback` detects expired/revoked tokens → returns `{requires_reauth: true}` → frontend triggers re-authorization flow. | `security/hooks.py` |

#### 10.2.2 Gaps in Credential Security

| Gap | Risk | Recommendation |
|-----|------|----------------|
| **No proactive token refresh** | Tokens may expire mid-conversation if session is long | Add background refresh task or refresh during `InstructionProvider` (runs each turn) |
| **No refresh token rotation tracking** | Can't detect if refresh token was revoked by user in Google | Track last successful refresh timestamp; if refresh fails, immediately signal reauth |
| **Fernet encryption in dev, KMS TODO in prod** | Local encryption key management is not production-grade | Complete `EncryptionService` KMS integration before production launch |
| **No credential expiry notifications** | Users discover broken credentials only when they try to use an agent | Add expiry monitoring: warn user in frontend when creds expire within 24h |
| **No cross-tenant isolation checks** | Credential retrieval uses `account_id` but no additional tenant boundary enforcement | Add explicit tenant context validation in `IntegrationCredentialsService` |

#### 10.2.3 Multi-Tenant Security for Specialist Agents

When specialist agents connect to multiple MCP servers per user (Sprint 5-6), each `McpToolset` needs its own `header_provider` that reads the correct platform credentials from session state:

```
Session state keys (per-platform):
  ga_credentials      → GA MCP header_provider
  google_ads_credentials → Google Ads MCP header_provider
  hubspot_credentials → HubSpot MCP header_provider
  meta_ads_credentials → Meta Ads SDK tool_context.state
```

The API layer must load and refresh credentials for all connected platforms at session creation time. This is a linear scaling problem: N platforms = N credential loads. Mitigation: parallel loading (already implemented for GA), Redis caching per-platform.

### 10.3 Rate Limiting & Platform Quota Management

#### 10.3.1 Current Rate Limiting

| Scope | Implementation | Key File |
|-------|---------------|----------|
| **Auth endpoints** | In-memory sliding window per IP. Login: 10/min, 50/hr. Token: 60/min, 1000/hr. Password reset: 3/min, 10/hr. | `auth/rate_limiting.py` |
| **External APIs** | Redis-backed per-API limits. Wikipedia: 10/min. Wikidata: 10/min. Gemini: 5/min. Fail-open if cache unavailable. | `services/rate_limiter.py` |
| **Firestore operations** | Retry with backoff on `ResourceExhausted` (Firestore's rate limit signal). | `strategy_agent/retry_utils.py` |

#### 10.3.2 Gap: No Marketing Platform Quota Management

Marketing platform APIs have aggressive rate limits that the specialist agents must respect:

| Platform | Rate Limits | Impact |
|----------|------------|--------|
| **Google Ads API** | 15,000 operations/day (basic access), per-customer limits on mutate operations | Daily quota exhaustion blocks all Google Ads queries |
| **Meta Marketing API** | Rate limits per ad account, sliding window with business use case rate limits | Account-level throttling; shared across all users accessing same ad account |
| **HubSpot API** | 100-200 requests/10s depending on plan tier, daily limits | Per-app limits shared across all KEN-E users on same HubSpot portal |
| **Google Analytics Data API** | 200 requests/min per property, 50,000 requests/day per project | Shared project quota across all KEN-E users |

**Recommendation:** Implement per-platform quota tracking at the specialist agent level:

1. **`before_tool_callback` quota check** — Before each tool call, check remaining quota from a shared counter (Redis). If quota is low, either throttle (add delay) or inform the user.
2. **Response header parsing** — Extract `X-RateLimit-Remaining` and `Retry-After` headers from MCP server responses. Store in Redis for quota tracking.
3. **Account-level quota isolation** — For platforms with per-account limits (Meta, HubSpot), track quota per `account_id`, not globally.
4. **User-facing feedback** — When rate limited, the specialist agent should explain the constraint: "Google Ads daily quota is at 95%. I can run 3 more queries today."

### 10.4 Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Context overflow during complex tasks** | High | High | ADK compaction (interval=5, threshold=50K), hierarchical loading, `tool_filter` |
| **MCP server connection failures** | Medium | High | ADK auto-reconnect, health monitoring, retry logic. Gap: no circuit breaker. |
| **Agent hallucination in strategy outputs** | Medium | High | Require citations, fact-checking tools, human review queue |
| **ADK version dependency** | Medium | Medium | Pin versions, test upgrades in staging before prod |
| **Firestore config drift** | Low | Medium | Config validation at deploy time, registry consistency tests |
| **Cost overrun from token usage** | Medium | Medium | UsageTracker (token + cost metrics), Weave tracing, alerts via `AlertData` model |
| **Platform API rate limit exhaustion** | Medium | Medium | Per-platform quota tracking (gap — not yet implemented) |
| **OAuth token expiry mid-conversation** | Medium | Low | 5-min refresh buffer, reauth signal to frontend. Gap: no proactive refresh. |
| **Credential encryption not prod-ready** | Low | High | Fernet in dev, KMS TODO in prod. Must complete before launch. |

### 10.2 Test Locations

| Test Suite | Location | Coverage |
|-----------|----------|----------|
| API unit tests | `api/tests/unit/` | Chat, auth, sessions, context |
| API integration tests | `api/tests/` | End-to-end API flows |
| Agent tests | `app/adk/agents/tests/` | Registry, dispatch, context loading |
| Shared module tests | `shared/tests/` | Context utils, token estimation |
| Load tests | `tests/load_test/` | Locust performance tests |

### 10.3 Performance Benchmarks

| Operation | Target | Acceptable | Critical | Measured |
|-----------|--------|------------|----------|----------|
| Session initialization | < 500ms | < 1s | > 2s | — |
| Tool search | < 200ms | < 500ms | > 1s | — |
| MCP server load | < 500ms | < 1s | > 2s | — |
| Agent response (simple) | < 5s | < 10s | > 15s | ~7-13s |
| Agent response (complex) | < 10s | < 20s | > 30s | — |
| Context section load | < 300ms | < 500ms | > 1s | — |

---

## 11. Sprint-Based Roadmap

### 11.1 Completed (Sprints 1-4)

| Sprint | What Was Built | Status |
|--------|---------------|--------|
| **Sprint 1** | Session state architecture (creds + org context in ADK state), authorization checks, KEN-E root agent with dispatch | Canonical |
| **Sprint 2** | HierarchicalContextManager, ToolRegistry, EventsCompactionConfig + ContextCacheConfig in deploy, shared context utils | Canonical |
| **Sprint 3** | MCPServerManager, security hooks, usage tracking, MCP admin endpoints | Partially superseded (see Section 5.3) |
| **Sprint 3b** | Agent registry + Firestore config, API allowlist from registry, context loader consolidation, chat latency optimization (~23s → ~7-13s), structured logging, Prometheus, Agent Engine tracing, MCP health ping | Canonical |
| **Sprint 4** | Weave SDK init, @weave.op() instrumentation, trace hierarchy (before/after callbacks), structured logging with request_id | Canonical |

### 11.2 In Progress

| Item | Sprint | Description |
|------|--------|-------------|
| Sprint 3b PR | 3b | Agent config optimization, final review |

### 11.3 Planned

| Item | Timeline | Description |
|------|----------|-------------|
| **Specialist agents + agent factory** | Sprint 5-6 | Config-driven agent assembly, category-based tool routing |
| **Additional MCP servers** | Sprint 5-6 | Google Ads MCP, HubSpot MCP integration |
| **SDK function tools** | Sprint 5-6 | Meta Ads, Mailchimp direct SDK integration |
| **Slack channel** | Sprint 8+ | Bolt SDK integration on separate Cloud Run |
| **Workflow management** | Sprint 8+ | Multi-step task tracking with Firestore persistence |
| **Voice channel** | Phase 4 | Pipecat + Meeting BaaS |
| **A/B testing** | Phase 4 | Experiment infrastructure for agent configs |

---

## 12. Appendices

### Appendix A: Platform Integration Reference

| Platform | Integration Type | MCP/SDK | Status |
|----------|-----------------|---------|--------|
| **Google Analytics** | Self-hosted MCP | GA MCP on Cloud Run | Implemented |
| **Google Ads** | Self-hosted MCP | Google official MCP | Planned |
| **HubSpot** | Provider-hosted MCP | `mcp.hubspot.com` | Planned |
| **Meta Ads** | SDK function tools | `facebook-business` | Planned |
| **Mailchimp** | SDK function tools | `mailchimp-marketing` | Planned |
| **Microsoft Ads** | Deferred | — | No current demand |

### Appendix B: Output Types for Evaluation

| Category | Output Types |
|----------|-------------|
| **Business Strategy** | company_overview, swot_analysis, strategic_goals, value_proposition |
| **Marketing Strategy** | icp_narrative, campaign_strategy, channel_strategy, messaging_framework |
| **Competitive** | competitor_analysis, competitive_positioning, market_trends |
| **Content** | blog_post, social_post, email_copy, video_script, landing_page |
| **Analytics** | performance_report, forecast, attribution_analysis |

### Appendix C: Configuration Reference

#### Agent Configuration (Firestore)

Agent behavior is driven by Firestore documents. Each document contains:
- `instruction` — system prompt text
- `model` — Gemini model identifier (e.g., `gemini-2.0-flash`)
- `temperature` — creativity parameter
- `description` — agent description for ADK
- `version` — semver for trace metadata

The agent registry (`app/adk/agents/registry.py`) maps agent names to their Firestore config doc IDs.

#### MCP Server Configuration (YAML → Firestore)

Current: `app/adk/mcp_config/config/mcp_servers.yaml` defines server connections, auth types, categories, and enabled status.

Planned: Migrate to Firestore config registry for per-org enablement without redeployment.

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **HCL** | Hierarchical Context Loading — 3-level context management |
| **MCP** | Model Context Protocol — standard for tool integration |
| **ADK** | Agent Development Kit — Google's agent framework |
| **McpToolset** | ADK class that manages MCP server connections |
| **InstructionProvider** | Callable that returns dynamic instructions per LLM turn |
| **Agent Factory** | [PLANNED] Config-driven system that assembles agents from Firestore config |
| **tool_filter** | ADK `BaseToolset` parameter — callable predicate evaluated per-turn to control which tools are visible to the LLM |
| **ToolRegistry** | Searchable metadata catalog for ~400 tools; planned as driver for `tool_filter` predicates |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Development Team | Initial design document |
| 2.0 | 2026-03-10 | Development Team | Updated to reflect Sprints 1-4 implementation. Removed fictional code for unimplemented features (PrimaryOrchestrator, ContextCompressor, ContextStateManager, ToolDiscoveryAgent, WebChannelAdapter, SlackChannelAdapter, VoiceChannelAdapter, WorkflowManager, ScheduledWorkflowManager, FeedbackCollector, ExperimentManager). Replaced with actual implementations. Marked unbuilt features as [PLANNED]. |
| 2.1 | 2026-03-10 | Development Team | Design review: Added `tool_filter` + ToolRegistry architecture for dynamic per-turn tool selection (preserves v1.0 ToolDiscoveryAgent capability via ADK-native mechanisms). Updated ADK internals analysis with version-specific behavior and issue references. Added sprint-3b dependency note. Fixed Deepgram latency claim. |

---

*This document describes the architecture for the KEN-E agentic harness. It is updated as implementation progresses.*
