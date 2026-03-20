# KEN-E Product Roadmap

**Version:** 2.0 — Notion is the single source of truth for PM data
**Date:** 2026-03-20
**Status:** ACTIVE

---

## Context

KEN-E is a multi-agent AI marketing system built on Google Cloud Platform. Release 1.0 is live in production with core chat capabilities, including Sprint 3b agent config optimizations (merged and deployed). This roadmap defines incremental production releases, each delivering a small set of reliable, well-tested features that build on one another.

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

### What is live in production (Release 1.0 + Sprint 3b)

- KEN-E Root Agent (ADK/LangGraph orchestration)
- Strategy Supervisor (CrewAI multi-agent: business, brand, competitive strategy)
- Company News Agent (transitional — will be replaced by skill + specialist)
- Google Analytics Agent (transitional — will be replaced by Analytics Specialist)
- FastAPI API with 40+ endpoints (knowledge graph CRUD, accounts, OAuth, monitoring)
- React frontend (chat, knowledge base editors, analytics, strategy, admin, agent config)
- Firebase authentication, Firestore, Neo4j, BigQuery
- Weave SDK tracing (basic span hierarchy)
- CI/CD pipelines (GitHub Actions) + Terraform infrastructure
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
6. **Stabilization between releases** — each release is followed by a stabilization sprint for production hardening before the next release begins

---

## Dependency Graph

```
R1.1  ADK Upgrade + Cleanup + Firestore Config Registry
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
 │     ├──► R5.0  MER-E Phase 3 (optimization) ► Prompt improvement loop
 │     │
 │     └──► R5.0  Voice Feasibility Spike ─────► De-risk R6.0 planning
 │
 └──► R6.0  Voice Channel ─────────────────────► Meeting participation
```

---

## Features Index

> **Note:** Notion is the single source of truth for all feature details, user stories, sprint assignments, and story points. This index provides Feature ID → Notion URL mappings and preserves the `> **Design refs:**` blockquotes used by design docs and `/start-session`.

### Release 1.1: Foundation Hardening
> [View in Notion](https://www.notion.so/32930fd653028157b6b5e1c7ead3aef8)

#### 1.1.1 — ADK Upgrade
> [View in Notion](https://www.notion.so/32930fd65302819d831bd6bad1f88772)

#### 1.1.2 — Tracing Hardening
> [View in Notion](https://www.notion.so/32930fd653028170b030dce347c28596)
> **Design refs:** [Harness §9.2](KEN-E-Agentic-Harness-Design.md#92-trace-instrumentation), [§11.1](KEN-E-Agentic-Harness-Design.md#111-current-error-handling-patterns) | [trace-structure-spec §3](trace-structure-spec.md#3-span-naming-conventions), [§10](trace-structure-spec.md#10-ken-e-implementation-checklist), [§11](trace-structure-spec.md#11-trace-compliance-validation)

#### 1.1.3 — Release 1 Optimization Gates
> [View in Notion](https://www.notion.so/32930fd653028170a44edebff1ced379)
> **Design refs:** [Harness §1.5](KEN-E-Agentic-Harness-Design.md#15-expected-outcomes), [§11.5–11.6](KEN-E-Agentic-Harness-Design.md#115-test-locations) | [Release-1-Optimization-Strategy.md](Release-1-Optimization-Strategy.md)

#### 1.1.4 — Firestore Config Registry
> [View in Notion](https://www.notion.so/32930fd6530281c9a7b4dea4a97e589c)
> **Design refs:** [Harness §3.6](KEN-E-Agentic-Harness-Design.md#36-session-state-management), [Appendix C](KEN-E-Agentic-Harness-Design.md#appendix-c-configuration-reference) | [agent-hierarchy §5](design/agent-hierarchy.md#5-firestore-driven-configuration), [§8.3](design/agent-hierarchy.md#83-config-to-constructor-mapping) | [mcp-architecture §6](design/mcp-architecture.md#6-mcp-server-config-registry)

#### 1.1.5 — Remove Session Timeout
> [View in Notion](https://www.notion.so/32930fd6530281859e1fc2491e79b966)

---

### Release 2.0: Intelligent Analytics
> [View in Notion](https://www.notion.so/32930fd6530281479a3ee6da8be73911)

#### 2.1 — Review Loop Framework
> [View in Notion](https://www.notion.so/32930fd6530281a7958fe044608ee208)
> **Design refs:** [Harness §4.6](KEN-E-Agentic-Harness-Design.md#46-planned-review-loop-pattern-generator-critic) | [agent-hierarchy §9.1](design/agent-hierarchy.md#91-review-loop-pattern-single-step) | [review-loop-implementation-plan §1–3, §5 Phases 1–3](design/review-loop-implementation-plan.md)

#### 2.2 — Agent Factory
> [View in Notion](https://www.notion.so/32930fd653028148a28bce667f3b2997)
> **Design refs:** [Harness §4.1](KEN-E-Agentic-Harness-Design.md#41-agent-hierarchy), [§4.4](KEN-E-Agentic-Harness-Design.md#44-planned-specialist-agents) | [agent-hierarchy §7](design/agent-hierarchy.md#7-planned-specialist-agent-layer), [§8](design/agent-hierarchy.md#8-planned-agent-factory) | [mcp-architecture §5a](design/mcp-architecture.md#5a-dynamic-tool-selection-via-tool_filter--toolregistry), [§6](design/mcp-architecture.md#6-mcp-server-config-registry)

#### 2.3 — Analytics Specialist
> [View in Notion](https://www.notion.so/32930fd65302813d9a96d204030594ec)
> **Design refs:** [Harness §4.4](KEN-E-Agentic-Harness-Design.md#44-planned-specialist-agents), [§6.3](KEN-E-Agentic-Harness-Design.md#63-predefined-skills-shipped) | [mcp-architecture §4](design/mcp-architecture.md#4-platform-integration-decisions), [§9](design/mcp-architecture.md#9-infrastructure-summary) | [User Stories: Scenarios 1–3](KEN-E_User_Stories.md)

#### 2.4 — Data Visualization
> [View in Notion](https://www.notion.so/32930fd65302815bb942ca34f57a6690)
> **Design refs:** [data-visualization §1–10](design/data-visualization.md) | [review-loop-implementation-plan §3.1](design/review-loop-implementation-plan.md#31-building-block-review-pipeline)

#### 2.5 — MER-E Phase 0: Trace Extraction
> [View in Notion](https://www.notion.so/32930fd65302814eb30bd242fb6e78b2)
> **Design refs:** [Harness §9](KEN-E-Agentic-Harness-Design.md#9-integration-with-evaluation-framework) | [trace-structure-spec §1–4, §7, §11](trace-structure-spec.md) | [MER-E Framework §4](KEN-E-Self-Improving-Evaluation-Framework-Design.md#4-data-storage-design--database-schema), [§6](KEN-E-Self-Improving-Evaluation-Framework-Design.md#6-trace-collection--wb-integration)

---

### Release 3.0: Content & Campaigns
> [View in Notion](https://www.notion.so/32930fd65302813398bdf47bfbff71cc)

#### 3.1 — Content Specialist
> [View in Notion](https://www.notion.so/32930fd6530281769a41fd5785313c2d)
> **Design refs:** [Harness §4.4](KEN-E-Agentic-Harness-Design.md#44-planned-specialist-agents) | [mcp-architecture §4](design/mcp-architecture.md#4-platform-integration-decisions) | [User Stories: Scenario 2 §§1–4](KEN-E_User_Stories.md#scenario-2-the-user-generates-content-to-improve-brand-awareness)

#### 3.2 — Execution Specialist
> [View in Notion](https://www.notion.so/32930fd6530281d5bb27f67f1e0ec0e4)
> **Design refs:** [Harness §4.4](KEN-E-Agentic-Harness-Design.md#44-planned-specialist-agents) | [mcp-architecture §4](design/mcp-architecture.md#4-platform-integration-decisions), [§8](design/mcp-architecture.md#8-read-only-limitations-and-cmo-impact) | [User Stories: Scenario 3 §§1–4](KEN-E_User_Stories.md#scenario-3-the-user-hosts-a-team-meeting-to-brainstorm-optimiztion-strategies)

#### 3.3 — Predefined Skills
> [View in Notion](https://www.notion.so/32930fd65302812a9c18da33bcb3453c)
> **Design refs:** [Harness §6.1–6.5](KEN-E-Agentic-Harness-Design.md#6-skills-architecture-planned) | [User Stories: Scenario 1 §§1–6](KEN-E_User_Stories.md#scenario-1-the-user-requests-a-keyword-analysis-for-a-website)

#### 3.4 — Multi-Step Workflows
> [View in Notion](https://www.notion.so/32930fd6530281deb526fa9c716c1dd6)
> **Design refs:** [Harness §8](KEN-E-Agentic-Harness-Design.md#8-workflow-management-planned) | [agent-hierarchy §9.2](design/agent-hierarchy.md#92-multi-step-workflow-pattern) | [review-loop-implementation-plan §5 Phase 4](design/review-loop-implementation-plan.md#phase-4-multi-step-workflow-support) | [trace-structure-spec §8–9](trace-structure-spec.md#8-threading-and-parallel-agents)

#### 3.5 — MER-E Phase 1: Quality Scoring
> [View in Notion](https://www.notion.so/32930fd6530281a18234ccfdd1772a31)
> **Design refs:** [Harness §9.3](KEN-E-Agentic-Harness-Design.md#93-output-type-classification), [Appendix B](KEN-E-Agentic-Harness-Design.md#appendix-b-output-types-for-evaluation) | [trace-structure-spec §4–5, §7](trace-structure-spec.md#4-required-metadata-per-span-level) | [MER-E Framework §7](KEN-E-Self-Improving-Evaluation-Framework-Design.md#7-automated-analysis--recommendation-engine), [§11](KEN-E-Self-Improving-Evaluation-Framework-Design.md#11-agentic-harness-integration)

---

### Release 4.0: Automation & Quality Feedback
> [View in Notion](https://www.notion.so/32930fd6530281968b0ef2817c159e0e)

#### 4.1 — Automation Specialist + n8n
> [View in Notion](https://www.notion.so/32930fd6530281928093def6a7ada45f)
> **Design refs:** [Harness §8.8](KEN-E-Agentic-Harness-Design.md#88-planned-n8n-integration) | [mcp-architecture §10](design/mcp-architecture.md#10-open-questions) | [MER-E Framework §14](KEN-E-Self-Improving-Evaluation-Framework-Design.md#14-n8n-workflow-evaluation)

#### 4.2 — Custom Skills
> [View in Notion](https://www.notion.so/32930fd653028115be3ae27b663b875b)
> **Design refs:** [Harness §6.4](KEN-E-Agentic-Harness-Design.md#64-custom-skills-user-created), [§6.6](KEN-E-Agentic-Harness-Design.md#66-planned-frontend-skill-builder)

#### 4.3 — MER-E Phase 2: Human Feedback + Patterns
> [View in Notion](https://www.notion.so/32930fd65302816abd19d2257b4fbdd8)
> **Design refs:** [Harness §9.4](KEN-E-Agentic-Harness-Design.md#94-planned-feedback-collection) | [MER-E Framework §5](KEN-E-Self-Improving-Evaluation-Framework-Design.md#5-human-feedback-capture-system), [§7.3](KEN-E-Self-Improving-Evaluation-Framework-Design.md#73-analysis-module-pattern-detector), [§7.7](KEN-E-Self-Improving-Evaluation-Framework-Design.md#77-automatic-issue-detection)

#### 4.4 — A/B Testing Infrastructure
> [View in Notion](https://www.notion.so/32930fd653028163b04edc3b0a6af137)
> **Design refs:** [Harness §9.5](KEN-E-Agentic-Harness-Design.md#95-planned-ab-testing-support) | [MER-E Framework §8.7](KEN-E-Self-Improving-Evaluation-Framework-Design.md#87-ab-testing-infrastructure)

---

### Release 5.0: Multi-Channel & Self-Improvement
> [View in Notion](https://www.notion.so/32930fd6530281088f80d0532e7e871b)

#### 5.1 — Slack Channel
> [View in Notion](https://www.notion.so/32930fd6530281f7a2d5fff74cf4c711)
> **Design refs:** [Harness §7.1–7.3](KEN-E-Agentic-Harness-Design.md#7-multi-channel-support-planned) | [api-gateway §4](design/api-gateway-multi-channel.md#4-planned-slack-integration-approach) | [data-visualization §9](design/data-visualization.md#9-channel-considerations)

#### 5.2 — MER-E Phase 3: Prompt Optimization
> [View in Notion](https://www.notion.so/32930fd65302814d9208fa5c9d97b1e5)
> **Design refs:** [MER-E Framework §7.2](KEN-E-Self-Improving-Evaluation-Framework-Design.md#72-analysis-module-alignment-analyzer), [§7.5](KEN-E-Self-Improving-Evaluation-Framework-Design.md#75-analysis-module-configuration-optimizer), [§12](KEN-E-Self-Improving-Evaluation-Framework-Design.md#12-human-edit-distance-tracking)

#### 5.3 — Workflow Templates
> [View in Notion](https://www.notion.so/32930fd6530281119736e30a63651bf9)
> **Design refs:** [Harness §8.5–8.7](KEN-E-Agentic-Harness-Design.md#85-workflow-state-machine) | [User Stories: Scenario 1](KEN-E_User_Stories.md#scenario-1-the-user-requests-a-keyword-analysis-for-a-website), [Scenario 2](KEN-E_User_Stories.md#scenario-2-the-user-generates-content-to-improve-brand-awareness)

#### 5.4 — Advanced Workflow & Observability
> [View in Notion](https://www.notion.so/32930fd65302818581e6f0ec4c156c4c)
> **Design refs:** [review-loop-implementation-plan §5 Phase 5](design/review-loop-implementation-plan.md#phase-5-observability--monitoring) | [trace-structure-spec §9](trace-structure-spec.md#9-multi-step-workflow-support-section-13) | [MER-E Framework §13](KEN-E-Self-Improving-Evaluation-Framework-Design.md#13-multi-step-workflow-evaluation)

#### 5.5 — Voice Feasibility Spike
> [View in Notion](https://www.notion.so/32930fd653028197950fe9e90b972689)
> **Design refs:** [Harness §7.4](KEN-E-Agentic-Harness-Design.md#74-voice-channel-notes) | [api-gateway §5](design/api-gateway-multi-channel.md#5-planned-voice-integration-approach)

---

### Release 6.0: Voice & Enterprise
> [View in Notion](https://www.notion.so/32930fd653028178aab2df0b830c3195)

#### 6.1 — Voice Channel
> [View in Notion](https://www.notion.so/32930fd6530281cfa64cce10737cac6e)
> **Design refs:** [Harness §7.4](KEN-E-Agentic-Harness-Design.md#74-voice-channel-notes) | [api-gateway §5](design/api-gateway-multi-channel.md#5-planned-voice-integration-approach)

#### 6.2 — Enterprise Integrations
> [View in Notion](https://www.notion.so/32930fd653028100becff4a0e7a92ae3)
> **Design refs:** [User Stories: Scenario 3 §§3–5](KEN-E_User_Stories.md#scenario-3-the-user-hosts-a-team-meeting-to-brainstorm-optimiztion-strategies)

#### 6.3 — MER-E Phase 4: Full Closed Loop
> [View in Notion](https://www.notion.so/32930fd6530281268205fc338a91a315)
> **Design refs:** [MER-E Framework §8](KEN-E-Self-Improving-Evaluation-Framework-Design.md#8-deployment-pipeline--rollback-system), [§13](KEN-E-Self-Improving-Evaluation-Framework-Design.md#13-multi-step-workflow-evaluation), [§14](KEN-E-Self-Improving-Evaluation-Framework-Design.md#14-n8n-workflow-evaluation), [§15](KEN-E-Self-Improving-Evaluation-Framework-Design.md#15-cross-account-benchmarking)

---

## Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|-----------|------------|
| 1 | **Review loop latency increase** | Medium | High | Cap max_iterations=3 (~15s overhead max). Root Agent skips criteria for simple lookups. |
| 2 | **Token cost increase from review loops** | Medium | High | Reviewer uses cheapest model. Criteria generation ~200 tokens. Monitor via Weave. |
| 3 | **LLM generates poor acceptance criteria** | Medium | Medium | Include good/bad criteria examples in Root Agent instruction. Iterate based on Weave traces. |
| 4 | **State collisions in parallel workflow execution** | High | Low | Unique `output_key` prefix per step enforced by `build_workflow_pipeline()` factory. |
| 5 | **Artifact size bloats review context** | Low | Medium | Limit embedded data to summaries. Defer raw data to separate `data_uri` if >1,000 rows. |
| 6 | **Voice latency incompatible with Agent Engine** | High | High | Agent Engine ~7-13s vs. voice <2s target. Voice feasibility spike scheduled in R5.0 (Story 5.5-1) to evaluate alternatives before R6.0 planning. |
| 7 | **Platform SDK breaking changes (Meta, Google Ads)** | Medium | Medium | Pin SDK versions. Integration tests catch regressions. Budget buffer in Execution Specialist sprint. |
| 8 | **MER-E evaluation of a moving target** | Medium | Medium | Parallel track design means extraction/scoring evolves with agents. Output type expansion story in each MER-E phase. |
| 9 | **ADK version dependency** | Low | Medium | Current >=1.23.0; bump to >=1.26.0 planned in Story 1.1.1-1 for per-invocation tool caching fix. Test thoroughly before upgrade. |
| 10 | **OTEL Pydantic serialization bug** | Low | Low | OTEL disabled (OTEL_SDK_DISABLED=true). Fix expected with ADK >=1.26.0 bump (Story 1.1.1-1). Re-enable OTEL after upgrade. |

---

## Team Decisions

Resolved during roadmap review on 2026-03-20.

1. **Sprint numbering:** Continue from existing project numbering. Sprint 4 was the last completed sprint; this roadmap starts at **Sprint 5**.

2. **Release 1.1 scope:** Do not pull additional work forward into Sprint 5 despite the reduced scope (~39 points). The lighter sprint provides natural buffer for ADK upgrade risk.

3. **Agent Factory complexity:** No spike needed. The team has already created experiments to prototype this functionality; the 2-sprint estimate (Sprints 8–9) stands.

4. **Platform SDK integrations (R3.0):** The team is confident in the 1-sprint-per-specialist plan for Meta Ads and Google Ads SDK integrations.

5. **MER-E resourcing:** The parallel MER-E track (~2-3 stories per sprint) is sustainable with the current team. No dedicated sub-team needed.

6. **Custom skills priority (R4.0):** Custom skills remain in R4.0. If timelines are tight, extend the R4.0 timeline rather than deferring to R5.0.

7. **Slack urgency:** No customer commitments require Slack sooner than R5.0.

8. **Voice feasibility:** A voice feasibility spike is scheduled in R5.0 (Sprint 24, Story 5.5-1) to de-risk R6.0 planning.

9. **Story point estimates:** All estimates are preliminary. The team will re-estimate during sprint planning based on actual complexity assessment.

10. **Release cadence:** A stabilization sprint is added between each release (Sprints 7, 12, 17, 21) for production hardening, bug fixes, and monitoring. No stabilization sprint after R5.0 since R6.0 planning will begin fresh.
