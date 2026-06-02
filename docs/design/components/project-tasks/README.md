# Project Tasks — Product Requirements Document

> **Linear Team:** [KEN-E] Projects & Tasks
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Project Tasks component is KEN-E's project-planning subsystem. It lets a user ask the agent to produce a structured project plan (tasks, dependencies, acceptance criteria, assignees, launch times) for a marketing initiative, then persist, display, edit, and execute that plan outside the agent session. Plans are the bridge between a conversational request ("plan an Instagram ad campaign") and concrete, scheduled, agent-or-human-executable work on a calendar.

The component spans the full stack — a FastAPI CRUD surface with Firestore persistence (PRD-1), a planning specialist agent with ADK tools (PRD-2; multi-category instruction update PRD-9), a React calendar page with activity detail and project edit UIs (PRD-3), an event-driven `TaskOrchestrator` that advances a DAG as tasks complete or get revised (PRD-4), and a Cloud-Scheduler-driven time-based trigger that fires tasks at `due_date + launch_time_utc` (PRD-6); the multi-category activity model (categories, sparse fields, orphan-task lifecycle, batch / group-edit endpoints) lives in PRD-7 and the first-class Campaign entity in PRD-8 — all verified end-to-end in PRD-5. It is the foundation consumed by the Automations component (`docs/design/components/automations/`) and by the Knowledge Graph session-end automation (`docs/design/components/knowledge-graph/`).

A developer reading only this section should understand: this component owns `ProjectPlan` / `PlanTask` data, the `/api/v1/plans/*` API, the `/calendar` page, the `project_planning` specialist agent, and the two triggering mechanisms (event-driven + time-based) that advance an active plan.

### Layer Boundary: In-Session vs. Cross-Session Orchestration

KEN-E has two distinct orchestration layers that must not be conflated:

| Layer | Mechanism | Scope | PRD |
|---|---|---|---|
| **In-session orchestration** | Supervisor model: `LlmAgent(mode='chat')` coordinator decomposes user message, delegates per-task to `mode='task'` specialists, synthesizes in one turn | Single chat session; everything within one user turn | [AH-PRD-05](../agentic-harness/projects/AH-PRD-05-multi-step-workflows.md) |
| **Cross-session, scheduled work** | `TaskOrchestrator` + `ProjectPlan` / `PlanTask` | Multi-session; scheduled triggers; calendar-based execution | This component |

The supervisor's task ledger (`TodoItem` with `assignee`, `depends_on`, etc.) borrows the DAG + assignee concepts from Project Tasks **conceptually** but does NOT route through `TaskOrchestrator`. In-session supervisor tasks are ephemeral (live in `session.state`); cross-session project tasks are persisted in Firestore (`accounts/{account_id}/project_plans/{plan_id}`).

**Decision:** [DESIGN-REVIEW-LOG Review 44](../../DESIGN-REVIEW-LOG.md#review-44--ah-97-supervisor-orchestration-adoption-adk-20)

## 2. Architecture

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/project_plan_models.py` | Pydantic models: `ProjectPlan`, `PlanTask`, `AcceptanceCriterion`, status enums, DAG validator |
| `api/src/kene_api/routers/project_plans.py` | CRUD + history endpoints under `/api/v1/plans/*` |
| `api/src/kene_api/routers/internal/scheduler.py` | Internal scheduler endpoint `launch-due-tasks` (PRD-6) |
| `api/src/kene_api/services/task_orchestrator.py` | `TaskOrchestrator` service (PRD-4) — event-driven DAG advancement, dispatch, revision loop |
| Firestore `agent_configs/project_planning` config doc | Read per turn by `specialist_runtime.resolve_config` (AH-PRD-09 Phase 2) — cached ~60 s. Defines model, instruction, temperature, `description` (drives root's description-based routing), tools, callbacks. `specialist_runtime.resolve_agent` builds the `LlmAgent` on demand; the root reaches the planning specialist via `transfer_to_agent("project_planning", …)` — no hand-written agent file, no dispatch handler. PRD-9 updates the instruction + tool roster for the multi-category model. |
| `app/adk/agents/project_planning_tools.py` | Python tool functions referenced by the config doc: `save_project_plan`, `update_task_status`, `get_project_plan` (PRD-2); `resolve_or_create_campaign` (PRD-9, post PR-PRD-08) |
| `frontend/src/pages/CalendarPage.tsx` | Calendar view + list view toggle at route `/calendar` |
| `frontend/src/components/calendar/` | `ActivityDetailPanel`, `ProjectEditDrawer`, filters, deep-link helpers |
| `frontend/src/contexts/ActivitiesContext.tsx` | Plan/task state context for the calendar page |
| `deployment/terraform/` | Cloud Scheduler resource + Firestore composite index for due-task query |

### 2.2 Data Flow

1. **Creation:** A user request to the root agent is routed via `transfer_to_agent("project_planning", query, acceptance_criteria)` (AH-PRD-09 Phase 2) to the project-planning specialist, which calls `save_project_plan` → `POST /api/v1/plans/{account_id}` → persisted to Firestore under `accounts/{account_id}/project_plans/{plan_id}`.
2. **Display:** The frontend calls `GET /api/v1/plans/{account_id}` (list) and `/{plan_id}` (detail) to render the calendar and task panels. Deep-links from chat (`/calendar?project={plan_id}&task={task_id}`) open the right plan with the right task focused.
3. **Activation:** A user activates a plan via `POST .../activate` (owned by PRD-4). Tasks with no unmet `depends_on` enter the "ready" pool.
4. **Advancement (event-driven, PRD-4):** When a task status changes (`PATCH .../tasks/{task_id}`), `TaskOrchestrator.on_task_status_change` resolves newly-unblocked tasks, dispatches agent tasks via `AgentEngineClient`, notifies humans via the existing notification system, and handles revision loops (capped at 5 iterations).
5. **Advancement (time-based, PRD-6):** Cloud Scheduler cron fires `POST /api/v1/internal/scheduler/launch-due-tasks` every minute. The endpoint scans `accounts/*/project_plans/*` via a collection-group query for tasks whose `due_date + launch_time_utc <= now`, status `Approved`, `launched_at IS NULL`. For each, it writes `launched_at` (idempotency guard) and hands off to `TaskOrchestrator.on_task_due`.
6. **Audit + Versioning:** Every mutation writes a new version snapshot under `.../versions/{n}` and an audit entry under `accounts/{account_id}/project_plan_audit/{audit_id}`.

### 2.3 API Contracts

Owned endpoints (published by PRD-1, extended by PRD-4 and PRD-6):

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/plans/{account_id}` | GET | PRD-1 (filter set extended by PR-PRD-07) | `list[ProjectPlan]` with filters: `status[]`, `category[]`, `owner_email[]`, `platform[]`, `channel[]`, `campaign_id[]`, `plan_id[]`, `task_type[]`, `tags[]`, `from`, `to`, `is_active` |
| `/api/v1/plans/{account_id}/{plan_id}` | GET | PRD-1 | `ProjectPlan` |
| `/api/v1/plans/{account_id}/{plan_id}/execution-order` | GET | PRD-1 | Topologically-sorted waves of task_ids for DAG execution |
| `/api/v1/plans/{account_id}` | POST | PRD-1 | `ProjectPlan` → `{plan_id}` |
| `/api/v1/plans/{account_id}/{plan_id}` | PUT | PRD-1 | new version snapshot |
| `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | PATCH | PRD-1 | single-task mutable fields |
| `/api/v1/plans/{account_id}/{plan_id}/tasks/batch` | POST | PR-PRD-07 | Batch-create tasks (multi-day, per-day overrides), transactional |
| `/api/v1/plans/{account_id}/{plan_id}/tasks:group-edit` | PATCH | PR-PRD-07 | Apply one patch to N tasks in a single transaction |
| `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/detach` | POST | PR-PRD-07 | Detach task from plan → moves it into the orphan subcollection |
| `/api/v1/plans/{account_id}/{plan_id}` | DELETE | PRD-1 | soft-delete (`is_active=false`) |
| `/api/v1/plans/{account_id}/{plan_id}/history` | GET | PRD-1 (schema owned by DM-PRD-07) | audit log entries |
| `/api/v1/plans/{account_id}/{plan_id}/activate` | POST | PRD-4 | starts orchestration |
| `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/revision` | POST | PRD-4 | triggers revision loop |
| `/api/v1/internal/scheduler/launch-due-tasks` | POST | PRD-6 | OIDC-authed, Cloud-Scheduler-driven |
| `/api/v1/orphan-tasks/{account_id}` | GET / POST | PR-PRD-07 | Orphan-task list + create (user-scoped) |
| `/api/v1/orphan-tasks/{account_id}/{task_id}` | PATCH / DELETE | PR-PRD-07 | Orphan-task update + soft-delete |
| `/api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-plan` | POST | PR-PRD-07 | Move orphan into an existing plan (transactional) |
| `/api/v1/orphan-tasks/{account_id}/{task_id}/attach-to-new-plan` | POST | PR-PRD-07 | Create plan + attach orphan in a single transaction |
| `/api/v1/campaigns/{account_id}` | GET / POST | PR-PRD-08 | Campaign list + create (objective-scoped, on-the-fly creation supported) |
| `/api/v1/campaigns/{account_id}/{campaign_id}` | GET / PATCH / DELETE | PR-PRD-08 | Campaign read, update, soft-delete |
| `/api/v1/campaigns/{account_id}/generic/{objective}` | GET | PR-PRD-08 | Look up generic fallback campaign for an objective |

Schema source of truth: `api/src/kene_api/models/project_plan_models.py` (Pydantic) and the mirrored TypeScript branded types in `frontend/src/types/` (`PlanId`, `TaskId`, `AccountId`, `PlanTask`, `ProjectPlan`).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `ProjectPlan` / `PlanTask` | `api/src/kene_api/models/project_plan_models.py` | Core Pydantic models; DAG + `launch_time_utc` validators live here. `TaskStatus` ships eight values from v1 (`Draft \| Awaiting Approval \| Approved \| Rejected \| Revision Requested \| Complete \| Failed \| Blocked`); the orchestrator (PRD-4) writes the terminal `Failed` and `Blocked` values. PR-PRD-07 extends `PlanTask` with `category`, `channel`, `task_type`, `owner_email`, `unscheduled`, task-level recurrence, and per-category sparse fields for promotion / holiday. PR-PRD-08 renames `ProjectPlan.campaign` → `campaign_id`. A-PRD-1 adds `type: freeform \| dashboard`, `extension_id`, `goal_id`. DP-PRD-03 extends `assignee_type` with `data_pipeline` and adds `pipeline_spec`. |
| `Campaign` | `api/src/kene_api/models/campaign_models.py` (PR-PRD-08) | First-class entity with `objective` enum; seeded with four per-objective generic fallbacks at account creation |
| Orphan task | `accounts/{account_id}/orphan_tasks/{task_id}` (PR-PRD-07) | `PlanTask` not attached to any plan; user-scoped; can be attached to an existing or new plan atomically |
| `is_system` flag | Same file | Marks platform-owned templates. Defined here; cross-component enforcement table in [`../data-management/README.md` §7.6](../data-management/README.md#76-is_system-system-plan-convention). |
| `TaskOrchestrator` | `api/src/kene_api/services/task_orchestrator.py` | Single convergence point for task-state changes; exposes `on_task_status_change`, `on_task_due`, `activate_plan` |
| `AgentEngineClient` (reused) | `api/src/kene_api/routers/chat.py` (258–378) | Used by orchestrator to dispatch agent tasks |
| `specialist_runtime.resolve_config` + `resolve_agent` | `app/adk/agents/agent_factory/specialist_runtime.py` | AH-PRD-09 Phase 2. Reads Firestore `agent_configs/*` per turn (cached ~60 s) and constructs the planning specialist's `LlmAgent` on demand. The root reaches it via `transfer_to_agent("project_planning", …)` — no `dispatch_to_project_planning()` is generated. (AH-PRD-02's `build_hierarchy()` survives, reduced to building the root only — see AH-PRD-09 §5.1.) |
| `project_planning_tools` | `app/adk/agents/project_planning_tools.py` | Python tool functions referenced by the agent config doc: `save_project_plan`, `update_task_status`, `get_project_plan` |
| `ActivitiesContext` | `frontend/src/contexts/ActivitiesContext.tsx` | Frontend plan/task state provider |
| `CalendarPage` | `frontend/src/pages/CalendarPage.tsx` | Top-level calendar/list view with filters and deep-link support |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Agent Factory (AH-PRD-02) + Per-Turn Dispatch (AH-PRD-09 Phase 2)** | **Hard prerequisite — must ship before PRD-2 starts.** AH-PRD-02 publishes the Firestore config schema (`agent_configs/*` with `description`, `model`, `instruction`, `tools`, etc.). AH-PRD-09 Phase 2 ships `specialist_runtime.resolve_config` + `resolve_agent` (per-turn construction) and `transfer_to_agent` (the single root tool). PR-PRD-02 writes the config doc + tool functions only; the runtime does the rest. | [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md), [`../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md`](../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | **Hard prerequisite — must ship before PR-PRD-01 starts.** Rewrites the enumerated sweep in `routers/accounts.py:968-997` as `firestore.recursive_delete(accounts/{account_id})` so account deletion automatically covers the new `project_plans` and `project_plan_audit` subcollections. | [`../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| **Data Management — DM-PRD-00 (Migration Foundation)** | **Hard prerequisite — must ship before PR-PRD-06 starts.** Provisions the `project_plans` collection-group composite index (`status ASC, launched_at ASC, due_date ASC`) used by the scheduler's due-task query. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-07 (Roles, Members, Audit Substrate)** | **Hard prerequisite — must ship before PR-PRD-07 starts.** Publishes the two-tier role model (`OrgRole` + `AccountRole`) with overlay rules + `require_role(min_role, scope="account")` + transition-policy table + generalized `AuditEntry` schema + `write_audit(parent_kind, parent_id, audit_subcollection, ...)` helper + per-component registry. Every status-changing endpoint in this component calls into that gate and writes via that helper with `audit_subcollection="project_plan_audit"`. | [`../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md`](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md) |
| Notifications (existing) | `create_notification` API + `NotificationCategory` enum — PRD-4 adds a `"Task Ready"` category and `NotificationSidebar.tsx` deep-link wiring | `api/src/kene_api/services/notification_service_v2.py`, `frontend/src/components/notifications/NotificationSidebar.tsx` |
| Strategy Document pattern (existing) | Firestore versioning + audit pattern used as the template for project-plan persistence | `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/models/strategy_models.py` |
| Root agent | Under AH-PRD-09 Phase 2 the root carries only `transfer_to_agent`. Routing guidance for the planning specialist lives in the `agent_configs/project_planning.description` field — rendered into the root's per-turn "Available Specialists" block by `specialist_runtime.available_specialists_provider`. No `create_project_plan` root-agent tool wrapper exists; no `_BASE_INSTRUCTION` CAPABILITY block edit is required. | n/a (config-driven) |
| Account / Auth | `check_strategy_access`-equivalent dependency for account-scoped access control | `api/src/kene_api/auth/` |
| Cloud Scheduler (GCP) | PRD-6 provisions a per-minute cron; OIDC service-account auth on the internal endpoint | `deployment/terraform/` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| Automations (`docs/design/components/automations/`) | Builds directly on `ProjectPlan` / `PlanTask` / `TaskOrchestrator` / Cloud Scheduler. Adds `PlanRun` (execution record) alongside `ProjectPlan` (template), a sibling recurring-scheduler endpoint, an artifact system, and a test/dry-run mode. |
| Knowledge Graph (`docs/design/components/knowledge-graph/`) | The session-end automation (KG-PRD-04) fires through an `is_system=true` project plan; KG-PRD-05 consumes the planning agent for research workflows. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Calendar page, Activity detail panel, Group edit drawer | When implementing any calendar-page UI (PRD-3). Note the terminology mapping: **"Tactic" → Task**, **"Tactic Group" → Project**, **"Edit Group" → "Edit Project"**. |
| `frontend/CLAUDE.md` | CSS architecture, component library | Before adding new visual components. |
| `frontend/src/pages/Insights.tsx` + `Home.tsx` | Page → axios → branded type pattern; context-provider pattern | Starting any new page or state context in the calendar feature. |

## 5. Project Index

The component's work is split across **9 independently shippable project PRDs** under [`projects/`](./projects/). Split rationale: enable parallel execution by multiple dev teams and shrink the surface area each team holds in context. PRD-6 was added when review of `project-planning-implementation-plan.md` surfaced that nothing in the plan actually fires a task at its scheduled `due_date + launch_time_utc`. PRDs 7 and 8 were added when the Figma-designed Calendar page surfaced multi-category activities, orphan-task lifecycle, and a first-class Campaign entity not covered by the original 6 PRDs. PRD-9 was added so that the planning specialist's instruction + tool roster catches up with the multi-category and Campaign contracts after PRDs 7 and 8 ship — without it, every plan the agent produces collapses to `category="task"` and never assigns a campaign.

### Dependency graph

```
DM-PRD-05 (Deletion Sweep Rewrite, data-management) ──> PR-PRD-01: Data Model & API  ──┬──> PR-PRD-02: Planning Agent & Tools ─┐
                                                          (BLOCKING — ships first)     ├──> PR-PRD-04: Event-Driven Orchestrator┤
                                                                                       ├──> PR-PRD-06: Time-Based Scheduler ────┤
                                                                                       ├──> PR-PRD-08: Campaign Management ─────┤──> PR-PRD-05: Integration Testing
                                                                                       └──> PR-PRD-07: Calendar Activities ─────┤    (closes out)
                                                                                                ▲                ▲              │
                                                                                                │                │              │
                                                                       PR-PRD-08 ────────────────┘                │              │
                                                                       DM-PRD-07 (approval+audit) ────────────────┘              │
                                                                                                                                 │
                                                                       PR-PRD-07 ──> PR-PRD-03: Calendar Page Frontend ──────────┤
                                                                       PR-PRD-02 + PR-PRD-07 + PR-PRD-08 ──> PR-PRD-09: Planning Agent Multi-Category Update ─┘

DM-PRD-00 (Migration Foundation) ──> PR-PRD-06 (collection-group index for the scheduler)
```

Edge summary:
- PR-PRD-01 unblocks 02 / 04 / 06 / 07 / 08.
- PR-PRD-07 is gated by PR-PRD-08 (campaigns) + DM-PRD-07 (approval gate + audit schema), and gates PR-PRD-03 (the calendar UI consumes the multi-category contract).
- PR-PRD-09 is gated by PR-PRD-02 + PR-PRD-07 + PR-PRD-08 (it updates the planning specialist's instruction to use the multi-category model and the Campaign entity).
- PR-PRD-05 runs last, after PR-PRDs 1–4 + 6–8 merge. PR-PRD-09 may land in parallel with PR-PRD-05 close-out.

### Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Status |
|---|-------------|------------|------------|---------------|--------|
| 1 | [Data Model & API](./projects/PR-PRD-01-data-model-and-api.md) | Backend (foundation) | DM-PRD-05 | — | Scheduled |
| 2 | [Planning Agent & Tools](./projects/PR-PRD-02-planning-agent-and-tools.md) | Agent / ML | PR-PRD-01, AH-PRD-02 | 4, 6, 8 | Scheduled |
| 3 | [Calendar Page Frontend](./projects/PR-PRD-03-calendar-page-frontend.md) | Frontend | PR-PRD-01, PR-PRD-07 | 9 (after deps met) | Scheduled |
| 4 | [Event-Driven Orchestrator](./projects/PR-PRD-04-event-driven-orchestrator.md) | Backend | PR-PRD-01 | 2, 6, 8 | Scheduled |
| 5 | [Integration Testing & Polish](./projects/PR-PRD-05-integration-testing-and-polish.md) | QA + first-finished team | PR-PRDs 1–4, 6, 7, 8 | 9 | Scheduled |
| 6 | [Time-Based Scheduler](./projects/PR-PRD-06-time-based-scheduler.md) | Backend / Infra | PR-PRD-01, DM-PRD-00 | 2, 4, 8 | Scheduled |
| 7 | [Calendar Activities (Multi-Category Model)](./projects/PR-PRD-07-calendar-activities.md) | Backend | PR-PRD-01, PR-PRD-08, DM-PRD-07 | 4, 6 (after deps met) | Scheduled |
| 8 | [Campaign Management](./projects/PR-PRD-08-campaign-management.md) | Backend | PR-PRD-01, DM-PRD-05 | 2, 4, 6 | Scheduled |
| 9 | [Planning Agent Multi-Category Update](./projects/PR-PRD-09-planning-agent-multi-category-update.md) | Agent / ML | PR-PRD-02, PR-PRD-07, PR-PRD-08 | 3, 5 | Scheduled |

### Recommended workflow

1. **Data-management phase** (see [`../data-management/README.md`](../data-management/README.md) §5.3): DM-PRD-00 → DM-PRD-01/02/03/04 in parallel → DM-PRD-05 → DM-PRD-07. Expected ≈ 8–12 working days with 3–4 teams.
2. **Once DM-PRD-05 merges:** Backend team ships PR-PRD-01 first (the field rename from `campaign` → `campaign_id` happens in lockstep with PR-PRD-08, but the rest of PR-PRD-01 ships as soon as DM-PRD-05 is merged). PR-PRD-08 can start in parallel once PR-PRD-01's data contract is published. Other teams stay engaged by reviewing data contracts and stubbing against the published Pydantic schemas. DM-PRD-00 should already be merged; if not, PR-PRD-06 stays parked until it is.
3. **Once PR-PRD-01 + PR-PRD-08 + DM-PRD-07 merge:** kick off PR-PRD-07 (Calendar Activities) alongside PR-PRDs 2, 4, and 6 in parallel. PR-PRD-03 (Calendar Frontend) starts after PR-PRD-07 since it consumes the multi-category contract.
4. **Once PR-PRD-02 + PR-PRD-07 + PR-PRD-08 merge:** kick off PR-PRD-09 (Planning Agent Multi-Category Update) — Agent / ML team only. Light-weight (instruction edit + one tool function + golden-path evals); can run alongside PR-PRD-03 and PR-PRD-05.
5. **Closing sprint:** PR-PRD-05 closes out with end-to-end testing once PR-PRDs 1–4 + 6–8 are merged. PR-PRD-09 can land before, during, or shortly after PR-PRD-05; failure does not block PR-PRD-05's ship since the agent's pre-PRD-9 instruction continues to produce valid (collapsed-to-`task`) plans.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| [`../../project-planning-implementation-plan.md`](../../project-planning-implementation-plan.md) | §Data Model, §Agent Design, §ADK Tools, §Frontend: Calendar Page, §Task Orchestration, §Verification Plan, §Implementation Phases | Parent implementation plan. Each project PRD maps to one phase. PRD-6 closes a gap not covered in the parent plan. |
| `docs/KEN-E-System-Architecture.md` | Agent dispatch, Tool discovery, Session management | When implementing PRD-2 (planning agent + tools) or PRD-4 (agent dispatch from orchestrator). |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2 Architecture, §2.4 Key Abstractions, §2.5 Tool-assignment & routing model | When writing the planning specialist's config doc (§2.5 description-based routing) and tool registration in PRD-2. |
| [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md) | §5.2 Config-to-constructor mapping | Firestore fields that define an agent config, consumed by the runtime resolver when PRD-2 writes `agent_configs/project_planning`. |
| [`../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md`](../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) | §4 Data contract (`specialist_runtime`, `transfer_to_agent`), §5 Implementation outline | The runtime resolver that picks up `agent_configs/project_planning` per turn — read alongside AH-PRD-02 §5.2. |
| [`AH-PRD-05 — Multi-Step Workflow Orchestration`](../agentic-harness/projects/AH-PRD-05-multi-step-workflows.md) | §1 Layer Boundary | In-session supervisor-orchestration model; layer boundary defined in §1 of this README |
| [`../agentic-harness/mcp-architecture.md`](../agentic-harness/mcp-architecture.md) | §4 Platform decisions, §6 Firestore config, §7 MCPServerManager | When wiring new ADK tools into the registry in PRD-2. |
| [`../data-management/multi-tenant-migration-plan.md`](../data-management/multi-tenant-migration-plan.md) | Phase 5 — PRD + doc edits | Firestore paths in this component follow **Shape B** (`accounts/{account_id}/project_plans/...`). |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Multi-Tenant Shape B) | Rationale for the current `accounts/*/project_plans/*` path layout and the collection-group scheduler query. |

## 7. Conventions and Constraints

### Naming
- Figma-to-code terminology mapping (carry throughout frontend): **"Tactic" → Task**, **"Tactic Group" → Project**, **"Edit Group" → "Edit Project"**.
- Project PRDs in [`projects/`](./projects/) use the `PR-PRD-NN-kebab-topic.md` filename pattern. The directory is named `projects/` (not `prd/`).

### Data model
- `due_date` is a `date` in **UTC**; combined with `launch_time_utc` (`HH:mm` UTC) it forms the trigger datetime consumed by PRD-6. Document this in the model docstring.
- `launched_at` lives on `PlanTask` from v1 (PRD-1) so the PRD-6 scheduler can set it as an idempotency guard without a schema migration.
- `is_system=True` marks platform-owned templates. This component defines the field on `ProjectPlan` and enforces write protection on the base endpoints (PR-PRD-01 §7 acceptance criteria 8a). Cross-component enforcement — list-page filtering, details-page read-only, recurrence-PATCH `403`, HITL carve-out — is documented in [`../data-management/README.md` §7.6](../data-management/README.md#76-is_system-system-plan-convention).

### Firestore layout (Shape B)

Component-owned paths:

- `accounts/{account_id}/project_plans/{plan_id}` — current version
- `accounts/{account_id}/project_plans/{plan_id}/versions/{n}` — archived snapshots
- `accounts/{account_id}/project_plan_audit/{audit_id}` — audit entries (shape owned by DM-PRD-07)
- `accounts/{account_id}/orphan_tasks/{task_id}` — orphan tasks (PR-PRD-07)
- `accounts/{account_id}/campaigns/{campaign_id}` — campaigns (PR-PRD-08)

Query pattern: single-account list endpoints use collection-scope indexes; the PRD-6 scheduler uses a collection-group query over `project_plans`. The index registry and cross-account pattern are documented in [`../data-management/README.md` §7.7](../data-management/README.md#77-cross-account-query-pattern).

### Standard shape for a project PRD in [`projects/`](./projects/)
Each PRD follows the same 10-section structure so parallel teams can onboard quickly:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to the parent plan and any Figma designs

### Testing
- DAG validator (cycle + missing-reference detection, Kahn's algorithm) is unit-tested in isolation from the rest of the model.
- PRD-6 integration test uses a clock override on the internal endpoint rather than real time.

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index (or a Features sub-table if the component adopts Linear feature-parents)
- When a feature-parent is completed: update its status in §5
- When architecture changes (new directories, new abstractions, new API endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec or design doc section becomes relevant: update §4

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — the agent has limited context. Every sentence should help the agent write better code or avoid mistakes.
-->
