# Data Residency Architecture — Regional Cells (US + EU)

**Status:** Draft for review · **Created:** 2026-05-29 · **Author:** Ken Williams (with automated residency audit)
**Scope:** Cross-component (Agentic Harness, Knowledge Graph, Chat, Integrations, Data Management, Billing, Data Pipeline, SAR-E/Performance, observability)
**Target:** First live users in ~1 month (≈ end of June 2026), distributed across US, Europe, and Asia.

This document is the program-level design for per-account data residency. It encodes the locked architectural decisions, the current-state gap register (produced by a 13-lane automated audit on 2026-05-29 — 142 findings, 52 critical / 40 high), the launch cut-line, and the breakdown into per-component PRDs. It is a cross-cutting design doc in the spirit of [`multi-tenant-data-model-research-findings.md`](multi-tenant-data-model-research-findings.md); the per-component PRDs it spawns follow the standard 10-section structure.

---

## 1. Executive summary

KEN-E already has the **routing key** (`data_region` on the account, values US / EU, "Data Storage Region" in the UI) and exactly **one** correctly region-pinned data plane: GCS business documents (`api/src/kene_api/services/storage_service.py:31-72`, US→`us-central1`, EU→`europe-west1`). That file is the **reference pattern** every other store must copy.

Everything else that touches account-scoped data is **single-region (`us-central1`) or global** — today KEN-E is, in the auditor's phrase, *"one US cell wearing a regional costume."* Five root causes generate the bulk of the findings:

1. A **single global Firestore database** backs all accounts (US + EU), with cross-account collection-group sweeps that assume one DB.
2. **Full prompt + response content is shipped to W&B Weave (US SaaS)** because `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` is set for dev/staging agent deploys (`deploy_ken_e.py:367-370`; prod already sets it `false`), and Weave (US SaaS) receives traces in *every* environment — the most direct egress of regulated EU content. For the EU cell the work is therefore guaranteeing capture stays off **and** not initializing US-hosted Weave (AH-PRD-12), not flipping a prod default.
3. **Vertex model inference + the Agent Engine reasoning/sandbox/session plane are pinned to `us-central1`** (bare model strings; ambient `VERTEX_AI_LOCATION`), so EU reasoning and EU context execute in the US. *(The recent `gemini-3.5-flash` 404 outage was an instance of this class — a bare model string resolving to the wrong endpoint.)*
4. **OAuth tokens are encrypted by a US KMS key** with no account routing — EU credentials encrypted by a US-region key.
5. **Neo4j is a single global Aura instance**, compounded by a cross-account authorization defect (see R-10).

A distinct integrity defect undermines the whole cell model: **`data_region` is mutable after account creation** with no guard (`accounts.py:832-834`) and an enabled UI dropdown — so an account can be silently moved between cells after its data has landed.

**Verdict:** An EU cell **can** be ready in ~1 month **iff** the 8 launch blockers in §6 are closed (or EU sign-ups are gated). The single hardest dependency is external: **whether Vertex AI Agent Engine is GA in a European region by launch.** If it is not, EU agent reasoning cannot be made resident in time and **EU sign-ups must be gated** until it is.

---

## 2. Locked decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Residency boundary = the account.** An account's *entire* data + processing plane is pinned to its `data_region`. | Aligns residency and latency for the common case (an EU customer's data + agents + users are all in EU). The only unavoidable latency cost is a user far from their account's home region — legally required. |
| D2 | **Two regions at launch: US and Europe.** No APAC cell at launch. | Per product decision (2026-05-29). Asia *users* attach to US/EU *accounts* (data stays in the account's region; they accept latency). Region set is a registry, extensible to APAC later. |
| D3 | **Regional cells + a thin global control plane.** Each region is a full stack; only auth, CDN, and an `account_id → region` routing directory are global. | The global directory holds routing metadata, not regulated content (confirmed acceptable, 2026-05-29). |
| D4 | **In-geography Vertex model endpoints — never `global` (steady state).** Model serving uses each region's single-region (`us-central1` / `europe-west1`) **or in-geography multi-region** (`us` / `eu`) endpoint. A model is adoptable in a cell only when it is served on that cell's endpoint. **Interim exception (Review 51, 2026-06-10):** staging/prod model serving routes to `global` while `gemini-3.1-pro-preview` (a `global`-only model) is in use — see §3.5 and the ⚠️ revert reminder. | The Vertex `global` endpoint gives no processing-location guarantee → a residency leak. The `us` / `eu` **multi-region** endpoints *do* guarantee in-geography (US-wide / EU-wide) processing, so they satisfy the no-leak requirement while serving newer / preview models that single regions do not. "Never `global`" still holds; "single-region only" was relaxed to "in-geography" (Review 50, 2026-06-09). The interim `global` exception is a temporary, model-driven relaxation **safe only while EU sign-ups are gated (D6)**; it reverts to in-geography routing once `gemini-3.1-pro-preview` is served on the `us` / `eu` multi-region endpoints. Supersedes the earlier "prefer global" stance now that residency is a hard requirement. |
| D5 | **`data_region` is immutable after account creation.** Changing region is a Phase-2 supervised migration, not a field edit. | A mutable region field silently orphans/splits data across cells and defeats every other fix. |
| D6 | **EU cell verified before EU sign-ups open.** If the launch-blocker set is not closed (esp. EU Agent Engine), gate EU sign-ups rather than process EU data in the US. | Under-promise beats a residency violation. |

---

## 3. Target architecture — regional cells

### 3.1 Global control plane (routing + identity only; NO regulated data)

- Global LB / CDN for the frontend + static assets (fast everywhere).
- Firebase Auth (global identity).
- **`account_id → home-region` routing directory** — a tiny, project-id-only Firestore lookup (`dependencies.py:36-37` is acceptable *for this purpose only*). Resolved once at the auth / account-selection boundary and pinned for the rest of the request.

### 3.2 Regional cell (one per region: `us` = `us-central1` / `nam5`; `eu` = `europe-west1` / `eur3`)

Each cell is a complete, independent stack:

| Layer | US cell | EU cell |
|-------|---------|---------|
| Firestore | `(default)` DB, `nam5` | `(default)` DB in a separate EU project, `eur3` |
| Neo4j | `NEO4J_URI_US` | `NEO4J_URI_EU` (Aura-EU or self-host on EU GKE) |
| Agent Engine (reasoning + sandbox + sessions) | `us-central1` | EU region **(gated on Agent Engine EU GA)** |
| Vertex model endpoint (model serving) | `global` (interim — revert target `us` multi-region) | `global` (interim — revert target `eu` multi-region) |
| GCS | `ken-e-files-us` | `ken-e-files-eu` ✅ already done |
| Redis (Memorystore) | US | EU |
| KMS keyring | `us-central1` | `europe-west1` |
| BigQuery | US dataset | EU dataset |
| Traces / logs | US sink | EU sink (or content-capture OFF for EU) |

**Recommended topology:** one **GCP project per region** (e.g. `ken-e-us` / `ken-e-eu`). This gives a clean `(default)` Firestore DB per region, separate KMS keyrings and IAM, and blast-radius isolation, and matches the existing per-env Terraform module shape (extend it to iterate over regions × environments).

### 3.3 Request flow

```
user → nearest edge (CDN/LB) → API resolves account.data_region (global directory)
     → pins the cell: regional Firestore client, Neo4j URI, Agent Engine + model endpoint,
       Redis, KMS key, trace sink → all downstream work stays in-cell
```

### 3.4 The reference pattern

`storage_service.py:_get_bucket_config(data_region)` is the canonical shape: a `data_region → (resource, location)` map with a US default and a normalize/validate step. **Every regionalization below replicates this pattern** — a `get_<resource>(account_id | data_region)` resolver that returns the region-appropriate client.

### 3.5 Model-endpoint strategy: dev experimentation vs. residency

**Decision (2026-05-29):** model-inference location is set **per deployment**, not per account within a cell — because each regional cell already runs its own Agent Engine (R-04), the engine's location pins inference for every account in that cell, so per-account model routing inside a cell is unnecessary.

| Environment / cell | Inference endpoint | Rationale |
|--------------------|--------------------|-----------|
| `development` | **`global`** | Dev holds no regulated data, and the `global` endpoint serves newly-released models (e.g. `gemini-3.5-flash`) months before regional endpoints — so dev is the model-experimentation sandbox. |
| `staging` / `prod` US cell | **`global`** (interim — revert target `us`) | `gemini-3.1-pro-preview` is served on `global` **only** (not on multi-region), so the US cell serves from `global` until the model reaches the `us` multi-region endpoint. Revert target: `us` (in-US processing). |
| `prod` EU cell | **`global`** (interim — revert target `eu`) | Same model-availability constraint. **Safe only while EU sign-ups are gated (D6)** — `global` does not keep EU inference in the EU. Revert to `eu` (EU multi-region) **before any EU account goes live**; see the ⚠️ revert reminder below. |

A small pure resolver `resolve_model_location(environment, data_region) -> location` encodes this. **Interim (Review 51, 2026-06-10):** it returns `global` for **every** environment because `gemini-3.1-pro-preview` is `global`-only; `data_region` is currently not branched on. The revert (in-geography routing — `development → global`; else `US → us`, `EU → eu`) is held in the resolver as the documented REVERT TRIGGER. The single-region `us-central1` / `europe-west1` strings remain in use for `VERTEX_AI_LOCATION` (engine / sandbox / session), which is a **separate** variable — see the mechanism caveat below. (Reinterpreted single-region → multi-region in Review 50; multi-region → interim `global` in Review 51; D4's "never `global`" remains the steady-state intent.)

> ⚠️ **FUTURE ACTION — in-geography revert reminder (Review 51).** When Google serves `gemini-3.1-pro-preview` on the `us` / `eu` **multi-region** endpoints, revert `resolve_model_location` (`app/adk/agents/agent_factory/model_routing.py`) to in-geography routing — `EU → "eu"`, `US → "us"` — and restore `GOOGLE_CLOUD_LOCATION` in `app/adk/.env.{staging,production}`. **This is required before any EU account goes live**, because the interim `global` route lets EU inference leave the EU (a D4 residency leak tolerated only under the D6 EU-sign-up gate). The resolver's REVERT TRIGGER comment carries the exact code; this is the model-serving half of **AH-PRD-11** (per-account region routing). Owner: agentic-harness / AH-PRD-11.

**Mechanism caveat (important):** ADK builds its genai client from `GOOGLE_CLOUD_LOCATION`, and the Agent Engine runtime **injects** that var (= the engine's deploy region), so the baked `.env` value is ignored under `load_dotenv(override=False)`. The resolver's output must therefore be applied **in-process at agent startup** — `os.environ["GOOGLE_CLOUD_LOCATION"] = resolve_model_location(...)` before the first model client is built — not via `.env`. (This is exactly why the existing `.env.staging` `GOOGLE_CLOUD_LOCATION=global` was inert.) `VERTEX_AI_LOCATION` is a separate var (engine/session/sandbox region) and is **not** changed by this.

**Consequence — dev must use only globally-served models.** Because the override is process-wide per deployment, every model used in dev must be served on `global`: migrate dev's `gemini-2.0-flash` / `-001` agents to `gemini-2.5-flash` (served on both `global` and regional), and confirm the dev embedding model is available on `global`.

**Model-promotion gate (preflight):** a model may be configured for staging/prod only after an automated check confirms it is served on the **in-geography endpoint** (single-region *or* multi-region) of **all** residency regions (US + EU) — never relying on `global`. Dev-on-`global` lets you build against a model in the meantime; the gate stops a `global`-only model from being promoted to a cell that cannot serve it in-geography — which is precisely the `gemini-3.5-flash` failure mode. Routing to the `us` / `eu` multi-region endpoints (Review 50) widens what passes the gate: a preview model served on the multi-region endpoint but not yet GA at a single region is promotable, because multi-region keeps processing in-geography. This pattern closes **AH-86** for dev and is the **first slice of DR-PRD-01**.

> **Recorded exception (Review 51).** `gemini-3.1-pro-preview` is served on `global` **only** — it passes neither the single-region nor the multi-region in-geography test, so the gate as written **forbids** it for staging/prod. It was nonetheless promoted on `global` as a conscious, time-boxed exception, valid **only while EU sign-ups are gated (D6)** so no EU account's inference actually leaves the EU. The exception expires when the model reaches the `us` / `eu` multi-region endpoints (the gate's normal condition) — see the ⚠️ revert reminder above. This is a recorded relaxation, not a silent bypass.

---

## 4. Per-store residency posture (current → action)

| Store | Current | Posture | Action |
|-------|---------|---------|--------|
| **GCS (business docs)** | US→us-central1, EU→europe-west1 | ✅ account-pinned | **Reference model — no change.** (But fix chat-artifact + strategy-artifact buckets, R-07.) |
| **Firestore** | Single `(default)` DB, `nam5`/us-central1 | ❌ single-region | EU Firestore (separate project), route by `data_region` at DI. **Keystone — R-01.** |
| **Neo4j** | Single global Aura instance | ❌ single-region | A separate EU **instance/DBMS** (not a second named database inside the US instance — same-instance databases share one cloud region, so that does not satisfy residency; and Aura multi-DB is tier-limited). Keep one database per regional instance; resolve `NEO4J_URI` by region. **R-06.** |
| **Agent Engine** (reasoning/sandbox/session) | us-central1 (ambient) | ❌ single-region | EU reasoning engine; thread `data_region` through build/sandbox/session. **R-04 (gated on EU GA).** |
| **Vertex model endpoint** | `global` (interim, Review 51 — `gemini-3.1-pro-preview` is `global`-only) | ❌ global | In-geography endpoint per account — single-region or `us`/`eu` multi-region; **revert from interim `global` to `eu` before any EU account goes live** (safe meanwhile only under the D6 gate). **R-03.** |
| **Redis** | Single global instance | ❌ single-region | Regional Memorystore; namespace keys by region. **R-11.** |
| **BigQuery** | Single US dataset | ❌ single-region | Per-region datasets; route by `data_region`. **R-14.** |
| **W&B / traces / logs** | Weave US SaaS + content capture; global Cloud Trace/Logging | ❌ global | EU: content capture OFF + EU-resident trace/log sink. **R-02 / R-12.** |
| **KMS** | us-central1, one keyring | ❌ single-region | Per-region keyrings; select by `data_region`. **R-05.** |
| **Global control plane** (auth, CDN, routing directory) | global | ✅ acceptable | No change (R-22). |

---

## 5. Residency gap register

52 critical / 40 high / 11 medium / 4 low / 35 confirmed-good across 142 raw findings, consolidated to 22 items. Severity is compliance risk; cut-line is in §6.

| ID | Sev | Cut | Component | Gap | Key sites |
|----|-----|-----|-----------|-----|-----------|
| **R-01** | 🔴 Crit | Blocker | data-management | Single global Firestore DB for all US+EU accounts; Shape B is logical-only, no physical residency | `firestore.py:61-83`, `dependencies.py:36-37` |
| **R-02** | 🔴 Crit | Blocker | agentic-harness | Full prompt+response content → W&B Weave (US SaaS); OTEL content capture on in dev/staging (prod already off), gated per-env not per-region; Weave US SaaS in all envs | `weave_observability.py:110-114`, `deploy_ken_e.py:367-370` |
| **R-03** | 🔴 Crit | Blocker | agentic-harness | Bare model strings → ambient/global Vertex endpoint; EU prompts processed in US | `builder.py:465` |
| **R-04** | 🔴 Crit | Blocker | agentic-harness | Agent Engine reasoning + sandbox + session pinned us-central1 | `deploy_ken_e.py:297-304`, `sandbox_pool.py:78-82`, `chat.py:376` |
| **R-05** | 🔴 Crit | Blocker | integrations | OAuth tokens encrypted with a US KMS key for all accounts | `encryption_service.py:50-52,145-230` |
| **R-06** | 🔴 Crit | Blocker | knowledge-graph | Single global Neo4j Aura instance; EU org/brand data in US DB. Fix = a **separate EU instance** (one DBMS per region), not a second named DB in the US instance | `database.py:26-28`, `chat.py:138-139` |
| **R-07** | 🟠 High | Blocker | chat | Chat artifact pipeline hardcodes US bucket + US-only allowlist | `chat/artifacts.py:184-189,217-224` |
| **R-08** | 🔴 Crit | Blocker | data-management | `data_region` mutable after creation (no guard) — defeats cell invariant | `accounts.py:832-834`, `AccountSettingsTabs.tsx:442-461` |
| **R-09** | 🟠 High | Phase 1 | data-management | Cross-account collection-group sweeps assume one DB (deletion/scheduler skip EU once split) | `chat/side_table.py:219-224`, `audit_service.py:246-277` |
| **R-10** | 🟠 High | **Hotfix now** | knowledge-graph | 7 Neo4j cascade queries omit `account_id` → cross-account read/delete (live auth leak) | `graph_sync_service.py:791,806,942,968` |
| **R-11** | 🟠 High | Phase 1 | chat | Redis single-region, not account/region partitioned (org context + GA creds cached) | `redis_client.py:63-194`, `chat.py:547-784` |
| **R-12** | 🟠 High | Phase 1 | agentic-harness | Cloud Trace/Logging + >250KB large-attr bucket are global | `tracing.py:55-60,130-137`, `structured_logging.py:95-129` |
| **R-13** | 🟠 High | Phase 1 | billing | `usage_records` / `tool_usage_events` global Shape-C; unreachable from EU DB once split | `usage.py:129,300`, `tracking/usage.py:135,262` |
| **R-14** | 🟠 High | Phase 1 | sar-e | BigQuery single-region (US); EU analytics in US dataset | `bigquery.py:59-62,245-255` |
| **R-15** | 🟡 Med | Phase 1 | agentic-harness | MCP server URLs not region/account-routed | `mcp.py:250-252,262-266` |
| **R-16** | 🟠 High | Phase 1 | chat | GA creds + org context persisted in US-hosted session state | `chat.py:588-671` |
| **R-17** | 🟡 Med | Phase 1 | chat | Chat idempotency keys in a global Firestore collection | `side_table_handlers.py:29,77` |
| **R-18** | 🟡 Med | Phase 1 | data-management | `data_region` lacks enum validation; unknown values default to US | `accounts.py:545-752` |
| **R-19** | 🟠 High | Phase 1 | data-pipeline | Data Pipeline service/run-records/artifacts not regionalized (pre-launch component) | `DP-PRD-01-foundation.md:225` |
| **R-20** | 🟡 Med | Phase 2 | sar-e | SAR-E/Performance will inherit all leaks unless designed regional | `sar-e/README.md`, `performance/README.md` |
| **R-21** | 🟡 Med | Phase 2 | data-management | Cross-cell global admin/analytics + change-region migration tooling missing | `monitoring_topics.py:179-221`, `admin.py:63-215` |
| **R-22** | 🟢 Low | Phase 2 | data-management | Global control-plane confirmations (auth, routing dir, GCS docs) — no change | `dependencies.py:36-37`, `storage_service.py:31-72` |

---

## 6. Launch cut-line

### 6.1 Launch blockers — EU regulated content must not leave the EU (or gate EU sign-ups)

R-01 (Firestore keystone), R-02 (Weave content egress), R-03 (regional model endpoint), R-04 (EU Agent Engine — *gated on EU GA*), R-05 (KMS), R-06 (Neo4j), R-07 (chat artifact buckets), R-08 (immutable `data_region`).

**Gating rule:** if any blocker is not closed by launch — most likely R-04 if Agent Engine is not GA in an EU region — **open US sign-ups only and gate EU sign-ups** behind a feature flag until the EU cell is verified end-to-end (an EU account's content provably never appears in US Firestore, Neo4j, traces, KMS, or the model endpoint).

### 6.2 Phase 1 — full regional-cell hardening (immediately post-launch)

R-09, R-11, R-12, R-13, R-14, R-15, R-16, R-17, R-18, R-19.

### 6.3 Phase 2 — steady-state operation

R-20 (SAR-E/Performance regional-by-design), R-21 (cross-cell admin + change-region migration), R-22 (confirmations only).

### 6.4 Independent security hotfix — ship now, not gated on residency

**R-10** is a cross-account authorization leak that is **exploitable today** regardless of regions: `delete_product_category()` / `delete_product()` / `update_product()` match Cypher on `node_id` alone, so a `node_id` from another account can discover and cascade-delete relationships across tenants. Bind `account_id` in every `WHERE` clause (template: `create_node` / `list_nodes` / `get_node`) and add a Cypher review checklist. This should go out as a standalone hotfix PR ahead of the residency program.

### 6.5 Transitive critical path — the launch-blocking dependency chain

**Decision (2026-05-29): close the full residency blocker set by launch — EU live at launch, not gated.** §6.1 lists eight gap-register blockers, but each launch-blocker *slice* also depends on its component's **foundation** PRD, and every one of those is currently un-started. The genuine launch-critical set is the transitive closure below — it is the program's dominant schedule risk and must be managed as a single critical path, not eight independent blockers:

| Launch blocker (slice) | Foundation it also needs (`blocked_by`) | Foundation status | Critical-path action |
|---|---|---|---|
| DM-PRD-09 — R-01, R-08 | DM-PRD-08 (prod cutover) | ✅ shipped | **Start now** — keystone, unblocked; blocks all others. |
| KG-PRD-07 — R-06 | KG-PRD-01 (migration runner) | not started | KG-PRD-01 has no dependencies — start in parallel now. |
| CH-PRD-07 — R-07, R-11, R-17 | CH-PRD-05 (todo lists + artifacts) | not started | Start CH-PRD-05 now. |
| AH-PRD-11 — R-03, R-04, R-16 | AH-PRD-09 (per-turn dispatch; 6-phase) | not started | AH-PRD-09's prerequisites (AH-PRD-01/02, DM-PRD-00) are shipped — start now; it is the long pole. The R-03 model-routing half can land early against already-shipped surfaces (`model_routing.py` + the before-agent callback), so split it from the R-04/R-16 engine work. |
| AH-PRD-12 — R-02, R-12 | AH-PRD-11 → AH-PRD-09 | not started | Sequenced behind AH-PRD-11; the R-02 content-capture-off half can land early/independently. |
| IN-PRD-08 — R-05 | IN-PRD-01 → DM-PRD-07 → PR-PRD-01 + DM-PRD-05 | not started (3-deep) | **Longest chain, highest risk** — R-05 sits behind roles/members/audit + the project-tasks data model, none of it residency work. De-risk first, or scope R-05 to regionalize the *current* encryption substrate without waiting for the full IN-PRD-01 (IN-PRD-08 §2 already supports either substrate). |

**Crash plan.** DM-PRD-09, KG-PRD-01, CH-PRD-05, and AH-PRD-09 are all startable now (prerequisites shipped) and are the long poles — run them in parallel immediately. The R-10 hotfix ships ahead of all of it (§6.4). The IN-PRD-01 → DM-PRD-07 → PR-PRD-01 chain is the critical path for R-05 and needs the earliest de-risking, or the scoped-down R-05 above.

**The one risk the crash plan cannot remove — R-04 (external).** Whether Vertex AI Agent Engine is GA in an EU region by launch (open Q1) is outside the team's control. Committing to an EU launch does not change that: if EU Agent Engine GA has not landed, AH-PRD-11's R-04/R-16 (EU reasoning / sandbox / session) cannot be made resident, and locked decision **D6** still governs — gate EU sign-ups **for that reason alone** until GA lands, even with every internal blocker closed. R-04 is therefore the single residual launch risk under this posture: track Q1 weekly and keep the EU sign-up gate (Feature-Flags) ready as the R-04-specific fallback.

---

## 7. Breakdown into component PRDs

**Homing decision (2026-05-29):** data residency is **not** a new component. Each slice below is a PRD **homed in the existing component that owns the affected code**, carrying that component's PRD prefix and next-available number. The program is held together by two cross-cutting artifacts, not by a component directory:

1. **This design doc** — the cross-component spec (locked decisions, gap register, cut-line). It plays the role `multi-tenant-data-model-research-findings.md` played for the Shape B migration.
2. **The "Data Residency (US + EU)" Linear Initiative** — the execution tracker that groups every component slice's Linear project.

The **keystone is `DM-PRD-09` (Regional-cell foundation)**, homed in Data Management. It ships the `account_id → region` routing directory, the `get_<resource>(account_id)` DI pattern — the **Regional Cell routing convention**, documented in [`components/data-management/README.md`](components/data-management/README.md) §7.8 the same way the Shape B path convention is the cross-component contract — and `data_region` immutability + enum validation. **Every other slice is `blocked_by` `DM-PRD-09` and reuses its routing helper rather than reinventing per-component.**

The `DR-PRD-NN` column is a stable *logical* label tying each slice back to the gap register (§5) and is **independent of the component PRD numbers** (e.g. logical `DR-PRD-00` becomes `DM-PRD-09`). The **Owning component → Component PRD** column is the actual PRD / Linear project the slice becomes; `NN` = next-available number in that component, assigned at creation.

| Logical slice | Title | Closes | Owning component → Component PRD | Notes |
|-----|-------|--------|----------------------------------|-------|
| **DR-PRD-00** | Regional-cell foundation | R-01, R-08, R-18, R-22 | **data-management → `DM-PRD-09`** | GCP project-per-region, Terraform regionalization, global routing directory, `get_firestore(account_id)` DI, `data_region` immutability + enum. **Keystone — created first; blocks all others.** |
| **DR-PRD-01** | Agent reasoning + inference residency | R-03, R-04, R-16 | agentic-harness → `AH-PRD-11` | EU Agent Engine, regional model endpoint, sandbox + session routing. **Gated on EU Agent Engine GA.** First slice already shipped: the per-environment `resolve_model_location` resolver (`development → global`) closing AH-86 in dev (PR #751; see §3.5). |
| **DR-PRD-02** | Observability residency | R-02, R-12 | agentic-harness → `AH-PRD-12` | EU content-capture off + EU-resident trace/log sink + large-attr bucket. |
| **DR-PRD-03** | Integrations residency | R-05 | integrations → `IN-PRD-08` | Per-region KMS keyrings; `integration_credentials` / `oauth_states` region-routed. |
| **DR-PRD-04** | Knowledge-graph residency | R-06 | knowledge-graph → `KG-PRD-07` | One EU Neo4j **instance per region** (not multi-DB in one instance); keep a single database per regional instance; `NEO4J_URI` routing by `data_region`. Confirm Aura-EU vs self-host (open Q4). *(R-10 ships separately as a hotfix.)* |
| **DR-PRD-05** | Chat residency | R-07, R-11, R-17 | chat → `CH-PRD-07` | Region-routed artifact buckets, regional Redis, Shape-B idempotency keys. |
| **DR-PRD-06** | Telemetry & analytics residency | R-13, R-14 | billing → `BL-PRD-07` (+ sar-e) | Shape-B/regional `usage_records`; per-region BigQuery datasets (BigQuery work split to a future `SE-PRD`). |
| **DR-PRD-07** | Cross-account sweep regionalization | R-09 | project-tasks → `PR-PRD-10` (+ data-management) | Per-region schedulers (PR-PRD-06), session-end loop (KG-PRD-04), deletion fan-out, audit. |
| **DR-PRD-08** | Data Pipeline residency | R-19 | data-pipeline → `DP-PRD-07` | Regional Cloud Run + run records + artifacts (fold into DP-PRD before it ships). |
| **DR-PRD-09** | SAR-E / Performance residency-by-design | R-20 | sar-e → `SE-PRD-08` (+ performance) | Bake regional requirements into SE-PRD-01/02/05/06 + PE-PRD-01. |
| **DR-PRD-10** | Cross-cell admin + change-region migration | R-21 | data-management → `DM-PRD-10` | Per-region fan-out for admin ops; supervised account region-migration tool. |
| **(hotfix)** | Neo4j cross-account `account_id` binding | R-10 | knowledge-graph (standalone PR) | Ships ahead of the program; not gated on residency. |
| **(phase 1)** | MCP server region/account routing | R-15 | agentic-harness — Phase-1 follow-up (slice TBD) | Not a launch blocker; deferred to post-launch Phase-1 hardening. Explicitly **not** folded into AH-PRD-11 (which excludes it, §2). Listed here so the gap-register item has an owner rather than being orphaned. |

**Status (2026-05-29):** the [Data Residency (US + EU) Initiative](https://linear.app/ken-e/initiative/data-residency-us-eu-e60f510ef09b), the keystone `DM-PRD-09` (full PRD authored), and **stub Linear projects for all ten dependent slices** — each linked to the Initiative, status Backlog, blocked by `DM-PRD-09`, homed in the team above — are created. The numbers in the **Component PRD** column are the allocated IDs. **The component PRD documents for all ten dependent slices are now authored** (in this change), each against the *proposed* DM-PRD-09 foundation contract and carrying its relevant open questions — so each will need a reconciliation pass if the foundation's open questions (Q3 topology / Q5 org-region scope / Q6 EU region) resolve differently. Multi-component slices (DR-PRD-06/07/09) are homed in the primary component's project with the secondary team attached for visibility.

---

## 8. Open questions (need answers before / during DR-PRD-00/01)

1. **🚧 Hard dependency: is Vertex AI Agent Engine GA in a European region by launch?** This single answer determines whether the EU cell is viable at launch or EU sign-ups must be gated (R-04).
2. **W&B Weave residency:** does W&B offer an EU-hosted/self-hosted tier, or is the launch decision simply "no Weave + content-capture off for EU"? Confirm with legal whether metadata-only traces are acceptable (R-02).
3. **Topology:** one GCP project per region (recommended) vs. one project with regional resources? Affects Firestore, KMS, IAM, Terraform shape.
4. **Neo4j EU:** Aura-EU under our plan, or self-host on EU GKE? Decide week 1 (R-06).
5. **Org/region scope:** can one organization contain accounts in *both* cells? If yes, all cross-account sweeps (deletion, audit, usage) must fan out per region (R-09). If org is region-pinned, routing simplifies.
6. **EU region choice:** confirm `europe-west1` (Belgium, the existing GCS pattern) for *all* EU stores, or does data-sovereignty require a specific member-state region? *(EU model serving target is the `eu` multi-region endpoint — Review 50 — but is **temporarily routed to `global`** because `gemini-3.1-pro-preview` is `global`-only; revert to `eu` before any EU account goes live, Review 51. This question otherwise applies to the `VERTEX_AI_LOCATION` plane — engine / sandbox / session / Firestore / Neo4j / KMS — where a specific member-state region may still be required.)*
7. **Existing data:** are there EU-designated accounts already holding data in the current US Firestore/Neo4j that must be migrated before launch, or is the EU cell green-field (new EU sign-ups only)?
8. **"Regulated content" for traces/logs:** confirm with legal whether trace/log *metadata* (account_id, user_id, session_id, tool names, durations, token counts) without message content may live in a US sink for EU accounts — this sets the bar for R-12.

---

## 9. Reference

- **Audit provenance:** 13-lane automated read-only audit of the codebase + design docs, 2026-05-29 — 142 findings across data-management, agentic-harness, chat, knowledge-graph, integrations, data-pipeline, sar-e/performance, skills, billing, feature-flags, observability, and frontend account lifecycle.
- **Reference implementation:** `api/src/kene_api/services/storage_service.py:31-72` (GCS regional routing).
- **Related:** [`multi-tenant-data-model-research-findings.md`](multi-tenant-data-model-research-findings.md) (Shape B; its "G1 confirmed unless Q9 surfaces a compliance requirement" — Q9 has now surfaced), [`components/data-management/README.md`](components/data-management/README.md), [`../KEN-E-System-Architecture.md`](../KEN-E-System-Architecture.md).
- **Model-endpoint context:** the `gemini-3.5-flash` 404 incident (2026-05-28/29) is an instance of R-03 — a bare model string resolving to a regional endpoint that does not serve the model. The §3.5 per-environment strategy (dev → `global`; in-geography multi-region elsewhere, **interim-routed to `global` for the `global`-only `gemini-3.1-pro-preview`** — Review 51) + a model-availability preflight (per residency region) closes AH-86 in dev and prevents recurrence; AH-86 is **not** resolved by PR #750 (an unrelated specialists-block change).
