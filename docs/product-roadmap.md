# KEN-E Product Roadmap

**Version:** 1.0 — Draft for Team Review
**Date:** 2026-03-18
**Status:** DRAFT — Pending team review and approval

---

## Table of Contents

- [Context](#context)
- [Current State](#current-state)
- [Guiding Principles](#guiding-principles)
- [Release Overview](#release-overview)
- [Dependency Graph](#dependency-graph)
- [Release 1.1: Foundation Hardening](#release-11-foundation-hardening)
- [Release 2.0: Intelligent Analytics](#release-20-intelligent-analytics)
- [Release 3.0: Content & Campaigns](#release-30-content--campaigns)
- [Release 4.0: Automation & Quality Feedback](#release-40-automation--quality-feedback)
- [Release 5.0: Multi-Channel & Self-Improvement](#release-50-multi-channel--self-improvement)
- [Release 6.0: Voice & Enterprise](#release-60-voice--enterprise)
- [Timeline Summary](#timeline-summary)
- [Risk Register](#risk-register)
- [Open Questions for Team Discussion](#open-questions-for-team-discussion)

---

## Context

KEN-E is a multi-agent AI marketing system built on Google Cloud Platform. Release 1.0 is live in production with core chat capabilities. Sprint 3b (agent config optimization) is on a feature branch, pending merge. This roadmap defines incremental production releases, each delivering a small set of reliable, well-tested features that build on one another.

### Key Design Documents

| Document | Purpose |
|----------|---------|
| `docs/KEN-E-Agentic-Harness-Design.md` | Root architecture — agents, context, tools, sessions, workflows |
| `docs/design/agent-hierarchy.md` | Agent tree, dispatch, specialist layer, agent factory |
| `docs/design/mcp-architecture.md` | MCP integration, platform decisions, token budget, tool_filter |
| `docs/design/review-loop-implementation-plan.md` | Review loop phases, ADK patterns, cost analysis |
| `docs/design/data-visualization.md` | Vega-Lite artifacts, create_visualization tool, rendering |
| `docs/design/api-gateway-multi-channel.md` | API layer, Slack, Voice channel designs |
| `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` | MER-E evaluation framework |
| `docs/trace-structure-spec.md` | W&B Weave span structure contract |

---

## Current State

### What is live in production (Release 1.0)

- KEN-E Root Agent (ADK/LangGraph orchestration)
- Strategy Supervisor (CrewAI multi-agent: business, brand, competitive strategy)
- Company News Agent (transitional — will be replaced by skill + specialist)
- Google Analytics Agent (transitional — will be replaced by Analytics Specialist)
- FastAPI API with 40+ endpoints (knowledge graph CRUD, accounts, OAuth, monitoring)
- React frontend (chat, knowledge base editors, analytics, strategy, admin, agent config)
- Firebase authentication, Firestore, Neo4j, BigQuery
- Weave SDK tracing (basic span hierarchy)
- CI/CD pipelines (GitHub Actions) + Terraform infrastructure

### What is on Sprint 3b branch (pending merge)

- **Agent Registry**: Centralized source of truth for 13 agents, API allowlist derivation
- **InstructionProvider pattern**: Dynamic system instructions from session state (~1,500 token savings per message)
- **Events Compaction**: Token threshold (50K) + event retention (10) configuration
- **Context optimization**: Shared ORG_CONTEXT_QUERY, deduplicated context loaders
- **ReflectAndRetryToolPlugin**: Retry logic for tool failures

---

## Guiding Principles

1. **Each release is production-deployable** — small scope, high reliability, well-tested
2. **Dependencies drive ordering** — review loops before specialists, specialists before workflows
3. **MER-E evaluation runs as a parallel track** — quality signal from Release 2.0 onward
4. **Analytics Specialist first** — highest customer value, validates the specialist pattern before scaling to other domains
5. **Incremental complexity** — single-step review loops before multi-step workflows, predefined skills before custom skills

---

## Release Overview

| Release | Theme | Sprints | Est. Points | Cumulative Capability |
|---------|-------|---------|-------------|----------------------|
| **1.1** | Foundation Hardening | 2 | ~104 | Optimized agent config, context compression, stable tracing, config registry |
| **2.0** | Intelligent Analytics | 4 | ~248 | Review loops, Analytics Specialist, data viz, basic evaluation |
| **3.0** | Content & Campaigns | 4 | ~244 | Content + Execution Specialists, predefined skills, multi-step workflows |
| **4.0** | Automation & Quality Feedback | 3 | ~180 | Automation Specialist, n8n, custom skills, MER-E scoring + patterns |
| **5.0** | Multi-Channel & Self-Improvement | 3 | ~174 | Slack, MER-E prompt optimization, workflow templates |
| **6.0** | Voice & Enterprise | TBD | TBD | Voice channel, enterprise integrations, multi-tenant |

**Velocity assumption:** ~60 story points per 2-week sprint.

---

## Dependency Graph

```
R1.1  Sprint 3b Merge + Firestore Config Registry
 │
 ├──► R2.0  Review Loop Framework ─────────────► All specialist review loops
 │     │
 │     ├──► R2.0  Agent Factory ───────────────► All specialist assembly
 │     │     │
 │     │     └──► R2.0  Analytics Specialist ──► First specialist validates pattern
 │     │          │
 │     │          └──► R2.0  Data Visualization
 │     │
 │     └──► R2.0  MER-E Phase 0 (extraction) ─► Quality signal from day 1
 │
 ├──► R3.0  Content Specialist ────────────────► Content creation pipeline
 ├──► R3.0  Execution Specialist ──────────────► Campaign deployment
 ├──► R3.0  Predefined Skills ─────────────────► Procedural knowledge
 ├──► R3.0  Multi-Step Workflows ──────────────► Complex orchestration
 │     │
 │     └──► R3.0  MER-E Phase 1 (scoring) ────► Quality measurement
 │
 ├──► R4.0  Automation Specialist + n8n ───────► Scheduled workflows
 ├──► R4.0  Custom Skills ─────────────────────► User-created expertise
 │     │
 │     └──► R4.0  MER-E Phase 2 (feedback) ───► Human-in-the-loop quality
 │
 ├──► R5.0  Slack Channel ─────────────────────► Multi-channel reach
 │     │
 │     └──► R5.0  MER-E Phase 3 (optimization) ► Prompt improvement loop
 │
 └──► R6.0  Voice Channel ─────────────────────► Meeting participation
```

---

## Release 1.1: Foundation Hardening

**Goal:** Merge Sprint 3b, pass Release 1 optimization gates, and prepare the infrastructure foundation (Firestore config registry) that all specialist agents will depend on.

**Duration:** 2 sprints (4 weeks)
**Estimated Points:** ~104

### Sprint 1

#### Feature 1.1.1: Agent Config Optimization (Sprint 3b Merge)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 1.1.1-1 | Merge Agent Registry | 5 | Centralized source of truth for 13 agents, API allowlist derivation |
| 1.1.1-2 | Merge InstructionProvider pattern | 8 | Dynamic system instructions from session state, eliminates per-message context injection (~1,500 token savings/message) |
| 1.1.1-3 | Merge Events Compaction | 5 | Token threshold compaction (50K tokens), event retention config (10 events) |
| 1.1.1-4 | Merge context optimization | 5 | Shared ORG_CONTEXT_QUERY, deduplicated context loaders |
| 1.1.1-5 | Regression testing | 8 | Validate all existing functionality against Sprint 3b changes |

#### Feature 1.1.2: Tracing Hardening

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 1.1.2-1 | Trace compliance validation | 8 | Validate required span attributes (agent_id, agent_version, account_id, session_id) per trace-structure-spec.md |
| 1.1.2-2 | Trace metadata completeness audit | 5 | Ensure L1-L3 spans carry all required fields; defaults applied for optional fields |

**Sprint 1 Subtotal: ~44 points**

### Sprint 2

#### Feature 1.1.3: Release 1 Optimization Gates

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 1.1.3-1 | Quality gates validation | 8 | Run 16 quality gates from Release-1-Optimization-Strategy.md |
| 1.1.3-2 | Performance gates validation | 8 | Run 10 performance gates (latency, token budget, session recovery) |
| 1.1.3-3 | Fix gate failures | 13 | Buffer for addressing any gate failures discovered |
| 1.1.3-4 | Production deployment + monitoring | 5 | Deploy R1.1, monitor for 48hrs, validate stability |

#### Feature 1.1.4: Firestore Config Registry (Preparation for Agent Factory)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 1.1.4-1 | Design Firestore schema for agent configs | 5 | Schema for `agents/{id}` and `mcp_servers/{id}` collections |
| 1.1.4-2 | Migrate existing agent config to Firestore | 8 | Move hardcoded agent configs to Firestore documents |
| 1.1.4-3 | Config read/write API endpoints | 8 | CRUD endpoints for agent and MCP server configurations |

**Sprint 2 Subtotal: ~55 points**

### Release 1.1 Exit Criteria

- [ ] All Release 1 optimization gates (quality + performance) pass
- [ ] Sprint 3b merged to main and deployed to production
- [ ] Firestore config registry populated with current agent + MCP server configs
- [ ] Trace compliance validation passing on production traces
- [ ] No regressions in existing chat, knowledge graph, or strategy flows

---

## Release 2.0: Intelligent Analytics

**Goal:** Introduce the specialist agent pattern with Analytics Specialist, review loops for quality assurance, data visualization capabilities, and foundational evaluation infrastructure (MER-E Phase 0).

**Duration:** 4 sprints (8 weeks)
**Estimated Points:** ~248

### Sprint 3

#### Feature 2.1: Review Loop Framework

The core building block for all specialist agents. Must be implemented first.

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.1-1 | `build_review_pipeline()` factory function | 13 | LoopAgent with specialist + reviewer sub-agents, output_key extraction, max_iterations=3. Specialist and reviewer are direct LoopAgent sub-agents (not wrapped in SequentialAgent — SequentialAgent swallows the `escalate` signal from exit_loop). |
| 2.1-2 | `exit_loop` integration and termination logic | 8 | Reviewer calls `exit_loop` when all acceptance criteria met; writes feedback to `{step_N_feedback}` on rejection |
| 2.1-3 | Reviewer agent template with `include_contents='none'` | 5 | Reviewer evaluates only the injected draft via template variable, not full conversation history |
| 2.1-4 | Acceptance criteria parameter passing | 5 | Root Agent generates criteria before dispatching; passes to specialist via `{acceptance_criteria}` template variable |
| 2.1-5 | Review loop unit tests | 8 | Test pipeline construction, iteration logic, termination conditions, output_key extraction |
| 2.1-6 | Review loop integration test | 8 | End-to-end test with mock specialist + reviewer agents |

#### Feature 2.2: Agent Factory — Phase 1

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.2-1 | Config-driven agent constructor | 13 | Read Firestore config → assemble LlmAgent (instruction, model, temperature, description, code_execution_enabled) |

**Sprint 3 Subtotal: ~60 points**

### Sprint 4

#### Feature 2.2: Agent Factory — Phase 2

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.2-2 | McpToolset creation from config | 8 | Create McpToolset instances per MCP server config with SseConnectionParams |
| 2.2-3 | Header Provider Factory | 8 | Map auth_type → session state credential key (ga_oauth → ga_credentials, etc.) |
| 2.2-4 | ToolRegistry integration with tool_filter | 13 | `before_agent_callback` runs ToolRegistry search → writes `tool_filter_state` to session state; `tool_filter` lambda reads state and exposes only matching tools |
| 2.2-5 | Dispatch function generation | 8 | Generate root agent dispatch functions from specialist configs |
| 2.2-6 | Agent factory unit + integration tests | 8 | Test assembly pipeline, config validation, tool_filter behavior |

#### Feature 2.3: Analytics Specialist — Phase 1

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.3-1 | Analytics Specialist agent definition | 8 | LlmAgent with analytics instruction, GA4 MCP toolset, Gemini code execution via GenerateContentConfig |
| 2.3-2 | Deprecate transitional GA Agent | 5 | Route analytics queries to new specialist, mark old agent as deprecated in registry |

**Sprint 4 Subtotal: ~58 points**

### Sprint 5

#### Feature 2.3: Analytics Specialist — Phase 2

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.3-3 | Analytics review loop integration | 8 | Wire Analytics Specialist into `build_review_pipeline()` with analytics-specific acceptance criteria |
| 2.3-4 | Gemini code execution for data analysis | 8 | Enable built-in code execution capability, test computational correctness of analysis outputs |
| 2.3-5 | Analytics Specialist E2E tests | 8 | Full query → analysis → review → approved output flow |

#### Feature 2.4: Data Visualization — Phase 1

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.4-1 | Artifact model (Vega-Lite) | 8 | Artifact BaseModel: type ("visualization"), spec (Vega-Lite JSON), metadata (chart_type_suggestion, title, data_source, description) |
| 2.4-2 | `create_visualization()` function tool | 8 | Writes to `response_artifacts` session state; params: chart_type, title, data (JSON), encoding (JSON), description |
| 2.4-3 | ChatResponse extension with artifacts | 5 | Add optional `artifacts: list[Artifact] \| None` field — backward-compatible, existing clients unaffected |
| 2.4-4 | Frontend Vega-Lite rendering | 13 | Render Vega-Lite specs inline in chat messages, agent-suggested chart type with frontend override |

**Sprint 5 Subtotal: ~58 points**

### Sprint 6

#### Feature 2.4: Data Visualization — Phase 2

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.4-5 | Review loop artifact evaluation | 8 | Reviewer evaluates text + artifacts together; `{step_N_artifacts?}` optional template variable |
| 2.4-6 | Data visualization E2E tests | 8 | Full analytics query → visualization → review → render flow |

#### Feature 2.5: MER-E Phase 0 — Trace Extraction (Parallel Track)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 2.5-1 | Output Extractor pipeline | 13 | Parse agent outputs into evaluatable items by category (analytics output types first; ~8 types) |
| 2.5-2 | Trace validation service | 8 | Compliance checking: required fields present (agent_id, agent_version, account_id, session_id), defaults applied for optional fields |
| 2.5-3 | Token usage visibility in UI | 8 | Surface token metrics to frontend: context percentage, running total, compaction warning |
| 2.5-4 | Evaluation data model (Firestore + BigQuery) | 8 | Schema for extracted outputs, evaluation results, aggregated metrics; 90-day raw trace retention, 1-year extraction retention |

**Sprint 6 Subtotal: ~53 points**

### Release 2.0 Exit Criteria

- [ ] Analytics Specialist handles all GA queries with review loop quality assurance
- [ ] Data visualizations (Vega-Lite charts) render correctly in chat
- [ ] Transitional GA Agent fully deprecated and removed
- [ ] Agent Factory assembles specialists from Firestore config
- [ ] tool_filter dynamically selects relevant tools per LLM turn
- [ ] Trace extraction pipeline running on production traces
- [ ] Token usage visible in UI
- [ ] Output extraction categorizing analytics outputs

---

## Release 3.0: Content & Campaigns

**Goal:** Enable the full content creation and campaign execution pipeline with Content + Execution Specialists, predefined skills for procedural knowledge, and multi-step workflow orchestration for complex marketing tasks.

**Duration:** 4 sprints (8 weeks)
**Estimated Points:** ~244

### Sprint 7

#### Feature 3.1: Content Specialist

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.1-1 | Content Specialist agent definition | 8 | LlmAgent with content instruction, HubSpot MCP (read-only CRM data for personalization) |
| 3.1-2 | Mailchimp SDK integration | 13 | Read + write operations via mailchimp-marketing SDK (audience data, campaign creation, email sends) |
| 3.1-3 | Content review loop (writer + editor) | 8 | Review pipeline with content-quality acceptance criteria (tone, accuracy, brand voice, CTA clarity) |
| 3.1-4 | Blog post generation flow | 8 | End-to-end: brief → draft → review loop → approved post |
| 3.1-5 | Email campaign generation flow | 8 | End-to-end: brief → email drafts (subject, body, CTA) → review loop → approved campaign |
| 3.1-6 | Content Specialist tests | 8 | Unit + integration tests for content generation and review flows |

**Sprint 7 Subtotal: ~53 points**

### Sprint 8

#### Feature 3.2: Execution Specialist

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.2-1 | Execution Specialist agent definition | 8 | LlmAgent with execution instruction, platform SDK tools for campaign deployment |
| 3.2-2 | Meta Ads SDK integration (facebook-business) | 13 | Full CRUD: campaigns, ad sets, ads, budget management, performance reads |
| 3.2-3 | Google Ads hybrid integration | 13 | MCP for read-only queries (shared with Analytics) + SDK function tools for writes (campaign CRUD, budget changes) |
| 3.2-4 | Execution review loop (executor + verifier) | 8 | Review pipeline with deployment-safety acceptance criteria (budget limits, targeting validation, compliance) |
| 3.2-5 | Execution Specialist tests | 8 | Unit + integration tests; mock platform APIs for safe testing |

**Sprint 8 Subtotal: ~50 points**

### Sprint 9

#### Feature 3.3: Predefined Skills

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.3-1 | Skills architecture (L1/L2/L3 progressive disclosure) | 8 | L1: metadata (~50-100 tokens, loaded at startup), L2: instructions (<5,000 tokens, on-demand), L3: resources (variable, on-demand) |
| 3.3-2 | Bundle 6 predefined skills | 13 | analyze-campaign-performance, generate-marketing-report, competitor-analysis, optimize-ad-spend, create-email-campaign, research-company-news |
| 3.3-3 | SkillToolset integration with agent factory | 8 | Load predefined skills during agent assembly, attach to appropriate specialist agents |
| 3.3-4 | Company News Agent transition | 5 | Replace transitional agent with research-company-news skill + appropriate specialist routing |
| 3.3-5 | Skills unit + integration tests | 8 | Test progressive loading, skill execution, specialist attachment |

#### Feature 3.4: Multi-Step Workflows — Phase 1

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.4-1 | `build_workflow_pipeline()` factory | 13 | Compose ParallelAgent + SequentialAgent from step definitions with dependency graph |
| 3.4-2 | Synthesizer pattern | 5 | LlmAgent with `include_contents='none'` + strong instruction framing injected data as "completed research" |

**Sprint 9 Subtotal: ~60 points**

### Sprint 10

#### Feature 3.4: Multi-Step Workflows — Phase 2

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.4-3 | `execute_workflow()` tool for Root Agent | 8 | Root Agent decomposes user request into steps with acceptance criteria and dependency graph |
| 3.4-4 | Approval checkpoints | 8 | Conversation-turn based user approval between workflow phases (no pause/resume framework needed) |
| 3.4-5 | Workflow state persistence (Firestore) | 8 | `workflows/{workflow_id}`: step status, inputs/outputs, attempt count; idempotency keyed by (workflow_id, step_id, attempt) |
| 3.4-6 | Workflow instruction update for Root Agent | 5 | Root Agent instruction includes guidance for workflow decomposition and step planning |
| 3.4-7 | Multi-step workflow E2E test | 13 | Full parallel data gathering → synthesis → user approval → execution flow |

#### Feature 3.5: MER-E Phase 1 — Quality Scoring (Parallel Track)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 3.5-1 | LLM-based quality scorer | 13 | Factor-level scoring: completeness, accuracy, actionability, domain relevance, clarity |
| 3.5-2 | Expand output extraction to Content + Execution types | 5 | Add ~16 new output types for content and execution specialist categories |

**Sprint 10 Subtotal: ~60 points**

### Release 3.0 Exit Criteria

- [ ] Content Specialist generates blog posts and email campaigns with review loop quality assurance
- [ ] Execution Specialist deploys campaigns to Meta Ads and Google Ads with safety review
- [ ] 6 predefined skills available and functional across specialist agents
- [ ] Company News Agent fully transitioned to skill + specialist
- [ ] Multi-step workflows execute with parallel phases, synthesis, and user approval checkpoints
- [ ] Workflow state persisted in Firestore with idempotent step execution
- [ ] MER-E quality scoring running on production outputs across all 3 specialist categories

---

## Release 4.0: Automation & Quality Feedback

**Goal:** Enable scheduled and recurring workflows via n8n, allow users to create custom skills, and close the evaluation feedback loop with human ratings, pattern detection, and A/B testing.

**Duration:** 3 sprints (6 weeks)
**Estimated Points:** ~180

### Sprint 11

#### Feature 4.1: Automation Specialist + n8n

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.1-1 | Automation Specialist agent definition | 8 | LlmAgent with automation instruction, n8n MCP server |
| 4.1-2 | n8n webhook integration | 13 | `POST /api/v1/workflows/{id}/execute` endpoint, n8n cron triggers, per-account isolation |
| 4.1-3 | Scheduled workflow execution | 13 | n8n cron → webhook → KEN-E workflow execution, service account authentication |
| 4.1-4 | Failure notifications | 5 | Alert on workflow execution failures (configurable notification channel) |
| 4.1-5 | Automation Specialist tests | 8 | Unit + integration tests for n8n flows and scheduled execution |

#### Feature 4.2: Custom Skills — Phase 1

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.2-1 | Skill builder UI | 13 | Frontend interface for creating, editing, and managing custom skills |

**Sprint 11 Subtotal: ~60 points**

### Sprint 12

#### Feature 4.2: Custom Skills — Phase 2

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.2-2 | GCS + Firestore per-org skill storage | 8 | `gs://ken-e-skills/{org_id}/{skill_name}/SKILL.md` + Firestore metadata per organization |
| 4.2-3 | Skill validation framework | 8 | Validate skill structure, instruction size limits, resource references, naming conventions |
| 4.2-4 | Custom skill loading via SkillToolset | 5 | Load org-specific custom skills during agent factory assembly alongside predefined skills |
| 4.2-5 | Custom skills tests | 8 | Unit + integration tests for CRUD, validation, loading, and per-org isolation |

#### Feature 4.3: MER-E Phase 2 — Human Feedback + Patterns (Parallel Track, Phase 1)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.3-1 | Human feedback collection UI | 13 | 1-5 star ratings, factor-level scores, queue feedback requests post-output |
| 4.3-2 | Feedback storage + alignment analysis trigger | 8 | Firestore storage; trigger LLM vs. human alignment analysis when sufficient data collected |

**Sprint 12 Subtotal: ~50 points**

### Sprint 13

#### Feature 4.3: MER-E Phase 2 — Human Feedback + Patterns (Parallel Track, Phase 2)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.3-3 | Pattern detection engine | 13 | Detect: consistency issues, hallucination signals, structural problems, length anomalies, repetitive content |
| 4.3-4 | LLM vs. human scoring calibration | 8 | Disagreement analysis between LLM scores and human ratings to identify scoring blind spots |
| 4.3-5 | MER-E evaluation dashboard | 13 | Visualize quality scores, patterns, trends over time; per-agent and per-specialist breakdowns |

#### Feature 4.4: A/B Testing Infrastructure

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 4.4-1 | Variant assignment (consistent hash per account) | 8 | Firestore variant configs, `experiment_id` / `variant_name` in trace metadata |
| 4.4-2 | Experiment tracking + reporting | 8 | Compare metrics between variants; statistical significance indicators |

**Sprint 13 Subtotal: ~50 points**

### Release 4.0 Exit Criteria

- [ ] Automation Specialist executes scheduled workflows via n8n cron triggers
- [ ] n8n webhook integration functional with per-account isolation
- [ ] Users can create, edit, and use custom skills via UI
- [ ] Custom skills stored per-org in GCS + Firestore
- [ ] Human feedback collected and stored from production users
- [ ] Pattern detection identifying systematic quality issues across specialists
- [ ] A/B testing infrastructure operational with consistent variant assignment
- [ ] MER-E dashboard showing quality trends

---

## Release 5.0: Multi-Channel & Self-Improvement

**Goal:** Extend KEN-E beyond the web UI to Slack, close the MER-E prompt optimization loop for continuous agent improvement, and provide pre-built workflow templates for common marketing tasks.

**Duration:** 3 sprints (6 weeks)
**Estimated Points:** ~174

### Sprint 14

#### Feature 5.1: Slack Channel

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 5.1-1 | Slack Bolt SDK service (separate Cloud Run) | 13 | Event handling, message routing, thread-based conversation mapping to KEN-E sessions |
| 5.1-2 | Slack auth adapter | 8 | OAuth flow for workspace installation, Slack user → KEN-E user mapping |
| 5.1-3 | Block Kit message formatting | 8 | Rich message rendering; charts rendered server-side to PNG via vega-lite-to-png |
| 5.1-4 | Slack channel integration tests | 8 | End-to-end message flow through Slack adapter to agent and back |

#### Feature 5.2: MER-E Phase 3 — Prompt Optimization (Phase 1)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 5.2-1 | Disagreement analysis pipeline | 13 | Identify cases where human and LLM quality scores diverge; analyze root causes |
| 5.2-2 | Prompt revision generator | 8 | Generate specific prompt text changes based on disagreement patterns |

**Sprint 14 Subtotal: ~58 points**

### Sprint 15

#### Feature 5.2: MER-E Phase 3 — Prompt Optimization (Phase 2)

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 5.2-3 | Canary deployment pipeline | 13 | Deploy revised prompts to configurable % of traffic; monitor quality metrics |
| 5.2-4 | Staged rollout with rollback gates | 8 | Progressive rollout with automatic rollback on quality degradation below threshold |

#### Feature 5.3: Workflow Templates

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 5.3-1 | Keyword analysis workflow template | 8 | Pre-built: data collection → analysis → recommendation report (maps to User Story Scenario 1) |
| 5.3-2 | Campaign creation workflow template | 8 | Pre-built: brief → content generation (parallel) → review → deployment (maps to User Story Scenario 2) |
| 5.3-3 | Performance report workflow template | 8 | Pre-built: data retrieval → analysis → insight generation |
| 5.3-4 | Workflow type weight configuration | 5 | Configure step weights per workflow type for MER-E evaluation scoring |

**Sprint 15 Subtotal: ~50 points**

### Sprint 16

#### Feature 5.4: Advanced Workflow & Observability

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 5.4-1 | Workflow step-level evaluation (MER-E integration) | 13 | Per-step quality scoring, workflow trajectory evaluation, dependency satisfaction analysis |
| 5.4-2 | Weave trace integration for workflows | 8 | Progress indicators in UI, step-level observability in Weave |
| 5.4-3 | Notification preferences (in-app, Slack, email) | 8 | User-configurable notification channels for workflow events and completion |
| 5.4-4 | Release 5.0 stabilization + cross-channel E2E testing | 13 | Validate same agent behavior across Web UI and Slack; workflow template testing |

**Sprint 16 Subtotal: ~42 points**

### Release 5.0 Exit Criteria

- [ ] Slack bot functional with thread-based conversations and Block Kit formatting
- [ ] Charts render as PNG in Slack messages
- [ ] MER-E prompt optimization loop operational: disagreement analysis → revision → canary → rollout
- [ ] Automatic rollback triggers on quality degradation
- [ ] 3 workflow templates available (keyword analysis, campaign creation, performance report)
- [ ] Notification preferences configurable per user (in-app, Slack, email)
- [ ] Step-level workflow observability in Weave traces

---

## Release 6.0: Voice & Enterprise

**Goal:** Enable KEN-E to participate in voice meetings and provide enterprise-grade multi-tenant features.

**Status:** Future — scope to be detailed closer to implementation based on learnings from Releases 1-5.

**Duration:** TBD
**Estimated Points:** TBD

### Feature 6.1: Voice Channel

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 6.1-1 | Pipecat orchestration framework | TBD | Voice pipeline: STT → agent → TTS |
| 6.1-2 | Deepgram STT integration | TBD | Sub-300ms speech-to-text |
| 6.1-3 | Cartesia/Deepgram TTS | TBD | Text-to-speech for agent responses |
| 6.1-4 | Meeting BaaS integration (Recall.ai) | TBD | Bot joins Zoom/Teams calls |
| 6.1-5 | Meeting transcript + decision recording | TBD | Record team acceptance/rejection of theories and recommendations |

**Known Risk:** Agent Engine latency (7-13s) is incompatible with voice target (<2s). May require a separate lightweight agent path or different serving strategy. This needs a spike before detailed planning.

### Feature 6.2: Enterprise Integrations

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 6.2-1 | Jira task automation | TBD | Post-meeting action items → Jira tickets with assignees |
| 6.2-2 | Notion integration | TBD | Task sync and project management integration |
| 6.2-3 | Multi-tenant scaling | TBD | Per-account MCP server sets, advanced RBAC for team collaboration |

### Feature 6.3: MER-E Phase 4 — Full Closed Loop

| ID | Story | Points | Description |
|----|-------|--------|-------------|
| 6.3-1 | Automated prompt improvement deployment | TBD | Fully autonomous improvement cycle with human oversight |
| 6.3-2 | Cross-workflow quality optimization | TBD | Optimize multi-step workflow patterns based on outcome data |
| 6.3-3 | Multi-agent coordination scoring | TBD | Evaluate inter-agent collaboration quality |

---

## Timeline Summary

| Release | Sprints | Duration | Est. Points | Key Deliverable |
|---------|---------|----------|-------------|-----------------|
| **1.1** | 2 | 4 weeks | ~104 | Sprint 3b merged, config registry, tracing hardened |
| **2.0** | 4 | 8 weeks | ~248 | Analytics Specialist + review loops + data viz + MER-E extraction |
| **3.0** | 4 | 8 weeks | ~244 | Content + Execution Specialists + skills + workflows + MER-E scoring |
| **4.0** | 3 | 6 weeks | ~180 | Automation + n8n + custom skills + MER-E feedback + A/B testing |
| **5.0** | 3 | 6 weeks | ~174 | Slack + MER-E optimization + workflow templates |
| **6.0** | TBD | TBD | TBD | Voice + enterprise |
| **Total (R1.1–R5.0)** | **16** | **~32 weeks** | **~950 pts** | Full platform excluding voice |

**Estimated end-to-end timeline through Release 5.0: ~8 months from start of R1.1**

---

## Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|-----------|------------|
| 1 | **Review loop latency increase** | Medium | High | Cap max_iterations=3 (~15s overhead max). Root Agent skips criteria for simple lookups. |
| 2 | **Token cost increase from review loops** | Medium | High | Reviewer uses cheapest model. Criteria generation ~200 tokens. Monitor via Weave. |
| 3 | **LLM generates poor acceptance criteria** | Medium | Medium | Include good/bad criteria examples in Root Agent instruction. Iterate based on Weave traces. |
| 4 | **State collisions in parallel workflow execution** | High | Low | Unique `output_key` prefix per step enforced by `build_workflow_pipeline()` factory. |
| 5 | **Artifact size bloats review context** | Low | Medium | Limit embedded data to summaries. Defer raw data to separate `data_uri` if >1,000 rows. |
| 6 | **Voice latency incompatible with Agent Engine** | High | High | Agent Engine ~7-13s vs. voice <2s target. Requires spike before R6.0 planning. May need separate serving strategy. |
| 7 | **Platform SDK breaking changes (Meta, Google Ads)** | Medium | Medium | Pin SDK versions. Integration tests catch regressions. Budget buffer in Execution Specialist sprint. |
| 8 | **MER-E evaluation of a moving target** | Medium | Medium | Parallel track design means extraction/scoring evolves with agents. Output type expansion story in each MER-E phase. |
| 9 | **ADK version dependency** | Low | Medium | Current >=1.23.0; bump to >=1.26.0 for per-invocation tool caching fix. Test thoroughly before upgrade. |
| 10 | **OTEL Pydantic serialization bug** | Low | Low | OTEL disabled (OTEL_SDK_DISABLED=true). Expected fix in ADK >=1.23.0. Re-enable when available. |

---

## Open Questions for Team Discussion

1. **Sprint numbering:** Continue from existing project numbering (Sprint 4, 5, 6...) or reset per release (R2.0-S1, R2.0-S2...)? This document uses sequential numbering from Sprint 1 for clarity.

2. **Release 1.1 scope:** Is the Sprint 3b merge + optimization gates truly ready, or are there known blockers that should be addressed before we commit to a 2-sprint timeline?

3. **Agent Factory complexity:** The config-driven agent assembly (Feature 2.2) is architecturally significant. Should we do a spike/prototype sprint before committing to the 2-sprint estimate?

4. **Platform SDK integrations (R3.0):** Meta Ads and Google Ads SDK integrations carry external dependency risk. Should we add a spike sprint for each, or is the team confident in the 1-sprint-per-specialist estimate?

5. **MER-E resourcing:** The parallel MER-E track adds ~2-3 stories per sprint. Is this sustainable with the current team, or should MER-E be a dedicated sub-team?

6. **Custom skills priority (R4.0):** Custom skills are valuable but complex (GCS storage, validation, UI builder). Could this be deferred to R5.0 if R4.0 timelines are tight?

7. **Slack urgency:** Slack is currently in R5.0. Are there customer commitments or business needs that require it sooner?

8. **Voice feasibility:** Given the Agent Engine latency gap (7-13s vs. <2s target), should we schedule a voice feasibility spike in R4.0 or R5.0 to de-risk R6.0 planning?

9. **Story point estimates:** All estimates in this document are preliminary. The team should re-estimate during sprint planning based on actual complexity assessment.

10. **Release cadence:** This plan assumes back-to-back releases. Should we add a stabilization sprint between releases for production hardening?
