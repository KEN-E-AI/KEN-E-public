# KEN-E System Architecture

**Version:** 4.2
**Date:** April 2026
**Author:** Development Team

> **Role of this document.** This is the canonical, high-level system architecture for KEN-E. It covers the cross-cutting concerns — context management, agent runtime, multi-step orchestration, evaluation framework, infrastructure, resilience, and security — and frames each major component with a short summary and a pointer to the detailed component doc. **Detailed, evolving implementation content lives in component docs and is not duplicated here.** See §1.6 for the full component landscape; individual components are covered in the sections that follow.
>
> **What this doc is not:** it is not a PRD (components own their PRDs under `docs/design/components/<component>/projects/`), not a roadmap (see [`docs/design/components/PROJECT-PLANNER.md`](design/components/PROJECT-PLANNER.md) for project sequencing; per-feature execution lives in Linear), and not an ADR log (see [`docs/design/DESIGN-REVIEW-LOG.md`](design/DESIGN-REVIEW-LOG.md) for decision history).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Context Management Strategy](#3-context-management-strategy)
4. [Agent Definitions](#4-agent-definitions)
5. [MCP Server Architecture](#5-mcp-server-architecture)
6. [Skills Architecture [PLANNED]](#6-skills-architecture-planned)
7. [Frontend & Channels](#7-frontend--channels)
8. [Multi-Step Orchestration](#8-multi-step-orchestration)
9. [Integration with Evaluation Framework](#9-integration-with-evaluation-framework)
10. [Infrastructure Requirements](#10-infrastructure-requirements)
11. [Resilience, Security & Testing](#11-resilience-security--testing)
12. [Roadmap](#12-roadmap)
13. [Appendices](#13-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the system architecture for KEN-E, a multi-agent AI marketing platform built on Google Cloud. KEN-E spans three complementary execution layers — an **agentic layer** (root agent + narrow per-platform specialists + review loop + config-driven agent factory), a **deterministic layer** (Data Pipeline's typed connectors running platform extractions on fixed schedules), and an **analytical layer** (SAR-E's statistical forecasting + LLM-driven target derivation feeding the Performance page). The three share a common substrate: persistent project plans, an event- and time-driven orchestrator, an artifact system, a KMS-encrypted credential store, a knowledge graph, and a design-system frontend — together the fifteen components listed in §1.6.

This doc serves as an architecture reference: current implementation + planned extensions. Features not yet built are marked `[PLANNED]` throughout; agents marked `[TRANSITIONAL]` exist in the current implementation but will be subsumed by specialist agents or automations when the specialist layer is built (R5). As planned features ship, this document is updated to collapse the distinction.

### 1.2 Critical Design Challenges

The agentic harness must solve three primary challenges:

| Challenge | Scale | Impact |
|-----------|-------|--------|
| **Massive Tool Inventory** | ~400 tools across 20-40 MCP servers | Tool definitions alone could consume 60,000+ tokens |
| **Large Context Requirements** | ~100,000 words of company knowledge | Leaves minimal room for conversation |
| **Multi-Step Autonomous Workflows** | Tasks spanning days/weeks | Requires persistent state and scheduled execution |

### 1.3 Agentic Harness Overview

The design implements a **Hierarchical Agent Architecture with Dynamic Context Loading**. A KEN-E root agent interprets user intent and routes by LLM reasoning over specialist descriptions to a **narrow per-platform specialist** — Google Analytics (R1), then Google Ads / Meta Ads / Mailchimp (R5). Every specialist delegation runs inside a Generator–Critic **review loop** that enforces acceptance criteria before the root relays the result. Specialists are assembled at deploy time by a **config-driven agent factory** that reads Firestore `agent_configs/*` + `mcp_servers/*`, with per-account overlays at `accounts/{account_id}/agent_configs/*`. Each specialist carries a **fixed curated tool roster of ≤30 tools** (MCP toolsets, SDK function tools, built-in Gemini code execution) — no per-turn filtering.

For the canonical architecture, agent tree, dispatch pattern, tool-assignment model, specialist roadmap, and review-loop design, see [`docs/design/components/agentic-harness/README.md`](design/components/agentic-harness/README.md).

### 1.4 Key Design Decisions

| Decision |
|----------|
| **Narrow per-platform specialists** — one specialist per platform (Google Analytics in R1; Google Ads, Meta Ads, Mailchimp in R5). No broad Analytics/Content/Execution/Automation rollups. |
| **Curated ≤30-tool roster per specialist** — fixed at construction; no per-turn `tool_filter`. The 30-tool cap is the scope discipline. |
| **Description-based routing** — root agent picks a specialist by LLM reasoning over each specialist's description (from `agent_configs/{id}.description`); ToolRegistry is a build-time catalog, not a runtime router. |
| **Review loop on every delegation** — Generator–Critic pattern via ADK `LoopAgent`; reviewer evaluates against acceptance criteria before the root relays output. |
| **Config-driven agent factory** — Firestore `agent_configs/*` + `mcp_servers/*` assembled at deploy time via `agent_factory.build_hierarchy()`. Per-account overlay at `accounts/{account_id}/agent_configs/*`. |
| **Per-turn dispatch agent** — Successor to the deploy-time factory above. Deployed root carries no specialist-dispatch tool; specialists are resolved per turn from Firestore via `specialist_runtime` (TTL + content-hash cache, per-key striped locking) and attached to `root.sub_agents` per turn by `sub_agent_attacher.attach_specialists_before_agent_callback`. The root LLM picks a specialist by name from the rendered "Available Specialists" prompt block and uses ADK's native `transfer_to_agent` to dispatch — specialist events (with `usage_metadata`) propagate through the outer Runner's event stream natively, satisfying the Chat + Billing parity contracts without a custom side channel. Admin agent edits (instruction / model / temperature / max_output_tokens / tools / new specialists) propagate to the next chat turn without redeploy — restores Sprint 6 Decision B's intent. Tracked as [AH-PRD-09](design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) (P1–P2 + the AH-75 transfer_to_agent refactor shipped in R1; **[PLANNED] Phase 3** `McpToolsetPool` + hybrid MCP `McpServerKind` enum tracked under AH-62; **[PLANNED] Phase 4 (R2)** Zapier deferred alongside Integrations). See [`docs/design/per-turn-dispatch-rfc.md`](design/per-turn-dispatch-rfc.md) for the original design and [DESIGN-REVIEW-LOG Review 35](design/DESIGN-REVIEW-LOG.md) for the AH-75 dispatch-surface decision. |
| **ADK native compaction** — `EventsCompactionConfig` with `gemini-2.5-flash` summarizer. |
| **`McpToolset` for MCP connections** — ADK handles lazy loading, connection pooling, per-user auth natively. |
| **SDK function tools for some platforms** — Meta Ads + Mailchimp use SDK directly (each specialist owns its own signatures; a shared SDK is just a shared Python dependency). |
| **ADK Skills for expertise delivery** — predefined skills shipped with product, custom skills created by users via UI. |
| **Vega-Lite artifacts for data visualization** — specialists produce Vega-Lite chart specs via `create_visualization()` tool; `ChatResponse` extended with `artifacts` field. |
| **Gemini code execution for numerical analysis** — Google Analytics Specialist uses Gemini's built-in code execution for reliable calculations (percentages, trends, averages). Google-managed sandbox — no infrastructure. |
| **Deterministic Data Pipeline for repeatable extractions** — a sibling `kene-data-pipeline-{env}` Cloud Run service runs well-defined platform extractions (GA, Google Ads, Meta Ads, Mailchimp) via typed connectors outside the agent path. `assignee_type="data_pipeline"` makes it a first-class `PlanTask` assignee alongside `agent` and `human`. Per-account caching + per-connector rate limits. |
| **Integrations-owned credentials** — third-party OAuth tokens live in a KMS-encrypted Firestore substrate; consumers fetch per-invocation via `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}`. Supersedes the legacy per-specialist session-state pattern. Generic OAuth flow driven by `PlatformDefinition` docs — adding a platform adds a doc, not a code branch. |
| **Opt-in analytical layer (SAR-E + Performance)** — statistical forecasting, IRF scenario propagation, and LLM-driven per-KPI-per-week targets activate per-account only after the setup wizard completes. Pre-wizard, SAR-E endpoints return empty-shape responses and the Performance page hides its analytical tabs. |
| **"Statistical association only"** — SAR-E outputs never claim causation. Enforced in the `performance_forecasting` specialist's system prompt, response schema, and a `make lint` CI gate that greps for banned phrases (`caused`, `because`, `due to`, …) in `sar_e_*` files. |

For full decision rationale, see [`docs/design/DESIGN-REVIEW-LOG.md`](design/DESIGN-REVIEW-LOG.md) — the canonical in-repo decision log. For execution plans, see [AH-PRD-01 Review Loop](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md), [AH-PRD-02 Agent Factory](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md), [AH-PRD-03 GA Specialist](design/components/agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md).

### 1.5 Expected Outcomes

| Metric | Target |
|--------|--------|
| Initial context consumption | <20% of available context |
| Tool discovery latency | <500ms |
| Task completion rate | >95% |
| Agent response (simple) | ~7-13s (measured) |

### 1.6 Component Landscape

KEN-E is built as fifteen discrete components, each with its own README and set of project PRDs under `docs/design/components/`. The component split lets independent dev teams ship in parallel and keeps the surface area each team holds in context small. Not every component is agentic — Data Pipeline is deterministic, SAR-E is a statistical + LLM-specialist hybrid, Integrations is OAuth plumbing, Performance is a frontend — and the split calls that out explicitly.

| Component | Scope | Primary component doc |
|-----------|-------|----------------------|
| **Agentic Harness** | Root agent, narrow per-platform specialists, review loop, config-driven agent factory, tool-assignment model, MCP integration | [`components/agentic-harness/README.md`](design/components/agentic-harness/README.md) |
| **Knowledge Graph** | Neo4j schema, provenance spine (`Session` / `Observation` / `ResearchRun`), orchestrator read tools, session-end learning loop | [`components/knowledge-graph/README.md`](design/components/knowledge-graph/README.md) |
| **Project Tasks** | `ProjectPlan` / `PlanTask` data model, `TaskOrchestrator`, event-driven + time-based triggers, planning specialist, calendar UI, multi-category activities, campaigns | [`components/project-tasks/README.md`](design/components/project-tasks/README.md) |
| **Automations** | `PlanRun` execution records, recurring scheduler, artifact system, test/dry-run mode, Automations UI (list + details) | [`components/automations/README.md`](design/components/automations/README.md) |
| **Dashboards** | `ProjectPlan` with `type="dashboard"` + canvas placements; server-side artifact resolver; four widget renderers (text / Vega-Lite / table / file); Performance-page Dashboards tab | [`components/dashboards/README.md`](design/components/dashboards/README.md) |
| **Data Pipeline** | Deterministic (non-agentic) platform-API extraction — typed connectors (GA, Google Ads, Meta Ads, Mailchimp), `DataPipelineJob` / `DataPipelineRun`, per-account caching, sibling `kene-data-pipeline-{env}` Cloud Run service, `assignee_type="data_pipeline"` task-orchestrator branch | [`components/data-pipeline/README.md`](design/components/data-pipeline/README.md) |
| **Integrations** | Third-party OAuth credential substrate — `PlatformDefinition`-driven OAuth flows, KMS-encrypted token store, per-account connection sharing, re-auth lifecycle, `/settings/integrations` UI. Every consumer (Data Pipeline, Agent Factory, KG) reads credentials via one internal API. | [`components/integrations/README.md`](design/components/integrations/README.md) |
| **SAR-E** | Analytical backend for marketing measurement — weekly `EffectivenessKPI` time series, VAR baseline forecasts, IRF scenario propagation, LLM-driven per-KPI-per-week `Target` derivation, analytical query layer. Opt-in per account; "statistical association only" methodology invariant. | [`components/sar-e/README.md`](design/components/sar-e/README.md) |
| **Performance** | `/performance` 6-tab page (Analysis / **Dashboards** / Simulations / Targets / Diagnostics / Configuration) + 4-step setup wizard + composite BFF endpoints. Renders SAR-E outputs (Analysis / Simulations / Targets / Diagnostics) plus the Dashboards tab (owned and filled in by the Dashboards component). Does no statistics itself. | [`components/performance/README.md`](design/components/performance/README.md) |
| **Skills** | User-authored + predefined skill packs, sandbox code execution, skill attachment to custom specialists, Skills authoring UI | [`components/skills/README.md`](design/components/skills/README.md) |
| **Chat** | `/chat` page, session history sidebar (search + category filter + 3-state status dots + infinite scroll), session status view (title / summary / tokens / context / activity / Delete / Export), per-user categories, todo lists in `session.state["todo_lists"]`, artifact provenance wrapper, Firestore `chat_sessions` side-table mirroring ADK sessions for pagination / search / listing. Cost display, manual Compact-now, and the "Permissions Approved" / "Loaded Tools" figma cards are scoped out of v1. | [`components/chat/README.md`](design/components/chat/README.md) |
| **UI** | Soft Maximalism design system, global shell (`LayoutC` / `LayoutSettings` / `Sidebar` / `TopNav` + `bannerSlot` outlet + super-admin Sidebar section + global ErrorBoundary / Toaster / NotFound + accessibility baseline + responsive breakpoints at 1200 / 768), and the page shell + styling for first-party React pages (auth, settings, organization-selection, workflows, calendar, knowledge, extensions). The `/chat` page is owned by the **Chat** component; the `/performance` page is owned by the **Performance** component. Both mount inside `LayoutC` but are not UI-component deliverables. | [`components/ui/README.md`](design/components/ui/README.md) |
| **Data Management** | Shape B Firestore convention (`accounts/{account_id}/…`), migration tooling, deletion sweep rewrite, composite-index registry, approval-workflow + audit schema | [`components/data-management/README.md`](design/components/data-management/README.md) |
| **Billing** | Stripe-backed subscriptions, 41-stop pricing tier table, internal token meter (per account → rolled up to org), monthly enforcement window, org-status state machine (`active` / `approaching_limit` / `inactive_overage` / `inactive_past_due` / `inactive_canceled`), Subscription tab + inactive banner + chat-disabled state, Stripe webhook idempotency journal, manual override, sales handoff. | [`components/billing/README.md`](design/components/billing/README.md) |
| **Feature Flags** | Targeted-rollout infrastructure — per-entity percentage bucketing, kill switches, admin UI, backend + frontend SDKs | [`components/feature-flags/README.md`](design/components/feature-flags/README.md) |

Each subsequent section either **describes a cross-cutting concern** (§3 Context, §9 Evaluation, §10 Infrastructure, §11 Resilience / Security) or **summarizes a component's architecture** (§4 Agent Definitions → Agentic Harness, §5 MCP → Agentic Harness, §6 Skills, §7 Frontend & Channels → UI + Performance, §8 Multi-Step Orchestration → Project Tasks + Automations + Data Pipeline + KG session-end + SAR-E analytical layer, §11.2 Credential Lifecycle → Integrations). Detailed PRDs live in the component dirs; this doc gives the cross-component story.

For project sequencing across components, see [`components/PROJECT-PLANNER.md`](design/components/PROJECT-PLANNER.md).

### 1.7 Sequencing principles

Four principles guide how we slice and order work across releases. They predate the current planner and continue to apply:

1. **Each release is production-deployable.** Small scope, high reliability, well-tested. Avoid "big bang" releases that depend on multiple components landing simultaneously.
2. **Dependencies drive ordering.** The `blocked_by` column in PROJECT-PLANNER is the authoritative graph; release themes follow what's actually unblocked, not what's marketing-friendly to ship together.
3. **Incremental complexity.** Single-step review loops before multi-step workflows. Predefined skills before custom skills. Narrow specialists before broad rollups. The simplest version that proves the pattern ships first; refinements ride later releases.
4. **Stabilization between releases.** Each customer-visible release is followed by a stabilization window (production hardening, bug fixes, monitoring) before the next release begins.

---

## 2. Architecture Overview

Client (Web UI; Slack and Voice planned) → FastAPI on Cloud Run (Firebase Auth, session management, platform credential injection) → Vertex AI Agent Engine (KEN-E root agent, narrow specialists, review loops). Persistent state lives in Firestore (config + session state) and Neo4j (knowledge graph). Tool access flows through `McpToolset` instances and SDK function tools, with Gemini code execution as a built-in capability on selected specialists.

For the canonical architecture diagram, key abstractions, data flow, API contracts, and per-turn dispatch mechanics, see [`docs/design/components/agentic-harness/README.md`](design/components/agentic-harness/README.md) §2. For the review loop that wraps every specialist delegation, see [`AH-PRD-01`](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md). For the config-driven agent factory that assembles the hierarchy, see [`AH-PRD-02`](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md). For the MCP integration layer, see [`mcp-architecture.md`](design/components/agentic-harness/mcp-architecture.md). For channel architecture, see [`api-gateway-multi-channel.md`](design/components/backlog/api-gateway-multi-channel.md) (in backlog).

### 2.1 Agent Type Selection (Google ADK)

KEN-E uses ADK's standard agent types. Root and all specialists are `LlmAgent` instances — LLM-backed, tool-calling agents with InstructionProvider closures reading org context from session state. Review pipelines use ADK's `LoopAgent` (Generator–Critic). Future multi-step workflows (R3) use `ParallelAgent` + `SequentialAgent` composition per the multi-step workflow pattern documented in `review-loop-implementation-plan.md`.

The [Strategy Supervisor](../app/adk/agents/create_strategy_docs_supervisor.py) is a multi-agent (non-LlmAgent) subsystem kept as a separate entry point — not dispatched from the root. Its replacement by knowledge-graph integration is tracked in [KG-PRD-05](design/components/knowledge-graph/README.md).

For the current and planned specialist roster, see [agentic-harness README §2.6 Specialist roadmap](design/components/agentic-harness/README.md#26-specialist-roadmap).

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

OPTIMIZED APPROACH (session-start executive summary + agent-driven KB reads + narrow specialist rosters):
  Session-start executive summary          ~   5,000 tokens  ( 2.5%)
  Agent-driven KB reads (when invoked)     ~   0 upfront, up to 10k per tool call
  Specialist tool roster (≤30 tools)       ~   5,000 tokens  ( 2.5%)  (per specialist, not all at root)
  System prompts & instructions            ~   5,000 tokens  ( 2.5%)
  TOTAL BEFORE CONVERSATION (at root)      ~  10,000 tokens  ( 5.0%)
  Available for conversation               ~ 190,000 tokens  (95.0%)
```

### 3.2 Knowledge Base Reads

Context flows into agent turns at two moments: a **session-start executive summary** (unchanged from the earlier HCL design) and **agent-driven knowledge-base reads** triggered per-turn by the orchestrator when the user's question requires more than the executive summary covers.

**Session start:** `HierarchicalContextManager` (`app/adk/agents/utils/context_loader.py`) loads a ~5,000-token executive summary from Neo4j (company overview, mission, products, ICPs, competitors, active campaigns, current focus, key KPIs) into session state as `organization_context`. The `InstructionProvider` (§3.4) injects it into every LLM turn.

**Per-turn reads:** Four complementary read tools owned by the Knowledge Graph component (KG-PRD-03). The orchestrator picks one per user question:

| Tool | Retrieval shape | Good for |
|------|-----------------|----------|
| `load_context_section(section)` | Bulk structured listing of one of 5 fixed domains (products, icps, competitors, strategies, brand) | "Who are our competitors?" / "What do we sell?" |
| `load_document(entity_type, entity_id)` | Detail drill-down on one entity | "Tell me more about ProductCategory X" |
| `search_kb(query, node_types?, k=10)` | Semantic vector similarity over the 768-dim `kb_vector_index` | "Anything about usage-based pricing?" |
| `list_observations(subject?, valid_only=true)` | Long-tail conversational facts captured by the learning loop | "What did we learn about pricing last time?" |

All four are read-only, account-scoped via `tool_context.state["account_id"]` (never by LLM argument), and wrapped with Weave tracing. Token budgets: `load_context_section` caps at ~10k tokens; `load_document` at ~8k tokens; over-budget truncation drops lowest-priority entities first.

> **Implementation:** See [KG-PRD-03](design/components/knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md) for the Cypher per section, the `:KGNode` label model, the vector-index integration, and the account-scoping rules. Realizes the Context Management decision (see [Review 4 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-4-context-loading--keyword-detection--agent-driven-loading)) — keyword detection (`SECTION_KEYWORDS`, `should_load_section`) is removed when KG-PRD-03 ships.

### 3.3 Learning Loop

The knowledge base the orchestrator reads against is **living**, not write-once-at-account-creation. Two additions in the Knowledge Graph component close the loop:

- **Provenance spine** (KG-PRD-02) — `Session`, `Observation`, and `ResearchRun` nodes. Every write through `GraphSyncService` auto-stamps `source_session_id` or `source_research_run_id` and writes provenance edges (`:OBSERVED_IN`, `:UPDATED_BY`, `:ESTABLISHED_BY`). Bi-temporal `valid_from` / `valid_to` ensures retired facts are soft-deleted rather than removed — history is never lost.
- **Session-end automation** (KG-PRD-04) — a daily Cloud Scheduler job sweeps idle sessions and dispatches a reviewer agent that reads the transcript + KB and proposes new `Observation` nodes, updates, and relationships. An applier agent routes each proposed change: additive changes auto-apply; destructive or cross-session changes halt for human-in-the-loop review in the Automations Outputs tab.

The effect: facts surfaced in conversation ("the CMO is pivoting to usage-based pricing") become retrievable `Observation` nodes on the next session, linked back to the conversation that produced them.

> **Implementation:** See the [Knowledge Graph component README](design/components/knowledge-graph/README.md) for the six-PRD rollout — schema foundation (KG-PRD-01), provenance spine (KG-PRD-02), read tools (KG-PRD-03), session-end automation (KG-PRD-04), research-on-creation refactor (KG-PRD-05), and integration testing & polish (KG-PRD-06).

### 3.4 Context-Aware Agent Instructions

The KEN-E root agent uses ADK's `InstructionProvider` pattern: a closure that's invoked on every LLM turn, reads `organization_context` from session state (populated once at session creation), and prepends it to the agent's base instruction. No DB call per turn. Implementation lives in `app/adk/agents/ken_e_agent.py`.

### 3.5 Session Compaction (ADK Native)

Long-running sessions are automatically compacted using ADK's `EventsCompactionConfig`, configured in `app/adk/deploy_ken_e.py`. A `gemini-2.5-flash` summarizer runs every 5 user invocations or whenever the session exceeds 50K tokens, with one invocation of overlap for continuity and the last 10 raw events kept un-compacted. ADK handles summarization, retention, and token budgeting natively — KEN-E owns only the config values. See [Review 24 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-24-backfill--decision-18-session-compaction--adk-native).

### 3.6 Session State Management

ADK session state carries per-session data that the API, agents, and security hooks read and write at runtime. The API layer (`api/src/kene_api/routers/chat.py`) initialises state at session creation; agents and hooks may update it mid-session.

#### 3.6.1 Current Session State Keys

| Key | Purpose | Set By | Read By |
|-----|---------|--------|---------|
| `user_id` | Authenticated user identifier | API at session creation | Security hooks, tracking callbacks |
| `account_id` | Selected account identifier | API at session creation | Dispatch handlers |
| `accessible_accounts` | Accounts the user can access | API at session creation | — |
| `organization_context` | Org + brand context text from Neo4j | API at session creation (cached in Redis, 15-min TTL) | InstructionProvider (per-turn), dispatch handlers |
| `ga_credentials` *(being retired)* | Google Analytics OAuth tokens (access, refresh, tenant, properties, expiry) | API from Firebase Auth (cached in Redis, 10-min TTL) | GA dispatch handler, security hooks. **Retired by [IN-PRD-06](design/components/integrations/projects/IN-PRD-06-integration-testing-cleanup.md)** — Agent Factory's `_make_header_provider` body is swapped to fetch from the Integrations internal API per tool invocation; session-state writes for `ga_credentials` / `google_ads_credentials` / etc. are removed. See §11.2. |
| `campaign_context` | Campaign context text (when loaded) | Context loader | Dispatch handlers |
| `connected_accounts` | User's connected platform account types | API at session creation | Tool discovery filtering |
| `uploaded_strategy_documents` | Strategy input documents loaded mid-session | Strategy orchestrator | Strategy orchestrator |
| `_tool_start_time` | Tool execution start timestamp | `adk_before_tool_callback` | `adk_after_tool_callback` |
| `_requires_reauth` | Flag: user must re-authenticate | Security hooks (permission denied) | API response handler (then cleared) |
| `_reauth_service` | Service name requiring re-auth | Security hooks | API response handler (then cleared) |

#### 3.6.2 [PLANNED] Target Session State Model

The target architecture generalises credentials to support all integrated platforms:

| Key | Purpose | Set By |
|-----|---------|--------|
| *(model retired)* `platform_credentials.<service>` | Originally planned: per-platform OAuth tokens in session state. **Superseded** by the Integrations component — credentials are **not** stored in session state; consumers fetch per-invocation via `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` (OIDC-authed). See §11.2 and [`components/integrations/README.md`](design/components/integrations/README.md). | — |
| `response_artifacts` | Visualization artifacts (Vega-Lite specs) produced by specialist agents during current invocation | `create_visualization` tool in specialist agents. See [`data-visualization.md`](design/components/agentic-harness/data-visualization.md) §4. |
| `todo_lists` | Multi-step task tracking that survives compaction. Dict-of-dicts keyed by `list_id`, each value matching the `TodoList` Pydantic shape (`title`, `is_current`, `created_at`, `items[]` of `TodoItem(item_id, text, completed, completed_at)`). 20-list × 50-item caps enforced by the tool helpers. Surfaced via `GET /api/v1/chat/conversations/{id}/todos`. See [CH-PRD-05](design/components/chat/projects/CH-PRD-05-todo-lists-and-artifacts.md). | ADK `FunctionTool`s `set_todo_list` / `update_todo_list` registered in `app/adk/tools/registry/config/tools.yaml` under `function_tools:` with `default_global: true`. |
| `{prefix}_draft`, `{prefix}_feedback` | Review-loop intermediate state (per specialist dispatch). Each review pipeline uses a unique `output_key_prefix`. | Specialist + reviewer `LlmAgent` via `output_key`. See [AH-PRD-01](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md). |
| `tool_filter_state` *(retired)* | Previously drove per-turn `tool_filter` predicates — **no longer used**. Specialists now receive a fixed ≤30-tool roster at construction (see [agentic-harness README §2.5](design/components/agentic-harness/README.md#25-tool-assignment--routing-model)). |

#### 3.6.3 What Is Not in Session State

| Item | Where it lives instead |
|------|----------------------|
| Base agent instructions | Firestore config (loaded at deploy time); InstructionProvider merges with `organization_context` from state |
| Token / cost usage metrics | UsageTracker via Weave traces (`app/adk/tracking/usage.py`) |
| Tool registry index | YAML config loaded at deploy time (`app/adk/tools/registry/config/tools.yaml`) |
| Conversation history | ADK event log (managed by EventsCompactionConfig, not stored in state) |

#### 3.6.4 Token Usage Visibility — superseded by CH-PRD-04

**Superseded by the Chat component.** The originally proposed approach (extend `ChatResponse` with a `usage` field) is replaced by Chat's per-turn accumulator + composite endpoint design:

- **Per-turn aggregation** — CH-PRD-01's `SessionTurnAccumulator` extracts tokens from every event via `extract_billable_tokens(event)` (Billing-owned helper at `shared/token_accounting.py`) and writes input / output / reasoning aggregates + `current_context_tokens` + `context_window_max` to the Firestore `chat_sessions` side-table at end-of-turn.
- **Composite read** — CH-PRD-04's `GET /api/v1/chat/conversations/{id}/status-detail` returns metadata + server-derived `context_usage_percent`, `total_tokens`, and `activity_summary` in one round-trip.
- **UI surface** — CH-PRD-04's `TokenUsagePanel.tsx` renders a context-window bar (Healthy / Moderate / Near-limit badge) and a 3-card token grid (Input / Output / Total). **No cost line** — subscription-level pricing is Billing's concern; Chat shows token counts only.

See [Chat component README](design/components/chat/README.md) §2.3 for the canonical contract and [Review 25 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-25-backfill--decision-19-token-usage-visibility-in-ui-proposed) for historical context.

#### 3.6.5 Unified Usage Tracking for Billing — superseded by BL-PRD-02

**Superseded by the Billing component.** [BL-PRD-02](design/components/billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md) owns the org-level token meter end-to-end:

- **Org-scoped meter** — Billing maintains `usage_windows` per `(org_id, billing_period)` rolled up from per-account `accounts/{account_id}/usage_daily/*` increments. Organization is the billing unit; sub-accounts contribute to the org-level total.
- **Single token-extraction helper** — `extract_billable_tokens(event)` at `shared/token_accounting.py` (Billing-owned per BL-PRD-02; Chat consumes via `SessionTurnAccumulator`). Token definition: input + output + reasoning, cached-input excluded. CI parity test enforces both consumers produce identical output.
- **Enforcement path** — every LLM-consuming agent invocation wraps `billing.check_status` (pre-call) + `billing.meter_increment` (post-call); on `BillingInactiveError`, the API maps to HTTP 402.

Tool observability and billing remain separate concerns — `tool_usage_events` (tool-call observability owned by the Agentic Harness) is no longer part of the billing pipeline. See [Billing component README](design/components/billing/README.md) §3 and [Review 26 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-26-backfill--decision-20-unified-usage-tracking-for-billing-superseded-in-part) for historical context.

---

## 4. Agent Definitions

The canonical specs for agent tree, dispatch pattern, agent factory, tool-assignment model, review loop, and specialist roadmap live in the agentic-harness component:

- [**Agent tree, dispatch, key abstractions**](design/components/agentic-harness/README.md#2-architecture) — [`agentic-harness/README.md`](design/components/agentic-harness/README.md) §2
- [**Tool-assignment & routing model**](design/components/agentic-harness/README.md#25-tool-assignment--routing-model) — README §2.5: curated ≤30-tool roster per specialist; description-based routing; ToolRegistry as build-time catalog
- [**Specialist roadmap**](design/components/agentic-harness/README.md#26-specialist-roadmap) — README §2.6: narrow per-platform (GA in R1; Google Ads, Meta Ads, Mailchimp in R5)
- [**Review loop**](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) — AH-PRD-01: Generator–Critic `LoopAgent`, reviewer with `include_contents='none'`, structural rules, cost/latency
- [**Agent factory (deploy-time, shipped)**](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md) — AH-PRD-02: config-driven assembly, multi-tenant overlay, ≤30-tool roster construction
- [**Per-turn dispatch agent (R1, supersedes AH-PRD-02 in the runtime path)**](design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) — AH-PRD-09 + [AH-75](https://linear.app/ken-e/issue/AH-75): deployed root carries no specialist-dispatch tool; specialists are resolved per turn from Firestore via `specialist_runtime` and attached to `root.sub_agents` per turn by `sub_agent_attacher`; the root LLM dispatches via ADK's native `transfer_to_agent`. Admin edits propagate without redeploy. **[PLANNED] Phase 3** `McpToolsetPool` + hybrid MCP `McpServerKind` (`cloud_run` + `zapier`) reusing connections across runtime rebuilds is tracked under AH-62; **[PLANNED] Phase 4 (R2)** Zapier is deferred alongside Integrations. Full design in [`docs/design/per-turn-dispatch-rfc.md`](design/per-turn-dispatch-rfc.md); dispatch-surface decision in [DESIGN-REVIEW-LOG Review 35](design/DESIGN-REVIEW-LOG.md).
- [**GA Specialist (first factory-built specialist)**](design/components/agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) — AH-PRD-03

This section retains only the **tool type taxonomy** — a cross-cutting reference used throughout the doc.

### 4.1 Tool Type Taxonomy

KEN-E agents carry tools from three distinct categories, each with different resolution mechanics and context costs:

| Tool Type | Resolution Mechanism | Context Overhead | Example |
|-----------|---------------------|-----------------|---------|
| **MCP Tools** | Resolved via `McpToolset` at agent construction; the ≤30-tool roster is fixed | ~150 tokens/tool in context | GA MCP `run_report_mt`, HubSpot MCP `get_contacts` |
| **SDK Function Tools** | Python functions wired at agent construction; each specialist owns its own signatures | ~150 tokens/tool in context | `update_meta_campaign_budget()`, `create_visualization()` |
| **Built-in Model Capabilities** | Enabled via `GenerateContentConfig.tools` | Zero — no tool definition sent to context | Gemini code execution (`ToolCodeExecution`) |

All three types count toward the agent's curated tool roster for scope purposes, but built-in capabilities carry zero context overhead and are not counted against the ≤30-tool cap. The Root Agent does not get domain tools or code execution — it routes to specialists. See [agentic-harness README §2.5](design/components/agentic-harness/README.md#25-tool-assignment--routing-model) for the full assignment model.

See [Review 22 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-22-backfill--decisions-7--8-token-budget-strategy--toolregistry-as-build-time-catalog) for the Token Budget Strategy + ToolRegistry rationale.

---

## 5. MCP Server Architecture

MCP integration — ADK internals, platform-by-platform decisions (provider vs self-hosted vs SDK), Firestore config schema, MCPServerManager disposition, infrastructure summary, read-only limitations — lives in [`docs/design/components/agentic-harness/mcp-architecture.md`](design/components/agentic-harness/mcp-architecture.md).

Headline properties (for anyone skimming this doc):

- **One MCP server instance serves all accounts**, scoped by per-user OAuth token in the header. No per-account MCP server instances.
- **`McpToolset` handles connection pooling, lazy-loading, and per-user auth natively.** SSE sessions are pooled by connection params; `get_tools()` is called every LLM turn (canonical tools cached per invocation since ADK v1.26.0).
- **Platform integration is hybrid by design** — provider-hosted MCP (HubSpot), self-hosted MCP (GA, Google Ads reads), SDK function tools (Meta Ads, Mailchimp, Google Ads writes), and Gemini built-in (code execution).
- **MCP server connections are fixed at deploy time.** Tool rosters per specialist are assembled by the factory at deploy time from Firestore `mcp_servers/{server_id}` + `agent_configs/{config_id}` documents — no per-turn filtering.
- **[PLANNED] Hybrid MCP kinds + runtime pooling (AH-PRD-09).** `mcp_servers/{server_id}` gains a `kind` field (`cloud_run` | `zapier`; open enum) and tool rosters resolve at runtime via `specialist_runtime`. A process-wide `McpToolsetPool` reuses connections across per-turn specialist rebuilds with LRU + idle-TTL eviction and `aclose()`-on-eviction. Long-tail integrations route through one Zapier MCP connection per account (`accounts/{account_id}/integrations/zapier`); flagship integrations stay on owned Cloud Run servers. Replaces the "fixed at deploy time" bullet above when AH-PRD-09 Phase 3 ships. Phase 4 (Zapier first-class integration) deferred to R2 alongside Integrations. See [`docs/design/per-turn-dispatch-rfc.md`](design/per-turn-dispatch-rfc.md) §4.2.1, §4.6, §4.8.

---

## 6. Skills Architecture [PLANNED]

**Skills** (ADK Agent Skills specification) package procedural knowledge as self-contained, progressively-disclosed units — they complement *tools* (which execute actions) by providing instructions for HOW to use those tools. KEN-E ships with a bundled set of system-owned predefined skills (one placeholder `example-skill` in v1, ramped up via subsequent content PRDs) and supports user-authored custom skills scoped to an account.

Progressive disclosure keeps token overhead low: L1 metadata (~50–100 tokens) is always available; L2 full `SKILL.md` body loads on activation; L3 resources/scripts load on-demand. Skills attach to specialists at factory build time and are restricted in scope by the specialist's ≤30-tool roster — a skill's `allowed-tools` field can narrow the tools it uses but never grants tools the specialist doesn't already have. Per-attachment version pinning is a v2 enhancement; v1 is latest-wins (editing a skill propagates immediately to attached agents).

The canonical Skills design, data model, sandbox policy, UI, and phased delivery live in the **Skills component**: [`docs/design/components/skills/README.md`](design/components/skills/README.md) and the six project PRDs there ([SK-PRD-00 Sandbox Spike](design/components/skills/projects/SK-PRD-00-skills-experiment.md), [SK-PRD-01 Backend](design/components/skills/projects/SK-PRD-01-skills-backend.md), [SK-PRD-02 Agent integration](design/components/skills/projects/SK-PRD-02-agent-integration.md), [SK-PRD-03 Authoring UI](design/components/skills/projects/SK-PRD-03-authoring-ui.md), [SK-PRD-04 Agent-builder controls](design/components/skills/projects/SK-PRD-04-agent-builder-controls.md), [SK-PRD-05 Predefined Skill Foundation](design/components/skills/projects/SK-PRD-05-predefined-skill-foundation.md)).

See [Review 7 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-7-transitional-agent-annotations-meta-ads-shared-access-skills-architecture) for rationale.

---

## 7. Frontend & Channels

### 7.1 Web UI

The primary user experience is a React SPA at `app.ken-e.ai`. The entire frontend is built on a shared design system and global shell delivered by the **UI component**:

- **Soft Maximalism design system** (UI-PRD-01) — `theme.css` tokens, Tailwind config, `ThemeProvider`, `BackgroundEffects`, re-skinned shadcn primitives, shell layouts (`LayoutC` with `bannerSlot` outlet, `LayoutSettings` with registry-driven sub-nav), and global chrome (`Sidebar` with super-admin section, `TopNav`, `AccountSwitcher`, `NotificationBell`, `ProfileMenu`). UI-PRD-01 also lands the global `ErrorBoundary`, `Toaster`, `NotFoundPage` + catch-all route, accessibility baseline (axe-CI on shell components, AA contrast, focus rings, semantic landmarks), and responsive breakpoints (Mobile <768px, Tablet 768–1199px, Desktop ≥1200px). The Chat-component-owned `SessionsSidebar` mounts inside `LayoutC` but is not a UI-component deliverable.
- **Core pages** (UI-PRD-02) — auth/invitation (route-based gate via `<Navigate to="/sign-in">`), organization/account/user settings, `/create-organization`, `/settings` → `/settings/organization` redirect, registry-pattern `LayoutSettings` sub-nav (seeded with Organization / Account / User; IN-PRD-03 plugs in Integrations, BL-PRD-04 plugs in Subscription).
- **Workflows tab container** (UI-PRD-03, Release 1) — the `WorkflowsLayout` tab host for Agents (data-wired by [AH-PRD-02](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md)), Automations (wired by [A-PRD-05](design/components/automations/README.md) / A-PRD-06), and Skills (wired by [SK-PRD-03](design/components/skills/README.md)). Three tabs total — data pipelines are not a tab; they are a `PlanTask.assignee_type` value created from inside the shared DAG editor (see §8.4).
- **Feature pages** — Calendar (UI-PRD-04, data-wired by [PR-PRD-03](design/components/project-tasks/projects/PR-PRD-03-calendar-page-frontend.md)), Knowledge/Strategy (UI-PRD-05), Extensions (UI-PRD-06), Organization Selection (UI-PRD-08).
- **Performance page** — `/performance` with **six** tabs (Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration) and a four-step setup wizard at `/performance/setup`. Owned by the **Performance component** ([`components/performance/README.md`](design/components/performance/README.md), PE-PRDs 01–08) as a frontend + thin BFF layer. The analytical data the SAR-E-backed tabs render comes from the **SAR-E component** (weekly KPI time series, VAR baselines, IRF scenarios, LLM-derived targets — see §8.5). The **Dashboards** tab is owned and filled in by the [Dashboards component](design/components/dashboards/README.md) (DB-PRD-02 list / DB-PRD-03 details) and is not gated by SAR-E enablement. UI-PRD-07 (the original presentation-only redesign) is **retired and subsumed by PE-PRD-01**.

The design-system foundation (UI-PRD-01) lands first in Release 1 so every subsequent component's frontend slots into the same shell. Full design system, component inventory, and page-by-page breakdown live in [`components/ui/README.md`](design/components/ui/README.md).

### 7.2 Channel-Agnostic API

The chat API is channel-agnostic from the start — any new channel needs only an auth adapter, input normalizer, and output formatter. The Agent Engine call path is unchanged regardless of source. Full API architecture, session management, and planned-channel integration approaches live in [`docs/design/components/backlog/api-gateway-multi-channel.md`](design/components/backlog/api-gateway-multi-channel.md) (in backlog).

### 7.3 [PLANNED] Additional Channels

| Channel | Framework | Deployment | Timeline |
|---------|-----------|------------|----------|
| **Web** | React SPA (UI-PRD-01+) | Firebase Hosting | Release 1 |
| **Slack** | Bolt SDK | Separate Cloud Run | Release 5 |
| **Voice** | Pipecat + Meeting BaaS (Recall.ai or equivalent) | Dedicated service | Release 6 |

See [Review 23 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-23-backfill--decisions-14--15--16-channel-architecture-api-gateway-slack-voice) for the channel architecture rationale (Channel-Agnostic API, Slack, Voice).

---

## 8. Multi-Step Orchestration

KEN-E handles work that spans more than one LLM turn or more than one session through several complementary mechanisms — in-session workflow agents, persistent project-task orchestration, automations, deterministic data-pipeline extraction, and a separate analytical-computation layer — all documented at the component level. This section frames the architecture at a high level and points at the component docs for details.

### 8.1 In-Session Multi-Step Workflows [PLANNED, R3]


For complex requests that can be decomposed into parallel + sequential steps within a single conversation (e.g., "Increase budgets for Meta Ads campaigns with the most engaged website visitors" → parallel data-gathering across Google Analytics + Meta Ads → synthesizer → user approval → execution step), KEN-E composes review pipelines (AH-PRD-01) into larger workflows using ADK workflow agents.

The **multi-step pattern** — `ParallelAgent` + pipeline-wrapped `LoopAgent`s + synthesizer with `include_contents='none'` — plus the `build_review_pipeline()` / `build_workflow_pipeline()` factory code, three validated ADK pitfalls (ADK 1.26.0), and LLM cost/latency tables all live in [`docs/design/review-loop-implementation-plan.md`](design/review-loop-implementation-plan.md) §3.3 (architecture) and §Phase 4 (4-story delivery plan). The single-step review-loop building block is tracked as [AH-PRD-01](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md); the multi-step composition (`build_workflow_pipeline`, `WorkflowStep`, `execute_workflow` root tool, approval-via-conversation-turns continuation) is tracked as [AH-PRD-05](design/components/agentic-harness/projects/AH-PRD-05-multi-step-workflows.md), targeting Release 3.

### 8.2 Project Plans & Task Orchestration

For work that spans **more than one session** — plans persisted across conversations, dispatched to agents or humans, fired at scheduled datetimes — KEN-E uses the **project-tasks** component. This is the persistent orchestration layer above the stateless per-turn agent runtime.

**Data model (high level)**

- **`ProjectPlan`** — template of tasks + DAG + acceptance criteria, persisted at `accounts/{account_id}/project_plans/{plan_id}`, versioned (every mutation snapshots a new version) and audited.
- **`PlanTask`** — DAG node with `depends_on`, `due_date`, `launch_time_utc` (HH:mm UTC), status, and a `launched_at` idempotency guard.
- **`is_system: bool`** flag on `ProjectPlan` — marks platform-owned seeded templates (hidden from user-facing lists, read-only in the UI). Consumed by the Automations component and by the Knowledge Graph session-end automation (§8.3).

**Two triggers converge through `TaskOrchestrator`**

```
Event-driven (user or agent updates a task):
  PATCH task → TaskOrchestrator.on_task_status_change
    → resolve newly-unblocked tasks
    → dispatch agent tasks via AgentEngineClient
    → notify human owners via existing notification system
    → revision loop if task returned for rework (capped at 5 iterations)

Time-based (task's scheduled datetime arrives):
  Cloud Scheduler cron (per minute)
    → POST /api/v1/internal/scheduler/launch-due-tasks (OIDC-authed)
    → collection-group query: status=Approved, launched_at IS NULL,
      due_date + launch_time_utc <= now
    → set launched_at (idempotency guard), then
    → TaskOrchestrator.on_task_due → same orchestration machinery
```

Both triggers hand off to the same `TaskOrchestrator` service — a single convergence point with three entry methods (`activate_plan`, `on_task_status_change`, `on_task_due`). The orchestrator reuses `AgentEngineClient` (the same client `chat.py` uses) for agent dispatch, so agent tasks benefit from the full harness — factory-assembled specialists, review loop, Weave tracing — without separate infrastructure.

**Planning specialist (factory-built)**

The `project_planning` specialist is assembled by the agent factory (AH-PRD-02) from a Firestore `agent_configs/project_planning` config doc + three Python tool functions (`save_project_plan`, `update_task_status`, `get_project_plan`); a fourth tool (`resolve_or_create_campaign`) and a multi-category instruction update land in PR-PRD-09 once the multi-category and Campaign contracts ship. No hand-written `LlmAgent` or dispatch handler — the factory generates `dispatch_to_project_planning()` and wires the standard callbacks. When a user asks the root agent for a plan, it dispatches to this specialist; the specialist calls `save_project_plan` which persists via the CRUD API.

**Multi-category activities, Campaigns, orphan tasks**

The base `PlanTask` model is extended (PR-PRD-07) with a `category` discriminator (`task` / `promotion` / `holiday` / `event`) and category-specific sparse fields — promotions carry `promotion_type`, `discount_details`, `end_date`, `region`; holidays carry `holiday_type` and an annual-`recurring` flag; tasks and events use the base shape. `PlanTask` also gains an `owner_email` (the human responsible) distinct from `assignee_name` (the agent / automation / human that *executes*), an `unscheduled` flag for orphan-panel candidates, and task-level recurrence (`recurrence_cron` + `recurrence_timezone` + `recurrence_enabled`) — distinct from plan-level recurrence on automations. Orphan tasks (not attached to any plan) live at `accounts/{account_id}/orphan_tasks/{task_id}` with attach-to-existing-plan, atomic create-plan-and-attach, and detach-from-plan transactions. Two new endpoints — batch-create (`POST .../tasks/batch`) and group-edit (`PATCH .../tasks:group-edit`) — back the Calendar's multi-day Wizard and bulk-edit drawer.

**Campaigns** (PR-PRD-08) are first-class entities at `accounts/{account_id}/campaigns/{campaign_id}` with a four-value `objective` enum (`Problem Awareness` / `Brand Awareness` / `Consideration` / `Conversion`). Four generic-fallback campaigns are seeded per account (one per objective) so every activity can resolve an objective even when no specific campaign is selected. Activities reference campaigns via `campaign_id` (rename from the legacy `campaign` string field, with a one-release alias).

**Frontend**

A calendar page at `/calendar` displays activities with category badges, sparse-field rendering, an Unscheduled Tasks panel for orphans, the Batch Activity Wizard, the Group Edit drawer, an inline campaign-create flow, and full filter coverage. Notifications on task-ready events link back into the right plan/activity.

For the full data model, Pydantic schemas, API contracts, the event-driven orchestrator internals, the Cloud Scheduler Terraform, and the calendar UI, see the [project-tasks component](design/components/project-tasks/README.md) and its nine PRDs (PR-PRD-01 through PR-PRD-09).

### 8.3 Automations & System-Triggered Plans

Three components build directly on §8.2 rather than reinventing the orchestration machinery:

**Automations** ([component](design/components/automations/README.md)) — layers a `PlanRun` (execution record) abstraction on top of `ProjectPlan` (template), adds a recurring scheduler (cron-style "every Monday at 9am UTC"), an artifact system (agents attach files/JSON to task runs; artifacts are retrievable via signed URLs), a test/dry-run mode, and a user-facing Automations UI with list + detail pages. Every automation is a `ProjectPlan` with one or more `PlanRun`s against it. `is_system=true` plans are filtered out of the default list and rendered read-only on the details page. The recurring scheduler also fires an `AUTOMATION_RUN_COMPLETE` notification for `plan.created_by` on every terminal `PlanRun` state — deep-link routes by `plan.type` (dashboard runs deep-link into the Dashboards details page; freeform runs into the Automations details page) so a single producer covers both consumers.

**Dashboards** ([component](design/components/dashboards/README.md)) — runs through A-PRD-02's manual-trigger endpoint with `type="dashboard"` plans; introduces no new orchestrator behavior, only a server-side artifact resolver that maps `(task_id, file_type)` → the latest `PlanRun`'s matching artifact. The canvas refreshes by re-resolving each placement against the latest run.

**Knowledge Graph session-end automation** ([KG-PRD-04](design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md)) — rides entirely on the Automations platform. A seeded `is_system=true` project plan (`kg-session-end-review`, `account_id="_system"`) runs a reviewer agent (reads the chat transcript + KB, emits a `proposal.json` artifact) and an applier agent (routes each proposed change: additive auto-applies, destructive halts for HITL). A daily Cloud Scheduler job sweeps idle sessions and triggers one `PlanRun` per session via the Automations manual-trigger endpoint. Surfaces in the Automations Outputs tab for user review.

**Why not n8n?** The Automations component delivers the feature set KEN-E needs (recurring schedules, multi-step DAGs, HITL, artifacts, dry-run) agent-natively — factory-assembled specialists, review loops, and Weave traces all flow through it unchanged. Running n8n would duplicate this infrastructure and add per-account tenancy + operational burden. Future: an n8n **MCP tool** could expose user-owned external n8n workflows to the agent without KEN-E hosting n8n itself — but that is a future specialist/tool decision, not a replacement for internal orchestration.

### 8.4 Deterministic Platform-API Extraction (Data Pipeline)

Not every third-party platform touch should flow through an agent. For **repeatable, well-defined extractions** — "pull daily GA first-purchase counts at 07:00 UTC," "fetch last week's Meta Ads spend by campaign" — the agent-routed path (Root → specialist → MCP call → code execution) is the wrong shape: non-deterministic, token-expensive, and hard to reason about. For that class of work, KEN-E uses the **Data Pipeline** component.

A `PlanTask` carries a third `assignee_type="data_pipeline"` alongside `agent` and `human`. The task holds a `pipeline_spec` (`{job_id, inputs, output_artifact_name}`); when the `TaskOrchestrator` (§8.2) fires it, the `DataPipelineDispatcher` HTTP-calls the sibling `kene-data-pipeline-{env}` Cloud Run service, which runs the job via a typed connector (Google Analytics, Google Ads, Meta Ads, Mailchimp), writes the result as a `TaskArtifact` (§8.3's artifact system), and reports completion back through an OIDC-authed callback endpoint. Downstream agent tasks read the artifact as upstream context via A-PRD-03's prompt-injection helper. A per-account cache (`sha256(account_id || job_id || canonical_json(inputs) || job.version)`) short-circuits duplicate runs; per-connector rate-limit budgets prevent platform-quota exhaustion.

**Frontend authoring lives inside the shared DAG editor — no standalone Workflows tab.** Data pipelines are created as tasks from the right-side panel that opens when a user clicks "+ Add Task" in the **shared DAG editor** (`frontend/src/components/dag/TaskGraph.tsx`, owned by A-PRD-06 and reused verbatim by DB-PRD-03). The editor surfaces on two pages: `/workflows/automations/{plan_id}` (Automations) and `/performance/dashboards/{plan_id}` (Dashboards). Selecting `assignee_type="data_pipeline"` swaps the agent/human fields for a `PipelineJobPicker` + JSON-Schema-driven inputs form; editor-role users can also expand the side-panel into a `CustomJobAuthoringPanel` to author a brand-new per-account job inline (Basics → Schemas → Connection → Preview → Publish & Use). Calendar's `ProjectEditDrawer` accepts the same assignee type (no code constraint), but the canonical authoring surface is the DAG editor. There are **no `/workflows/data-pipelines` standalone routes** — that scope was retired in favor of the inline-in-side-panel design.

Credentials flow through Integrations, not session state — the Data Pipeline service calls `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` per run (OIDC-authed). See §11.2.

The first production consumer is **SAR-E's weekly KPI ingestion automation** — a seeded `is_system=true` `ProjectPlan` with four daily GA extraction tasks feeding a single glue agent task that aggregates daily rows to weekly KPI series (§8.5).

Full data model (`DataPipelineJob`, `DataPipelineRun`, `PipelineJobSpec`), connector catalog, cache semantics, `test_mode_policy` handling, frontend authoring UI, and the sibling Cloud Run service's footprint live in [`components/data-pipeline/README.md`](design/components/data-pipeline/README.md) and the six DP-PRDs.

### 8.5 Analytical Layer (SAR-E & Performance)

Some of KEN-E's work is **analytical and statistical**, not agentic. Forecasting the next 12 weeks of funnel KPIs, computing vector-auto-regression (VAR) baselines, propagating simulated lifts as impulse-response functions, and deriving per-KPI weekly targets — all of this lives in the **SAR-E component** (Simulation and Recommendations Engine). Statistical code runs synchronously via `statsmodels`; one LLM specialist (`performance_forecasting`, factory-built via AH-PRD-02) handles the reasoning step in target derivation.

Four facts shape the design:

- **SAR-E is the computation home.** Performance renders SAR-E outputs; Data Pipeline feeds SAR-E inputs. SAR-E owns every statistical artifact — KPI series, baselines, targets, scenarios, thresholds, coverage, mapping history. A developer touching numbers (baselines, targets, trendlines, cost rollups) touches this component. SAR-E is also **opt-in per account**: at account creation the forecasting stack is disabled; it activates only after the user connects at least one integration and completes the Performance component's four-step setup wizard (picks four Effectiveness KPIs, maps them to the four funnel Objectives). Until then, every SAR-E analytical endpoint returns an empty-shape response and the Performance page hides its analytical tabs.
- **Weekly is the only internal granularity.** Daily rows are produced by Data Pipeline (§8.4), aggregated to weekly at ingestion time, and the daily source rows are not persisted in SAR-E. VAR training, Target derivation, and trendline queries all operate on weekly series.
- **Reasoning belongs to an ADK specialist; math belongs to statsmodels.** VAR training and IRF propagation are closed-form numerical code (statsmodels + numpy) invoked synchronously at request time or on retrain. Target derivation is a Gemini 2.0 Pro specialist (`performance_forecasting`, factory-built via AH-PRD-02) call that reasons over baseline + calendar + historical pulses. Two independent subsystems; neither replaces the other.
- **"Statistical association only" is an invariant.** The target-derivation specialist's system prompt, response schema, and a `make lint` CI gate forbid causal language (`caused`, `because`, `due to`, …) in SAR-E outputs. Every `Target` carries a `methodology_note` phrasing the relationship as association.

SAR-E's inputs come from Data Pipeline via a system-triggered weekly automation (§8.3 + §8.4); its outputs are rendered by the **Performance** component at `/performance` (§7.1). Performance is a frontend + thin BFF layer — it does no statistics — which keeps computation testable and the render path cacheable.

Full design, VAR model details, IRF propagation, target derivation specialist, methodology gate, and the analytical query layer live in [`components/sar-e/README.md`](design/components/sar-e/README.md) + the seven SE-PRDs. The Performance page structure (tabs, setup wizard, BFF composition) lives in [`components/performance/README.md`](design/components/performance/README.md) + the eight PE-PRDs.

---

## 9. Integration with Evaluation Framework


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


A feedback collection system will enable human evaluation alignment:
- Queue feedback requests for users after agent outputs
- Store ratings (1-5) and factor-level ratings in Firestore
- Trigger alignment analysis when sufficient feedback is collected

### 9.5 [PLANNED] A/B Testing Support


The harness will support A/B testing of agent configurations:
- Consistent hash-based variant assignment per account
- Firestore-stored variant configurations
- Trace metadata includes `experiment_id` and `variant_name` for evaluation

---

## 10. Infrastructure Requirements

### 10.1 Data Layer

KEN-E uses five persistent stores with a standardized layout across all components:

- **Firestore (Shape B)** — per-account configuration, session state, project plans, plan runs, task artifacts metadata, skills, observations metadata, chat-session metadata, and audit logs. Every account-scoped collection lives at `accounts/{account_id}/{resource}/…` per the Shape B convention owned by the **Data Management component**. Account-scoped subcollections include: `project_plans` / `plan_runs` (Project Tasks + Automations); `members` (DM-PRD-07 — explicit account-level role grants only, overlay handles the common case); `platform_connections/{connection_id}/tokens/*` (Integrations, KMS-encrypted — see Cloud KMS below); `data_pipeline_jobs` + `data_pipeline_runs` (Data Pipeline overlay catalog + execution records); `kpi_time_series` / `baselines` / `irf_coefficients` / `targets` / `funnel_mapping` / `channel_coverage` / `thresholds` / `effectiveness_kpis` / `sar_e_config` (SAR-E); `chat_sessions` + nested `chat_sessions/{session_id}/artifacts/*` (Chat — CH-PRD-01 side-table mirroring ADK sessions, plus CH-PRD-05 artifact metadata index); five audit subcollections (`project_plan_audit`, `integrations_audit`, `sar_e_audit`, `data_pipeline_audit`, `account_member_audit`). Org-scoped subcollections include `members` (DM-PRD-07 — every org member has a row), `billing_audit` (Billing — org-scoped audits), and `account_member_audit` (DM-PRD-07 — org-level member-CRUD events). User-scoped subcollections (Shape B-compatible, predate the migration) include `notification_status`, `preferences`, `notifications`, `security`, and `chat_categories` (CH-PRD-03). Global (non-account-scoped) collections include `platform_definitions/*` (Integrations OAuth metadata), `data_pipeline_jobs/*` (platform-global job catalog), `feature_flags/*` + `feature_flag_audit/*` (Feature Flags), and the `agent_configs/*` + `mcp_servers/*` factory inputs. Account deletion is covered by `firestore.recursive_delete(accounts/{account_id})` so new subcollections automatically inherit clean-deletion semantics; user deletion is covered by `delete_user_data(user_id)` (DM-PRD-05) which sweeps cross-account/org `members` rows, fires Integrations' `on_user_removed` hook per affected account, and recursively deletes the user doc + registered user-scoped subcollections.
- **Neo4j (AuraDB)** — the account knowledge graph. Shared `:KGNode` label on all 29 node types enables one account-scoped lookup index and one 768-dim cosine vector index (`kb_vector_index`) across the whole KB. Migration runner + `:Migration` ledger bootstrap constraints and indexes on API startup. See [Knowledge Graph component](design/components/knowledge-graph/README.md).
- **Cloud KMS** — env-specific symmetric key that wraps OAuth token payloads before they're written to Firestore. The key never leaves GCP; a stolen Firestore export yields no usable credentials. Owned by the **Integrations component** (IN-PRD-01). See §11.2.
- **Redis (Memorystore)** — session cache, short-TTL credential cache (for the Integrations internal endpoint), rate-limiter counters, and Data Pipeline per-account rate-limit windows.
- **GCS buckets** — `kene-skills-{env}` for `SKILL.md` content + resources (CMEK, 30-day `-trash` sibling); `kene-task-artifacts-{env}` for automation + Data Pipeline task artifacts (30-day lifecycle, 100MB cap per artifact).

The Shape B layout, migration tooling, deletion-sweep rewrite (account + user), two-tier role model with overlay, members CRUD API, and generalized audit substrate live in [`components/data-management/README.md`](design/components/data-management/README.md) and the eight DM-PRDs. DM-PRDs 00–06 are a **Release 1 foundation** — every component that writes to Firestore lands directly on Shape B rather than migrating after the fact. DM-PRD-07 (Release 2) layers the unified roles + audit substrate on top: `require_role(min_role, scope=Org|Account)` and `write_audit(parent_kind, parent_id, audit_subcollection, ...)` are used by every mutating endpoint across Project Tasks, Automations, Calendar Activities, Campaigns, Integrations, Billing, SAR-E, and Data Pipeline.

### 10.2 Compute Requirements

| Component | Specification | Scaling |
|-----------|--------------|---------|
| **API Server (Cloud Run)** | 4 vCPU, 8GB RAM | 2-10 instances based on load |
| **Agent Engine (Vertex AI)** | Managed by Google | Auto-scaled |
| **GA MCP Server (Cloud Run)** | 2 vCPU, 4GB RAM | On-demand |
| **Data Pipeline service (Cloud Run)** | `kene-data-pipeline-{env}`, 2 vCPU, 4GB RAM | On-demand; per-account + per-connector rate-limit budgets |
| **Cloud Scheduler** | Per-minute crons (task orchestrator `launch-due-tasks`, automations engine `launch-due-automations`); daily (Integrations idle-connection cleanup, Integrations stuck-expired watchdog, KG session-end sweeper); weekly (SAR-E ingestion + retrain `is_system` automation, Mondays 07:00 UTC — extracts the prior ISO week per mapped KPI, aggregates daily→weekly via the `sar_e_ingestion` glue agent, then chains `sar_e_retrain` to refit VAR + IRF) | Managed by Google |

### 10.3 Cost Estimates

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

- **Token cost scales linearly** with requests × tools-per-request. Narrow per-platform specialists with curated ≤30-tool rosters keep per-request tool context ~5–15 tools (≈750–2,250 tokens) instead of the full ~400-tool catalog.
- **MCP server costs scale with server count**, not user count (multi-tenant). Adding Google Ads MCP + HubSpot MCP adds ~$345/month in Cloud Run.
- **Voice channel** (Phase 4) adds: STT/TTS API costs (~$0.006/min for Deepgram) + Meeting BaaS ($50-100+/month per bot seat for Recall.ai). Not included in moderate tier estimate. Budget ~$500-1,500/month additional depending on meeting volume.
- **Gemini code execution** adds minimal cost — billed as additional output tokens (~500-2,000 per request, ~$0.00015-0.0006 at Flash pricing). No separate compute cost; Google manages the sandbox.
- **Voice latency gap:** Current Agent Engine response time is ~7-13s. Voice requires <2s end-to-end. Voice may need a lightweight agent path or a streaming-optimized serving strategy — this is an unsolved prerequisite for Phase 4.

#### Cost Monitoring

The `UsageTracker` (`app/adk/tracking/usage.py`) records per-tool-call events in Firestore with batched writes (100 events or 30s flush). Alert support: `AlertData` model supports threshold-based alerts. **Scalability concern:** At heavy usage, individual Firestore documents per tool call create expensive aggregation queries. A time-bucketed rollup strategy (hourly/daily pre-aggregated counters) is recommended before production scale.

### 10.4 Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE CLOUD PLATFORM                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────────────┐     ┌─────────────────┐        │
│  │  Cloud Run  │     │ Vertex AI           │     │ Cloud Run       │        │
│  │   API       │────▶│ Agent Engine        │────▶│ GA MCP Server   │        │
│  │  (FastAPI)  │     │ (KEN-E root +       │     │ (+ future       │        │
│  │             │     │  specialists +      │     │   platform MCPs)│        │
│  │             │     │  review loops)      │     └─────────────────┘        │
│  │             │     └─────────────────────┘                                │
│  │             │                                                            │
│  │             │     ┌─────────────────────────┐                            │
│  │             │────▶│ Cloud Run               │                            │
│  │             │◀────│ kene-data-pipeline-{env}│  Data Pipeline sibling     │
│  │             │     │ (deterministic, §8.4)   │  (OIDC callbacks)          │
│  └──────┬──────┘     └─────────────────────────┘                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │Firestore │ │  Neo4j   │ │ Redis │ │ Cloud    │ │  GCS     │ │  Cloud   ││
│  │(Shape B  │ │ AuraDB   │ │       │ │ KMS      │ │ task-    │ │ Scheduler││
│  │ config + │ │(Knowledge│ │       │ │ (token   │ │ artifacts│ │ (crons,  ││
│  │ state)   │ │  Graph)  │ │       │ │ wrapping)│ │ + skills │ │  §10.2)  ││
│  └──────────┘ └──────────┘ └───────┘ └──────────┘ └──────────┘ └──────────┘│
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    Secret Manager                                   │     │
│  │      (API keys, OAuth client secrets, HMAC state-token key)         │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │ Weave / W&B    │  │ Platform APIs        │  │ [PLANNED] MCP        │    │
│  │ (Tracing)      │  │ GA, Google Ads,      │  │ Google Ads MCP       │    │
│  │                │  │ Meta Ads, Mailchimp, │  │ HubSpot MCP (hosted) │    │
│  │                │  │ HubSpot              │  │                      │    │
│  └────────────────┘  └──────────────────────┘  └──────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
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

Every third-party credential in KEN-E — OAuth access/refresh tokens, API keys, platform metadata — is owned by the **Integrations** component as a first-class substrate. Every consumer that touches a third-party platform (Data Pipeline connectors, Agent Factory specialists, future Knowledge Graph ingestion) reads credentials through a single internal API (`GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}`, OIDC-authed). No other component decrypts tokens, speaks OAuth, or writes to `platform_connections/*`.

Four properties shape the model:

- **Account-scoped, not user-scoped.** When a user authorizes "my business's GA account," the resulting tokens belong to the KEN-E account; every member can invoke jobs that use them. Matches how marketing teams actually work.
- **KMS-encrypted at rest.** Env-specific Cloud KMS key (never leaves GCP). Encrypted token rows live under `accounts/{account_id}/platform_connections/{connection_id}/tokens/*`. A stolen Firestore export does not yield usable credentials.
- **Generic OAuth driven by `PlatformDefinition`.** The OAuth initiate / callback / refresh machinery is platform-agnostic; adding a platform adds a `PlatformDefinition` Firestore doc (scopes, authorize/token URLs, health check, optional long-lived exchange), not a code branch. HMAC-signed JWT state tokens (10-min expiry, nonce-based replay protection) secure the callback.
- **Re-auth is first-class.** A single `INTEGRATION_NEEDS_REAUTH` notification category + deep-link to `/settings/integrations/{connection_id}` + per-connection 24h dedup. Every consumer handles expired credentials the same way — hold the task, surface the notification, resume on reconnection.

**Legacy pattern retired by IN-PRD-06.** The pre-Integrations model stored per-platform credentials in ADK session state (`ga_credentials`, `google_ads_credentials`, etc.) and used per-specialist `header_provider` closures to read them. IN-PRD-06 swaps the Agent Factory's `_make_header_provider` body to call the Integrations internal endpoint per tool invocation, drops the session-state writes, and enforces removal via a `grep`-based regression guard. Redis caches the encrypted-token fetch with short TTL to absorb burst traffic.

Full data model (`PlatformDefinition`, `PlatformConnection`, `EncryptedToken`, `ConnectionAuditEntry`), OAuth flow + state-token validation, KMS key-rotation runbook, per-platform quirks (Google incremental scopes, Meta long-lived-token exchange, Mailchimp `dc` metadata), and the seven-PRD rollout live in [`components/integrations/README.md`](design/components/integrations/README.md) and IN-PRDs 01–07. IN-PRD-07 adds an opt-in on-demand connection-test surface (`POST /connections/{id}/test`, Settings-card button, MCP tool for agent-side preflight) layered on top of the substrate; it gates nothing downstream.

> For the multi-tenancy model (one MCP server instance per platform serving all accounts, scoped by the per-request OAuth token), see [`docs/design/components/agentic-harness/mcp-architecture.md`](design/components/agentic-harness/mcp-architecture.md) §3.

### 11.3 Rate Limiting & Platform Quota Management

#### 11.3.1 Current Rate Limiting

| Scope | Implementation | Key File |
|-------|---------------|----------|
| **Auth endpoints** | In-memory sliding window per IP. Login: 10/min, 50/hr. Token: 60/min, 1000/hr. Password reset: 3/min, 10/hr. | `auth/rate_limiting.py` |
| **External APIs** | Redis-backed per-API limits. Wikipedia: 10/min. Wikidata: 10/min. Gemini: 5/min. Fail-open if cache unavailable. | `services/rate_limiter.py` |
| **Firestore operations** | Retry with backoff on `ResourceExhausted` (Firestore's rate limit signal). | `strategy_agent/retry_utils.py` |

#### 11.3.2 Platform Quota Management

Marketing platform APIs have aggressive rate limits. KEN-E touches these APIs through two paths, each with its own quota posture:

| Platform | Rate Limits | Path | Quota posture |
|----------|------------|------|---------------|
| **Google Analytics Data API** | 200 requests/min per property, 50,000 requests/day per project | Data Pipeline connector (`ga.*` jobs) **and** GA MCP via the specialist | Data Pipeline: per-account budgets 100/day · 20/hr · 5 concurrent (DP-PRD-02). Specialist MCP calls: **gap — no per-account tracking yet.** |
| **Google Ads API** | 15,000 operations/day (basic access) | Data Pipeline connector (DP-PRD-05) **and** future Google Ads specialist | Data Pipeline: 50/10/3. Specialist path: **gap.** |
| **Meta Marketing API** | Per-ad-account sliding window + business-use-case limits | Data Pipeline connector (DP-PRD-05) **and** future Meta Ads specialist | Data Pipeline: 50/10/3. Specialist path: **gap.** |
| **Mailchimp** | Per-account budgets | Data Pipeline connector (DP-PRD-05) **and** future Mailchimp specialist | Data Pipeline: 20/5/2. Specialist path: **gap.** |
| **HubSpot** | 100-200 requests/10s per plan tier, daily limits | Provider-hosted HubSpot MCP (no Data Pipeline connector today) | **Gap on both paths.** |

Data Pipeline consumers already honor per-account + per-connector budgets; transient 429s retry with exponential backoff, and semantic 4xxs fail the task with a notification. The remaining gap is **agent-routed MCP calls** — the specialist's McpToolset has no quota awareness today.

**Recommendation (specialist path only):**

1. **`before_tool_callback` quota check** — Before each MCP tool call, check remaining quota from a shared counter (Redis) keyed by `(account_id, platform)`. If low, throttle or inform the user.
2. **Response header parsing** — Extract `X-RateLimit-Remaining` / `Retry-After` from MCP responses; store in Redis for quota tracking.
3. **User-facing feedback** — When rate limited, the specialist surfaces the constraint: "Google Ads daily quota is at 95%; I can run 3 more queries today."

### 11.4 Risk Assessment Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Context overflow during complex tasks** | High | High | ADK compaction (interval=5, threshold=50K), hierarchical loading, narrow specialist scope, ≤30-tool roster discipline |
| **MCP server connection failures** | Medium | High | ADK auto-reconnect, health monitoring, retry logic. Gap: no circuit breaker. |
| **Agent hallucination in strategy outputs** | Medium | High | Require citations, fact-checking tools, human review queue |
| **ADK version dependency** | Medium | Medium | Pin versions, test upgrades in staging before prod |
| **Firestore config drift** | Low | Medium | Config validation at deploy time, registry consistency tests |
| **Cost overrun from token usage** | Medium | Medium | UsageTracker (token + cost metrics), Weave tracing, alerts via `AlertData` model |
| **Platform API rate limit exhaustion** | Medium | Medium | Per-platform quota tracking (gap — not yet implemented) |
| **OAuth token expiry mid-conversation** | Medium | Low | Integrations' pre-emptive refresh sweeper + synchronous refresh on near-expiry reads + `INTEGRATION_NEEDS_REAUTH` notification + per-connection 24h dedup (IN-PRD-02 / IN-PRD-05). |
| **Credential encryption at rest** | Low | High | Cloud KMS per env (env-specific key, never leaves GCP). Owned by Integrations (IN-PRD-01). |
| **Review loop latency increase** | High | Medium | Cap `max_iterations=3` (~15s overhead max). Root agent skips criteria for simple lookups. AH-PRD-01. |
| **Token cost increase from review loops** | High | Medium | Reviewer uses cheapest model (`gemini-2.0-flash`); criteria generation ~200 tokens; monitored via Weave. |
| **LLM-generated acceptance criteria are poor** | Medium | Medium | Include good/bad criteria examples in root-agent instruction; iterate based on Weave traces. |
| **State collisions in parallel workflow execution** | Low | High | Unique `output_key` prefix per step, enforced by `build_workflow_pipeline()` factory. |
| **Artifact size bloats review context** | Medium | Low | Limit embedded data to summaries; defer raw data to separate `data_uri` if >1,000 rows. AH-PRD-04. |
| **Voice latency incompatible with Agent Engine** | High | High | Agent Engine ~7-13s vs. voice <2s target. R5 voice feasibility spike (Story 5.5-1) is the de-risk gate before R6 commits. |
| **Platform SDK breaking changes (Meta, Google Ads)** | Medium | Medium | Pin SDK versions; integration tests catch regressions; budget buffer in Execution Specialist sprint. |
| **MER-E evaluation of a moving target** | Medium | Medium | Parallel track design — extraction/scoring evolves with agents. Output type expansion story per MER-E phase. |

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

### 11.7 Targeted Rollouts & Kill Switches

KEN-E uses a first-party **Feature Flags** system for safe rollouts across every component — percentage-based bucketing per entity (account, organization, or user), explicit allowlists, and super-admin-managed kill switches with a 60-second propagation SLO.

- **Evaluation:** `is_feature_enabled(flag_key, context)` Python helper on the backend + `useFeatureFlag(key)` React hook on the frontend. Bucketing is deterministic (`sha256(flag_key:entity_id)[:8] % 100`) — same entity lands in the same bucket across sessions, devices, and backend/frontend callers.
- **Targeting:** allowlists override percentage rollouts; allowlists are positive-match only (always-on). The only "off" mechanism is the kill switch (`is_active=false`), which short-circuits all targeting and returns `default_enabled` — meaning a true global disable also requires `default_enabled=false`. Release 1 ships boolean flags only; multi-variant is deferred.
- **Kill switches:** Super-admin UI at `/admin/feature-flags` with audit log. 60s in-process LRU cache on the backend + TanStack Query `staleTime` on the frontend bounds propagation.
- **Dev overrides:** Non-production `?ff.<key>=on|off` URL parameter, hard-gated on `VITE_ENVIRONMENT !== 'production'`.
- **Server-built context:** `EvaluationContext` is derived from the auth token, not client-sent — callers cannot spoof a different identity into an evaluation.

Full system design, data model, targeting rules, and admin UI live in [`components/feature-flags/README.md`](design/components/feature-flags/README.md) and the three FF-PRDs. This is a Release 1 foundation — later components (agent factory, skills, new specialists) can land behind flags for controlled rollout.

---

## 12. Roadmap

Project-level sequencing with `blocked_by` dependencies across all components is tracked in [`docs/design/components/PROJECT-PLANNER.md`](design/components/PROJECT-PLANNER.md). Per-feature execution (Issues, Cycles, status transitions) is tracked in Linear — see [`CLAUDE.md`](../CLAUDE.md) "Linear Workflow Conventions" for the team → repo → component mapping.

### Release overview

| Release | Theme | Components / headline projects |
|---------|-------|--------------------------------|
| **1** | Foundation | Data Management Shape B migration (DM-PRDs 00–06); Agentic Harness review loop + agent factory + GA specialist (AH-PRDs 01–03); UI design system + core shell + workflows shell + organization selection (UI-PRDs 01, 02, 03, 08 — UI-PRD-03 moved up from R2 to align with AH-PRD-02); Feature Flags (FF-PRDs 01–03); Chat substrate — session metadata + sidebar + categories + todos/artifacts (CH-PRDs 01, 02, 03, 05) |
| **2** | Task Automation | Approval workflow & audit (DM-PRD-07); Project Tasks end-to-end (PR-PRDs 01–09); Automations platform (A-PRDs 01–07 — A-PRD-06 publishes the shared `frontend/src/components/dag/TaskGraph.tsx` plus shared `frontend/src/components/workflows/ActivityDetailPanel.tsx` / `ScheduleEditorModal.tsx`; A-PRD-02 fires `AUTOMATION_RUN_COMPLETE` notifications); Dashboards (DB-PRDs 01–04); Performance page shell (PE-PRD-01 — moved up from R4 to unblock DB-PRD-02; gate degrades gracefully pre-SAR-E); Calendar UI (UI-PRD-04); Integrations OAuth substrate (IN-PRDs 01–07); Data Pipeline foundation + GA connector + task integration + inline authoring panel + testing (DP-PRDs 01–04, 06 — DP-PRD-04 rescoped to inline in the shared DAG editor side-panel; no `/workflows/data-pipelines` standalone routes); Chat session status view (CH-PRD-04, requires IN-PRD-03) |
| **3** | Expertise + Monetization | Knowledge Graph migrations + provenance + read tools + session-end automation + research refactor + integration polish (KG-PRDs 01–06); Skills sandbox + backend + factory integration + authoring UI + agent-builder controls (SK-PRDs 00–04); Knowledge/Strategy UI redesign (UI-PRD-05); Data Visualization (AH-PRD-04); Billing end-to-end — Stripe, token meter, monthly enforcement, subscription UI, sales handoff (BL-PRDs 01–06) |
| **4** | Measurement | SAR-E analytical backend — configuration, weekly ingestion, VAR baselines, IRF scenarios, target derivation, analytical query layer (SE-PRDs 01–07); Performance page tab content — analysis, simulations, configuration, setup wizard, targets, diagnostics, testing (PE-PRDs 02–08; the Performance shell PE-PRD-01 shipped in Release 2 to unblock the Dashboards tab) |
| **5** | Multi-Channel + Extensions | Slack channel; Extensions marketplace (UI-PRD-06); additional platform connectors — Google Ads / Meta Ads / Mailchimp (DP-PRD-05); additional narrow specialists (Google Ads, Meta Ads, Mailchimp) |
| **6** | Voice | Voice channel (Pipecat + Meeting BaaS) |

**Subsumed / dropped:** `UI-PRD-07` (Performance page redesign) is folded into `PE-PRD-01`, which delivers the same `/performance` shell on `LayoutC` as part of the full Performance component.


---

## 13. Appendices

### Appendix A: Platform Integration Reference

Full platform-by-platform integration table (MCP / SDK / built-in, status, specialist assignment) lives in [`docs/design/components/agentic-harness/mcp-architecture.md`](design/components/agentic-harness/mcp-architecture.md) §4.

### Appendix B: Output Types for Evaluation

| Category | Output Types |
|----------|-------------|
| **Business Strategy** | company_overview, swot_analysis, strategic_goals, value_proposition |
| **Marketing Strategy** | icp_narrative, campaign_strategy, channel_strategy, messaging_framework |
| **Competitive** | competitor_analysis, competitive_positioning, market_trends |
| **Content** | blog_post, social_post, email_copy, video_script, landing_page |
| **Analytics** | performance_report, forecast, attribution_analysis |

### Appendix C: Configuration Reference

Agent configuration (Firestore `agent_configs/{id}` fields + per-account overlay + forward-compat skill fields) lives in [`AH-PRD-02`](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md) §4 and §5.2. MCP server configuration (current YAML + planned Firestore schema) lives in [`mcp-architecture.md`](design/components/agentic-harness/mcp-architecture.md) §6.

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| **HCL** | Hierarchical Context Loading — original 3-level context-loading design. Superseded: L1 executive summary still loads at session start; L2/L3 replaced by the four KB read tools in KG-PRD-03. |
| **Session-start executive summary** | ~5,000-token company overview loaded from Neo4j into `organization_context` session-state key at session creation. Injected into every LLM turn by the `InstructionProvider`. |
| **load_context_section** | Orchestrator read tool that returns one of 5 domain sections as formatted markdown (products, icps, competitors, strategies, brand). Calendar / campaign / performance data lives in Firestore and SAR-E and is accessed through component-specific paths, not through this tool. Account-scoped via `tool_context.state["account_id"]`. See [KG-PRD-03](design/components/knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md). |
| **load_document** | Orchestrator read tool that returns drill-down detail for a specific entity (`entity_type`, `entity_id`). Complements `load_context_section`. See [KG-PRD-03](design/components/knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md). |
| **search_kb** | Orchestrator read tool for semantic vector search over the 768-dim `kb_vector_index` on `:KGNode` (Google `text-embedding-004`). Fuzzy fallback when the question doesn't map cleanly to a domain section. See [KG-PRD-03](design/components/knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md). |
| **list_observations** | Orchestrator read tool for long-tail conversational facts captured by the session-end learning loop (KG-PRD-04). See [KG-PRD-03](design/components/knowledge-graph/projects/KG-PRD-03-orchestrator-read-tools.md). |
| **Observation** | Neo4j node representing a conversational fact surfaced in chat (e.g., "CMO is pivoting to usage-based pricing"). Bi-temporal (`valid_from`/`valid_to`); linked to the `Session` that produced it via `:OBSERVED_IN`. See [KG-PRD-02](design/components/knowledge-graph/projects/KG-PRD-02-provenance-spine.md). |
| **Session (Neo4j)** | Neo4j node representing a chat session. Per-turn `touch_session` lazy-creates on first turn and bumps `last_message_at`. Used for provenance on Observations and other writes. See [KG-PRD-02](design/components/knowledge-graph/projects/KG-PRD-02-provenance-spine.md). (Not to be confused with ADK session state.) |
| **ResearchRun** | Neo4j node representing an episode of research (e.g., account-creation deep research). Carries `source_research_run_id` and `:ESTABLISHED_BY` edges on every node produced. Enables idempotent reruns. See [KG-PRD-02](design/components/knowledge-graph/projects/KG-PRD-02-provenance-spine.md), [KG-PRD-05](design/components/knowledge-graph/projects/KG-PRD-05-research-on-creation-refactor.md). |
| **Session-end automation** | Daily system-triggered automation that reviews idle sessions and proposes KB updates. Reviewer agent emits `proposal.json`; applier agent routes each change (auto-apply vs HITL halt). See [KG-PRD-04](design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md). |
| **`:KGNode`** | Shared Neo4j label on every strategy + provenance node (29 types). Enables one vector index, one account-scoped lookup index, one uniqueness constraint across the whole KB. See [KG-PRD-01](design/components/knowledge-graph/projects/KG-PRD-01-migrations-constraints-indexes.md). |
| **`ProjectPlan` / `PlanTask`** | Persistent plan + DAG-node definitions; core project-tasks data model. `ProjectPlan` lives at `accounts/{account_id}/project_plans/{plan_id}` with versioning + audit log. See [project-tasks README](design/components/project-tasks/README.md). |
| **`TaskOrchestrator`** | Service that advances active plans; single convergence point for task-state changes. Three entry methods: `activate_plan`, `on_task_status_change` (event-driven), `on_task_due` (time-based). Reuses `AgentEngineClient` for agent dispatch. See [PR-PRD-04](design/components/project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md). |
| **`is_system`** | Flag on `ProjectPlan` marking platform-owned seeded templates (hidden from user-facing lists, read-only in UI). Consumed by Automations and by the KG session-end automation. |
| **Time-based scheduler** | Cloud Scheduler cron firing `POST /api/v1/internal/scheduler/launch-due-tasks` per minute; collection-group query for tasks whose `due_date + launch_time_utc <= now` and `launched_at IS NULL`, hands off to `TaskOrchestrator.on_task_due`. See [PR-PRD-06](design/components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md). |
| **`PlanRun`** | Execution record against a `ProjectPlan` template (Automations component). One plan can have many runs — recurring, manual, or system-triggered. See [automations README](design/components/automations/README.md). |
| **Data Pipeline** | Deterministic (non-agentic) component owning platform-API extraction. Typed connectors (GA, Google Ads, Meta Ads, Mailchimp) run on fixed schedules via a sibling `kene-data-pipeline-{env}` Cloud Run service; output is persisted as a `TaskArtifact`. See [Data Pipeline component](design/components/data-pipeline/README.md). |
| **`DataPipelineJob`** | Declarative specification of a platform-API extraction — connector, operation, input schema, output shape, cache TTL, rate-limit budget, test-mode policy. Global + per-account overlay catalogs. |
| **`DataPipelineRun`** | Execution record of a `DataPipelineJob` — inputs, input hash, output artifact id, cache hit/miss, status, start/finish timestamps. |
| **`assignee_type="data_pipeline"`** | Third `PlanTask.assignee_type` value alongside `agent` and `human`. Signals the `TaskOrchestrator` to dispatch via `DataPipelineDispatcher` → sibling Cloud Run service. See [DP-PRD-03](design/components/data-pipeline/projects/DP-PRD-03-task-system-integration.md). |
| **Integrations** | Component owning the third-party OAuth credential substrate. Every consumer (Data Pipeline, Agent Factory, future KG ingestion) reads credentials via a single internal API (`GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}`, OIDC). KMS-encrypted token store; generic OAuth driven by `PlatformDefinition`. See [Integrations component](design/components/integrations/README.md). |
| **`PlatformDefinition`** | Global Firestore doc describing a third-party platform's OAuth metadata (authorize URL, scopes, token URL, health check, optional long-lived exchange). Adding a platform adds a `PlatformDefinition`, not a code branch. |
| **`PlatformConnection`** | Per-account Firestore doc at `accounts/{account_id}/platform_connections/{connection_id}` recording an account's connection to a platform (status, scope, external label, connected-by user). Token rows live in the `tokens/` subcollection, KMS-encrypted. |
| **`INTEGRATION_NEEDS_REAUTH`** | Notification category raised by Integrations when an account's platform connection expires or is revoked. Deep-links to `/settings/integrations/{connection_id}`; per-connection 24h dedup. Every consumer handles expired credentials the same way. See [IN-PRD-05](design/components/integrations/projects/IN-PRD-05-reauth-lifecycle.md). |
| **SAR-E** | Simulation and Recommendations Engine — KEN-E's analytical backend. Owns weekly KPI time series, VAR baseline forecasts, IRF scenario propagation, LLM-driven target derivation, and the analytical query layer the Performance page renders. Opt-in per account; "statistical association only" methodology invariant. See [SAR-E component](design/components/sar-e/README.md). |
| **`EffectivenessKPI`** | SAR-E's unit of measurement — a weekly metric (e.g., "first-purchase events") mapped to one of four funnel Objectives (`Problem Awareness` / `Brand Awareness` / `Consideration` / `Conversion`). Four per account, chosen during the setup wizard. |
| **`FunnelStageMapping`** | 4-row binding of funnel Objectives to `EffectivenessKPI`s. Versioned (history retained) — mapping changes alter historical interpretation, so trendlines walk the history per week. |
| **VAR (model)** | Vector Auto-Regression model trained weekly per account on the four KPI time series (min 26 weeks, max lag 8, AIC/BIC lag selection). Produces 12-week baseline forecasts with 80% prediction intervals. Flat-baseline fallback for accounts with <26 weeks of history. See [SE-PRD-03](design/components/sar-e/projects/SE-PRD-03-var-baseline.md). |
| **IRF** | Impulse-Response Function — the VAR model's moving-average representation over the 12-week horizon. Drives scenario propagation: user supplies weekly per-KPI overrides, SAR-E returns baseline / scenario / incremental per KPI per week. See [SE-PRD-04](design/components/sar-e/projects/SE-PRD-04-irf-scenarios.md). |
| **`Target`** (SAR-E) | Per-KPI, per-week goal derived by the `performance_forecasting` specialist from baseline + calendar + historical pulses. Supersedes on edit (no version history); carries a `methodology_note` phrasing the relationship as association. See [SE-PRD-05](design/components/sar-e/projects/SE-PRD-05-target-derivation-specialist.md). |
| **Performance page** | `/performance` — six-tab surface (Analysis / **Dashboards** / Simulations / Targets / Diagnostics / Configuration, in Figma order) + four-step setup wizard at `/performance/setup`. Opt-in per account for the four SAR-E-backed tabs; Dashboards + Configuration are always visible. The Dashboards tab is owned by the Dashboards component (DB-PRD-02 / DB-PRD-03); the rest by Performance (PE-PRDs 01–08). See [Performance component](design/components/performance/README.md). |
| **Setup Wizard** | Four-step onboarding flow (`/performance/setup`) that turns an opted-out account into a fully configured SAR-E consumer: picks four Effectiveness KPIs, maps them to the four funnel Objectives, sets backfill depth (computed, not chosen — `min(104, min(weeks_available_across_KPIs))`), reviews + submits. See [PE-PRD-05](design/components/performance/projects/PE-PRD-05-setup-wizard.md). |
| **Workflows tab** | Top-level `/workflows` route hosting three tabs — Agents (config-driven specialist admin, owned by AH-PRD-02), Automations (A-PRD-05/06), Skills (SK-PRD-03). Tab container shell delivered by UI-PRD-03 (Release 1). Data pipelines are not a tab — they are a `PlanTask.assignee_type="data_pipeline"` value created from inside the shared DAG editor on Automations and Dashboards detail pages (§8.4). |
| **Performance page** (entry) | `/performance` 6-tab page (Analysis / Dashboards / Simulations / Targets / Diagnostics / Configuration). PE-PRD-01 owns the shell + tab routing + SAR-E gate; the Dashboards tab is owned by the Dashboards component (DB-PRD-02 list / DB-PRD-03 details) and is not gated by SAR-E enablement. UI-PRD-07 was the original presentation-only redesign — retired and subsumed by PE-PRD-01. |
| **Shared DAG editor** | `frontend/src/components/dag/TaskGraph.tsx` (+ `TaskNode.tsx`, `dagLayout.ts`) — single React Flow DAG editor implementation owned by A-PRD-06 and reused verbatim by DB-PRD-03. Surfaces on `/workflows/automations/{plan_id}` (Automations details) and `/performance/dashboards/{plan_id}` (Dashboards details). The "+ Add Task" button on the canvas opens the right-side task panel; selecting `assignee_type="data_pipeline"` swaps the agent/human fields for DP-PRD-04's `PipelineJobPicker` + (editor role only) `CustomJobAuthoringPanel`. |
| **Shape B** | Firestore layout convention — every account-scoped resource lives at `accounts/{account_id}/{resource}/…`. Owned by the Data Management component. See [data-management README](design/components/data-management/README.md). |
| **`FeatureFlag`** | Boolean targeted-rollout flag with allowlist + percentage-bucketing rules; kill switches propagate in ≤60s. See [feature-flags README](design/components/feature-flags/README.md). |
| **`is_feature_enabled` / `useFeatureFlag`** | Backend Python helper + frontend React hook for evaluating a feature flag. Bucketing is deterministic `sha256(flag_key:entity_id)[:8] % 100`. |
| **Design System (Soft Maximalism)** | KEN-E's visual design system — `theme.css` tokens, Tailwind config, re-skinned shadcn primitives. Delivered by UI-PRD-01 and used by every frontend page. |
| **MCP** | Model Context Protocol — standard for tool integration |
| **ADK** | Agent Development Kit — Google's agent framework |
| **McpToolset** | ADK class that manages MCP server connections; one per server per specialist, wired at agent construction |
| **InstructionProvider** | Callable that returns dynamic instructions per LLM turn (reads `organization_context` from session state) |
| **Agent Factory** | Config-driven system that assembles agents from Firestore at deploy time. See [AH-PRD-02](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md). |
| **Specialist** | A narrow per-platform `LlmAgent` with a curated ≤30-tool roster (e.g., Google Analytics Specialist, Google Ads Specialist). See [agentic-harness README §2.6](design/components/agentic-harness/README.md#26-specialist-roadmap). |
| **Review Loop** | Generator–Critic pattern via ADK `LoopAgent` — reviewer evaluates specialist's draft against acceptance criteria. See [AH-PRD-01](design/components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md). |
| **Skill** | Self-contained unit of expertise (SKILL.md) providing procedural knowledge to agents via progressive disclosure (L1/L2/L3). See [Skills component](design/components/skills/README.md). |
| **SkillToolset** | ADK class for incorporating skills into `LlmAgent` via the `tools` parameter |
| **SKILL.md** | Markdown file with YAML frontmatter defining a skill's name, description, allowed-tools, and procedural instructions |
| **ToolRegistry** | Build-time metadata catalog that the agent factory reads to assemble each specialist's ≤30-tool roster. Not a runtime router or filter. See [agentic-harness README §2.5](design/components/agentic-harness/README.md#25-tool-assignment--routing-model). |
| **tool_filter** *(retired)* | ADK `BaseToolset` parameter for per-turn tool filtering. KEN-E retired this mechanism in favor of fixed ≤30-tool rosters; term appears only in historical context. |
| **ReadonlyContext** | ADK read-only view of session state (`MappingProxyType`), passed to `InstructionProvider`. Live view of the mutable state dict — sees `CallbackContext` writes immediately. |
| **CallbackContext** | ADK mutable context passed to `before_agent_callback`, `after_agent_callback`, and model callbacks. Writes to `callback_context.state` go to `session.state` with delta tracking. |
| **before_agent_callback** | ADK callback that fires before each LLM turn. Receives `CallbackContext` (mutable). Used for Weave tracing. |
| **Vega-Lite** | Declarative JSON-based visualization grammar. Agents produce Vega-Lite chart specs via `create_visualization()`; the frontend renders them. See [`data-visualization.md`](design/components/agentic-harness/data-visualization.md). |
| **Artifact** | A structured output (e.g., Vega-Lite chart spec) produced alongside text by specialist agents. Delivered to the frontend via the `artifacts` field on `ChatResponse`. |
| **create_visualization** | Python function tool available to all specialist agents. Produces a Vega-Lite artifact and writes it to `response_artifacts` session state. Not an MCP tool. |
| **Code Execution (Gemini)** | Built-in Gemini model capability that generates and runs Python code in a Google-managed sandbox. Enabled via `GenerateContentConfig.tools = [Tool(code_execution=ToolCodeExecution())]`. Returns `executable_code` and `code_execution_result` parts in the LLM response. |
| **Built-in Model Capability** | A capability provided natively by the LLM model (e.g., Gemini code execution), configured via `GenerateContentConfig` rather than as an MCP or SDK tool. Zero context overhead — no tool definition is sent. |
| **ToolCodeExecution** | ADK/Gemini class that enables code execution when added to `GenerateContentConfig.tools`. Part of `google.genai.types`. |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 4.5 | 2026-04-27 | Development Team | SAR-E pre-Linear alignment pass. §1.1 component count corrected from "thirteen" → "fifteen" (stale phrasing from v4.2; §1.6 table has shown 15 since v4.4 added Performance + SAR-E + Integrations + Data Pipeline). §8.5 "Three facts shape the design" → "Four facts" — added the missing facts the SAR-E component README + implementation-plan have always declared: "SAR-E is the computation home" (Performance renders, Data Pipeline feeds, SAR-E owns every statistical artifact) and "Reasoning belongs to an ADK specialist; math belongs to statsmodels" (closed-form numerical code vs. Gemini Pro target derivation). §10.2 Cloud Scheduler row reworded — the weekly cron is the SAR-E *ingestion + retrain* `is_system` automation (Mondays 07:00 UTC), not just retrain; the chain is `sar_e_ingestion` glue agent → `sar_e_retrain` glue agent. No schema, API, or orchestration changes — doc accuracy only. Sister edits: SAR-E PRDs (SE-PRD-01 adds `ab_harness_opt_out` to `SarEConfig`; SE-PRDs 01/02/03 add the missing `A-PRD-01..04` + `AH-PRD-02` blockers their glue agents and `is_system` automations require; SE-PRDs 01/05/07 normalize audit action names — `setup_completed`, `target_save`, `ab_config_update` — to match DM-PRD-07's registered tuple set), AH-PRD-02 (adds optional `agent_configs/{id}.response_schema` field that SE-PRD-05's `performance_forecasting` specialist needs for `DerivedTargetsResponse` enforcement), PROJECT-PLANNER (SE-PRD-01/02/03 `blocked_by` columns updated). |
| 4.4 | 2026-04-27 | Development Team | Dashboards-component cleanup pass. §8.3 Automations & System-Triggered Plans expanded from "Two components" → "Three components" — added a Dashboards bullet describing it as the third consumer of the §8.2 orchestration layer (runs through A-PRD-02 manual-trigger; introduces only the canvas-resolution layer, no new orchestrator behavior); existing Automations bullet updated to mention A-PRD-02's new `AUTOMATION_RUN_COMPLETE` notification (single producer, deep-link routes by `plan.type`, replaces the unsubstantiated "Dashboard ready" claim that had been documented in DB-PRD-02 §3 with no producer). §12 Release overview: PE-PRD-01 (Performance shell) moved from R4 → R2 to unblock DB-PRD-02 — its `ForecastingEnabledGate` degrades gracefully (`enabled=false` on 4xx/5xx/network from `/sar-e/{account_id}/config/status`) so SAR-E-backed tabs stay hidden in R2 and light up automatically when SE-PRD-01 ships in R4. Release 2 row gained PE-PRD-01 + a note on shared panels (A-PRD-06 publishes `ActivityDetailPanel` and `ScheduleEditorModal` at `frontend/src/components/workflows/`; `ActivityDetailPanel` is relocated from Calendar PRD-3 and given an additive `pinToDashboardSlot?: ReactNode` prop that DB-PRD-03 fills). Release 4 row reworded "PE-PRDs 01–08" → "PE-PRDs 02–08". No schema, API, or orchestration changes in this doc — sequencing + producer cleanup only. Sister edits in PROJECT-PLANNER.md, PE-PRD-01, A-PRD-02, A-PRD-06, DB-PRDs 01–04, PE-PRD-02. |
| 4.3 | 2026-04-27 | Development Team | Project-tasks PRD alignment pass (see [Review 29](design/DESIGN-REVIEW-LOG.md#review-29-project-tasks-prds--cross-component-alignment-pass)). §8.2 Project Plans & Task Orchestration: corrected the planning-specialist Firestore config-doc path (`agents/project_planning` → `agent_configs/project_planning`); added a "Multi-category activities, Campaigns, orphan tasks" paragraph block describing PR-PRD-07's category discriminator + sparse fields + recurrence + `owner_email` / `unscheduled` extensions, the orphan-task subcollection + lifecycle, and PR-PRD-08's first-class Campaign entity with the four-objective enum + per-account generic-fallback seeding; closing pointer updated from "six PRDs (PR-PRD-01 through PR-PRD-06)" to "nine PRDs (PR-PRD-01 through PR-PRD-09)". §12 Release table for Release 2 updated PR-PRDs 01–08 → 01–09 to reflect the new PR-PRD-09 (Planning Agent Multi-Category Update). No data-model, API, or orchestration changes in this doc — this is doc-alignment only; the changes shipped in component PRDs. |
| 4.2 | 2026-04-23 | Development Team | Reflected the four new components added in April (Data Pipeline, Integrations, SAR-E, Performance). §1.1 Purpose reframed from "agentic harness" to "system architecture" — acknowledges the agentic + deterministic + analytical execution layers. §1.4 Key Design Decisions gained four rows (deterministic Data Pipeline, Integrations-owned credentials, opt-in analytical layer, "statistical association only" invariant). §1.6 Component Landscape updated from "nine" to "thirteen" discrete components; table gained Data Pipeline / Integrations / SAR-E / Performance rows with scope summaries; trailing section-mapping refreshed. §3.6 session-state tables marked `ga_credentials` as being retired by IN-PRD-06 and noted the `platform_credentials.<service>` model was superseded by Integrations' fetch-per-call endpoint. §7.1 split Performance out of "Feature pages" into its own bullet naming Performance (PE-PRDs 01–08) as page owner and SAR-E (SE-PRDs 01–07) as analytical source. §8 intro updated; added §8.4 Deterministic Platform-API Extraction (Data Pipeline) framing `assignee_type="data_pipeline"`, and §8.5 Analytical Layer (SAR-E & Performance) framing the opt-in statistical backend. §10.1 Data Layer expanded with Integrations / Data Pipeline / SAR-E Firestore surfaces, added Cloud KMS as a fifth persistent store, clarified the skills + task-artifacts GCS buckets. §10.2 Compute gained a Data Pipeline Cloud Run row + a Cloud Scheduler row enumerating the per-minute/daily/weekly crons. §10.4 Architecture Diagram refreshed with the sibling Data Pipeline service, Cloud KMS, Cloud Scheduler, and an accurate Secret Manager description (OAuth tokens moved out). §11.2 Credential Lifecycle collapsed from three subsections (GA-specific OAuth flow + gap table + session-state credential keys) to one tight Integrations-owned summary — four key properties + explicit retirement of the legacy pattern + pointer to `integrations/README.md`. §11.3.2 retitled "Platform Quota Management" — split rate-limit handling into Data Pipeline path (budgets enforced) vs agent-routed MCP path (still a gap). §11.4 Risk Matrix: OAuth expiry and credential-encryption rows updated to reflect Integrations' refresh sweeper + KMS-at-rest. §12 Roadmap gained a "TBD" row for the four unassigned components. §3.4 + §3.5 trimmed Python code blocks to prose + file pointers. Appendix D Glossary gained 17 new entries covering Data Pipeline / Integrations / SAR-E / Performance terminology. Fixed two broken `design/api-gateway-multi-channel.md` links (file moved to backlog). |
| 1.0 | 2026-01-10 | Development Team | Initial design document |
| 2.0 | 2026-03-10 | Development Team | Updated to reflect Sprints 1-4 implementation. Replaced fictional code with actual implementations. Marked unbuilt features as [PLANNED]. |
| 2.1 | 2026-03-10 | Development Team | Design review: Added `tool_filter` + ToolRegistry architecture (Section 4.3). Updated ADK internals analysis. Added sprint-3b dependency note. Fixed Deepgram latency claim. |
| 2.2 | 2026-03-11 | Development Team | Cross-reference pass: added links to design docs (`agent-hierarchy.md`, `mcp-architecture.md`, `api-gateway-multi-channel.md`) and Notion Design Decisions database. Fixed Section 10 duplicate numbering and ToC mismatch. |
| 2.3 | 2026-03-11 | Development Team | Architecture accuracy pass: reframed doc as architecture reference (current + `[PLANNED]`). Split Sections 1.3, 2.3 into current/planned. Rewrote Section 2.1 diagram for target architecture. Expanded Section 3.6 (session state keys, token visibility, billing/usage tracking). Added Decisions 19-20 links. |
| 2.4 | 2026-03-11 | Development Team | Added Section 4.6 Review Loop Pattern (Generator-Critic with LoopAgent). Updated Section 2.3.2 request flow to show review loop. Rewrote Section 8.1 with ADK workflow agent architecture, ParallelAgent for concurrent steps, Meta Ads optimisation example, and dynamic pipeline construction. Added Decision 21 link. |
| 2.5 | 2026-03-11 | Development Team | Added `[TRANSITIONAL]` convention for GA Agent and Company News Agent (successors documented). Added Meta Ads SDK shared access (Analytics reads + Execution reads/writes via `tool_filter`). Added Section 6 Skills Architecture (predefined + custom skills, SkillToolset integration, skill builder UI). Renumbered Sections 6-12 → 7-13. Added Decision 22 link. Updated glossary with Skill/SkillToolset/SKILL.md terms. |
| 2.6 | 2026-03-18 | Development Team | ADK 1.26.0 experiment corrections: removed `SequentialAgent` wrappers inside `LoopAgent` (Sections 4.6, 8.1), added `include_contents='none'` on reviewers and synthesizers, added `{key?}` optional template syntax, added pipeline `SequentialAgent` wrappers for `ParallelAgent` branches. New subsections: 8.2 ADK Implementation Details (`build_review_pipeline()` and `build_workflow_pipeline()` factories, synthesizer pattern), 8.3 ADK Pitfalls (3 validated pitfalls), 8.4 LLM Call Cost & Latency. Renumbered 8.2-8.5 → 8.5-8.8. Added LLM call cost table to Section 4.6. |
| 2.7 | 2026-03-18 | Development Team | Experiment #4 resolution — resolved `tool_filter` driver pattern as `before_agent_callback`. Updated Section 3.6.2 (`tool_filter_state` Set By). Resolved `[PLANNED] tool_filter driver` in Section 4.3 (added execution order note). Added specialist callback chaining note to Section 4.2. Added ReadonlyContext, CallbackContext, before_agent_callback glossary entries (Appendix D). See [Review 9 in DESIGN-REVIEW-LOG](design/DESIGN-REVIEW-LOG.md#review-9-experiment-4--tool_filter-integration-pattern-resolution). |
| 2.8 | 2026-03-18 | Development Team | Data visualization & artifacts. Added Vega-Lite artifacts decision to Section 1.4. Updated Section 2.3.2 request flow (create_visualization in specialist, artifacts extraction in response). Added `response_artifacts` to Section 3.6.2 session state. Added visualization blockquote to Section 4.4. Added "Visualization Artifacts in Review Loops" subsection after Section 4.6. Added data visualization row to Section 12.3 roadmap. Added Vega-Lite, Artifact, create_visualization glossary entries (Appendix D). Created [`data-visualization.md`](design/components/agentic-harness/data-visualization.md). |
| 2.9 | 2026-03-18 | Development Team | Gemini native code execution. Added code execution decision to Section 1.4. Added Tool Type Taxonomy table to Section 4.3 (MCP Tools, SDK Function Tools, Built-in Model Capabilities). Updated Analytics Specialist in Sections 4.4 and 4.5 with Gemini code execution. Added code execution note to Section 4.6 review loop. Added Section 9.2.1 Code Execution Traces. Added code execution cost bullet to Section 10.2. Added Gemini code execution to Section 12.3 roadmap and Appendix A. Added Code Execution (Gemini), Built-in Model Capability, ToolCodeExecution to Appendix D glossary. |
| 4.1 | 2026-04-22 | Development Team | Added the **Dashboards** component (ninth component). §1.6 prose updated from "eight discrete components" → "nine"; §1.6 table gained a Dashboards row between Automations and Skills (`type="dashboard"` ProjectPlans + canvas placements + artifact resolver + Performance-page Dashboards tab). Project Tasks row updated to reflect PR-PRDs 07–08 additions (multi-category activities, campaigns); Data Management row updated to reflect DM-PRD-07 (Roles, Members, Audit Substrate). §12 Release overview updated: Release 1 includes DM-PRDs 00–06; Release 2 adds DM-PRD-07 (was implicitly bundled with R1) plus PR-PRDs 01–08 (was 01–06) and Dashboards DB-PRDs 01–04. No schema, API, or orchestration changes in this doc — the Dashboards component sits on top of existing Project Tasks + Automations + A-PRD-03 artifact infrastructure without introducing new storage or runtime primitives. |
| 4.0 | 2026-04-20 | Development Team | **Document reframed as `KEN-E System Architecture`** (from "Agentic Harness Design"). The doc's scope had grown beyond agent architecture to cover context management, multi-step orchestration (project-tasks + Automations + KG session-end), evaluation framework, infrastructure, resilience/security, and now the full eight-component landscape — the title and framing needed to match. Changes: renamed header + rewrote top-of-doc purpose statement to position this as the canonical system architecture (not a PRD, not a roadmap, not an ADR log). Added §1.6 Component Landscape (eight-component table with one-line scope + doc pointer per component). Renamed §7 "Multi-Channel Support" → "Frontend & Channels" and added §7.1 (Web UI / design system / workflows tab container, from UI component), §7.2 (channel-agnostic API), §7.3 (planned channels). Added §10.1 Data Layer covering Firestore Shape B (data-management), Neo4j, Redis, GCS — renumbered downstream §10 subsections. Added §11.7 Targeted Rollouts & Kill Switches (feature-flags). Expanded §12 Roadmap with a release-plan table tying components to releases + a note reconciling PROJECT-PLANNER vs product-roadmap numbering. Added glossary entries for `Workflows tab`, `Shape B`, `FeatureFlag`, `is_feature_enabled` / `useFeatureFlag`, `Design System (Soft Maximalism)`. File renamed `KEN-E-Agentic-Harness-Design.md` → `KEN-E-System-Architecture.md` with cross-references updated in 21 files. |
| 3.2 | 2026-04-20 | Development Team | Restructured §8 to cover persistent orchestration. Renamed from "Workflow Management" → "Multi-Step Orchestration" with two clean subsections: §8.1 in-session multi-step workflows (unchanged — ADK ParallelAgent + LoopAgent composition, pointer to review-loop-implementation-plan.md) and §8.2 Project Plans & Task Orchestration (new — frames the project-tasks component as the persistent cross-session orchestration layer: `ProjectPlan` / `PlanTask` data model, `TaskOrchestrator` convergence point, event-driven + time-based triggers, factory-built planning specialist). Added §8.3 Automations & System-Triggered Plans describing how Automations (PlanRun on top of ProjectPlan) and the KG session-end automation both build on §8.2. Deleted the stale §8.2 workflow state machine, §8.3 `workflows/{workflow_id}` data model, §8.4 persistence & recovery — all superseded by project-tasks. Deleted §8.5 n8n integration entirely — Automations replaces it; n8n may return as an MCP tool for user-owned external workflows but not as an orchestration replacement. Added glossary entries for `ProjectPlan`/`PlanTask`, `TaskOrchestrator`, `is_system`, time-based scheduler, `PlanRun`. Updated Table of Contents. |
| 3.1 | 2026-04-20 | Development Team | Context management alignment with Knowledge Graph component. Renamed §3.2 "Hierarchical Context Loading" → "Knowledge Base Reads" — kept the session-start executive summary (unchanged) and replaced L2/L3 HCL levels with the four orchestrator read tools owned by KG-PRD-03 (`load_context_section`, `load_document`, `search_kb`, `list_observations`). Replaced §3.3 "Context Loading Implementation" with a new §3.3 "Learning Loop" describing the provenance spine (KG-PRD-02) and session-end automation (KG-PRD-04). Updated §3.1 token table to reflect the session-start + per-turn KB-reads model. Added glossary entries for the four read tools, `Observation` / `Session (Neo4j)` / `ResearchRun`, session-end automation, `:KGNode`; reframed `HCL` as superseded. |
| 3.0 | 2026-04-20 | Development Team | Major alignment + simplification pass. Reframed as high-level product/architecture vision with detailed content delegated to component docs. Collapsed §1.3 (deleted current-state snapshot and broad-specialist target diagram); updated §1.4 key decisions to reflect narrow per-platform specialists, curated ≤30-tool rosters, description-based routing. Replaced §2 (Architecture Overview) with pointers to agentic-harness README. Kept §2.1 Agent Type Selection. §3 (Context Management) retained; §3.6.2 marked `tool_filter_state` as retired and added review-loop `{prefix}_draft`/`{prefix}_feedback` keys. §4 reduced from six subsections to just §4.1 Tool Type Taxonomy + pointers; deleted §4.1 tree, §4.2 root-agent code, §4.3 Tool Discovery, §4.4 specialist catalog, §4.5 agent table, §4.6 review-loop detail. §5 collapsed to a summary paragraph pointing at mcp-architecture.md. §6 Skills collapsed to pointer at Skills component. §7 Multi-Channel collapsed to pointer at api-gateway-multi-channel.md. §8 Workflow Management: deleted §8.1–§8.4 (~317 lines of multi-step pattern, factory code, pitfalls, cost tables) — all now consolidated in review-loop-implementation-plan.md; kept and renumbered §8.2 state machine, §8.3 data model (replaced specialist enum with `specialist_config_id`), §8.4 persistence, §8.5 n8n. §9–§11 retained; minor stale-reference fixes (tool_filter → curated roster in §10.2; multi-tenant credential keys in §11.2.3 updated for narrow specialists). §12 Sprint Roadmap collapsed to pointer at product-roadmap.md. Appendix A and C collapsed to pointers at mcp-architecture / AH-PRD-02. Appendix D glossary: marked `tool_filter` as retired, updated ToolRegistry definition, added Specialist and Review Loop entries, removed agent-hierarchy.md references. Net result: ~1,862 → ~530 lines. |

---

*This document describes the architecture for the KEN-E agentic harness. It is updated as implementation progresses.*
