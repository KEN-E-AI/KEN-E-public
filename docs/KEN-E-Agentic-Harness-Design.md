# KEN-E Agentic Harness Design Document

**Version:** 2.9
**Date:** March 18, 2026
**Author:** Development Team

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
6. [Skills Architecture [PLANNED]](#6-skills-architecture-planned)
7. [Multi-Channel Support [PLANNED]](#7-multi-channel-support-planned)
8. [Workflow Management [PLANNED]](#8-workflow-management-planned)
9. [Integration with Evaluation Framework](#9-integration-with-evaluation-framework)
10. [Infrastructure Requirements](#10-infrastructure-requirements)
11. [Resilience, Security & Testing](#11-resilience-security--testing)
12. [Sprint-Based Roadmap](#12-sprint-based-roadmap)
13. [Appendices](#13-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the comprehensive design for KEN-E's agentic harness — the software framework that enables KEN-E to function as an autonomous AI marketing agent. The harness orchestrates multiple specialized agents using Google's Agent Development Kit (ADK) to complete complex marketing tasks including strategy development, content creation, campaign execution, and performance optimization.

This document serves as an architecture reference: it describes both the current implementation and planned extensions. Features not yet built are marked `[PLANNED]` throughout. Agents marked `[TRANSITIONAL]` exist in the current implementation but will be subsumed by a specialist agent or automation when the specialist layer is built (Sprint 5-6). As planned features are deployed, this document is updated to collapse the distinction.

### 1.2 Critical Design Challenges

The agentic harness must solve three primary challenges:

| Challenge | Scale | Impact |
|-----------|-------|--------|
| **Massive Tool Inventory** | ~400 tools across 20-40 MCP servers | Tool definitions alone could consume 60,000+ tokens |
| **Large Context Requirements** | ~100,000 words of company knowledge | Leaves minimal room for conversation |
| **Multi-Step Autonomous Workflows** | Tasks spanning days/weeks | Requires persistent state and scheduled execution |

### 1.3 Agentic Harness Overview

The design implements a **Hierarchical Agent Architecture with Dynamic Context Loading**.

#### 1.3.1 Current Agentic Harness (March 11, 2026)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       KEN-E AGENTIC HARNESS (Current)                   │
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
│  │                    SUB-AGENT LAYER                             │     │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────────────────┐   │     │
│  │  │   News    │ │  Google   │ │  Strategy Supervisor      │   │     │
│  │  │   Agent   │ │ Analytics │ │  (multi-agent)            │   │     │
│  │  │ [TRANSIT.]│ │   Agent   │ │                           │   │     │
│  │  │           │ │ [TRANSIT.]│ │                           │   │     │
│  │  └───────────┘ └───────────┘ └───────────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                │                                       │
│                                ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              TOOL & INTEGRATION LAYER                         │     │
│  │  ┌───────────────────────────────────────────────────────┐   │     │
│  │  │          MCP Servers (Lazy-Loaded via McpToolset)      │   │     │
│  │  │  GA MCP (Cloud Run)                                    │   │     │
│  │  └───────────────────────────────────────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 1.3.2 [PLANNED] Agentic Harness

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       KEN-E AGENTIC HARNESS (Target)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                  ORCHESTRATOR LAYER                            │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │     │
│  │  │  KEN-E Root │  │   Context   │  │  Tool Registry      │   │     │
│  │  │   Agent     │  │   Loader    │  │  + tool_filter      │   │     │
│  │  │  (LlmAgent) │  │             │  │                     │   │     │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                │                                       │
│                                ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              SPECIALIST LAYER (config-driven agent factory)   │     │
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
│  │  │  GA MCP | Google Ads MCP | HubSpot MCP | n8n MCP     │   │     │
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

| Decision |
|----------|
| **Specialist routing for token budgets** — each specialist sees only its domain tools (~10-30), not all 400 |
| **ADK native compaction** — `EventsCompactionConfig` with `gemini-2.5-flash` summarizer |
| **`McpToolset` for MCP connections** — ADK handles lazy loading, connection pooling, per-user auth natively |
| **SDK function tools for some platforms** — Meta Ads + Mailchimp use SDK directly |
| **Firestore-driven agent config** — change instructions, model, temperature without redeployment |
| **Config-driven agent factory** — Sprint 5-6: config-driven specialist assembly |
| **ADK Skills for expertise delivery** — predefined skills shipped with product, custom skills created by users via UI |
| **Vega-Lite artifacts for data visualization** — specialists produce Vega-Lite chart specs via `create_visualization()` tool; `ChatResponse` extended with `artifacts` field; agent suggests chart type, frontend can override |
| **Gemini code execution for analytics** — Analytics Specialist uses Gemini's built-in code execution for reliable calculations (percentage changes, averages, trend analysis). No new infrastructure — Google-managed sandbox. |

For full decision rationale, see the [Design Decisions database in Notion](https://www.notion.so/2f230fd6530280d599f0ca1449111d7e).

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
│   • Platform credential injection into session state (OAuth, API keys) │
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
│   ├── Security hooks (before tool — credential refresh, permissions)   │
│   │                                                                     │
│   ├── News Agent (LlmAgent) [TRANSITIONAL → Automation Specialist + Skill]│
│   ├── Strategy Supervisor (multi-agent)                                 │
│   └── [PLANNED] Specialist Agents (config-driven via agent factory)    │
│       ├── Analytics Specialist (GA MCP, Google Ads MCP, Meta Ads reads)│
│       ├── Content Specialist (HubSpot MCP, Mailchimp SDK)              │
│       ├── Execution Specialist (Meta Ads SDK r/w, Google Ads MCP)      │
│       └── Automation Specialist (n8n MCP)                              │
│                                                                         │
│   EventsCompactionConfig: interval=5, overlap=1, threshold=50K tokens  │
│   ContextCacheConfig: enabled                                          │
│   ReflectAndRetryToolPlugin: enabled                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
       ┌───────────┐        ┌───────────┐        ┌───────────────────┐
       │  Neo4j    │        │ Firestore │        │   MCP Servers     │
       │ Knowledge │        │  Config,  │        │  (Cloud Run)      │
       │   Graph   │        │   State   │        │  GA, Ads, HubSpot │
       └───────────┘        └───────────┘        └───────────────────┘
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

For detailed patterns of each component listed above, see [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Sections 2-6.

### 2.3 Request Flow

#### 2.3.1 Current Request Flow (March 11, 2026)

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

See [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Section 3 for the dispatch pattern implementation.

#### 2.3.2 [PLANNED] Request Flow (Sprint 5-6+)

```
User Request: "Show me last week's traffic and top-performing ad campaigns"

    ┌─────────────┐
    │   Web UI    │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 1. FASTAPI (Cloud Run)                                   │
    │    • Validate Firebase Auth token                        │
    │    • Resolve session (pending_* → ADK session)           │
    │    • Inject platform credentials into session state      │
    │    • Forward to Agent Engine                             │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 2. KEN-E ROOT AGENT                                      │
    │    • InstructionProvider loads org context from state    │
    │    • LLM interprets intent: "analytics" + "advertising" │
    │    • Generates acceptance criteria for the request       │
    │    • Routes to Analytics Specialist with criteria        │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 3. REVIEW LOOP (LoopAgent, max_iterations=3)             │
    │    Repeats until reviewer approves or iterations exhaust │
    │                                                          │
    │    ┌────────────────────────────────────────────────┐    │
    │    │ 3a. ANALYTICS SPECIALIST (output_key="draft")  │    │
    │    │    • Assembled by agent factory                 │    │
    │    │    • tool_filter selects relevant tools         │    │
    │    │    • McpToolset → GA MCP (traffic data)         │    │
    │    │    • McpToolset → Google Ads MCP (campaigns)    │    │
    │    │    • create_visualization() for data charts     │    │
    │    │    • Reads {review_feedback} if prior iteration │    │
    │    └────────────────────────────────────────────────┘    │
    │                        │                                 │
    │                        ▼                                 │
    │    ┌────────────────────────────────────────────────┐    │
    │    │ 3b. REVIEWER (output_key="review_feedback")    │    │
    │    │    • Evaluates {draft} vs acceptance criteria   │    │
    │    │    • ALL criteria met → call exit_loop          │    │
    │    │    • ANY not met → write actionable feedback    │    │
    │    └────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────────┐
    │ 4. RESPONSE                                              │
    │    • Approved draft extracted from session state         │
    │    • Artifacts extracted from response_artifacts state   │
    │    • ChatResponse includes content + artifacts field     │
    │    • KEN-E relays to user                                │
    │    • Background: update session preview + Redis cache    │
    └─────────────────────────────────────────────────────────┘
```

See Section 4.6 for the review loop pattern design and Section 8.1 for multi-step workflow application.

> **Transitional note:** The current request flow dispatches directly to the Google Analytics Agent and Company News Agent. These agents are `[TRANSITIONAL]` — GA queries will route to the Analytics Specialist when the specialist layer is built (Section 4.4). Company news will transition to a scheduled automation (Automation Specialist) plus a predefined `research-company-news` Skill (Section 6).

### 2.4 Agent Type Selection (Google ADK)

| Agent | ADK Type | Status | Successor |
|-------|----------|--------|-----------|
| **KEN-E Root** | `LlmAgent` | Implemented | — |
| **Company News** | `LlmAgent` | Implemented `[TRANSITIONAL]` | Automation Specialist + `research-company-news` Skill |
| **Google Analytics** | `LlmAgent` + `McpToolset` | Implemented `[TRANSITIONAL]` | Analytics Specialist |
| **Strategy Supervisor** | Multi-agent (custom) | Implemented | — |
| **Analytics Specialist** | `LlmAgent` | [PLANNED] | — |
| **Content Specialist** | `LlmAgent` | [PLANNED] | — |
| **Execution Specialist** | `LlmAgent` | [PLANNED] | — |
| **Automation Specialist** | `LlmAgent` | [PLANNED] | — |

---

## 3. Context Management Strategy

> **Roadmap:** [Feature 1.1.1: Agent Config Optimization](product-roadmap.md#feature-111-agent-config-optimization-sprint-3b-merge) — Release 1.1

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

LEVEL 2: SECTION SUMMARIES (~10,000 tokens each) - Agent-Driven Loading
  [products] [icps] [competitors] [campaigns] [strategies] [brand]
  [performance] [calendar]
  Loaded via `load_context_section(section)` tool — agent decides when needed

LEVEL 3: FULL DETAIL (~20,000+ tokens each) - Agent-Driven Loading
  Complete documentation for individual entities
  Loaded via same tool with detail level parameter
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
- Level 2 (Section Summaries): Partially implemented — campaign context loading exists but needs migration from keyword detection to agent-driven approach
- Level 3 (Full Detail): Not yet implemented

The canonical Neo4j query for org context is defined in `shared/context_utils.py` (`ORG_CONTEXT_QUERY`), shared between the API and agent layers.

> **Revised March 11, 2026** — Keyword detection replaced with agent-driven loading via `load_context_section(section)` tool. See [Decision 17: Context Management](https://www.notion.so/32030fd6530281dca919d68aa0e27094) for rationale.

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

ADK handles summarization, retention, and token budgeting natively. See [Decision 18: Session Compaction](https://www.notion.so/32030fd65302811dbc29f1c34dd46eab).

### 3.6 Session State Management

ADK session state carries per-session data that the API, agents, and security hooks read and write at runtime. The API layer (`api/src/kene_api/routers/chat.py`) initialises state at session creation; agents and hooks may update it mid-session.

#### 3.6.1 Current Session State Keys

| Key | Purpose | Set By | Read By |
|-----|---------|--------|---------|
| `user_id` | Authenticated user identifier | API at session creation | Security hooks, tracking callbacks |
| `account_id` | Selected account identifier | API at session creation | Dispatch handlers |
| `accessible_accounts` | Accounts the user can access | API at session creation | — |
| `organization_context` | Org + brand context text from Neo4j | API at session creation (cached in Redis, 15-min TTL) | InstructionProvider (per-turn), dispatch handlers |
| `ga_credentials` | Google Analytics OAuth tokens (access, refresh, tenant, properties, expiry) | API from Firebase Auth (cached in Redis, 10-min TTL) | GA dispatch handler, security hooks |
| `campaign_context` | Campaign context text (when loaded) | Context loader | Dispatch handlers |
| `connected_accounts` | User's connected platform account types | API at session creation | Tool discovery filtering |
| `uploaded_strategy_documents` | Strategy input documents loaded mid-session | Strategy orchestrator | Strategy orchestrator |
| `_tool_start_time` | Tool execution start timestamp | `adk_before_tool_callback` | `adk_after_tool_callback` |
| `_requires_reauth` | Flag: user must re-authenticate | Security hooks (permission denied) | API response handler (then cleared) |
| `_reauth_service` | Service name requiring re-auth | Security hooks | API response handler (then cleared) |

#### 3.6.2 [PLANNED] Target Session State Model (Sprint 5-6+)

The target architecture generalises credentials to support all integrated platforms:

| Key | Purpose | Set By |
|-----|---------|--------|
| `platform_credentials.<service>` | Per-platform OAuth tokens or API keys (GA, Google Ads, HubSpot, Meta Ads, Mailchimp) | API at session creation |
| `tool_filter_state` | ToolRegistry search results driving per-turn `tool_filter` predicates | `before_agent_callback` on specialist agents (ToolRegistry search, written per-turn before tool resolution) |
| `response_artifacts` | Visualization artifacts (Vega-Lite specs) produced by specialist agents during current invocation | `create_visualization` tool in specialist agents. See [`data-visualization.md`](design/data-visualization.md) Section 4. |

#### 3.6.3 What Is Not in Session State

| Item | Where it lives instead |
|------|----------------------|
| Base agent instructions | Firestore config (loaded at deploy time); InstructionProvider merges with `organization_context` from state |
| Token / cost usage metrics | UsageTracker via Weave traces (`app/adk/tracking/usage.py`) |
| Tool registry index | YAML config loaded at deploy time (`app/adk/tools/registry/config/tools.yaml`) |
| Conversation history | ADK event log (managed by EventsCompactionConfig, not stored in state) |

#### 3.6.4 [PLANNED] Token Usage Visibility

Token usage data exists at every layer (Vertex AI `usage_metadata`, Weave traces, `ConversationSummarizer` budget tracking) but does not currently cross the API boundary to the frontend. The `ChatResponse` model returns content and session metadata only — no token counts.

The planned feature surfaces token data to the UI:

| Metric | Source | Display |
|--------|--------|---------|
| Tokens sent with most recent query | `usage_metadata` from Agent Engine response | Percentage of total available context |
| Session tokens used | `ConversationSummarizer.token_budget_usage` | Running total |
| Compaction proximity | `ConversationSummarizer.should_compact()` threshold (80% of 40K) | Warning indicator when approaching limit |

Implementation requires changes at three layers: API (extract `usage_metadata`, extend `ChatResponse`), response model (add `usage` field), and frontend (token display components). See [Decision 19: Token Usage Visibility in UI](https://www.notion.so/32030fd65302815ca0d6fe5291fdfc54).

#### 3.6.5 [PLANNED] Unified Usage Tracking for Billing

Monthly billing requires aggregating token usage to the organisation level. The current codebase has two separate tracking systems that cannot support this:

| Collection | Tracks | Has `organization_id` | Has `session_id` | Has token counts |
|------------|--------|----------------------|-------------------|-----------------|
| `tool_usage_events` | Tool calls (name, duration, user) | ✅ | ❌ | ❌ |
| `usage_records` | LLM calls (tokens, model, cost) | ❌ | ❌ | ✅ (partial) |

**Billing hierarchy:** Organisation → Accounts → Sessions → Usage records.

**Gaps to close:**

1. Add `organization_id` and `session_id` to `usage_records` at write time
2. Ensure LLM token counts from Vertex AI `usage_metadata` are reliably written to `usage_records` (currently they only reach W&B traces)
3. Build a billing aggregation query or scheduled Cloud Function that sums tokens by organisation and billing period

The two collections will remain separate (tool observability vs. billing) but share `organization_id` and `session_id` as common keys for cross-referencing. See [Decision 20: Unified Usage Tracking for Billing](https://www.notion.so/32030fd6530281bfa31cf19af537b206).

---

## 4. Agent Definitions

> For full details on the agent tree, registry, dispatch pattern, and agent factory, see [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md).

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
    ├── Execution Specialist (Meta Ads SDK, Google Ads SDK writes, Google Ads MCP reads)
    └── Automation Specialist (n8n MCP)
```

### 4.2 KEN-E Root Agent

> **Roadmap:** [Feature 1.1.1: Agent Config Optimization](product-roadmap.md#feature-111-agent-config-optimization-sprint-3b-merge), [Feature 2.2: Agent Factory](product-roadmap.md#feature-22-agent-factory--phase-1) — Releases 1.1, 2.0

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

> **Specialist `before_agent_callback` chaining:** Specialist agents (assembled by the agent factory) use a composite callback that chains Weave tracing with ToolRegistry search. The ToolRegistry callback writes `state["tool_filter_state"]` before tool resolution. The root agent keeps only the Weave callback since it routes via dispatch, not MCP tools. See `docs/design/mcp-architecture.md` Section 5a.

See [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Section 4 for the InstructionProvider closure pattern and Section 5 for Firestore-driven configuration details.

### 4.3 Tool Discovery & Dynamic Tool Selection

Tool management operates at two levels:

**Level 1 — Specialist Routing (structural, deploy-time):** Each specialist agent receives only its domain MCP servers via `McpToolset` instances, wired at agent construction. This reduces the tool space from ~400 to ~10-30 per specialist.

**Level 2 — `tool_filter` + ToolRegistry (dynamic, per-turn):** ADK's `BaseToolset` accepts a `tool_filter` predicate evaluated on every LLM turn. Combined with the ToolRegistry's search capabilities, this enables exposing only the relevant subset of a specialist's tools on any given turn.

The **ToolRegistry** (`app/adk/tools/registry/tool_registry.py`) provides:

- Tool metadata catalog loaded from YAML (`app/adk/tools/registry/config/tools.yaml`)
- Search by name, category, keyword with relevance scoring
- Compact ~2,000-token index via `get_index_for_context()`
- Permission validation (required OAuth scopes)
- **`tool_filter` driver via `before_agent_callback`** — each specialist's `before_agent_callback` runs ToolRegistry search, writes results to `state["tool_filter_state"]`, read by `McpToolset` `tool_filter` predicates per-turn. Validated in Experiment #4; see `docs/design/mcp-architecture.md` Section 5a for execution order and anti-patterns. (Production implementation pending Sprint 5-6.)

MCP server connections are fixed at deploy time — only *which tools* are visible is dynamic per-turn.

#### Tool Type Taxonomy

| Tool Type | Resolution Mechanism | Context Overhead | Subject to `tool_filter` | Example |
|-----------|---------------------|-----------------|--------------------------|---------|
| **MCP Tools** | Resolved via `McpToolset` + `tool_filter` | ~150 tokens/tool in context | Yes | GA MCP `run_report_mt`, HubSpot MCP `get_contacts` |
| **SDK Function Tools** | Python functions wired at agent construction | ~150 tokens/tool in context | Yes (via `FunctionTool` wrapper) | `update_meta_campaign_budget()`, `create_visualization()` |
| **Built-in Model Capabilities** | Enabled via `GenerateContentConfig.tools` | Zero — no tool definition sent to context | No — not subject to `tool_filter` | Gemini code execution (`ToolCodeExecution`) |

> **Built-in model capabilities** are orthogonal to the tool management system. They are configured at agent construction via `GenerateContentConfig`, not as MCP or SDK tools. The LLM can invoke them natively without a tool definition in context. Currently, only Gemini code execution is planned (Analytics Specialist, Sprint 5-6).

> **Execution order per LLM turn (verified in Experiment #4):** `before_agent_callback` (writes `tool_filter_state`) → `InstructionProvider` (reads state) → `tool_filter` (reads state) → `before_model_callback` → LLM call. All share the same `session.state` dict — `ReadonlyContext.state` is a `MappingProxyType` (read-only live view), so `CallbackContext` writes are immediately visible.

See [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Section 6 for the ToolRegistry's current and planned roles.

See [Decision 7: Token Budget Strategy](https://www.notion.so/32030fd6530281da97cef1729242ccd1) and [Decision 8: ToolRegistry](https://www.notion.so/32030fd65302813ab406cf15f7e1e7f6) in the Design Decisions database.

### 4.4 [PLANNED] Specialist Agents

> **Roadmap:** [Feature 2.2: Agent Factory](product-roadmap.md#feature-22-agent-factory--phase-1), [Feature 2.3: Analytics Specialist](product-roadmap.md#feature-23-analytics-specialist--phase-1), [Feature 3.1: Content Specialist](product-roadmap.md#feature-31-content-specialist), [Feature 3.2: Execution Specialist](product-roadmap.md#feature-32-execution-specialist), [Feature 4.1: Automation Specialist](product-roadmap.md#feature-41-automation-specialist--n8n) — Releases 2.0–4.0

The specialist layer (Sprint 5-6) partitions tools by domain.

| Specialist | Tool Sources | Integration Type | Key Capabilities |
|-----------|-------------|-----------------|------------------|
| **Analytics** | GA MCP, Google Ads MCP, Meta Ads SDK (reads), Gemini code execution | McpToolset + SDK + built-in | Data queries, reporting, performance analysis, calculations |
| **Content** | HubSpot MCP, Mailchimp SDK | McpToolset + SDK | CRM data, email campaigns, content management |
| **Execution** | Meta Ads SDK (reads + writes), Google Ads SDK (writes), Google Ads MCP (reads) | SDK + McpToolset | Campaign deployment, budget management |
| **Automation** | n8n MCP | McpToolset | Workflow creation, scheduling |

> **Note:** The `facebook-business` SDK is available to both Analytics (read-only tools: get campaigns, get spend, get metrics) and Execution (full CRUD). `tool_filter` controls which tools each specialist sees — Analytics sees read-only tools while Execution sees the full CRUD set. This parallels Google Ads, where the MCP (reads) is shared with Analytics.

Each specialist will be assembled by the config-driven agent factory, reading from Firestore config.

> **Visualization artifacts:** All specialist agents have the `create_visualization()` function tool, enabling them to produce Vega-Lite chart specs alongside text responses. This is not an MCP tool — it is a Python function tool that writes artifacts to `response_artifacts` session state. See [`docs/design/data-visualization.md`](design/data-visualization.md) for the full artifact model, tool signature, and data flow.

> **[PLANNED] Gemini code execution:** The Analytics Specialist uses Gemini's built-in code execution for reliable numerical calculations (percentage changes, averages, trend analysis). Enabled via `GenerateContentConfig.tools = [Tool(code_execution=ToolCodeExecution())]` at agent construction — not an MCP or SDK tool, and not subject to `tool_filter`. Google manages the sandbox; no infrastructure required. The Content Specialist may receive code execution later if needed for data-driven content. The Root Agent does NOT get code execution — it routes to specialists. See Section 4.3 Tool Type Taxonomy.

> For platform-by-platform integration rationale (why hybrid MCP+SDK for Google Ads, why SDK-only for Meta/Mailchimp, provider-hosted vs self-hosted decisions) and the SDK function tools pattern, see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md) Sections 4 and 8.

See [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Section 7 for the specialist layer design and Section 8 for the config-driven agent factory.

### 4.5 Agent Summary Table

#### Current (Sprints 1-4)

| Agent | Type | Config Doc ID | Key Files | Lifecycle |
|-------|------|---------------|-----------|-----------|
| KEN-E Root | LlmAgent | `ken_e_chatbot` | `app/adk/agents/ken_e_agent.py` | Permanent |
| Company News | LlmAgent | `company_news_agent` | `app/adk/agents/company_news_chatbot/agent.py` | `[TRANSITIONAL]` → Automation Specialist (scheduled n8n workflow) + `research-company-news` Skill (Section 6) |
| Google Analytics | LlmAgent + McpToolset | `google_analytics_agent` | `app/adk/agents/google_analytics_agent_v4.py` | `[TRANSITIONAL]` → Analytics Specialist |
| Strategy Supervisor | Multi-agent | 8 sub-config docs | `app/adk/agents/create_strategy_docs_supervisor.py` | Permanent |

#### [PLANNED] Specialist Layer (Sprint 5-6+)

| Agent | Type | Tool Sources | Assembled By |
|-------|------|-------------|--------------|
| Analytics Specialist | LlmAgent + McpToolset + SDK + code execution | GA MCP, Google Ads MCP, Meta Ads SDK (reads), Gemini code execution | Config-driven agent factory |
| Content Specialist | LlmAgent + McpToolset + SDK | HubSpot MCP, Mailchimp SDK | Config-driven agent factory |
| Execution Specialist | LlmAgent + SDK + McpToolset | Meta Ads SDK (reads + writes), Google Ads SDK (writes), Google Ads MCP (reads) | Config-driven agent factory |
| Automation Specialist | LlmAgent + McpToolset | n8n MCP | Config-driven agent factory |

### 4.6 [PLANNED] Review Loop Pattern (Generator-Critic)

> **Roadmap:** [Feature 2.1: Review Loop Framework](product-roadmap.md#feature-21-review-loop-framework) — Release 2.0

Every specialist delegation is wrapped in a **review loop** that enforces acceptance criteria before returning results to the user. This uses ADK's native workflow agents:

| ADK Construct | Role |
|---------------|------|
| `LoopAgent` | Repeats specialist + reviewer cycle until approved or `max_iterations` reached. Iterates its sub-agents sequentially and checks for `escalate` between each one — no `SequentialAgent` wrapper needed. |
| `output_key` | Specialist writes to `"step_N_draft"`, reviewer writes to `"step_N_feedback"` — shared via session state |
| `include_contents` | Set to `'none'` on the reviewer so it evaluates only the template-injected `{draft}`, not the full conversation history |
| `exit_loop` | Built-in tool the reviewer calls when all acceptance criteria are met. Sets `escalate=True` in `EventActions`, causing the parent `LoopAgent` to skip remaining sub-agents and exit. |

#### Review Loop Structure

```
build_review_pipeline(specialist, acceptance_criteria, max_iterations=3)
→ returns:

    review_loop (LoopAgent, max_iterations=3)
    ├── specialist (LlmAgent, output_key="step_N_draft")
    │     instruction: task + acceptance_criteria + {step_N_feedback?}
    │     tools: [specialist-specific MCP/SDK tools]
    └── reviewer (LlmAgent, output_key="step_N_feedback", include_contents='none')
          instruction: evaluate {step_N_draft} vs acceptance_criteria
          tools: [exit_loop]
          ALL criteria met → call exit_loop
          ANY not met → write actionable feedback
```

> **Why no `SequentialAgent` wrapper?** `LoopAgent` already iterates its sub-agents in order and checks `escalate` between each one. A `SequentialAgent` wrapper would swallow the `escalate` signal — if agent order were ever reversed, the specialist would run even after approval. Placing agents directly under `LoopAgent` ensures `exit_loop` immediately terminates the iteration.

> **Why `include_contents='none'` on the reviewer?** Without it, the reviewer sees the full conversation history (all prior turns, tool calls, and review loop back-and-forth), producing inconsistent evaluations. With `include_contents='none'`, the reviewer evaluates only the template-injected `{step_N_draft}` — a clean, repeatable signal.

> **Why `{step_N_feedback?}` (with `?`)?** On the first iteration, no feedback exists. The `?` suffix makes the template variable optional — it resolves to an empty string instead of raising `KeyError`.

#### How It Works

1. **Root Agent generates acceptance criteria** — before calling a tool, the Root Agent's LLM produces 2-4 measurable criteria based on the user's request
2. **Criteria passed as tool parameter** — `search_company_news(query="...", acceptance_criteria="1. Must include... 2. Must cite...")`
3. **Dispatch handler builds pipeline** — `build_review_pipeline()` constructs a `LoopAgent` containing the specialist and reviewer as direct sub-agents
4. **Iteration cycle** — specialist produces draft → reviewer checks against criteria → approved (exit_loop) or feedback for next iteration
5. **Result extraction** — dispatch handler reads final `draft` from session state and returns to Root Agent

#### Termination

- **Approved:** Reviewer calls `exit_loop` → `escalate=True` → LoopAgent skips specialist, exits
- **Max iterations reached:** Last draft returned with soft warning — user always gets a response

#### LLM Call Cost

Each review loop iteration makes 2 LLM calls (specialist + reviewer):

| Scenario | LLM Calls | Latency (~5-15s/call) |
|----------|-----------|----------------------|
| Approved first pass | 2 | ~10-30s |
| 1 revision | 4 | ~20-60s |
| Max iterations (3) | 6 | ~30-90s |

#### Extension to Multi-Step Workflows

The review pipeline is the **atomic building block** for Section 8.1 multi-step workflows. Multiple review pipelines compose into parallel and sequential workflow structures. See Section 8 for the full pattern including `ParallelAgent` for concurrent steps, synthesizer agents, and user approval checkpoints.

> **Planned Sprint 5-6+** — Depends on the specialist layer (Section 4.4) and config-driven agent factory. See [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e) for rationale.

See [`docs/design/agent-hierarchy.md`](design/agent-hierarchy.md) Section 9 for the review loop and workflow orchestration architecture, including the multi-step pattern and planned key files.

See [`docs/design/review-loop-implementation-plan.md`](design/review-loop-implementation-plan.md) for the phased delivery plan — 13 stories across 5 phases covering pipeline factories, dispatch integration, criteria generation, multi-step workflows, and observability.

#### Visualization Artifacts in Review Loops

When a specialist calls `create_visualization()`, the produced artifacts are stored in session state alongside the text draft. The reviewer evaluates both text quality and artifact quality — including chart type appropriateness, data completeness, and consistency between narrative and visualization.

When the specialist uses Gemini code execution, the generated Python code and its results are part of the draft output. The reviewer can evaluate computational correctness — verifying that the code logic matches the stated analysis, that results are consistent with the source data, and that percentage changes and averages are calculated correctly.

Acceptance criteria can explicitly require visualizations (e.g., "Must include a line chart showing daily sessions"). The reviewer's instruction template supports an optional `{step_N_artifacts?}` variable for artifact evaluation.

See [`docs/design/data-visualization.md`](design/data-visualization.md) Section 6 for the full review loop integration design including reviewer instruction templates and acceptance criteria patterns.

---

## 5. MCP Server Architecture

> **Roadmap:** [Feature 1.1.1: Agent Config Optimization](product-roadmap.md#feature-111-agent-config-optimization-sprint-3b-merge), [Feature 2.2: Agent Factory](product-roadmap.md#feature-22-agent-factory--phase-1) — Releases 1.1, 2.0

> For ADK internals verification, platform integration decisions, and the full `tool_filter` architecture, see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md).

### 5.1 Lazy-Loading

ADK's `McpToolset` handles lazy-loading natively — SSE connections open on first `get_tools()` call, not at deploy time. This reduces initial context from ~60,000 tokens (all tools) to ~2,000 tokens (registry index only), with 200-500ms load time per server when first accessed.

> **Important constraint:** `get_tools()` re-queries connected MCP servers each turn, but cannot connect to *new* MCP servers mid-conversation. The set of `McpToolset` instances is fixed at agent construction time. For full ADK internals (per-invocation caching in v1.26.0, SSE session pooling), see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md) Section 2.

### 5.2 Tool Registry

The ToolRegistry (`app/adk/tools/registry/tool_registry.py`) is implemented infrastructure from Sprint 2. It provides:

- **Metadata catalog** — tool definitions loaded from `app/adk/tools/registry/config/tools.yaml`
- **Search** — query by name, category, keyword with relevance scoring
- **Compact index** — `get_index_for_context()` generates ~2,000 token summary for agent context
- **Permission validation** — checks required OAuth scopes

Currently defines ~9 Google Analytics tools.

### 5.3 MCPServerManager

The `MCPServerManager` at `app/adk/mcp_config/manager.py` was built in Sprint 3 as an in-process Python singleton.

| Component | Disposition |
|-----------|-------------|
| Health monitoring + admin endpoints | **Keep** |
| Connection pooling | **Deprecated** |
| LRU eviction logic | **Deprecated** |
| Config loading + auth helpers | **Reuse** — foundation for agent factory |

See [Decision 9: MCPServerManager Disposition](https://www.notion.so/32030fd6530281ffafe8fd75298dce1d).

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

Currently defines 6 servers (1 enabled: Google Analytics). The schema will evolve to include agent config, tool_filter, and dispatch configuration for the agent factory. See [Decision 10: MCP Config Migration — YAML to Firestore](https://www.notion.so/32030fd6530281868b47e989b059e03a).

---

## 6. Skills Architecture [PLANNED]

> **Roadmap:** [Feature 3.3: Predefined Skills](product-roadmap.md#feature-33-predefined-skills), [Feature 4.2: Custom Skills](product-roadmap.md#feature-42-custom-skills--phase-1) — Releases 3.0, 4.0

> **Status:** No skills infrastructure exists in the codebase today. ADK recently added Skills support (Agent Skills specification) for packaging procedural knowledge as self-contained, progressively-disclosed units. This section defines the architecture for predefined and custom skills.

### 6.1 Overview

ADK Skills are self-contained units of expertise that provide procedural knowledge to agents. They complement tools (which execute actions) by providing instructions for HOW to use tools effectively — step-by-step workflows, best practices, decision frameworks, and domain-specific procedures.

Skills use **progressive disclosure** to minimize token overhead:

| Level | What's Loaded | When | Token Cost |
|-------|--------------|------|------------|
| **L1 (Metadata)** | Name + description | At startup, always available | ~50-100 tokens/skill |
| **L2 (Instructions)** | Full SKILL.md body | On activation (agent determines relevance) | <5,000 tokens |
| **L3 (Resources)** | Scripts, references, assets | On-demand during skill execution | Variable |

Each skill is defined by a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: analyze-campaign-performance
description: Step-by-step workflow for cross-platform campaign analysis
allowed-tools:
  - run_report_mt
  - get_meta_campaign_metrics
  - get_google_ads_report
---

## Procedure

1. Gather data from all connected platforms...
2. Normalize metrics across platforms...
3. Identify top and bottom performers...
```

### 6.2 Skill Types

| Type | Storage | Lifecycle | Example |
|------|---------|-----------|---------|
| **Predefined** | Bundled in deployment (`app/adk/skills/`) | Static, versioned with releases | `analyze-campaign-performance`, `generate-marketing-report` |
| **Custom** | Firestore (metadata) + GCS (SKILL.md content) | Dynamic, user-managed via UI | "Q2 campaign launch checklist", "Weekly client report template" |

### 6.3 Predefined Skills (Shipped)

| Skill | Description | Specialist(s) |
|-------|-------------|---------------|
| `analyze-campaign-performance` | Step-by-step workflow for cross-platform campaign analysis | Analytics |
| `generate-marketing-report` | Report generation with standard sections and formatting | Analytics, Content |
| `competitor-analysis` | Competitive research procedures using available data sources | Analytics |
| `optimize-ad-spend` | Budget optimization workflow across platforms | Execution |
| `create-email-campaign` | Email campaign creation workflow (Mailchimp) | Content |
| `research-company-news` | Company news research and summarization — successor to the `[TRANSITIONAL]` Company News Agent | Root, Analytics |

The `research-company-news` skill encapsulates the Company News Agent's functionality as a reusable skill. When the specialist layer is built, any specialist can invoke company news research without requiring a standalone agent. The Company News Agent's retrieval pipeline transitions to a scheduled automation (n8n workflow) managed by the Automation Specialist, while this skill provides the analysis and summarization procedures.

### 6.4 Custom Skills (User-Created)

Users create skills via a UI skill builder. Skills are scoped to an organization.

**Storage:**
- SKILL.md content: GCS (`gs://ken-e-skills/{org_id}/{skill_name}/SKILL.md`)
- Metadata: Firestore (`skills/{skill_id}` — name, description, org_id, created_by, status, created_at)

**Lifecycle:**
1. User creates skill via UI → validated → stored in GCS + Firestore
2. On session start, agent factory loads org's active skills via `SkillToolset`
3. `LlmAgent` reads skill catalog (L1), activates relevant skills dynamically (L2)
4. User can edit, disable, or delete skills via UI

**Validation:** Custom skills are validated at creation time for well-formed YAML frontmatter, non-empty instruction body, and `allowed-tools` references matching known tools in the ToolRegistry.

### 6.5 Integration with Agent Architecture

Skills are loaded onto agents via ADK's `SkillToolset` in the `tools` parameter:

- **Root Agent:** Predefined skills for general marketing expertise (e.g., `research-company-news`)
- **Specialist Agents:** Domain-specific predefined skills + organization's custom skills
- **Agent factory:** Reads skill config from Firestore and assembles `SkillToolset` per agent at deploy time

**Interaction with `tool_filter`:** Skills and tools are complementary. `tool_filter` controls WHICH tools are visible to the LLM on each turn; skills provide instructions for HOW to use those tools effectively. A skill's `allowed-tools` field documents which tools the skill's procedures reference, but tool visibility is still governed by `tool_filter`.

**Interaction with review loops (Section 4.6):** When a specialist executes a skill-guided workflow within a review loop, the reviewer evaluates the output against acceptance criteria — the skill provides procedural guidance but does not bypass quality gates.

### 6.6 [PLANNED] Frontend: Skill Builder

UI extension for skill management:

| Feature | Description |
|---------|-------------|
| **Skill list view** | Organization's predefined + custom skills with status indicators |
| **Create/edit form** | Name, description, markdown instructions editor with syntax highlighting |
| **Preview** | Preview skill activation behavior and token cost estimate |
| **Enable/disable toggle** | Per-skill toggle without deletion |
| **Usage analytics** | Which skills are activated most often, by which specialists |

> See [Decision 22: ADK Skills Architecture](https://www.notion.so/32030fd653028114827be82c2731ea72) for rationale.

---

## 7. Multi-Channel Support [PLANNED]

> **Roadmap:** [Feature 5.1: Slack Channel](product-roadmap.md#feature-51-slack-channel), [Feature 6.1: Voice Channel](product-roadmap.md#feature-61-voice-channel) — Releases 5.0, 6.0

> For the full API architecture and channel integration approaches, see [`docs/design/api-gateway-multi-channel.md`](design/api-gateway-multi-channel.md). Design decisions: [Decision 14: Channel-Agnostic API](https://www.notion.so/32030fd65302811ea99dfa94c3448a0d), [Decision 15: Slack Channel](https://www.notion.so/32030fd6530281148e89eb56494a7489), [Decision 16: Voice Channel](https://www.notion.so/32030fd6530281ce82d3f7bbbee439c3).

### 7.1 Architecture Overview

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

### 7.2 Unified Message Format

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

### 7.3 Channel Integration Plans

| Channel | Framework | Deployment | Timeline |
|---------|-----------|------------|----------|
| **Web** | React SPA | Firebase Hosting | Implemented |
| **Slack** | Bolt SDK | Separate Cloud Run | Sprint 8+ |
| **Voice** | Pipecat + Meeting BaaS | Dedicated service | Phase 4 |

### 7.4 Voice Channel Notes

Voice-enabled meeting participation is technically feasible using:
- **Meeting Bot API**: Recall.ai or Meeting BaaS
- **STT**: Deepgram (sub-300ms streaming latency)
- **TTS**: Cartesia (sub-100ms TTFB) or Deepgram Aura (sub-200ms TTFB)
- **Framework**: Pipecat for pipeline orchestration

Key considerations: voice responses must be concise (< 30s), target < 2s end-to-end latency, need speaker diarization. Estimated cost: ~$1.20/hour per meeting.

---

## 8. Workflow Management [PLANNED]

> **Roadmap:** [Feature 3.4: Multi-Step Workflows](product-roadmap.md#feature-34-multi-step-workflows--phase-1), [Feature 5.3: Workflow Templates](product-roadmap.md#feature-53-workflow-templates), [Feature 5.4: Advanced Workflow](product-roadmap.md#feature-54-advanced-workflow--observability) — Releases 3.0, 5.0

> **Status:** No workflow framework exists in the codebase today. The strategy agent's `execute_strategy_generation()` orchestrator is the closest pattern — it coordinates multiple sub-agents in sequence with Firestore persistence. No n8n, webhook, or cron infrastructure exists.
>
> **Revised March 18, 2026** — Structural corrections based on ADK 1.26.0 experiments. Removed `SequentialAgent` wrappers inside `LoopAgent`, added `include_contents='none'` on reviewers and synthesizers, added pipeline wrappers for `ParallelAgent` branches, added ADK Pitfalls and LLM Cost subsections.
>
> **Delivery plan:** See [`docs/design/review-loop-implementation-plan.md`](design/review-loop-implementation-plan.md) for the phased implementation plan covering Sections 8.1-8.4 — 13 stories across 5 phases.

### 8.1 Multi-Step Workflow Pattern

KEN-E will handle complex, multi-step workflows with the pattern:
1. **Plan** the workflow — Root Agent decomposes the request into steps with acceptance criteria and a dependency graph
2. **Execute** each step via a review loop (Section 4.6) — specialist produces draft, reviewer verifies against criteria
3. **Run independent steps in parallel** — `ParallelAgent` wraps concurrent review loops (each wrapped in a pipeline `SequentialAgent` for future pre/post steps)
4. **Synthesise** parallel results — a dedicated synthesizer agent with `include_contents='none'` reads parallel outputs via template substitution
5. **Get approval** at decision points — workflow pauses at approval checkpoints; Root Agent presents results and asks user to confirm
6. **Resume** where left off — workflow progress tracked in session state across conversation turns

#### ADK Constructs for Multi-Step Workflows

| Construct | Role |
|-----------|------|
| `build_review_pipeline()` | Atomic building block — one specialist + reviewer as direct `LoopAgent` sub-agents (Section 4.6). Reviewer uses `include_contents='none'`. |
| `ParallelAgent` | Wraps independent review pipelines for concurrent execution. Each branch is wrapped in a pipeline `SequentialAgent` for extensibility. |
| `SequentialAgent` | Chains phases (data gathering → synthesis → execution). Also used as pipeline wrapper around each `LoopAgent` inside `ParallelAgent` — allows future pre/post steps per branch. **Not** used inside `LoopAgent` (see Section 8.3 Pitfall 2). |
| `output_key` | Each step writes to a unique key (e.g., `step_1a_draft`); downstream steps read via `{step_1a_draft}`. Use `{key?}` (optional syntax) for keys that may not exist on first iteration. |
| Synthesizer `LlmAgent` | Dedicated agent with `include_contents='none'` that reads parallel outputs via template substitution. Instruction must explicitly state the injected data is "completed research" (see Section 8.3 Pitfall 3). |

#### Example: "Increase budgets for Meta Ads campaigns with the most engaged website visitors"

Root Agent decomposes this into phases:

```
Phase 1 — Data Gathering (parallel):
  Step 1a: Query GA for engagement rate by Meta Ads campaign
           → Analytics Specialist
           CRITERIA: Table with columns: campaign name, sessions, engagement rate

  Step 1b: Query Meta Ads for spend by campaign
           → Execution Specialist
           CRITERIA: Table with columns: campaign name, amount spent

Phase 2 — Synthesis (approval checkpoint):
  Step 2:  Synthesise optimisation plan from step 1a + 1b data
           → Synthesizer agent presents to user for approval

Phase 3 — Execution (after user approval):
  Step 3:  Execute budget changes in Meta Ads
           → Execution Specialist
           CRITERIA: Confirmation of each change made
```

This maps to ADK workflow agents:

```
CONVERSATION TURN 1:

    data_gathering (ParallelAgent)
    ├── step_1a_pipeline (SequentialAgent)
    │   └── step_1a_loop (LoopAgent, max_iterations=3)
    │       ├── analytics_specialist (LlmAgent, output_key="step_1a_draft")
    │       │     instruction: task + criteria + {step_1a_feedback?}
    │       └── step_1a_reviewer (LlmAgent, output_key="step_1a_feedback",
    │             include_contents='none', tools=[exit_loop])
    │
    └── step_1b_pipeline (SequentialAgent)
        └── step_1b_loop (LoopAgent, max_iterations=3)
            ├── execution_specialist (LlmAgent, output_key="step_1b_draft")
            │     instruction: task + criteria + {step_1b_feedback?}
            └── step_1b_reviewer (LlmAgent, output_key="step_1b_feedback",
                  include_contents='none', tools=[exit_loop])

    synthesizer (LlmAgent, include_contents='none')
      instruction: "You are given completed research from two parallel analyses.
                    Combine the following into an optimisation plan:
                    Analytics findings: {step_1a_draft}
                    Spend data: {step_1b_draft}"

    → Root Agent presents synthesised plan to user:
      "Here's my recommended plan... Shall I proceed?"

CONVERSATION TURN 2 (after user approval):

    step_3_pipeline (SequentialAgent)
    └── step_3_loop (LoopAgent, max_iterations=3)
        ├── execution_specialist (LlmAgent, output_key="step_3_draft")
        │     instruction includes: the approved plan + {step_3_feedback?}
        └── step_3_reviewer (LlmAgent, output_key="step_3_feedback",
              include_contents='none', tools=[exit_loop])

    → Returns: "I've made the following changes to your Meta Ads campaigns: ..."
```

> **Pipeline wrappers:** Each `LoopAgent` is wrapped in a `SequentialAgent` ("pipeline") inside the `ParallelAgent`. This allows future pre-processing (e.g., context injection) or post-processing (e.g., result formatting) steps per branch without restructuring the tree.

#### User Approval Splits Workflows Into Conversation Turns

User approval checkpoints do **not** require ADK pause/resume infrastructure. The Root Agent's conversational nature handles this naturally — it presents results, the user responds, and the next turn executes the remaining steps. Workflow progress is tracked in session state between turns.

#### Workflow Planning: Dynamic Pipeline Construction

The Root Agent calls an `execute_workflow(steps)` tool with a structured plan:

```python
execute_workflow(steps=[
    {"id": "1a", "specialist": "analytics", "query": "...", "criteria": "...", "depends_on": []},
    {"id": "1b", "specialist": "execution", "query": "...", "criteria": "...", "depends_on": []},
    {"id": "2",  "specialist": "root",      "query": "...",
     "depends_on": ["1a", "1b"], "approval_required": True},
    {"id": "3",  "specialist": "execution", "query": "...", "criteria": "...", "depends_on": ["2"]},
])
```

The pipeline factory reads the `depends_on` graph to determine structure:
- Steps with no shared dependencies → `ParallelAgent` (each branch wrapped in pipeline `SequentialAgent`)
- Steps that depend on a prior step → sequential (run after dependency completes)
- Steps with `approval_required: True` → return to Root Agent for user presentation
- Template variables use `{key?}` (optional syntax) for first-iteration safety

#### Second Example: "Launch a Q2 campaign for Product X"

```
Phase 1 — Research (sequential):
  Step 1: Research competitors → Analytics Specialist
  Step 2: Generate campaign strategy → Strategy Supervisor

Phase 2 — Content (parallel, depends on Phase 1):
  Step 3a: Create ad copy variations → Content Specialist
  Step 3b: Design creative briefs → Content Specialist

Phase 3 — Approval checkpoint:
  Step 4: User reviews strategy + copy → [Approval required]

Phase 4 — Deployment (sequential, after approval):
  Step 5: Deploy to Meta Ads → Execution Specialist
  Step 6: Set up weekly performance reporting → Automation Specialist
```

### 8.2 ADK Implementation Details

#### `build_review_pipeline()` Factory

The atomic building block for all review loops. Constructs a `LoopAgent` with specialist and reviewer as direct sub-agents:

```python
def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str = "review",
    max_iterations: int = 3,
) -> LoopAgent:
    """Build a review loop: specialist produces draft, reviewer evaluates against criteria."""

    draft_key = f"{output_key_prefix}_draft"
    feedback_key = f"{output_key_prefix}_feedback"

    specialist_with_output = LlmAgent(
        name=f"{specialist.name}_worker",
        model=specialist.model,
        instruction=f"""
{specialist.instruction}

ACCEPTANCE CRITERIA:
{acceptance_criteria}

PREVIOUS FEEDBACK (if any):
{{{feedback_key}?}}

Your task: produce output that meets ALL acceptance criteria. If feedback is provided,
address each point specifically.
""",
        tools=specialist.tools,
        output_key=draft_key,
    )

    reviewer = LlmAgent(
        name=f"{output_key_prefix}_reviewer",
        model="gemini-2.0-flash",
        include_contents='none',
        instruction=f"""
You are a quality reviewer. Evaluate the following draft against the acceptance criteria.

ACCEPTANCE CRITERIA:
{acceptance_criteria}

DRAFT TO REVIEW:
{{{draft_key}}}

If ALL criteria are met: call the exit_loop tool immediately.
If ANY criteria are NOT met: write specific, actionable feedback explaining what is missing
or incorrect. Do NOT call exit_loop.
""",
        output_key=feedback_key,
    )

    return LoopAgent(
        name=f"{output_key_prefix}_loop",
        sub_agents=[specialist_with_output, reviewer],
        max_iterations=max_iterations,
    )
```

Key details:
- **No `SequentialAgent`** — specialist and reviewer are direct `LoopAgent` sub-agents. `LoopAgent` iterates them sequentially and checks `escalate` between each.
- **`include_contents='none'` on reviewer** — reviewer evaluates only the template-injected `{draft_key}`, not conversation history.
- **`{feedback_key?}` (optional)** — on first iteration, no feedback exists. The `?` suffix resolves to empty string.
- **`output_key` on reviewer is `feedback_key`**, not `draft_key` — the reviewer's `exit_loop` call produces no text, so `output_key` extracts `""`. This is safe because only the specialist's `draft_key` is read downstream (see Section 8.3 Pitfall 1).

#### `build_workflow_pipeline()` Composition Pattern

Composes multiple review pipelines into a workflow with parallel and sequential phases:

```python
def build_workflow_pipeline(
    steps: list[WorkflowStep],
    specialists: dict[str, LlmAgent],
) -> Agent:
    """Build a workflow from a dependency graph of steps."""

    levels = _compute_dependency_levels(steps)

    level_agents = []
    for level_steps in levels:
        pipelines = []
        for step in level_steps:
            loop = build_review_pipeline(
                specialist=specialists[step.specialist],
                acceptance_criteria=step.criteria,
                output_key_prefix=f"step_{step.id}",
            )
            # Wrap each LoopAgent in a pipeline SequentialAgent
            pipeline = SequentialAgent(
                name=f"step_{step.id}_pipeline",
                sub_agents=[loop],
            )
            pipelines.append(pipeline)

        if len(pipelines) == 1:
            level_agents.append(pipelines[0])
        else:
            level_agents.append(ParallelAgent(
                name=f"parallel_level_{levels.index(level_steps)}",
                sub_agents=pipelines,
            ))

    if len(level_agents) == 1:
        return level_agents[0]

    return SequentialAgent(name="workflow", sub_agents=level_agents)
```

#### Synthesizer Agent Pattern

After parallel branches complete, a synthesizer agent combines results. It must use `include_contents='none'` with a strong instruction that frames the injected data as completed research:

```python
synthesizer = LlmAgent(
    name="synthesizer",
    model="gemini-2.0-flash",
    include_contents='none',
    instruction="""You are given completed research from parallel analyses.
Combine the following data into an actionable optimisation plan.

Analytics findings:
{step_1a_draft}

Spend data:
{step_1b_draft}

Produce a clear plan with specific budget recommendations.""",
    output_key="synthesis_result",
)
```

Without `include_contents='none'`, the synthesizer sees full conversation history from all parallel branches (including review loop back-and-forth), which confuses the model. With `include_contents='none'` but a weak instruction (e.g., bare bracket placeholders), the model may not understand the injected data is final. The instruction must explicitly frame it as "completed research" or equivalent.

### 8.3 ADK Pitfalls

Three experimentally validated pitfalls (ADK 1.26.0):

#### Pitfall 1: `output_key` + `exit_loop` Interaction

`exit_loop` is a tool call with no text output. If an agent has both `output_key` and calls `exit_loop`, `output_key` extracts `""` and overwrites the state key.

**Rule:** Never place `exit_loop` on the agent whose `output_key` holds important state. In the review loop, the reviewer (not the specialist) calls `exit_loop`. The reviewer's `output_key` is `feedback_key`, which is only read on the *next* iteration — by the time `exit_loop` fires, the loop is exiting, so the `""` overwrite is harmless. The specialist's `draft_key` is never overwritten by `exit_loop`.

#### Pitfall 2: `SequentialAgent` Ignores `escalate`

Only `LoopAgent` checks `escalate` between sub-agents. `SequentialAgent` runs all its sub-agents unconditionally.

**Rule:** Place agents directly under `LoopAgent` when `exit_loop` should skip subsequent agents. Wrapping specialist + reviewer in a `SequentialAgent` inside a `LoopAgent` means that if agent order were ever reversed, the `escalate` signal from `exit_loop` would be ignored by the `SequentialAgent`, and the specialist would run unnecessarily after approval.

#### Pitfall 3: Synthesizer `include_contents` Behavior

| Configuration | Behavior | Result |
|--------------|----------|--------|
| `include_contents='none'` + weak instruction (bare `{placeholders}`) | Model sees only injected text but doesn't understand context | Confused or incomplete output |
| Default (no `include_contents`) | Model sees full conversation history from all parallel branches | Confused by review loop back-and-forth; unreliable |
| `include_contents='none'` + strong instruction ("completed research from parallel analyses") | Model sees only injected text with clear framing | Correct, focused output |

**Rule:** Always pair `include_contents='none'` with an instruction that explicitly frames injected template data as completed, final input.

### 8.4 LLM Call Cost & Latency

#### Per-Step Cost

Each review loop iteration makes 2 LLM calls (specialist + reviewer):

| Scenario | LLM Calls | Latency (~5-15s/call) |
|----------|-----------|----------------------|
| Approved first pass | 2 | ~10-30s |
| 1 revision | 4 | ~20-60s |
| Max iterations (3) | 6 | ~30-90s |

#### Parallel Execution Characteristics

`ParallelAgent` runs branches concurrently. Total latency = max(branch latencies), not sum:

| Workflow Shape | Total LLM Calls | Wall-Clock Latency |
|---------------|-----------------|-------------------|
| 2 parallel steps, both approved first pass | 4 (2+2) | ~10-30s (parallel) |
| 2 parallel steps + synthesizer + 1 execution step | 4+1+2 = 7 minimum | ~30-90s total |
| Same with 1 revision each | 4+4+1+4 = 13 | ~40-120s total |

Add ~1 LLM call for the synthesizer agent. Approval checkpoints add user wait time (not LLM latency).

### 8.5 Workflow State Machine

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

### 8.6 Workflow Data Model

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

### 8.7 Persistence & Recovery

| Concern | Approach |
|---------|----------|
| **Crash recovery** | Workflow state persisted to Firestore after each step transition. On recovery, resume from last completed step. |
| **Idempotency** | Each step execution keyed by `(workflow_id, step_id, attempt)`. Before executing, check if output already exists for this attempt. |
| **Partial failure** | Individual step failure marks step as FAILED, increments `attempts`. If `attempts < max_retries`, re-queue. If exhausted, mark workflow as FAILED with last error. |
| **User interruption** | Steps in AWAITING_INPUT pause workflow. User response writes to `step.inputs` and transitions step to IN_PROGRESS. |
| **Long-running steps** | Steps that take >30s (e.g., strategy generation) execute asynchronously. Workflow polls step status. Frontend shows progress. |

### 8.8 [PLANNED] n8n Integration

> **Roadmap:** [Feature 4.1: Automation Specialist + n8n](product-roadmap.md#feature-41-automation-specialist--n8n) — Release 4.0

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

## 9. Integration with Evaluation Framework

> **Roadmap:** [Feature 2.5: MER-E Phase 0](product-roadmap.md#feature-25-mer-e-phase-0--trace-extraction-parallel-track), [Feature 3.5: MER-E Phase 1](product-roadmap.md#feature-35-mer-e-phase-1--quality-scoring-parallel-track), [Feature 4.3: MER-E Phase 2](product-roadmap.md#feature-43-mer-e-phase-2--human-feedback--patterns-parallel-track-phase-1), [Feature 4.4: A/B Testing](product-roadmap.md#feature-44-ab-testing-infrastructure) — Releases 2.0–4.0

### 9.1 Overview

The agentic harness integrates with the Self-Improving Evaluation Framework (MER-E) to enable:
1. **Automatic tracing** of all agent outputs via Weave
2. **Quality scoring** via LLM-based evaluation
3. **Human feedback collection** for alignment
4. **Continuous improvement** of agent prompts

### 9.2 Trace Instrumentation

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

#### 9.2.1 Code Execution Traces

When the Analytics Specialist uses Gemini code execution, the LLM response contains `executable_code` and `code_execution_result` part types interleaved with text parts within L3 LLM Call spans. These are NOT separate L3 spans — they are additional content parts within the `generate_content` response.

| Part Type | Key Fields | Description |
|-----------|-----------|-------------|
| `executable_code` | `code` (string) | Python code generated by the model |
| `code_execution_result` | `output` (string), `outcome` (enum) | Execution output and success/failure status |

These parts appear as siblings of text parts within a single `generate_content` span. MER-E extractors should detect `executable_code` parts and pair them with their corresponding `code_execution_result` to evaluate computational correctness.

See `docs/trace-structure-spec.md` Section 4.4.1 for the full trace structure specification and MER-E extraction guidance.

### 9.3 Output Type Classification

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

### 9.4 [PLANNED] Feedback Collection

> **Roadmap:** [Feature 4.3: MER-E Phase 2 — Human Feedback](product-roadmap.md#feature-43-mer-e-phase-2--human-feedback--patterns-parallel-track-phase-1) — Release 4.0

A feedback collection system will enable human evaluation alignment:
- Queue feedback requests for users after agent outputs
- Store ratings (1-5) and factor-level ratings in Firestore
- Trigger alignment analysis when sufficient feedback is collected

### 9.5 [PLANNED] A/B Testing Support

> **Roadmap:** [Feature 4.4: A/B Testing Infrastructure](product-roadmap.md#feature-44-ab-testing-infrastructure) — Release 4.0

The harness will support A/B testing of agent configurations:
- Consistent hash-based variant assignment per account
- Firestore-stored variant configurations
- Trace metadata includes `experiment_id` and `variant_name` for evaluation

---

## 10. Infrastructure Requirements

### 10.1 Compute Requirements

| Component | Specification | Scaling |
|-----------|--------------|---------|
| **API Server (Cloud Run)** | 4 vCPU, 8GB RAM | 2-10 instances based on load |
| **Agent Engine (Vertex AI)** | Managed by Google | Auto-scaled |
| **GA MCP Server (Cloud Run)** | 2 vCPU, 4GB RAM | On-demand |

### 10.2 Cost Estimates

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
- **Gemini code execution** adds minimal cost — billed as additional output tokens (~500-2,000 per request, ~$0.00015-0.0006 at Flash pricing). No separate compute cost; Google manages the sandbox.
- **Voice latency gap:** Current Agent Engine response time is ~7-13s. Voice requires <2s end-to-end. Voice may need a lightweight agent path or a streaming-optimized serving strategy — this is an unsolved prerequisite for Phase 4.

#### Cost Monitoring

The `UsageTracker` (`app/adk/tracking/usage.py`) records per-tool-call events in Firestore with batched writes (100 events or 30s flush). Alert support: `AlertData` model supports threshold-based alerts. **Scalability concern:** At heavy usage, individual Firestore documents per tool call create expensive aggregation queries. A time-bucketed rollup strategy (hourly/daily pre-aggregated counters) is recommended before production scale.

### 10.3 Architecture Diagram

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

## 11. Resilience, Security & Testing

### 11.1 Current Error Handling Patterns

The codebase has multi-layer error handling. This section documents what exists and identifies gaps.

#### 11.1.1 Implemented Patterns

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

#### 11.1.2 Gap: No Circuit Breaker Pattern

Current retry logic always attempts up to `max_retries` even if a service is clearly down. Missing:
- **Circuit breaker state machine** (CLOSED → OPEN → HALF-OPEN) for MCP servers and Agent Engine
- **Failure rate threshold** — e.g., if >50% of calls to an MCP server fail in 60s, stop sending for 30s
- **Cascading failure protection** — if GA MCP is down, GA agent should fail fast rather than retry 3x per dispatch

**Recommendation:** Implement circuit breaker at the `McpToolset` or dispatch handler level. ADK's `before_tool_callback` could check circuit state before allowing tool execution.

#### 11.1.3 Gap: Firestore Unavailability at Deploy Time

If Firestore is unreachable during `deploy_ken_e.py` execution, `load_config_from_firestore()` raises `FirestoreConnectionError`. The deployment fails — there are no bundled fallback configs.

**Recommendation:** Bundle last-known-good config snapshots in the deployment package. Deploy script should catch `FirestoreConnectionError` and fall back to bundled config with a warning.

### 11.2 Credential Lifecycle & Security Model

#### 11.2.1 Current OAuth Flow

| Step | Implementation | Key File |
|------|---------------|----------|
| **Authorization** | Frontend initiates `GET /api/oauth/authorize/google-analytics`. Generates state token (15-min TTL in Firestore). Redirects to Google with `offline` + `consent` prompts. Scopes: `analytics.readonly`, `analytics.edit`. | `routers/oauth_integrations.py` |
| **Callback** | Validates state token (CSRF protection). Exchanges auth code for tokens. Preserves existing refresh_token if Google doesn't return new one. Encrypts and stores in Firestore. | `routers/oauth_integrations.py` |
| **Storage** | Credentials encrypted via `EncryptionService` (Fernet-based). Stored in Firestore via `IntegrationCredentialsService`. Keys: `access_token`, `refresh_token`, `expires_at`, `tenant_id`, `selected_property_ids`. | `ga_credential_helper.py`, `encryption_service.py` |
| **Injection** | API loads creds from Firestore at session creation, refreshes if expired, writes to ADK session state as `ga_credentials`. Cached in Redis (10-min TTL). | `routers/chat.py` |
| **Per-request auth** | `_ga_header_provider()` reads `ga_credentials` from `context.state`, builds `Authorization: Bearer` + `X-Tenant-ID` headers. Called per turn by McpToolset. | `google_analytics_agent_v4.py` |
| **Token refresh** | On-demand: checks `expires_at` with 5-min buffer. Calls `https://oauth2.googleapis.com/token` with 10s timeout. Updates Firestore + returns refreshed creds. | `ga_credential_helper.py` |
| **Reauth signal** | `adk_before_tool_callback` detects expired/revoked tokens → returns `{requires_reauth: true}` → frontend triggers re-authorization flow. | `security/hooks.py` |

#### 11.2.2 Gaps in Credential Security

| Gap | Risk | Recommendation |
|-----|------|----------------|
| **No proactive token refresh** | Tokens may expire mid-conversation if session is long | Add background refresh task or refresh during `InstructionProvider` (runs each turn) |
| **No refresh token rotation tracking** | Can't detect if refresh token was revoked by user in Google | Track last successful refresh timestamp; if refresh fails, immediately signal reauth |
| **Fernet encryption in dev, KMS TODO in prod** | Local encryption key management is not production-grade | Complete `EncryptionService` KMS integration before production launch |
| **No credential expiry notifications** | Users discover broken credentials only when they try to use an agent | Add expiry monitoring: warn user in frontend when creds expire within 24h |
| **No cross-tenant isolation checks** | Credential retrieval uses `account_id` but no additional tenant boundary enforcement | Add explicit tenant context validation in `IntegrationCredentialsService` |

#### 11.2.3 Multi-Tenant Security for Specialist Agents

When specialist agents connect to multiple MCP servers per user (Sprint 5-6), each `McpToolset` needs its own `header_provider` that reads the correct platform credentials from session state:

```
Session state keys (per-platform):
  ga_credentials      → GA MCP header_provider
  google_ads_credentials → Google Ads MCP header_provider
  hubspot_credentials → HubSpot MCP header_provider
  meta_ads_credentials → Meta Ads SDK tool_context.state
```

The API layer must load and refresh credentials for all connected platforms at session creation time. This is a linear scaling problem: N platforms = N credential loads. Mitigation: parallel loading (already implemented for GA), Redis caching per-platform.

> For the multi-tenancy model (one MCP server instance per platform serving all accounts, scoped by OAuth token), see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md) Section 3.

### 11.3 Rate Limiting & Platform Quota Management

#### 11.3.1 Current Rate Limiting

| Scope | Implementation | Key File |
|-------|---------------|----------|
| **Auth endpoints** | In-memory sliding window per IP. Login: 10/min, 50/hr. Token: 60/min, 1000/hr. Password reset: 3/min, 10/hr. | `auth/rate_limiting.py` |
| **External APIs** | Redis-backed per-API limits. Wikipedia: 10/min. Wikidata: 10/min. Gemini: 5/min. Fail-open if cache unavailable. | `services/rate_limiter.py` |
| **Firestore operations** | Retry with backoff on `ResourceExhausted` (Firestore's rate limit signal). | `strategy_agent/retry_utils.py` |

#### 11.3.2 Gap: No Marketing Platform Quota Management

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

### 11.4 Risk Assessment Matrix

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

### 11.5 Test Locations

| Test Suite | Location | Coverage |
|-----------|----------|----------|
| API unit tests | `api/tests/unit/` | Chat, auth, sessions, context |
| API integration tests | `api/tests/` | End-to-end API flows |
| Agent tests | `app/adk/agents/tests/` | Registry, dispatch, context loading |
| Shared module tests | `shared/tests/` | Context utils, token estimation |
| Load tests | `tests/load_test/` | Locust performance tests |

### 11.6 Performance Benchmarks

| Operation | Target | Acceptable | Critical | Measured |
|-----------|--------|------------|----------|----------|
| Session initialization | < 500ms | < 1s | > 2s | — |
| Tool search | < 200ms | < 500ms | > 1s | — |
| MCP server load | < 500ms | < 1s | > 2s | — |
| Agent response (simple) | < 5s | < 10s | > 15s | ~7-13s |
| Agent response (complex) | < 10s | < 20s | > 30s | — |
| Context section load | < 300ms | < 500ms | > 1s | — |

---

## 12. Sprint-Based Roadmap

### 12.1 Completed (Sprints 1-4)

| Sprint | What Was Built | Status |
|--------|---------------|--------|
| **Sprint 1** | Session state architecture (creds + org context in ADK state), authorization checks, KEN-E root agent with dispatch | Canonical |
| **Sprint 2** | HierarchicalContextManager, ToolRegistry, EventsCompactionConfig + ContextCacheConfig in deploy, shared context utils | Canonical |
| **Sprint 3** | MCPServerManager, security hooks, usage tracking, MCP admin endpoints | Partially superseded (see Section 5.3) |
| **Sprint 3b** | Agent registry + Firestore config, API allowlist from registry, context loader consolidation, chat latency optimization (~23s → ~7-13s), structured logging, Prometheus, Agent Engine tracing, MCP health ping | Canonical |
| **Sprint 4** | Weave SDK init, @weave.op() instrumentation, trace hierarchy (before/after callbacks), structured logging with request_id | Canonical |

### 12.2 In Progress

| Item | Sprint | Description |
|------|--------|-------------|
| Sprint 3b PR | 3b | Agent config optimization, final review |

### 12.3 Planned

| Item | Timeline | Description |
|------|----------|-------------|
| **Specialist agents + agent factory** | Sprint 5-6 | Config-driven agent assembly, category-based tool routing |
| **Additional MCP servers** | Sprint 5-6 | Google Ads MCP, HubSpot MCP integration |
| **SDK function tools** | Sprint 5-6 | Meta Ads, Mailchimp direct SDK integration |
| **Skills architecture** | Sprint 5-6 | Predefined skills bundled, custom skills via UI (Section 6) |
| **Slack channel** | Sprint 8+ | Bolt SDK integration on separate Cloud Run |
| **Workflow management** | Sprint 8+ | Multi-step task tracking with Firestore persistence. See [`review-loop-implementation-plan.md`](design/review-loop-implementation-plan.md) for phased delivery plan. |
| **Gemini code execution** | Sprint 5-6 | Enable on Analytics Specialist via `GenerateContentConfig`. Depends on specialist agents + agent factory. |
| **Data visualization & artifacts** | Sprint 7+ | Vega-Lite artifacts in ChatResponse, `create_visualization()` tool, frontend chart rendering. See [`data-visualization.md`](design/data-visualization.md). |
| **Voice channel** | Phase 4 | Pipecat + Meeting BaaS |
| **A/B testing** | Phase 4 | Experiment infrastructure for agent configs |

---

## 13. Appendices

### Appendix A: Platform Integration Reference

| Platform | Integration Type | MCP/SDK | Status |
|----------|-----------------|---------|--------|
| **Google Analytics** | Self-hosted MCP | GA MCP on Cloud Run | Implemented |
| **Google Ads** | Hybrid: MCP reads + SDK writes | Google official MCP + `google-ads` SDK | Planned |
| **HubSpot** | Provider-hosted MCP | `mcp.hubspot.com` | Planned |
| **Meta Ads** | SDK function tools | `facebook-business` — shared: Analytics (reads) + Execution (reads + writes) | Planned |
| **Mailchimp** | SDK function tools | `mailchimp-marketing` | Planned |
| **Microsoft Ads** | Deferred | — | No current demand |
| **Gemini Code Execution** | Built-in model capability | `GenerateContentConfig.tools` | Planned (Sprint 5-6) |

> For detailed integration rationale per platform (hybrid MCP+SDK pattern, read-only limitations and CMO impact, SDK function tools code pattern), see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md) Sections 4 and 8.

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
| **Skill** | Self-contained unit of expertise (SKILL.md) providing procedural knowledge to agents via progressive disclosure (L1/L2/L3) |
| **SkillToolset** | ADK class for incorporating skills into `LlmAgent` via the `tools` parameter |
| **SKILL.md** | Markdown file with YAML frontmatter defining a skill's name, description, allowed-tools, and procedural instructions |
| **ToolRegistry** | Searchable metadata catalog for ~400 tools; planned as driver for `tool_filter` predicates |
| **ReadonlyContext** | ADK read-only view of session state (`MappingProxyType`), passed to `InstructionProvider` and `tool_filter`. Live view of the mutable state dict — sees `CallbackContext` writes immediately. |
| **CallbackContext** | ADK mutable context passed to `before_agent_callback`, `after_agent_callback`, and model callbacks. Writes to `callback_context.state` go to `session.state` with delta tracking. |
| **before_agent_callback** | ADK callback that fires before each LLM turn's tool resolution. Receives `CallbackContext` (mutable). Used for Weave tracing and ToolRegistry-driven `tool_filter` state writes. |
| **Vega-Lite** | Declarative JSON-based visualization grammar. Agents produce Vega-Lite chart specs via `create_visualization()`; the frontend renders them. See [`data-visualization.md`](design/data-visualization.md). |
| **Artifact** | A structured output (e.g., Vega-Lite chart spec) produced alongside text by specialist agents. Delivered to the frontend via the `artifacts` field on `ChatResponse`. |
| **create_visualization** | Python function tool available to all specialist agents. Produces a Vega-Lite artifact and writes it to `response_artifacts` session state. Not an MCP tool. |
| **Code Execution (Gemini)** | Built-in Gemini model capability that generates and runs Python code in a Google-managed sandbox. Enabled via `GenerateContentConfig.tools = [Tool(code_execution=ToolCodeExecution())]`. Returns `executable_code` and `code_execution_result` parts in the LLM response. |
| **Built-in Model Capability** | A capability provided natively by the LLM model (e.g., Gemini code execution), configured via `GenerateContentConfig` rather than as an MCP or SDK tool. Zero context overhead — no tool definition is sent. Not subject to `tool_filter`. |
| **ToolCodeExecution** | ADK/Gemini class that enables code execution when added to `GenerateContentConfig.tools`. Part of `google.genai.types`. |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-10 | Development Team | Initial design document |
| 2.0 | 2026-03-10 | Development Team | Updated to reflect Sprints 1-4 implementation. Replaced fictional code with actual implementations. Marked unbuilt features as [PLANNED]. |
| 2.1 | 2026-03-10 | Development Team | Design review: Added `tool_filter` + ToolRegistry architecture (Section 4.3). Updated ADK internals analysis. Added sprint-3b dependency note. Fixed Deepgram latency claim. |
| 2.2 | 2026-03-11 | Development Team | Cross-reference pass: added links to design docs (`agent-hierarchy.md`, `mcp-architecture.md`, `api-gateway-multi-channel.md`) and Notion Design Decisions database. Fixed Section 10 duplicate numbering and ToC mismatch. |
| 2.3 | 2026-03-11 | Development Team | Architecture accuracy pass: reframed doc as architecture reference (current + `[PLANNED]`). Split Sections 1.3, 2.3 into current/planned. Rewrote Section 2.1 diagram for target architecture. Expanded Section 3.6 (session state keys, token visibility, billing/usage tracking). Added Decisions 19-20 links. |
| 2.4 | 2026-03-11 | Development Team | Added Section 4.6 Review Loop Pattern (Generator-Critic with LoopAgent). Updated Section 2.3.2 request flow to show review loop. Rewrote Section 8.1 with ADK workflow agent architecture, ParallelAgent for concurrent steps, Meta Ads optimisation example, and dynamic pipeline construction. Added Decision 21 link. |
| 2.5 | 2026-03-11 | Development Team | Added `[TRANSITIONAL]` convention for GA Agent and Company News Agent (successors documented). Added Meta Ads SDK shared access (Analytics reads + Execution reads/writes via `tool_filter`). Added Section 6 Skills Architecture (predefined + custom skills, SkillToolset integration, skill builder UI). Renumbered Sections 6-12 → 7-13. Added Decision 22 link. Updated glossary with Skill/SkillToolset/SKILL.md terms. |
| 2.6 | 2026-03-18 | Development Team | ADK 1.26.0 experiment corrections: removed `SequentialAgent` wrappers inside `LoopAgent` (Sections 4.6, 8.1), added `include_contents='none'` on reviewers and synthesizers, added `{key?}` optional template syntax, added pipeline `SequentialAgent` wrappers for `ParallelAgent` branches. New subsections: 8.2 ADK Implementation Details (`build_review_pipeline()` and `build_workflow_pipeline()` factories, synthesizer pattern), 8.3 ADK Pitfalls (3 validated pitfalls), 8.4 LLM Call Cost & Latency. Renumbered 8.2-8.5 → 8.5-8.8. Added LLM call cost table to Section 4.6. |
| 2.7 | 2026-03-18 | Development Team | Experiment #4 resolution — resolved `tool_filter` driver pattern as `before_agent_callback`. Updated Section 3.6.2 (`tool_filter_state` Set By). Resolved `[PLANNED] tool_filter driver` in Section 4.3 (added execution order note). Added specialist callback chaining note to Section 4.2. Added ReadonlyContext, CallbackContext, before_agent_callback glossary entries (Appendix D). See [Decision 23](https://www.notion.so/32730fd6530281999389eb3116e7585c). |
| 2.8 | 2026-03-18 | Development Team | Data visualization & artifacts. Added Vega-Lite artifacts decision to Section 1.4. Updated Section 2.3.2 request flow (create_visualization in specialist, artifacts extraction in response). Added `response_artifacts` to Section 3.6.2 session state. Added visualization blockquote to Section 4.4. Added "Visualization Artifacts in Review Loops" subsection after Section 4.6. Added data visualization row to Section 12.3 roadmap. Added Vega-Lite, Artifact, create_visualization glossary entries (Appendix D). Created [`data-visualization.md`](design/data-visualization.md). |
| 2.9 | 2026-03-18 | Development Team | Gemini native code execution. Added code execution decision to Section 1.4. Added Tool Type Taxonomy table to Section 4.3 (MCP Tools, SDK Function Tools, Built-in Model Capabilities). Updated Analytics Specialist in Sections 4.4 and 4.5 with Gemini code execution. Added code execution note to Section 4.6 review loop. Added Section 9.2.1 Code Execution Traces. Added code execution cost bullet to Section 10.2. Added Gemini code execution to Section 12.3 roadmap and Appendix A. Added Code Execution (Gemini), Built-in Model Capability, ToolCodeExecution to Appendix D glossary. |

---

*This document describes the architecture for the KEN-E agentic harness. It is updated as implementation progresses.*
