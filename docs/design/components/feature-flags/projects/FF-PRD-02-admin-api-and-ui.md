# FF-PRD-02 — Admin API + UI

**Status:** Blocked (on FF-PRD-01 and UI-PRD-01)
**Owner team:** Platform (backend + frontend)
**Blocked by:** FF-PRD-01, UI-PRD-01
**Parallel with:** FF-PRD-03
**Estimated effort:** 3–4 days

---

## 1. Context

Adds the management surface on top of FF-PRD-01's evaluation engine — the super-admin-only CRUD API and the `/admin/feature-flags` page. Without this PRD, engineers can only create flags by seeding Firestore directly; with it, any `@ken-e.ai` super-admin can create, target, kill, and audit flags through the UI. This is what makes the feature flag system *usable* as a daily tool rather than just a library.

Every mutation writes an audit entry so flag activity is traceable — a lightweight compliance posture that matters more than it costs.

See [`../README.md`](../README.md) §2.3 and §7.6 for the component-level API and security conventions.

## 2. Scope

### In scope
- `/api/v1/admin/feature-flags/*` super-admin CRUD (list, get, create, update, delete, audit)
- `feature_flag_audit/{audit_id}` writes on every mutation (action, actor email, diff, timestamp)
- TypeScript type surface mirroring FF-PRD-01's Pydantic models (`FeatureFlag`, `TargetingRules`, `FlagKey` branded type)
- `/admin/feature-flags` React page: list table, create/edit drawer, kill-switch toggle, audit log tab per flag
- React Query hooks for the admin endpoints (`useFeatureFlags`, `useFeatureFlag`, `useCreateFlag`, `useUpdateFlag`, `useDeleteFlag`, `useFlagAudit`)
- Admin-nav entry for super-admins only (visible in `Sidebar` when `isSuperAdmin === true`)
- Component tests for the admin UI
- Integration tests for the admin endpoints against the Firestore emulator

### Out of scope
- Non-super-admin access (org admins managing their own flags) — deferred to a future PRD
- Multi-variant flag types — deferred
- Scheduled rollouts (auto-ramp from 5% → 50% over N days) — deferred
- Import / export of flag configs — deferred
- The runtime `useFeatureFlag` hook and `FeatureFlagsProvider` — owned by FF-PRD-03

## 3. Dependencies

- **FF-PRD-01** — Pydantic models, `FeatureFlagService`, `feature_flags/*` collection, evaluation API (import; do not redefine)
- **UI-PRD-01** — `LayoutC`, re-skinned shadcn primitives (Table, Drawer, Button, Input, Switch, Badge, Tabs), `Sidebar`, `AccountSwitcher` context (for evaluating whether the current viewer is a super-admin)
- Existing `is_super_admin` check in `api/src/kene_api/auth/` — reused for route-level authorization
- Existing `useAuth()` hook — exposes `isSuperAdmin` to the `Sidebar` + admin page guards
- Existing TanStack Query provider at the app root

## 4. Data contract

### Typescript (`frontend/src/lib/featureFlags/types.ts` — shared with FF-PRD-03)

```ts
import type { Brand } from "@/lib/types";

export type FlagKey = Brand<string, "FlagKey">;

export type BucketingEntity = "account" | "organization" | "user";

export type TargetingRules = {
  user_emails: string[];
  email_domains: string[];
  organization_ids: string[];
  account_ids: string[];
  rollout_percentage: number;  // 0-100
};

export type FeatureFlag = {
  key: FlagKey;
  description: string;
  default_enabled: boolean;
  is_active: boolean;
  targeting_rules: TargetingRules;
  bucketing_entity: BucketingEntity;
  owner: string;
  expected_ga_release: string | null;
  created_at: string;  // ISO-8601
  updated_at: string;  // ISO-8601
};

export type FeatureFlagAuditEntry = {
  audit_id: string;
  flag_key: FlagKey;
  actor_email: string;
  action: "create" | "update" | "delete" | "toggle_active";
  diff: Record<string, { before: unknown; after: unknown }>;
  created_at: string;
};
```

### Request/response shapes (mirror `feature_flag_models.py`)

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/v1/admin/feature-flags` | — | `{ flags: FeatureFlag[] }` |
| `POST /api/v1/admin/feature-flags` | `FeatureFlag` (without `created_at` / `updated_at`) | `FeatureFlag` |
| `GET /api/v1/admin/feature-flags/{key}` | — | `FeatureFlag` |
| `PUT /api/v1/admin/feature-flags/{key}` | `FeatureFlag` (full replace; server fills timestamps) | `FeatureFlag` |
| `DELETE /api/v1/admin/feature-flags/{key}` | — | `204 No Content` |
| `GET /api/v1/admin/feature-flags/{key}/audit` | `?limit=50&cursor=<audit_id>` | `{ entries: FeatureFlagAuditEntry[], next_cursor: string \| null }` |

All endpoints 403 for non-super-admins.

## 5. Implementation outline

### Backend

| Action | File |
|--------|------|
| Create | `api/src/kene_api/routers/admin_feature_flags.py` — 6 endpoints + super-admin dependency |
| Create | `api/src/kene_api/services/feature_flag_audit.py` — `record_audit(flag_key, actor_email, action, diff)` |
| Modify | `api/src/kene_api/services/feature_flag_service.py` — add `create_flag`, `update_flag`, `delete_flag`, `list_flags`, `get_flag_audit` (CRUD moves through the service so the in-process cache in FF-PRD-01 invalidates the local entry on write) |
| Modify | `api/src/kene_api/main.py` — register the admin router under `/api/v1/admin/feature-flags` |
| Create | `api/tests/integration/test_admin_feature_flags_endpoints.py` |
| Create | `api/tests/unit/test_feature_flag_audit_diff.py` |

### Frontend

| Action | File |
|--------|------|
| Create | `frontend/src/lib/featureFlags/types.ts` — shared with FF-PRD-03 |
| Create | `frontend/src/lib/featureFlags/adminClient.ts` — typed axios wrappers |
| Create | `frontend/src/lib/featureFlags/hooks.ts` — React Query hooks (`useFeatureFlags`, `useCreateFlag`, etc.) |
| Create | `frontend/src/pages/admin/FeatureFlagsPage.tsx` — list + create drawer + edit drawer + audit tab |
| Create | `frontend/src/components/admin/featureFlags/FlagTable.tsx` |
| Create | `frontend/src/components/admin/featureFlags/FlagEditDrawer.tsx` |
| Create | `frontend/src/components/admin/featureFlags/TargetingRulesEditor.tsx` |
| Create | `frontend/src/components/admin/featureFlags/FlagAuditList.tsx` |
| Modify | `frontend/src/App.tsx` — register `/admin/feature-flags` route, guarded by `isSuperAdmin` |
| Modify | `frontend/src/components/layout/Sidebar.tsx` — admin nav section, visible only when `isSuperAdmin` |
| Create | colocated `*.test.tsx` for each new component |

### 5.1 Audit diff rules

`record_audit` computes a shallow diff between old and new flag documents and stores only the changed top-level keys (including nested `targeting_rules` as a single `diff` entry if any sub-field changed). Timestamps are excluded from the diff.

### 5.2 Sidebar integration

The admin nav entry lives in a new "Admin" section of `Sidebar`, rendered conditionally. No behavior for non-admins — the section is absent from the DOM, not just hidden.

### 5.3 UI details

- **List table** columns: `key`, `description` (truncated), `is_active` (toggle switch; one-click kill), `default_enabled` (badge), `rollout %`, `owner`, `updated_at`. Sort by `updated_at` descending by default.
- **Create / Edit drawer**: form fields for every `FeatureFlag` property. `bucketing_entity` dropdown has helper text: *"'account' is correct for most product flags. Choose 'user' only if the feature travels with the person across accounts (e.g., profile settings). 'organization' for org-wide capabilities."*
- **Targeting rules editor**: comma- or newline-separated inputs for each list plus a `0-100` slider for `rollout_percentage`.
- **Kill switch**: `is_active` toggle in the table row and in the drawer. Flipping it off requires no confirmation; flipping a currently-failing feature off quickly matters more than a confirmation prompt.
- **Audit tab**: chronological list inside the edit drawer, paginated via `next_cursor`.

## 6. API contract

See §4.

## 7. Acceptance criteria

1. All six endpoints exist under `/api/v1/admin/feature-flags` and return 403 for callers whose `is_super_admin` is false.
2. `POST` rejects keys that don't match `FLAG_KEY_REGEX` with 422; rejects creating an existing key with 409.
3. `PUT` on a non-existent key returns 404; successful `PUT` updates `updated_at` server-side.
4. Every successful `POST` / `PUT` / `DELETE` writes a `feature_flag_audit/{audit_id}` document whose `diff` contains only changed top-level fields (timestamps excluded) and whose `actor_email` matches the token.
5. `GET /{key}/audit` returns entries newest-first, paginates via `cursor`, and stops at `limit=50` per call.
6. Mutating a flag through the service invalidates the in-process cache for that `flag_key` on the *current* Cloud Run instance (verified in a unit test). Other instances pick up the change within the 60 s TTL.
7. `/admin/feature-flags` route is reachable only when `isSuperAdmin === true`. Non-admins who navigate directly get redirected to `/` (no error flash).
8. The admin nav entry is absent from the `Sidebar` DOM for non-admins.
9. Create drawer posts valid payloads successfully; validation errors (invalid key, rollout out of range) surface as inline error text.
10. Kill-switch toggle in the list row calls `PUT` with the new `is_active` value and optimistically updates the row. On failure, the optimistic update reverts and a toast shows the error.
11. Audit tab renders the chronological log for the currently open flag; paginates on "Load more".
12. The `bucketing_entity` dropdown help text matches the wording in `../README.md` §7.3 (verified by a snapshot test).
13. All component tests, `npm run typecheck`, `npm run format.fix`, `npm run build`, and `npm test` pass.
14. `pytest api/tests/integration/test_admin_feature_flags_endpoints.py api/tests/unit/test_feature_flag_audit_diff.py` passes.
15. `make lint` passes.

## 8. Test plan

### Backend

- `test_admin_feature_flags_endpoints.py` (integration, Firestore emulator):
  - super-admin can list / create / read / update / delete
  - non-super-admin gets 403 on every endpoint
  - duplicate-create returns 409
  - delete-then-get returns 404
  - audit is written for each mutation with the actor email from the token
  - `GET /{key}/audit` paginates correctly (seed 3 pages, verify order + cursor)
- `test_feature_flag_audit_diff.py` (unit):
  - only changed fields appear in the diff
  - nested `targeting_rules` changes produce a single `targeting_rules` diff entry
  - unchanged doc produces empty diff (no audit row written)

### Frontend

- `FlagTable.test.tsx`: renders rows from a mocked hook, kill-switch click fires mutation, optimistic update reverts on error
- `FlagEditDrawer.test.tsx`: form submit posts expected payload; validation errors render inline
- `TargetingRulesEditor.test.tsx`: comma-split and newline-split inputs parse to the same array; slider value clamps to `[0, 100]`
- `FlagAuditList.test.tsx`: renders newest-first; "Load more" fires the next paginated fetch
- `FeatureFlagsPage.test.tsx`: renders only when `isSuperAdmin`; redirect works otherwise
- Sidebar snapshot test: admin section is absent in the non-admin render

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| An admin flipping a kill switch expects instant effect, but other Cloud Run instances cache for up to 60 s | Surface the ≤60 s propagation SLO as a toast after any toggle: *"Kill switch applied. Fully effective within 60 s across all servers."* |
| A deleted flag's audit log is orphaned (no doc at `feature_flags/{key}` to open) | Audit list is queryable by key alone (no foreign key). Admin page adds a "Deleted flags" view that lists keys that appear in `feature_flag_audit` but not in `feature_flags` — deferred to FF-PRD-03 or a follow-up if needed. |
| Super-admin bypass is email-based (`@ken-e.ai`) — a compromised email domain yields full flag control | Matches existing platform pattern; not a FF-PRD regression. Document and accept for Release 1. |
| A typo in `user_emails` silently excludes the intended user (no feedback loop) | The evaluate endpoint's `reason` field already makes this introspectable. FF-PRD-03's dev override lets any engineer validate targeting locally. |
| Large paste into `user_emails` / `account_ids` fields could exceed Firestore doc size (~1 MiB) | Model-level limit: each list capped at 1 000 entries. Enforced in Pydantic (`max_length=1000`). |

### Open questions

- **Q:** Should the audit log record read accesses or only mutations? → **Default: mutations only.** Read logs inflate the audit collection with low value.
- **Q:** Should deletion be soft (`deleted_at` field) rather than hard? → **Default: hard delete.** Flags are expected to be retired and removed; a soft-deleted flag can be re-created with the same key if needed. Audit trail preserves history.

## 10. Reference

- Parent component: [`../README.md`](../README.md) §2.3, §7.6
- Sibling PRDs: [FF-PRD-01](./FF-PRD-01-data-model-evaluation-api.md), [FF-PRD-03](./FF-PRD-03-frontend-sdk-and-e2e.md)
- Depends on: [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md) for shell + primitives
- Root `CLAUDE.md` — §C-5, §C-6, §C-8 (TypeScript), §T-1…T-3 (Testing), §G-1…G-3 (Gates)
- `frontend/CLAUDE.md` — CSS architecture, shadcn component library
- `api/CLAUDE.md` — super-admin auth pattern
