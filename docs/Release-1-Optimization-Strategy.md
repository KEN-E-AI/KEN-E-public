# Release 1 Optimization Strategy

**Version:** 1.0
**Date:** February 20, 2026
**Status:** Draft
**Purpose:** Comprehensive evaluation plan to ensure Release 1 delivers high-quality outputs and optimal performance before deployment to live users.

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

Release 1 is the first deployment to live users. Evaluation must cover both the **user-facing agentic harness** (the features users interact with directly) and the **evaluation framework infrastructure** (the tooling that enables ongoing quality monitoring after launch). Both must work correctly before go-live.

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

Release 1 spans two categories of work. Both must be evaluated.

### 2.1 User-Facing Agentic Harness (Design Document Phase 1)

| ID | Feature | User Impact |
|----|---------|-------------|
| DDP1-1 | Hierarchical Context Manager | Determines quality of personalized responses |
| DDP1-2 | Tool Registry & Index | Enables correct tool selection for user requests |
| DDP1-3 | MCP Server Manager | Controls tool availability and connection reliability |
| DDP1-4 | Session Service | Maintains conversation continuity |
| DDP1-5 | Web Channel Adapter | User's primary interface for chat |
| DDP1-6 | Primary Orchestrator (KEN-E) | Core conversational intelligence and routing |
| DDP1-7 | Context Compression | Keeps long sessions functional |
| DDP1-8 | Basic Monitoring | Enables operational visibility |
| DDP1-9 | Onboarding Research Pipeline | First-run experience; triggers Strategy Specialist |
| DDP1-10 | Google Analytics MCP Integration | Users can query and discuss GA data |

### 2.2 Evaluation Framework Infrastructure (Notion Release 1)

| ID | Feature | Purpose |
|----|---------|---------|
| NR1-1.1 | Evaluation Results Module | Fetch LLM/human evaluations from W&B and Firestore |
| NR1-1.2 | Tool Call Extractor | Parse individual tool calls from agent traces |
| NR1-1.3 | KEN-E Trace Enhancements | Standardized trace metadata on all agent calls |
| NR1-1.4 | Enhanced Agent Config Schema | Version lineage and deployment status tracking |
| NR1-1.5 | Database Schema Setup | Firestore/BigQuery collections for evaluation data |
| NR1-1.6 | Basic API Endpoints | Agent CRUD, evaluation CRUD, and queue endpoints |

---

## 3. Quality Evaluation Plan

Quality is the primary optimization target. Each section below defines what "high quality" means for that feature area and how to evaluate it.

> **Story References:** The "Stories" column links each evaluation item to its Sprint 5c (MER-E trace readiness) and Sprint 6b (KEN-E evaluation execution) user stories. Additionally, evaluation factor configuration stories span multiple items:
> - **5c.19** configures evaluation factors for Q-1.1–Q-1.7 (all 4 strategy agent output types)
> - **5c.20** configures evaluation factors for Q-2.1–Q-2.9 (orchestrator outputs)
> - **5c.21** configures evaluation factors for Q-4.1–Q-4.6 (analytics outputs)
> - **5c.22** configures evaluation factors for Q-5.1–Q-5.2 (tool discovery outputs)
> - **5c.23–5c.25** verify the MER-E tool call extractor for orchestrator, MCP, and context manager traces
> - **5c.18** ensures latency metrics (duration_ms) are present across all traces (performance readiness)
> - **6b.51–6b.56** cover performance evaluation and final Go/No-Go validation (not tied to specific Q items)

### 3.1 Onboarding Research Pipeline Quality

The onboarding research pipeline is the user's first experience with KEN-E. When a user creates an account and provides their business information, the Strategy Specialist agent automatically conducts research on the user's company, competitors, ICPs, and market positioning. This research populates the Neo4j knowledge graph that KEN-E uses for all subsequent conversations.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-1.1 | Company overview accuracy | Factually correct; no hallucinated details; captures industry, size, and products accurately | Human review of 20+ generated overviews against actual company data | 5c.1, 5c.4, 6b.1, 6b.4 |
| Q-1.2 | ICP relevance | Generated ICPs match the company's actual target market; pain points are realistic and specific | Marketing expert review; compare to known ICPs for recognizable companies | 5c.2, 6b.2 |
| Q-1.3 | Competitor identification accuracy | Correct competitors identified; no irrelevant companies; competitive positioning is defensible | Cross-reference against industry databases and company websites | 5c.3, 6b.3 |
| Q-1.4 | Research completeness | All expected knowledge graph sections populated (company overview, products, ICPs, competitors, strategies, brand guidelines) | Automated check of Neo4j graph completeness per account | 5c.5, 6b.5 |
| Q-1.5 | Research depth | Level 2 and Level 3 context sections contain substantive, actionable detail — not shallow summaries | Human review: are Section summaries (~10k tokens) and Full details (~20k tokens) rich enough to inform strategy conversations? | (covered by Q-1.1–Q-1.4 stories) |
| Q-1.6 | Knowledge graph structure | Entities and relationships are correctly typed; no orphan nodes; graph is traversable for context loading | Automated graph integrity checks | 5c.5, 6b.6 |
| Q-1.7 | Source citation quality | Research claims are traceable to real sources; URLs resolve; no fabricated citations | Automated link validation + human spot-check | 5c.6, 6b.7 |

**Test Companies:**
- 5 well-known companies (verifiable ground truth)
- 5 mid-market companies (realistic user base)
- 5 small/niche businesses (edge cases)
- 2 brand-new companies with minimal web presence (stress test)

### 3.2 Primary Orchestrator (KEN-E) Quality

KEN-E is the main agent users interact with. Quality here means understanding user intent correctly, routing to the right specialist or tool, loading the right context, and delivering clear, tailored responses.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-2.1 | Intent classification accuracy | KEN-E correctly identifies user intent (strategy question vs analytics request vs general chat) | Run 100+ diverse prompts; measure classification accuracy against human-labeled ground truth | 5c.7, 6b.8 |
| Q-2.2 | Context selection relevance | KEN-E loads the correct context sections for the user's question (e.g., loads [competitors] for competitive questions, not [calendar]) | Log which sections are loaded per query; human review of appropriateness | 5c.8, 6b.9 |
| Q-2.3 | Response personalization | Responses reference the user's specific company data (not generic advice) | Human review: does the response mention the user's actual products, ICPs, competitors? | 5c.9, 6b.10 |
| Q-2.4 | Response accuracy | Factual claims about the user's business are correct based on the loaded context | Compare response content to knowledge graph source data | 5c.9, 6b.11 |
| Q-2.5 | Response actionability | Recommendations are specific and implementable, not vague platitudes | Marketing expert scoring on 1-5 actionability scale | 6b.12 |
| Q-2.6 | Conversation coherence | Multi-turn conversations maintain thread; KEN-E remembers what was discussed | Run 10+ multi-turn scenario scripts (5-15 turns each); verify no context loss | 5c.10, 6b.13 |
| Q-2.7 | Clarification behavior | KEN-E asks clarifying questions when requests are ambiguous rather than guessing | Test with 20+ deliberately ambiguous prompts | 5c.11, 6b.14 |
| Q-2.8 | Error handling quality | When something fails (tool unavailable, context missing), KEN-E communicates clearly and suggests alternatives | Simulate failures; evaluate error response quality | 5c.11, 6b.15 |
| Q-2.9 | Tone and brand consistency | KEN-E maintains consistent professional-yet-approachable marketing expert persona | Human review across diverse conversation types | 6b.16 |

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

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-3.1 | Executive summary completeness (Level 1) | Always-loaded summary captures the essential company identity in ~5,000 tokens | Human review across test companies | 5c.12, 6b.17 |
| Q-3.2 | Section summary quality (Level 2) | Loaded sections are substantive enough to answer section-level questions without needing Level 3 | Test: ask questions answerable from Level 2; verify correctness | 5c.12, 6b.18 |
| Q-3.3 | Full detail quality (Level 3) | Detail pages contain comprehensive information for specialist tasks | Test: ask detail-specific questions; verify Level 3 data sufficiency | 5c.12, 6b.19 |
| Q-3.4 | Context budget compliance | Total loaded context stays under 40,000 token budget at all times | Automated monitoring during all test scenarios | 5c.12, 6b.20 |
| Q-3.5 | Section loading appropriateness | Only relevant sections are loaded; irrelevant sections are not loaded unnecessarily | Log analysis: review section load patterns across 100+ queries | 5c.12, 6b.21 |
| Q-3.6 | Unloading behavior | Sections are properly unloaded when switching topics to free token budget | Multi-topic conversation tests; verify budget reclamation | 5c.12, 6b.22 |

### 3.4 Google Analytics MCP Integration Quality

Users will ask KEN-E about their website analytics. KEN-E must correctly use the GA MCP server to run queries and interpret results.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-4.1 | Query construction accuracy | GA API queries correctly match the user's question (right metrics, dimensions, date ranges) | Run 30+ analytics questions; verify query parameters | 5c.13, 6b.23 |
| Q-4.2 | Data interpretation accuracy | KEN-E correctly interprets GA data (e.g., doesn't confuse sessions with users, understands bounce rate meaning) | Human expert review of analytics explanations | 5c.14, 6b.24 |
| Q-4.3 | Insight quality | KEN-E surfaces meaningful insights, not just raw numbers (trends, anomalies, actionable recommendations) | Marketing analyst scoring of insight depth | 5c.14, 6b.25 |
| Q-4.4 | Error handling for GA queries | When GA returns no data or errors, KEN-E communicates clearly and suggests alternatives | Test with invalid date ranges, unavailable properties, etc. | 5c.15, 6b.26 |
| Q-4.5 | Follow-up handling | KEN-E can drill deeper into analytics based on follow-up questions without re-querying unnecessarily | Multi-turn analytics conversation tests | 6b.27 |
| Q-4.6 | Data accuracy relay | Numbers presented to the user match the actual GA API response (no rounding errors, no fabricated data) | Compare KEN-E's stated numbers to raw API responses | 5c.13, 6b.28 |

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

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-5.1 | Search relevance | Tool searches return the correct MCP server/tools for the query (>90% relevant results in top 5) | Run 50+ tool search queries across all categories; measure precision@5 | 5c.16, 6b.29 |
| Q-5.2 | Keyword coverage | Common user phrasings map to correct tools (e.g., "email marketing" -> mailchimp_mcp, "SEO" -> data4seo_mcp) | Test with synonym and paraphrase variations | 5c.16, 6b.30 |
| Q-5.3 | Server loading reliability | MCP servers connect successfully on first attempt (>99% success rate) | Automated load testing of each MCP server 100 times | 5c.16, 6b.31 |
| Q-5.4 | LRU eviction correctness | When at capacity, the least-recently-used server is evicted (not an actively needed one) | Simulate capacity scenarios; verify correct eviction | 5c.16, 6b.32 |
| Q-5.5 | Tool schema accuracy | Loaded tool schemas match actual API capabilities; no stale definitions | Compare loaded schemas to source-of-truth API docs | 6b.33 |

### 3.6 Session Service Quality

Session persistence and state management ensure conversation continuity.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-6.1 | State persistence across reconnects | User reconnects to an existing session and conversation context is preserved | Simulate disconnection/reconnection; verify state continuity | 5c.17, 6b.34 |
| Q-6.2 | Session isolation | Different users' sessions are completely isolated; no data leakage | Create concurrent sessions for different accounts; verify isolation | 5c.17, 6b.35 |
| Q-6.3 | Context compression fidelity | When compression triggers, the summary preserves key decisions and facts from the conversation | Run long conversations; review compressed summaries for information loss | 5c.17, 6b.36 |
| Q-6.4 | Session recovery | If the backend restarts mid-session, the user can resume without data loss | Simulate service restart during active session | 5c.17, 6b.37 |

### 3.7 Web Channel Adapter Quality

The web UI is the user's primary interface.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-7.1 | Message delivery reliability | All user messages reach the orchestrator; all responses reach the user (no dropped messages) | Automated send/receive verification across 1000+ messages | 5c.17, 6b.38 |
| Q-7.2 | Streaming behavior | Responses stream to the user token-by-token (not delayed until complete) | Measure time-to-first-token | 5c.17, 6b.39 |
| Q-7.3 | Structured content rendering | Analytics charts, tables, and formatted outputs render correctly in the web UI | Visual inspection of all output types | 6b.40 |
| Q-7.4 | Connection stability | WebSocket connection remains stable for 30+ minute sessions | Long-running session tests | 6b.41 |
| Q-7.5 | Reconnection handling | If WebSocket drops, the client automatically reconnects and recovers state | Simulate network interruptions | 6b.42 |

### 3.8 Evaluation Framework Infrastructure Quality

The Notion Release 1 features build the evaluation infrastructure. While these are developer-facing, they must work correctly to enable ongoing quality monitoring.

**What to Evaluate:**

| # | Evaluation Item | Quality Criteria | Method | Stories |
|---|----------------|-----------------|--------|---------|
| Q-8.1 | Trace completeness | Every agent call produces a trace with all required metadata fields (agent_id, agent_version, account_id, session_id, model config) | Run compliance validation across all agent types | 5c.32, 6b.43 |
| Q-8.2 | Tool call extraction accuracy | Extractor correctly identifies >90% of tool calls in a trace, preserving parent-child relationships | Compare extracted tool calls to known trace data | 5c.33, 6b.44 |
| Q-8.3 | LLM evaluation retrieval | Fetching evaluations from W&B Weave returns correct, complete data keyed by (trace_id, item_index) | Verify against manually created evaluations | 5c.26, 6b.45 |
| Q-8.4 | Human evaluation retrieval | Fetching evaluations from Firestore returns correct, filtered data | Verify with known test evaluations | 5c.27, 6b.46 |
| Q-8.5 | Agreement rate calculation | Agreement rates correctly computed for matching pairs; edge cases (zero overlap, partial overlap) handled | Unit tests with known score sets | 5c.28, 6b.47 |
| Q-8.6 | Agent config versioning | Config changes create history records with correct diffs and timestamps | Modify configs; verify audit trail | 5c.29, 6b.48 |
| Q-8.7 | API endpoint correctness | All CRUD endpoints return correct data, handle errors, and enforce authentication | Automated API test suite | 5c.30, 6b.49 |
| Q-8.8 | Database schema integrity | All Firestore collections and BigQuery tables exist with correct indexes and partitioning | Schema validation scripts | 5c.31, 6b.50 |

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
| **API endpoint response** (evaluation framework) | < 200ms | < 500ms | > 1s |
| **Evaluation data fetch** (1000 records) | < 5s | < 10s | > 15s |

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
| Evaluation API requests per second | 100+ | Load test evaluation endpoints |

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

### 5.8 Evaluation Framework Infrastructure

**Procedure:**
1. **Trace completeness (Q-8.1):** Run each agent type; validate traces pass `validate_trace_compliance`.
2. **Tool call extraction (Q-8.2):** Create 20 test traces with known tool calls; run extractor; compare output to ground truth.
3. **Evaluation retrieval (Q-8.3, Q-8.4):** Seed W&B and Firestore with known evaluations; fetch and verify.
4. **Agreement rate (Q-8.5):** Calculate agreement for known LLM/human score pairs; verify against hand-calculated results.
5. **Config versioning (Q-8.6):** Modify agent configs 10 times; verify complete audit trail.
6. **API endpoints (Q-8.7):** Run the full API test suite (`api/tests/`); verify all endpoints.
7. **Database schema (Q-8.8):** Run schema validation against Firestore and BigQuery.

**Pass Criteria:**
- 100% trace compliance across all agent types
- Tool call extraction accuracy >= 90%
- Evaluation retrieval returns correct data for all test cases
- Agreement rate matches hand-calculated values exactly
- All API tests pass
- All database indexes and collections exist

---

## 6. Test Environment Requirements

### 6.1 Test Data Requirements

| Data Type | Requirement |
|-----------|-------------|
| **Test companies** | 17 companies (5 well-known, 5 mid-market, 5 niche, 2 brand-new) with verified ground truth data |
| **Test GA4 property** | GA4 property with 6+ months of known data for analytics testing |
| **Test Neo4j graph** | Pre-populated knowledge graphs for at least 5 companies |
| **Test evaluations** | Seed data for W&B Weave and Firestore evaluation collections |
| **Test user accounts** | 10+ test accounts with Firebase Auth credentials |
| **Prompt test suite** | 100+ categorized prompts with expected behaviors documented |
| **Multi-turn scripts** | 10+ conversation scripts of 5-15 turns each with expected outcomes |

### 6.2 Infrastructure Requirements

| Component | Requirement |
|-----------|-------------|
| **Staging environment** | Full deployment matching production architecture |
| **MCP servers** | At minimum: Google Analytics MCP server connected to test GA4 property |
| **Neo4j** | Staging instance with test company data |
| **Firestore** | Staging project with evaluation collections and test data |
| **BigQuery** | Staging dataset with evaluation tables |
| **W&B Weave** | Staging project for trace validation |
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
| **G-Q9** | Trace compliance | 100% of agent traces pass validation |
| **G-Q10** | Evaluation framework APIs | 100% of API tests pass |

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
| **G-P10** | Evaluation API response time | p95 < 500ms |

### 7.3 Go/No-Go Decision

- **Go**: All G-Q and G-P gates pass.
- **Conditional Go**: Up to 2 non-critical gates fail (G-Q5/Q6/Q7 are critical and cannot fail). Document known limitations and create follow-up tickets.
- **No-Go**: Any critical gate fails, or more than 2 gates fail. Remediate and re-test.

---

## 8. Evaluation Schedule

### 8.1 Recommended Timeline

| Phase | Duration | Activities |
|-------|----------|------------|
| **Test Preparation** | 3-5 days | Set up staging environment; prepare test data (companies, prompts, scripts); seed evaluation data; configure load test tooling |
| **Functional Testing** | 3-5 days | Execute evaluation framework API tests (Section 5.8); verify database schema; validate trace compliance; test tool discovery and MCP loading |
| **Quality Assessment** | 5-7 days | Run onboarding pipeline for 17 companies (Section 5.1); execute 100+ prompt test suite with evaluators (Section 5.2); test GA MCP integration (Section 5.3); test context manager (Section 5.4); test session service (Section 5.6) |
| **Performance Testing** | 3-5 days | Latency profiling for all operations (Section 4.4.1); load testing with Locust (Section 4.4.2); token budget stress test (Section 4.4.3) |
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
