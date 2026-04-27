# Feature Flags — Product Requirements Document

> **Linear Team:** [KEN-E] Feature Flags
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Feature Flags component gives the engineering team a runtime kill-switch and targeted-rollout surface so new capabilities can ship to production behind a toggle and reach a small subset of users first — a specific account allowlist, an email-domain (e.g., `@ken-e.ai` for internal dogfood), or a deterministic percentage bucket — before going generally available. It does not manage user-facing preferences, product experiments, or billing gates; those are separate concerns. This is a platform tool owned by engineering.

The component owns three architectural pillars. **The evaluation engine** (backend `FeatureFlagService` + its in-process cache) takes an `EvaluationContext` (user, organization, account) and a flag key and returns `{enabled, reason}` in <10 ms. **The admin surface** (super-admin CRUD API + `/admin/feature-flags` page) lets platform engineers create, target, kill, and audit flags without a deploy. **The client SDKs** (Python helper for routers/services, React hook for the frontend) are thin wrappers over the evaluation API that every consumer uses so behavior stays consistent between server-rendered decisions and client-rendered UI.

A developer reading only this section should understand: this component owns the `feature_flags/*` + `feature_flag_audit/*` Firestore collections, the `/api/v1/feature-flags/evaluate` and `/api/v1/admin/feature-flags/*` API surfaces, the `/admin/feature-flags` admin page, and the `is_feature_enabled()` (Python) + `useFeatureFlag()` (React) client primitives. It ships in **Release 1: Foundation** so every subsequent component can gate new code behind a flag from day one.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Callers                                                                    │
│    Python: is_feature_enabled("new_ui", user_context)                       │
│    React:  useFeatureFlag("new_ui")  →  { enabled, reason }                 │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  /api/v1/feature-flags/evaluate (POST)                                      │
│    Body: { flag_keys: ["new_ui", "automations_beta"] }                      │
│    Auth: Firebase JWT → UserContext (user_id, email, org_id, account_id)    │
│    Returns: { evaluations: { "new_ui": {enabled, reason}, ... } }           │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FeatureFlagService.evaluate_batch(flag_keys, ctx)                          │
│    ├── in-process LRU cache (60s TTL, keyed by flag_key)                    │
│    ├── Firestore read: feature_flags/{flag_key}                             │
│    └── evaluate(flag, ctx):                                                 │
│          1. is_active=false      → default_enabled   (kill switch)          │
│          2. user email in list   → enabled                                  │
│          3. email domain match   → enabled                                  │
│          4. organization_id in list → enabled                               │
│          5. account_id in list   → enabled                                  │
│          6. hash(flag_key, <bucketing_entity_id>) % 100 < rollout_percentage│
│                                  → enabled                                  │
│          7. otherwise            → default_enabled                          │
└─────────────────────────────────────────────────────────────────────────────┘

                              Admin surface

┌─────────────────────────────────────────────────────────────────────────────┐
│  /admin/feature-flags  (super-admin only)                                   │
│    list · create · edit targeting · toggle is_active · audit log            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  /api/v1/admin/feature-flags/*  (super-admin only)                          │
│    GET /              POST /              GET /{key}                        │
│    PUT /{key}         DELETE /{key}       GET /{key}/audit                  │
│    writes audit entry on every mutation                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/feature_flag_models.py` | `FeatureFlag`, `TargetingRules`, `EvaluationContext`, `FlagEvaluation`, `EvaluateRequest`, `EvaluateResponse`. Created by FF-PRD-01. |
| `api/src/kene_api/services/feature_flag_service.py` | `FeatureFlagService.evaluate_batch`, `evaluate(flag, ctx)`, hash-bucketing helper, in-process cache. Created by FF-PRD-01. |
| `api/src/kene_api/routers/feature_flags.py` | `POST /api/v1/feature-flags/evaluate` — authenticated users evaluate flags for their own context. Created by FF-PRD-01. |
| `api/src/kene_api/routers/admin_feature_flags.py` | `/api/v1/admin/feature-flags/*` — super-admin CRUD + audit. Created by FF-PRD-02. |
| `api/src/kene_api/services/feature_flag_audit.py` | Writes `feature_flag_audit/{audit_id}` on every mutation. Created by FF-PRD-02. |
| `frontend/src/contexts/FeatureFlagsContext.tsx` | `FeatureFlagsProvider`, `useFeatureFlag(key)` hook, dev URL-override integration. Created by FF-PRD-03. |
| `frontend/src/lib/featureFlags/client.ts` | Typed client calling `/api/v1/feature-flags/evaluate` with React Query. Created by FF-PRD-03. |
| `frontend/src/pages/admin/FeatureFlagsPage.tsx` | Admin list + create/edit drawer + audit tab. Created by FF-PRD-02. |
| `deployment/firestore.indexes.json` | One composite index on `feature_flag_audit` (`flag_key ASC, created_at DESC`). Added by FF-PRD-01. |

### 2.2 Data Flow

1. **Flag creation (FF-PRD-02):** A super-admin opens `/admin/feature-flags`, fills in `key`, `description`, `default_enabled=false`, `is_active=true`, targeting rules, and `bucketing_entity` (default `account`). The admin API writes `feature_flags/{key}` and an audit entry to `feature_flag_audit/{audit_id}`.
2. **Server-side evaluation (FF-PRD-01):** A router or service calls `is_feature_enabled("new_ui", user_context)`. The helper calls `FeatureFlagService.evaluate_batch(["new_ui"], ctx)`. Service hits the in-process LRU cache (60 s TTL keyed by `flag_key`); on miss, reads Firestore. The evaluator walks the precedence ladder (see §2, §7.2) and returns `{enabled, reason}`.
3. **Client-side evaluation (FF-PRD-03):** `FeatureFlagsProvider` (mounted under `AuthContext`) batch-evaluates the flags used in the app via `POST /api/v1/feature-flags/evaluate` on mount and whenever `selectedAccount.accountId` changes. Results cached in TanStack Query with 60 s staleTime. `useFeatureFlag("new_ui")` reads from that cache.
4. **Kill switch:** An admin toggles `is_active=false`. Backend LRU cache expires within 60 s; frontend cache expires within 60 s of the next `AuthContext` change or on SWR revalidation. Worst-case propagation: ~60 s. That latency is the Release 1 trade-off for simplicity (no Firestore listeners, no Redis).
5. **Audit trail:** Every CRUD mutation records `{flag_key, actor_email, action, diff, created_at}` to `feature_flag_audit/{audit_id}`. The admin UI surfaces this per-flag.
6. **Dev override (FF-PRD-03):** In non-production environments (`import.meta.env.VITE_ENVIRONMENT !== 'production'`), a URL param `?ff.new_ui=on` or `?ff.new_ui=off` short-circuits the hook for that browser tab. Persisted to `sessionStorage`. Has no effect in production.

### 2.3 API Contracts

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/feature-flags/evaluate` | POST | FF-PRD-01 | `EvaluateRequest { flag_keys }` → `EvaluateResponse { evaluations: Record<FlagKey, FlagEvaluation> }` |
| `/api/v1/admin/feature-flags` | GET | FF-PRD-02 | List all flags (super-admin only) |
| `/api/v1/admin/feature-flags` | POST | FF-PRD-02 | Create flag (super-admin only) |
| `/api/v1/admin/feature-flags/{key}` | GET | FF-PRD-02 | Single flag (super-admin only) |
| `/api/v1/admin/feature-flags/{key}` | PUT | FF-PRD-02 | Full replace of flag config (super-admin only) |
| `/api/v1/admin/feature-flags/{key}` | DELETE | FF-PRD-02 | Hard-delete (super-admin only; writes audit entry) |
| `/api/v1/admin/feature-flags/{key}/audit` | GET | FF-PRD-02 | Audit log for a flag (super-admin only) |

Schema source of truth: `api/src/kene_api/models/feature_flag_models.py` (Pydantic), mirrored in `frontend/src/lib/featureFlags/types.ts` as branded `FlagKey` + matching `FeatureFlag` / `TargetingRules` / `FlagEvaluation` types. URL paths use kebab-case (`feature-flags`); Firestore collections use snake_case (`feature_flags`, `feature_flag_audit`); **flag keys are snake_case** (regex in §7.1). Drift between Python and TypeScript is gated by FF-PRD-01's JSON-schema snapshot test (see §7.1).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `FeatureFlag` | `api/src/kene_api/models/feature_flag_models.py` | Pydantic model: `key`, `description`, `default_enabled`, `is_active`, `targeting_rules`, `bucketing_entity`, `owner`, `expected_ga_release`. (FF-PRD-01) |
| `TargetingRules` | Same | `user_emails`, `email_domains`, `organization_ids`, `account_ids`, `rollout_percentage` (0–100). (FF-PRD-01) |
| `EvaluationContext` | Same | `user_id`, `user_email`, `organization_id`, `account_id`. Built from the auth token server-side. (FF-PRD-01) |
| `FeatureFlagService.evaluate_batch(keys, ctx)` | `api/src/kene_api/services/feature_flag_service.py` | Batch evaluator + in-process LRU cache. Never raises — unknown flag returns `{enabled: false, reason: "unknown_flag"}`. (FF-PRD-01) |
| `is_feature_enabled(key, ctx, default=False)` | Same | Ergonomic Python helper for routers/services. Swallows service errors and returns `default` so a flag outage cannot take down the app. (FF-PRD-01) |
| `hash_bucket(flag_key, entity_id)` | Same | `int(sha256(f"{flag_key}:{entity_id}").hexdigest()[:8], 16) % 100`. Deterministic 0–99. (FF-PRD-01) |
| `FeatureFlagsProvider` | `frontend/src/contexts/FeatureFlagsContext.tsx` | React context that batch-evaluates known flags against the active `AuthContext` and re-evaluates on `selectedAccount` change. (FF-PRD-03) |
| `useFeatureFlag(key)` | Same | Hook returning `{ enabled, reason, isLoading }`. Uses dev URL-override when not in production. (FF-PRD-03) |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| GCP Firestore | New `feature_flags/` + `feature_flag_audit/` top-level collections (Shape C — global, not account-scoped). One composite index on `feature_flag_audit (flag_key, created_at)`. | `deployment/firestore.indexes.json` |
| Existing `UserContext` / `is_super_admin` | Evaluation context is built from the auth token; admin endpoints gated on `is_super_admin` (email suffix `@ken-e.ai`). | `api/src/kene_api/auth/models.py` |
| `AuthContext` (frontend) | Provides `user.id`, `user.email`, `selectedOrgAccount.{orgId, accountId}` — the full evaluation context. | `frontend/src/contexts/AuthContext.tsx` |
| TanStack Query | Existing `QueryClientProvider` is reused by the `FeatureFlagsProvider` — no new cache stack. | `frontend/src/App.tsx` |
| UI-PRD-01 (Design System Foundation + Shell) | **Hard prerequisite for FF-PRD-02.** The admin page lives inside `LayoutC` and uses re-skinned shadcn primitives. | [`../ui/projects/UI-PRD-01-design-system-foundation.md`](../ui/projects/UI-PRD-01-design-system-foundation.md) |

This component **does not** depend on the Data Management migration (DM-PRD-00…06) because flags are a global Shape-C collection, not account-scoped. FF-PRD-01 can start on day 1 of Release 1.

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| All Release 1+ feature work | Any new capability that ships during Release 1 can be gated behind a flag. Teams opt in per feature; no mandatory instrumentation. |
| [UI](../ui/README.md) | UI-PRD-06's `VITE_EXTENSIONS_ENABLED` one-off env flag can migrate to a feature flag as a follow-up (non-blocking — UI team owns the migration timing). |
| [Agentic Harness](../agentic-harness/README.md) | AH-PRD-02's Agent Factory can gate the factory-driven build path behind a flag during the cut-over from hardcoded specialists. Non-blocking. |
| Engineering incident response | Any shipped feature can be killed in ≤60 s via `is_active=false`. Documented in `api/CLAUDE.md` runbook section. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Admin / internal-tooling patterns (reuse the Settings table + drawer pattern from UI-PRD-02) | When implementing FF-PRD-02. No bespoke admin design in Figma yet — reuse existing table + drawer primitives. |
| `frontend/CLAUDE.md` | CSS architecture, branded types, UI component library | Before adding any new React component. |

## 5. Project Index

The component's Release 1 work is split across **3 project PRDs** under [`projects/`](./projects/). FF-PRD-01 unblocks FF-PRD-02 and FF-PRD-03, which can then run in parallel by separate dev teams.

### 5.1 Dependency graph

```
                   ┌─────────────────────────────────────┐
                   │  FF-PRD-01: Data Model +            │
                   │             Evaluation API +        │
                   │             Backend SDK             │
                   └──────────────┬──────────────────────┘
                                  │
            ┌─────────────────────┴──────────────────────┐
            ▼                                            ▼
   ┌─────────────────────┐                  ┌─────────────────────┐
   │  FF-PRD-02:         │                  │  FF-PRD-03:         │
   │  Admin API + UI     │◄─ UI-PRD-01      │  Frontend SDK + E2E │
   └─────────────────────┘                  └─────────────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Data Model, Evaluation API, Backend SDK](./projects/FF-PRD-01-data-model-evaluation-api.md) | Platform / Backend | — | DM-PRD-00–06, AH-PRD-01, UI-PRD-01 | 3–4 days |
| 02 | [Admin API + UI](./projects/FF-PRD-02-admin-api-and-ui.md) | Platform (backend + frontend) | FF-PRD-01, UI-PRD-01 | FF-PRD-03 | 3–4 days |
| 03 | [Frontend SDK + E2E](./projects/FF-PRD-03-frontend-sdk-and-e2e.md) | Frontend | FF-PRD-01 | FF-PRD-02 | 2–3 days |

### 5.3 Cross-PRD coordination points

Two touchpoints need conscious coordination:

- **Typed-client contract (FF-PRD-02 ↔ FF-PRD-03):** `frontend/src/lib/featureFlags/types.ts` is **owned by FF-PRD-02**. FF-PRD-03 imports from it and appends runtime-only types (`FeatureFlagsContextValue`, `UseFeatureFlagResult`). The Pydantic models in `feature_flag_models.py` (FF-PRD-01) are mirrored manually; a JSON-schema snapshot test (`api/tests/unit/test_feature_flag_schema_contract.py`) catches Python-side drift, and the PR reviewer compares the snapshot diff against the matching `types.ts` change in the same PR.
- **Bucketing-entity choice in documentation (FF-PRD-01 ↔ FF-PRD-02):** The admin UI must explain `bucketing_entity` clearly (default `account`; switch to `user` only when the flag genuinely follows a person across accounts). FF-PRD-01 owns the prose; FF-PRD-02 surfaces it in the create/edit form's help text.

### 5.4 Recommended workflow

1. **Sprint 1:** Backend ships FF-PRD-01 (3–4 days). No external blockers — runs in parallel with DM-PRD-00 and UI-PRD-01.
2. **Sprint 2:** FF-PRD-02 and FF-PRD-03 parallelize across two teams (full-stack for 02, frontend for 03). UI-PRD-01 must have merged for FF-PRD-02's admin page.
3. **Release 1 exit:** Feature flag system operational in staging. Engineering incident runbook updated. Any Release 1 feature can now be shipped gated.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §4 Database, §6 Tooling Gates | Branded types (C-5), `import type` (C-6), Pydantic models (PY-2), Firestore context manager (D-1), test conventions (T-1…T-8), lint/typecheck gates (G-1…G-3). |
| `api/CLAUDE.md` | Firestore access patterns, super-admin auth pattern, Secret Manager | Before building the evaluation service or admin endpoints. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn component library, TanStack Query patterns | Before building the admin UI or the React hook. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 Feature Flags entry | Rationale for the current Shape-C collection layout and bucketing-entity decision. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Review 16 — Feature Flags Component | Full decision rationale for the targeting model (allowlist + per-entity percentage rollout). |

## 7. Conventions and Constraints

### 7.1 Flag schema

- **Boolean flags only for Release 1.** Multi-variant (string / JSON) flags are a future PRD; no speculative schema in Release 1.
- `key` is **snake_case**, regex `^[a-z0-9][a-z0-9_]{2,63}$`. Enforced in the Pydantic model and at the admin API. (Snake_case matches the convention every consumer component uses — `chat_v2_enabled`, `billing_enabled`, `performance_dashboards_tab`, etc.)
- `default_enabled` should be `false` for in-development features. Flip to `true` at GA and then retire the flag (delete the doc, remove callers).
- `is_active=false` is the kill switch — always returns `default_enabled` regardless of targeting.
- `bucketing_entity` is `"account"` by default; override to `"user"` only when the feature genuinely travels with a person across accounts (e.g., profile settings), or `"organization"` when the feature is an org-wide capability.
- `owner` is the responsible engineer's email. Every flag has an owner.
- `expected_ga_release` is a free-text string (e.g., `"Release 2"`). No machine-readable semantics — purely for the admin UI's "old flags" report.

### 7.2 Targeting evaluation order (highest precedence first)

1. `is_active=false` → `default_enabled` (kill switch short-circuits all targeting).
2. `user_email` ∈ `targeting_rules.user_emails` (case-insensitive) → `enabled=true`.
3. email domain (substring after `@`) ∈ `targeting_rules.email_domains` → `enabled=true`.
4. `organization_id` ∈ `targeting_rules.organization_ids` → `enabled=true`.
5. `account_id` ∈ `targeting_rules.account_ids` → `enabled=true`.
6. `rollout_percentage > 0` AND `hash_bucket(flag_key, <bucketing_entity_id>) < rollout_percentage` → `enabled=true`.
7. Otherwise → `default_enabled`.

Allowlists compose with percentage rollout (e.g., "enable for `@ken-e.ai` + 5% of accounts" is expressible as `email_domains=["ken-e.ai"]` + `rollout_percentage=5` on the same flag).

### 7.3 Stickiness

- Percentage-rollout bucket = `int(sha256(f"{flag_key}:{entity_id}").hexdigest()[:8], 16) % 100`. Deterministic across sessions, devices, and backend/frontend callers.
- `entity_id` resolves from the flag's `bucketing_entity`:
  - `"account"` → `evaluation_context.account_id`
  - `"organization"` → `evaluation_context.organization_id`
  - `"user"` → `evaluation_context.user_id`
- If the chosen bucketing entity is missing from the context (e.g., a user with no selected account), rollout returns `false` and evaluation falls through to `default_enabled`. Surfaced in the admin UI as a help note.
- **Never hash on `email` or any PII-bearing field** — the entity ID is an opaque ULID/branded string.

### 7.4 Caching and propagation

- **Backend:** in-process LRU cache, 60 s TTL, keyed by `flag_key` (not by user). Each Cloud Run instance has its own cache; kill-switch propagation is bounded by TTL × fleet size, but per-instance it's ≤60 s. No Redis or Firestore listener in Release 1.
- **Frontend:** TanStack Query with `staleTime=60_000`. Re-evaluation triggered by any of: initial mount, `selectedAccount.accountId` change, `user.id` change, explicit `queryClient.invalidateQueries(['feature-flags'])`.
- **Kill switch SLO:** a malfunctioning feature can be killed in ≤60 s end-to-end (admin write + cache expiry). Documented in `api/CLAUDE.md`.

### 7.5 Firestore layout (Shape C — global)

- `feature_flags/{flag_key}` — one doc per flag, keyed by the human-readable `flag_key` itself.
- `feature_flag_audit/{audit_id}` — one doc per mutation; flat global collection indexed on `(flag_key ASC, created_at DESC)`.

These are **Shape C carve-outs** — global, not under `accounts/{account_id}/…`. Mirrors the `notifications` / `usage_records` pattern and is spelled out in the Multi-Tenant Data Model decision.

### 7.6 Security

- `POST /api/v1/feature-flags/evaluate` — any authenticated user. The server builds the evaluation context from the auth token, so users cannot spoof a different `user_id` / `organization_id` / `account_id` into an evaluation. Evaluation never returns the underlying flag config.
- `/api/v1/admin/feature-flags/*` — gated on `is_super_admin` (email ends with `@ken-e.ai`). No org-admin access in Release 1.
- Flag values should **never gate security-sensitive decisions** (auth, payment, data isolation). Flags are for UX and capability rollout only. Enforced by convention + code review, not by the platform.

### 7.7 Dev override (non-production only)

- URL param `?ff.<key>=on` or `?ff.<key>=off` overrides the evaluated value for that browser tab.
- Persisted to `sessionStorage` so tab refresh preserves the override.
- Only active when `import.meta.env.VITE_ENVIRONMENT !== 'production'`. In production the param is ignored and never read.
- Surfaced in the `FeatureFlagsProvider` — `useFeatureFlag` returns `{ enabled, reason: "dev_override", ... }` so tests can detect it.

### 7.8 Standard shape for a project PRD in [`projects/`](./projects/)

Every PRD follows the shared 10-section structure used across sibling components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, upstream design docs

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a flag migrates to GA and the flag is retired: no PRD update needed; remove callers + delete the Firestore doc.
- When multi-variant (string / JSON) flags are added: open FF-PRD-04 and update §7.1.
- When per-account or per-org admin self-service is added: open FF-PRD-05 and update §7.6.
- When architecture changes (new endpoints, new caching layer): update §2.
- When a cross-component dependency is introduced: update §3.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
