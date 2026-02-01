# KEN-E Design Document Mapping

This file maps KEN-E features (tracked in Notion) to sections in the design document at `docs/KEN-E-Agentic-Harness-Design.md`. Use this mapping to quickly find the architectural context for any feature or user story you're working on.

---

## Design Document Section Index

| Section | Title | Lines |
|---------|-------|-------|
| §1 | Executive Summary | 28–108 |
| §1.1 | Purpose | 30–32 |
| §1.2 | Critical Design Challenges | 34–42 |
| §1.3 | Solution Overview | 44–87 |
| §1.4 | Key Design Decisions | 89–98 |
| §1.5 | Expected Outcomes | 100–108 |
| §2 | Architecture Overview | 111–376 |
| §2.1 | System Architecture | 113–245 |
| §2.2 | Component Responsibilities | 247–278 |
| §2.3 | Request Flow | 280–360 |
| §2.4 | Agent Type Selection (Google ADK) | 362–376 |
| §3 | Context Management Strategy | 379–796 |
| §3.1 | The Context Challenge | 381–415 |
| §3.2 | Hierarchical Context Loading (HCL) | 417–509 |
| §3.3 | Context Loading Implementation | 511–605 |
| §3.4 | Context-Aware Agent Instructions | 607–655 |
| §3.5 | Dynamic Context Compression | 657–732 |
| §3.6 | Context State Management (ADK Integration) | 734–796 |
| §4 | Agent Definitions | 800–1570 |
| §4.1 | Agent Hierarchy Overview | 802–840 |
| §4.2 | Primary Orchestrator Agent | 842–1048 |
| §4.3 | Tool Discovery Agent | 1050–1167 |
| §4.4 | Strategy Specialist Agent | 1169–1238 |
| §4.5 | Content Specialist Agent | 1240–1307 |
| §4.6 | Analytics Specialist Agent | 1309–1409 |
| §4.7 | Execution Specialist Agent | 1411–1492 |
| §4.8 | Automation Specialist Agent | 1494–1557 |
| §4.9 | Agent Summary Table | 1559–1570 |
| §5 | MCP Server Architecture | 1573–1983 |
| §5.1 | Lazy-Loading Recommendation | 1575–1584 |
| §5.2 | Tool Registry Architecture | 1586–1661 |
| §5.3 | Tool Registry Implementation | 1663–1797 |
| §5.4 | MCP Server Manager | 1799–1928 |
| §5.5 | MCP Server Configuration Examples | 1930–1983 |
| §6 | Multi-Channel Support | 1987–2435 |
| §6.1 | Unified Channel Architecture | 1989–2065 |
| §6.2 | Unified Message Format | 2067–2128 |
| §6.3 | Channel Adapters | 2130–2409 |
| §6.4 | Voice Channel Implementation Notes | 2411–2435 |
| §7 | Workflow Management | 2438–2777 |
| §7.1 | Multi-Step Workflow Handling | 2440–2497 |
| §7.2 | Workflow Data Model | 2499–2684 |
| §7.3 | Scheduled Workflow Integration | 2686–2777 |
| §8 | Integration with Evaluation Framework | 2781–3042 |
| §8.1 | Overview | 2783–2789 |
| §8.2 | Trace Instrumentation | 2791–2869 |
| §8.3 | Output Type Classification | 2871–2925 |
| §8.4 | Feedback Collection Integration | 2927–2985 |
| §8.5 | A/B Testing Support | 2987–3042 |
| §9 | Infrastructure Requirements | 3046–3159 |
| §9.1 | Compute Requirements | 3048–3056 |
| §9.2 | Memory Estimates | 3058–3077 |
| §9.3 | Cost Estimates | 3079–3094 |
| §9.4 | Architecture Diagram | 3096–3159 |
| §10 | Risks and Testing Requirements | 3163–3471 |
| §10.1 | Risk Assessment Matrix | 3165–3178 |
| §10.2 | Critical Test Scenarios | 3180–3422 |
| §10.3 | Performance Benchmarks | 3424–3435 |
| §10.4 | Monitoring Requirements | 3437–3471 |
| §11 | Prioritized Feature Roadmap | 3475–3663 |
| §11.1 | Phase Overview | 3477–3510 |
| §11.2 | Phase 1: Foundation (Critical Path) | 3512–3531 |
| §11.3 | Phase 2: Core Agents | 3533–3552 |
| §11.4 | Phase 3: Automation | 3554–3573 |
| §11.5 | Phase 4: Advanced Features | 3575–3594 |
| §11.6 | Dependencies Graph | 3596–3645 |
| §11.7 | Success Metrics by Phase | 3647–3663 |
| §12 | Appendices | 3666–3771 |

---

## Feature-to-Section Mapping

### Release 1 — Foundation

#### 1.1 - Context Manager

Centralized context management system with Hierarchical Context Loading (HCL) for efficient token usage.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §3.1 The Context Challenge | 381–415 |
| **Primary** | §3.2 Hierarchical Context Loading (HCL) | 417–509 |
| **Primary** | §3.3 Context Loading Implementation | 511–605 |
| **Primary** | §3.4 Context-Aware Agent Instructions | 607–655 |
| **Primary** | §3.6 Context State Management (ADK Integration) | 734–796 |
| Supporting | §1.2 Critical Design Challenges | 34–42 |
| Supporting | §1.4 Key Design Decisions | 89–98 |
| Supporting | §2.2 Component Responsibilities | 247–278 |
| Supporting | §10.2.1 Context Management Tests | 3184–3233 |

---

#### 1.2 - Tool Registry

Searchable tool index with lightweight metadata for on-demand tool discovery.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §5.2 Tool Registry Architecture | 1586–1661 |
| **Primary** | §5.3 Tool Registry Implementation | 1663–1797 |
| Supporting | §1.4 Key Design Decisions | 89–98 |
| Supporting | §2.2 Component Responsibilities (Data & Integration Layer) | 269–278 |
| Supporting | §4.3 Tool Discovery Agent | 1050–1167 |
| Supporting | §12 Appendix A: Tool Categories Reference | 3668–3681 |

---

#### 1.3 - MCP Manager

Lazy-loading MCP server manager with LRU eviction to manage Model Context Protocol server connections.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §5.1 Lazy-Loading Recommendation | 1575–1584 |
| **Primary** | §5.4 MCP Server Manager | 1799–1928 |
| **Primary** | §5.5 MCP Server Configuration Examples | 1930–1983 |
| Supporting | §1.4 Key Design Decisions | 89–98 |
| Supporting | §2.1 System Architecture (Tool & Integration Layer) | 113–245 |
| Supporting | §10.2.2 Tool Discovery Tests | 3236–3300 |

---

#### 1.4 - Session Service

State management using ADK patterns with session-level, user-level, and app-level state.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §3.6 Context State Management (ADK Integration) | 734–796 |
| **Primary** | §2.3 Request Flow (Session Manager step) | 280–360 |
| Supporting | §3.5 Dynamic Context Compression | 657–732 |
| Supporting | §6.1 Unified Channel Architecture (Session Manager) | 2036–2040 |
| Supporting | §7.2 Workflow Data Model | 2499–2684 |
| Supporting | §12 Appendix C: Configuration Reference | 3694–3747 |

---

#### 1.5 - Web Channel

React-based web chat interface with real-time streaming, file uploads, and rich message rendering.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §6.1 Unified Channel Architecture | 1989–2065 |
| **Primary** | §6.2 Unified Message Format | 2067–2128 |
| **Primary** | §6.3.1 Web Channel Adapter | 2132–2196 |
| Supporting | §2.1 System Architecture (Client Interfaces) | 113–140 |
| Supporting | §2.3 Request Flow (Channel Adapter & Response Delivery) | 296–353 |

---

#### 1.6 - Primary Orchestrator

Main LangGraph orchestrator agent that routes requests, coordinates specialist agents, and manages conversation flow.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.1 Agent Hierarchy Overview | 802–840 |
| **Primary** | §4.2 Primary Orchestrator Agent | 842–1048 |
| Supporting | §2.2.1 Orchestrator Layer | 249–256 |
| Supporting | §2.3 Request Flow | 280–360 |
| Supporting | §2.4 Agent Type Selection (Google ADK) | 362–376 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |
| Supporting | §12 Appendix C: Configuration Reference (agents section) | 3712–3730 |

---

#### 1.7 - Basic Monitoring

Token usage, latency metrics, and core observability for the agentic harness.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §10.4 Monitoring Requirements | 3437–3471 |
| **Primary** | §10.3 Performance Benchmarks | 3424–3435 |
| Supporting | §1.5 Expected Outcomes | 100–108 |
| Supporting | §9.3 Cost Estimates | 3079–3094 |
| Supporting | §11.7 Success Metrics by Phase | 3647–3663 |

---

### Release 2 — Billing

#### 2.1 - Enable Billing

Subscription and payment infrastructure for KEN-E accounts.

| Type | Section | Lines |
|------|---------|-------|
| Supporting | §9.3 Cost Estimates | 3079–3094 |
| Supporting | §2.2 Component Responsibilities (Firestore) | 269–278 |

> **Note:** The design document does not include a dedicated billing section. This feature is primarily implementation-driven without specific architectural guidance in the design doc.

---

### Release 3 — Core Agents

#### 3.1 - Strategy Specialist

Research, ICP creation, competitor analysis, and campaign planning agent.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.4 Strategy Specialist Agent | 1169–1238 |
| Supporting | §2.2.2 Specialist Agent Layer | 258–267 |
| Supporting | §4.1 Agent Hierarchy Overview | 802–840 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |
| Supporting | §8.3 Output Type Classification | 2871–2925 |
| Supporting | §12 Appendix B: Output Types for Evaluation | 3683–3691 |

---

#### 3.2 - Content Specialist

Multi-format content generation agent for blog, social, email, video, and landing pages.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.5 Content Specialist Agent | 1240–1307 |
| Supporting | §2.2.2 Specialist Agent Layer | 258–267 |
| Supporting | §4.1 Agent Hierarchy Overview | 802–840 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |
| Supporting | §8.3 Output Type Classification | 2871–2925 |

---

#### 3.3 - Analytics Specialist

Sequential agent for data queries, analysis, visualization, and reporting.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.6 Analytics Specialist Agent | 1309–1409 |
| Supporting | §2.2.2 Specialist Agent Layer | 258–267 |
| Supporting | §2.4 Agent Type Selection (SequentialAgent rationale) | 362–376 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |
| Supporting | §12 Appendix A: Tool Categories Reference (Analytics) | 3668–3681 |

---

#### 3.4 - Execution Specialist

Content deployment with validate-execute-verify sequential pattern.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.7 Execution Specialist Agent | 1411–1492 |
| Supporting | §2.2.2 Specialist Agent Layer | 258–267 |
| Supporting | §2.4 Agent Type Selection (SequentialAgent rationale) | 362–376 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |

---

#### 3.5 - Slack Channel

Slack bot integration using Bolt SDK with DM and channel mention support.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §6.3.2 Slack Channel Adapter | 2198–2291 |
| **Primary** | §6.1 Unified Channel Architecture | 1989–2065 |
| Supporting | §6.2 Unified Message Format | 2067–2128 |
| Supporting | §2.1 System Architecture (Client Interfaces) | 113–140 |
| Supporting | §10.2.3 Multi-Channel Tests | 3302–3353 |

---

#### 3.6 - Workflow Manager & Tool Discovery

Multi-step workflow tracking with persistent state, user approval gates, and intelligent semantic tool discovery.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §7.1 Multi-Step Workflow Handling | 2440–2497 |
| **Primary** | §7.2 Workflow Data Model | 2499–2684 |
| **Primary** | §4.3 Tool Discovery Agent | 1050–1167 |
| Supporting | §2.2.1 Orchestrator Layer (Workflow Router) | 249–256 |
| Supporting | §8.2 Trace Instrumentation | 2791–2869 |
| Supporting | §10.2.4 Workflow Tests | 3355–3422 |
| Supporting | §11.6 Dependencies Graph | 3596–3645 |

---

### Release 4 — Automation

#### 4.1 - n8n Integration & Automation Specialist

n8n workflow automation engine with a specialized Automation Agent.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.8 Automation Specialist Agent | 1494–1557 |
| **Primary** | §7.3 Scheduled Workflow Integration | 2686–2777 |
| Supporting | §2.1 System Architecture (Automation Platform) | 236–242 |
| Supporting | §2.2.2 Specialist Agent Layer (Automation Specialist) | 258–267 |
| Supporting | §2.2.3 Data & Integration Layer (Automation Platform) | 269–278 |
| Supporting | §4.9 Agent Summary Table | 1559–1570 |
| Supporting | §12 Appendix A: Tool Categories Reference (Automation) | 3668–3681 |

---

#### 4.2 - Scheduled Workflows & Reporting

Scheduled workflow execution, automated content calendar reviews, and report generation.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §7.3 Scheduled Workflow Integration | 2686–2777 |
| Supporting | §4.8 Automation Specialist Agent (Workflow Types) | 1500–1536 |
| Supporting | §7.1 Multi-Step Workflow Handling | 2440–2497 |
| Supporting | §12 Appendix C: Configuration Reference (automation section) | 3742–3747 |

---

#### 4.3 - Approval Queue

Content approval workflow integrated into KEN-E for review before deployment.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §7.1 Multi-Step Workflow Handling (AWAITING_APPROVAL state) | 2440–2497 |
| **Primary** | §7.2 Workflow Data Model (WorkflowStatus, TaskStatus) | 2499–2560 |
| Supporting | §4.7 Execution Specialist Agent (validation step) | 1411–1424 |
| Supporting | §8.4 Feedback Collection Integration | 2927–2985 |

---

#### 4.4 - KPI Monitoring & Notifications

Automated KPI monitoring with intelligent notifications for performance changes.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §10.4 Monitoring Requirements | 3437–3471 |
| Supporting | §4.8 Automation Specialist Agent (KPI Monitoring workflow type) | 1500–1536 |
| Supporting | §7.3 Scheduled Workflow Integration | 2686–2777 |
| Supporting | §10.3 Performance Benchmarks | 3424–3435 |

---

### Release 5 — Advanced

#### 5.1 - Voice Channel

Voice interaction through Pipecat and Meeting BaaS for meeting participation.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §6.3.3 Voice Channel Adapter | 2293–2409 |
| **Primary** | §6.4 Voice Channel Implementation Notes | 2411–2435 |
| Supporting | §6.1 Unified Channel Architecture | 1989–2065 |
| Supporting | §6.2 Unified Message Format | 2067–2128 |
| Supporting | §9.1 Compute Requirements (Voice Pipeline) | 3048–3056 |
| Supporting | §9.3 Cost Estimates (Voice costs) | 3079–3094 |
| Supporting | §10.1 Risk Assessment Matrix (Voice latency) | 3165–3178 |
| Supporting | §10.2.3 Multi-Channel Tests (Voice tests) | 3335–3353 |

---

#### 5.2 - A/B Testing Support

Experiment infrastructure for testing agent configurations with traffic splitting.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §8.5 A/B Testing Support | 2987–3042 |
| Supporting | §8.2 Trace Instrumentation (experiment_id metadata) | 2791–2869 |
| Supporting | §11.5 Phase 4: Advanced Features | 3575–3594 |

---

#### 5.3 - Self-Optimization & Advanced Analytics

MER-E evaluation framework integration for continuous improvement and predictive analytics.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §8 Integration with Evaluation Framework | 2781–3042 |
| **Primary** | §8.2 Trace Instrumentation | 2791–2869 |
| **Primary** | §8.3 Output Type Classification | 2871–2925 |
| **Primary** | §8.4 Feedback Collection Integration | 2927–2985 |
| Supporting | §4.6 Analytics Specialist Agent (forecasting) | 1309–1409 |
| Supporting | §12 Appendix B: Output Types for Evaluation | 3683–3691 |

---

#### 5.4 - Custom Report Builder

Natural language report creation with user-defined templates and scheduling.

| Type | Section | Lines |
|------|---------|-------|
| **Primary** | §4.6 Analytics Specialist Agent | 1309–1409 |
| Supporting | §7.3 Scheduled Workflow Integration | 2686–2777 |
| Supporting | §4.8 Automation Specialist Agent (Performance Reports) | 1500–1536 |

---

#### 5.5 - Cross-Account Learning & Proactive Suggestions

Anonymized pattern sharing across accounts and AI-initiated proactive recommendations.

| Type | Section | Lines |
|------|---------|-------|
| Supporting | §11.5 Phase 4: Advanced Features (Cross-Account Learning, Proactive Suggestions) | 3575–3594 |
| Supporting | §8.3 Output Type Classification | 2871–2925 |

> **Note:** The design document provides minimal architectural detail for this feature. It is listed in the roadmap (§11.5) but lacks a dedicated design section.

---

## Special Topic Sections

These sections cover cross-cutting concerns relevant to multiple features.

| Topic | Section | Lines | Relevant Features |
|-------|---------|-------|-------------------|
| **Google ADK integration** | §2.4 Agent Type Selection | 362–376 | 1.6, 3.1–3.4, 3.6 |
| **Token budget management** | §3.1 The Context Challenge | 381–415 | 1.1, 1.2, 1.3 |
| **Agent hierarchy & delegation** | §4.1 Agent Hierarchy Overview | 802–840 | 1.6, 3.1–3.4, 3.6 |
| **Channel-agnostic message format** | §6.2 Unified Message Format | 2067–2128 | 1.5, 3.5, 5.1 |
| **Evaluation & tracing** | §8.2 Trace Instrumentation | 2791–2869 | 1.7, 5.2, 5.3 |
| **Infrastructure & scaling** | §9 Infrastructure Requirements | 3046–3159 | All features |
| **Risk assessment** | §10.1 Risk Assessment Matrix | 3165–3178 | All features |
| **Feature dependencies** | §11.6 Dependencies Graph | 3596–3645 | All features |
| **Configuration reference** | §12 Appendix C | 3694–3747 | 1.1, 1.3, 1.6, 5.1 |

---

## Quick Reference: Line Ranges by Section

```
§1  Executive Summary ........................ 28–108
§2  Architecture Overview .................... 111–376
§3  Context Management Strategy .............. 379–796
§4  Agent Definitions ........................ 800–1570
§5  MCP Server Architecture .................. 1573–1983
§6  Multi-Channel Support .................... 1987–2435
§7  Workflow Management ...................... 2438–2777
§8  Integration with Evaluation Framework .... 2781–3042
§9  Infrastructure Requirements .............. 3046–3159
§10 Risks and Testing Requirements ........... 3163–3471
§11 Prioritized Feature Roadmap .............. 3475–3663
§12 Appendices ............................... 3666–3771
```

---

## Keyword Search Index

Use these keywords to quickly find relevant sections when working on a task.

### Architecture & Framework

| Keyword | Sections |
|---------|----------|
| ADK, Agent Development Kit | §2.4 (362), §4.1 (802), §12 Glossary (3749) |
| LangGraph, orchestration | §4.2 (842), §2.3 (280) |
| hierarchical agents | §4.1 (802), §2.2.1 (249) |
| LlmAgent, SequentialAgent, LoopAgent | §2.4 (362), §4.2–4.8 |

### Context Management

| Keyword | Sections |
|---------|----------|
| HCL, hierarchical context loading | §3.2 (417), §12 Glossary (3749) |
| DCL, dynamic context loading | §3.1 (381), §12 Glossary (3749) |
| token budget, context budget | §3.1 (381), §3.3 (511), §3.6 (734) |
| context compression | §3.5 (657) |
| executive summary, Level 1 context | §3.2 (417), §3.4 (607) |
| section summary, Level 2 context | §3.2 (445), §3.3 (544) |
| full detail, Level 3 context | §3.2 (475), §3.3 (570) |
| Neo4j, knowledge graph | §2.2.3 (269), §3.3 (519) |

### Tool Discovery & MCP

| Keyword | Sections |
|---------|----------|
| MCP, Model Context Protocol | §5 (1573), §12 Glossary (3749) |
| lazy loading, on-demand | §5.1 (1575), §1.4 (89) |
| LRU eviction | §5.4 (1799), §12 Glossary (3749) |
| tool registry, tool index | §5.2 (1586), §5.3 (1663) |
| tool discovery, search tools | §4.3 (1050), §5.3 (1719) |
| MCPToolset, StdioConnectionParams | §5.4 (1802) |
| server configs, connection types | §5.5 (1930) |

### Specialist Agents

| Keyword | Sections |
|---------|----------|
| strategy agent, ICP, competitor | §4.4 (1169) |
| content agent, blog, social, email | §4.5 (1240) |
| analytics agent, reports, visualization | §4.6 (1309) |
| execution agent, deploy, publish | §4.7 (1411) |
| automation agent, n8n, workflows | §4.8 (1494) |
| delegate_to_specialist | §4.2 (919) |

### Channels

| Keyword | Sections |
|---------|----------|
| web channel, WebSocket, React | §6.3.1 (2132), §6.1 (1989) |
| Slack, Bolt SDK, Block Kit | §6.3.2 (2198) |
| voice, Pipecat, STT, TTS | §6.3.3 (2293), §6.4 (2411) |
| Recall.ai, Meeting BaaS, Deepgram | §6.3.3 (2293), §6.4 (2411) |
| channel adapter, message normalizer | §6.1 (2017), §6.2 (2067) |
| UnifiedMessage, UnifiedResponse | §6.2 (2080), §6.2 (2109) |

### Workflows & Automation

| Keyword | Sections |
|---------|----------|
| workflow, multi-step, task tracking | §7.1 (2440), §7.2 (2499) |
| WorkflowStatus, TaskStatus | §7.2 (2507) |
| scheduled workflows, n8n | §7.3 (2686) |
| approval, AWAITING_APPROVAL | §7.1 (2464), §7.2 (2510) |
| workflow persistence, Firestore | §7.2 (2561) |

### Evaluation & Testing

| Keyword | Sections |
|---------|----------|
| Weave, tracing, instrumentation | §8.2 (2791) |
| output type, classification | §8.3 (2871) |
| feedback, human evaluation | §8.4 (2927) |
| A/B testing, experiment, variant | §8.5 (2987) |
| alignment, self-optimization | §8.1 (2783) |

### Infrastructure

| Keyword | Sections |
|---------|----------|
| Cloud Run, GCP, scaling | §9.1 (3048), §9.4 (3096) |
| Firestore, BigQuery | §2.2.3 (269), §9.4 (3096) |
| Secret Manager | §9.4 (3138) |
| cost estimates, pricing | §9.3 (3079) |
| performance benchmarks, latency | §10.3 (3424) |
| monitoring metrics | §10.4 (3437) |

---

## Usage Examples

### Example 1: Starting work on "1.1 - Context Manager"

1. Look up Feature 1.1 in the mapping table above
2. Read primary sections first:
   - `docs/KEN-E-Agentic-Harness-Design.md` lines 381–415 (The Context Challenge)
   - `docs/KEN-E-Agentic-Harness-Design.md` lines 417–509 (HCL design)
   - `docs/KEN-E-Agentic-Harness-Design.md` lines 511–605 (Implementation)
3. Check supporting sections for broader context:
   - Lines 34–42 for the design challenges driving this feature
   - Lines 3184–3233 for the expected test scenarios

### Example 2: Starting work on "3.5 - Slack Channel"

1. Look up Feature 3.5 in the mapping table above
2. Read primary sections:
   - `docs/KEN-E-Agentic-Harness-Design.md` lines 2198–2291 (Slack Adapter implementation)
   - `docs/KEN-E-Agentic-Harness-Design.md` lines 1989–2065 (Unified Channel Architecture)
3. Check the unified message format at lines 2067–2128
4. Review cross-channel test scenarios at lines 3302–3353

### Example 3: Searching by keyword

If a user story mentions "tool discovery":
1. Check the Keyword Search Index under "Tool Discovery & MCP"
2. Find: §4.3 (1050), §5.3 (1719)
3. Read those sections for architectural intent
