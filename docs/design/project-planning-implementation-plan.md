# Project Planning Feature — Implementation Plan

> **Status (2026-04-17):** This plan has been split into 6 independently shippable PRDs in [`components/project-tasks/projects/`](./components/project-tasks/projects/) for parallel execution by multiple dev teams. See [`components/project-tasks/README.md`](./components/project-tasks/README.md) for the dependency graph and team workflow.
>
> **Gap closed by the split:** A new **PRD-6 — Time-Based Scheduler** ([`components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md`](./components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md)) was added because this document does not include any mechanism to fire a task when its `due_date + launch_time_utc` arrives. KEN-E has no scheduler infrastructure today; PRD-6 builds it.

## Context

Users of KEN-E need the ability to ask the agent to create structured project plans for complex marketing initiatives. Today, KEN-E can generate strategy documents and answer questions, but it cannot produce actionable plans with tasks, assignments, and dependency tracking. Since project plans involve work for both agents and humans, the plan must be persisted outside the agent session and accessible via the API/frontend.

This document is the implementation plan for the development team. No code is included — only architecture decisions, data models, component designs, and phasing.

---

## Approach: Firestore-Native

Follow the existing Strategy Document pattern (`api/src/kene_api/routers/strategy.py`) — account-scoped Firestore collections with versioning, audit trails, and access control. This requires zero new infrastructure and maintains codebase consistency.

---

## Data Model

### Core Entities

```
ProjectPlan
  plan_id: str (UUID)
  account_id: str
  title: str
  goal: str                           # What the project aims to achieve
  acceptance_criteria: list[AcceptanceCriterion]
  tasks: list[PlanTask]
  campaign: str | None                # Optional campaign name to group projects
                                      # A project belongs to at most one campaign
  tags: list[str]                     # User-created categories for grouping projects
  status: PlanStatus                  # draft | active | completed | archived
  created_by: str (user_id)
  created_at: datetime
  updated_at: datetime
  version: int
  is_active: bool

AcceptanceCriterion
  criterion_id: str
  description: str
  is_met: bool (default False)

PlanTask
  task_id: str
  title: str
  description: str
  assignee_type: "agent" | "human"
  assignee_name: str                  # Agent name from registry, or human name/role
  status: TaskStatus                  # Draft | Awaiting Approval | Approved |
                                      # Rejected | Revision Requested | Complete
  depends_on: list[str]               # task_ids this task waits on (forms the DAG)
  cost: float | None                  # Cost of completing the task (e.g., $100 ad spend)
  due_date: date | None
  launch_time_utc: str | None         # HH:mm format — specific time on due_date
                                      # (e.g., "13:00" for 1:00 PM UTC email send)
  platform: str | None                # Platform for task execution
                                      # e.g., "Google Ads", "Mailchimp", "Instagram",
                                      # "Meta Ads", "TikTok", "LinkedIn"
  tags: list[str]                     # User-created categories for grouping tasks
  estimated_effort: str | None        # "small" | "medium" | "large"
  completion_notes: str | None
  revision_comment: str | None        # Feedback from human reviewer for revisions
```

### Status Flow

Task statuses align with the Figma calendar design:

```
Draft → Awaiting Approval → Approved → Complete
                          ↘ Rejected
                          ↘ Revision Requested → (back to Draft for rework)
```

### Dependency Graph Validation

The `depends_on` field on each task forms a directed acyclic graph (DAG). The Pydantic model validator must:
1. Verify all referenced `task_id`s in `depends_on` exist in the plan's task list
2. Detect cycles using topological sort (Kahn's algorithm)
3. Reject plans with circular dependencies, returning clear error messages

### Firestore Collection Structure

> **Revised 2026-04-20** — Firestore paths follow the Shape B layout (`accounts/{account_id}/{resource}/...`). See [Review 15 in DESIGN-REVIEW-LOG](DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) — Multi-Tenant Data Model Shape for rationale.

```
accounts/{account_id}/project_plans/{plan_id}
    plan_id, account_id, title, goal, acceptance_criteria,
    tasks, campaign, tags, status, version, created_at, updated_at,
    created_by, is_active

accounts/{account_id}/project_plans/{plan_id}/versions/{version_number}
    ... archived version snapshot ...

accounts/{account_id}/project_plan_audit/{audit_id}
    ... audit trail entries (who changed what, when) ...
```

Account-scoped under Shape B; the existing strategy-doc / strategy-audit subcollections (`accounts/{account_id}/strategy_docs/*`, `accounts/{account_id}/strategy_audit/*`) follow the same pattern.

---

## Agent Design

### New Planning Specialist Agent

**File:** `app/adk/agents/project_planning_agent.py`

An `LlmAgent` following the same pattern as `ken_e_agent.py`:
- **Model:** `gemini-2.0-flash` (configurable via Firestore)
- **Thinking:** `ThinkingConfig(include_thoughts=True)` (same as root agent)
- **Instruction provider:** Closure-based, reads `organization_context` from session state
- **Firestore config doc:** `project_planning_agent`
- **Tools:** `save_project_plan`, `update_task_status`, `get_project_plan`
- **Callbacks:** Same Weave tracing callbacks as existing agents

The agent instruction should guide the model to:
1. Analyze the user's project request and ask clarifying questions if needed
2. Define a clear, measurable project goal
3. Define acceptance criteria that can verify project success
4. Decompose the project into discrete tasks
5. For each task, determine whether it should be assigned to an agent or a human, and name the assignee
6. For each task, set the `platform` if applicable (e.g., "Google Ads", "Mailchimp")
7. For each task, estimate the `cost` if applicable (e.g., ad spend)
8. For each task, set `launch_time_utc` if the task must execute at a specific time
9. Establish task dependencies (which tasks must complete before others can start)
10. Optionally assign the project to a `campaign` and apply `tags` for organization
11. Output a structured JSON matching the `ProjectPlan` Pydantic schema
12. Call `save_project_plan` to persist the plan

### Registry Entry

**File:** `app/adk/agents/registry.py`

```
AgentEntry(
    name="project_planning",
    module_path=".project_planning_agent",
    attr_name="project_planning_agent",
    description="Specialist agent for creating and managing project plans",
    capabilities=["planning", "project_management"],
    config_doc_id="project_planning_agent",
)
```

### Dispatch Handler

**File:** `app/adk/agents/utils/dispatch_handlers.py`

New `dispatch_to_project_planning()` function following the exact pattern of `dispatch_to_company_news()`:
- Extract `account_id` and `organization_context` from `tool_context.state`
- Inject org context into the query
- Invoke the planning agent with retry
- Return structured result: `{status, query, result, source: "project_planning_specialist", agent: "project_planning"}`

### Root Agent Integration

**File:** `app/adk/agents/ken_e_agent.py`

Add a new tool function `create_project_plan(query: str, tool_context: ToolContext | None = None)` that calls `dispatch_to_project_planning()`. Add a new capability section to `_BASE_INSTRUCTION`:

```
**CAPABILITY N - Project Planning:**
Use `create_project_plan` for queries about:
- Creating a project plan, work breakdown, or task list
- Planning a marketing campaign, product launch, or initiative
- Organizing work across team members and agents
- Breaking down complex goals into actionable steps
```

---

## ADK Tools

### Tool 1: `save_project_plan`

Called by the planning agent after generating the plan.
- **Input:** Plan data as JSON dict
- **Behavior:** Validate against `ProjectPlan` Pydantic model, check DAG validity, save to Firestore
- **Output:** `plan_id` and confirmation message

### Tool 2: `update_task_status`

Allows the agent to update a task's status within a plan.
- **Input:** `plan_id`, `task_id`, `new_status`, optional `completion_notes` or `revision_comment`
- **Behavior:** Validate status transition, update Firestore, trigger dependency resolution (see Task Orchestration section)
- **Output:** Updated task summary + list of newly unblocked tasks

### Tool 3: `get_project_plan`

Retrieves an existing plan for display or modification.
- **Input:** `plan_id`
- **Output:** Full plan structure

**File:** `app/adk/agents/project_planning_tools.py`

Register in tools YAML (`app/adk/tools/registry/config/tools.yaml`) under a new `planning` category.

---

## API Endpoints

### New Router: `api/src/kene_api/routers/project_plans.py`

Follow the pattern of `api/src/kene_api/routers/strategy.py`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/plans/{account_id}` | List all plans for account |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}` | Get a specific plan |
| `POST` | `/api/v1/plans/{account_id}` | Create a new plan |
| `PUT` | `/api/v1/plans/{account_id}/{plan_id}` | Update a plan |
| `PATCH` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` | Update a task status |
| `DELETE` | `/api/v1/plans/{account_id}/{plan_id}` | Soft-delete (archive) a plan |
| `GET` | `/api/v1/plans/{account_id}/{plan_id}/history` | Audit log for a plan |

### New Models: `api/src/kene_api/models/project_plan_models.py`

Pydantic request/response models following `api/src/kene_api/models/strategy_models.py`:
- `ProjectPlanResponse`, `ProjectPlanListResponse`
- `ProjectPlanCreateRequest`, `ProjectPlanUpdateRequest`
- `TaskStatusUpdateRequest`
- `ProjectPlanAuditEntry`, `ProjectPlanAuditLogResponse`

Register the router in `api/src/kene_api/main.py`.

---

## Frontend: Calendar Page

The project planning frontend is a new **Calendar Page** following the Figma design at `https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism`. The Figma design currently uses "Tactic Groups" which will be replaced with "Projects" from our data model.

### Page Structure

**File:** `frontend/src/pages/CalendarPage.tsx`

The page supports two view modes toggled by radio buttons:

**Calendar View (default):**
- Monthly grid showing tasks on their `due_date` / `launch_time_utc`
- Each task cell shows: title, platform badge (color-coded per the Figma platform color map), status badge, assignee
- Tasks color-coded by platform (Paid Search = oranges, Social = blues, Email = greens, Display = purples, Content = teals)
- Month/year navigation with `MonthYearPicker` component
- Click a task cell to open the detail panel

**List View:**
- Sortable table of tasks with columns: title, project, campaign, platform, status, assignee, due date, launch time, cost, tags
- Sortable/filterable by any column

**Filter Bar:**
- Filter by **Project** (replaces "Tactic Group" from Figma)
- Filter by **Campaign** (new grouping level above project)
- Filter by platform, status, assignee, tags

**Add Button:**
- Dropdown with options: Add Task, Add Project (replaces Figma's `BatchActivityWizard`)

### Detail Panel (Right Slider)

**File:** `frontend/src/components/ActivityDetailPanel.tsx`

When a task is selected (click in calendar or list), a right-side sliding panel appears showing:
- Task title (editable)
- Project name (links to project)
- Campaign name (if set)
- Status with transition controls (dropdown matching the status flow)
- Assignee (with agent/human badge)
- Platform
- Cost (formatted as currency)
- Due date + launch time (UTC)
- Tags (editable chips)
- Dependencies (list of blocking tasks with their statuses)
- Revision comment / feedback (visible when status = "Revision Requested")
- Completion notes
- Created/updated metadata

### Project Edit Drawer

**File:** `frontend/src/components/ProjectEditDrawer.tsx` (replaces `GroupEditDrawer` from Figma)

Drawer for editing project-level properties:
- Project title, goal, acceptance criteria
- Campaign assignment
- Project-level tags
- Bulk task property editing (apply shared changes across multiple tasks)

### Supporting Files

- `frontend/src/services/projectPlanService.ts` — API client for plan CRUD
- `frontend/src/types/projectPlan.ts` — TypeScript types (with branded IDs per C-5)
- `frontend/src/contexts/ProjectPlanContext.tsx` — React context for plan state (follows `ActivitiesContext` pattern from Figma)
- Route in `frontend/src/App.tsx`
- Navigation entry in sidebar (calendar icon)

### Chat Integration

When the agent creates a plan, the chat response should include a clickable link: "Your project plan has been created. [View Plan](/calendar?project={plan_id})".

---

## Task Orchestration: Dependency Resolution & Notifications

A core requirement is a system that observes task completions, analyzes the dependency graph, and triggers the next tasks. This section describes the recommended approach.

### Problem Statement

Consider a 3-task Instagram ad project:
1. **Agent 1** creates the ad creative (assignee: agent)
2. **Human** reviews and approves the ad (assignee: human)
3. **Agent 2** deploys the ad to Instagram Ads (assignee: agent)

The system must:
- Automatically start Task 1 when the project is activated
- Notify the human when Task 1 completes and Task 2 is unblocked
- Support iterative feedback: human can request revisions, sending Task 1 back for rework
- Notify/trigger Agent 2 when Task 2 is approved (Task 3 unblocked)

### Recommended Architecture: Event-Driven Task Orchestrator

> **Note:** This section covers event-driven orchestration only — i.e., "when task A finishes, dispatch task B." Time-based triggering (firing a task at `due_date + launch_time_utc`) is **not** covered here and is the subject of [PRD-6 — Time-Based Scheduler](./components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md).

#### Component: `TaskOrchestrator` service

**File:** `api/src/kene_api/services/task_orchestrator.py`

A service that runs on every task status change and determines what should happen next.

**Core Logic — `on_task_status_change(plan_id, task_id, new_status)`:**

```
1. Load the project plan from Firestore
2. Update the task's status
3. If new_status is "Complete" or "Approved":
   a. Find all tasks whose `depends_on` includes this task_id
   b. For each downstream task, check if ALL its dependencies are now met
   c. If all dependencies met → mark downstream task as "unblocked"
   d. For unblocked agent tasks → dispatch to the assigned agent
   e. For unblocked human tasks → create in-app notification via NotificationService
4. If new_status is "Revision Requested":
   a. Identify the upstream agent task that produced this work
   b. Set upstream task back to "Draft" with the revision_comment
   c. Dispatch the agent to re-execute with the feedback
5. If new_status is "Rejected":
   a. Mark all downstream tasks as "blocked"
   b. Notify project owner
6. Persist updated plan to Firestore
7. Log audit entry
```

#### Triggering the Orchestrator

The orchestrator is invoked from two entry points:

1. **API endpoint** — when a human updates a task status via the frontend:
   - `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}` calls `TaskOrchestrator.on_task_status_change()`

2. **Agent tool** — when an agent completes a task:
   - `update_task_status` ADK tool calls the same orchestrator logic

Both paths converge on the same orchestrator to ensure consistent behavior.

#### Agent Task Dispatch

When the orchestrator determines an agent task is unblocked:

1. Create a new agent session (or reuse existing) via `AgentEngineClient`
2. Construct a prompt containing:
   - The task description
   - Any revision comments (if this is a re-execution after feedback)
   - Relevant context from the project plan (goal, related task outputs)
   - The `account_id` for org context loading
3. Invoke the appropriate agent via the existing dispatch handler pattern
4. On agent completion, the agent calls `update_task_status(status="Awaiting Approval")` or `update_task_status(status="Complete")` depending on whether the task requires human review

#### Human Notification

When the orchestrator determines a human task is unblocked, it uses the **existing Firestore-based notification system** (`api/src/kene_api/services/notification_service_v2.py`) rather than sending emails directly.

**How it works:**

1. Call `NotificationService.create_notification()` with:
   - `account_id`: from the project plan
   - `category`: A new `NotificationCategory` value — add `"Task Ready"` to the existing enum (currently: Data Quality Alert, News & Press, Industry News, Competitor Activities, Scheduled Report Status, KPI Performance, New Features)
   - `description`: e.g., "Task ready for review: Review Instagram ad creative"
   - `data`: JSON payload containing `plan_id`, `task_id`, `task_title`, `upstream_task_summary`, `action_required`, and a deep link path `/calendar?project={plan_id}&task={task_id}`

2. The notification appears in the existing `NotificationSidebar` component (`frontend/src/components/notifications/NotificationSidebar.tsx`) with the unread badge indicator

3. When the user clicks the notification, the `onNotificationClick` handler navigates to the calendar page with the task detail panel open

**Changes required to the existing notification system:**

- Add `"Task Ready"` to `NotificationCategory` enum in `api/src/kene_api/models/kene_models.py`
- Add corresponding icon and color mappings in `frontend/src/types/notification.types.ts` (`NOTIFICATION_ICONS`, `NOTIFICATION_CATEGORY_COLORS`, `NOTIFICATION_CATEGORY_BG_COLORS`)
- Add click-through navigation in `NotificationSidebar.tsx` — when a "Task Ready" notification is clicked, navigate to the deep link in `data`

**Files involved:**
- `api/src/kene_api/services/notification_service_v2.py` — existing service, no changes needed (generic `create_notification` already supports custom categories)
- `api/src/kene_api/repositories/firestore_notification_repository.py` — existing Firestore persistence, no changes needed
- `api/src/kene_api/models/kene_models.py` — add `"Task Ready"` category
- `frontend/src/types/notification.types.ts` — add icon/color for new category
- `frontend/src/components/notifications/NotificationSidebar.tsx` — add deep link navigation for task notifications

#### Revision Loop (Human ↔ Agent Iteration)

The revision flow handles the case where a human requests changes:

```
Agent creates ad → status: "Awaiting Approval"
  → Human reviews → status: "Revision Requested" + revision_comment: "Make the headline bolder"
    → Orchestrator sets agent task back to "Draft" with the feedback
    → Orchestrator re-dispatches agent with the revision comment
      → Agent revises ad → status: "Awaiting Approval"
        → Human approves → status: "Approved"
          → Orchestrator unblocks downstream tasks
```

The `revision_comment` field on `PlanTask` carries the feedback between iterations. Each revision cycle is logged in the audit trail.

#### Plan Activation

When a project plan transitions from `draft` to `active`:

1. Identify all root tasks (tasks with no `depends_on` entries)
2. For agent root tasks → dispatch immediately
3. For human root tasks → send notification

This is triggered by a `POST /api/v1/plans/{account_id}/{plan_id}/activate` endpoint.

### Additional API Endpoints for Orchestration

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/activate` | Activate plan, start root tasks |
| `POST` | `/api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}/revision` | Submit revision feedback |

---

## Implementation Phases

### Phase 1: Data Model & API (2-3 days)
1. Create `api/src/kene_api/models/project_plan_models.py` with Pydantic models and DAG validator
2. Create `api/src/kene_api/routers/project_plans.py` with CRUD endpoints
3. Register router in `api/src/kene_api/main.py`
4. Write unit tests for models (DAG validation, status transitions) and integration tests for API endpoints

### Phase 2: Agent & Tools (2-3 days)
1. Create `app/adk/agents/project_planning_agent.py` (LlmAgent with instruction, tools, callbacks)
2. Create `app/adk/agents/project_planning_tools.py` (save/update/get tools)
3. Register agent in `app/adk/agents/registry.py`
4. Add dispatch handler in `app/adk/agents/utils/dispatch_handlers.py`
5. Add `create_project_plan` tool to root agent in `app/adk/agents/ken_e_agent.py`
6. Create Firestore config document for the planning agent
7. Write unit tests for tools and agent wiring

### Phase 3: Calendar Page Frontend (3-4 days)
1. Create `CalendarPage.tsx` with calendar and list view toggle
2. Create `ActivityDetailPanel.tsx` (right slider) for task details
3. Create `ProjectEditDrawer.tsx` for project-level editing
4. Create `ProjectPlanContext.tsx` for state management
5. Create `projectPlanService.ts` API client and `projectPlan.ts` types
6. Add route and sidebar navigation
7. Implement filters (project, campaign, platform, status, tags)
8. Write component tests

### Phase 4: Task Orchestration (3-4 days)
1. Create `api/src/kene_api/services/task_orchestrator.py`
2. Implement dependency resolution logic (unblocking, status propagation)
3. Implement agent task dispatch (reuse existing `AgentEngineClient` pattern)
4. Integrate with existing notification system: add `"Task Ready"` category to `NotificationCategory` enum, add icon/color mappings in frontend, add deep link navigation in `NotificationSidebar`
5. Implement revision loop (human feedback → agent re-execution)
6. Add `/activate` and `/revision` API endpoints
7. Write unit tests for orchestrator logic and integration tests for end-to-end flows

### Phase 5: Integration Testing & Polish (1-2 days)
1. End-to-end test: user asks for plan in chat → agent generates → saves → calendar page displays → activate plan → agent executes tasks → human reviews → orchestrator triggers next tasks
2. Test access control, versioning, audit trail
3. Test DAG validation edge cases
4. Test revision loop with multiple iterations
5. Performance testing with plans of varying sizes

---

## Risks

| Risk | Mitigation |
|------|------------|
| Agent produces invalid dependency graph (cycles) | Pydantic DAG validator catches cycles; agent re-prompted with error |
| Agent assigns tasks to non-existent agents | Validate `assignee_name` against agent registry for agent-type tasks |
| Revision loop runs indefinitely | Cap revision iterations (e.g., max 5); escalate to human after limit |
| Agent task dispatch fails mid-plan | Orchestrator marks task as failed; notifies project owner; plan continues with remaining independent tasks |
| Notification not seen by user | Existing notification system is polling-based (not real-time); unread badge on sidebar draws attention; future: add Firestore real-time listeners for push |
| Human never acts on notification | Future: add escalation rules, periodic reminder notifications, deadline alerts |
| Prompt injection via task descriptions or revision comments | Existing `adk_before_tool_callback` security hook applies; sanitize revision comments before injecting into agent prompts |

---

## Verification Plan

1. **Unit tests:** DAG validation (valid graphs, cycle detection, missing refs), Pydantic model serialization, status transition rules, orchestrator dependency resolution logic
2. **Integration tests:** API CRUD operations, access control, versioning, audit trail, orchestrator end-to-end with mock agent dispatch
3. **Agent tests:** Planning agent produces valid JSON matching the schema, `save_project_plan` tool persists correctly
4. **Orchestration tests:** Task completion triggers correct downstream unblocking; revision loop correctly re-dispatches agent with feedback; notification emails sent for unblocked human tasks
5. **Manual E2E test:** Open chat → ask "Create a project plan for an Instagram ad campaign" → verify plan appears in calendar page → activate plan → verify agent executes first task → verify human receives notification → submit revision → verify agent re-executes → approve → verify downstream task triggers

---

## Key Files to Create or Modify

| Action | File |
|--------|------|
| **Create** | `api/src/kene_api/models/project_plan_models.py` |
| **Create** | `api/src/kene_api/routers/project_plans.py` |
| **Create** | `api/src/kene_api/services/task_orchestrator.py` |
| **Create** | `app/adk/agents/project_planning_agent.py` |
| **Create** | `app/adk/agents/project_planning_tools.py` |
| **Create** | `frontend/src/pages/CalendarPage.tsx` |
| **Create** | `frontend/src/components/ActivityDetailPanel.tsx` |
| **Create** | `frontend/src/components/ProjectEditDrawer.tsx` |
| **Create** | `frontend/src/contexts/ProjectPlanContext.tsx` |
| **Create** | `frontend/src/services/projectPlanService.ts` |
| **Create** | `frontend/src/types/projectPlan.ts` |
| **Modify** | `app/adk/agents/registry.py` — register new agent |
| **Modify** | `app/adk/agents/ken_e_agent.py` — add tool + instruction |
| **Modify** | `app/adk/agents/utils/dispatch_handlers.py` — add dispatch handler |
| **Modify** | `app/adk/tools/registry/config/tools.yaml` — register planning tools |
| **Modify** | `api/src/kene_api/main.py` — register router |
| **Modify** | `frontend/src/App.tsx` — add route |

### Figma Design Reference

- **Figma Make:** `https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism`
- **Key Figma components to adapt:** `CalendarPage.tsx`, `ActivityDetailPanel.tsx`, `GroupEditDrawer.tsx` (→ `ProjectEditDrawer`), `calendarData.ts`, `ActivitiesContext.tsx`
- **Terminology mapping:** "Tactic" → Task, "Tactic Group" → Project, "Edit Group" → "Edit Project"
