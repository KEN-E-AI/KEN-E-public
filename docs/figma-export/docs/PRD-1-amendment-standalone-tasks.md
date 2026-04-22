# PRD-1 Amendment: Standalone Tasks

**Status:** Draft
**Date:** 2026-04-21
**Affects:** PRD-1 (Projects, Plans, and the DAG), Calendar, Workflows

## Motivation

The original PRD-1 required every task to live inside a project plan (`plans/{plan_id}/tasks/{task_id}`). Users have quick, one-off work — a copy tweak, an asset review, a newsletter draft — that does not belong to any project. Forcing these into ad-hoc "Misc" projects pollutes the project list, hides ownership, and inflates DAG noise.

This amendment introduces **standalone tasks**: tasks that exist outside any plan, with first-class create/read/update/delete and explicit transitions into and out of projects.

## Data model

New collection, parallel to projects/plans:

```
accounts/{account_id}/tasks/{task_id}
```

`Task` shares the existing `CalendarActivity` shape plus a nullable `plan_id`:

- `plan_id: string | null` — `null` means standalone. Non-null means the task lives inside the referenced plan and should be read from `plans/{plan_id}/tasks/{task_id}` instead. This field is **redundant by design** so clients can render a "Unfiled" badge without a join.
- `depends_on` is **omitted** for standalone tasks. The DAG only applies inside a plan; a standalone task has no predecessors or successors.

## API changes

- `POST /tasks` — create standalone task.
- `GET /tasks?owner=…&status=…` — list standalone tasks (filter by owner/status/date range).
- `PATCH /tasks/{task_id}` — update.
- `DELETE /tasks/{task_id}` — delete.

Transition endpoints:

- `POST /tasks/{task_id}/attach` body `{ plan_id }` — atomically: delete from `tasks`, insert into `plans/{plan_id}/tasks` with `depends_on: []`. Idempotent: re-attaching to the same plan is a no-op.
- `POST /plans/{plan_id}/tasks/{task_id}/detach` — atomically: delete from `plans/{plan_id}/tasks`, insert into `tasks` with `plan_id: null`. Cascades: removes `task_id` from every sibling's `depends_on[]`.
- `POST /plans:createFromTasks` body `{ title, goal, task_ids[] }` — creates a new plan, moves the listed standalone tasks into it as unlinked nodes (no dependencies), returns the new `plan_id`.

## DAG validator carve-out

The existing DAG validator (cycle detection, orphan-node check, "every node reachable from a root") runs **only** on `plans/{plan_id}/tasks`. Standalone tasks are explicitly excluded. A standalone task is not an "orphan" in the DAG sense — it is simply not part of any graph.

Consequence: the UI must not present a DAG view for a single standalone task. The calendar-level editor for a standalone task is a plain form, not a graph.

## Consumers

- **Calendar**: merges `plans/*/tasks` and `tasks` into a single list. Standalone tasks render with a dashed border and "Unfiled" label.
- **Audit**: both collections emit events to the same audit stream; `plan_id` on each event disambiguates.
- **Search**: indexer reads both collections; result cards show the "Unfiled" badge when `plan_id === null`.
- **Reports / rollups**: any report scoped to a project continues to read `plans/{plan_id}/tasks`. Reports scoped to an owner or timeframe must union both collections.

## Migration

None required for existing data — all current tasks remain in `plans/*/tasks`. The new `tasks` collection starts empty. No writes change shape.

## Open questions

- Do standalone tasks participate in capacity planning? Proposed: yes, same owner/estimate fields, included in workload totals.
- Can a standalone task block a project task? Proposed: no, `depends_on` is strictly intra-plan. If a user needs a cross-boundary dependency, the standalone task must first be attached.
- Should bulk attach preserve creation order as a linear chain, or drop into the plan as parallel unlinked nodes? Current implementation: parallel unlinked. User wires dependencies in the DAG editor.
