# Knowledge Graph — Product Requirements Document

> **Linear Team:** [KEN-E] Knowledge Graph
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Knowledge Graph component evolves Neo4j from a write-once-at-account-creation store into a **living, account-scoped knowledge base** that the orchestrator reads during conversations and that a daily system-triggered automation writes to when chat sessions conclude. Its reason for existing is the learning loop: new facts surfaced in conversation — "the CMO is pivoting to usage-based pricing" — are captured as `Observation` nodes, linked to the `Session` that produced them, and returned by semantic search on the next turn. Retired facts are soft-deleted via bi-temporal `valid_from` / `valid_to` so history is never lost.

The component spans five architectural pillars — a **Neo4j migration runner + schema foundation** (constraints, lookup indexes, 768-dimension cosine vector index, shared `:KGNode` label), a **provenance spine** (`Session`, `Observation`, `ResearchRun` nodes + six relationship types + `source_session_id` / `source_research_run_id` properties automatically stamped by `GraphSyncService`), a **read layer** for the orchestrator (`load_context_section`, `load_document`, `search_kb`, `list_observations`), a **session-end writer** that rides on the Automations platform (a seeded `is_system=true` project plan with reviewer + applier agents, HITL halt for destructive changes), and a **research-on-creation refactor** that unifies the strategy-agent write path through `GraphSyncService` with `ResearchRun`-keyed idempotency.

A developer reading only this section should understand: this component owns the Neo4j schema + migration runner, the `Session` / `Observation` / `ResearchRun` node types, the four orchestrator read tools, the session-end reviewer / applier agents (dispatched through the Automations platform), and the rewire that makes every strategy-agent write go through `GraphSyncService`. It is the reason the orchestrator gets smarter over time and why the KB carries auditable provenance for every fact.

## 2. Architecture

```
                   ┌──────────────────────────────────────────┐
                   │  Neo4j schema foundation (KG-PRD-01)     │
                   │  :KGNode label · kg_node_account_id      │
                   │  kb_vector_index (768-dim cosine)        │
                   │  migration runner (lifespan hook)        │
                   └─────────────────┬────────────────────────┘
                                     │
          ┌──────────────────────────┼────────────────────────────────┐
          ▼                          ▼                                ▼
┌──────────────────────┐  ┌───────────────────────┐  ┌───────────────────────────┐
│ Provenance spine     │  │ Orchestrator read      │  │ Research-on-creation      │
│ (KG-PRD-02)          │  │ tools (KG-PRD-03)      │  │ refactor (KG-PRD-05)      │
│ Session · Observation│  │ load_context_section   │  │ strategy agents →         │
│ · ResearchRun +      │  │ load_document · search │  │ GraphSyncService          │
│ GraphSyncService     │  │ _kb · list_observations│  │ ResearchRun-keyed         │
│ provenance stamping  │  │                        │  │ idempotency (MERGE on     │
│                      │  │                        │  │ account + run + natural)  │
└──────────┬───────────┘  └───────────┬────────────┘  └───────────────────────────┘
           │                          │
           │                          │ reads
           │                          ▼
           │               ┌────────────────────────┐
           │               │ Chat orchestrator      │
           │               │ (ken_e_agent)          │
           │               └────────────────────────┘
           │
           │ writes via
           ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ Session-End Automation (KG-PRD-04) — is_system=true ProjectPlan                │
│                                                                                │
│   daily Cloud Scheduler → sweeper → Automations manual-trigger endpoint        │
│        ↓                                                                       │
│   reviewer agent (LLM) ──artifact──▶ applier agent (deterministic)             │
│        ↓                                       ↓                               │
│   proposal.json                      route each change: apply / halt for HITL  │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/db_migrations/` | Numbered `.cypher` migration files + `:Migration` ledger (KG-PRD-01) |
| `api/scripts/apply_neo4j_migrations.py` | Idempotent runner invoked from the FastAPI lifespan (KG-PRD-01) |
| `api/src/kene_api/constants.py` | `NODE_TYPE_REGISTRY` extended with `Session`, `Observation`, `ResearchRun` (KG-PRD-02) |
| `api/src/kene_api/models/session_models.py` | `Session` Pydantic (KG-PRD-02) |
| `api/src/kene_api/models/observation_models.py` | `Observation` Pydantic (KG-PRD-02) |
| `api/src/kene_api/models/research_run_models.py` | `ResearchRun` Pydantic (KG-PRD-02) |
| `api/src/kene_api/services/graph_sync_service.py` | Extended with session / observation / research-run lifecycle + provenance-stamping branch in `create_node` / `update_node` + `idempotency_key` parameter (KG-PRD-02, KG-PRD-05) |
| `api/src/kene_api/services/graph_validation_service.py` | Per-type validators for the three new node types (KG-PRD-02) |
| `api/src/kene_api/routers/knowledge_graph/sessions.py` | CRUD router via `crud_factory` (KG-PRD-02) |
| `api/src/kene_api/routers/knowledge_graph/observations.py` | CRUD router via `crud_factory` (KG-PRD-02) |
| `api/src/kene_api/routers/chat.py` | Per-turn `touch_session` hook (KG-PRD-02) |
| `api/src/kene_api/routers/internal/session_sweeper.py` | `POST /api/v1/internal/scheduler/process-idle-sessions` (KG-PRD-04) |
| `app/adk/agents/shared_tools/kb_read_tools.py` | Four orchestrator read tools wrapped as `FunctionTool` (KG-PRD-03) |
| `app/adk/agents/shared_tools/kb_cypher.py` | `SECTION_SPECS` — centralized Cypher for the five domain sections (KG-PRD-03) |
| `app/adk/agents/shared_tools/kb_formatting.py` | Markdown renderers shared across tools (KG-PRD-03) |
| `app/adk/agents/session_end_agent/reviewer.py` | LLM agent — reads transcript + KB, emits `proposal.json` artifact (KG-PRD-04) |
| `app/adk/agents/session_end_agent/applier.py` | Deterministic applier — routes each change to apply / halt for HITL (KG-PRD-04) |
| `app/adk/agents/session_end_agent/core.py` | `review_session()` pure function (KG-PRD-04) |
| `app/adk/agents/session_end_agent/models.py` | `SessionReview`, `ProposedChange` Pydantic (KG-PRD-04) |
| `app/adk/agents/strategy_agent/orchestrator.py` | Refactored to create/close `ResearchRun`, thread `run_id` into builders (KG-PRD-05) |
| `app/adk/agents/strategy_agent/*_graph_builder.py` | Four builders refactored to write via `GraphSyncService.create_node` (KG-PRD-05) |
| `api/scripts/seed_session_end_template.py` | One-time Firestore seed of the Session-End Review ProjectPlan (KG-PRD-04) |
| `deployment/terraform/cloud_scheduler_session_sweeper.tf` | Daily Cloud Scheduler job + OIDC auth (KG-PRD-04) |

### 2.2 Data Flow

1. **Schema bootstrap (KG-PRD-01):** On API startup, the lifespan runs `apply_all_migrations()`. Migration 001 creates `:Account` / `:Organization` / `:KGNode` uniqueness constraints, the `kg_node_account_id` lookup index, and the `kb_vector_index` (768-dim, cosine). Migration 002 adds the shared `:KGNode` label and backfills `valid_from` on every existing strategy node (28 labels). A `:Migration` ledger node skips already-applied migrations.
2. **Per-turn session touch (KG-PRD-02):** Every chat turn's handler calls `GraphSyncService.touch_session(session_id, account_id, user_id)` — a single `MERGE` that creates the `Session` node lazily on the first turn and bumps `last_message_at` + `message_count` thereafter. Synchronous; < 20 ms typical.
3. **Provenance stamping (KG-PRD-02):** Any write through `GraphSyncService.create_node` / `update_node` that supplies `session_id` or `research_run_id` auto-stamps `source_session_id` / `source_research_run_id` + writes `:OBSERVED_IN` / `:UPDATED_BY` / `:ESTABLISHED_BY` edges after the Firestore sync succeeds. Edge writes use `MERGE` — retry-safe if the follow-up query fails after the node is persisted.
4. **Orchestrator reads (KG-PRD-03):** When the user asks about the account, the ken_e_agent picks one of four read tools: `load_context_section(section)` for a whole domain (products / icps / competitors / strategies / brand), `load_document(entity_type, entity_id)` for drill-down, `search_kb(query)` for semantic fallback via the vector index, `list_observations(subject?)` for long-tail conversational facts. All four are account-scoped by `tool_context.state["account_id"]` (never by LLM argument). Calendar / campaign / performance data lives in Firestore (Project Tasks `Campaign`) and SAR-E — not in Neo4j — so it is out of scope for these read tools; the orchestrator reads it through component-specific paths.
5. **Research-on-creation (KG-PRD-05):** New-account research creates a `ResearchRun` node up front; the four builders (business / competitive / marketing / brand) are refactored to call `GraphSyncService.create_node(..., idempotency_key=(account_id, run_id, natural_key), research_run_id=run_id)` instead of raw Cypher. Every produced node carries `source_research_run_id` and a `:ESTABLISHED_BY` edge. Re-dispatching a builder with the same `run_id` + `natural_key` is a no-op (`MERGE` on `ON MATCH`).
6. **Daily session sweep (KG-PRD-04):** Cloud Scheduler fires `POST /api/v1/internal/scheduler/process-idle-sessions` at 04:00 UTC. The sweeper runs a Cypher query for `Session` nodes where `status="active"` AND `last_message_at < now - 24h`, atomically flips each to `"processing"` (idempotency guard), and for each claimed session triggers one `PlanRun` on the seeded `kg-session-end-review` ProjectPlan via the Automations manual-trigger endpoint with `triggered_by="system"` and `inputs={session_id, account_id}`.
7. **Reviewer → applier (KG-PRD-04):** The Automations orchestrator (Project Tasks PR-PRD-04, extended by A-PRD-02) dispatches the `session_reviewer` agent. It fetches the transcript via `AgentEngineClient.get_conversation_history(session_id)`, grounds itself via the KG-PRD-03 read tools, emits a `SessionReview` JSON artifact (`proposal.json`) via A-PRD-03's `attach_task_artifact`. The orchestrator then dispatches the `session_applier` task, which downloads the artifact and routes each `ProposedChange` by autonomy rules: additive + in-session changes auto-apply via `GraphSyncService`; destructive / cross-session / user-recent-write changes halt the task with `status="Awaiting Approval"` (A-PRD-04 HITL semantics). Users review halted runs on the Automation Details Outputs tab (A-PRD-06) and either Mark Complete (approve) or Revision Requested (re-dispatch the reviewer, capped at 5 iterations).

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/accounts/{account_id}/sessions` | POST / GET | KG-PRD-02 | `Session` |
| `/api/v1/accounts/{account_id}/sessions/{session_id}` | GET / PATCH / DELETE | KG-PRD-02 | `Session` |
| `/api/v1/accounts/{account_id}/observations` | POST / GET | KG-PRD-02 | `Observation` |
| `/api/v1/accounts/{account_id}/observations/{node_id}` | GET / PATCH / DELETE | KG-PRD-02 | `Observation` |
| `/api/v1/internal/scheduler/process-idle-sessions` | POST | KG-PRD-04 | OIDC-auth only; daily sweeper tick |

No owned HTTP endpoints for `ResearchRun` (internal — produced only by KG-PRD-05's orchestrator). The four orchestrator read tools in KG-PRD-03 are not HTTP endpoints — they are ADK `FunctionTool`s called by the runtime.

Schema source of truth: `api/src/kene_api/models/session_models.py`, `observation_models.py`, `research_run_models.py` (Pydantic). The `SessionReview` / `ProposedChange` payload (KG-PRD-04) lives in `app/adk/agents/session_end_agent/models.py` — it travels as a JSON artifact through A-PRD-03's GCS store, not over the API.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `:KGNode` label + `kb_vector_index` | Neo4j schema (KG-PRD-01) | Shared label on every strategy + provenance node; single vector index covers cross-type semantic search |
| `Session` / `Observation` / `ResearchRun` | `api/src/kene_api/models/` | The provenance spine — episodes of knowledge acquisition and the facts they produce |
| `GraphSyncService.create_node(..., session_id?, research_run_id?, idempotency_key?)` | `api/src/kene_api/services/graph_sync_service.py` | Unified write path; auto-stamps provenance; optional `idempotency_key` (tuple) enables MERGE-on-natural-key for research reruns |
| `touch_session(session_id, account_id, user_id)` | `GraphSyncService` | Per-turn lazy-create + bump; sub-20 ms `MERGE` transaction called from `routers/chat.py` |
| `kb_read_tools` (`load_context_section` / `load_document` / `search_kb` / `list_observations`) | `app/adk/agents/shared_tools/kb_read_tools.py` | The orchestrator's four read primitives — account-scoped via `tool_context.state["account_id"]`, LLM-supplied account_id always ignored |
| `SessionReview` + `ProposedChange` | `app/adk/agents/session_end_agent/models.py` | Structured LLM output for the reviewer; 5 kinds of proposed change (`create_observation`, `add_relationship`, `supersede_observation`, `update_node`, `delete_node`) |
| `review_session()` pure function | `app/adk/agents/session_end_agent/core.py` | LLM-and-tools-injected; safe to unit-test without the Automations platform |
| `route_change()` autonomy rules | `app/adk/agents/session_end_agent/applier.py` | Deterministic "apply vs halt" routing — covers delete (always halt), supersede-of-same-session (apply), update-of-user-recent-write (halt), etc. |
| `kg-session-end-review` seeded ProjectPlan | `api/scripts/seed_session_end_template.py` | `is_system=true`, `account_id="_system"`, two tasks (reviewer + applier). Write-protected + list-filtered out + read-only on the Details page. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Project Tasks (PR-PRD-01, PR-PRD-04, PR-PRD-06)** | **Hard prerequisite for KG-PRD-04.** Provides `ProjectPlan` / `PlanTask` base models with `is_system: bool` + write-protection, the `TaskOrchestrator` DAG dispatch + HITL `Awaiting Approval` semantics, and the Cloud Scheduler Terraform + OIDC auth pattern the session sweeper reuses. | [`../project-tasks/README.md`](../project-tasks/README.md) |
| **Automations (A-PRD-01, A-PRD-02, A-PRD-03, A-PRD-04, A-PRD-05, A-PRD-06)** | **Hard prerequisite for KG-PRD-04.** KG-PRD-04 rides entirely on this platform: `PlanRun.inputs` + `triggered_by="system"` (A-PRD-01), manual-trigger endpoint + `{inputs.*}` prompt template substitution (A-PRD-02), `TaskArtifact` + `attach_task_artifact` tool + signed-URL download (A-PRD-03), test-run `inputs` for validation (A-PRD-04), default list filter hiding `is_system=true` (A-PRD-05), and read-only Details page + Outputs tab for HITL Mark Complete / Revision Requested (A-PRD-06). | [`../automations/README.md`](../automations/README.md) |
| **Data Management — DM-PRD-00 (Migration Foundation)** | **Hard prerequisite for KG-PRD-02.** Establishes the Shape B convention (`accounts/{account_id}/{resource}/…`) so the new `Session`, `Observation`, and `ResearchRun` Firestore writes land under `accounts/{account_id}/sessions/…`, `accounts/{account_id}/observations/…`, and `accounts/{account_id}/research_runs/…` from day one. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | **Hard prerequisite for KG-PRD-02.** Rewrites the enumerated account-deletion sweep in `routers/accounts.py:968-997` as `firestore.recursive_delete(accounts/{account_id})` so the three new subcollections (`sessions`, `observations`, `research_runs`) are automatically covered on account deletion without a one-off sweep change per KG node type. | [`../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| Neo4j 5.13+ | Vector index support (`CREATE VECTOR INDEX ... OPTIONS {...}`). KG-PRD-01 verifies the version on all three environments before kickoff; upgrade ticket if any env is older. | `api/src/kene_api/database.py` |
| Google `text-embedding-004` | 768-dimension embedding model used for both stored embeddings (`RETRIEVAL_DOCUMENT` task) and query embeddings (`RETRIEVAL_QUERY` task in `search_kb`). | `app/adk/agents/strategy_agent/embeddings.py` |
| ADK agent registry | KG-PRD-04 registers `session_reviewer` and `session_applier` so the Automations dispatcher can resolve `assignee_name` against them. | `app/adk/agents/registry.py` |
| Vertex AI session store | KG-PRD-04 pulls transcripts via `AgentEngineClient.get_conversation_history(session_id)`. Sessions older than ~7 days age out; daily sweep stays well within the window. | `api/src/kene_api/routers/chat.py:1291` |
| Cloud Scheduler (GCP) | KG-PRD-04 provisions a daily cron (04:00 UTC) under the same OIDC pattern as A-PRD-02 and Project Tasks PR-PRD-06. | `deployment/terraform/` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| Chat orchestrator (`app/adk/agents/ken_e_agent.py`) | Registers the four KG-PRD-03 read tools and consumes them per conversation turn. Replaces the partial keyword-detection path (`SECTION_KEYWORDS`, `should_load_section`) per the Context Management decision ([Review 4 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-4-context-loading--keyword-detection--agent-driven-loading)). |
| Strategy agents (`app/adk/agents/strategy_agent/`) | KG-PRD-05 refactors the four builders to write via `GraphSyncService.create_node`, removing the divergent raw-Cypher write path. `neo4j_tools.py` retains embedding helpers only; write helpers are deprecated. |

## 5. Project Index

The component's work is split across **6 independently shippable project PRDs** under [`projects/`](./projects/). The split follows the same logic as the Project Tasks and Automations sets: one foundation PRD that unblocks everything, two provenance / read PRDs that run in parallel, two consumer PRDs (one blocked on the Automations platform, one on the strategy agents), and one closing-out integration-testing PRD. Each PRD publishes a contract up front so downstream teams can stub against it and run in parallel.

### 5.1 Dependency graph

```
                                 ┌─────────────────────────────────────┐
                                 │ Prereq: Project Tasks PR-PRDs 01,   │
                                 │         04, 06 + Automations        │
                                 │         A-PRDs 01–06 (is_system +   │
                                 │         inputs adds already folded) │
                                 └────────────────┬────────────────────┘
                                                  │
                                                  │ (KG-PRD-04 only)
                                                  │
KG-PRD-01: Migrations,     ┌──> KG-PRD-03: Orchestrator Read Tools ┐
  Constraints, Indexes,    │     (hierarchical context + hybrid)    │
  :KGNode Backfill  ───────┼──> KG-PRD-02: Provenance Spine ────────┼──> KG-PRD-04: Session-End Automation ┐
  (BLOCKING — ships first) │     (Session / Observation / ResearchRun│     (reviewer + applier + daily sweeper)│
                           │      + GraphSyncService methods)        │     — also waits on Project Tasks +     │
                           │                            │           │     Automations                          │
                           │                            │           │                                          ▼
                           │                            │           │                          KG-PRD-06: Integration
                           │                            │           │                          Testing & Polish
                           │                            │           │                          (E2E + multi-tenant +
                           │                            │           │                           perf smoke + observability)
                           │                                        │                                          ▲
                           └──> KG-PRD-05: Research-on-Creation ─────┘──────────────────────────────────────────┘
                                 Refactor (strategy agents →
                                 GraphSyncService + ResearchRun)
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Migrations, Constraints, Indexes, `:KGNode` Backfill](./projects/KG-PRD-01-migrations-constraints-indexes.md) | Backend / Infra (foundation) | — | — | 2 days |
| 02 | [Provenance Spine + GraphSyncService Methods](./projects/KG-PRD-02-provenance-spine.md) | Backend (foundation) | KG-PRD-01, DM-PRD-00, DM-PRD-05 | KG-PRD-03 | 3–4 days |
| 03 | [Orchestrator Read Tools](./projects/KG-PRD-03-orchestrator-read-tools.md) | Agent / ML | KG-PRD-01, KG-PRD-02 | KG-PRD-05 | 4–5 days |
| 04 | [Session-End as a System-Triggered Automation](./projects/KG-PRD-04-session-end-automation.md) | Agent / ML + Backend (pair) | KG-PRDs 01, 02, 03 + PR-PRDs 01, 04, 06 + A-PRDs 01, 02, 03, 04, 05, 06 | KG-PRD-05 | 5–7 days |
| 05 | [Research-on-Creation Refactor](./projects/KG-PRD-05-research-on-creation-refactor.md) | Agent / ML | KG-PRD-01, KG-PRD-02 | KG-PRD-03, KG-PRD-04 | 3–4 days |
| 06 | [Integration Testing & Polish](./projects/KG-PRD-06-integration-testing-and-polish.md) | QA + the team that finishes its KG-PRD first | KG-PRDs 01, 02, 03, 04, 05 | — | 1–2 days |

**Total effort:** ~18–24 engineer-days. With three teams in parallel, clock time is roughly:
- **Sprint 1:** KG-PRD-01 alone (critical path; 2 days).
- **Sprint 2:** KG-PRD-02 solo (foundation for 3, 4, 5) while Prereq team folds `is_system` / `inputs` into Project Tasks + Automations PRDs (already landed per this README).
- **Sprint 3:** KG-PRDs 3 and 5 in parallel (different teams), KG-PRD-04 design work begins waiting on Automations platform.
- **Sprint 4 (pending Automations ship):** KG-PRD-04.
- **Sprint 5:** KG-PRD-06 — integration testing + polish, run by whichever team finished its component PRD first.

If the Automations platform ships in Sprint 2–3 (7 A-PRDs over ~4 weeks based on the Automations README estimates), KG-PRD-04 can start in Sprint 4 without a stall.

### 5.3 Recommended team assignments

Three teams, minimal handoffs:

- **Team A — Backend Foundation** (Python / Neo4j / FastAPI)
  - Sprint 1: KG-PRD-01 (solo, 2 days)
  - Sprint 2: KG-PRD-02 (solo, 3–4 days)
  - Sprint 3+: available to pair on KG-PRD-04's backend pieces (sweeper endpoint, seed script, Terraform) or to support others

- **Team B — Agent / ML**
  - Sprint 1: review KG-PRD-01, prep KG-PRD-05 (audit current strategy_agent → raw Cypher sites)
  - Sprint 2: KG-PRD-05 starts after KG-PRD-02 ships (3–4 days)
  - Sprint 3: KG-PRD-03 (4–5 days; orchestrator read tools)
  - Sprint 4: KG-PRD-04 (pair with Team A for the backend bits; reviewer / applier agents)

- **Team C — Platform PRD support**
  - Sprint 1–2: confirm the additive Project Tasks + Automations PRD changes (`is_system`, `inputs`, etc.) are landed and unchanged — implementation effort lives in those components' sprints themselves.

If only two teams are available, Team B absorbs Team C's work in Sprint 1.

### 5.4 Cross-PRD coordination points

- **KG-PRD-02 ↔ KG-PRD-03:** The `Observation` model + `:KGNode` label must stabilize before read tools can test their Cypher. KG-PRD-03 teams should stub against the Pydantic schema as soon as KG-PRD-02's PR is in review (don't wait for merge).
- **KG-PRD-02 ↔ KG-PRD-05:** Research refactor depends on `GraphSyncService.create_node(..., idempotency_key=..., research_run_id=...)` signature. KG-PRD-02 lands the provenance branch; KG-PRD-05 adds the `idempotency_key` parameter and lands the callers. Coordinate to avoid the two PRs landing in conflicting order.
- **KG-PRD-04 ↔ Automations platform:** KG-PRD-04 assumes `is_system` write-protection, `inputs` substitution, and the Outputs-tab HITL interaction. The additive changes to PR-PRD-01 / A-PRDs 01, 02, 04, 05, 06 must be shipped before KG-PRD-04 can integration-test.
- **KG-PRD-03 ↔ KG-PRD-04:** Reviewer agent uses the Phase 3 read tools to ground itself. If KG-PRD-03 ships first (expected), KG-PRD-04 reviewer works against the real KB; if not, use mocked tools in unit tests and wait for KG-PRD-03 to merge before e2e testing.
- **KG-PRD-05 ↔ DM-PRD-05:** KG-PRD-05 widens the Firestore-sync blast radius (every research write goes through `GraphSyncService`, which dual-writes). DM-PRD-05's `recursive_delete` sweep covers these automatically via the Shape B subcollections — no coordination needed beyond ordering, but call this out in KG-PRD-05 § Risks.

### 5.5 Recommended workflow

1. **Sprint 1** — Team A ships KG-PRD-01. Other teams review specs, confirm the Project Tasks / Automations PRD additions are in place (Team C), and audit the existing strategy-agent write paths (Team B, for KG-PRD-05 readiness).
2. **Sprint 2** — Team A ships KG-PRD-02. Team B starts KG-PRD-05 (the parts that don't need KG-PRD-02 — research-run lifecycle design, builder refactor planning). Team C has any remaining Project Tasks / Automations PRD additions in review.
3. **Sprint 3** — Team B ships KG-PRD-05 and KG-PRD-03 in parallel (different engineers, same team). Team A is available to unblock the Automations platform team on anything KG-PRD-04 will need.
4. **Sprint 4** (pending Automations ship) — Team B + Team A pair on KG-PRD-04.
5. **Sprint 5** — KG-PRD-06 — whichever team finished its component PRD first owns this; QA leads. End-to-end suites, multi-tenant isolation, performance smoke, observability checks, and the README "Status: shipped" report.

**First shippable value lands at end of Sprint 2:** KG-PRD-01 + KG-PRD-02 together give the KB its provenance spine, vector index, and constraints — the orchestrator's context-loading is unchanged but the data it reads is now traceable.

**Full user-visible value lands at end of Sprint 3:** KG-PRD-03 makes the orchestrator actually smarter during conversations; KG-PRD-05 unifies the research write path; no visible UI changes but query quality improves.

**Learning loop closes at end of Sprint 4:** KG-PRD-04 enables session-end updates; the KB grows with every conversation.

**Component is verified end-to-end at end of Sprint 5:** KG-PRD-06 confirms every seam — Neo4j ↔ Firestore, sweeper ↔ Automations, read tools ↔ orchestrator — works against real services.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`../project-tasks/README.md`](../project-tasks/README.md) | §2 (Architecture), §7 (`is_system` semantics) | KG-PRD-04's seeded template is an `is_system=true` `ProjectPlan`; HITL halt + revision loop live in PR-PRD-04. |
| [`../automations/README.md`](../automations/README.md) | §2 (Architecture), §7 (Conventions — `inputs`, `triggered_by`, `is_system`) | KG-PRD-04 rides on this platform; the `inputs` + `triggered_by="system"` + Outputs-tab contracts live here. |
| [`../data-management/README.md`](../data-management/README.md) | §2 (Architecture), §5.3 (Shape B indexes) | Shape B path convention the three new KG Firestore subcollections (`sessions`, `observations`, `research_runs`) follow. |
| `docs/KEN-E-System-Architecture.md` | §3.2 (Hierarchical Context Loading), §Agent hierarchy | Background for KG-PRD-03 (replaces keyword-detection path per the Context Management decision; see [Review 4 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-4-context-loading--keyword-detection--agent-driven-loading)). |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2 Architecture, §2.4 Key Abstractions | When wiring `session_reviewer` / `session_applier` into the registry (KG-PRD-04). |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Multi-Tenant Shape B) | Rationale for the `accounts/*/{sessions,observations,research_runs}/*` path layout. |
| Neo4j docs: [Vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/), [Constraints](https://neo4j.com/docs/cypher-manual/current/constraints/) | Entire pages | Reference when implementing KG-PRD-01's migrations and KG-PRD-03's `kb_vector_index` calls. |
| Historical Notion User Stories (archive only): [Story 1.1.6-1](https://www.notion.so/34230fd653028175bccadb3dfd3d581f), [Story 1.1.6-2](https://www.notion.so/34230fd65302816ea2eeeec49aedd90e) | Stories subsumed by KG-PRD-03 | Original user stories for on-demand section loading + per-entity drill-down. |

## 7. Conventions and Constraints

### Data model
- **`:KGNode` shared label** on every strategy + provenance node (29 types total). Enables one vector index, one account-scoped lookup index, one uniqueness constraint — instead of 29 of each.
- **Bi-temporal validity:** `valid_from` set on create; `valid_to` only set by soft-delete or supersede. Current facts have `valid_to IS NULL`. KG-PRD-03's `search_kb` filters to `valid_to IS NULL` by default; `list_observations(valid_only=false)` opens the filter.
- **Provenance properties on every node:** `source_session_id`, `source_research_run_id`, `last_updated_by_agent` (`"researcher"` / `"session_end_agent"` / `"user"`). Caller-supplied on `create_node` / `update_node` via `GraphSyncService`.
- **Six provenance relationships:** `(:KGNode)-[:OBSERVED_IN]->(:Session)`, `[:UPDATED_BY]->(:Session)`, `[:ESTABLISHED_BY]->(:ResearchRun)`, `(:Observation)-[:ABOUT]->(:KGNode)`, `[:SUPERSEDES]->(:Observation)`, `(:Session)-[:FOR_ACCOUNT]->(:Account)`.
- **Observations are session-born:** `session_id` is required on `create_observation`. A future PRD can widen this if session-less observations become needed.
- **Supersede over delete:** Prefer `supersede_observation` over editing or deleting; bi-temporal history is the value proposition.

### Neo4j layout
- Migration files: `api/src/kene_api/db_migrations/NNN_short_snake_case_name.cypher`. Immutable after merge; hash-mismatch on startup → hard error. Every statement idempotent (`IF NOT EXISTS` or `MERGE`).
- Vector index: `kb_vector_index` — 768-dim, cosine, on `:KGNode.embedding`. Stored embeddings use Google `text-embedding-004` with task `RETRIEVAL_DOCUMENT`; query embeddings use `RETRIEVAL_QUERY`.
- Account-scoping: every section / drill-down Cypher **must** include `{account_id: $account_id}` in the traversal seed. Defense-in-depth: post-filter in Python too.

### Firestore layout (Shape B)
- `accounts/{account_id}/sessions/{session_id}` — session metadata mirror (NEW; KG-PRD-02)
- `accounts/{account_id}/observations/{node_id}` — observation metadata mirror (NEW; KG-PRD-02)
- `accounts/{account_id}/research_runs/{run_id}` — research-run metadata mirror (NEW; KG-PRD-02)
- Covered by DM-PRD-05's `recursive_delete` on account deletion — no per-collection sweep edits needed.

### Read-tool account-scoping (KG-PRD-03)
- `account_id` pulled from `tool_context.state["account_id"]` — **never** from an LLM-supplied argument. Tool function signatures exclude `account_id`; a malicious LLM passing `account_id=...` gets a `TypeError`.
- Each tool wraps with `@safe_weave_op(name="kb.<tool_name>")` and emits one span per call with `account_id` as an attribute.
- Token budgets: `load_context_section` caps at 10k tokens; `load_document` caps at 8k tokens; over-budget truncation drops lowest-priority entity types entity-at-a-time, never mid-entity.

### `_system` sentinel (KG-PRD-04)
- `account_id="_system"` holds platform-owned ProjectPlans (only the Session-End Review template today). Write-protected + list-filtered + read-only on Details page. Users cannot query the sentinel normally — the sweeper hardcodes `plan_id="kg-session-end-review"`.
- Account-deletion DELETE on `_system` is not guarded specifically — it would recursively-delete the seeded template. Operational concern only (why would you delete the system account?); tracked as a KG-PRD-04 §9 risk.

### Autonomy rules (KG-PRD-04 applier)
- **Apply automatically:** `create_observation`, `add_relationship`, `supersede_observation` of a same-session observation, `update_node` of a non-user or >7-day-old user field.
- **Halt for HITL:** `delete_node` (always), `supersede_observation` of a cross-session observation, `update_node` of a user-written field < 7 days old, any unknown `kind` (fail-closed).
- Halt surfaces as `PlanRun.status="halted_for_human"` + applier task `status="Awaiting Approval"` with a clear `revision_comment`. User reviews in the Outputs tab (A-PRD-06) and either Marks Complete or Revision Requested.

### Idempotency keys (KG-PRD-05)
- `GraphSyncService.create_node(idempotency_key=(account_id, run_id, natural_key))` enables MERGE-on-natural-key, making research reruns no-ops.
- `natural_key` = `normalize(type-specific string)` where `normalize()` = lowercase + trim + collapse whitespace + strip punctuation.
- `normalize()` centralized in `app/adk/agents/utils/text_normalization.py` so research and session-end agents share one definition.

### Testing
- Unit tests per migration verify constraints / indexes / labels are present after apply.
- Provenance-stamping tests use mocked Neo4j to verify emitted Cypher includes the expected `source_session_id` / edge-MERGE statements.
- Read-tool multi-tenant isolation: every tool called with session state `account_id=A` returns zero rows belonging to account B (explicit test suite per `tests/integration/test_kb_tools_multi_tenant.py`).
- KG-PRD-04 HITL halt-resume is covered end-to-end via the Automations orchestrator (live or stubbed depending on test environment).

### Standard shape for a project PRD in [`projects/`](./projects/)
Each PRD follows the same 10-section structure as the Project Tasks and Automations PRDs:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, parent plans, external docs

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new node types, new relationships, new tools, new abstractions): update §2
- When a new cross-component dependency is introduced: update §3
- When Neo4j schema changes: update §7 Neo4j layout
- Update after KG-PRD-06 integration test runs with a "Status: shipped" section at the top of §5.5 linking the verification report.

This PRD is read by the Dev Team agent during implementation planning. Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
