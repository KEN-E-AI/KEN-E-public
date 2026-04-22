# PRD-5 — Integration Testing & Polish

**Status:** Ready for development (after PRDs 1–4 + 6 merge)
**Owner team:** QA + the team that finishes its PRD first
**Blocked by:** PRDs 1, 2, 3, 4, 6
**Estimated effort:** 1–2 days

---

## 1. Context

Once the foundation, agent, frontend, orchestrator, and scheduler are all merged, the project planning feature must be exercised end-to-end against real services to confirm the seams hold together. This PRD owns that closing-out work — no new features, just verification, edge-case coverage, and polish.

## 2. Scope

### In scope
- E2E test that walks the full user journey (chat → plan → calendar → activate → agent execution → human review → orchestrator → revision → time-based fire)
- Edge-case suites for DAG validation, revision loop, scheduler, access control
- Performance test with realistic plan sizes
- Documentation polish (README updates, in-app help text where missing)
- Observability check: logs and traces are present at each major step

### Out of scope
- Any new features or new endpoints
- Architectural changes — file bugs back to the relevant PRD if found

## 3. Dependencies

All other PRDs (1, 2, 3, 4, 6) must be merged. PRD-5 cannot start before then.

## 4. Test catalog

### E2E happy path
1. Open the chat page; log in as a test account user
2. Send: "Create a project plan for an Instagram ad campaign launching next Tuesday at 1pm UTC"
3. Verify: the planning agent runs (visible in Weave trace), `save_project_plan` is called, the chat response includes a `[View Plan]` link
4. Click the link → calendar page opens with the plan focused
5. Open the project edit drawer → verify goal, acceptance criteria, tasks render correctly
6. Click "Activate plan" → first agent root task is dispatched (orchestrator log entry)
7. Wait for the agent task to complete → verify status changes to "Awaiting Approval", a "Task Ready" notification appears in the sidebar
8. Click the notification → calendar opens with the task detail panel open
9. Click "Request Revision" with comment "make headline bolder" → agent re-runs, status returns to "Awaiting Approval"
10. Click "Approve" → next downstream task dispatches OR a notification appears (depending on assignee)
11. For the time-scheduled task: set `launch_time_utc` to "<one minute from now>", `status="Approved"` → wait ~60s → verify `launched_at` is populated and the orchestrator was invoked

### Edge-case suites

**DAG validation (re-runs PRD-1 unit suite + adds:):**
- Plan with 100 tasks and 200 edges
- Plan with multiple disjoint subgraphs
- Plan where two tasks both have an edge to a third (fan-in)
- Plan where one task has 20 dependents (fan-out)

**Revision loop:**
- 3 successful revision iterations (verify the comment is included in the agent prompt each time, visible in the trace)
- 6th iteration triggers `Failed`; owner notified

**Time-based scheduler:**
- Task fires within 60s of `due_date + launch_time_utc`
- Task with `launch_time_utc IS NULL` fires at UTC midnight of `due_date`
- Two parallel scheduler invocations fire each task exactly once
- A task with `due_date` last week and `launched_at` already set is not re-fired
- A task whose orchestrator hand-off fails: status is `Failed`, no auto re-fire

**Access control:**
- User from account A cannot view, modify, or delete a plan from account B (verify on every endpoint)

**Audit & versioning:**
- Every status change appears in the audit log with actor, timestamp, old/new
- PUT on a plan creates a new version snapshot; history endpoint returns all versions

### Performance
- Calendar page load with 50 plans / 500 tasks: < 2s to first interaction
- Plan list with filters applied: re-renders in < 200ms
- Scheduler endpoint scan with 10,000 tasks across 100 accounts: < 5s

### Observability check
- Every orchestrator invocation produces a Weave trace
- Scheduler endpoint logs `tasks_fired` count per tick
- Failed agent dispatches log a clear error with `plan_id`, `task_id`, `account_id`

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `tests/integration/test_project_plan_e2e.py` (full happy-path walkthrough) |
| Create | `tests/integration/test_project_plan_edge_cases.py` (DAG, revision cap, scheduler edge cases) |
| Create | `tests/load_test/locustfile_project_plans.py` (calendar load + scheduler scan) |
| Modify | `frontend/src/pages/CalendarPage.tsx` — add any in-app help text or empty-state copy revealed during testing |
| Modify | `docs/design/project-planning-implementation-plan.md` — append a "Status: shipped" section at the top with link to this PRD's verification report |

## 6. Acceptance criteria

1. E2E happy-path test passes against a staging environment with a real planning agent
2. All edge-case tests pass
3. Performance tests meet the targets above (or the team agrees on a documented relaxation)
4. Manual smoke from a non-developer user (PM, designer) confirms the calendar page is intuitive
5. Observability spot-checks pass: pick 5 random recent runs in Weave and confirm the trace is complete
6. A short verification report is added to `docs/design/project-planning-implementation-plan.md` linking each PRD to its verifying test

## 7. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Real-agent E2E is flaky due to LLM nondeterminism | Use a fixed seed where possible; assert structure (valid JSON, has tasks) rather than exact content |
| Scheduler test depends on real time | Use the `now` override on the endpoint to simulate firing |
| Bugs found that cross PRD boundaries | File against the most-likely owner; coordinate fixes via the affected teams; do not reimplement here |
| Performance targets not met | Document gaps; file follow-up tickets; do not block ship if targets are close (<2x) |

## 8. Reference

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Verification Plan, §Implementation Phases (Phase 5)
- All sibling PRDs: [01](./PR-PRD-01-data-model-and-api.md), [02](./PR-PRD-02-planning-agent-and-tools.md), [03](./PR-PRD-03-calendar-page-frontend.md), [04](./PR-PRD-04-event-driven-orchestrator.md), [06](./PR-PRD-06-time-based-scheduler.md)
- CLAUDE.md rules in scope: T-3, T-5 (integration tests preferred over heavy mocking)
