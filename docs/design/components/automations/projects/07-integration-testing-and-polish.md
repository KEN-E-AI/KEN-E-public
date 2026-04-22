# A-PRD-7 — Integration Testing & Polish

**Status:** Ready for development (after A-PRDs 1–6 merge)
**Owner team:** QA + the team that finishes its A-PRD first
**Blocked by:** A-PRDs 1, 2, 3, 4, 5, 6
**Estimated effort:** 1–2 days

---

## 1. Context

Once the foundation, scheduler, artifact system, test mode, list page, and details page are all merged, the Automations feature must be exercised end-to-end against real services to confirm the seams hold. This PRD owns that closing-out work — no new features, just verification, edge-case coverage, and polish.

## 2. Scope

### In scope
- E2E test that walks the full user journey (create automation → schedule → fires → all tasks run → outputs visible → test mode halt + resume)
- Edge-case suites: cron + DST, overlapping runs, downtime backfill, artifact size cap, lifecycle deletion, pagination correctness
- Performance test with realistic counts (1,000 automations, 50-node DAG, large run history)
- Documentation polish: parent plan's "Status: shipped" report; in-app help text where the dev sessions revealed gaps
- Observability check: every critical step produces a Weave trace and / or structured log

### Out of scope
- Any new features or new endpoints
- Architectural changes — file bugs back to the relevant A-PRD if found

## 3. Dependencies

All other A-PRDs (1–6) must be merged. A-PRD-7 cannot start before then.

## 4. Test catalog

### E2E happy path (recurring automation)

1. Log in as a test account user; navigate to `/workflows`
2. Create a project plan via chat → mark `save_as_automation=true` → set recurrence to "every minute" via the schedule editor
3. Verify: the new automation appears in the list with `next_run_at ≈ now + 1min`
4. Wait ~70s → verify a new `PlanRun` doc was created (visible via the runs list endpoint)
5. Wait for all agent tasks to dispatch and complete → verify each task generated artifacts (visible in the Outputs tab)
6. Wait another minute → verify a second `PlanRun` was created
7. Open Automation Details page → verify the DAG diagram renders, schedule summary is correct, and the Outputs tab on each agent task shows artifacts from both runs

### E2E test mode

1. Open Automation Details page for an automation that includes a HITL task
2. Click "Test Run" → verify a `PlanRun` with `is_test=true` was created and the first agent task dispatches
3. Wait until the orchestrator reaches the HITL task → verify the task halts (status `Awaiting Approval`), the diagram node pulses, and a notification appears with `is_test=true` badge
4. Open the right panel for the HITL task → verify "Mark Complete" button is visible
5. Click "Mark Complete" → verify downstream agent tasks dispatch
6. Run completes → verify Outputs tab shows artifacts for the test run, badged as "Test"
7. Trigger a second test run → click "Cancel" mid-flight → verify run status becomes `cancelled` and pending dispatches are dropped

### Edge-case suites

**Recurrence + DST:**
- `recurrence_cron="30 2 * * *"` in `America/Los_Angeles` on the spring-forward Sunday → fire happens correctly (no double-fire, no skip)
- `recurrence_cron="30 1 * * *"` on fall-back Sunday → fires once at 1:30am even though 1:30am occurs twice
- `recurrence_cron="0 9 * * MON"` in `Europe/London` across the GMT/BST boundary

**Overlapping runs:**
- Trigger a manual run while a scheduled run of the same automation is in flight → both runs proceed independently
- Two concurrent ticks fire the same automation → exactly ONE PlanRun is created (transaction guard)

**Downtime backfill:**
- Stop the scheduler, wait 1 hour, restart → verify each automation fires exactly once on the next tick (not 60 times)

**Artifact size cap:**
- Agent tries to upload a 150MB file → 413 + run continues without that artifact + audit log entry
- Agent uploads a 100MB file (exact limit) → success
- Agent uploads 0 bytes → reject with clear error

**Artifact lifecycle:**
- Upload artifact → set GCS object age to 31 days (test bucket with 1-day rule) → verify object is gone, Firestore metadata remains as tombstone
- Frontend Outputs tab handles tombstoned artifacts gracefully (grayed-out download button)

**Pagination correctness:**
- Create 100 automations → walk pagination cursor → verify 100 unique items returned, no duplicates, no skips
- Apply a filter mid-pagination → verify cursor resets

**Access control:**
- User from account A cannot view, modify, run, test, or cancel an automation from account B (every endpoint)

**HITL completion concurrency:**
- Two users mark the same HITL task complete simultaneously → one wins, the other gets a clear conflict error; orchestrator dispatches downstream exactly once

### Performance

- Automations list with 1,000 entries: < 1s to first interaction (cursor pagination must work)
- DAG diagram with 50 nodes: render in < 500ms; smooth drag at 60fps
- Test run kickoff: API responds in < 500ms (BackgroundTask handles dispatch)
- Scheduler endpoint scan with 10,000 automations across 100 accounts: < 5s

### Observability check

- Every PlanRun creation produces a Weave trace tagged with `is_test`, `triggered_by`
- Scheduler endpoint logs `automations_due_count`, `automations_fired_count` per tick
- Failed agent dispatches log a clear error with `plan_id`, `run_id`, `task_id`, `account_id`
- Artifact uploads log size, mime type, agent name
- Pick 5 random recent test runs → confirm the trace is complete end-to-end

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `tests/integration/test_automation_e2e.py` (full happy-path walkthrough) |
| Create | `tests/integration/test_automation_edge_cases.py` (DST, overlap, backfill, size cap) |
| Create | `tests/integration/test_artifact_lifecycle_e2e.py` (uses test bucket with short-TTL rule) |
| Create | `tests/load_test/locustfile_automations.py` (list page + scheduler scan) |
| Modify | `frontend/src/pages/AutomationDetailsPage.tsx` — add any in-app help text or empty-state copy revealed during testing |
| Modify | `docs/design/components/automations/README.md` — append a "Status: shipped" section at the top with link to this PRD's verification report |

## 6. Acceptance criteria

1. E2E happy-path test passes against a staging environment with real planning agent + real scheduler
2. E2E test-mode test passes including the halt + manual-resume cycle
3. All edge-case tests pass
4. Performance tests meet targets (or the team agrees on a documented relaxation)
5. Manual smoke from a non-developer user (PM, designer) confirms the page is intuitive
6. Observability spot-checks pass: 5 random recent runs in Weave have complete traces
7. A short verification report is added to the component `README.md` linking each A-PRD to its verifying test

## 7. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Real-agent E2E is flaky due to LLM nondeterminism | Use a fixed seed where possible; assert structure (artifact present, valid mime) rather than exact content |
| DST tests depend on real time | Use the `now` override on the scheduler endpoint to simulate firing across DST boundaries |
| Test bucket lifecycle delays | Use a separate test bucket configured with a 1-day rule; for the test, mock the GCS lifecycle clock if available, or run as a long-cycle nightly test |
| Bugs found that cross A-PRD boundaries | File against the most-likely owner; coordinate fixes via the affected teams; do not reimplement here |
| Performance targets not met | Document gaps; file follow-up tickets; do not block ship if targets are close (<2x) |

## 8. Reference

- Parent plan: [`../README.md`](../README.md) §6 (Verification plan)
- All sibling PRDs: [01](./01-data-model-and-api.md), [02](./02-recurring-scheduler.md), [03](./03-task-artifact-system.md), [04](./04-test-dry-run-mode.md), [05](./05-automations-list-page.md), [06](./06-automation-details-page.md)
- Calendar verification reference: [Calendar PRD-5](../../project-tasks/projects/PR-PRD-05-integration-testing-and-polish.md)
- CLAUDE.md rules in scope: T-3, T-5 (integration tests preferred over heavy mocking)
