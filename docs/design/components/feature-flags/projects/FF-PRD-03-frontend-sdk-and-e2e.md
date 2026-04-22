# FF-PRD-03 — Frontend SDK + E2E

**Status:** Blocked (on FF-PRD-01)
**Owner team:** Frontend
**Blocked by:** FF-PRD-01
**Parallel with:** FF-PRD-02
**Estimated effort:** 2–3 days

---

## 1. Context

Ships the runtime client SDK that every frontend caller uses to read feature flags: `FeatureFlagsProvider`, `useFeatureFlag(key)`, and the non-production URL-override escape hatch. Also closes out the component with an end-to-end test that proves the full loop (admin creates a flag → targeting rule matches → hook returns `true` for matching users and `false` for others), plus the `api/CLAUDE.md` runbook so the engineering team can actually use the system on day one of Release 1.

This PRD does not migrate any existing gated features to flags (e.g., UI-PRD-06's `VITE_EXTENSIONS_ENABLED`). Migrations are owned by the feature teams and happen opportunistically.

See [`../README.md`](../README.md) §2.2 step 3, §7.4, and §7.7 for the client-side evaluation behavior.

## 2. Scope

### In scope
- `FeatureFlagsProvider` React context mounted under `AuthContext` in `App.tsx`
- `useFeatureFlag(key) → { enabled, reason, isLoading }` hook
- Typed evaluate client (`frontend/src/lib/featureFlags/client.ts`) hitting `POST /api/v1/feature-flags/evaluate`
- TanStack Query integration: `staleTime=60_000`, query key `["feature-flags", user.id, accountId]`, re-evaluation on `selectedAccount.accountId` change
- Dev URL-override mechanism (`?ff.<key>=on|off`) — active only when `VITE_ENVIRONMENT !== 'production'`, persisted to `sessionStorage`
- Registry of known flag keys (`frontend/src/lib/featureFlags/registry.ts`) — the keys the app batch-evaluates at provider mount
- End-to-end Playwright test exercising the full admin-to-hook loop
- Runbook section in `api/CLAUDE.md` (kill-switch procedure) and `frontend/CLAUDE.md` (how to gate a new feature behind a flag)

### Out of scope
- Per-call (one-off) evaluation outside the batch registry — deferred
- Server-side rendering / Next.js integration (KEN-E is SPA-only)
- Migrating existing `VITE_*` gates to flags — feature-team-owned migrations
- Backend Python helper, evaluate endpoint, admin UI — owned by FF-PRD-01 and FF-PRD-02

## 3. Dependencies

- **FF-PRD-01** — `/api/v1/feature-flags/evaluate` endpoint + response shape
- **FF-PRD-02** — shared `types.ts` (branded `FlagKey`, `FlagEvaluation`, etc.). Whichever PRD ships first owns the file; the other imports from it.
- Existing `AuthContext` — provides `user.id`, `user.email`, `selectedOrgAccount`
- Existing `QueryClientProvider` at the app root
- Existing Playwright harness (if present) or a new minimal setup (≤1/2 day)

## 4. Data contract

### Shared types (from FF-PRD-02's `frontend/src/lib/featureFlags/types.ts`)

Re-used here:

```ts
export type FlagEvaluation = {
  key: FlagKey;
  enabled: boolean;
  reason:
    | "kill_switch" | "email_match" | "domain_match"
    | "org_match" | "account_match" | "rollout" | "default"
    | "unknown_flag" | "dev_override";
};
```

### New types owned here (`frontend/src/lib/featureFlags/types.ts`, appended)

```ts
export type FeatureFlagsContextValue = {
  evaluations: Record<string, FlagEvaluation>;
  isLoading: boolean;
  refetch: () => Promise<void>;
};

export type UseFeatureFlagResult = {
  enabled: boolean;
  reason: FlagEvaluation["reason"];
  isLoading: boolean;
};
```

### Registry (`frontend/src/lib/featureFlags/registry.ts`)

```ts
import type { FlagKey } from "./types";

// Keys the app batch-evaluates on provider mount.
// Add entries here before using useFeatureFlag(key) anywhere in the app.
export const KNOWN_FLAGS: FlagKey[] = [
  // "automations-beta" as FlagKey,
] satisfies FlagKey[];
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create (or extend) | `frontend/src/lib/featureFlags/types.ts` — extend FF-PRD-02's type file with runtime types |
| Create | `frontend/src/lib/featureFlags/client.ts` — typed `evaluate(flagKeys)` call |
| Create | `frontend/src/lib/featureFlags/registry.ts` — `KNOWN_FLAGS` array |
| Create | `frontend/src/lib/featureFlags/devOverride.ts` — URL-param parser + sessionStorage persistence |
| Create | `frontend/src/contexts/FeatureFlagsContext.tsx` — `FeatureFlagsProvider` + `useFeatureFlag` |
| Modify | `frontend/src/App.tsx` — mount `<FeatureFlagsProvider>` under `<AuthProvider>` and `<QueryClientProvider>` |
| Create | `frontend/src/contexts/FeatureFlagsContext.test.tsx` |
| Create | `frontend/src/lib/featureFlags/devOverride.test.ts` |
| Create | `frontend/e2e/featureFlags.spec.ts` (Playwright) |
| Modify | `api/CLAUDE.md` — kill-switch runbook section |
| Modify | `frontend/CLAUDE.md` — "Gating a feature behind a flag" recipe |

### 5.1 Provider behavior

```
mount
  └─ read KNOWN_FLAGS
  └─ read user + accountId from AuthContext
  └─ apply dev overrides (non-production only) — overrides short-circuit per key
  └─ queryClient.fetchQuery(["feature-flags", user.id, accountId], () => evaluate(KNOWN_FLAGS))
  └─ expose { evaluations, isLoading, refetch }

on accountId change (AuthContext)
  └─ queryClient.invalidateQueries(["feature-flags"])

on explicit refetch()
  └─ queryClient.invalidateQueries(["feature-flags"])
```

### 5.2 `useFeatureFlag(key)`

- If a dev override exists for `key` (only possible in non-production), return `{ enabled: <override>, reason: "dev_override", isLoading: false }`.
- Else return `{ enabled, reason, isLoading }` from the context.
- If `key` is not in `KNOWN_FLAGS`, return `{ enabled: false, reason: "unknown_flag", isLoading: false }` and log a `console.warn` in development (not production).

### 5.3 Dev override

```ts
// ?ff.automations-beta=on  →  override = true
// ?ff.automations-beta=off →  override = false
// Any other value → ignored
// Value persisted to sessionStorage under key "kene.ff-overrides"
// Only honored when import.meta.env.VITE_ENVIRONMENT !== "production"
```

### 5.4 E2E test outline (`frontend/e2e/featureFlags.spec.ts`)

1. Seed flag `e2e-test-flag` in Firestore emulator with `targeting_rules.email_domains=["ken-e.ai"]`, `default_enabled=false`.
2. Add `"e2e-test-flag"` to `KNOWN_FLAGS` (via a test-only registry shim) or ship a test-mode env that unions a fixture registry.
3. Log in as a `@ken-e.ai` user → assert `useFeatureFlag("e2e-test-flag")` returns `{ enabled: true, reason: "domain_match" }` on the test harness page.
4. Log out, log in as a non-`@ken-e.ai` user → assert `{ enabled: false, reason: "default" }`.
5. Flip `is_active=false` via the admin API → wait ≤60 s → assert `{ enabled: false, reason: "kill_switch" }` for both users.
6. In a non-production env, navigate with `?ff.e2e-test-flag=on` as the non-`@ken-e.ai` user → assert `{ enabled: true, reason: "dev_override" }`.

### 5.5 Documentation recipes

`frontend/CLAUDE.md` gains a short "Gating a feature behind a flag" section:

```ts
// 1. Add the key to frontend/src/lib/featureFlags/registry.ts
export const KNOWN_FLAGS = [
  "automations-beta" as FlagKey,
];

// 2. Use the hook where the feature is rendered
const { enabled } = useFeatureFlag("automations-beta" as FlagKey);
if (!enabled) return <LegacyView />;
return <NewView />;

// 3. Ask a super-admin to create the flag in /admin/feature-flags
//    with targeting rules + owner + expected_ga_release.

// 4. In dev, toggle with ?ff.automations-beta=on
```

`api/CLAUDE.md` gains a "Feature flag kill-switch" runbook:

```
To kill a feature in production:

1. Open /admin/feature-flags as a super-admin.
2. Find the flag; flip is_active → off.
3. Confirm the toast ("Kill switch applied. Fully effective within 60 s").
4. Monitor error rates / user reports. Full propagation across all Cloud Run
   instances takes ≤60 s (cache TTL).
```

## 6. API contract

Consumes `POST /api/v1/feature-flags/evaluate` (owned by FF-PRD-01). No new endpoints.

## 7. Acceptance criteria

1. `FeatureFlagsProvider` mounts under `AuthContext` and `QueryClientProvider` in `App.tsx`. Before it resolves, `useFeatureFlag` returns `isLoading: true`.
2. Provider issues exactly one `POST /evaluate` on initial mount with `flag_keys` equal to `KNOWN_FLAGS`.
3. Switching the active account (`AuthContext.selectedOrgAccount.accountId` change) invalidates the query and issues a fresh `POST /evaluate` within one tick.
4. `useFeatureFlag(key)` returns the cached evaluation for `key`; unknown keys return `{ enabled: false, reason: "unknown_flag" }` and log a dev-only `console.warn`.
5. Dev URL override `?ff.<key>=on|off` sets `{ enabled, reason: "dev_override" }` for that key in non-production. In production (`VITE_ENVIRONMENT === "production"`), the URL param is ignored and `reason` never equals `"dev_override"`.
6. Dev override persists to `sessionStorage` so a tab refresh preserves the value; clearing the param from the URL does *not* clear the override (matches browser session-storage semantics).
7. `KNOWN_FLAGS` registry is the single source of truth for batch-evaluated keys. Adding a new feature flag requires editing this file.
8. E2E test (§5.4) passes in CI against the Firestore emulator.
9. `frontend/CLAUDE.md` has a "Gating a feature behind a flag" section matching §5.5.
10. `api/CLAUDE.md` has a "Feature flag kill-switch" runbook section matching §5.5.
11. All component tests, `npm run typecheck`, `npm run format.fix`, `npm run build`, and `npm test` pass. `make lint` passes.

## 8. Test plan

### Unit / component tests

- `devOverride.test.ts`:
  - parses `?ff.foo=on` → `{ foo: true }`
  - parses `?ff.foo=off&ff.bar=on` → `{ foo: false, bar: true }`
  - ignores `?ff.foo=maybe` (non-binary value)
  - writes to `sessionStorage` under `kene.ff-overrides`
  - returns empty overrides when `VITE_ENVIRONMENT === "production"` (env mocked at module level)
- `FeatureFlagsContext.test.tsx`:
  - provider mounts, issues one evaluate call, then `useFeatureFlag` returns the resolved value
  - account switch triggers a re-evaluation
  - dev override wins over server evaluation
  - unknown key returns `reason: "unknown_flag"`
  - `refetch()` invalidates the query

### E2E test (Playwright)

- `featureFlags.spec.ts` per §5.4.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Race between `AuthContext` settling and `FeatureFlagsProvider` evaluating | Provider reads auth *inside* the React Query function; TanStack Query won't fetch with an undefined user (gate the query with `enabled: !!user`). `useFeatureFlag` surfaces `isLoading: true` while auth or the query is pending. |
| Dev override leaking into production via URL-sharing | Hard-gated on `VITE_ENVIRONMENT !== "production"`. Enforced in tests. |
| E2E test flakiness from the 60 s cache TTL after kill-switch | Test monkey-patches the Cloud Run instance's cache TTL to 1 s in the emulator environment (exposed via a test-only env var read in FF-PRD-01's service). |
| Adding a flag key to a component but forgetting `KNOWN_FLAGS` → silent `unknown_flag` everywhere | `console.warn` in development + ESLint rule (follow-up, not in this PRD) that flags literal string args to `useFeatureFlag` not present in `KNOWN_FLAGS`. |
| Sessionstorage override persists across test runs and leaks state | Test setup explicitly clears `kene.ff-overrides` before each E2E scenario. |

### Open questions

- **Q:** Should `useFeatureFlag` accept a default-enabled second argument (e.g., `useFeatureFlag("foo", { defaultEnabled: true })`) to render something while loading? → **Default: no.** Components render on the evaluated value; loading states are standard React Query UX. Adding a default would encourage drift from the server decision.
- **Q:** Should we ship a `<FeatureGate flag="foo">…</FeatureGate>` component? → **Default: no.** The hook is ergonomic enough; a component wrapper adds surface area without clear value. Revisit if call sites get repetitive.

## 10. Reference

- Parent component: [`../README.md`](../README.md) §2.2, §7.4, §7.7
- Sibling PRDs: [FF-PRD-01](./FF-PRD-01-data-model-evaluation-api.md), [FF-PRD-02](./FF-PRD-02-admin-api-and-ui.md)
- Root `CLAUDE.md` — §C-5, §C-6, §C-8 (TypeScript), §T-2 (Tests), §G-2, §G-3 (Gates)
- `frontend/CLAUDE.md` — shadcn component library, TanStack Query patterns
