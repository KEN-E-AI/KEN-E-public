# CH-PRD-07 — Chat Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Chat
**Initiative:** Data Residency (US + EU)
**Blocked by:** [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md), [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
**Blocks:** —
**Estimated effort:** 3–4 days

> **Program context.** This is the **chat slice** of the data-residency program (logical `DR-PRD-05` in the program breakdown). The program is *not* a new component: each slice is a PRD homed in the component that owns the affected code, bound together by the **Data Residency (US + EU)** Linear Initiative and the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md). Read that doc's §1–§3 (esp. §2 locked decisions, §3.2 per-cell layer table, §3.4 the reference pattern) and §5 (gap register — **R-07, R-11, R-17**) before this PRD. This project reuses, and never redefines, the keystone foundation shipped by [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS`, `resolve_account_region(account_id)`, and `get_firestore_for_account(account_id)`.

---

## 1. Context

Chat touches three account-scoped data planes that are still single-region (`us-central1`) or global, so an EU account's regulated content lands in the US (program spec §4 per-store posture table, chat-artifact + Redis rows):

1. **Chat artifact buckets are hardcoded US.** The artifact pipeline shipped by [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md) resolves the GCS bucket to `ken-e-{environment}-files-us` regardless of the account's region (`api/src/kene_api/chat/artifacts.py:184-189`), and signs URLs only against a **US-only allowlist** (`artifacts.py:217-224`). An EU account's session artifacts are therefore written to, and served from, the US bucket — even though GCS already has an EU bucket (`ken-e-files-eu` / `europe-west1`) wired by the reference pattern `storage_service.py:_get_bucket_config` (`storage_service.py:31-72`). **This is R-07, a launch blocker.**

2. **Redis is single-region.** The org-context cache and the Google-Analytics-credentials cache are populated during session creation (`api/src/kene_api/routers/chat.py:543-697`) against one global Memorystore instance via `redis_client.py` (`redis_client.py:63-194`), with keys `chat:org_context:{account_id}` and `chat:ga_creds:{account_id}` (`cache.py:211-228`) that carry **no region**. EU org context and EU GA credentials are cached in a US instance, and US/EU keys collide in one keyspace. **This is R-11, Phase 1.**

3. **Chat idempotency keys live in a global Firestore collection.** The internal side-table update path writes at-most-once gate documents to a top-level `chat_idempotency_keys/{sha256(key)}` collection (`api/src/kene_api/chat/side_table_handlers.py:29,77`) through the global control-plane Firestore client (`db` flows from `get_firestore_client()`). Once Firestore is split per region (R-01), an EU session's idempotency gate is unreachable from the EU database, and EU routing metadata sits in the US. **This is R-17, Phase 1.**

This PRD makes all three account-pinned by **routing through the foundation resolver**, mirroring the GCS reference pattern. **No new store is regionalized that the foundation doesn't already supply**, and **no existing data is migrated** (green-field per program spec §8 Q7 — new EU sign-ups only).

**Out of this slice (owned elsewhere):** the **session GA-creds / org-context residency** gap — that the *materialized* org context + GA credentials are persisted into US-hosted ADK **session state** (`chat.py:588-671`) — is **R-16**, owned by **[AH-PRD-11](../../agentic-harness/projects/AH-PRD-11-agent-reasoning-inference-residency.md)** (the agent reasoning + session plane). CH-PRD-07 regionalizes only the *Redis cache* of those values (R-11). The two are complementary: AH-PRD-11 pins where session state physically lives; CH-PRD-07 pins where the cache that feeds it lives.

## 2. Scope

### In scope

- **Region-routed artifact buckets (R-07).** Replace `artifacts.py::_resolve_bucket` (`184-189`) so the bucket is chosen by the account's `data_region`, reusing `storage_service.py`'s `data_region → (bucket, location)` map shape rather than the hardcoded `ken-e-{environment}-files-us`. Replace the US-only `_ALLOWED_GCS_BUCKETS` frozenset (`217-224`) with a region-aware allowlist derived from the same map (both US and EU buckets, all environments), so `generate_artifact_signed_url` can sign for an EU blob. The bucket-config map is the single source of truth, mirroring DM-PRD-09's `CELLS` shape; chat does not hardcode bucket strings beyond that map.
- **Region-routed artifact indexing (R-07).** `register_artifact` and `list_artifacts` currently read/write the Firestore index via the global `get_firestore_client()` (`artifacts.py:244,427`). Route them through `get_firestore_for_account(account_id)` so the `ChatArtifactIndex` row lands in the account's home cell alongside the rest of its Shape-B data. The `account_id` is already in hand (`tool_context.state["account_id"]` on write; the ownership-gated caller on read).
- **Regional Redis (R-11).** A regional Memorystore per cell (US / EU), selected by `resolve_account_region(account_id)` at the chat caching call sites (`chat.py:543-697`). Two mechanisms, pick one in implementation (§5): (a) a `get_redis_for_account(account_id)` resolver returning the per-region client, or (b) a region prefix on the cache key. **This PRD ships both the region-namespaced keys** (`chat:{region}:org_context:{account_id}`, `chat:{region}:ga_creds:{account_id}` in `cache.py:211-228`) **and** the per-region client selection, so EU values neither collide with US keys nor live in the US instance.
- **Shape-B / regional idempotency keys (R-17).** Move `chat_idempotency_keys` from the global top-level collection (`side_table_handlers.py:29,77`) into the account's regional database via `get_firestore_for_account(account_id)`, under the Shape-B path `accounts/{account_id}/chat_idempotency_keys/{sha256(key)}`. `apply_side_table_update` already receives `account_id` (`side_table_handlers.py:61-67`); thread the region-routed `db` in from the caller (`chat.py:2173,2319,3176`) instead of the global client. TTL semantics (24 h) unchanged.
- **Convention docs.** A short "Chat residency routing" note under [`../README.md`](../README.md) §7 pointing at the three call sites and the foundation resolver; a one-line cross-reference in the §7.5 artifact-save wrapper contract that the wrapper now routes by region.

### Out of scope

- **Defining the resolver / region registry** — owned by [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md). This PRD *consumes* `Region`, `CELLS`, `resolve_account_region`, `get_firestore_for_account`.
- **Standing up the EU Memorystore instance / EU GCS bucket / EU Firestore** — infra is foundation (DM-PRD-09 Terraform) + the existing GCS reference pattern. This PRD wires the application code to route to them.
- **Session GA-creds + org-context residency (R-16)** — owned by [AH-PRD-11](../../agentic-harness/projects/AH-PRD-11-agent-reasoning-inference-residency.md) (ADK session state plane). See §1.
- **Migrating existing US-resident chat artifacts / idempotency rows / cache entries into the EU cell** — green-field (program spec §8 Q7); supervised migration is DR-PRD-10.
- **Todo lists** ([CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)) — they live in ADK `session.state`, not in any store this PRD routes; their residency follows the session plane (AH-PRD-11).
- **The chat side-table itself** (`accounts/{account_id}/chat_sessions/*`) — already Shape-B; its physical residency is delivered by the foundation's Firestore DI refactor (R-01), not re-plumbed here. Only the *global* `chat_idempotency_keys` collection moves.

## 3. Dependencies

- **[DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)** complete — the keystone. Provides `shared/residency/regions.py` (`Region`, `CellConfig`, `CELLS`, `normalize_region`) and `shared/residency/routing.py` (`resolve_account_region`, `get_firestore_for_account`). **Hard.**
- **[CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)** complete — ships `chat/artifacts.py` (the `register_artifact` wrapper, `_resolve_bucket`, `_ALLOWED_GCS_BUCKETS`, `list_artifacts`, `generate_artifact_signed_url`) and the idempotency path this PRD regionalizes. **Hard.**
- Reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region → (bucket, location)` map) — the shape the artifact-bucket map copies.
- Existing call sites this PRD modifies: `chat/artifacts.py:184-189,217-224,244,427`; `chat/side_table_handlers.py:29,77`; `routers/chat.py:543-697,2173,2319,3176`; `cache.py:211-228`; `redis_client.py:63-194`.
- **External / open:** confirm the EU Memorystore instance + connection env (`REDIS_HOST_EU` or per-cell config) with infra; confirm the EU artifact bucket naming matches the GCS reference (`ken-e-{env}-files-eu`). EU Agent Engine GA (program spec §8 Q1) does **not** block this PRD — it blocks AH-PRD-11.

## 4. Data contract

### 4.1 Artifact bucket map (mirrors `storage_service.py`)

```python
# api/src/kene_api/chat/artifacts.py — replaces hardcoded _resolve_bucket
# Keyed identically to storage_service._get_bucket_config; one source of truth.
def _artifact_bucket_for_region(environment: str, region: Region) -> str:
    # environment ∈ {production, staging, development}; region ∈ {US, EU}
    # production: US→ken-e-files-us / EU→ken-e-files-eu
    # staging:    US→ken-e-staging-files-us / EU→ken-e-staging-files-eu
    # development:US→ken-e-dev-files-us / EU→ken-e-dev-files-eu
    ...
```

The signed-URL allowlist (`_ALLOWED_GCS_BUCKETS`) becomes the set of *all* values this map can produce across `{US, EU} × {production, staging, development, dev}`, so a legitimate EU blob signs and a tampered out-of-system bucket is still rejected.

### 4.2 Region-namespaced cache keys (`cache.py`)

| Key (today) | Key (this PRD) |
|---|---|
| `chat:org_context:{account_id}` | `chat:{region}:org_context:{account_id}` |
| `chat:ga_creds:{account_id}` | `chat:{region}:ga_creds:{account_id}` |

`region` is the lower-cased `Region` value (`us` / `eu`) from `resolve_account_region(account_id)`. The per-region Redis client (one client per region, cached) backs the actual instance selection; the key prefix is defence-in-depth against a single-instance misconfiguration. Other chat keys (`chat:user_sessions:{user_id}`, `chat:session:{user_id}:{session_id}`) are **user-scoped, not account-scoped**, and are routed via the user's resolved account region at their call site (or left in the home cell if the user is single-account) — tracked but not load-bearing for the launch blocker.

### 4.3 Idempotency-key path (Shape B + regional DB)

```
# was: global top-level collection on the control-plane client
chat_idempotency_keys/{sha256(idempotency_key)}            # global  (R-17)

# becomes: account-scoped, in the account's regional Firestore
accounts/{account_id}/chat_idempotency_keys/{sha256(idempotency_key)}   # via get_firestore_for_account
```

Document body (gate timestamp + `expires_at`, 24 h TTL) and the `create()`-as-compare-and-swap semantics (`side_table_handlers.py:117`) are unchanged. Only the database (regional, not global) and the path (Shape B, not top-level) change.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/chat/artifacts.py` — replace `_resolve_bucket` (`184-189`) with the region-keyed map (§4.1); derive `_ALLOWED_GCS_BUCKETS` (`217-224`) from that map; route `register_artifact` (`427`) + `list_artifacts` (`244`) through `get_firestore_for_account(account_id)`; resolve region from the account's `data_region` for bucket choice |
| Modify | `api/src/kene_api/cache.py` (`211-228`) — `org_context_key` / `ga_credentials_key` take a `region` and emit `chat:{region}:…` |
| Modify | `api/src/kene_api/redis_client.py` (`63-194`) — add a per-region client selection (`get_redis_for_account(account_id)` or a region→client cache); keep the graceful-degradation + `set_json` failure-counter behavior intact |
| Modify | `api/src/kene_api/routers/chat.py` (`543-697`) — resolve region once per request via `resolve_account_region(selected_account_id)`; pass it to the cache-key builders + Redis selection in `load_org_context` / `load_ga_credentials` |
| Modify | `api/src/kene_api/chat/side_table_handlers.py` (`29,77`) — write the idempotency gate under `accounts/{account_id}/chat_idempotency_keys/{hash}` (Shape B); accept the region-routed `db` from the caller |
| Modify | `api/src/kene_api/routers/chat.py` (`2173,2319,3176`) — supply `get_firestore_for_account(account_id)` as the `db` passed into `apply_side_table_update` |
| Modify | [`../README.md`](../README.md) §7 — add the "Chat residency routing" note; one-line cross-ref in §7.5 |
| Create | `api/tests/unit/chat/test_artifact_bucket_routing.py` |
| Create | `api/tests/unit/chat/test_cache_key_region_namespacing.py` |
| Create | `api/tests/integration/chat/test_idempotency_key_regional.py` |
| Create | `api/tests/integration/chat/test_artifact_index_regional.py` |

**Resolve-once discipline.** Region is resolved a single time per chat request at the account-selection boundary (matching DM-PRD-09's pin-once convention) and threaded through; no call site re-resolves per artifact / per cache write.

## 6. API contract

This PRD publishes **no new public HTTP surface**. It is a residency-routing change behind existing endpoints + the `register_artifact` wrapper. The observable contract changes are physical-location only:

| Contract | Change | Source of truth |
|---|---|---|
| `register_artifact(...)` / `list_artifacts(...)` | Bucket + Firestore index now selected by the account's `data_region` (was always US) | `api/src/kene_api/chat/artifacts.py` |
| `GET /api/v1/chat/conversations/{id}/artifacts` | Signs URLs against the region-aware allowlist (EU blobs now signable) | `api/src/kene_api/routers/chat.py` (CH-PRD-05 endpoint) |
| `POST /api/v1/internal/chat/side-table/update` | Idempotency gate now in the regional Shape-B path; response shape (`{"status": "applied"\|"duplicate"}`) unchanged | `api/src/kene_api/chat/side_table_handlers.py` |
| Cache keys `chat:{region}:org_context:*` / `chat:{region}:ga_creds:*` | Region-namespaced; per-region instance | `api/src/kene_api/cache.py` |

Consumed-from contract: `Region`, `CELLS`, `resolve_account_region`, `get_firestore_for_account` from `shared/residency/*` (DM-PRD-09) — imported, never redefined.

## 7. Acceptance criteria

1. `_artifact_bucket_for_region` returns `ken-e-{env}-files-eu` for an EU account and `ken-e-{env}-files-us` for a US account across all three environments; the derived `_ALLOWED_GCS_BUCKETS` contains both regions' buckets for every environment.
2. `register_artifact` for an **EU** account writes the GCS blob under the EU bucket and writes the `ChatArtifactIndex` row through `get_firestore_for_account` into the EU database; for a US account, US bucket + US database. (Verified by asserting the resolved bucket + the Firestore client's target.)
3. `generate_artifact_signed_url` signs a URL for an EU-bucket `gcs_path` (previously raised `ValueError` "bucket … not in the system allowlist"); a bucket outside the US+EU map is still rejected.
4. `org_context_key(account_id, region=EU)` → `chat:eu:org_context:{account_id}`; `region=US` → `chat:us:org_context:{account_id}`; same for `ga_credentials_key`. A US and an EU account never produce the same cache key.
5. The chat session-creation path resolves region exactly once via `resolve_account_region(selected_account_id)` and uses the per-region Redis client; an EU account's org-context / GA-creds cache read+write hits the EU instance (asserted via the resolved client, not a real instance).
6. `apply_side_table_update` for an EU account writes the idempotency gate to `accounts/{account_id}/chat_idempotency_keys/{hash}` in the EU database; at-most-once semantics (second call → `{"status": "duplicate"}`) hold within the regional collection; no document is written to the global top-level `chat_idempotency_keys`.
7. **Control-plane isolation:** no account-scoped chat read/write (artifact index, idempotency gate, account cache) goes through the global `get_firestore_client()`; grep gate + unit assertion on call sites.
8. The foundation symbols (`Region`, `CELLS`, `resolve_account_region`, `get_firestore_for_account`) are **imported** from `shared/residency/*`; this PRD adds no parallel region enum or resolver (grep gate).
9. [`../README.md`](../README.md) §7 documents the chat residency routing and the three call sites; §7.5 notes the wrapper routes by region.
10. `make lint` passes. `pytest api/tests/unit/chat/test_artifact_bucket_routing.py api/tests/unit/chat/test_cache_key_region_namespacing.py api/tests/integration/chat/test_idempotency_key_regional.py api/tests/integration/chat/test_artifact_index_regional.py` passes.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_artifact_bucket_routing.py`, `test_cache_key_region_namespacing.py`)
- `_artifact_bucket_for_region` table-driven over `{US, EU} × {production, staging, development}` (AC-1).
- `_ALLOWED_GCS_BUCKETS` is exactly the closure of the map (AC-1); EU bucket present, an unknown bucket absent (AC-3).
- `generate_artifact_signed_url` accepts an EU `gcs_path`, rejects an out-of-system bucket (AC-3) — mock `storage.Client`, assert no `ValueError` for EU.
- Cache-key builders emit `chat:{region}:…`; US vs EU never collide (AC-4).

### Integration (Firestore emulator + mocked Neo4j + mocked region resolver)
- `register_artifact` / `list_artifacts`: stub `resolve_account_region` → `EU`; assert the bucket resolved is the EU bucket and the Firestore write went through the EU `CellConfig` client (AC-2); repeat for US.
- `apply_side_table_update`: with an EU-routed `db`, the gate doc lands at `accounts/{id}/chat_idempotency_keys/{hash}`, a duplicate call returns `duplicate`, and nothing is written to the global collection (AC-6).
- Control-plane isolation: assert chat account-scoped paths never call `get_firestore_client()` (AC-7).
- Foundation-reuse guard: assert no local `class Region` / `def resolve_account_region` is defined in `chat/` (AC-8).

### Operator-verified (not gated in CI)
- In a dev EU cell, an EU account's session artifact is provably written to `ken-e-dev-files-eu` and its index row to the EU Firestore; the idempotency gate appears only in the EU DB (program spec §6.1 end-to-end EU-residency verification, the chat slice).

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| A stray `get_firestore_client()` / hardcoded `…-files-us` left in a chat call site silently keeps an EU account US-resident | AC-7 grep gate + unit assertion on the three call sites; the bucket map is the only producer of bucket strings (AC-1). |
| Redis client cache leaks across regions (one client serving both instances) | One client per `Region`, keyed off `CellConfig` (mirrors DM-PRD-09's per-region Firestore client cache); region-prefixed keys are a second layer so even a misrouted client cannot serve cross-region values. |
| Region resolution adds latency to the hot session-creation path | Resolve once per request (directory fast-path in `resolve_account_region`, already request-cacheable per DM-PRD-09 §4.4); no per-artifact / per-cache re-resolve. |
| User-scoped cache keys (`chat:user_sessions:*`, `chat:session:*`) for a user with accounts in both cells | §4.2: route by the user's resolved account region at the call site; full cross-cell-user handling depends on program spec §8 Q5 (can one org span cells?) — does not block the launch blocker (R-07 is account-scoped artifacts). |
| Green-field assumption wrong — pre-launch EU chat artifacts already in the US bucket | Re-confirm Q7 at kickoff; if false, those rows are handled by the supervised migration (DR-PRD-10), not here. |

### Open questions (carry from program spec §8)
- **Q (Redis topology):** one Memorystore instance per region vs. one instance with region-prefixed keys? This PRD ships **both** the per-region client and the prefix so either deployment is correct; confirm the infra choice (separate instance is the residency-correct answer — §3.2 of the spec lists Redis as a per-cell layer).
- **Q6 — EU region:** confirm `europe-west1` for the EU artifact bucket + Memorystore, matching the existing GCS pattern.
- **Q7 — existing data:** confirmed green-field (new EU sign-ups only). Re-confirm at kickoff.
- **R-16 boundary:** confirm with AH-PRD-11 that the session-state copy of org-context / GA-creds is theirs and the cache copy is ours — so neither slice double-owns nor drops the credential.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 decisions, §3.2 per-cell layer table (Redis, GCS rows), §3.4 reference pattern, §4 per-store posture (chat-artifact + Redis), §5 gap register (R-07 / R-11 / R-16 / R-17), §7 PRD breakdown (DR-PRD-05 row).
- Keystone foundation: [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region`, `CELLS`, `resolve_account_region`, `get_firestore_for_account`.
- Sibling chat PRD (the foundation this builds on): [`./CH-PRD-05-todo-lists-and-artifacts.md`](./CH-PRD-05-todo-lists-and-artifacts.md) — owns `register_artifact`, `list_artifacts`, the idempotency path.
- Sibling agentic-harness slice (owns R-16, session plane): [`../../agentic-harness/projects/AH-PRD-11-agent-reasoning-inference-residency.md`](../../agentic-harness/projects/AH-PRD-11-agent-reasoning-inference-residency.md).
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing).
- Refactor targets: `api/src/kene_api/chat/artifacts.py:184-189,217-224,244,427`; `api/src/kene_api/chat/side_table_handlers.py:29,77`; `api/src/kene_api/routers/chat.py:543-697,2173,2319,3176`; `api/src/kene_api/cache.py:211-228`; `api/src/kene_api/redis_client.py:63-194`.
- Component README: [`../README.md`](../README.md) §7.5 (artifact-save wrapper contract), §7.10 (Firestore layout — Shape B).
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-2, D-3, D-5; T-1, T-3, T-4, T-6; G-1.
