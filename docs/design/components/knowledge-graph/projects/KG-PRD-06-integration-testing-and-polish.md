# KG-PRD-06 — Integration Testing & Polish

**Status:** Ready for development (after KG-PRDs 01–05 merge)
**Owner team:** QA + the team that finishes its KG-PRD first
**Blocked by:** KG-PRDs 01, 02, 03, 04, 05
**Estimated effort:** 1–2 days

---

## 1. Context

Once the schema foundation, provenance spine, read tools, session-end automation, and research-on-creation refactor are all merged, the Knowledge Graph component must be exercised end-to-end against real services to confirm the seams hold. This PRD owns that closing-out work — no new features, just verification, edge-case coverage, multi-tenant isolation across every read and write path, and polish.

The KG component carries higher-than-average integration risk because it sits at the intersection of three storage layers (Neo4j, Firestore, GCS for artifacts), is consumed by both an in-conversation orchestrator and a daily Cloud Scheduler sweep, and now dual-writes through `GraphSyncService` from two write origins (research-on-creation and session-end). A focused integration sprint catches the seams that unit tests miss.

## 2. Scope

### In scope
- **E2E happy paths**, against live Neo4j + Firestore emulator + (where available) the real Automations orchestrator:
  - Full session-end loop — fixture chat session idle > 24h → sweeper → reviewer → applier → `Observation` in Neo4j with `:OBSERVED_IN` edge + `embedding` populated.
  - Full HITL halt + resume — destructive proposal → halt → notification emitted → Mark Complete via the Automations Outputs tab → delete lands in Neo4j and the run completes.
  - Full research-on-creation — POST account → `ResearchRun` created → all four builders write via `GraphSyncService` → `:ESTABLISHED_BY` on every produced node → Firestore mirror in sync → `close_research_run(status="complete")`.
- **Multi-tenant isolation suite** covering every KG read tool (`load_context_section`, `load_document`, `search_kb`, `list_observations`) and every KG-owned subcollection (`accounts/*/sessions`, `accounts/*/observations`, `accounts/*/research_runs`) across two seeded accounts. Every cross-account read returns zero rows. Every cross-account `about_node_id` write returns 422.
- **Provenance roundtrip** — confirm `source_session_id` / `source_research_run_id` properties and the corresponding `:OBSERVED_IN` / `:UPDATED_BY` / `:ESTABLISHED_BY` edges agree on every read path. A property without its edge (the documented post-Firestore-sync failure mode in KG-PRD-02 §9) is flagged but does not fail the test.
- **Bi-temporal correctness** — supersede chains traversable; `valid_to IS NULL` filtering in `search_kb` and `list_observations` (default-on); `valid_only=false` opens the filter; `:SUPERSEDES` relationships chain correctly across multiple supersedes.
- **Performance smoke** —
  - `load_context_section` p95 < 1s on a populated account
  - `search_kb` p95 < 1.5s end-to-end (including embedding generation)
  - `touch_session` p95 < 20ms (per-turn latency budget)
  - Sweeper handles 500 idle sessions per tick without timeout
  - Research-on-creation total run time stays within ±10% of pre-refactor baseline (regression check on KG-PRD-05)
- **Observability check** — every read tool emits a Weave span with `account_id` attribute; the sweeper emits one structured-log line per claimed session; the reviewer + applier emit task-level Weave spans; halt notifications appear in the existing notification-system audit log.
- **Idempotency replay** — re-run the seed script (`seed_session_end_template.py`); re-run a research builder with the same `(account_id, run_id, natural_key)` tuple; re-fire the sweeper for an already-`processed` session. Each is a no-op.
- **Documentation polish:**
  - Add a "Status: shipped" report block to the Knowledge Graph README §5.5 linking to this PRD's verification report.
  - Confirm the legacy `SECTION_KEYWORDS` / `should_load_section` paths have been removed (KG-PRD-03 deliverable; verify).
  - Audit README §2.1 directory table — every file listed exists at the documented path.
  - Audit README §2.3 API contract table — every endpoint exists, returns the documented shape, and the auth posture matches.

### Out of scope
- Any new features or new endpoints
- Architectural changes — file bugs back to the relevant KG-PRD if found
- Cross-component verification beyond the KG ↔ Automations and KG ↔ Project Tasks seams documented in KG-PRD-04 (Automations integration is owned by A-PRD-07; Project Tasks integration by PR-PRD-05)

## 3. Dependencies

All other KG-PRDs (01–05) must be merged. KG-PRD-06 cannot start before then. Cross-component dependencies (Automations A-PRDs 01–06, Project Tasks PR-PRDs 01, 04, 06, Data Management DM-PRDs 00, 05) must also be in their finished state — the integration tests assume the platforms behave per their PRD specs.

## 4. Test catalog

### E2E: session-end happy path

1. Seed a test account with at least 5 strategy nodes spanning multiple types.
2. Open a chat session as a fixture user; send 3–4 turns including one clearly new fact ("our pricing model is shifting to per-seat next quarter").
3. Stop sending messages; advance test clock by 25 hours.
4. POST to `/api/v1/internal/scheduler/process-idle-sessions` with mock OIDC auth.
5. Verify: exactly one `PlanRun` created against `kg-session-end-review` with `triggered_by="system"`, `inputs.session_id` and `inputs.account_id` populated, `Session.status="processing"`.
6. Wait for the run to terminate (poll the Automations API until `status` is terminal).
7. Assert: the new pricing fact lands as exactly one `Observation` in Neo4j with `:OBSERVED_IN` edge to the Session, `valid_from` set, `embedding` non-null within a bounded window (< 5 minutes), `last_updated_by_agent="session_end_agent"`, mirror doc present in `accounts/{account_id}/observations/{node_id}` Firestore subcollection.
8. The Session flips to `status="processed"` with a non-null `summary`.

### E2E: HITL halt + resume

1. Seed a test account with a `Product` node.
2. Open a session, say "we discontinued Product X last quarter — please remove it."
3. Advance clock 25h; trigger the sweeper.
4. Assert: `PlanRun.status="halted_for_human"`, applier task in `Awaiting Approval`, no Product deleted, exactly one `kg_session_end_halt` notification emitted to the session's user_id with deep_link `/workflows/automations/kg-session-end-review?run={run_id}&task=applier`.
5. PATCH the applier task `Complete` via the A-PRD-06 endpoint.
6. Assert: the Product is deleted (or soft-deleted with `valid_to` set) in Neo4j, run flips to `status="complete"`, no second notification fires.

### E2E: research-on-creation

1. POST a new account through the existing endpoint.
2. Wait for `execute_strategy_generation_direct` to complete (existing background-task signal).
3. Assert:
   - Exactly one `ResearchRun` node with `status="complete"` and `agents=["business", "competitive", "marketing", "brand"]`.
   - Every node produced by the run carries `source_research_run_id == run.run_id`, `last_updated_by_agent="researcher"`, `valid_from` set, one `:ESTABLISHED_BY` edge.
   - Firestore subcollection counts equal Neo4j counts per node type.
   - Re-running the orchestrator with the same `research_run_id` (direct call, bypass account endpoint) creates zero new nodes.
   - Re-running with a fresh `research_run_id` creates a second `ResearchRun` and a parallel set of nodes; old nodes are not modified.

### Multi-tenant isolation suite

Seeded fixture: two accounts A and B, each with the same set of node types but distinct content + distinct chat sessions + distinct observations + distinct research runs.

For every (tool, account) pair:
- `load_context_section(section)` for every valid section → zero rows from the other account.
- `load_document(entity_type, entity_id)` with the other account's entity_id → 404 / "not found, may belong to another account."
- `search_kb(query)` with a query matching content in both accounts → only the calling account's content appears.
- `list_observations(...)` → only the calling account's observations.

For every direct CRUD endpoint (`/api/v1/accounts/{account_id}/sessions`, `.../observations`):
- Cross-account GET → 403.
- Cross-account `about_node_id` on observation create → 422 from the validation service.

### Provenance roundtrip

For every node produced in the E2E paths above:
- `MATCH (n {node_id: $id})-[:OBSERVED_IN|UPDATED_BY|ESTABLISHED_BY]->(ep)` returns at least one episode node.
- The corresponding `source_session_id` / `source_research_run_id` property is non-null.
- Property and edge agree (point at the same `session_id` / `run_id`).

A property-without-edge result is logged as a warning (the documented retry-safe failure mode from KG-PRD-02 §9) but does not fail the suite.

### Bi-temporal correctness

- Create observation O1 in session S1.
- Supersede O1 with O2 in session S2.
- Assert: `O1.valid_to` is set, `O1.superseded_by == O2.node_id`, `(:O2)-[:SUPERSEDES]->(:O1)` edge exists.
- `search_kb` does not return O1 by default; returns O2.
- `list_observations()` does not return O1 by default; `list_observations(valid_only=false)` returns both.
- Supersede chain: `MATCH (latest:Observation)-[:SUPERSEDES*]->(o) RETURN o` traverses correctly.

### Performance smoke

| Path | Target | Method |
|---|---|---|
| `load_context_section("competitors")` | p95 < 1s | populated account, 50 entities, 20 calls |
| `search_kb("usage-based pricing")` | p95 < 1.5s | seeded vector index, 20 calls |
| `touch_session` | p95 < 20ms | 100 invocations |
| Sweeper full tick | < 30s | 500 seeded idle sessions, single tick |
| Research-on-creation | within ±10% of pre-refactor | timed against the historic baseline captured before KG-PRD-05 |

### Observability check

- Every KG read-tool call produces a Weave span named `kb.<tool_name>` with `account_id` attribute.
- Sweeper emits `kg.session_sweeper.tick` structured log per run with `claimed_count`, `triggered_count`, `failed_count`.
- Reviewer + applier produce task-level Weave spans inside the parent `PlanRun` span (cross-component check with A-PRD-07).
- Halt notifications appear in the notification-system audit log with kind `kg_session_end_halt`.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `tests/integration/test_kg_e2e_session_end_happy.py` |
| Create | `tests/integration/test_kg_e2e_session_end_halt_resume.py` |
| Create | `tests/integration/test_kg_e2e_research_on_creation.py` |
| Create | `tests/integration/test_kg_multi_tenant_isolation.py` — every read tool + every CRUD path |
| Create | `tests/integration/test_kg_provenance_roundtrip.py` |
| Create | `tests/integration/test_kg_bitemporal.py` |
| Create | `tests/integration/test_kg_performance_smoke.py` |
| Create | `tests/integration/test_kg_observability.py` |
| Create | `tests/integration/test_kg_idempotency_replay.py` |
| Create | `tests/fixtures/kg_seed.py` — shared fixture builders for the integration tests |
| Modify | `docs/design/components/knowledge-graph/README.md` §5.5 — add "Status: shipped" block linking the verification report |
| Modify | `docs/design/components/PROJECT-PLANNER.md` — flip KG-PRDs 01–06 statuses on completion |

## 6. Acceptance criteria

1. All E2E suites pass against a freshly-seeded staging environment with no manual intervention.
2. The multi-tenant suite reports zero cross-account leaks across all four read tools and every CRUD path.
3. The provenance roundtrip suite reports zero property-without-edge or edge-without-property records on data produced after KG-PRDs 02 + 05 are merged (warnings only on legacy nodes that pre-date the audit-field rollout).
4. The bi-temporal suite confirms supersede chains traverse correctly and default filters exclude superseded observations.
5. The performance smoke targets are met on staging hardware; any miss files a follow-up bug, not a polish PRD blocker.
6. Every KG read tool produces a Weave span with the documented attributes; the sweeper produces the documented structured log; the halt notification produces an audit entry.
7. Idempotency replay tests confirm: seed script is idempotent; same-`run_id` research is a no-op; sweeper skips already-`processed` sessions.
8. README §5.5 carries a "Status: shipped" block linking to this PRD's verification report; PROJECT-PLANNER.md reflects the shipped state for KG-PRDs 01–06.
9. Legacy `SECTION_KEYWORDS` / `should_load_section` are confirmed removed (grep returns zero hits in the live codebase).
10. README §2.1 + §2.3 audits pass — every file path and endpoint listed in the README exists at the documented location with the documented contract.

## 7. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Integration tests flake against shared staging | Use isolated fixture accounts per test run; tear down on completion. Clock-advance helpers must be deterministic. |
| Performance smoke fails because staging is under-provisioned | Targets are p95, not hard ceilings; document the run environment and re-baseline if hardware changes. A miss files a follow-up, not a regression. |
| The KG-PRD-04 halt-resume test depends on the Automations orchestrator being live in staging | If A-PRD-07 hasn't shipped by the time this PRD lands, gate the halt-resume test on a feature flag and run against a stubbed orchestrator. The non-Automations parts (sessions, observations, research runs, read tools) all stand alone. |
| Vector-index embedding lag breaks `search_kb` performance smoke on a freshly seeded account | Pre-warm embeddings for the fixture set; document a startup window (< 5 min) inside which `search_kb` returns the legacy `list_observations` fallback. |
| Multi-tenant suite false positive from a leaked test fixture | All fixtures namespace by `account_id` prefix `kg_test_`; teardown verifies zero residual nodes / docs before the next run. |

## 8. Reference

- KG-PRDs 01–05 (everything this verifies).
- A-PRD-07 (sibling polish PRD on Automations) and PR-PRD-05 (sibling on Project Tasks) for shape and tone.
- `docs/KEN-E-System-Architecture.md` §3.2 + §3.3 — the design behavior these tests verify.
- CLAUDE.md rules in scope: T-1, T-3, T-4, T-5, T-6, T-7, T-8.
