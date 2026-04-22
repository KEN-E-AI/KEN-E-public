# PR-PRD-08 — Campaign Management

**Status:** Blocked — resumes once PR-PRD-01 and DM-PRD-05 ship
**Owner team:** Backend
**Blocked by:** PR-PRD-01 (existing `campaign` string field on `ProjectPlan`); DM-PRD-05 (ensures `recursive_delete` covers the new `campaigns` subcollection)
**Blocks:** PR-PRD-07 (activities reference `Campaign` by id and rely on the generic-fallback-per-objective)
**Estimated effort:** 1–2 days

---

## 1. Context

The Figma-designed Calendar and Projects pages treat **Campaigns** as a first-class entity with a `name` and an **objective** drawn from a four-value enum (`Problem Awareness`, `Brand Awareness`, `Consideration`, `Conversion`). Activities and plans reference a campaign by id; an activity's objective is *derived* from its campaign rather than stored directly.

In PR-PRD-01 and A-PRD-1, `ProjectPlan.campaign` is currently a free-form string — there is no `Campaign` entity, no objective enum, no way to list or filter by objective, no lifecycle, and no concept of a "generic fallback campaign per objective" that an activity can auto-assign to when the user does not pick a specific campaign.

This PRD adds the entity, the CRUD endpoints, on-the-fly creation semantics (the Calendar's activity-add drawer lets a user type a new campaign name and have it created inline), and seeds four generic fallback campaigns at account creation so the objective can always be resolved for any activity.

## 2. Scope

### In scope
- `Campaign` Pydantic model (`campaign_id`, `account_id`, `name`, `objective`, timestamps, actor)
- `CampaignObjective` enum (`Problem Awareness | Brand Awareness | Consideration | Conversion`)
- CRUD router with list / get / create / update / soft-delete endpoints
- Uniqueness rule: (`account_id`, `name`) is unique within an account
- Seeding: four generic campaigns per account (one per objective) created at account creation via an account-bootstrap hook
- Helper: `get_generic_campaign_id(account_id, objective) -> str` for callers that need the fallback id
- Migration of `ProjectPlan.campaign: str | None` → `ProjectPlan.campaign_id: str | None` (rename + FK), with a backfill script
- Unit tests for the objective enum + the uniqueness validator; integration tests for the CRUD endpoints and the bootstrap seeding

### Out of scope
- Activity-to-campaign resolution and derived-objective logic (lives in PR-PRD-07 on the activity read path)
- Frontend changes (PR-PRD-03)
- Cross-campaign analytics or reporting (out of scope for this release)
- Linking a campaign to a Strategy or a Goal (considered; deferred to a follow-up PRD once the data model stabilizes)

## 3. Dependencies

- **PR-PRD-01:** renames `ProjectPlan.campaign` → `ProjectPlan.campaign_id`; the DAG validator and versioning logic are unaffected.
- **PR-PRD-07 (Calendar Activities):** consumer — calls `get_generic_campaign_id(...)` when `campaign_id is None` on activity submit. Landing order: PR-PRD-08 ships first; PR-PRD-07 depends on it.
- **DM-PRD-05:** `recursive_delete` already covers any subcollection under `accounts/{account_id}/...`; no new delete path required.
- **DM-PRD-00:** adds the one `campaigns` collection-scope composite index (see §5).
- **Account creation path:** the bootstrap hook that seeds the four generic campaigns needs to run in the same transaction as account creation. Identify the existing account-creation endpoint/service at implementation start (likely `api/src/kene_api/routers/accounts.py`) and add the seed step there.
- **Existing files to study:** `api/src/kene_api/routers/strategy.py`, `api/src/kene_api/routers/project_plans.py` (pattern to mirror), `api/src/kene_api/routers/accounts.py` (account creation).

## 4. Data contract

### `Campaign`

```
campaign_id: str                           # UUID, or a stable slug for generics ("cc-gen-pa" etc.)
account_id: str
name: str                                  # unique within (account_id, is_active=true)
objective: Literal[
    "Problem Awareness", "Brand Awareness",
    "Consideration", "Conversion"
]
is_generic: bool = False                   # true for the four seeded fallback campaigns
is_active: bool = True                     # soft-delete flag
created_by: str
created_at: datetime
updated_at: datetime
```

### `CampaignObjective` enum

```
Literal[
    "Problem Awareness",
    "Brand Awareness",
    "Consideration",
    "Conversion",
]
```

### Generic campaigns (seeded per account)

At account creation, four `Campaign` docs are seeded with `is_generic=true`:

```
campaign_id        name                           objective
─────────────────────────────────────────────────────────────────────
cc-gen-pa          General Problem Awareness      Problem Awareness
cc-gen-ba          General Brand Awareness        Brand Awareness
cc-gen-c           General Consideration          Consideration
cc-gen-cv          General Conversion             Conversion
```

The generic campaigns are returned by the list endpoint like any other campaign, but the Calendar UI filters them out of the campaign picker unless the caller opts in (see PR-PRD-07 frontend note). They cannot be deleted; `DELETE` on a generic returns `409 Conflict`.

### Validators

- `name` non-empty, trimmed, ≤ 200 chars
- `(account_id, name)` unique among active campaigns (case-insensitive compare); duplicate create → `409`
- `is_generic=true` forbids delete; forbids renaming via `PATCH` (updating `name` on a generic returns `403`)

### `ProjectPlan` — rename

```
# Before (PR-PRD-01 §4)
campaign: str | None

# After (this PRD)
campaign_id: str | None                    # now a FK to Campaign.campaign_id in the same account
```

The rename is backwards-compatible at the API level via a request-shape alias for one release cycle: the router accepts both `campaign` (legacy) and `campaign_id` (new). Responses return only `campaign_id`. The alias is removed in the next release.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/campaign_models.py` |
| Create | `api/src/kene_api/routers/campaigns.py` |
| Modify | `api/src/kene_api/models/project_plan_models.py` — rename `campaign` → `campaign_id` with alias |
| Modify | `api/src/kene_api/routers/accounts.py` — seed the four generic campaigns in the account-creation transaction |
| Modify | `api/src/kene_api/main.py` — register router under `/api/v1/campaigns` |
| Create | `api/src/kene_api/services/campaign_service.py` — `get_generic_campaign_id`, uniqueness check helper |
| Create | `api/scripts/backfill_campaign_field_rename.py` — one-shot backfill for existing `ProjectPlan` docs |
| Create | `api/tests/unit/test_campaign_models.py` |
| Create | `api/tests/integration/test_campaigns_router.py` |
| Create | `api/tests/integration/test_account_bootstrap_seeds_generic_campaigns.py` |
| Modify | `deployment/terraform/firestore_indexes_project_tasks.tf` — add `campaigns` composite index |

### Firestore layout

```
accounts/{account_id}/campaigns/{campaign_id}            # NEW — user + generic campaigns
accounts/{account_id}/project_plan_audit/{audit_id}      # existing; new entry types for campaign mutations
```

### Composite index

```
collection: accounts/*/campaigns   (queryScope: COLLECTION)
  fields: [is_active ASC, objective ASC, updated_at DESC]
```

### Backfill plan

Backfill script walks every `accounts/{account_id}/project_plans/{plan_id}`:

1. If `campaign` is set and matches an existing campaign name → `campaign_id = <that id>`, drop `campaign`.
2. If `campaign` is set but no matching Campaign doc exists → create a Campaign with that name, `objective = "Brand Awareness"` (default), `is_generic=false`, then set `campaign_id` on the plan.
3. If `campaign is None` → leave `campaign_id=None`. Activity objective at read time falls back to the per-objective generic via `get_generic_campaign_id`.
4. Emit an audit entry for each plan mutated.

The script is idempotent (re-running it is a no-op on already-migrated plans).

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/campaigns/{account_id}` | List campaigns. Query params: `objective[]`, `is_active` (default true), `include_generic` (default true), `cursor`, `page_size` |
| `GET` | `/api/v1/campaigns/{account_id}/{campaign_id}` | Fetch one |
| `POST` | `/api/v1/campaigns/{account_id}` | Create. Body: `{name, objective}`. Returns `201` with the new `Campaign`. `409` on duplicate name within the account. |
| `PATCH` | `/api/v1/campaigns/{account_id}/{campaign_id}` | Update (name, objective). Renaming a generic → `403`. |
| `DELETE` | `/api/v1/campaigns/{account_id}/{campaign_id}` | Soft-delete (`is_active=false`). Generic → `409`. |
| `GET` | `/api/v1/campaigns/{account_id}/generic/{objective}` | Convenience: returns the generic campaign for the given objective. Used by server-side callers that would otherwise need the mapping table. |

All endpoints use the existing account-scoped access-control dependency. Auth errors → `403`.

## 7. Acceptance criteria

1. `POST /api/v1/accounts` (or equivalent account-creation path) seeds four `Campaign` docs with `is_generic=true` and the canonical ids `cc-gen-pa`, `cc-gen-ba`, `cc-gen-c`, `cc-gen-cv`. Seeding happens in the same transaction as account creation — failure rolls back both.
2. `GET /api/v1/campaigns/{account_id}` on a new account returns exactly four campaigns, all generic.
3. `POST /api/v1/campaigns/{account_id}` with `{name: "Spring Promo 2026", objective: "Conversion"}` returns `201` with a new `campaign_id`. A second `POST` with the same name returns `409`.
4. `PATCH` on a generic campaign's `name` returns `403`. `PATCH` on a generic's `objective` also returns `403`.
5. `DELETE` on a generic returns `409`. `DELETE` on a user campaign soft-deletes (subsequent `GET` with `is_active=true` filter does not return it).
6. `GET /api/v1/campaigns/{account_id}/generic/Conversion` returns the campaign with `campaign_id="cc-gen-cv"` and `objective="Conversion"`.
7. `get_generic_campaign_id(account_id, "Brand Awareness")` returns `"cc-gen-ba"`.
8. Posting a `ProjectPlan` with legacy body `{campaign: "Spring Promo 2026"}` is accepted (alias honored), persists as `campaign_id="<that id>"`, and responds with `campaign_id` only.
9. Backfill script on a seeded dataset of 20 plans (10 with `campaign`, 10 without) completes, creates missing Campaign docs, sets `campaign_id` on all 10, leaves the 10 nulls untouched, writes 10 audit entries, and is idempotent on re-run.
10. Cross-account access returns `403` on every endpoint.
11. Composite index exists in `firestore_indexes_project_tasks.tf`; emulator runs list queries without scan warnings.
12. All unit and integration tests pass; `make lint` clean.

## 8. Test plan

**Unit tests** (`test_campaign_models.py`):
- Each of the four objective values accepted; fifth value rejected
- `name` empty / whitespace / > 200 chars rejected
- `is_generic=True` + `DELETE` intent rejected at the service layer
- Uniqueness helper: case-insensitive compare on `name`

**Integration tests** (`test_campaigns_router.py`):
- Full CRUD lifecycle for a user campaign
- Duplicate-name create → `409` with clear error
- Generic-campaign rename → `403`; generic-campaign delete → `409`
- Soft-delete: `DELETE` then `GET` with `is_active=true` (default) returns 4 generics only
- Cross-account → `403` on every endpoint
- `generic/{objective}` endpoint for each of the four objectives

**Integration tests** (`test_account_bootstrap_seeds_generic_campaigns.py`):
- Create account → 4 generics seeded with canonical ids
- Account-creation failure mid-transaction → no partial seed (verify via list on rolled-back account)
- Re-running the seed step on an existing account is a no-op (idempotent)

**Backfill script** (`backfill_campaign_field_rename.py`):
- Seed 20 plans (mixed `campaign` / null); run script; verify all 10 non-null plans have `campaign_id` set; 10 new Campaign docs exist; re-run is idempotent

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Two accounts with the same canonical generic ids → global collisions in queries | Ids are only unique within `accounts/{account_id}/campaigns/`; collection-group queries that need to union across accounts must filter by `account_id`. Documented. |
| A user deletes-then-recreates a campaign with the same name | Allowed: soft-delete flips `is_active=false`; the uniqueness check considers only active rows. |
| Legacy `campaign` field still present on old `ProjectPlan` docs after the alias is removed | Backfill script runs before the alias is removed; DM-PRD migration hygiene covers the long tail. |
| Generic ids collide with a user who manually names a campaign `"cc-gen-pa"` | User names never populate `campaign_id`; they populate `name`. Ids are server-generated (UUID for user campaigns). No collision path. |
| Should Campaign tie to Strategy or Goal? | Deferred. This PRD ships a minimal Campaign entity; Strategy/Goal linkage is a follow-up PRD once the data model settles. |
| Default objective in backfill when the legacy `campaign` string had no objective context | Default to `"Brand Awareness"`. Flag in backfill logs for manual review. |

## 10. Reference

- Foundation: [PR-PRD-01](./PR-PRD-01-data-model-and-api.md) §4 (`campaign` field rename)
- Consumer: [PR-PRD-07](./PR-PRD-07-calendar-activities.md) §3 (generic-fallback consumption), §4 (activity `campaign_id` field)
- Frontend context: `docs/figma-export/src/app/data/calendarData.ts` (`CalendarCampaign`, `FunnelObjective`, `getGenericCampaignId`), `docs/figma-export/src/app/pages/CalendarPage.tsx` (on-the-fly campaign creation from the activity drawer)
- Pattern files: `api/src/kene_api/routers/project_plans.py`, `api/src/kene_api/models/project_plan_models.py`
- CLAUDE.md rules in scope: C-5; D-1, D-2, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-7, T-8
