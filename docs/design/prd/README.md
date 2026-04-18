# Project Planning Feature — PRDs

This directory contains the PRDs for the Project Planning feature. The work is split into **6 independently shippable PRDs** that map (with one addition) to the phases in [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md).

## Why 6 PRDs

The original implementation plan bundles five phases into one document. Splitting them lets multiple dev teams work in parallel and shrinks the surface area each team needs to hold in their head.

PRD-6 is **net-new**: while reviewing the plan, we identified that nothing in it actually fires a task at its scheduled `due_date + launch_time_utc`. The plan only handles event-driven orchestration ("task A finished → start task B"). KEN-E has no scheduler infrastructure today (no Cloud Scheduler, Cloud Tasks, APScheduler, etc.), so a dedicated PRD is needed to build it.

## Dependency graph

```
PRD-1: Data Model & API  ──┬──> PRD-2: Planning Agent & Tools ─┐
  (BLOCKING — ships first) ├──> PRD-3: Calendar Page Frontend ─┤
                           ├──> PRD-4: Event-Driven Orchestrator┤──> PRD-5: Integration Testing
                           └──> PRD-6: Time-Based Scheduler ────┘    (closes out)
```

| # | PRD | Owner team | Blocked by | Parallel with |
|---|-----|------------|------------|---------------|
| 1 | [Data Model & API](./01-data-model-and-api.md) | Backend (foundation) | — | — |
| 2 | [Planning Agent & Tools](./02-planning-agent-and-tools.md) | Agent / ML | PRD-1 | 3, 4, 6 |
| 3 | [Calendar Page Frontend](./03-calendar-page-frontend.md) | Frontend | PRD-1 | 2, 4, 6 |
| 4 | [Event-Driven Orchestrator](./04-event-driven-orchestrator.md) | Backend | PRD-1 | 2, 3, 6 |
| 5 | [Integration Testing & Polish](./05-integration-testing-and-polish.md) | QA + first-finished team | PRDs 1–4, 6 | — |
| 6 | [Time-Based Scheduler](./06-time-based-scheduler.md) | Backend / Infra | PRD-1 | 2, 3, 4 |

## Recommended workflow

1. **Sprint 1:** Backend team ships PRD-1. Other teams stay engaged by reviewing the data contract and stubbing their own work against the published Pydantic schema.
2. **Sprint 2–3:** Once PRD-1 merges, kick off PRDs 2, 3, 4, and 6 in parallel — four teams, no blocking dependencies between them. Coordinate only on the small integration touchpoint between PRD-3 and PRD-4 (the notification-deep-link snippet in `NotificationSidebar.tsx`).
3. **Sprint 4:** PRD-5 closes out with end-to-end testing once everything else is merged.

## Standard PRD shape

Every PRD in this directory follows the same structure:

1. **Context** — problem this PRD solves
2. **Scope** — explicit in/out
3. **Dependencies** — other PRDs, files, services
4. **Data contract** — Pydantic / TypeScript types owned or consumed
5. **Implementation outline** — files to create / modify (table)
6. **API contract** — endpoints (where applicable)
7. **Acceptance criteria** — what "done" means
8. **Test plan** — unit / integration / E2E coverage
9. **Risks & open questions**
10. **Reference** — links back to the parent plan and any Figma designs

## Reference

- Parent plan: [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md)
- Figma design: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism)
- Terminology mapping: "Tactic" → Task, "Tactic Group" → Project, "Edit Group" → "Edit Project"
