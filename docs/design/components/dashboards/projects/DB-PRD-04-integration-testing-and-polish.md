# DB-PRD-04 — Integration Testing & Polish

**Status:** Blocked — resumes once DB-PRD-01, DB-PRD-02, and DB-PRD-03 all ship
**Owner team:** QA + whichever DB-PRD team finishes first
**Blocked by:** DB-PRD-01, DB-PRD-02, DB-PRD-03
**Blocks:** —
**Estimated effort:** 1–2 days

---

## 1. Context

The three prior PRDs deliver the data model, the list page, and the details page. Each ships with its own unit and integration tests. This PRD is the **end-to-end closing sprint**: cross-component flows, edge cases that are hard to cover inside one PRD, performance targets, and the list-separation guarantee between Automations and Dashboards.

It also performs a final pass on documentation — updating the component README with shipped status, appending a verification report, and ensuring the Automations README correctly cross-references the `type="freeform"` default.

## 2. Scope

### In scope
- **E2E suites** (Playwright): two golden-path flows + four edge cases (disconnected, pending-after-partial-rerun, pending-on-fresh-dashboard, blob-expired, oversize-inline)
- **Performance targets** (automated): 100-placement dashboard GET < 500 ms p95; canvas drag @ 60 fps with 50 tiles; full-canvas PUT < 200 ms p95
- **List-separation tests**: dashboards never appear in the Automations list (and vice versa), including the case of a dashboard with `save_as_automation=true`
- **Artifact edge cases**: 30-day TTL expiry surfacing; `output_config` removed mid-life; Vega-Lite spec >64 KB; 10 MB CSV
- **Multi-user isolation**: two accounts each with a dashboard of the same title — no cross-account leakage
- **Role-matrix verification**: every combination of (viewer, editor, approver, admin) × (each DB-PRD endpoint) × (owning account, foreign account)
- **Observability spot-check**: verify audit entries for placement PUT diffs; Weave traces cover the resolver's Firestore reads
- **Documentation updates**: component README "shipped" section + verification report appended

### Out of scope
- Load testing at account scales beyond the p95 targets below (separate perf PRD if needed later)
- Security pen-testing beyond role matrix (ongoing security-review skill covers this)
- Accessibility audit (separate a11y pass across the product)

## 3. Dependencies

- **DB-PRD-01, DB-PRD-02, DB-PRD-03:** all merged before this PRD starts.
- **A-PRD-04 (Test / Dry-Run Mode) and A-PRD-07 (Automations Integration Testing & Polish):** verify the Automations list defaults (`type="freeform"`) land as part of this PRD's list-separation tests; no new changes required in Automations.
- **DM-PRD-07:** audit log verification relies on its `AuditEntry` schema being live.
- **Existing files to study:**
  - `api/tests/integration/` — existing integration test patterns
  - `frontend/e2e/` — existing Playwright setup
  - `deployment/ci/` — pipeline hooks for E2E + perf gates

## 4. Test plan

### 4.1 End-to-end golden paths (Playwright)

**E2E-1 — Create → add task → pin → run → refresh**

1. Log in (editor role).
2. Navigate to `/performance/dashboards`. Verify empty state.
3. Click "New Dashboard"; title = "Q2 Competitive Landscape"; tags = ["q2", "competitive"]; Create.
4. Land on `/performance/dashboards/{plan_id}`. Verify empty-canvas placeholder.
5. Add a task via the shared `ActivityDetailPanel`: `title="Collect competitor pricing"`, `assignee_type="agent"`, `output_config.enabled=true`, `expected_file_types=["text", "visualization"]`.
6. Click "Pin to dashboard" on the task → select "text" → tile appears top-left on the canvas with `status="pending"` badge.
7. Pin "visualization" similarly → second tile appears.
8. Click "Run" → Run button shows elapsed counter.
9. Wait for `latest_run.status === "complete"` (test harness mock returns in <5 s).
10. Both tiles transition to `status="fresh"`; text widget renders markdown content; visualization widget renders a Vega-Lite chart.
11. Re-run → widgets' `updated_at` ticks forward; no user action required to refresh.

**E2E-2 — Multi-placement layout persistence**

1. From a dashboard with 5 placements, drag three of them to new positions.
2. Reload the page.
3. Verify all five are where the user dropped them (8-px snap enforced).
4. Resize one tile; reload; verify new dimensions.

### 4.2 Edge cases

**Edge-1 — Disconnected placement after `output_config` flip**
- Seed: 1 placement referencing `(task_A, visualization)`.
- Flip `task_A.output_config.enabled = false` via `PATCH .../tasks/{task_id}`.
- Reload the dashboard.
- Expected: placement renders with `status="disconnected"` and a broken-link badge. Tile shows a prompt to remove or reconfigure. Clicking Remove fires a PUT without the placement.

**Edge-2 — Pending placement after partial re-run**
- Seed: run produces `(task_A, visualization)` and `(task_B, text)`.
- Re-run; test harness emits only `(task_A, visualization)` this time.
- Reload.
- Expected: `(task_A, visualization)` is `fresh` with new `updated_at`; `(task_B, text)` is `pending` with `updated_at=null` and no inline payload / download URL. (Per DB-PRD-01 §4.7 — no `stale` status; the resolver does not surface the prior run's text artifact. The user re-runs to refresh.)

**Edge-3 — Pending placement before first run**
- Seed: new dashboard with 2 placements; never run.
- Expected: both placements render with `status="pending"`; spinner badge; widget body shows "Task hasn't produced [file_type] yet. Run the dashboard to generate it."

**Edge-4 — Artifact blob expired (>30 days)**
- Seed: `latest_run` completed 31 days ago; the `TaskArtifact` Firestore doc still exists in the run's `artifacts/` subcollection, but the GCS object has been lifecycled out (30-day TTL per A-PRD-03).
- Expected: GET returns `status="fresh"` (the metadata exists, classifier matches) with a `download_url` signed against the now-missing blob. The widget fetches the URL → GCS 404 → frontend catches the error and renders "Artifact expired — re-run the dashboard to refresh." For inline-eligible artifacts (`text`, `visualization` ≤64 KB), the inline payload itself was never persisted (resolver re-derives it on every GET from the live blob), so the widget displays the same "expired" message rather than serving a stale inline body.

**Edge-5 — Placement exceeds size thresholds**
- Seed: a text artifact of 65 KB; a Vega-Lite spec of 70 KB.
- Expected: neither is inlined; both served via `download_url`; widgets fetch and render without inline payloads.

### 4.3 List-separation

**LS-1 — Dashboard does not appear in Automations list**
- Seed: 3 plans — one `type="freeform"` + `save_as_automation=true`, one `type="dashboard"` + `save_as_automation=true`, one `type="dashboard"` + `save_as_automation=false`.
- `GET /api/v1/automations/{account_id}` returns only the freeform plan.
- `GET /api/v1/dashboards/{account_id}` returns both dashboards.
- `GET /api/v1/automations/{account_id}?type=all` returns all three (debug path).

**LS-2 — Flipping a plan's `type` updates which list it appears in**
- Seed: 1 plan `type="freeform"`, in the Automations list.
- `PUT /api/v1/plans/{account_id}/{plan_id}` with body setting `type="dashboard"`.
- Plan now appears in the Dashboards list; disappears from Automations. Audit entry written for the mutation.

### 4.4 Role matrix

For each of DB-PRD-01's 5 endpoints × 4 roles × 2 account contexts (owning, foreign), assert the response code matches the DM-PRD-07 policy table.

| Endpoint | viewer | editor | approver | admin | cross-account |
|---|---|---|---|---|---|
| `GET /dashboards` | 200 | 200 | 200 | 200 | 403 |
| `GET /dashboards/{id}` | 200 | 200 | 200 | 200 | 403 |
| `POST /dashboards` | 403 | 201 | 201 | 201 | 403 |
| `PUT /placements` | 403 | 200 | 200 | 200 | 403 |
| `DELETE /dashboards/{id}` | 403 | 200 | 200 | 200 | 403 |

Implement as a parameterized Pytest suite in `api/tests/integration/test_dashboards_role_matrix.py`.

### 4.5 Performance targets

**P-1 — 100-placement GET**
- Seed: dashboard with 100 placements, 20 tasks, latest run with 100 artifacts (50 inlined text, 50 signed-URL CSV).
- Measure: `GET /dashboards/{id}` round-trip.
- Target: p95 < 500 ms. Runs 100 iterations. Fails CI if p95 > 500 ms.

**P-2 — Canvas drag FPS**
- 50-tile dashboard; automated drag of one tile across 500 px with `requestAnimationFrame` tracing.
- Target: ≥55 fps sustained during the drag.

**P-3 — Placements PUT**
- 50-placement array submitted via PUT.
- Target: p95 < 200 ms. Runs 100 iterations.

### 4.6 Observability spot-check

- Canvas PUT writes an `AuditEntry` with `action="update"`, `resource_type="project_plan"`, and `diff_summary` describing added/removed/moved placement ids. Verify entry exists after each test run that mutates placements.
- `DashboardArtifactResolver` Firestore reads appear as child spans under the `GET /dashboards/{id}` Weave trace with `placement_count` attribute.
- Every mutating endpoint's 4xx/5xx responses produce a structured log line with `account_id`, `plan_id`, `actor_email`, `action` — for ops/security.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `frontend/e2e/dashboards-golden-path.spec.ts` — E2E-1 + E2E-2 |
| Create | `frontend/e2e/dashboards-edge-cases.spec.ts` — Edge-1 through Edge-5 |
| Create | `api/tests/integration/test_dashboards_role_matrix.py` — §4.4 |
| Create | `api/tests/integration/test_automations_dashboards_list_separation.py` — §4.3 |
| Create | `api/tests/perf/test_dashboards_perf.py` — §4.5 with `pytest-benchmark` |
| Create | `frontend/e2e/dashboards-canvas-perf.spec.ts` — P-2 FPS test via `performance.measure` |
| Modify | `docs/design/components/dashboards/README.md` — append "Shipped 2026-MM-DD" banner, append §8 Verification Report with test run stats |
| Verify | `docs/design/components/automations/README.md` cross-refs `type="freeform"` default cleanly |
| Verify | `PROJECT-PLANNER.md` DB-PRD rows move to `shipped` status |

## 6. Acceptance criteria

1. All six Playwright E2E specs (`dashboards-golden-path`, `dashboards-edge-cases`) pass in CI.
2. `test_dashboards_role_matrix` covers all 40 cells (5 endpoints × 4 roles × 2 account contexts) and passes.
3. `test_automations_dashboards_list_separation` covers the 3 scenarios in §4.3 and passes.
4. Performance suite passes under CI: P-1 p95 < 500 ms, P-2 ≥ 55 fps, P-3 p95 < 200 ms.
5. Audit verification: every placement PUT produces exactly one `AuditEntry` with non-null `diff_summary` when the layout changed, empty `diff_summary` on no-op.
6. Weave trace inspection confirms the resolver emits per-placement spans with attributes.
7. Component README gains a "Shipped" banner with date and a §Verification Report section containing the performance numbers observed.
8. PROJECT-PLANNER DB-PRD rows flipped to `shipped`.
9. `make lint` clean; `pytest api/tests/` all green; `npm run typecheck` clean; Playwright CI green.

## 7. Risks & open questions

| Risk | Mitigation |
|---|---|
| Mock run harness doesn't exist at CI parity | If A-PRD-04's test-run mode has shipped, use it to produce deterministic run outputs for the E2E tests. Otherwise, this PRD adds a `seed_dashboard_fixture` helper that writes `PlanRun` + `TaskArtifact` docs directly. Documented in the test file headers. |
| Perf tests flaky in CI (shared runners) | Run 100 iterations and use p95 rather than max; fail only on sustained regression. Add a 10% tolerance bumper for the first 60 days post-ship. |
| GCS 30-day TTL cannot be exercised in a unit test | Use emulator + clock injection; A-PRD-03 already documents this pattern. |
| Role-matrix test count (40) is tedious to maintain | Parameterize the test to iterate over a policy table so new endpoints automatically get covered. |

### Open questions

- **Should we run the perf suite on every PR or nightly?** Recommendation: nightly + on PRs touching `dashboards/` or `artifact_store`. Confirm with infra team.
- **Who owns the Vega canvas-perf thresholds long-term?** If thresholds drift, either the Vega renderer or the resolver caching layer is at fault. Leave the first investigation to DB-PRD-04 owner; escalate to Frontend if chart rendering is the culprit, Backend if the resolver is.

## 8. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md)
- Siblings: [DB-PRD-01](./DB-PRD-01-data-model-and-api.md), [DB-PRD-02](./DB-PRD-02-dashboards-tab-and-list.md), [DB-PRD-03](./DB-PRD-03-dashboard-details-and-canvas.md)
- Pattern: [A-PRD-07 Automations Integration Testing & Polish](../../automations/projects/A-PRD-07-integration-testing-and-polish.md) — same closeout pattern
- Role policy: [DM-PRD-07 §4 transition policy table](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md#4-data-contract)
- CLAUDE.md rules in scope: T-2, T-3, T-4, T-5, T-6, T-8; G-1, G-2, G-3
