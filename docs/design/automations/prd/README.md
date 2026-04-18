# Automations Feature — PRDs

This directory contains the PRDs for the **Automations** feature, which extends the Calendar by allowing a project to be saved as a re-executable template, scheduled with cron-style recurrence, and validated end-to-end via a "Test Run" mode that produces inspectable artifacts.

> **Prerequisite:** all 6 [Project Planning PRDs](../../prd/README.md) must be shipped before any of these begin. Automations build directly on top of the data model, agent, calendar, orchestrator, and scheduler delivered there.

## Why 7 PRDs

Same logic as the Calendar set: split by team boundary, ship a foundation that publishes the contract first, then run independent pieces in parallel.

The artifact system is large enough to deserve its own PRD (GCS bucket, lifecycle policy, agent-side tooling, downstream prompt injection). The test mode is small but architecturally distinct from recurring scheduling, so it gets its own PRD too — and its dependency on the artifact system is the one non-trivial cross-PRD coupling.

## Dependency graph

```
A-PRD-1: Data Model & API ──┬──> A-PRD-2: Recurring Scheduler ──┐
  (BLOCKING)                ├──> A-PRD-3: Task Artifact System ─┤
                            ├──> A-PRD-5: List Page ────────────┤
                            └──> A-PRD-6: Details Page ─────────┤──> A-PRD-7:
                                                                │     Integration Testing
                            A-PRD-3 ──> A-PRD-4: Test Mode ─────┤
```

| # | PRD | Owner team | Blocked by | Parallel with |
|---|-----|------------|------------|---------------|
| 1 | [Data Model & API Extensions](./01-data-model-and-api.md) | Backend (foundation) | — | — |
| 2 | [Recurring Scheduler & Run Engine](./02-recurring-scheduler.md) | Backend / Infra | A-PRD-1 | 3, 5, 6 |
| 3 | [Task Artifact System](./03-task-artifact-system.md) | Backend + Agent | A-PRD-1 | 2, 5, 6 |
| 4 | [Test/Dry-Run Mode](./04-test-dry-run-mode.md) | Backend | A-PRD-1, A-PRD-3 | 5, 6 |
| 5 | [Automations List Page](./05-automations-list-page.md) | Frontend | A-PRD-1 | 2, 3, 6 |
| 6 | [Automation Details Page](./06-automation-details-page.md) | Frontend | A-PRD-1 (soft: 3, 4) | 2, 3, 5 |
| 7 | [Integration Testing & Polish](./07-integration-testing-and-polish.md) | QA + first-finished team | All others | — |

## Cross-PRD coordination points

A few touchpoints don't fit cleanly inside one PRD and need an owning team to consciously sync:

- **Orchestrator signature change** (A-PRD-2 ↔ Calendar PRD-4): `TaskOrchestrator` methods grow an optional `run_id` parameter. When present, all status reads/writes target the `PlanRun` doc; when absent, legacy template behavior. The Automations PRD-2 team owns the change; the Calendar PRD-4 team must be looped in for review.
- **Right-panel "Outputs" tab** (A-PRD-6 ↔ Calendar PRD-3): The frontend Details page reuses `ActivityDetailPanel`. A-PRD-6 adds a new tab; coordinate with whoever owns that file.
- **Notification routing for HITL halts in test mode** (A-PRD-4 ↔ Calendar PRD-4): Reuse the existing `"Task Ready"` notification category; no new enum value needed.

## Recommended workflow

1. **Sprint 1:** Backend ships A-PRD-1. All other teams stub against the published Pydantic schema.
2. **Sprint 2–3:** A-PRDs 2, 3, 5, 6 run in parallel. A-PRD-4 starts mid-sprint once A-PRD-3 lands.
3. **Sprint 4:** A-PRD-7 closes out with end-to-end testing.

## Standard PRD shape

Every PRD in this directory follows the same structure as the Calendar PRDs:

1. **Context** — problem this PRD solves
2. **Scope** — explicit in/out
3. **Dependencies** — other PRDs, files, services
4. **Data contract** — Pydantic / TypeScript types owned or consumed
5. **Implementation outline** — files to create / modify (table)
6. **API contract** — endpoints (where applicable)
7. **Acceptance criteria** — what "done" means
8. **Test plan** — unit / integration / E2E coverage
9. **Risks & open questions**
10. **Reference** — links back to the parent plan and Calendar PRDs

## Reference

- Parent plan: [`../automations-implementation-plan.md`](../automations-implementation-plan.md)
- Calendar foundation: [`../../prd/`](../../prd/)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) (Workflows page, Automations tab)
