# IN-PRD-08 — Integrations Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Integrations
**Initiative:** Data Residency (US + EU)
**Blocked by:** [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) (regional-cell foundation — `Region`/`CELLS` registry, `resolve_account_region`, `get_firestore_for_account`), [IN-PRD-01](./IN-PRD-01-core-model-encryption.md) (`KMSEncryptionService` + Shape B token layout)
**Blocks:** —
**Estimated effort:** 2–3 days backend

> **Program context.** This is the Integrations slice of the data-residency program (logical `DR-PRD-03` in [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §7). The program is *not* a new component — each slice is homed in the component that owns the affected code and reuses the keystone foundation's routing helpers rather than reinventing per-component. Read the program spec's §1–§4 (esp. §2 locked decisions, §3.2 KMS row, §3.4 reference pattern, §4 KMS posture) and §5 (R-05) before this PRD. This project closes **R-05** — a launch blocker.

---

## 1. Context

Integrations is KEN-E's third-party credential substrate (OAuth flow per platform, encrypted token store, refresh lifecycle, sharing, re-auth). Today **every account's OAuth tokens are encrypted with a single US Cloud KMS key**, regardless of the account's `data_region`. The KMS branch of `EncryptionService` pins the key to `us-central1` with no account routing (`api/src/kene_api/services/encryption_service.py:49-52`):

```python
self.location_id = os.getenv("KMS_LOCATION_ID", "us-central1")
self.key_ring_id  = os.getenv("KMS_KEY_RING_ID", "integration-keys")
self.key_id       = os.getenv("KMS_KEY_ID", "integration-encryption-key")
```

`IntegrationCredentialsService` (`encryption_service.py:136-230`) constructs one `EncryptionService()` per instance and stores ciphertext in the **global** `integration_credentials` collection keyed `{account_id}_{integration_type}` (`encryption_service.py:143,169`). The OAuth CSRF state store is likewise a global collection `oauth_states` (`api/src/kene_api/services/oauth_state_service.py:14,27`). Both are acquired through the region-blind singleton Firestore client (`api/src/kene_api/dependencies.py:20-37,40-56`).

The net effect (**R-05**, 🔴 Critical, launch blocker — [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §5): **an EU customer's credentials are encrypted by a US-region KMS key and stored in the US Firestore cell.** That is a residency violation for the most sensitive class of account data.

This PRD extends the IN-PRD-01 encryption substrate to **per-region KMS keyrings selected by `data_region`**, and region-routes the `integration_credentials` / `oauth_states` stores through the DM-PRD-09 resolver — copying the canonical `storage_service.py:_get_bucket_config(data_region)` shape (`api/src/kene_api/services/storage_service.py:31-72`), exactly as DM-PRD-09's GCS reference prescribes.

**Green-field — no re-wrap of existing tokens.** Per program open question Q7 (confirmed green-field), there are no EU accounts holding credentials today; all existing tokens are US-only and stay US-encrypted. New EU accounts start fresh against the EU keyring. There is **no migration / re-encryption sweep** in this PRD. KMS key-*rotation* (re-wrap after a key version bumps) is owned by [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md)'s rotation runbook — this PRD adds a second keyring but does not change the rotation story; the per-region keyring must simply be addressable by IN-PRD-06's future sweeper.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (D1 residency boundary = the account; D2 US + EU at launch), §3.2 (KMS keyring row: US `us-central1` / EU `europe-west1`), §3.4 (reference pattern), §4 (KMS posture: per-region keyrings, select by `data_region`).

## 2. Scope

### In scope

- **Region-keyed KMS config** — a `data_region → (kms_location, key_ring_id, key_id)` resolver on the encryption service, mirroring `storage_service.py:_get_bucket_config`. US → `us-central1` / EU → `europe-west1`, with the existing US values as the default (back-compat). One config map per environment (dev / staging / prod), so the existing `KMS_*` env vars become the **US-cell** defaults rather than the only key.
- **`EncryptionService(data_region)`** — the service selects the region-appropriate Cloud KMS key at encrypt/decrypt time. The `data_region` is resolved from the account via the foundation's `resolve_account_region(account_id)` (DM-PRD-09, `shared/residency/routing.py`) — **not** redefined here. Local-dev Fernet path (`USE_LOCAL_ENCRYPTION`, `encryption_service.py:24,32-43`) is unchanged (no regional KMS in local dev).
- **Region-route the credential store** — `IntegrationCredentialsService` acquires its Firestore client via `get_firestore_for_account(account_id)` (DM-PRD-09) instead of the region-blind singleton, so EU credential ciphertext lands in the EU Firestore cell. The `{account_id}_{integration_type}` doc-id convention is preserved.
- **Region-route the OAuth state store** — `OAuthStateService` acquires its Firestore client via `get_firestore_for_account(account_id)` so `oauth_states` records (which carry `account_id`, `api/src/kene_api/services/oauth_state_service.py:32-33`) live in the account's home cell. State records hold no regulated content but are written/read mid-flow against the account, so they route with it for cell consistency.
- **Thread `data_region` through the call sites** — the routers/services that construct these services (`api/src/kene_api/routers/oauth_integrations.py:285,391,486,522,793,849`; `api/src/kene_api/routers/integrations.py:109,146,207,257,308`; `api/src/kene_api/services/ga_credential_helper.py:30`; `api/src/kene_api/services/account_tools_service.py:44,182-196`) resolve region from `account_id` (already in scope at every site) and pass the region-routed client + region-keyed encryption service.
- **Terraform: EU KMS keyring** — add the `europe-west1` keyring + `token-encryption` key + `cryptoKeyEncrypterDecrypter` IAM binding for the EU-cell API service account, mirroring the US keyring IN-PRD-01 provisions. Green-field; no key import.
- **Convention adherence** — uses, and does not extend, the **Regional Cell routing convention** documented at [`../README.md`](../README.md) §7.8 (DM-PRD-09). KMS becomes the second store (after Firestore) wired through it.

### Out of scope

- **Defining the region resolver, `Region`/`CELLS` registry, or `get_firestore_for_account`** — owned by DM-PRD-09; this PRD only *consumes* them.
- **Migrating / re-encrypting existing tokens into the EU cell** — green-field per Q7; no existing EU credentials exist. A supervised account region-migration (which would re-wrap) is DM-PRD-10.
- **KMS key-rotation sweeper / re-wrap-after-rotation** — IN-PRD-06's rotation runbook. This PRD only ensures the per-region key is addressable; it does not rotate or re-wrap.
- **Regionalizing any other store** — Neo4j (KG-PRD-07 / R-06), model + Agent Engine (AH-PRD-11), Redis / artifacts (CH-PRD-07), traces (AH-PRD-12). Separate slices.
- **The IN-PRD-01 → service migration** — IN-PRD-01 replaces this legacy `EncryptionService` / `IntegrationCredentialsService` with `KMSEncryptionService` + Shape B token subcollections. This PRD regionalizes whichever encryption substrate is current at implementation time (the legacy service today, the IN-PRD-01 `KMSEncryptionService` if it has landed first) — the **per-region key-selection contract is identical** either way (§4.1). It does **not** re-do the IN-PRD-01 Shape B token move.
- **EU sign-up gating feature flag** — Feature-Flags concern (program §6.1), wired when the EU cell is verified end-to-end.

## 3. Dependencies

| Dependency | What it provides | Reference |
|---|---|---|
| **[DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md)** | `Region` enum + `CELLS` config map + `normalize_region()`; `resolve_account_region(account_id) -> Region`; `get_firestore_for_account(account_id) -> firestore.Client` (per-region-cached). **Reused verbatim — not redefined.** | `shared/residency/regions.py`, `shared/residency/routing.py` |
| **[IN-PRD-01](./IN-PRD-01-core-model-encryption.md)** | The encryption substrate this extends: `KMSEncryptionService` (env-keyed Cloud KMS), Shape B token layout, the US `integrations` keyring + IAM. This PRD adds the EU keyring + per-region key selection on top. | IN-PRD-01 §4 (KMS scheme), §5.4 (`KMSEncryptionService` contract) |
| Reference pattern | `storage_service.py:_get_bucket_config(data_region)` — the `data_region → (resource, location)` map shape every regionalization copies. | `api/src/kene_api/services/storage_service.py:31-72` |
| Cloud KMS (Terraform) | Existing US `integration-keys` keyring (`us-central1`); this PRD adds the `europe-west1` keyring + key + IAM for the EU-cell SA. | `deployment/terraform/` |
| Current encryption substrate | `EncryptionService` + `IntegrationCredentialsService` (legacy, today) — the regionalization target until IN-PRD-01's `KMSEncryptionService` supersedes it. | `api/src/kene_api/services/encryption_service.py:27-230` |

**External / open:** confirm `europe-west1` for the EU KMS keyring (program Q6 — same region as the existing EU GCS bucket). EU Agent Engine GA (Q1) does **not** block this PRD.

## 4. Data contract

### 4.1 Region-keyed KMS config (single source of truth, this component)

```python
# api/src/kene_api/services/encryption_service.py (extends the existing service)
# Mirrors storage_service._get_bucket_config: a data_region -> KMS-target map,
# US default, normalize/validate step. Region is resolved via the DM-PRD-09
# foundation, NOT redefined here.

def _get_kms_config(data_region: str) -> tuple[str, str, str]:
    """Return (kms_location, key_ring_id, key_id) for the account's home cell.
    US default; EU -> europe-west1 keyring. Per-environment values."""
    region = normalize_region(data_region)        # from residency.regions (DM-PRD-09)
    ...
```

| `data_region` | KMS location | Key ring | Key |
|---|---|---|---|
| `US` (default) | `us-central1` | `integration-keys` (existing) | `integration-encryption-key` |
| `EU` | `europe-west1` | `integration-keys` (EU project/keyring) | `integration-encryption-key` |

- The existing `KMS_LOCATION_ID` / `KMS_KEY_RING_ID` / `KMS_KEY_ID` env vars (`encryption_service.py:50-52`) become the **US-cell defaults**; the EU row resolves from the EU cell's `CellConfig` (DM-PRD-09 `CELLS`) / the EU keyring Terraform provisions.
- Encryption/decryption otherwise unchanged: ciphertext is base64'd KMS output; KMS resolves the key *version* from the ciphertext on decrypt, so existing US ciphertext keeps decrypting against the US key.

### 4.2 Store routing (no schema change)

| Store | Collection | Today | After this PRD |
|---|---|---|---|
| Credentials | `integration_credentials/{account_id}_{integration_type}` (`encryption_service.py:143,169`) | global / US singleton client | client = `get_firestore_for_account(account_id)` → account's home cell |
| OAuth state | `oauth_states/{state_token}` (`oauth_state_service.py:14,27`) | global / US singleton client | client = `get_firestore_for_account(account_id)` → account's home cell |

No document shape changes. Doc-id conventions, ciphertext fields, and TTL semantics are preserved — only the **target cell** and the **encryption key** change, both derived from `data_region`.

### 4.3 Invariant

For any account, `resolve_account_region(account_id)` determines **both** the Firestore cell its credentials/state land in **and** the KMS keyring that encrypts its tokens. The two can never diverge because both derive from the same `data_region`, which DM-PRD-09 makes immutable after account creation (R-08). An EU account's credentials are therefore EU-stored and EU-encrypted; a US account's are US-stored and US-encrypted.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/services/encryption_service.py` — add `_get_kms_config(data_region)` (mirror `storage_service._get_bucket_config`); `EncryptionService.__init__(self, data_region: str = "US")` selects the region keyring; preserve the `USE_LOCAL_ENCRYPTION` Fernet path unchanged (`:24,32-43`). |
| Modify | `api/src/kene_api/services/encryption_service.py` — `IntegrationCredentialsService.__init__` resolves `data_region` from `account_id` via `resolve_account_region` (DM-PRD-09), acquires its client via `get_firestore_for_account(account_id)`, and builds `EncryptionService(data_region)`. (`:136-143`.) |
| Modify | `api/src/kene_api/services/oauth_state_service.py` — acquire the Firestore client via `get_firestore_for_account(account_id)` keyed on the flow's `account_id` (`:20-27,32-33`). |
| Modify | `api/src/kene_api/routers/oauth_integrations.py` — at each `IntegrationCredentialsService(db)` site (`:285,391,486,522,793,849`) pass `account_id` through so the service self-routes; drop the region-blind `db`. |
| Modify | `api/src/kene_api/routers/integrations.py` — same at `:109,146,207,257,308`; the two raw `db.collection("integration_credentials")…` reads/writes (`:157,225`) route through `get_firestore_for_account(account_id)`. |
| Modify | `api/src/kene_api/services/ga_credential_helper.py` — thread `account_id` into `IntegrationCredentialsService` construction (`:30`). |
| Modify | `api/src/kene_api/services/account_tools_service.py` — the `integration_credentials` existence read (`:44,182-196`) routes via `get_firestore_for_account(account_id)`. |
| Modify | `deployment/terraform/` — EU `europe-west1` KMS keyring + `token-encryption` key + `cryptoKeyEncrypterDecrypter` IAM binding for the EU-cell API SA; `lifecycle { prevent_destroy = true }` on the key (mirror IN-PRD-01). |
| Create | `api/tests/unit/test_encryption_region_routing.py` — `_get_kms_config` table + key-selection. |
| Create | `api/tests/integration/test_integration_credentials_residency.py` — EU credentials land in the EU cell + EU keyring; US unaffected. |

**Refactor note.** Every call site already has `account_id` in scope (it is in the path for every integrations endpoint), so threading it is mechanical and adds no new request input. If IN-PRD-01's `KMSEncryptionService` has landed first, apply the identical `_get_kms_config` selection to *its* constructor instead — the contract (§4.1) is the same.

## 6. API contract

This slice publishes **no new public HTTP surface**. It changes *where* existing integrations endpoints' data is encrypted and stored, transparently to callers. The internal contracts:

| Contract | Consumed by | Source of truth |
|---|---|---|
| `EncryptionService(data_region)` selects the region-appropriate KMS key (US default, EU → `europe-west1`) | `IntegrationCredentialsService`; any future direct caller | `api/src/kene_api/services/encryption_service.py` |
| `IntegrationCredentialsService` / `OAuthStateService` route their Firestore client via `get_firestore_for_account(account_id)` | All integrations routers/services | `encryption_service.py`, `oauth_state_service.py` |
| `_get_kms_config(data_region) -> (location, key_ring, key)` (the `get_<resource>(data_region)` pattern, KMS edition) | This component | `api/src/kene_api/services/encryption_service.py` |
| `resolve_account_region` + `get_firestore_for_account` (reused, not defined) | — | `shared/residency/routing.py` (DM-PRD-09) |

Existing endpoints (`POST /api/v1/integrations/{account_id}/...`, `GET .../status`, the OAuth initiate/callback in `oauth_integrations.py`) keep their request/response shapes; an EU account's credentials simply become EU-resident and EU-encrypted.

## 7. Acceptance criteria

1. `_get_kms_config("EU")` returns the `europe-west1` keyring target; `_get_kms_config("US")` and `_get_kms_config(None)`/unknown return the existing `us-central1` defaults (back-compat). Invalid non-empty values are normalized via the DM-PRD-09 `normalize_region` (rejecting e.g. `"APAC"`), not silently defaulted.
2. `EncryptionService(data_region="EU")` encrypts/decrypts against the EU key; `EncryptionService("US")` against the US key; the `USE_LOCAL_ENCRYPTION` Fernet dev path is unchanged regardless of region.
3. `IntegrationCredentialsService` for an EU account writes `integration_credentials/{id}` into the **EU** Firestore cell (via `get_firestore_for_account`) with ciphertext produced by the **EU** KMS key; for a US account, into the US cell with the US key.
4. `OAuthStateService` for an EU account writes/reads `oauth_states/{state_token}` in the EU cell.
5. A US account's credential read/write path is byte-for-byte unchanged (same cell, same key) — existing US ciphertext still round-trips (regression).
6. Every integrations call site that constructed `IntegrationCredentialsService(db)` with the region-blind singleton now self-routes by `account_id`; no account-scoped credential read/write uses the control-plane/global singleton client (asserted by unit guard + grep gate).
7. Terraform applies cleanly: the EU `europe-west1` `integration-keys` keyring + `token-encryption` key exist with the EU-cell SA bound `cryptoKeyEncrypterDecrypter` (operator-verified in dev; not gated in CI).
8. No re-wrap / migration job exists or runs (green-field assertion — confirms scope guardrail).
9. `make lint` passes. `pytest api/tests/unit/test_encryption_region_routing.py api/tests/integration/test_integration_credentials_residency.py` passes.
10. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_encryption_region_routing.py`)

- `_get_kms_config` table-driven over `US` / `EU` / `None` / unknown → expected `(location, key_ring, key)`; unknown delegates to `normalize_region` (AC-1).
- `EncryptionService(data_region)` builds the `crypto_key_path` for the right region (mock KMS client; assert the path args per region) (AC-2).
- Fernet dev path unaffected when `USE_LOCAL_ENCRYPTION=true` regardless of `data_region` (AC-2).
- Region-blind-isolation guard: assert no integrations service reads/writes `integration_credentials` / `oauth_states` through the DM-PRD-09 control-plane singleton (AC-6).

### Integration (`test_integration_credentials_residency.py`, Firestore emulator + mocked KMS + mocked region resolver)

- EU account: `store_credentials` → doc lands in the EU-cell client's `integration_credentials`; ciphertext tagged to the EU key; `get_credentials` round-trips (AC-3).
- US account: same flow → US cell + US key; pre-existing US ciphertext (seeded) still decrypts (AC-5).
- OAuth state: EU account `create_state` → record in EU cell; `validate_state` reads it back (AC-4).
- Assert no migration/sweep code path is invoked (AC-8).

### Manual verification (dev)

- Apply EU Terraform; `gcloud kms keys list --location=europe-west1 --keyring=integration-keys --project=<eu-dev-project>` shows the `token-encryption` key (AC-7).
- Connect a stub integration on a US dev account and an EU dev account; inspect Firestore consoles per cell to confirm ciphertext placement.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| A straggler call site constructs `EncryptionService()` / `IntegrationCredentialsService(db)` region-blind and silently stays US-only for an EU account | The call-site list (§5) is exhaustive per grep; AC-6 unit guard + a grep review-checklist item for direct construction. Same straggler-audit posture as DM-PRD-09. |
| Decrypt fails after a future key rotation if the per-region key version is disabled | KMS resolves the version from ciphertext; this PRD only adds a keyring. Re-wrap-after-rotation is IN-PRD-06's runbook — the EU keyring is provisioned so IN-PRD-06's sweeper can target it. |
| IN-PRD-01 lands first and replaces the legacy service | The per-region key-selection contract (§4.1) is identical; apply it to `KMSEncryptionService.__init__` instead. No re-do of IN-PRD-01's Shape B token move. |
| EU keyring region mismatch with EU Firestore/GCS | All EU stores standardize on `europe-west1` (Q6); EU KMS keyring uses the same, matching the existing EU GCS bucket. |

### Open questions (carry from program §8)

- **Q6 — EU region:** confirm `europe-west1` for the EU KMS keyring (assumed: same region as the existing EU GCS bucket, `storage_service.py:51`). Member-state sovereignty could force a specific region.
- **Q7 — existing data:** confirmed green-field (no EU credentials in the US cell today). Re-confirm at kickoff — if any EU account already holds tokens, a one-time re-wrap moves to DM-PRD-10, **not** this PRD.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 (D1/D2), §3.2 (KMS keyring row), §3.4 (reference pattern), §4 (KMS posture), §5 (R-05), §7 (DR-PRD-03 → IN-PRD-08).
- Keystone foundation: [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region`/`CELLS`, `resolve_account_region`, `get_firestore_for_account`, the Regional Cell routing convention ([`../README.md`](../README.md) §7.8).
- Encryption substrate this extends: [IN-PRD-01](./IN-PRD-01-core-model-encryption.md) §4, §5.4.
- Rotation owner (not this PRD): [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md).
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing).
- Regionalization targets: `api/src/kene_api/services/encryption_service.py:49-52,136-230`; `api/src/kene_api/services/oauth_state_service.py:14,20-33`; `api/src/kene_api/routers/oauth_integrations.py`, `api/src/kene_api/routers/integrations.py`, `api/src/kene_api/services/ga_credential_helper.py`, `api/src/kene_api/services/account_tools_service.py`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-2, D-5; T-1, T-3, T-4, T-6.
