# Release 1 Optimization Strategy

**Version:** 1.1
**Date:** February 20, 2026 (realigned 2026-04-21)
**Status:** Active — evaluation gates for Release 1.1 (Foundation Hardening)
**Purpose:** Comprehensive evaluation plan to ensure Release 1 delivers high-quality outputs and optimal performance before deployment to live users.

> **Status note (2026-04-21):** Release 1 has been re-scoped around the 15-component structure tracked in [`design/components/PROJECT-PLANNER.md`](design/components/PROJECT-PLANNER.md). The authoritative sections of this document are: §3 Quality Evaluation Plan (methodology), §4 Performance Evaluation Plan, §6 Test Environment Requirements, §7 Acceptance Criteria (G-Q/G-P gates), §8 Schedule. §2 has been rewritten to map to current Release 1 components. MER-E / evaluation-framework infrastructure work is no longer part of R1 — it now lives in MER-E Phases 0–2 and is owned by [`KEN-E-Self-Improving-Evaluation-Framework-Design.md`](KEN-E-Self-Improving-Evaluation-Framework-Design.md). The old DDP1-/NR1- scope IDs and Sprint 5c/6b story references have been removed from this document; they do not map to any current work.

---

## Table of Contents

1. [Evaluation Overview](#1-evaluation-overview)
2. [Scope Summary](#2-scope-summary)
3. [Quality Evaluation Plan](#3-quality-evaluation-plan)
4. [Performance Evaluation Plan](#4-performance-evaluation-plan)
5. [Evaluation Procedures by Feature Area](#5-evaluation-procedures-by-feature-area)
6. [Test Environment Requirements](#6-test-environment-requirements)
7. [Acceptance Criteria Summary](#7-acceptance-criteria-summary)
8. [Evaluation Schedule](#8-evaluation-schedule)

---

## 1. Evaluation Overview

### 1.1 Objectives

This document defines the evaluation strategy for Release 1 of KEN-E. The two priorities, in order, are:

1. **Quality** — Every agent produces accurate, relevant, and actionable outputs across all user scenarios.
2. **Speed** — The system responds within acceptable latency targets for each operation type.

### 1.2 Evaluation Philosophy

Release 1 is the first deployment to live users. Evaluation must cover the **user-facing agentic harness** (onboarding research, orchestrator routing, context loading, GA integration, tool discovery, session service, web channel) and the **R1.1 Foundation Hardening** features (ADK upgrade, tracing hardening, optimization gates, Firestore config registry, session-timeout removal). Tracing hardening (Feature 1.1.2) is the prerequisite that unblocks MER-E ingestion in R2.5 — in R1 we validate the trace contract holds, not the downstream evaluation pipeline.

### 1.3 Evaluation Types

| Type | Description | When |
|------|-------------|------|
| **Functional Testing** | Verify each feature works as specified | During development (per-story) |
| **Quality Assessment** | Evaluate agent output accuracy, relevance, and helpfulness | After feature integration |
| **Performance Benchmarking** | Measure latency, throughput, and resource usage | After feature integration |
| **End-to-End Scenario Testing** | Test complete user journeys across features | Pre-deployment |
| **Load Testing** | Verify system behavior under concurrent user load | Pre-deployment |

---

## 2. Scope Summary

Release 1 is the first deployment to live users. The evaluation covers two things: the **existing agentic harness capabilities** that users will exercise on day one, and the **Release 1.1 "Foundation Hardening" features** that make those capabilities ready for production.

### 2.1 Release 1.1 Foundation Hardening features (active development)

Source of truth: [`design/components/PROJECT-PLANNER.md`](design/components/PROJECT-PLANNER.md) for project sequencing; Linear for per-feature execution.

| Feature | Purpose | Design ref |
|---|---|---|
| 1.1.1 — ADK Upgrade | Move to ADK ≥ 1.26 for per-invocation tool caching + other fixes | Linear (the KEN-E team's tracked feature) |
| 1.1.2 — Tracing Hardening | Every agent call emits a trace with the required metadata fields (contract in `trace-structure-spec.md`) — enables MER-E ingestion starting in R2.5 | [trace-structure-spec §3, §10, §11](trace-structure-spec.md) |
| 1.1.3 — Release 1 Optimization Gates | The go/no-go checklist — **this document defines the gates** | §7 below |
| 1.1.4 — Firestore Config Registry | Agent configs live in Firestore; factory reads at deploy time | [AH-PRD-02 §4, §5.2](design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md), [mcp-architecture §6](design/components/agentic-harness/mcp-architecture.md#6-mcp-server-config-registry) |
| 1.1.5 — Remove Session Timeout | Session lifecycle aligned to ADK's invocation model | Linear (the KEN-E team's tracked feature) |

### 2.2 Existing harness capabilities evaluated by this plan

These capabilities are already implemented; R1.1 hardens them. The evaluation items in §3 and procedures in §5 target these surfaces directly.

| Capability | Evaluation coverage |
|---|---|
| Primary Orchestrator (KEN-E) routing + response quality | §3.2, §5.2 |
| Onboarding Research Pipeline (Strategy Specialist on account creation) | §3.1, §5.1 |
| Hierarchical Context Manager + Level 1/2/3 loading + budget compliance | §3.3, §5.4 |
| Google Analytics MCP integration | §3.4, §5.3 |
| Tool discovery + MCP Server Manager | §3.5, §5.5 |
| Session Service + context compression + multi-account isolation | §3.6, §5.6 |
| Web Channel Adapter (WebSocket, streaming, structured rendering) | §3.7, §5.7 |

### 2.3 Out of scope for this plan

The following were in the original (Feb 2026) scope but are no longer R1 work:

- **MER-E / evaluation framework infrastructure** (trace extractors, evaluation-results APIs, BigQuery tables, agreement-rate calculations). Now Features 2.5 / 3.5 / 4.3 — see [`KEN-E-Self-Improving-Evaluation-Framework-Design.md`](KEN-E-Self-Improving-Evaluation-Framework-Design.md).
- **Review loops, agent factory, specialist assembly** (R2.0 — see AH-PRD-01, AH-PRD-02, AH-PRD-03).
- **Multi-tenant data-model migration** (R1 foundation parallel track — see [`design/components/data-management/README.md`](design/components/data-management/README.md)).

These will get their own evaluation plans when those releases are cut.

---

## 3. Quality Evaluation Plan

Quality is the primary optimization target. Each section below defines what "high quality" means for that feature area and how to evaluate it. Execution of the plan (assigning individual Q-items to user stories in Linear) is tracked under the Release 1 Optimization Gates feature; this document defines **what** to evaluate, not which cycle owns each item.

### 3.1 Onboarding Research Pipeline Quality

The onboarding research pipeline is the user's first experience with KEN-E. When a user creates an account and provides their business information, the Strategy Specialist agent automatically conducts research on the user's company, competitors, ICPs, and market positioning. This research populates the Neo4j knowledge graph that KEN-E uses for all subsequent conversations.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-1.1 | Company overview accuracy | Factually correct; no hallucinated details; captures industry, size, and products accurately | Human review of 20+ generated overviews against actual company data |
| Q-1.2 | ICP relevance | Generated ICPs match the company's actual target market; pain points are realistic and specific | Marketing expert review; compare to known ICPs for recognizable companies |
| Q-1.3 | Competitor identification accuracy | Correct competitors identified; no irrelevant companies; competitive positioning is defensible | Cross-reference against industry databases and company websites |
| Q-1.4 | Research completeness | All expected knowledge graph sections populated (company overview, products, ICPs, competitors, strategies, brand guidelines) | Automated check of Neo4j graph completeness per account |
| Q-1.5 | Research depth | Level 2 and Level 3 context sections contain substantive, actionable detail — not shallow summaries | Human review: are Section summaries (~10k tokens) and Full details (~20k tokens) rich enough to inform strategy conversations? |
| Q-1.6 | Knowledge graph structure | Entities and relationships are correctly typed; no orphan nodes; graph is traversable for context loading | Automated graph integrity checks |
| Q-1.7 | Source citation quality | Research claims are traceable to real sources; URLs resolve; no fabricated citations | Automated link validation + human spot-check |

**Test Companies:**
- 5 well-known companies (verifiable ground truth)
- 5 mid-market companies (realistic user base)
- 5 small/niche businesses (edge cases)
- 2 brand-new companies with minimal web presence (stress test)

### 3.2 Primary Orchestrator (KEN-E) Quality

KEN-E is the main agent users interact with. Quality here means understanding user intent correctly, routing to the right specialist or tool, loading the right context, and delivering clear, tailored responses.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-2.1 | Intent classification accuracy | KEN-E correctly identifies user intent (strategy question vs analytics request vs general chat) | Run 100+ diverse prompts; measure classification accuracy against human-labeled ground truth |
| Q-2.2 | Context selection relevance | KEN-E loads the correct context sections for the user's question (e.g., loads [competitors] for competitive questions, not [calendar]) | Log which sections are loaded per query; human review of appropriateness |
| Q-2.3 | Response personalization | Responses reference the user's specific company data (not generic advice) | Human review: does the response mention the user's actual products, ICPs, competitors? |
| Q-2.4 | Response accuracy | Factual claims about the user's business are correct based on the loaded context | Compare response content to knowledge graph source data |
| Q-2.5 | Response actionability | Recommendations are specific and implementable, not vague platitudes | Marketing expert scoring on 1-5 actionability scale |
| Q-2.6 | Conversation coherence | Multi-turn conversations maintain thread; KEN-E remembers what was discussed | Run 10+ multi-turn scenario scripts (5-15 turns each); verify no context loss |
| Q-2.7 | Clarification behavior | KEN-E asks clarifying questions when requests are ambiguous rather than guessing | Test with 20+ deliberately ambiguous prompts |
| Q-2.8 | Error handling quality | When something fails (tool unavailable, context missing), KEN-E communicates clearly and suggests alternatives | Simulate failures; evaluate error response quality |
| Q-2.9 | Tone and brand consistency | KEN-E maintains consistent professional-yet-approachable marketing expert persona | Human review across diverse conversation types |

**Scenario Categories for Testing:**
1. **Strategy discussions** — "What should our Q2 marketing strategy focus on?"
2. **Competitive inquiries** — "How do we compare to [competitor]?"
3. **Content requests** — "Help me draft a blog post about [topic]"
4. **Analytics questions** — "What's our website traffic trend?"
5. **Multi-step tasks** — "Research our competitor landscape and create an ICP"
6. **Ambiguous requests** — "Help me with marketing"
7. **Out-of-scope requests** — "Write me Python code" (should gracefully redirect)
8. **Context-heavy requests** — Questions requiring Level 3 detail loading

### 3.3 Hierarchical Context Manager Quality

The context manager determines what company knowledge KEN-E has available for each conversation. Poor context loading = poor personalization.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-3.1 | Executive summary completeness (Level 1) | Always-loaded summary captures the essential company identity in ~5,000 tokens | Human review across test companies |
| Q-3.2 | Section summary quality (Level 2) | Loaded sections are substantive enough to answer section-level questions without needing Level 3 | Test: ask questions answerable from Level 2; verify correctness |
| Q-3.3 | Full detail quality (Level 3) | Detail pages contain comprehensive information for specialist tasks | Test: ask detail-specific questions; verify Level 3 data sufficiency |
| Q-3.4 | Context budget compliance | Total loaded context stays under 40,000 token budget at all times | Automated monitoring during all test scenarios |
| Q-3.5 | Section loading appropriateness | Only relevant sections are loaded; irrelevant sections are not loaded unnecessarily | Log analysis: review section load patterns across 100+ queries |
| Q-3.6 | Unloading behavior | Sections are properly unloaded when switching topics to free token budget | Multi-topic conversation tests; verify budget reclamation |

### 3.4 Google Analytics MCP Integration Quality

Users will ask KEN-E about their website analytics. KEN-E must correctly use the GA MCP server to run queries and interpret results.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-4.1 | Query construction accuracy | GA API queries correctly match the user's question (right metrics, dimensions, date ranges) | Run 30+ analytics questions; verify query parameters |
| Q-4.2 | Data interpretation accuracy | KEN-E correctly interprets GA data (e.g., doesn't confuse sessions with users, understands bounce rate meaning) | Human expert review of analytics explanations |
| Q-4.3 | Insight quality | KEN-E surfaces meaningful insights, not just raw numbers (trends, anomalies, actionable recommendations) | Marketing analyst scoring of insight depth |
| Q-4.4 | Error handling for GA queries | When GA returns no data or errors, KEN-E communicates clearly and suggests alternatives | Test with invalid date ranges, unavailable properties, etc. |
| Q-4.5 | Follow-up handling | KEN-E can drill deeper into analytics based on follow-up questions without re-querying unnecessarily | Multi-turn analytics conversation tests |
| Q-4.6 | Data accuracy relay | Numbers presented to the user match the actual GA API response (no rounding errors, no fabricated data) | Compare KEN-E's stated numbers to raw API responses |

**Test GA Scenarios:**
1. "What was our website traffic last month?"
2. "Which pages have the highest bounce rate?"
3. "Compare our organic vs paid traffic over the last quarter"
4. "What are our top acquisition channels?"
5. "Show me conversion trends for the past 6 months"
6. "How did our traffic change after we launched the new campaign?"

### 3.5 Tool Discovery & MCP Server Manager Quality

Tool discovery determines whether KEN-E finds the right tools for user requests. MCP server management determines whether those tools are available and functional.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-5.1 | Search relevance | Tool searches return the correct MCP server/tools for the query (>90% relevant results in top 5) | Run 50+ tool search queries across all categories; measure precision@5 |
| Q-5.2 | Keyword coverage | Common user phrasings map to correct tools (e.g., "email marketing" -> mailchimp_mcp, "SEO" -> data4seo_mcp) | Test with synonym and paraphrase variations |
| Q-5.3 | Server loading reliability | MCP servers connect successfully on first attempt (>99% success rate) | Automated load testing of each MCP server 100 times |
| Q-5.4 | LRU eviction correctness | When at capacity, the least-recently-used server is evicted (not an actively needed one) | Simulate capacity scenarios; verify correct eviction |
| Q-5.5 | Tool schema accuracy | Loaded tool schemas match actual API capabilities; no stale definitions | Compare loaded schemas to source-of-truth API docs |

### 3.6 Session Service Quality

Session persistence and state management ensure conversation continuity.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-6.1 | State persistence across reconnects | User reconnects to an existing session and conversation context is preserved | Simulate disconnection/reconnection; verify state continuity |
| Q-6.2 | Session isolation | Different users' sessions are completely isolated; no data leakage | Create concurrent sessions for different accounts; verify isolation |
| Q-6.3 | Context compression fidelity | When compression triggers, the summary preserves key decisions and facts from the conversation | Run long conversations; review compressed summaries for information loss |
| Q-6.4 | Session recovery | If the backend restarts mid-session, the user can resume without data loss | Simulate service restart during active session |

### 3.7 Web Channel Adapter Quality

The web UI is the user's primary interface.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-7.1 | Message delivery reliability | All user messages reach the orchestrator; all responses reach the user (no dropped messages) | Automated send/receive verification across 1000+ messages |
| Q-7.2 | Streaming behavior | Responses stream to the user token-by-token (not delayed until complete) | Measure time-to-first-token |
| Q-7.3 | Structured content rendering | Analytics charts, tables, and formatted outputs render correctly in the web UI | Visual inspection of all output types |
| Q-7.4 | Connection stability | WebSocket connection remains stable for 30+ minute sessions | Long-running session tests |
| Q-7.5 | Reconnection handling | If WebSocket drops, the client automatically reconnects and recovers state | Simulate network interruptions |

### 3.8 Trace compliance (tracing hardening — Feature 1.1.2)

Feature 1.1.2 — Tracing Hardening is the R1.1 item that makes every agent call emit a trace matching the contract in [`trace-structure-spec.md`](trace-structure-spec.md). This is a **prerequisite** for MER-E ingestion in R2.5 and later; in R1 we only validate that the contract holds.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method |
|---|----------------|-----------------|--------|
| Q-8.1 | Trace completeness | Every agent call produces a trace with all required metadata fields (agent_id, agent_version, account_id, session_id, model config, duration_ms) per `trace-structure-spec.md` §4, §10 | Run the compliance validator (`trace-structure-spec.md` §11) across every agent type on staging |
| Q-8.2 | Span naming conventions | Span names match the conventions in `trace-structure-spec.md` §3 (e.g., `ken_e.root`, `ken_e.specialist.{name}`, `ken_e.tool.{name}`) | Snapshot a diverse set of traces; diff against the convention table |

Full MER-E evaluation-retrieval / agreement-rate / extractor-quality work (previously Q-8.3–Q-8.8) is scoped to MER-E Phase 0 (trace extraction) and later, not Release 1. See [`KEN-E-Self-Improving-Evaluation-Framework-Design.md`](KEN-E-Self-Improving-Evaluation-Framework-Design.md).

---

## 4. Performance Evaluation Plan

Performance is the secondary optimization target. Latency directly affects user experience and perceived intelligence of the system.

### 4.1 Latency Targets

These targets are derived from the design document Section 10.3.

| Operation | Target | Acceptable | Critical (Requires Fix) |
|-----------|--------|------------|------------------------|
| **Account onboarding research** (full pipeline) | < 60s | < 120s | > 180s |
| **Session initialization** | < 500ms | < 1s | > 2s |
| **Executive summary load** (Level 1 context) | < 300ms | < 500ms | > 1s |
| **Section summary load** (Level 2 context) | < 300ms | < 500ms | > 1s |
| **Full detail load** (Level 3 context) | < 500ms | < 1s | > 2s |
| **Tool registry search** | < 200ms | < 500ms | > 1s |
| **MCP server connection** | < 500ms | < 1s | > 2s |
| **Simple agent response** (single-turn, no tool calls) | < 3s | < 5s | > 10s |
| **Complex agent response** (multi-tool, multi-step) | < 10s | < 20s | > 30s |
| **GA query + interpretation** | < 5s | < 10s | > 15s |
| **Context compression** | < 2s | < 5s | > 10s |
| **Workflow state save** | < 100ms | < 200ms | > 500ms |

### 4.2 Token Efficiency Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Initial context consumption (before conversation) | < 20% of 200k window (< 40k tokens) | Monitor token usage at session start |
| Tool registry index size | ~2,000 tokens | Measure index token count |
| Per-MCP-server token overhead | ~1,500 tokens average | Measure per loaded server |
| Context compression ratio | > 60% reduction when triggered | Compare pre/post compression token counts |
| Average tokens per simple response | < 2,000 tokens | Track across test scenarios |
| Average tokens per complex response | < 8,000 tokens | Track across test scenarios |

### 4.3 Throughput Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Concurrent active sessions | 100+ without degradation | Load test with simulated users |
| Messages per second (system-wide) | 50+ | Load test with concurrent conversations |
| MCP server connections per minute | 20+ | Concurrent tool loading test |

### 4.4 Performance Test Procedures

#### 4.4.1 Latency Profiling

For each operation in the latency targets table:
1. Run the operation 100 times under normal conditions.
2. Record p50, p90, p95, and p99 latency.
3. Flag any operations where p95 exceeds the "Acceptable" threshold.
4. For flagged operations, profile the code path to identify bottlenecks.

#### 4.4.2 Load Testing

Using the existing Locust test framework (`tests/load_test/`):
1. **Ramp-up test**: Gradually increase from 1 to 100 concurrent users over 10 minutes.
2. **Sustained load test**: Maintain 50 concurrent users for 30 minutes.
3. **Spike test**: Suddenly increase from 10 to 100 users; observe recovery.
4. **Endurance test**: Run 20 concurrent users for 2 hours to detect memory leaks or degradation.

Metrics to capture during load tests:
- Response latency distribution (p50, p90, p99)
- Error rate
- Memory usage over time
- CPU usage over time
- Neo4j query latency
- Firestore read/write latency
- MCP server connection pool utilization

#### 4.4.3 Token Budget Stress Test

Simulate worst-case token usage scenarios:
1. Load maximum context sections (all Level 2 + one Level 3).
2. Load maximum MCP servers (10 concurrent).
3. Run a 50-turn conversation with diverse topics.
4. Verify context compression triggers correctly.
5. Verify system remains functional after compression.
6. Measure final token usage vs budget.

---

## 5. Evaluation Procedures by Feature Area

### 5.1 Onboarding Research Pipeline

**Procedure:**
1. Create 17 test accounts (per the test company list in Section 3.1).
2. For each account, provide company name, website URL, and industry.
3. Trigger the onboarding research pipeline.
4. Wait for pipeline completion.
5. Export the generated knowledge graph for each account.
6. Have a marketing expert review each knowledge graph against the evaluation items in Section 3.1 (Q-1.1 through Q-1.7).
7. Score each evaluation item on a 1-5 scale.
8. Calculate aggregate quality scores.

**Pass Criteria:**
- Average score >= 4.0 across all evaluation items
- No individual account scores below 3.0 on any item
- 100% graph completeness (all expected sections populated)
- Research pipeline completes within latency target

### 5.2 Primary Orchestrator (KEN-E) Conversational Quality

**Procedure:**
1. Prepare a test script of 100+ prompts covering all scenario categories (Section 3.2).
2. Run each prompt against KEN-E using 3 different test accounts (to test personalization).
3. Log the full conversation including context loads, tool calls, and specialist delegations.
4. Have two evaluators independently score each response on evaluation items Q-2.1 through Q-2.9.
5. Calculate inter-rater agreement.
6. Identify systematic quality issues (patterns across multiple failures).

**Pass Criteria:**
- Intent classification accuracy >= 95%
- Response personalization score >= 4.0/5.0 average
- Response actionability score >= 3.5/5.0 average
- Zero instances of data leakage between accounts
- Clarification behavior triggers on >= 80% of ambiguous prompts

### 5.3 Google Analytics MCP Integration

**Procedure:**
1. Set up a test GA4 property with known data (or use a shared demo property).
2. Run the 6 test GA scenarios (Section 3.4) plus 24 additional analytics questions.
3. For each query, capture: the GA API request KEN-E generated, the raw API response, and KEN-E's interpretation presented to the user.
4. Verify query construction accuracy (correct metrics, dimensions, date ranges).
5. Verify data relay accuracy (numbers match raw response).
6. Have a marketing analyst score insight quality.

**Pass Criteria:**
- Query construction accuracy >= 90%
- Data relay accuracy = 100% (no fabricated numbers)
- Insight quality score >= 3.5/5.0 average
- Error handling passes all failure scenarios

### 5.4 Hierarchical Context Manager

**Procedure:**
1. For each of 5 test accounts, run the following sequence:
   a. Verify Level 1 loads automatically at session start.
   b. Ask a question requiring Level 2 context; verify correct section loads.
   c. Ask a question requiring Level 3 detail; verify correct detail loads.
   d. Switch to an unrelated topic; verify the previous sections are unloaded.
   e. Repeat topic-switching 10 times; verify budget compliance throughout.
2. Measure token usage at each step.
3. Verify correctness of loaded content against source data.

**Pass Criteria:**
- Context budget never exceeds 40,000 tokens
- Level 1 always loaded at session start
- Correct sections loaded >= 90% of the time
- Unloading works correctly for topic switches

### 5.5 Tool Discovery & MCP Server Manager

**Procedure:**
1. Prepare 50 tool search queries spanning all categories (analytics, ads, email, social, CMS, SEO, CRM, e-commerce).
2. Run each query and record the top 5 results.
3. Human evaluator marks each result as relevant or irrelevant.
4. Calculate precision@5 for each query.
5. For MCP server loading: connect and load each configured MCP server 100 times; record success rate and latency.
6. Test LRU eviction by loading servers to capacity and verifying correct eviction behavior.

**Pass Criteria:**
- Tool search precision@5 >= 90%
- MCP server connection success rate >= 99%
- MCP server load latency p95 < 1s
- LRU eviction always evicts the correct (least recently used) server

### 5.6 Session Service & Context Compression

**Procedure:**
1. Run 10 conversation scenarios of 30+ turns each.
2. Simulate disconnection at turn 15; reconnect and verify state.
3. Simulate backend restart at turn 20; reconnect and verify state.
4. For context compression: run conversations until compression triggers; review the summary for information preservation.
5. Run parallel sessions for different accounts; verify isolation.

**Pass Criteria:**
- State persists across 100% of reconnections
- State persists across 100% of backend restarts
- Compression summaries preserve key decisions (human review score >= 4.0/5.0)
- Zero cross-session data leakage

### 5.7 Web Channel Adapter

**Procedure:**
1. Automated message delivery test: send 1,000 messages; verify 1,000 responses received.
2. Measure time-to-first-token for 100 responses.
3. Test structured output rendering (tables, charts, formatted text) for each output type.
4. Run a 60-minute continuous session; monitor WebSocket stability.
5. Simulate 10 network interruptions; verify reconnection and state recovery.

**Pass Criteria:**
- Message delivery rate = 100%
- Time-to-first-token p95 < 1s
- All output types render correctly
- Zero dropped WebSocket connections in 60-minute test
- Reconnection succeeds within 5 seconds for all simulated drops

### 5.8 Trace Compliance (Feature 1.1.2)

**Procedure:**
1. **Trace completeness (Q-8.1):** Run each agent type on staging; run the compliance validator from `trace-structure-spec.md` §11.
2. **Span naming (Q-8.2):** Snapshot a representative set of traces; diff span names against the convention table in `trace-structure-spec.md` §3.

**Pass Criteria:**
- 100% trace compliance across all agent types per the validator
- All span names match the convention table
- Required metadata (agent_id, agent_version, account_id, session_id, model config, duration_ms) present on every top-level and tool span

---

## 6. Test Environment Requirements

### 6.1 Test Data Requirements

| Data Type | Requirement |
|-----------|-------------|
| **Test companies** | 17 companies (5 well-known, 5 mid-market, 5 niche, 2 brand-new) with verified ground truth data |
| **Test GA4 property** | GA4 property with 6+ months of known data for analytics testing |
| **Test Neo4j graph** | Pre-populated knowledge graphs for at least 5 companies |
| **Test user accounts** | 10+ test accounts with Firebase Auth credentials |
| **Prompt test suite** | 100+ categorized prompts with expected behaviors documented |
| **Multi-turn scripts** | 10+ conversation scripts of 5-15 turns each with expected outcomes |

### 6.2 Infrastructure Requirements

| Component | Requirement |
|-----------|-------------|
| **Staging environment** | Full deployment matching production architecture |
| **MCP servers** | At minimum: Google Analytics MCP server connected to test GA4 property |
| **Neo4j** | Staging instance with test company data |
| **Firestore** | Staging project with test data |
| **W&B Weave** | Staging project for trace validation (Feature 1.1.2) |
| **Load test tooling** | Locust configured for KEN-E endpoints |

### 6.3 Evaluator Requirements

| Role | Count | Responsibility |
|------|-------|---------------|
| **Marketing domain expert** | 1-2 | Evaluate research quality, ICP relevance, strategic advice quality, analytics insight quality |
| **QA engineer** | 1-2 | Execute functional tests, load tests, and automated test suites |
| **Developer** | 1 | Evaluate trace completeness, API correctness, database schema integrity |

---

## 7. Acceptance Criteria Summary

### 7.1 Quality Gates (Must Pass for Go-Live)

| Gate | Criteria | Threshold |
|------|----------|-----------|
| **G-Q1** | Onboarding research quality | Average score >= 4.0/5.0 across 17 test companies |
| **G-Q2** | KEN-E intent classification | >= 95% accuracy on 100+ test prompts |
| **G-Q3** | KEN-E response personalization | Average score >= 4.0/5.0 |
| **G-Q4** | GA query accuracy | >= 90% correct queries; 100% data relay accuracy |
| **G-Q5** | Context budget compliance | Zero budget violations across all tests |
| **G-Q6** | Tool search relevance | Precision@5 >= 90% |
| **G-Q7** | Session persistence | 100% state recovery on reconnect/restart |
| **G-Q8** | Account isolation | Zero data leakage between accounts |
| **G-Q9** | Trace compliance (Feature 1.1.2) | 100% of agent traces pass `trace-structure-spec.md` §11 validation |

### 7.2 Performance Gates (Must Pass for Go-Live)

| Gate | Criteria | Threshold |
|------|----------|-----------|
| **G-P1** | Session initialization latency | p95 < 1s |
| **G-P2** | Simple agent response latency | p95 < 5s |
| **G-P3** | Complex agent response latency | p95 < 20s |
| **G-P4** | Tool search latency | p95 < 500ms |
| **G-P5** | MCP server load latency | p95 < 1s |
| **G-P6** | Context section load latency | p95 < 500ms |
| **G-P7** | MCP server connection success rate | >= 99% |
| **G-P8** | 50-user sustained load | No errors for 30 minutes |
| **G-P9** | Initial context consumption | < 20% of context window |

### 7.3 Go/No-Go Decision

- **Go**: All G-Q and G-P gates pass.
- **Conditional Go**: Up to 2 non-critical gates fail (G-Q5/Q6/Q7 are critical and cannot fail). Document known limitations and create follow-up tickets.
- **No-Go**: Any critical gate fails, or more than 2 gates fail. Remediate and re-test.

---

## 8. Evaluation Schedule

### 8.1 Recommended Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Test Preparation** | 3-5 days | Set up staging environment; prepare test data (companies, prompts, scripts); configure load test tooling |
| **Functional Testing** | 3-5 days | Validate trace compliance (§5.8); test tool discovery and MCP loading (§5.5); test session service (§5.6); test web channel adapter (§5.7) |
| **Quality Assessment** | 5-7 days | Run onboarding pipeline for 17 companies (§5.1); execute 100+ prompt test suite with evaluators (§5.2); test GA MCP integration (§5.3); test context manager (§5.4) |
| **Performance Testing** | 3-5 days | Latency profiling for all operations (§4.4.1); load testing with Locust (§4.4.2); token budget stress test (§4.4.3) |
| **Issue Resolution** | 3-5 days | Address quality and performance issues found; re-test failed items |
| **Final Validation** | 2-3 days | Re-run failed gates; end-to-end user journey walkthrough; sign-off |

**Total estimated duration: 19-30 days**

### 8.2 Dependencies

| Dependency | Required By |
|------------|-------------|
| All Release 1 features deployed to staging | Test Preparation start |
| Test company data prepared and verified | Quality Assessment start |
| Test GA4 property accessible from staging | GA MCP Integration testing |
| Locust test scripts updated for Release 1 endpoints | Performance Testing start |
| Marketing domain expert available | Quality Assessment phase |

### 8.3 Deliverables

| Deliverable | Produced By |
|-------------|-------------|
| Test data package (companies, prompts, scripts) | Test Preparation phase |
| Quality assessment scorecards (per feature area) | Quality Assessment phase |
| Performance benchmark report (latency distributions, load test results) | Performance Testing phase |
| Issue log with severity ratings | Throughout |
| Go/No-Go recommendation with gate results | Final Validation phase |
