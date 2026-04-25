# Research Brief — Multi-Tenant Data Model Shape (Firestore + GCS)

**Status:** Research needed; decision pending
**Owner:** TBD (assign during research kickoff)
**Created:** 2026-04-20
**Expected output:** A Review entry in `docs/design/DESIGN-REVIEW-LOG.md` + a migration plan (if the decision changes the current pattern). *Historically resolved in [Review 15 — Multi-Tenant Data Model Shape](DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1).*

---

## 1. Why this is on the table

KEN-E is multi-tenant by account. Every user-facing feature (strategies, project plans, automations, skills, knowledge graph, calendar, etc.) stores account-scoped data in Firestore and GCS. The **shape** of that storage — whether data is partitioned by collection name, nested under an account document, or kept in a single global collection with an `account_id` field — was set early by the strategy module and has been copied by subsequent features without a dedicated design review.

We now have **at least two coexisting patterns** (see §3 below), and a third (Skills) was about to be added. Before committing to the flat-collection-per-account shape for Skills and future features, we should decide, once, which shape is right and realign the codebase.

**Key enabling condition:** KEN-E is in development with **no production users**. We can make breaking structural changes without migration windows, versioned dual-writes, or backwards-compatibility shims. The cost of picking the wrong shape now is mostly developer time; the cost of keeping an inconsistent pattern indefinitely is ongoing friction across every feature we build.

## 2. The decision to make

Pick **one** primary shape for account-scoped Firestore data, and **one** for account-scoped GCS data, and realign existing code + planned PRDs accordingly.

### Firestore — three candidate shapes

| Shape | Example path | Today's usage in KEN-E |
|---|---|---|
| **A. Flat, per-account top-level collection** | `strategy_docs_{account_id}/{doc_id}` | Strategy, audit, planned for Skills/Plans |
| **B. Nested subcollections under an account doc** | `accounts/{account_id}/strategy_docs/{doc_id}` | Not currently used for these resources |
| **C. Global collection with `account_id` as a field** | `strategy_docs/{doc_id}` with `account_id` field + composite indexes | Not currently used |
| **D. Nested fields on a single account document** | `accounts/{account_id}` doc with map fields like `funnels.organization.{funnel_step_num}` | Currently used for KPI/funnel config (see §3) |

Shape D is **not** a candidate for the general pattern — it's an appropriate choice for small, bounded, always-loaded-together config but doesn't scale for unbounded collections (audit logs, versions, etc.). It's listed here only to acknowledge that it exists today and to make sure the decision explicitly carves out which resources stay on D.

### GCS — two candidate shapes

| Shape | Example path | Today's usage |
|---|---|---|
| **G1. Single bucket per env, `accounts/{account_id}/…` prefix** | `gs://kene-docs-{env}/accounts/{account_id}/file.pdf` | Current pattern in `storage_service.py` |
| **G2. One bucket per account** | `gs://kene-{env}-{account_id}/file.pdf` | Not used |

**Working hypothesis:** G1 is clearly correct for a SaaS at our scale (see §6 for why); the research task for GCS is narrow — confirm there are no compliance or data-residency asks that would justify G2.

The meaty question is the **Firestore** shape.

## 3. Current state — what's actually in the codebase

Ground-truth findings from the `api/src/kene_api/` tree as of 2026-04-20:

### Shape A (flat top-level per account)
- `strategy_docs_{account_id}` — `api/src/kene_api/routers/strategy.py:86`, line 149, 154, 219, 233, 336
- `strategy_audit_{account_id}` — `api/src/kene_api/services/audit_service.py:75, 111, 154, 226`
- Account-deletion flow sweeps `strategy_docs_{account_id}` in `api/src/kene_api/routers/accounts.py:968-970` (the deletion code must know every collection name explicitly)

### Shape D (nested map fields on `accounts/{account_id}`)
- `accounts.{account_id}.account_settings.overview_kpis.{kpi_name}` — `api/src/kene_api/firestore.py:441`
- `accounts.{account_id}.funnels.organization.{funnel_step_num}` — `api/src/kene_api/firestore.py:746`
- `accounts.{account_id}.funnels.big_bets.{big_bet_name}.{funnel_step_num}` — `api/src/kene_api/firestore.py:749`
- Plus ~10 additional nested field paths for channels/tactics (firestore.py:891, 893, 1078, 1080, 1135, 1137, 1211, 1213, 1407, 1409, 1467, 1469)
- This implies `accounts` is a root collection with a doc per account, and much of the account config is stored as a single deep JSON blob.

### Shape G1 (single bucket, account prefix) — GCS
- `api/src/kene_api/services/storage_service.py:157` — `blob_path = f"accounts/{account_id}/{file.filename}"`
- `storage_service.py:246, 288, 341` — list / delete / placeholder operations all prefix with `accounts/{account_id}/`
- `account_service.py:358` — ensures a regional GCS bucket per account *environment*, not per account ID

### In-flight PRDs (would follow whatever we decide)
- `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` — just updated to Shape A (`skills_{account_id}`). Would flip to B if we change the decision.
- `docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md` — specifies Shape A for `project_plans_{account_id}` and `project_plan_audit_{account_id}`. Not yet implemented.

### Repositories using shape-agnostic global collections
- `firestore_notification_repository.py` uses flat global `notifications` and `users/{user_id}/notification_status` — ignores account scope entirely for notifications
- `token_revocation` uses `{self.collection_name}_all`

**Observation:** We already have at least three patterns (A, D, and global-collection) in active use. "Consistent with existing convention" is not a decisive argument in either direction because the existing convention isn't internally consistent.

## 4. Research questions — Firestore

Each question has a concrete method. Answers should be captured directly in the eventual `DESIGN-REVIEW-LOG` Review entry.

### Q1. What's the full inventory of account-scoped Firestore data?

**Method:**
1. Grep for `f"…_{{account_id}}"` and `f"accounts.{{account_id}}"` across `api/`, `app/`, and any workers.
2. Grep for `account_id` in Firestore queries (`.where("account_id", "==", …)`) to find Shape-C candidates.
3. For each hit, classify: shape (A/B/C/D/other), resource type, read volume, write volume, whether it's bounded (≤N docs) or unbounded.

**Deliverable:** A table with columns `[path, shape, resource, bounded?, notes]`. This is the ground truth the decision operates on.

**Expected size of table:** 15–30 rows based on initial grep.

### Q2. What cross-account queries do we run today, or plan to run?

**Method:**
1. Grep for admin-scoped endpoints, ops scripts, and background jobs that read across accounts.
2. Review each in-flight PRD for cross-account queries (e.g., MER-E's evaluation pipeline reading all traces, platform ops dashboards, billing aggregation).
3. Classify each query by which shape can serve it cheaply:
   - Shape A: requires iterating every `{type}_*` collection — expensive at scale
   - Shape B: works natively via `collectionGroup("{type}")` queries with a collection-group index
   - Shape C: works natively with a composite index on `account_id`
4. Include in the table: is this query latency-sensitive? Run-frequency?

**Deliverable:** List of cross-account queries and which shape(s) serve each cheaply.

**Why this matters:** If we have many cross-account queries, Shape A is painful. If we have zero, Shape A's cross-account "isolation-by-impossibility" may be a feature, not a bug.

### Q3. How does account deletion actually work today, and how would each shape change it?

**Method:**
1. Read `api/src/kene_api/routers/accounts.py` deletion flow end-to-end. Document every collection/doc/bucket it sweeps.
2. For each shape, estimate:
   - **Shape A:** every new feature requires updating the deletion list. Count how many collection names the flow already enumerates.
   - **Shape B:** `firestore.recursive_delete(db.collection("accounts").doc(account_id))` sweeps everything under the account doc in one call. Time this against a seeded test account with realistic fanout (100 docs × 5 subcollections).
   - **Shape C:** A query-and-batch-delete per collection, filtered by `account_id`. Time this too.
3. Benchmark deletion latency for a realistic account (seed 1k docs across multiple resources, measure wall-clock).

**Deliverable:** Deletion-complexity comparison with measured latencies.

### Q4. What are the Firestore platform limits that matter?

Reference the current [Firestore quotas](https://firebase.google.com/docs/firestore/quotas) and confirm against our expected scale. Specifically:

1. **Max subcollections per document** — Firestore has no documented hard cap, but there's a practical cap (~100 subcollection *names* per doc before the console UI becomes unusable). If Shape B concentrates everything under `accounts/{account_id}`, how many distinct subcollection names will we accumulate? (Current list: strategy_docs, strategy_audit, plans, plan_audit, skills, skills_versions, automations, knowledge_graph_nodes, knowledge_graph_edges, …) Estimate the 2-year list.
2. **Max document size (1 MiB)** — relevant only for Shape D. Current funnel/KPI blobs: what's the p99 doc size today? What's the growth trajectory (more channels, more tactics)? This tells us whether Shape D is quietly going to break.
3. **Collection-group index fan-out** — collection-group queries scan all collections with the same name. Shape B means a query on `collectionGroup("skills")` scans every account's skills subcollection. Is that the cost we want, or is Shape A's "the collection literally doesn't exist for other accounts" cheaper?
4. **Index count limits** — project-level cap on composite indexes is 200. Count current + projected indexes under each shape. Shape A uses collection-scoped indexes; a cross-account admin query under Shape A would need 1 index per account collection (infeasible). Shape B uses collection-group indexes (1 index serves all accounts).
5. **Write throughput** — Firestore documents 500 writes/sec per collection as a soft limit before auto-sharding. At our projected scale (accounts × ops/account), does Shape B's shared `skills` collection-group saturate faster than Shape A's per-account collections?

**Deliverable:** Answer each with a citation from Firestore docs and a number for our expected scale at 1 year and 3 years.

### Q5. What do security rules look like under each shape?

**Method:**
1. Draft Firestore security rules for one representative resource (Skills) under each of shapes A, B, C.
2. Have each rule enforce: (a) caller is a member of the target account, (b) skill's `account_id` matches the path.
3. Compare rule length, readability, and whether the rule can be authored without a custom claim or an auxiliary lookup.

**Observation:** Today we enforce access in the Python layer (`check_strategy_access`-style dependencies), not Firestore rules. If we're moving any future access to rules (e.g., direct-from-frontend reads for static data), that changes the weighting.

**Deliverable:** Three sample rule files + a recommendation on whether rules or Python-layer checks should be the source of truth.

### Q6. What's the developer ergonomics delta?

**Method:** Write the same list/get/create/update/delete flow as four drop-in service implementations (A, B, C, D). Compare:
1. Lines of code
2. Test-setup complexity (seeding data for tests — does each test need to create a different collection name?)
3. Migration ergonomics — if we add a new resource tomorrow, how many places do we touch?
4. Type-safety — does Pydantic/ADK code need to know the full collection path?

**Deliverable:** Side-by-side code samples. If one shape is meaningfully more ergonomic (e.g., half the boilerplate), weight accordingly.

### Q7. What does backup / export / disaster recovery look like?

**Method:**
1. Read Google's `gcloud firestore export` and `import` docs. Can it operate on a subcollection (Shape B)? On a single top-level collection (Shape A)? What about `collectionGroup`?
2. Today, do we back up Firestore? If yes, how? If no, what's the plan?
3. For each shape, estimate restore time for a single account vs. the whole project.

**Deliverable:** Answer per shape.

### Q8. Are there ADK / Vertex AI / Agent Engine constructs that assume a particular shape?

**Method:**
1. Check whether any ADK session-state persistence, memory API, or Agent Engine artifact API has opinions about collection structure.
2. Check whether the Skills ADK module (`google.adk.skills`) has any assumptions about where the skill originated (it reads the filesystem / passed-in objects, so probably no — but confirm).
3. Check whether our tracing/Weave integration namespaces by collection.

**Deliverable:** Short confirmation or list of constraints discovered.

## 5. Research questions — GCS

### Q9. Are there compliance, data-residency, or per-customer-CMEK requirements that would force bucket-per-account (Shape G2)?

**Method:** One conversation with whoever owns security/compliance (no one yet?), plus a review of any existing customer contracts / marketing claims about data isolation.

**Deliverable:** Yes/no + rationale. If yes, evaluate the per-project bucket quota ceiling (default 1000 buckets/project; bumpable but hard-capped). If no, G1 wins.

### Q10. What's our projected account count at 1, 3, and 5 years?

**Method:** Pull from business plan or ask product. Answer shape: "≤N at year 1, ≤M at year 3."

**Why this matters:** If >1000 accounts projected, Shape G2 is infeasible without project sharding. That effectively rules out G2.

### Q11. Do we plan per-account GCS lifecycle / retention policies, or do all accounts share the same rules?

**Method:** Ask product / legal whether retention policies (e.g., 30-day skills-trash, annual audit retention) need to vary by customer tier.

**Deliverable:** If policies are uniform across accounts, G1 is trivial. If they must vary, G1 still works (via object-level lifecycle via custom metadata) but is noticeably harder.

## 6. Decision criteria

Weight these criteria when evaluating research results. Order is approximate; the working group should adjust before synthesizing.

1. **Operational simplicity at our actual scale** — not theoretical scale. Optimize for the shape that makes day-to-day feature work faster, not the shape that would be textbook-optimal at 10M accounts.
2. **Cross-account query support** — if MER-E, platform ops, or billing need cross-account reads, favor Shape B or C.
3. **Account-deletion ergonomics** — we already feel this pain once per feature under Shape A. Favor whichever shape makes this a single code path.
4. **Security rules / isolation primitive** — if a structural guarantee ("different accounts literally cannot share a collection path") is a security feature we want, Shape A earns credit.
5. **Consistency across the codebase** — whatever we pick, we realign. The decision must commit to cleaning up the 2–3 existing patterns, not adding a fourth.
6. **Index budget headroom** — don't pick a shape that puts us on a fixed-cost collision course with the 200-composite-indexes-per-project cap.
7. **Reversibility** — how painful is it to migrate again if the decision turns out wrong in a year? (Firestore schema migrations are hand-rolled; the shorter the migration script, the better.)

## 7. Out of scope for this research

- **Non-account-scoped resources** (users, system templates, feature flags, global tool registry). Their shape is a separate question.
- **Neo4j schema** — the graph DB has its own account-scoping (node properties); not affected by this decision.
- **BigQuery / Vertex AI dataset layout** — analytics-store decisions are independent.
- **Notion / Linear / external tool data** — lives in those systems, not ours.
- **Choosing Firestore vs. another DB** — we're keeping Firestore.

## 8. What the deliverable looks like

After research concludes, the owner produces:

1. **A Review entry** in `docs/design/DESIGN-REVIEW-LOG.md`: title, status, context (summary of this brief + findings), decision, consequences, link to this file. (This step was completed in Review 15.)
2. **A migration plan** checked in as `docs/design/components/data-management/multi-tenant-migration-plan.md` if the decision changes the current pattern. The plan enumerates:
   - Every collection / path / bucket prefix that must move
   - The script or batch job that moves it (even in dev/staging — repeatability matters)
   - Code edits required (routers, services, repositories, tests, deployment configs)
   - How each in-flight PRD is affected (components/skills/projects/*, components/project-tasks/projects/*)
   - Terraform changes (indexes, bucket lifecycle, IAM)
3. **PRD updates** — if the decision changes the shape for Skills / Project Plans, edit the affected PRDs and add a line to `docs/design/DESIGN-REVIEW-LOG.md` referencing the Review entry that captures the decision.

## 9. Context for the next session

When you pick this up:

- **The current Skills PRDs (`docs/design/components/skills/projects/SK-PRD-01..04`) and the Project Plans PRD (`docs/design/components/project-tasks/projects/PR-PRD-01-data-model-and-api.md`) were written assuming Shape A.** If the decision goes Shape B or C, those PRDs need updates before any development starts. SK-PRD-01 specifically has ~15 spots referencing the collection name shape.
- **No users are in production**, so the migration plan can be aggressive — drop collections, rename buckets, do it in a single maintenance window. Backwards compatibility is not a constraint.
- **Start with Q1 and Q2** — the inventory and the cross-account query list are the biggest inputs into the decision. Once those are in hand, the answer often becomes obvious.
- **Expected total research effort:** 2–3 focused days. Not a sprint.

## 10. Reference

- `api/src/kene_api/routers/strategy.py` — canonical Shape A implementation
- `api/src/kene_api/firestore.py` — canonical Shape D implementation
- `api/src/kene_api/services/storage_service.py` — canonical Shape G1 implementation
- `api/src/kene_api/routers/accounts.py:968-970` — current account-deletion sweep (the pain point)
- [Firestore quotas and limits](https://firebase.google.com/docs/firestore/quotas)
- [Firestore data model best practices](https://firebase.google.com/docs/firestore/best-practices)
- [GCS bucket limits](https://cloud.google.com/storage/quotas)
- `CLAUDE.md` §"Documentation Model" — the DESIGN-REVIEW-LOG decision workflow this research feeds into
