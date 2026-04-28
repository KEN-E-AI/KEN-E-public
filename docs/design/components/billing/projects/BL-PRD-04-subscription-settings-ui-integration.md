# BL-PRD-04 — Subscription Settings UI Integration

**Status:** Not started
**Owner team:** Frontend team + Billing component team (joint)
**Blocked by:** [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md), [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md), [UI-PRD-01](../../ui/projects/UI-PRD-01-design-system-foundation.md) (provides `LayoutC` + `bannerSlot` outlet), [UI-PRD-02](../../ui/projects/UI-PRD-02-core-shell-pages.md) (provides `SETTINGS_NAV_REGISTRY`), [CH-PRD-02](../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md) (creates `frontend/src/components/chat/ChatInterface.tsx` that BL-PRD-04 modifies for the chat-input disabled state)
**Parallel with:** [BL-PRD-05](./BL-PRD-05-failure-modes-permissions.md) — UI work and backend hardening don't block each other; BL-PRD-04 ships against the BL-PRD-03 endpoints with no admin gate and BL-PRD-05 layers DM-PRD-07's `OrgRole.ADMIN` gate on later
**Blocks:** BL-PRD-06
**Estimated effort:** 4 days frontend (≈3 days production wiring + ≈1 day inactive-banner + chat-disabled state)

---

## 1. Context

The figma-export prototype (`docs/figma-export/src/app/components/SubscriptionTab.tsx`) is the design contract this project ships in production. It already implements the Subscription tab UI: Current Plan card, usage bar, daily-usage area chart with breakdown selector, tiered upgrade slider with sales-handoff prompt at the top of the slider. The prototype currently uses mock data and local state; this PRD wires every surface to the real APIs from BL-PRD-02 and BL-PRD-03 and adds the cross-app surfaces that the prototype doesn't cover (the global inactive banner and the chat-input disabled state).

Three things land here that don't exist in the prototype:

1. **Global inactive banner** at the app-shell level — visible across every page when `OrganizationStatus.status` starts with `inactive_`. Renders the structured `reason_message` from the backend with a CTA deep-linking to the Subscription tab.
2. **Chat input disabled state** — `ChatInterface` calls a `useOrgStatus()` hook on mount and on focus; when status is `inactive_*`, the input is disabled with an inline explanation that mirrors the banner.
3. **Sales-handoff form** — when the slider hits the max ($4,829 / 81M), the existing "Need a larger allowance?" callout becomes a real form (estimated tokens, billing contact, anticipated start date, free-text notes) that posts to the BL-PRD-06 endpoint.

The pricing slider also moves from a hardcoded constant in the prototype to a fetch from `/api/v1/billing/pricing-tiers` — keeping the JSON in `shared/billing/pricing-tiers.v1.json` as the single source of truth.

## 2. Scope

### In scope
- **Replace mock state in `SubscriptionTab.tsx`** with real API calls:
  - `useBillingProfile(orgId)` — fetches `/api/v1/billing/{org_id}/profile`. Drives the Current Plan card.
  - `useUsageCurrent(orgId)` — fetches `/api/v1/billing/{org_id}/usage/current`. Drives the usage bar + reset-date copy.
  - `useUsageDaily(orgId, from, to, breakdown)` — fetches `/api/v1/billing/{org_id}/usage/daily`. Drives the chart.
  - `usePricingTiers()` — fetches `/api/v1/billing/pricing-tiers` once per session, cached. Drives the slider stops, endpoint labels, and dynamic "Next step" helper text.
- **Upgrade button wiring** — `Upgrade Subscription` CTA in the dialog footer POSTs `/api/v1/billing/{org_id}/checkout-session` with the chosen `tier_stop_index` and redirects to the returned `checkout_url`. On return from Stripe (success_url query param), refetch profile + status; render a confirmation toast.
- **Mid-cycle subscription change wiring** — for an org already on a paid plan, the "Upgrade Subscription" button instead opens a "Change plan" variant of the same dialog and POSTs `/subscription/change`. The dialog header and CTA copy adapt based on `BillingProfile.plan`.
- **Cancel subscription** — net-new "Cancel subscription" tertiary action in the Subscription tab (link-style, below the upgrade dialog) that opens a confirmation modal explaining "Your plan continues until {period_end}; you'll revert to Free." Calls `/subscription/cancel`.
- **Customer Portal deep-link** — net-new "Manage payment method" link in the Current Plan card that POSTs `/customer-portal-session` and redirects to the returned `portal_url`.
- **Sales-handoff form** — the existing max-tier callout becomes a real form with fields `{estimated_monthly_tokens (number), billing_contact_email, anticipated_start_date (optional), notes (textarea)}`. POSTs `/api/v1/billing/{org_id}/sales-handoff` (BL-PRD-06 contract); shows confirmation. Form is keyed to be filled-once-per-month (sessionStorage debounce).
- **Global inactive banner** — net-new component `OrganizationStatusBanner` mounted in `LayoutC.tsx` above the page content. Visible whenever `OrganizationStatus.status != "active"`. Renders `reason_message` + CTA "Manage subscription" linking to `/settings/organization/subscription`. Color-codes by status (`inactive_overage` red, `inactive_past_due` red, `inactive_canceled` amber, `approaching_limit` amber).
- **`useOrgStatus` hook** — shared hook that polls `/api/v1/internal/billing/status/{org_id}` (proxied through a thin frontend BFF endpoint that doesn't require OIDC) every 60s, plus an immediate refresh on tab focus and on every successful Stripe-return navigation. Single source of truth for the banner, the chat-disabled state, and any other gated surface added later.
- **Chat input disabled state** — `ChatInterface` reads `useOrgStatus()`; when inactive, replaces the input area with a disabled state showing the same reason message + CTA. Existing in-flight chat continues to render normally; the disabled state applies to *new* messages only.
- **402 response handling** — global API client interceptor (`apiClient.ts`) catches 402 responses, calls `useOrgStatus().refetch()`, and surfaces a toast pointing to the Subscription tab. Idempotent — repeated 402s don't stack toasts.
- **Dynamic chart breakdown** — current chart logic from prototype reused; `breakdown=user` in the API response fills the `by_user` color encoding; `breakdown=account` fills `by_account`.
- **Pricing-tier feature parity with prototype** — slider stops, helper text ("Next step: +X tokens for $Y more"), endpoint labels all preserved; only data source changes.
- **Loading + error states** — every async surface has skeleton + error fallbacks following the existing UI conventions in `frontend/src/`.

### Out of scope
- Org-admin auth on the upgrade button (visible to all org members in v1; backend rejects non-admins with 403 in BL-PRD-05; UI hides the button if the backend returns "not allowed" → in BL-PRD-05).
- Manual override admin tool — BL-PRD-05.
- Sales-handoff actual destination (the form posts but the routing logic is BL-PRD-06).
- Reconciliation / finance dashboard surfaces — BL-PRD-06 (and likely deferred to a future release).
- Migrating the prototype out of `docs/figma-export/` into `frontend/` — this PRD assumes the production tab lives at `frontend/src/app/components/SubscriptionTab.tsx` (or wherever the production UI lives), with the prototype acting as the design reference.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)** | `/usage/current`, `/usage/daily`, `/internal/status/{org_id}`. | This component |
| **[BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)** | `/checkout-session`, `/subscription/change`, `/subscription/cancel`, `/customer-portal-session`. | This component |
| **Existing frontend** | `LayoutC.tsx` (banner mount point); `apiClient.ts` (402 interceptor); shared toast / dialog / form primitives. | `frontend/CLAUDE.md` |
| **[CH-PRD-02](../../chat/projects/CH-PRD-02-chat-page-shell-and-sidebar.md)** | **Hard upstream prerequisite** — creates `frontend/src/components/chat/ChatInterface.tsx`, which BL-PRD-04 modifies to add the chat-input disabled state when `useOrgStatus().status != "active"`. CH-PRD-02 ships in R1; BL-PRD-04 (in R3) consumes the file already on `main`. | [`../../chat/README.md`](../../chat/README.md) |
| **Pricing-tier JSON** | `shared/billing/pricing-tiers.v1.json` consumed by both backend (via `/pricing-tiers`) and frontend (slider). The prototype's hardcoded constants are removed in favor of the API. | This component |
| **Frontend BFF** (existing) | Proxy endpoint `/bff/billing/status/{org_id}` that wraps the OIDC-authed internal endpoint. (If no BFF pattern exists, a thin Cloud Run-side route handler does the proxy.) | TBD per architecture |
| **Sales-handoff endpoint** | `POST /api/v1/billing/{org_id}/sales-handoff` — contract defined here, implementation in BL-PRD-06. UI ships against the contract. | BL-PRD-06 |

## 4. Data contract

### Frontend type imports

The frontend re-exports backend types through a generated TypeScript client. New types consumed:

```ts
type BillingProfile = {
  plan: "free" | "paid" | "enterprise_invoice";
  current_tier_stop_index: number | null;
  monthly_token_allowance: number;
  billing_email: string;
  stripe_subscription_id: string | null;
};

type UsageCurrent = {
  tokens_used: number;
  allowance: number;
  period_start: string;       // ISO
  period_end: string;
  status: OrganizationStatus["status"];
};

type UsageDailyRow = {
  date: string;               // YYYY-MM-DD
  tokens: number;
  account?: string;           // present when breakdown=account|user
  user?: string;              // present when breakdown=user
};

type PricingTier = {
  stop_index: number;
  monthly_price_usd: number;
  monthly_token_allowance: number;
};

type OrganizationStatus = {
  status: "active" | "approaching_limit" | "inactive_overage" | "inactive_past_due" | "inactive_canceled";
  reason_message: string;
  updated_at: string;
};
```

### Sales-handoff request body (contract)

```ts
type SalesHandoffRequest = {
  estimated_monthly_tokens: number;       // integer; UI validates ≥81_000_000
  billing_contact_email: string;
  anticipated_start_date: string | null;  // ISO date
  notes: string;                          // ≤2000 chars
};
```

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create (or move from figma-export) | `frontend/src/app/components/SubscriptionTab.tsx` — production-wired version |
| Create | `frontend/src/app/hooks/useBillingProfile.ts` |
| Create | `frontend/src/app/hooks/useUsageCurrent.ts` |
| Create | `frontend/src/app/hooks/useUsageDaily.ts` |
| Create | `frontend/src/app/hooks/usePricingTiers.ts` |
| Create | `frontend/src/app/hooks/useOrgStatus.ts` — polls + focus-refresh; shared across banner / chat-input / slider |
| Create | `frontend/src/app/components/OrganizationStatusBanner.tsx` |
| Create | `frontend/src/app/components/SalesHandoffForm.tsx` |
| Create | `frontend/src/app/components/CancelSubscriptionDialog.tsx` |
| Consume | UI-PRD-01's `LayoutC.tsx` `bannerSlot` outlet — mount `OrganizationStatusBanner` into the slot via the existing render-prop / context API. **No `LayoutC.tsx` modification required** — the slot was reserved by UI-PRD-01 §2 specifically so banner consumers don't have to edit the layout. |
| Modify | `frontend/src/components/chat/ChatInterface.tsx` (created by CH-PRD-02) — disabled state when `useOrgStatus().status != "active"` |
| Modify | `frontend/src/app/lib/apiClient.ts` — 402 response interceptor |
| Create | `frontend/src/app/lib/billingApi.ts` — typed wrappers for every billing endpoint |
| Delete (after migration) | hardcoded `PRICING_BANDS` / `PRICING_STOPS` constants in figma-export prototype |
| Create | `frontend/tests/unit/billing/SubscriptionTab.spec.tsx`, `OrganizationStatusBanner.spec.tsx`, `useOrgStatus.spec.ts`, `SalesHandoffForm.spec.tsx` |
| Create | `frontend/tests/integration/billing/upgrade-flow.spec.tsx` (mock Stripe redirect) |

### 5.2 Upgrade-flow user journey

```text
1. User opens Settings → Organization → Subscription.
2. SubscriptionTab fetches profile + usage + pricing-tiers + status (parallel).
3. User clicks "Upgrade Subscription".
   - If profile.plan == "free": dialog opens; CTA = "Confirm Upgrade".
   - If profile.plan == "paid": dialog opens with current tier preselected; CTA = "Confirm Plan Change".
4. User adjusts slider; dialog updates price + tokens + helper text in real time.
5. User clicks CTA.
   - "Confirm Upgrade" → POST /checkout-session → window.location.href = checkout_url.
   - "Confirm Plan Change" → POST /subscription/change → toast "Plan updated"; refetch profile + status; close dialog.
6. After Stripe Checkout: redirected to /settings/organization/subscription?status=success.
   - Tab detects query param → refetches profile + status → toast "Subscription active"; clears query param.
7. If user landed at the max stop and clicks "Contact Sales":
   - SalesHandoffForm opens inline.
   - On submit → POST /sales-handoff → toast "We'll be in touch within 1 business day"; sessionStorage debounce key set.
```

### 5.3 Inactive banner placement and copy

Mount in `LayoutC.tsx` between the top-nav row and the main content row. Banner is full-width, ~48px tall, color-coded:

```text
┌───────────────────────────────────────────────────────────────────┐
│ ⚠  Token limit exceeded — resets May 1, 2026.   [Manage subscription] │  inactive_overage (red)
├───────────────────────────────────────────────────────────────────┤
│ ⚠  Payment failed — update your card to continue. [Update payment] │  inactive_past_due (red)
├───────────────────────────────────────────────────────────────────┤
│ ⚠  Subscription canceled. Reactivate any time.   [Reactivate]    │  inactive_canceled (amber)
├───────────────────────────────────────────────────────────────────┤
│ ⓘ  You've used 75% of this month's tokens.       [Upgrade]       │  approaching_limit (amber, dismissable for the session)
└───────────────────────────────────────────────────────────────────┘
```

Copy is sourced from `OrganizationStatus.reason_message` (backend authority). The CTA destination is fixed by status: `inactive_past_due` → Customer Portal session; everything else → Subscription tab.

### 5.4 Chat input disabled state

```text
ChatInterface render:
  status = useOrgStatus()
  if status.status starts with "inactive":
    render disabled input area:
      icon + status.reason_message + "Manage subscription" link
    return
  else:
    render normal input
```

The `MessageList` continues to render as normal (history is always visible). Disabled state is purely about the *next* message.

### 5.5 402 interceptor

```ts
apiClient.interceptors.response.use(undefined, async (error) => {
  if (error.response?.status === 402) {
    // Force a status refresh so the banner appears within milliseconds, not seconds.
    queryClient.invalidateQueries(['orgStatus', currentOrgId]);
    if (!toastQueue.has('billing_inactive')) {
      toast({
        id: 'billing_inactive',
        title: 'Subscription required',
        description: error.response.data.reason,
        action: { label: 'Manage', href: '/settings/organization/subscription' },
      });
    }
  }
  throw error;
});
```

The toast is dedup'd by ID so 100 simultaneous 402s create one toast.

## 6. API contract (consumed)

This PRD ships no new API contracts; it consumes the contracts defined in BL-PRD-02 and BL-PRD-03. The sales-handoff form posts against the BL-PRD-06 contract:

| Method | Path | Defined by |
|---|---|---|
| `GET` | `/api/v1/billing/{org_id}/profile` | BL-PRD-01 (extended in BL-PRD-03 with paid fields) |
| `GET` | `/api/v1/billing/{org_id}/usage/current` | BL-PRD-02 |
| `GET` | `/api/v1/billing/{org_id}/usage/daily` | BL-PRD-02 |
| `GET` | `/api/v1/billing/pricing-tiers` | BL-PRD-01 |
| `POST` | `/api/v1/billing/{org_id}/checkout-session` | BL-PRD-03 |
| `POST` | `/api/v1/billing/{org_id}/subscription/change` | BL-PRD-03 |
| `POST` | `/api/v1/billing/{org_id}/subscription/cancel` | BL-PRD-03 |
| `POST` | `/api/v1/billing/{org_id}/customer-portal-session` | BL-PRD-03 |
| `POST` | `/api/v1/billing/{org_id}/sales-handoff` | BL-PRD-06 (contract here, impl there) |
| `GET` | `/bff/billing/status/{org_id}` | This PRD (BFF wrapping `/internal/billing/status/{org_id}`) |

## 7. Acceptance criteria

1. **Pricing slider sourced from API** — `usePricingTiers()` returns 41 stops; slider min/max/step derived from response; helper text adapts per current stop. No hardcoded pricing constants remain in the production frontend.
2. **Current Plan card reflects API state** — Free org shows "Free / $0/month / 500K"; paid org shows tier name / price / allowance / `Manage payment method` link.
3. **Usage bar reflects real usage** — color tier (teal / amber / red) calculated from API response; "resets on" date populated from `period_end`.
4. **Daily-usage chart fed by API** — month picker triggers refetch with new `from/to`; breakdown selector triggers refetch with new `breakdown`; loading skeleton displayed during fetch; empty / error states handled.
5. **Upgrade flow E2E (mock Stripe)** — slider → "Confirm Upgrade" → POST `/checkout-session` → redirect to mock checkout URL → on return, profile + status refetched → toast displayed → tab updated.
6. **Mid-cycle change flow E2E** — paid org → slider → "Confirm Plan Change" → POST `/subscription/change` → toast → tab updated without full reload.
7. **Cancel flow E2E** — "Cancel subscription" link → confirmation modal → POST `/subscription/cancel` → toast → cancel-pending state shown in Current Plan card.
8. **Customer Portal redirect** — "Manage payment method" → POST `/customer-portal-session` → redirect to returned portal URL.
9. **Sales-handoff form** — at max slider stop, form renders with the four fields; client validates `estimated_monthly_tokens >= 81_000_000`, valid email, notes ≤2000 chars; submit POSTs to `/sales-handoff`; success toast shows; sessionStorage debounce prevents resubmit within an hour.
10. **`useOrgStatus` polling** — verified 60s polling cadence + immediate refresh on tab focus + immediate refresh on Stripe-return query param.
11. **Inactive banner** — appears in `LayoutC` above page content for every `inactive_*` and `approaching_limit` status; copy + color match table in §5.3; CTA destination correct per status; banner disappears within 1s of status flipping back to `active` (status cache invalidation flow).
12. **Chat input disabled state** — when status is `inactive_*`, input area shows disabled state with `reason_message`; existing message history renders normally; toggling status to `active` re-enables input on next render.
13. **402 interceptor** — server-returned 402 triggers a single dedup'd toast; status refetched immediately; subsequent 402s in the same window don't stack toasts.
14. **Loading + error states** — every async hook has explicit loading skeleton and error fallback; tested via mocked failure paths.
15. **No regressions in figma-export prototype** — the prototype continues to render with mock data so it remains a usable design reference. (The production wiring lives in `frontend/`, not in `docs/figma-export/`.)

## 8. Test plan

### Unit
- Each hook: returns expected shape on success, error fallback, loading state.
- `OrganizationStatusBanner`: renders correct copy / color / CTA per status; null when status is `active`.
- `SubscriptionTab`: pricing slider math identical to prototype (regression on the tiered increments); plan-name rendering correct for `free`, `paid`, `enterprise_invoice`.
- `SalesHandoffForm`: client validation rejects under-81M values, invalid email, oversize notes.
- `apiClient` 402 interceptor: dedup behavior; status invalidate fires.

### Integration (jest + msw mocking the backend)
- Upgrade flow: slider → checkout → redirect → return → profile updated.
- Mid-cycle change: slider → confirm → toast → state update.
- Cancel: link → modal → cancel → state update.
- Customer Portal: link → session created → redirect.
- Sales handoff: form → submit → success toast.
- Banner appearance / disappearance across status transitions.
- Chat input disable / enable as status flips.

### Manual verification
- Dev: stand up backend in `BILLING_STRIPE_DRIVER=stub`; click through every flow in a browser; confirm banner / toast / chat-disabled visuals.
- Staging: real Stripe test mode; complete a real checkout from the UI; verify period of zero perceived staleness on return.
- Visual diff vs. figma-export prototype: capture screenshots; confirm pixel parity on the Subscription tab body (banner is net-new and not in the prototype).

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Status staleness on return from Stripe (banner disappears slowly) | Stripe success_url query param triggers immediate refetch; cache invalidation on the backend side runs synchronously in the webhook handler. Worst case 1–2s. |
| User opens two tabs and upgrades in one — banner stuck in the other | Cross-tab broadcast via `BroadcastChannel` API on status changes. Stretch in v1; if not shipped, the 60s poll catches it. |
| 402 interceptor + status refetch storm under sustained over-limit traffic | Toast dedup'd by ID; status refetch is queryClient.invalidate which collapses to one fetch per cache window. |
| `useOrgStatus` polling load on the BFF (60s × N tabs × M users) | Frontend caches per-org; backend caches 30s. Per-user polling traffic is bounded; well within capacity. |
| Banner mount in `LayoutC` displaces existing layout vertically | Banner is collapsible with smooth transition; `ChatPage` and other height-sensitive pages account for the additional ~48px (CSS variable `--banner-height` set conditionally). |
| Customer Portal opens in same tab → user loses Subscription tab context | Open in same tab (default); back-button returns to Subscription tab. Confirmed acceptable in design review of the prototype. |
| Sales-handoff form spam | Per-org sessionStorage debounce (1h) for v1; backend rate-limit in BL-PRD-05. |
| Production lives at a different file path than the prototype | Production wiring assumes `frontend/src/` paths; if production has migrated to a different structure, the file inventory adjusts. Spike before first commit confirms paths. |

### Open questions
- **Q:** Should the production tab be a port of the figma-export prototype, or a fresh build that consumes shared design primitives? → **Proposal:** port the prototype (it's been reviewed and signed off); refactor only what's necessary to consume real APIs and shared primitives.
- **Q:** Should the `approaching_limit` banner be dismissable for the session, or persistent? → **Proposal:** dismissable (session-scoped); reappears on next session. The `inactive_*` banners are NOT dismissable — they reflect a billing state, not a notification.
- **Q:** Banner placement vs. mobile bottom-nav — the figma-export uses a bottom-nav on mobile. Does the banner go above or below it? → **Proposal:** above content, below the top header on both desktop and mobile. Mobile bottom-nav is unaffected. Confirm in design review.
- **Q:** Should the upgrade dialog show a Stripe-provided proration preview before confirm (per BL-PRD-03 §9 Q3)? → Defer to v2 polish (out of scope for this PRD); confirm before launch.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md), [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)
- Parallel: [BL-PRD-05](./BL-PRD-05-failure-modes-permissions.md)
- Downstream: [BL-PRD-06](./BL-PRD-06-integration-testing-go-live.md)
- Design reference: `docs/figma-export/src/app/components/SubscriptionTab.tsx`, `docs/figma-export/src/app/layouts/LayoutC.tsx`
- Frontend conventions: `frontend/CLAUDE.md`
- CLAUDE.md rules in scope: C-2, C-4, C-5, C-6, C-7, C-8; T-2; G-2, G-3
