# Automations — Implementation Plan

> **Status (2026-04-17):** This plan has been split into 7 independently shippable PRDs in [`prd/`](./prd/) for parallel execution by multiple dev teams. See [`prd/README.md`](./prd/README.md) for the dependency graph and team workflow.
>
> **Prerequisite:** This plan assumes the 6 [Project Planning PRDs](../prd/README.md) are shipped. Automations build directly on top of `ProjectPlan` / `PlanTask` / `TaskOrchestrator` / Cloud Scheduler infrastructure delivered there.

---

## 1. Context

The Project Planning feature treats a `ProjectPlan` as a **one-shot DAG** — created, activated, run to completion, archived. Automations turn that one-shot model into a **template** that can be re-executed on a recurring schedule, on demand, or in a "test" mode that lets a user verify outputs before turning the automation loose.

A user marks a project as an automation by setting `save_as_automation = true`. Each subsequent execution creates a new `PlanRun` document (with its own task statuses, dispatches, and generated artifacts), while the parent `ProjectPlan` remains the immutable-ish recipe.

### What's new vs. the Calendar feature

| Concern | Calendar (today) | Automations (this plan) |
|---------|------------------|--------------------------|
| Plan lifetime | One-shot | Template that's re-run |
| Execution record | Lives on the `ProjectPlan` itself | New `PlanRun` doc per execution |
| Scheduling | Per-task `launch_time_utc` (absolute) | Per-automation `recurrence_cron` (recurring) |
| Task outputs | Free-form completion notes | Structured GCS artifacts with 30-day TTL |
| Validation before activation | Activate → ship | "Test Run" mode halts at HITL gates |
| Frontend | Calendar grid view | Dedicated list + DAG details page |

## 2. Architectural overview

```
┌────────────────────┐                                  ┌─────────────────────┐
│  ProjectPlan       │  save_as_automation=true,        │  PlanRun            │
│  (template)        │──recurrence_cron, recurrence_tz─▶│  (execution)        │
│                    │                                  │  triggered_by:      │
│  tasks[]           │  scheduler tick                  │    scheduled │      │
│  recurrence_cron   │  ──────────────────────▶         │    manual    │      │
│  next_run_at       │  (clones template into a run)    │    test             │
└────────────────────┘                                  │  task_states[]      │
                                                        │  artifacts[] ───────┼──▶ GCS
                                                        └─────────────────────┘     (30d TTL)
                                                                  │
                                                                  ▼
                                                        TaskOrchestrator
                                                        (PRD-4 of Calendar set,
                                                         extended for runs +
                                                         test mode)
```

Three architectural pillars:

1. **Template/run split** — `ProjectPlan` becomes the recipe; `PlanRun` is the execution record. The orchestrator is taught to operate on either (legacy plans = template-only; automation runs = the run doc). This is the single biggest change.
2. **Recurrence engine** — A new internal scheduler endpoint runs alongside [PRD-6](../prd/06-time-based-scheduler.md). Every minute it finds automations whose `next_run_at <= now`, clones the template into a new `PlanRun`, computes the next fire from the cron expression, and hands the run to the orchestrator.
3. **Artifact system** — Tasks generate files (text, JSON, image, short video). Files are persisted to a dedicated GCS bucket with a 30-day lifecycle rule, and downstream agent tasks receive signed-URL references to upstream artifacts in their prompts.

### Test mode flow

```
User clicks "Test Run" on Automation Details page
  │
  ▼
POST /runs/test  →  PlanRun{is_test=true} created
  │
  ▼
TaskOrchestrator.activate_plan(run_id, is_test=True)
  │
  ├─▶ agent task    → dispatch as normal, save artifact
  │
  └─▶ HITL task     → halt; status="Awaiting Approval"; notification
                      ▲
                      │ user clicks task in UI, marks Complete
                      │
                      └── orchestrator continues downstream
```

## 3. Data model extensions

Full detail in [PRD-1](./prd/01-data-model-and-api.md). Headlines:

**`ProjectPlan` (extended):**
- `save_as_automation: bool`
- `recurrence_cron: str | None` — 5-field cron, e.g., `"0 9 * * MON"`
- `recurrence_timezone: str` — IANA name, e.g., `"America/Los_Angeles"`
- `last_run_at: datetime | None`
- `last_run_id: str | None`
- `next_run_at: datetime | None` — computed by the scheduler

**`PlanRun` (new):**
- `run_id`, `account_id`, `template_plan_id`
- `triggered_by: Literal["scheduled", "manual", "test"]`
- `is_test: bool`
- `status: RunStatus` (pending / running / halted_for_human / complete / failed / cancelled)
- `task_states: list[TaskRunState]` — per-task execution status (status, started_at, completion_notes, revision_iteration)

## 4. API surface (summary)

| Method | Path | PRD |
|--------|------|-----|
| GET | `/api/v1/automations/{account_id}` | 1 |
| GET | `/api/v1/automations/{account_id}/{plan_id}` | 1 |
| PATCH | `/api/v1/automations/{account_id}/{plan_id}/recurrence` | 1 |
| GET | `/api/v1/automations/{account_id}/{plan_id}/runs` | 1 |
| GET | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}` | 1 |
| POST | `/api/v1/automations/{account_id}/{plan_id}/runs` (manual) | 2 |
| POST | `/api/v1/automations/{account_id}/{plan_id}/runs/test` | 4 |
| POST | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/cancel` | 4 |
| GET | `…/runs/{run_id}/tasks/{task_id}/artifacts` | 3 |
| GET | `…/tasks/{task_id}/artifacts/recent` | 3 |
| POST | `/api/v1/internal/scheduler/launch-due-automations` (OIDC) | 2 |

## 5. Implementation phases

The phases map 1:1 to the PRDs.

| Phase | PRD | Owner | Estimated effort |
|-------|-----|-------|-------------------|
| 1 | [Data Model & API Extensions](./prd/01-data-model-and-api.md) | Backend (foundation) | 2–3 days |
| 2 | [Recurring Scheduler & Run Engine](./prd/02-recurring-scheduler.md) | Backend / Infra | 3 days |
| 3 | [Task Artifact System](./prd/03-task-artifact-system.md) | Backend + Agent | 3–4 days |
| 4 | [Test/Dry-Run Mode](./prd/04-test-dry-run-mode.md) | Backend | 2 days |
| 5 | [Automations List Page](./prd/05-automations-list-page.md) | Frontend | 2 days |
| 6 | [Automation Details Page](./prd/06-automation-details-page.md) | Frontend | 4–5 days |
| 7 | [Integration Testing & Polish](./prd/07-integration-testing-and-polish.md) | QA + first-finished team | 1–2 days |

Phase 1 is blocking. Phases 2, 3, 5, 6 run in parallel after Phase 1 merges. Phase 4 depends on Phase 3 (test mode is most useful with artifacts visible). Phase 7 closes out.

## 6. Verification plan

A short verification report should be appended at the bottom of this plan when all 7 PRDs ship. Each PRD's acceptance criteria → its verifying test.

## 7. Risks

| Risk | Mitigation |
|------|------------|
| Orchestrator API change ripples back into shipped Calendar code | Coordinate with the team that owns Calendar PRD-4 in the same sprint as Automations PRD-2; gate behind run_id presence (None = legacy template behavior) |
| Cron + DST correctness | Use `croniter` with explicit IANA timezone; integration test covers DST transitions |
| Artifact storage cost runs away | 30-day GCS lifecycle rule + 100MB cap per artifact; signed URLs to avoid API-server proxying; dashboard for bucket size |
| Overlapping runs of the same automation interfere | Each run is its own Firestore doc with its own task_states; orchestrator never reads from the template during a run |
| Backfill on server downtime fires N missed runs | Documented policy: only the next single run fires after recovery, never a backlog |

## 8. Reference

- Calendar PRDs: [`../prd/`](../prd/)
- Calendar implementation plan: [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) (Workflows page, Automations tab)
