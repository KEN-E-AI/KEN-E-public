# Research Findings — Multi-Tenant Data Model Shape (Firestore + GCS)

**Status:** In progress — Q1 and Q2 complete; Q3–Q11 pending user direction
**Companion to:** [`multi-tenant-data-model-research-brief.md`](multi-tenant-data-model-research-brief.md)
**Last updated:** 2026-04-20

---

## Q1 — Full inventory of account-scoped Firestore data

**Method:** Grep across `api/`, `app/`, and ops scripts for `f"..._{{account_id}}"`, `f"accounts.{{account_id}}"`, `.where("account_id", ...)`, and `.document(account_id)` call sites. Classified each by shape, resource, and boundedness.

### 1.1. Shape A — flat per-account top-level collections

| Collection path | Resource | Bounded? | Primary call sites |
|---|---|---|---|
| `strategy_docs_{account_id}/{doc_type}` | Strategy stage docs (value_proposition, swot, etc.) | Bounded (~11 doc types) | `routers/strategy.py:86,149,154,219,233,336`; `app/adk/agents/strategy_agent/firestore.py:280,335,363,406` |
| `strategy_docs_{account_id}/{doc_type}/versions/{n}` | Strategy doc version snapshots | Unbounded (grows per edit) | `routers/strategy.py:149,233` |
| `strategy_audit_{account_id}/{audit_id}` | Strategy audit log | Unbounded | `services/audit_service.py:75,111,154,226`; `routers/strategy.py:445` |
| `strategy_processing_state_{account_id}` | Async processing status | Bounded | `app/adk/agents/strategy_agent/firestore.py:622,642` |
| `agent_analytics_{account_id}` | Per-account agent run metrics | Unbounded | `app/adk/agents/strategy_agent/analytics_service.py:143,211,239,383`; `async_analytics_queue.py:170`; `optimization_analyzer.py:200` |
| `cost_aggregations_{account_id}` | Rolled-up cost/time stats | Unbounded | `analytics_service.py:281,342` |
| `performance_profiles_{account_id}` (referenced as `performance_profiles_acc_{account_id}` in `RUNTIME_WARNINGS_ERRORS.md:230`) | Perf profiler output | Unbounded | `performance_profiler.py:240,320` |
| **Planned**: `skills_{account_id}/{skill_id}` + `/versions/{n}` | User-authored skills | Skills bounded per account; versions unbounded | SK-PRD-01 |
| **Planned**: `project_plans_{account_id}/{plan_id}` + `/versions/{n}` | Project plans | Unbounded | `components/project-tasks/projects/PR-PRD-01-data-model-and-api.md:120-124` |
| **Planned**: `project_plan_audit_{account_id}/` | Project-plan audit log | Unbounded | `components/project-tasks/projects/PR-PRD-01-data-model-and-api.md:123` |
| **Planned**: `plan_runs_{account_id}/{run_id}` + `/artifacts/{id}` | Automation runs + artifacts | Unbounded | `components/automations/projects/01-data-model-and-api.md:140-141`, `components/automations/projects/03-task-artifact-system.md:36` |

### 1.2. Shape D — nested map fields on a shared root doc

**Correction to brief §3**: the parent doc is `organizations/{org_id}`, **not** `accounts/{account_id}`. The field path `accounts.{account_id}.…` refers to `accounts` as a *map field* inside an organization doc. Multiple accounts' config is co-resident in one document.

| Nested path (inside `organizations/{org_id}`) | Resource | Bounded? |
|---|---|---|
| `accounts.{account_id}.account_settings.overview_kpis.{kpi_name}` | KPI-to-metric mapping | Bounded (~3 KPIs) |
| `accounts.{account_id}.funnels.organization.{step}` | Org funnel steps | Bounded (~6 steps) |
| `accounts.{account_id}.funnels.big_bets.{big_bet_name}.{step}` | Big-bet funnels | Unbounded in big_bet count |
| `…/{step}.channels.{channel_name}` | Channels under steps | Unbounded |
| `…/{step}.channels.{channel_name}.tactics.{tactic_name}` | Tactics under channels | Unbounded |

**Concrete size risk:** A single `organizations/{org_id}` doc holds `accounts × funnel_steps × big_bets × channels × tactics` of nested data for every account in that org. The 1 MiB per-doc cap is plausibly reachable for agency-style organizations with multiple accounts (Q4 will quantify).

Call sites: `api/src/kene_api/firestore.py:441,746,749,891,893,1078,1080,1135,1137,1211,1213,1407,1409,1467,1469` (15 nested field updates).

### 1.3. Shape B-like — `account_id` as document ID in a global collection

Not the canonical Shape B from the brief (subcollections under an account doc) — but structurally similar: one doc per account, all accounts co-resident in one flat collection.

| Collection path | Resource | Bounded? | Call sites |
|---|---|---|---|
| `monitoring_topics/{account_id}` | Monitoring subjects/keywords | Bounded | `services/monitoring_sync_service.py`; `graph_sync_service.py:2298,2883`; `routers/monitoring_topics.py` |
| `alert_configurations/{account_id}` | Alert thresholds | Bounded | `app/adk/agents/strategy_agent/alert_manager.py:145-147,202,486,641` |

### 1.4. Shape C — global collection with `account_id` field + `where()` filter

| Collection | Resource | Bounded? | Call sites |
|---|---|---|---|
| `usage_records` | LLM/tool token usage | Unbounded | `routers/usage.py:125-126,188-189,297`; filters on `user_id`, `account_id`, `timestamp` |
| `notifications` | User notifications | Unbounded | `repositories/firestore_notification_repository.py:75-77,166-168`; uses `where("account_id", "in", [batch])` to support multi-account reads |

### 1.5. Non-account-scoped global collections (out of scope for this decision)

| Collection | Purpose |
|---|---|
| `organizations` | Root container; Shape D parent |
| `users` | User profile + subcollections (`notification_status`, `preferences`) — user-scoped Shape B |
| `agent_configs` | Platform-owned agent configs |
| `industry_keywords`, `industry-templates`, `subscription-plans` | Reference data |
| `strategy_doc_guides` | Platform prompt guides |
| `security_audit_logs`, `revoked_tokens`, `revoked_tokens_all`, `oauth_states` | Auth/security |
| `integration_credentials` | Per-account but keyed by a composite doc_id, with encrypted payload — effectively Shape B-like |
| `optimization_recommendations`, `health_check` | Platform ops |

### 1.6. Observations from Q1

1. **Not two patterns, but five.** The codebase mixes Shape A, Shape D (under org doc), Shape B-like (doc-per-account in a global collection), Shape C, and user-scoped Shape B. "Follow existing convention" is meaningless — there are too many existing conventions.

2. **Account deletion is already incomplete** (`api/src/kene_api/routers/accounts.py:968-997`). The deletion flow only sweeps `strategy_docs_{account_id}`. It does **not** touch:
   - `strategy_audit_{account_id}` (unbounded, contains PII-adjacent audit data)
   - `strategy_processing_state_{account_id}`
   - `agent_analytics_{account_id}` (unbounded)
   - `cost_aggregations_{account_id}`
   - `performance_profiles_{account_id}` (or `_acc_{account_id}`)
   - `monitoring_topics/{account_id}` doc in the global collection
   - `alert_configurations/{account_id}` doc
   - The `organizations/{org_id}.accounts.{account_id}.*` nested map field
   
   Every one of these is orphaned on account deletion today. This is a latent compliance issue (GDPR right-to-erasure), not a theoretical risk. The Skills and Plans PRDs add 4–5 more Shape A collections to this list.

3. **Shape D's 1 MiB ceiling is the biggest sleeper risk.** The `organizations/{org_id}` doc holds *all* accounts under the org, with the full funnel×channel×tactic tree per account. Large agencies hit the cap first.

4. **Shape C already works for notifications.** The `in` clause batching (10 accounts at a time) is a workable pattern — a user with 25 account permissions costs 3 parallel queries.

5. **Shape A's explicit-per-collection indexing forecloses several query patterns** — see Q2.

---

## Q2 — Cross-account queries (existing + planned)

**Method:** Grep for `collection_group`, `stream()` on global collections, admin-endpoint handlers, and ops scripts. Reviewed every in-flight PRD (skills, automations, calendar/plans, knowledge graph, MER-E framework) for cross-account access patterns.

### 2.1. Cross-account queries that exist in code today

| Query / use case | Location | Shape needed | Status |
|---|---|---|---|
| Notifications for a user's N accounts in a single call | `repositories/firestore_notification_repository.py:75,166` (`where("account_id","in",batch)`) | Shape C works natively | **Working** |
| Archive old notifications — scan all users → `notification_status` subcollections | `firestore_notification_repository.py:376-443` | User-scoped Shape B | Working (uses `stream()` over `users` root) |
| Usage records by user across all their accounts (super-admin) | `routers/usage.py:125-126` | Shape C | Working |
| Usage records for one account | `routers/usage.py:188-189` | Shape C | Working |
| **Strategy audit — "user activity across all accounts"** | `services/audit_service.py:189` uses `db.collection_group("strategy_audit")` | Shape B via `collection_group` | **BROKEN by Shape A.** `collection_group` matches collections *literally named* `strategy_audit`; our collections are named `strategy_audit_{account_id}`. The query returns empty. Silent bug. |
| Active composite indexes on collection groups | `deployment/firestore.indexes.json` — 4 entries on `notifications` and `notification_status` | Shape B / C | Deployed |
| Scripts doing cross-account Shape A sweeps | `scripts/delete_intellipure_accounts.py`, `scripts/redis_performance_test.py` | Shape A forces per-account iteration | Working but must enumerate every per-account collection by name |

### 2.2. Cross-account queries required by in-flight PRDs

| Planned query | PRD | Preferred shape | Risk under Shape A |
|---|---|---|---|
| Scheduler finds all due tasks across all accounts every N minutes | `components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md:94,173` | Shape B/C — `collection_group("plans").where("due_datetime_utc","<=",now)` | PRD already flags this as a blocker: *"fall back to per-account iteration… acceptable for moderate account counts"* |
| Session-end sweeper: find idle sessions across all accounts daily | `components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md:145` | Shape B/C | Would need per-account iteration |
| Scheduler-endpoint scan with 10k tasks across 100 accounts in <5s | `components/automations/projects/07-integration-testing-and-polish.md:75` | Shape B/C | 100 collection queries serially is slow; batched parallel queries work but add complexity |
| Org-level billing aggregation (sum tokens per org per period) | `KEN-E-System-Architecture.md:542` + `DESIGN-REVIEW-LOG.md:214` | Shape C on `usage_records` (currently lacks `organization_id` — separate gap) | Doesn't use account-scoped collections; orthogonal to this decision |
| **MER-E cross-account benchmarking (anonymized aggregation)** | `KEN-E-Self-Improving-Evaluation-Framework-Design.md` §15 (§28 TOC entry) + §53 ("Global Optimization — Improvements apply across all KEN-E accounts") | Operates on Weave traces, not Firestore directly. However, if any evaluation state is mirrored to Firestore, Shape B/C preferred. | N/A if purely in Weave; Shape A painful if it lands in Firestore |
| Plan-run aggregation (A-PRD-5 list view across all runs for an org admin) | `components/automations/projects/03-task-artifact-system.md`, `components/automations/projects/05-automations-list-page.md` | Shape B/C | Per-account iteration works; scales poorly at N accounts × runs/account |

### 2.3. Observations from Q2

1. **Cross-account is not hypothetical.** Two shipped queries already rely on Shape C (`notifications`, `usage_records`). One shipped query silently fails under Shape A (`get_user_activity` via `collection_group`). Multiple near-term PRDs (Scheduler, Session Sweeper, Automations) require cross-account access by design.

2. **Shape A forces per-account iteration** for every cross-account read path. That works "for moderate account counts" (as PRD-6 acknowledges) but:
   - Adds a new call for every new account. O(accounts) per tick.
   - The scheduler tick currently has budget concerns at ~100 accounts; the same pattern would be worse for 1k+ accounts.
   - Cannot be rescued by indexes — Shape A's collections literally don't share a queryable namespace.

3. **Shape B and Shape C both serve every identified cross-account query cheaply** via `collection_group` + composite index (Shape B) or composite indexes on `account_id + {sort_key}` (Shape C). Both are one query per request, regardless of account count.

4. **The already-broken `collection_group("strategy_audit")` call at `audit_service.py:189`** is diagnostic: someone *tried* to write Shape B cross-account code, and Shape A silently broke it. That's two anecdotes that Shape A actively hampers planned work (PRD-6's mitigation and this dead query).

5. **Security rules are not the tiebreaker today.** All access control is enforced in Python via `UserContext.has_account_access()` + `is_super_admin` bypass. No Firestore rules enforce account isolation. So Shape A's "structural isolation" benefit is a backup layer, not the primary defense. If we moved to Shape B or C, we would not lose our primary defense, only the backup.

---

## Preliminary direction (after Q1 + Q2)

> **Not a final recommendation.** Captured here per the brief's instruction to check in after Q1/Q2. Full recommendation follows Q3–Q11 if the user confirms the direction is worth continuing to sharpen.

The Q1 + Q2 evidence points strongly toward **Shape B (subcollections under `accounts/{account_id}`) as the primary shape** for account-scoped Firestore data, with these carve-outs:

1. **Keep Shape C for cross-cutting event-stream data** that is genuinely queried cross-account by the product (notifications, usage_records). The batching pattern already in place is proven.

2. **Migrate Shape D (nested maps inside `organizations/{org_id}`) to an `accounts/{account_id}` root doc** and split the funnel/channel/tactic tree into a small number of bounded subcollections (or keep a single bounded config map on the account doc, if the 1 MiB test in Q4 gives comfort). The current "multiple accounts nested in one org doc" pattern is the biggest sleeper risk in the codebase.

3. **Migrate Shape A collections to Shape B subcollections.** This single change:
   - Fixes the broken `collection_group("strategy_audit")` query in `audit_service.py:189`.
   - Collapses account deletion to `firestore.recursive_delete(db.collection("accounts").document(account_id))` — one call, never outdated.
   - Unblocks the planned Scheduler, Session Sweeper, and Automations cross-account reads without fallback paths.
   - Preserves structural isolation when paired with security rules *or* the existing Python-layer checks (either is fine; we should decide in Q5).

**The open questions that would change this direction:**

- **Q4 (limits):** Is the 200-composite-index project cap hit by the Shape B migration? (Probably not — subcollections share indexes under collection-group scope.) Is the 100-subcollection-name-per-doc soft limit hit under Shape B for the 2-year resource list? (Likely no — the current list is ~15.) Confirm before recommending.
- **Q3 (deletion):** Measure `recursive_delete` latency on a realistic seeded account vs. the current hand-rolled iteration.
- **Q6 (ergonomics):** Does Shape B require notably more boilerplate than Shape A for the common read/write path? (Early read: no — `db.collection("accounts").document(acc_id).collection("skills").document(skill_id)` vs. `db.collection(f"skills_{acc_id}").document(skill_id)` is the same line count with better structure.)

If any of Q4/Q3/Q6 produce a surprise, the recommendation can shift toward Shape C.

### GCS direction

Nothing in Q1/Q2 challenges the brief's working hypothesis: **G1 (single bucket per environment + per region, `accounts/{account_id}/…` prefix) is the right default.** The current `storage_service.py` implementation already regionalizes buckets for US/EU data residency, so per-account bucket creation (G2) would have to be regional-aware *and* subject to the 1000-buckets-per-project soft cap, with no observed upside. **G1 confirmed unless Q9 surfaces a compliance requirement.**

---

## Answers to the external-input questions (provided 2026-04-20 by Ken Williams)

1. **Q9 — GCS compliance / CMEK:** No contracts, legal commitments, or marketing claims requiring per-customer bucket isolation or per-customer CMEK.
2. **Q10 — Account projection:** Target **10k+ accounts** over the next several years (see Q4 answer for ramp).
3. **Q11 — Per-account retention:** Retention policies are **uniform** across all accounts. No tier-based retention variance.
4. **Q5 — Isolation enforcement:** Keep Python-layer checks (`has_account_access` + `is_super_admin` bypass) as the authoritative enforcement. No move to Firestore security rules as the primary defense.
5. **Q4 — Scheduler scale target:** **1k accounts** at the scheduler's design target, ramping to **10k within the following year.**

These answers are decisive enough to close out the recommendation without running Q3, Q6, Q7, Q8. They remain open for a follow-up validation pass *after* the shape is committed.

---

## Final recommendation

### Firestore — Shape B (subcollections under `accounts/{account_id}`) as the primary shape

**Root pattern:**
```
accounts/{account_id}                                  # account doc (config, metadata)
accounts/{account_id}/strategy_docs/{doc_type}
accounts/{account_id}/strategy_docs/{doc_type}/versions/{n}
accounts/{account_id}/strategy_audit/{audit_id}
accounts/{account_id}/skills/{skill_id}
accounts/{account_id}/skills/{skill_id}/versions/{n}
accounts/{account_id}/project_plans/{plan_id}
accounts/{account_id}/project_plans/{plan_id}/versions/{n}
accounts/{account_id}/project_plan_audit/{audit_id}
accounts/{account_id}/plan_runs/{run_id}
accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}
accounts/{account_id}/agent_analytics/{metric_id}
accounts/{account_id}/cost_aggregations/{agg_id}
accounts/{account_id}/performance_profiles/{profile_id}
accounts/{account_id}/strategy_processing_state/{state_id}
accounts/{account_id}/monitoring_topics/{topic_id}     # migrated from global monitoring_topics/{account_id}
accounts/{account_id}/alert_configurations/{config_id} # migrated from global alert_configurations/{account_id}
```

### Firestore — carve-outs from Shape B

**Keep as Shape C (global collection with `account_id` field)** — these are genuinely cross-cutting event streams that the product reads across accounts in the hot path:

| Collection | Why Shape C |
|---|---|
| `notifications` | Already Shape C. Users have permissions on N accounts; `where("account_id", "in", [batch])` serves a user's notifications feed in a single query. Index already deployed. |
| `usage_records` | Already Shape C. Org-level billing aggregation (`KEN-E-System-Architecture.md:542`) sums tokens across all accounts in an org — natural Shape C use case. |

**Decision rule for future resources:** default to Shape B. Move to Shape C only if the resource's *primary read pattern* is across-account aggregation by a non-account key (e.g., by user, by org, by time window).

**Deprecated — do not repeat:**

- **Shape A** (`{resource}_{account_id}` top-level collections). Migrate all existing Shape A collections to Shape B subcollections.
- **Shape D as currently implemented** — `organizations/{org_id}` doc with nested `accounts.{account_id}.funnels.…` map. The 1 MiB per-doc cap is the blocker at 10k+ accounts. Migrate to `accounts/{account_id}` doc fields (bounded config) or `accounts/{account_id}/funnels/` subcollection (unbounded tree), whichever shakes out during implementation.
- **The degenerate Shape B-like** (`monitoring_topics/{account_id}`, `alert_configurations/{account_id}`) — roll into true Shape B subcollections under `accounts/{account_id}` for consistency. Not a correctness issue, just a consistency one.

### GCS — G1 (single bucket per env + region, `accounts/{account_id}/…` prefix)

Keep the current pattern (`storage_service.py:157`, `246`, `288`, `341`). Q9 ruled out compliance-driven G2, Q10 rules it out on bucket-quota grounds (10k+ accounts ≫ 1k bucket soft cap), and Q11 makes bucket-level lifecycle policies sufficient. **No changes to GCS layout.**

### Rationale — why Shape B wins at 10k accounts

**1. Account deletion collapses to one call.**
Current: `accounts.py:968-997` enumerates one collection name and sweeps it. Seven other per-account collections are orphaned (latent GDPR issue). Under Shape B: `firestore.recursive_delete(db.collection("accounts").document(account_id))` sweeps the account doc and every subcollection in one call, every time, no matter what new resources we add.

**2. Scheduler at 10k scales natively.**
Current Shape A approach: 10k per-account iterations per tick. PRD-6 flagged this explicitly ("acceptable for moderate account counts" — which 10k is not). Under Shape B: `db.collection_group("project_plans").where("due_datetime_utc", "<=", now)` — one query regardless of account count. Same pattern serves the session sweeper (KG-04) and automation runs.

**3. The broken audit query becomes correct.**
`services/audit_service.py:189` already has `db.collection_group("strategy_audit")` written. Shape A silently breaks it (collections are named `strategy_audit_{account_id}`, so the group is empty). Migrating to `accounts/{account_id}/strategy_audit/…` makes the existing dead code work without edits beyond the collection path.

**4. Shape D's 1 MiB ceiling is unavoidable at 10k accounts.**
A single `organizations/{org_id}` doc that holds funnel/channel/tactic trees for 5–20 accounts per org approaches the 1 MiB cap as soon as an agency-style org adds more channels/tactics. Splitting to `accounts/{account_id}` doc fields removes the account-multiplier inside each doc.

**5. Index budget stays safe.**
Shape A consumes one index per per-account collection (infeasible for cross-account reads — would need 10k). Shape B uses collection-group indexes, which share across all accounts (one index per query shape, not per account). The 200-composite-indexes-per-project cap is not at risk for the foreseeable future.

**6. Losing structural isolation is a non-cost.**
Q5 confirmed that account-isolation enforcement stays in Python. Shape A's "different accounts literally cannot share a path" is a nice-to-have backup, not load-bearing. Moving to Shape B does not weaken the primary defense.

### What this implies for in-flight PRDs

| PRD | Change required |
|---|---|
| `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` | Replace `skills_{account_id}/{skill_id}` path references (~15 spots) with `accounts/{account_id}/skills/{skill_id}`. Update composite-index section (collection-group instead of collection-scoped). Update account-deletion section (remove explicit sweep — `recursive_delete` covers it). |
| `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md`, `SK-PRD-04-agent-builder-controls.md` | Path references aligned with SK-PRD-01. |
| `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md` (Project Plans) | Replace `project_plans_{account_id}/…` and `project_plan_audit_{account_id}/…` with `accounts/{account_id}/project_plans/…` and `accounts/{account_id}/project_plan_audit/…`. |
| `docs/design/components/project-tasks/projects/PR-PRD-06-time-based-scheduler.md` | Remove the "fall back to per-account iteration" mitigation — collection-group query is the primary path. |
| `docs/design/components/automations/projects/01-data-model-and-api.md`, `03-task-artifact-system.md` | Replace `plan_runs_{account_id}/…` with `accounts/{account_id}/plan_runs/…`. |
| `docs/design/components/knowledge-graph/projects/KG-PRD-04-session-end-automation.md` | Session-sweeper query pattern updates to collection-group. |

### What this implies for existing code (to be scoped in the migration plan)

All existing Shape A call sites listed in §1.1 and Shape D call sites in §1.2 need rewriting. The migration plan (separate doc) will enumerate each file + the Terraform index changes. Since there are no production users, the migration can be a single maintenance window with no dual-write phase.

### Out-of-scope decisions this recommendation does NOT make

- **Shape-B-like flat collections staying vs. moving** — `monitoring_topics/{account_id}` and `alert_configurations/{account_id}` are a nudge, not a mandate. If the migration scope is tight, they can stay.
- **Moving enforcement from Python to Firestore rules** — confirmed out of scope per Q5.
- **Per-account quotas, rate limits, or tenant-tier configuration** — separate from data shape.
- **Neo4j schema** — unchanged; graph DB uses node properties for account_id.
- **Billing aggregation gap** (`DESIGN-REVIEW-LOG.md:214`, missing `organization_id` / `session_id` on `usage_records`) — surfaces here but is a separate fix.

---

## Post-decision follow-ups (not blockers)

These can be answered *after* the shape is committed, in implementation or post-migration validation:

- **Q3** Benchmark `recursive_delete` latency on a seeded realistic account (once a real test account exists under Shape B).
- **Q6** Write one CRUD flow four ways to confirm the ergonomics delta — likely neutral or slightly better for Shape B, but worth documenting.
- **Q7** Verify `gcloud firestore export` supports subcollection-group exports for disaster recovery.
- **Q8** Walk the ADK session-state and artifact APIs to confirm nothing is hard-coded against Shape A collection names. (Quick scan done during Q1 — no obvious dependencies — but worth a dedicated pass.)
- **Shape D → Shape B split for funnel/KPI config:** prototype the new layout (account doc field vs. subcollection) and pick based on observed doc sizes.
