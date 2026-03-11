# KEN-E Agentic Harness Design Document

**Version:** 2.4
**Date:** March 11, 2026
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
6. [Multi-Channel Support [PLANNED]](#6-multi-channel-support-planned)
7. [Workflow Management [PLANNED]](#7-workflow-management-planned)
8. [Integration with Evaluation Framework](#8-integration-with-evaluation-framework)
9. [Infrastructure Requirements](#9-infrastructure-requirements)
10. [Resilience, Security & Testing](#10-resilience-security--testing)
11. [Sprint-Based Roadmap](#11-sprint-based-roadmap)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the comprehensive design for KEN-E's agentic harness — the software framework that enables KEN-E to function as an autonomous AI marketing agent. The harness orchestrates multiple specialized agents using Google's Agent Development Kit (ADK) to complete complex marketing tasks including strategy development, content creation, campaign execution, and performance optimization.

This document serves as an architecture reference: it describes both the current implementation and planned extensions. Features not yet built are marked `[PLANNED]` throughout. As planned features are deployed, this document is updated to collapse the distinction.

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
│  │  │           │ │   Agent   │ │                           │   │     │
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
│   ├── News Agent (LlmAgent)                                            │
│   ├── Strategy Supervisor (multi-agent)                                 │
│   └── [PLANNED] Specialist Agents (config-driven via agent factory)    │
│       ├── Analytics Specialist (GA MCP, Google Ads MCP)                │
│       ├── Content Specialist (HubSpot MCP, Mailchimp SDK)              │
│       ├── Execution Specialist (Meta Ads SDK, Google Ads MCP)          │
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
    │    • KEN-E relays to user                                │
    │    • Background: update session preview + Redis cache    │
    └─────────────────────────────────────────────────────────┘
```

See Section 4.6 for the review loop pattern design and Section 7.1 for multi-step workflow application.

### 2.4 Agent Type Selection (Google ADK)

| Agent | ADK Type | Status |
|-------|----------|--------|
| **KEN-E Root** | `LlmAgent` | Implemented |
| **Company News** | `LlmAgent` | Implemented |
| **Google Analytics** | `LlmAgent` + `McpToolset` | Implemented |
| **Strategy Supervisor** | Multi-agent (custom) | Implemented |
| **Analytics Specialist** | `LlmAgent` | [PLANNED] |
| **Content Specialist** | `LlmAgent` | [PLANNED] |
| **Execution Specialist** | `LlmAgent` | [PLANNED] |
| **Automation Specialist** | `LlmAgent` | [PLANNED] |

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
| `tool_filter_state` | ToolRegistry search results driving per-turn `tool_filter` predicates | ToolRegistry (written per-turn) |

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

MCP server connections are fixed at deploy time — only *which tools* are visible is dynamic per-turn.

See [Decision 7: Token Budget Strategy](https://www.notion.so/32030fd6530281da97cef1729242ccd1) and [Decision 8: ToolRegistry](https://www.notion.so/32030fd65302813ab406cf15f7e1e7f6) in the Design Decisions database.

### 4.4 [PLANNED] Specialist Agents

The specialist layer (Sprint 5-6) partitions tools by domain.

| Specialist | Tool Sources | Integration Type | Key Capabilities |
|-----------|-------------|-----------------|------------------|
| **Analytics** | GA MCP, Google Ads MCP | McpToolset | Data queries, reporting, performance analysis |
| **Content** | HubSpot MCP, Mailchimp SDK | McpToolset + SDK | CRM data, email campaigns, content management |
| **Execution** | Meta Ads SDK, Google Ads SDK (writes), Google Ads MCP (reads) | SDK + McpToolset | Campaign deployment, budget management |
| **Automation** | n8n MCP | McpToolset | Workflow creation, scheduling |

Each specialist will be assembled by the config-driven agent factory, reading from Firestore config.

### 4.5 Agent Summary Table

#### Current (Sprints 1-4)

| Agent | Type | Config Doc ID | Key Files |
|-------|------|---------------|-----------|
| KEN-E Root | LlmAgent | `ken_e_chatbot` | `app/adk/agents/ken_e_agent.py` |
| Company News | LlmAgent | `company_news_agent` | `app/adk/agents/company_news_chatbot/agent.py` |
| Google Analytics | LlmAgent + McpToolset | `google_analytics_agent` | `app/adk/agents/google_analytics_agent_v4.py` |
| Strategy Supervisor | Multi-agent | 8 sub-config docs | `app/adk/agents/create_strategy_docs_supervisor.py` |

#### [PLANNED] Specialist Layer (Sprint 5-6+)

| Agent | Type | Tool Sources | Assembled By |
|-------|------|-------------|--------------|
| Analytics Specialist | LlmAgent + McpToolset | GA MCP, Google Ads MCP | Config-driven agent factory |
| Content Specialist | LlmAgent + McpToolset + SDK | HubSpot MCP, Mailchimp SDK | Config-driven agent factory |
| Execution Specialist | LlmAgent + SDK + McpToolset | Meta Ads SDK, Google Ads SDK (writes), Google Ads MCP (reads) | Config-driven agent factory |
| Automation Specialist | LlmAgent + McpToolset | n8n MCP | Config-driven agent factory |

### 4.6 [PLANNED] Review Loop Pattern (Generator-Critic)

Every specialist delegation is wrapped in a **review loop** that enforces acceptance criteria before returning results to the user. This uses ADK's native workflow agents:

| ADK Construct | Role |
|---------------|------|
| `LoopAgent` | Repeats specialist + reviewer cycle until approved or `max_iterations` reached |
| `SequentialAgent` | Chains specialist → reviewer within each iteration |
| `output_key` | Specialist writes to `"draft"`, reviewer writes to `"review_feedback"` — shared via session state |
| `exit_loop` | Built-in tool the reviewer calls when all acceptance criteria are met |

#### Review Loop Structure

```
build_review_pipeline(specialist, acceptance_criteria, max_iterations=3)
→ returns:

    review_loop (LoopAgent, max_iterations=3)
    └── work_cycle (SequentialAgent)
        ├── specialist (LlmAgent, output_key="step_N_draft")
        │     instruction: task + acceptance_criteria + {step_N_feedback}
        │     tools: [specialist-specific MCP/SDK tools]
        └── reviewer (LlmAgent, output_key="step_N_feedback")
              instruction: evaluate {step_N_draft} vs acceptance_criteria
              tools: [exit_loop]
              ALL criteria met → call exit_loop
              ANY not met → write actionable feedback
```

#### How It Works

1. **Root Agent generates acceptance criteria** — before calling a tool, the Root Agent's LLM produces 2-4 measurable criteria based on the user's request
2. **Criteria passed as tool parameter** — `search_company_news(query="...", acceptance_criteria="1. Must include... 2. Must cite...")`
3. **Dispatch handler builds pipeline** — `build_review_pipeline()` constructs a `LoopAgent` wrapping a `SequentialAgent(specialist, reviewer)`
4. **Iteration cycle** — specialist produces draft → reviewer checks against criteria → approved (exit_loop) or feedback for next iteration
5. **Result extraction** — dispatch handler reads final `draft` from session state and returns to Root Agent

#### Termination

- **Approved:** Reviewer calls `exit_loop` → `escalate=True` → LoopAgent exits
- **Max iterations reached:** Last draft returned with soft warning — user always gets a response
- **Token overhead:** ~1,000 tokens per iteration (reviewer turn). With `max_iterations=3`, worst case ~3,000 tokens additional

#### Extension to Multi-Step Workflows

The review pipeline is the **atomic building block** for Section 7.1 multi-step workflows. Multiple review pipelines compose into parallel and sequential workflow structures. See Section 7.1 for the full pattern including `ParallelAgent` for concurrent steps and user approval checkpoints.

> **Planned Sprint 5-6+** — Depends on the specialist layer (Section 4.4) and config-driven agent factory. See [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e) for rationale.

---

## 5. MCP Server Architecture

> For ADK internals verification, platform integration decisions, and the full `tool_filter` architecture, see [`docs/design/mcp-architecture.md`](design/mcp-architecture.md).

### 5.1 Lazy-Loading

ADK's `McpToolset` handles lazy-loading natively — SSE connections open on first `get_tools()` call, not at deploy time. This reduces initial context from ~60,000 tokens (all tools) to ~2,000 tokens (registry index only), with 200-500ms load time per server when first accessed.

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

## 6. Multi-Channel Support [PLANNED]

> For the full API architecture and channel integration approaches, see [`docs/design/api-gateway-multi-channel.md`](design/api-gateway-multi-channel.md). Design decisions: [Decision 14: Channel-Agnostic API](https://www.notion.so/32030fd65302811ea99dfa94c3448a0d), [Decision 15: Slack Channel](https://www.notion.so/32030fd6530281148e89eb56494a7489), [Decision 16: Voice Channel](https://www.notion.so/32030fd6530281ce82d3f7bbbee439c3).

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
1. **Plan** the workflow — Root Agent decomposes the request into steps with acceptance criteria and a dependency graph
2. **Execute** each step via a review loop (Section 4.6) — specialist produces draft, reviewer verifies against criteria
3. **Run independent steps in parallel** — `ParallelAgent` wraps concurrent review loops
4. **Get approval** at decision points — workflow pauses at approval checkpoints; Root Agent presents results and asks user to confirm
5. **Resume** where left off — workflow progress tracked in session state across conversation turns

#### ADK Constructs for Multi-Step Workflows

| Construct | Role |
|-----------|------|
| `build_review_pipeline()` | Atomic building block — one specialist + reviewer LoopAgent (Section 4.6) |
| `ParallelAgent` | Wraps independent review loops for concurrent execution |
| `SequentialAgent` | Chains phases (data gathering → synthesis → execution) |
| `output_key` | Each step writes to a unique key (e.g., `step_1a_draft`); downstream steps read via `{step_1a_draft}` |

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

Phase 2 — Synthesis (Root Agent, approval checkpoint):
  Step 2:  Create optimisation plan from step 1a + 1b data
           → Present to user for approval

Phase 3 — Execution (after user approval):
  Step 3:  Execute budget changes in Meta Ads
           → Execution Specialist
           CRITERIA: Confirmation of each change made
```

This maps to ADK workflow agents:

```
CONVERSATION TURN 1:

    data_gathering (ParallelAgent)
    ├── step_1a_loop (LoopAgent, max_iterations=3)
    │   └── work_cycle (SequentialAgent)
    │       ├── analytics_specialist (output_key="step_1a_draft")
    │       └── reviewer (output_key="step_1a_feedback", tools=[exit_loop])
    │
    └── step_1b_loop (LoopAgent, max_iterations=3)
        └── work_cycle (SequentialAgent)
            ├── execution_specialist (output_key="step_1b_draft")
            └── reviewer (output_key="step_1b_feedback", tools=[exit_loop])

    → Root Agent reads step_1a_draft + step_1b_draft
    → Synthesises optimisation plan
    → Presents to user: "Here's my recommended plan... Shall I proceed?"

CONVERSATION TURN 2 (after user approval):

    step_3_loop (LoopAgent, max_iterations=3)
    └── work_cycle (SequentialAgent)
        ├── execution_specialist (output_key="step_3_draft")
        │     instruction includes: the approved plan
        └── reviewer (output_key="step_3_feedback", tools=[exit_loop])

    → Returns: "I've made the following changes to your Meta Ads campaigns: ..."
```

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
- Steps with no shared dependencies → `ParallelAgent`
- Steps that depend on a prior step → sequential (run after dependency completes)
- Steps with `approval_required: True` → return to Root Agent for user presentation

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

## 10. Resilience, Security & Testing

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

### 10.5 Test Locations

| Test Suite | Location | Coverage |
|-----------|----------|----------|
| API unit tests | `api/tests/unit/` | Chat, auth, sessions, context |
| API integration tests | `api/tests/` | End-to-end API flows |
| Agent tests | `app/adk/agents/tests/` | Registry, dispatch, context loading |
| Shared module tests | `shared/tests/` | Context utils, token estimation |
| Load tests | `tests/load_test/` | Locust performance tests |

### 10.6 Performance Benchmarks

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
| **Google Ads** | Hybrid: MCP reads + SDK writes | Google official MCP + `google-ads` SDK | Planned |
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
| 2.0 | 2026-03-10 | Development Team | Updated to reflect Sprints 1-4 implementation. Replaced fictional code with actual implementations. Marked unbuilt features as [PLANNED]. |
| 2.1 | 2026-03-10 | Development Team | Design review: Added `tool_filter` + ToolRegistry architecture (Section 4.3). Updated ADK internals analysis. Added sprint-3b dependency note. Fixed Deepgram latency claim. |
| 2.2 | 2026-03-11 | Development Team | Cross-reference pass: added links to design docs (`agent-hierarchy.md`, `mcp-architecture.md`, `api-gateway-multi-channel.md`) and Notion Design Decisions database. Fixed Section 10 duplicate numbering and ToC mismatch. |
| 2.3 | 2026-03-11 | Development Team | Architecture accuracy pass: reframed doc as architecture reference (current + `[PLANNED]`). Split Sections 1.3, 2.3 into current/planned. Rewrote Section 2.1 diagram for target architecture. Expanded Section 3.6 (session state keys, token visibility, billing/usage tracking). Added Decisions 19-20 links. |
| 2.4 | 2026-03-11 | Development Team | Added Section 4.6 Review Loop Pattern (Generator-Critic with LoopAgent). Updated Section 2.3.2 request flow to show review loop. Rewrote Section 7.1 with ADK workflow agent architecture, ParallelAgent for concurrent steps, Meta Ads optimisation example, and dynamic pipeline construction. Added Decision 21 link. |

---

*This document describes the architecture for the KEN-E agentic harness. It is updated as implementation progresses.*
