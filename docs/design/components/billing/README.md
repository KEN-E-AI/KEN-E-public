# Billing — Product Requirements Document

> **Linear Team:** [KEN-E] Billing
> **Last Updated:** 2026-04-23
> **Status:** Draft — substrate designed, PRDs scoped, not yet implemented
> **Backend payment provider:** Stripe (Checkout + Subscriptions + Customer Portal + Tax)

## 1. Overview

The Billing component is KEN-E's **monetization substrate**. It owns the subscription tiers, the per-organization Stripe relationship, the token meter (per account → rolled up to org), the monthly enforcement window, the upgrade/downgrade flow, and the org-status state machine that gates the rest of the product when an organization exceeds its allowance or fails payment. No other component talks to Stripe, decrypts payment artifacts, increments the token counter, or writes to `organizations/{org_id}/billing_profile`, `usage_windows`, or `status`.

Five facts shape the design. **Billing is org-scoped, not account-scoped** — one Stripe Customer + at most one active Stripe Subscription per organization; sub-accounts inherit and contribute to the org-level token total. **Free is "no Stripe Subscription"** — every org starts with a 500K monthly token cap and a placeholder Stripe Customer, with no Stripe product representing Free; paid plans are 41 distinct Stripe Prices that an upgrade swaps in. **The meter is internal; Stripe never sees tokens** — Stripe knows what the org pays per month and nothing else, which keeps Stripe's role minimal and avoids depending on Stripe's metered-billing reporting latency for enforcement. **Status enforcement is centralized** — chat, scheduled-task firing, and any LLM-consuming endpoint check `org.status` via `billing.check_status` (a 30-second cached read); when an org goes inactive (over-limit *or* past-due), every consumer fails fast with HTTP 402 and the same user-facing notification. **PCI scope is zero** — all card capture goes through Stripe Checkout (hosted) or Stripe Customer Portal; KEN-E backend never sees a card number, CVC, or full PAN, and a CI lint blocks Stripe SDK imports outside the allow-listed callsites.

A developer reading only this section should understand: this component owns the `billing_pricing/*`, `billing_stripe_events/*` (webhook idempotency journal), and per-org `billing_profile`, `usage_windows`, `accounts/{account_id}/usage_daily`, `status`, and `billing_audit` Firestore collections. It owns the `/api/v1/billing/*` user-facing surface and the `/api/v1/internal/billing/*` service-to-service + webhook surface. It owns the production Subscription tab in the Settings UI plus the global app-shell inactive banner and the chat-input disabled state. The Stripe Customer + Subscription lifecycle, the monthly reset, daily reconciliation, sales handoff for >$4,829 / 81M tokens, and the manual-override admin tool all live here. It ships across **6 project PRDs (BL-PRD-01 → BL-PRD-06)** and is required by the Agentic Harness (every LLM call hits `meter_increment` + `check_status`), Project Tasks / Automations (scheduled runs gated by status), and the production UI (Subscription tab + banner + chat-disabled state).

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Org creation                                                               │
│    create_billing_profile_for_org(org_id, owner_email)                      │
│      → stripe.Customer.create(...)        (placeholder, no payment method)  │
│      → BillingProfile(plan="free", allowance=500_000)                       │
│      → OrganizationStatus(status="active")                                  │
│      → write_billing_audit(event="profile_created")                         │
└─────────────────────────────────────────────────────────────────────────────┘

                          Token-meter increment (hot path)

┌─────────────────────────────────────────────────────────────────────────────┐
│  Agentic Harness LLM call                                                   │
│    1. billing.check_status(org_id)        (30s in-process cache)            │
│       └── if inactive_*: raise BillingInactiveError → 402                   │
│    2. provider.invoke(...)                (existing path)                   │
│    3. billing.meter_increment(org_id, account_id, user_id, tokens, trace_id)│
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  meter_increment (Firestore TX, distributed counter)                        │
│    1. read usage_windows/{YYYY-MM} + usage_daily/{YYYY-MM-DD} + status      │
│    2. dedup on trace_id (24h TTL)                                           │
│    3. window.tokens_used += tokens; daily.by_user[user_id] += tokens         │
│    4. if crossed 100% and status="active": flip → "inactive_overage"        │
│       elif crossed 75% and status="active": flip → "approaching_limit"      │
│    5. commit TX                                                             │
│    6. (post-TX) emit notification once per window; invalidate status cache  │
└─────────────────────────────────────────────────────────────────────────────┘

                                Stripe Checkout

┌────────────────┐  POST /checkout-session  ┌────────────────────────────────┐
│  Subscription  ├─────────────────────────►│  create_checkout_session       │
│  tab UI        │                          │   stripe.checkout.Session.create│
│  (BL-PRD-04)   │◄─{checkout_url}──────────┤   client_reference_id=org_id   │
└────────┬───────┘                          │   automatic_tax: enabled       │
         │ window.location.href             └─────────────────┬──────────────┘
         ▼                                                    │
   Stripe-hosted Checkout (PCI scope = zero)                  │
         │ user pays                                          │
         ▼                                                    │
┌─────────────────────────────────────────────────────────────▼──────────────┐
│  Stripe                                                                     │
│    sends webhook ─── checkout.session.completed                             │
│    sends webhook ─── customer.subscription.created                          │
│    sends webhook ─── invoice.payment_succeeded                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ (signed; retry on 5xx)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  POST /api/v1/internal/billing/stripe-webhook                               │
│    1. verify signature (primary, then secondary during rotation)            │
│    2. idempotency: read billing_stripe_events/{event.id}                    │
│       if already processed → return 200 (replay)                            │
│    3. dispatch handler:                                                     │
│         checkout.session.completed   → activate subscription                │
│         customer.subscription.updated → re-derive tier; audit; notify       │
│         customer.subscription.deleted → revert to Free; recompute status    │
│         invoice.payment_succeeded     → if past_due → active                │
│         invoice.payment_failed        → email; if attempts>=4 → past_due    │
│    4. write billing_stripe_events/{event.id} = {outcome: success}           │
│    5. invalidate_status_cache(org_id)                                       │
│    6. return 200 within 5s                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                            Monthly reset (scheduled)

┌────────────────────┐ 00:05 UTC, 1st of month ┌────────────────────────────┐
│  Cloud Scheduler   ├────────────────────────►│  POST /internal/monthly-reset│
└────────────────────┘                         │  (idempotent per YYYY-MM)   │
                                                └────────────┬───────────────┘
                                                             │
                                                             ▼
                                       for each org:
                                         create new MonthlyUsageWindow
                                         if status="inactive_overage" → "active"
                                         clear notification flags on prior window
                                         invalidate_status_cache(org_id)
                                         audit "status_changed"

                              Daily reconciliation

┌────────────────────┐ 03:00 UTC daily        ┌────────────────────────────┐
│  Cloud Scheduler   ├───────────────────────►│  reconcile_billing_meter.py │
└────────────────────┘                        └────────────┬────────────────┘
                                                           │
                                                           ▼
                            query Weave for prior-day LLM-consumption spans
                            sum per (org, account, user)
                            diff vs. usage_daily/* meter rows
                            if max drift > 0.5% → Slack alert
                            write billing_reconciliation/{date} report
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `shared/billing/pricing-tiers.v1.json` | **Single source of truth** for the 41 tier stops. Consumed by backend (`billing.pricing.load()`), frontend (slider), and the `migrate_billing_pricing.py` seed. Stripe Price IDs intentionally NOT in this file — joined per-env from Secret Manager. (BL-PRD-01) |
| `api/src/kene_api/models/billing.py` | `TierStop`, `BillingProfile`, `MonthlyUsageWindow`, `AccountUsageDaily`, `OrganizationStatus`, `BillingAuditEntry`. (BL-PRD-01) |
| `api/src/kene_api/billing/pricing.py` | Loads JSON; resolves env-specific Stripe Price IDs from Secret Manager. (BL-PRD-01) |
| `api/src/kene_api/billing/profile.py` | `create_billing_profile_for_org`, `get_billing_profile`, `get_or_create_status`. (BL-PRD-01) |
| `api/src/kene_api/billing/audit.py` | `write_billing_audit` — wraps DM-PRD-07's `write_audit`; lint rule blocks card substrings in `metadata`. (BL-PRD-01) |
| `api/src/kene_api/billing/stripe_client.py` | Stripe SDK wrapper + driver dispatch (`real` vs `stub`). The **only allowed Stripe-import callsite** along with the handlers below. (BL-PRD-01; extended BL-PRD-03) |
| `api/src/kene_api/billing/stub_stripe.py` | In-memory fake Stripe for dev/test. Selected via `BILLING_STRIPE_DRIVER=stub`. (BL-PRD-01; extended BL-PRD-03) |
| `api/src/kene_api/billing/_stripe_callsites.py` | Allow-list registry of files permitted to `import stripe`. CI lint enforces. (BL-PRD-05) |
| `api/src/kene_api/billing/meter.py` | `meter_increment(...)`, `check_status(...)`, `invalidate_status_cache(...)`. The hot-path API for the Agentic Harness. (BL-PRD-02) |
| `api/src/kene_api/billing/state_machine.py` | Pure transition functions; testable without Firestore. (BL-PRD-02) |
| `api/src/kene_api/billing/counters.py` | Distributed-counter read/write helpers (10-shard pattern). (BL-PRD-02) |
| `api/src/kene_api/billing/notifications.py` | `Approaching Token Limit`, `Token Limit Exceeded`, `Payment Failed`, `Subscription Updated` factories. (BL-PRD-02 + BL-PRD-03) |
| `api/src/kene_api/billing/exceptions.py` | `BillingInactiveError` — typed exception mapped to HTTP 402 by the API exception handler. (BL-PRD-02) |
| `api/src/kene_api/billing/checkout.py` | `create_checkout_session(org_id, tier_stop_index)`. (BL-PRD-03) |
| `api/src/kene_api/billing/subscription.py` | `change_subscription`, `cancel_subscription`. (BL-PRD-03) |
| `api/src/kene_api/billing/portal.py` | `create_customer_portal_session` — configured to expose payment + invoices only (no plan-change UI). (BL-PRD-03) |
| `api/src/kene_api/billing/webhooks.py` | Webhook handler dispatch + idempotency journal + multi-secret signature verification. (BL-PRD-03; rotation-secret support BL-PRD-05) |
| `api/src/kene_api/billing/handlers/checkout_session_completed.py` | (BL-PRD-03) |
| `api/src/kene_api/billing/handlers/subscription_lifecycle.py` | `created`, `updated`, `deleted`. (BL-PRD-03) |
| `api/src/kene_api/billing/handlers/invoice_payment.py` | `succeeded`, `failed` + grace-period logic. (BL-PRD-03) |
| `api/src/kene_api/billing/email.py` | SendGrid wrapper for payment-failure template. (BL-PRD-03) |
| `api/src/kene_api/billing/manual_override.py` | `credit_tokens`, `uplift_cap`, `force_downgrade`, `force_status` actions; mandatory `reason` audit. (BL-PRD-05) |
| (no Billing-specific permissions module) | Authorization uses DM-PRD-07's `require_role(OrgRole.ADMIN \| OrgRole.MEMBER, scope="org")` directly. (BL-PRD-05) |
| `api/src/kene_api/billing/rate_limit.py` | Firestore-backed sliding-window limiter for `/checkout-session`, `/sales-handoff`, etc. (BL-PRD-05) |
| `api/src/kene_api/billing/sales_handoff.py` | `/sales-handoff` handler — sends email + Slack webhook + audit. (BL-PRD-06) |
| `api/src/kene_api/billing/monthly_reset.py` | Reset-job entry point; idempotent per `YYYY-MM` via marker doc. (BL-PRD-02) |
| `api/src/kene_api/routers/billing.py` | All public + internal endpoints. (BL-PRD-01..03; permissions added BL-PRD-05) |
| `api/scripts/migrate_billing_pricing.py` | Seeds `billing_pricing/v1` from JSON + Stripe Price ID secret. (BL-PRD-01) |
| `api/scripts/migrate_billing_backfill.py` | Back-fills `BillingProfile` + Stripe Customer for existing orgs. Idempotent + dry-run mode. (BL-PRD-01) |
| `api/scripts/reconcile_billing_meter.py` | Daily Weave-vs-meter drift report. (BL-PRD-02) |
| `api/scripts/replay_billing_webhooks.py` | Operator tool to re-process `billing_stripe_events` for a date range. (BL-PRD-05) |
| `api/scripts/lint/check_stripe_imports.py` | CI lint enforcing the `_stripe_callsites.py` allow-list. (BL-PRD-05) |
| `frontend/src/app/components/SubscriptionTab.tsx` | Production wiring of the figma-export prototype. (BL-PRD-04) |
| `frontend/src/app/components/OrganizationStatusBanner.tsx` | Global app-shell banner mounted in `LayoutC.tsx`. (BL-PRD-04) |
| `frontend/src/app/components/SalesHandoffForm.tsx` | At-max-slider sales contact form. (BL-PRD-04) |
| `frontend/src/app/components/CancelSubscriptionDialog.tsx` | (BL-PRD-04) |
| `frontend/src/app/hooks/useBillingProfile.ts`, `useUsageCurrent.ts`, `useUsageDaily.ts`, `usePricingTiers.ts`, `useOrgStatus.ts` | TanStack Query hooks. `useOrgStatus` is the single source of truth for banner / chat-disabled / 402 invalidation. (BL-PRD-04) |
| `frontend/src/app/lib/billingApi.ts` | Typed wrappers for every billing endpoint. (BL-PRD-04) |
| `docs/design/components/billing/runbooks/` | `stripe-dev-setup.md`, `stripe-portal-config.md`, `webhook-debugging.md` (BL-PRD-03); `manual-override.md`, `stripe-outage-response.md`, `webhook-replay.md`, `webhook-secret-rotation.md` (BL-PRD-05); `rollout.md`, `rollback.md`, `finance-dashboard.md`, `customer-overbilled.md`, `webhook-outage.md`, `README.md` (BL-PRD-06). |

### 2.2 Data Flow

1. **Org creation (BL-PRD-01).** Existing org-creation flow calls `create_billing_profile_for_org(org_id, owner_email)` after committing the org doc. The hook creates a Stripe Customer (placeholder, no payment method), writes a `BillingProfile` (`plan="free"`, `allowance=500_000`, `stripe_subscription_id=null`), writes an `OrganizationStatus` (`active`), and emits a `profile_created` audit entry. On Stripe failure, the whole org-create operation aborts (billing profile is mandatory).
2. **LLM call meter + status check (BL-PRD-02).** Every LLM-consuming agent invocation in the Agentic Harness wraps the call with two billing helpers. Before the call: `billing.check_status(org_id)` reads `OrganizationStatus` from a 30-second in-process cache; if `inactive_*`, raises `BillingInactiveError` which the API layer maps to HTTP 402 with `{error: "billing_inactive", reason, upgrade_url}`. After the call: `billing.meter_increment(...)` opens a Firestore transaction touching the org's monthly counter, the account's daily counter (with a per-user breakdown for the chart), and (only on transition) the status doc. The increment is keyed on `trace_id` for 24-hour idempotency.
3. **Status state machine.** Transitions: `active` → `approaching_limit` (≥75%) → `inactive_overage` (≥100%); reverse only via monthly reset or upgrade. Two additional inactive states are owned by webhook handlers: `inactive_past_due` (after Stripe Smart Retries exhausted) and `inactive_canceled` (after `customer.subscription.deleted` arrives at period end). All flips invalidate the status cache so the next `check_status` reads fresh.
4. **Notifications (BL-PRD-02 + BL-PRD-03).** `Approaching Token Limit` fires once per window when usage crosses 75%; `Token Limit Exceeded` fires once when it crosses 100%. `Payment Failed` fires on every `invoice.payment_failed`. `Subscription Updated` fires on every plan transition. Per-window notification flags prevent duplicate firing across multiple increments in the same threshold band.
5. **Stripe Checkout (BL-PRD-03).** UI POSTs `/api/v1/billing/{org_id}/checkout-session` with `tier_stop_index`. Server resolves the Stripe Price ID for the chosen stop, creates a Stripe Checkout Session with `client_reference_id=org_id` and `automatic_tax.enabled=true`, returns `{checkout_url}`. UI redirects. User completes payment on Stripe-hosted page (no PCI exposure). Stripe redirects back to `/settings/organization/subscription?status=success`.
6. **Webhook handling (BL-PRD-03).** Stripe POSTs `/api/v1/internal/billing/stripe-webhook`. Handler verifies signature against `stripe-webhook-secret-{env}` (with two-secret rotation support per BL-PRD-05), checks `billing_stripe_events/{event.id}` for idempotency, dispatches to the per-event handler. Each handler runs in a Firestore transaction, mutates `BillingProfile` / `MonthlyUsageWindow` / `OrganizationStatus`, calls `invalidate_status_cache`, writes audit, optionally fires notification + email. Returns 200 within 5s; on error returns 500 and Stripe retries (handlers are idempotent against re-delivery).
7. **Mid-cycle change (BL-PRD-03).** Existing-paid POSTs `/subscription/change` with new `tier_stop_index`. Server calls `stripe.subscription.modify(proration_behavior="create_prorations")` for upgrades (immediate allowance bump); for downgrades, the change is scheduled at period end (no immediate allowance reduction; `customer.subscription.updated` arrives later and applies the change). Cache invalidated; audit written.
8. **Cancel + period rollover (BL-PRD-03).** `/subscription/cancel` calls `stripe.subscription.modify(cancel_at_period_end=True)`. Plan stays `paid` until period end; `customer.subscription.deleted` fires at rollover; handler sets `plan="free"`, `allowance=500_000`, recomputes status (if current usage >500K → `inactive_overage`).
9. **Past-due grace period (BL-PRD-03).** First `invoice.payment_failed` fires email + notification but keeps status `active`. Stripe Smart Retries default schedule runs (3, 5, 7 days). On exhaustion (`attempt_count >= 4` or `next_payment_attempt is null`), status flips to `inactive_past_due`. Recovery via `invoice.payment_succeeded` flips back to `active` and invalidates cache.
10. **Monthly reset (BL-PRD-02).** Cloud Scheduler hits `/internal/billing/monthly-reset` at 00:05 UTC on the 1st. Creates a fresh `MonthlyUsageWindow` for every org, snapshotting the current `BillingProfile.monthly_token_allowance` as `allowance_at_period_start`. For every org in `inactive_overage`, flips back to `active` and invalidates cache. Idempotent via per-period marker doc.
11. **Daily reconciliation (BL-PRD-02 + BL-PRD-06).** Cloud Scheduler hits `reconcile_billing_meter.py` at 03:00 UTC daily. Queries W&B Weave for the previous day's LLM-consumption spans, sums per `(org, account, user)`, diffs against `usage_daily/*` rows. On >0.5% drift, posts a Slack alert. Writes a per-day report under `organizations/{org_id}/billing_reconciliation/{date}`. The 30-day clean-reconciliation window is the launch acceptance gate for flipping `billing_enforce_limits=true`.
12. **Manual override (BL-PRD-05).** Internal staff hit `/internal/billing/{org_id}/manual-override` with one of `credit_tokens` / `uplift_cap` / `force_downgrade` / `force_status` plus a mandatory ≥20-character `reason`. Action executes; full prior-state snapshot captured in the `manual_override` audit entry. Used for refunds, incident response, customer goodwill.
13. **Sales handoff (BL-PRD-06).** When the user lands on the max slider stop ($4,829 / 81M), the form lets them request enterprise pricing. POSTs `/sales-handoff` with `{estimated_monthly_tokens, billing_contact_email, anticipated_start_date, notes}`. Server emails `sales@ken-e.ai`, posts to a Slack channel webhook, and writes an `enterprise_handoff_initiated` audit entry. Sales follows up; ops uses `manual_override` to set up custom invoice billing.

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Purpose |
|----------|--------|-------|---------|
| `/api/v1/billing/pricing-tiers` | GET | BL-PRD-01 | Public. Returns 41 tier stops without Stripe Price IDs. Cached server-side 5 min. |
| `/api/v1/billing/{org_id}/profile` | GET | BL-PRD-01 (extended BL-PRD-03) | Any org member. Current plan, allowance, billing email, payment-method summary. |
| `/api/v1/billing/{org_id}/usage/current` | GET | BL-PRD-02 | Any org member. This month's tokens used, allowance, status. |
| `/api/v1/billing/{org_id}/usage/daily?from=&to=&breakdown=none\|account\|user` | GET | BL-PRD-02 | Any org member. Daily aggregates feeding the chart. |
| `/api/v1/billing/{org_id}/checkout-session` | POST | BL-PRD-03 | **Org admin** (BL-PRD-05). Body `{tier_stop_index}` → `{checkout_url}`. Rate-limited 10/hour/org. |
| `/api/v1/billing/{org_id}/subscription/change` | POST | BL-PRD-03 | **Org admin** (BL-PRD-05). Mid-cycle plan change with proration. Rate-limited 20/hour/org. |
| `/api/v1/billing/{org_id}/subscription/cancel` | POST | BL-PRD-03 | **Org admin** (BL-PRD-05). Schedules cancellation at period end. |
| `/api/v1/billing/{org_id}/customer-portal-session` | POST | BL-PRD-03 | **Org admin** (BL-PRD-05). Returns Stripe Customer Portal URL (payment + invoices only). |
| `/api/v1/billing/{org_id}/sales-handoff` | POST | BL-PRD-06 (contract BL-PRD-04) | **Org admin** (BL-PRD-05). Routes to sales via email + Slack. Rate-limited 3/day/org. |
| `/api/v1/internal/billing/status/{org_id}` | GET | BL-PRD-01 (real impl BL-PRD-02) | OIDC. Returns `OrganizationStatus`. 30s in-process cache. Read on every gated request. |
| `/api/v1/internal/billing/meter-increment` | POST | BL-PRD-02 | OIDC. Body `{org_id, account_id, user_id, tokens, trace_id}`. Idempotent on `trace_id`. |
| `/api/v1/internal/billing/stripe-webhook` | POST | BL-PRD-03 | Stripe-signed; idempotent via `billing_stripe_events`. Multi-secret rotation support (BL-PRD-05). |
| `/api/v1/internal/billing/monthly-reset` | POST | BL-PRD-02 | Cloud Scheduler. Idempotent per `YYYY-MM`. |
| `/api/v1/internal/billing/{org_id}/manual-override` | POST | BL-PRD-05 | OIDC + internal-staff allow-list. Mandatory `reason` ≥20 chars. |
| `/bff/billing/status/{org_id}` | GET | BL-PRD-04 | Frontend BFF wrapping `/internal/billing/status/{org_id}` (no OIDC required from the browser). |

Schema source of truth: `api/src/kene_api/models/billing.py` (Pydantic), mirrored in `frontend/src/app/lib/billingApi.ts`. URL paths use kebab-case (`pricing-tiers`, `checkout-session`); Firestore paths use snake_case (`billing_pricing`, `usage_windows`).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `BillingProfile` | `api/src/kene_api/models/billing.py` | One per org. `plan` (`free`/`paid`/`enterprise_invoice`), `stripe_customer_id` (always populated), `stripe_subscription_id` (None on Free), `current_tier_stop_index`, `monthly_token_allowance`, `billing_email`. |
| `MonthlyUsageWindow` | Same | One per `(org, YYYY-MM)`. `tokens_used` (distributed counter), `allowance_at_period_start` (snapshotted; mid-cycle upgrades raise it), `notification_*_sent` flags. |
| `OrganizationStatus` | Same | Materialized status doc; **read-hot**. `status` Literal of 5 values; `reason_message` is the user-facing copy rendered in the inactive banner. Single source of truth for every gated decision. |
| `TierStop` | Same | One row of the pricing table. 41 stops in v1; Stripe Price ID joined per-env from Secret Manager. |
| `BillingAuditEntry` | Same | Lifecycle audit. `event` Literal includes `profile_created`, `subscription_*`, `payment_*`, `status_changed`, `manual_override`, `enterprise_handoff_initiated`. **No card substrings or PII beyond `user_id` ever in `metadata`** (lint-enforced). |
| `meter_increment(org_id, account_id, user_id, tokens, trace_id)` | `api/src/kene_api/billing/meter.py` | Hot-path increment. Single Firestore transaction; trace-id-idempotent (24h TTL); flips status synchronously when crossing 75% / 100%. |
| `check_status(org_id) → OrganizationStatus` | Same | 30s in-process cached read. Called on every LLM invocation, every scheduled-task fire, every gated endpoint. Cache invalidated by `invalidate_status_cache(org_id)` on every status mutation. |
| `BillingInactiveError` | `api/src/kene_api/billing/exceptions.py` | Typed exception raised by `check_status` when status starts with `inactive_`. API exception handler maps to HTTP 402 + structured body. |
| `create_checkout_session(org_id, tier_stop_index)` | `api/src/kene_api/billing/checkout.py` | Stripe Checkout Session creation. `client_reference_id=org_id` is the canonical link the webhook reads. |
| `stripe_client` driver dispatch | `api/src/kene_api/billing/stripe_client.py` | `BILLING_STRIPE_DRIVER=stub` selects `StubStripe` (default in dev/test); `=real` selects the Stripe SDK with key from Secret Manager. **Production refuses to boot if `=stub`.** |
| `StubStripe` | `api/src/kene_api/billing/stub_stripe.py` | In-memory fake Stripe — Customer / Subscription / CheckoutSession / Webhook surfaces. Lets every test run hermetically without a Stripe account. |
| `require_role(min_role, scope="org")` (DM-PRD-07) | `api/src/kene_api/dependencies/rbac.py` | FastAPI `Depends` from DM-PRD-07 enforcing org-role auth on Billing's state-changing endpoints. 403 with structured body on rejection. Billing does not maintain its own role middleware. |
| `write_billing_audit(...)` | `api/src/kene_api/billing/audit.py` | Wraps DM-PRD-07's `write_audit`. Lint rule blocks card substrings in `metadata`. |
| `useOrgStatus()` | `frontend/src/app/hooks/useOrgStatus.ts` | Single frontend source of truth for org status. Polls `/bff/billing/status/{org_id}` every 60s + on tab focus + on Stripe-return query param. Drives the banner, chat-disabled state, and 402 interceptor. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[Data Management — DM-PRD-00 (Migration Foundation)](../data-management/projects/DM-PRD-00-migration-foundation.md)** | **Hard prerequisite for BL-PRD-01.** Shape B convention + `migrate_to_shape_b.py` + `_migrate_shape_b/resources.py` registry. Billing lands its new subcollections (`organizations/{org_id}/billing_profile`, `usage_windows`, `accounts/{account_id}/usage_daily`, `status`, `billing_audit`) via this framework. | `../data-management/README.md` §2.2 |
| **[Data Management — DM-PRD-07 (Approval Workflow & Audit)](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)** | **Hard prerequisite for BL-PRD-01.** `AuditEntry` schema + `write_audit(actor_id, event, ...)`. Billing subclasses into `BillingAuditEntry`. | `../data-management/README.md` audit section |
| **[Feature Flags — FF-PRD-01](../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md)** | **Hard prerequisite.** Three flags: `billing_enabled` (master kill switch), `billing_enforce_limits` (separate enforcement gate so observe-only mode works), `billing_show_subscription_ui` (gates the Subscription tab visibility). | `../feature-flags/README.md` |
| Existing org-creation flow | Single hook insertion — calls `create_billing_profile_for_org(org_id, owner_email)` after the org doc commits. Spike required to confirm where this lives today. | `api/src/kene_api/routers/organizations.py` |
| Org role model (DM-PRD-07) | `organizations/{org_id}/members/{user_id}.role` (`OrgRole`). Read by DM-PRD-07's `require_role` dependency. | `../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md` §4.1 |
| Existing notification system | `create_notification(category, org_id, user_ids, ...)`. Four new categories: `Approaching Token Limit`, `Token Limit Exceeded`, `Payment Failed`, `Subscription Updated`. | `api/src/kene_api/notifications/` |
| Existing email service (SendGrid) | Templated send for payment failure (BL-PRD-03) and sales handoff (BL-PRD-06). Templates stored in Secret Manager (`billing-payment-failed-template-id-{env}`, `billing-sales-handoff-template-id-{env}`). | `api/CLAUDE.md` Email Service Setup |
| **W&B Weave tracing** (existing) | `docs/trace-structure-spec.md` already captures token counts on LLM-call spans. Reconciliation reads from Weave's exported span store. The meter increment is a *sibling* of Weave span emission, not a downstream consumer — so a Weave outage cannot un-bill a customer. | `docs/trace-structure-spec.md` |
| GCP Secret Manager | Per-env: `stripe-api-key-{env}`, `stripe-webhook-secret-primary-{env}`, `stripe-webhook-secret-secondary-{env}` (rotation), `stripe-price-ids-{env}` (map of `stop_index → stripe_price_id`), `billing-payment-failed-template-id-{env}`, `billing-sales-handoff-template-id-{env}`, `billing-sales-handoff-slack-{env}`, `billing-reconciliation-slack-{env}`. | `deployment/terraform/secret_manager.tf` |
| GCP Cloud Scheduler | Two cron jobs per env: `billing-monthly-reset` (`0 5 1 * *`), `billing-daily-reconciliation` (`0 3 * * *`). Both OIDC-authed. | `deployment/terraform/cloud_scheduler.tf` |
| GCP Cloud Run / API ingress | Webhook endpoint must be publicly reachable + receive raw request body for signature verification (no JSON parsing before sig check). | `api/src/kene_api/main.py` |
| GCP BigQuery (BL-PRD-06) | `billing_kpis_v1` SQL view federating Firestore export → MRR / churn / conversion / refunds. Powers the finance Looker Studio dashboard. | `deployment/terraform/bigquery.tf` |
| **Stripe** (external) | One Stripe account per environment. 41 Prices (one per tier stop) created manually pre-launch via `runbooks/stripe-dev-setup.md`. Stripe Tax enabled per-region. Customer Portal configured per `runbooks/stripe-portal-config.md` (payment + invoices only). | Stripe Dashboard |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **[Agentic Harness](../agentic-harness/README.md)** | **Every LLM-consuming agent invocation** wraps `billing.check_status` (pre-call) + `billing.meter_increment` (post-call). On `BillingInactiveError`, the runtime refuses with a typed exception that the API layer maps to HTTP 402. The integration is one helper at the LLM-call site — see `app/adk/agents/...`. The hook is the single place tokens are metered for chat (no global middleware that double-counts). |
| **[Project Tasks](../project-tasks/README.md) + [Automations](../automations/README.md)** | `TaskOrchestrator` calls `billing.check_status(org_id)` before firing any scheduled run. On `inactive_*`, the run is skipped, the task is marked `skipped_billing`, and a notification fires (deduped per day to avoid spam). |
| **[Data Pipeline](../data-pipeline/README.md)** | Deterministic platform-API extraction jobs **do not count** against the token meter (zero LLM tokens consumed). They continue running while an org is inactive. Intentional — data freshness shouldn't lapse with paused chat. Flagged as `implementation-plan.md` §10 Q3. |
| **[UI](../ui/README.md)** | Subscription tab (BL-PRD-04) lives in the production frontend; figma-export prototype is the design contract. Global app-shell `OrganizationStatusBanner` mounted in `LayoutC.tsx`. `ChatInterface` renders the disabled state when `useOrgStatus().status` is `inactive_*`. The 402 response interceptor in `apiClient.ts` triggers a status refetch + dedup'd toast. |
| **[Performance / Setup Wizard](../performance/README.md)** | If a customer's wizard requires an LLM-driven step and the org is inactive, the wizard surfaces the same banner copy and links to the Subscription tab. No direct billing dependency beyond `useOrgStatus()`. |
| **[Knowledge Graph](../knowledge-graph/README.md)** | Knowledge-graph reads/writes via the agent runtime, so they inherit the same `meter_increment` + `check_status` gating. No direct billing API surface required. |
| Engineering incident response | `manual_override` admin endpoint provides the break-glass path for credit-backs, cap uplifts, forced downgrades, and forced status flips during incidents. Mandatory `reason` audit on every action. Webhook replay tool + Stripe-outage runbook documented in `runbooks/`. |
| Finance team | `billing_kpis_v1` BigQuery view + Looker Studio dashboard surfaces MRR, churn, conversion, refunds. Daily reconciliation report scopes Stripe-vs-meter discrepancies. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| `docs/figma-export/src/app/components/SubscriptionTab.tsx` | Entire file | **Design contract for BL-PRD-04.** The production wiring is a port that consumes real APIs; visuals + slider math + chart spec are unchanged. |
| `docs/figma-export/src/app/layouts/LayoutC.tsx` | Banner mount point (above page content; below top nav); chat-disabled state in `ChatInterface` | When implementing BL-PRD-04's `OrganizationStatusBanner` and chat-disabled wiring. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui component library, branded types, TanStack Query patterns, toast / dialog / form primitives | Before adding any React component under `frontend/src/app/components/` for the Subscription tab. |
| UI-PRD-01's Settings-page tab pattern | Existing Settings shell | The Subscription tab follows the same pattern as Account / User / Organization settings. Match it. |

## 5. Project Index

The component's work is split across **6 project PRDs** under [`projects/`](./projects/). BL-PRD-01 is a strict prerequisite (the substrate). After BL-PRD-01, BL-PRD-02 (meter) and BL-PRD-03 (Stripe lifecycle) can run in parallel. BL-PRD-04 (UI) needs both. BL-PRD-05 (failure modes + permissions) depends only on BL-PRD-03 and runs in parallel with BL-PRD-04. BL-PRD-06 is the capstone — E2E + sales handoff + 30-day reconciliation + go-live playbook.

### 5.1 Dependency graph

```
DM-PRD-00 (Migration Foundation)  ─┐
DM-PRD-07 (Audit schema)          ─┤
FF-PRD-01 (Feature Flags)         ─┤
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   BL-PRD-01       │  Core model + Stripe foundation
                          │                   │  Stripe Customer per org, pricing JSON,
                          │                   │  StubStripe, back-fill migration
                          └─────────┬─────────┘
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
              ┌───────────────────┐   ┌───────────────────┐
              │   BL-PRD-02       │   │   BL-PRD-03       │
              │ Token meter +     │   │ Stripe Checkout + │
              │ monthly enforce   │   │ subscription      │
              │ (observe-only)    │   │ lifecycle + tax + │
              │                   │   │ past-due grace    │
              └─────────┬─────────┘   └─────────┬─────────┘
                        │                       │
                        └───────────┬───────────┘
                                    ▼
                          ┌───────────────────┐       ┌───────────────────┐
                          │   BL-PRD-04       │       │   BL-PRD-05       │
                          │ Subscription tab  │       │ Failure modes +   │
                          │ wiring + banner + │       │ permissions +     │
                          │ chat-disabled     │       │ outage + replay   │
                          └─────────┬─────────┘       └─────────┬─────────┘
                                    │                           │
                                    └─────────────┬─────────────┘
                                                  ▼
                                        ┌───────────────────┐
                                        │   BL-PRD-06       │
                                        │ E2E + sales       │
                                        │ handoff + finance │
                                        │ dashboard +       │
                                        │ rollout playbook  │
                                        └───────────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Core Model + Stripe Foundation](./projects/BL-PRD-01-core-model-stripe-foundation.md) | Billing / Backend | DM-PRD-00, DM-PRD-07, FF-PRD-01 | — | 4 days |
| 02 | [Token Meter + Monthly Enforcement](./projects/BL-PRD-02-token-meter-monthly-enforcement.md) | Billing / Backend + Agentic Harness (integration) | BL-PRD-01 | BL-PRD-03 | 5 days |
| 03 | [Stripe Checkout + Subscription Lifecycle](./projects/BL-PRD-03-stripe-checkout-subscription-lifecycle.md) | Billing / Backend | BL-PRD-01 | BL-PRD-02 | 6 days |
| 04 | [Subscription Settings UI Integration](./projects/BL-PRD-04-subscription-settings-ui-integration.md) | Billing / Frontend + thin backend | BL-PRD-02, BL-PRD-03 | BL-PRD-05 | 4 days |
| 05 | [Failure Modes + Permissions](./projects/BL-PRD-05-failure-modes-permissions.md) | Billing / Backend + Platform | BL-PRD-03 | BL-PRD-04 | 3 days |
| 06 | [Integration Testing + Sales Handoff + Go-Live](./projects/BL-PRD-06-integration-testing-go-live.md) | Billing + Frontend + Ops/Finance | BL-PRDs 01–05 | — | 4 days |

### 5.3 Cross-PRD coordination points

Four touchpoints need conscious coordination:

- **Meter accuracy gate (BL-PRD-02 → BL-PRD-04 enforcement flip).** BL-PRD-02 ships in observe-only mode — meter runs, status flips, notifications fire, but the API layer does not return 402. The enforcement flip (`billing_enforce_limits=true`) requires 30 consecutive nights of <0.5% reconciliation drift. Until the rollout playbook in BL-PRD-06 reaches its day-31 gate, `billing_enforce_limits` stays off in production. **The figma-export prototype includes the inactive banner / chat-disabled UX so customers see the same surface during early-access enforcement.**
- **Webhook idempotency contract (BL-PRD-03 ↔ Stripe SDK).** Every webhook handler must be safe to call N times with the same `event.id` — Stripe retries failed deliveries for up to 3 days. The dedup mechanism is `billing_stripe_events/{event.id}`; the *handler* is also independently idempotent at the state level. Any new webhook handler added later must satisfy both. The replay tool in BL-PRD-05 relies on this property to safely re-process date ranges.
- **Status cache invalidation (BL-PRD-02 ↔ BL-PRD-03).** The 30-second status cache means an upgrade webhook arriving 25 seconds after a 402-rejected request will not surface to the user for up to 5 more seconds unless the cache is explicitly invalidated. **Every BL-PRD-03 webhook handler that mutates `OrganizationStatus` MUST call `invalidate_status_cache(org_id)`.** The mid-cycle change endpoint also invalidates synchronously so the user's first post-upgrade chat goes through immediately.
- **PCI scope (BL-PRD-01 ↔ BL-PRD-03 ↔ BL-PRD-05).** The Stripe SDK can be imported only from files registered in `_stripe_callsites.py`. CI lint enforces. New Stripe-touching code requires a registry update + code review. The frontend has an equivalent eslint rule blocking `@stripe/stripe-js` imports outside the Subscription tab + Customer Portal redirect path. **No exception, ever, even for "just a quick admin tool".**

### 5.4 Recommended workflow

1. **Sprint 1:** BL-PRD-01 lands (4 days, backend). No downstream work possible — gate. Pre-launch: ops creates 41 Stripe Prices in dev test mode and writes the IDs to `stripe-price-ids-dev`.
2. **Sprint 2:** BL-PRD-02 (backend) and BL-PRD-03 (backend) run in parallel. Both ship behind `billing_enabled=true` + `billing_enforce_limits=false` in dev. BL-PRD-02's reconciliation script starts producing reports.
3. **Sprint 3:** BL-PRD-04 (frontend) and BL-PRD-05 (backend) run in parallel. Frontend ships against the unsecured BL-PRD-03 endpoints first; BL-PRD-05's `require_role(OrgRole.ADMIN, scope="org")` gate (via DM-PRD-07) layers on after. The 402 interceptor and inactive banner light up automatically once status enforcement works in dev.
4. **Sprint 4:** BL-PRD-06 capstone — E2E suite, sales handoff, finance dashboard, rollout playbook execution begins. Day 0 of the 30-day observe-only window starts. Verification report appended once the early-access cohort onboards a paying customer.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §4 Database, §6 Tooling Gates, §7 Git | Branded types (C-5), Pydantic (PY-2), context managers (PY-5), lint gates (G-1..G-3), conventional commits (GH-1). |
| `api/CLAUDE.md` | Firestore access patterns, Secret Manager integration, OIDC for internal endpoints, Email Service Setup | Before building the Stripe wrapper, webhook handler, manual-override endpoint, or any internal endpoint. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui, branded types, TanStack Query | Before building the Subscription tab production version. |
| [`./implementation-plan.md`](./implementation-plan.md) | Entire document, especially §10 open questions | Full component design narrative + 11 open questions with proposals (token definition, sales-handoff destination, Data Pipeline metering, grace period length, etc.). Reference while reviewing a project PRD if a decision feels implicit. |
| `docs/trace-structure-spec.md` | Sections describing LLM-call spans + token attributes | Before implementing the meter hook in BL-PRD-02 or the reconciliation script. The meter pulls token counts from the same provider response that Weave records — **alongside, not from, Weave**. |
| `docs/KEN-E-System-Architecture.md` | §1.6 Component Landscape — Billing row | Cross-component orientation. Will be updated to drop `[PLANNED]` tags during BL-PRD-06. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Entry dated BL-PRD-06 completion | Rationale for the org-scoped + Free-is-no-Stripe + meter-internal design. (To be authored during BL-PRD-06.) |

## 7. Conventions and Constraints

### 7.1 PCI scope = zero

- **Card data never touches KEN-E backend.** Stripe Checkout (hosted page) and Stripe Customer Portal are the only card-capture surfaces. Backend code never sees a card number, CVC, expiration, or full PAN.
- **Stripe SDK imports are allow-listed.** `_stripe_callsites.py` registers the files permitted to `import stripe`. CI lint (`check_stripe_imports.py`) fails the build on any unauthorized import. New callsites require a registry PR + code review.
- **Frontend equivalent:** eslint rule blocks `@stripe/stripe-js` imports outside the Subscription tab and the Customer Portal redirect path. Same enforcement model.
- **No card substrings in audit metadata.** Lint rule on `write_billing_audit` rejects metadata containing card-shaped digits or known Stripe object IDs that could leak via logs.

### 7.2 Webhook handler idempotency contract

Every webhook handler must satisfy two conditions:

1. **Journal-level idempotency:** the dispatcher reads `billing_stripe_events/{event.id}` first; if `processing_outcome == "success"`, return 200 immediately without invoking the handler.
2. **State-level idempotency:** even if the journal is bypassed (e.g. by the BL-PRD-05 replay tool), running the handler twice on the same event must not corrupt state. Setting `BillingProfile.plan = "paid"` on a customer already on paid is a no-op; flipping `OrganizationStatus.status` to its current value is a no-op; etc. Audit entries are written conditionally on actual state change.

This is checked by an integration test in BL-PRD-03 that replays every event type twice for every fixture customer.

### 7.3 Status cache invalidation contract

The 30-second status cache is the single optimization that makes `check_status` cheap enough to call on every request. **Every code path that mutates `OrganizationStatus` MUST call `invalidate_status_cache(org_id)` synchronously inside the same transaction or immediately after commit.** The list of mutators:

- `meter_increment` on threshold crossing (BL-PRD-02)
- `monthly_reset` per org reactivated (BL-PRD-02)
- All five Stripe webhook handlers (BL-PRD-03)
- `change_subscription` immediate proration path (BL-PRD-03)
- `manual_override` for `credit_tokens`, `uplift_cap`, `force_status` (BL-PRD-05)

Forgetting to invalidate manifests as "user upgraded but the inactive banner is still showing for up to 30s." The invariant is captured by an integration test in BL-PRD-05 that forces every mutator and asserts the cache is cleared.

### 7.4 Token definition

Per `implementation-plan.md` §10 Q1 + BL-PRD-02 ratification: a "token" for billing purposes is **input + output + reasoning tokens**, *exclusive* of the cached-input discount. Cached-token savings flow to KEN-E margin, not the customer. Tool-use tokens count as LLM tokens. Pure platform-API extraction (Data Pipeline) does not count.

The single point that extracts the count is the LLM-provider-response-to-int helper in `app/adk/...`. If a new LLM provider is added, the extraction logic for *that provider* updates; the meter contract itself stays stable.

### 7.5 Pricing tiers

- **41 stops in v1.** Hardcoded in `shared/billing/pricing-tiers.v1.json`. Validated by a unit test asserting monotonicity and band arithmetic.
- **Tiered increments**, not linear: 500K@$30 (up to $149/3M) → 1M@$60 (up to $509/9M) → 1.5M@$90 (up to $1,049/18M) → 2M@$120 (up to $2,129/36M) → 3M@$180 (up to $4,829/81M).
- **Stripe Price IDs are env-specific** and live in `stripe-price-ids-{env}` Secret Manager secrets. The migration joins JSON + secret to write `billing_pricing/v1`. This means dev / staging / prod each have their own 41 Stripe Prices; the JSON is identical.
- **Pricing-table changes are versioned.** A v2 ships as `pricing-tiers.v2.json` + `billing_pricing/v2`. Existing subscriptions stay on v1 (Stripe Price IDs are immutable in their reference); new subscribers see v2; UI shows a "Switch to new pricing" CTA when beneficial. Deferred per `implementation-plan.md` §10 Q11.

### 7.6 Permissions

Authorization rides on DM-PRD-07's `OrgRole` enum (`admin | member`) — Billing does not maintain a separate role enum. The earlier `owner / admin` distinction has been collapsed (see [BL-PRD-05 §1 Role-model decision](./projects/BL-PRD-05-failure-modes-permissions.md#1-context)).

| Endpoint class | Required role |
|---|---|
| Public reads (`/pricing-tiers`) | (public) |
| Org reads (`/profile`, `/usage/*`, `/bff/billing/status/{org_id}`) | `OrgRole.MEMBER` |
| Upgrade-class (`/checkout-session`, `/subscription/change`, `/sales-handoff`) | `OrgRole.ADMIN` |
| Cancel + payment-method (`/subscription/cancel`, `/customer-portal-session`) | `OrgRole.ADMIN` |
| Manual override | internal-staff allow-list only (super-admin / `@ken-e.ai`) |

Multi-admin orgs coordinate destructive actions out-of-band; the audit trail (DM-PRD-07's generalized `write_audit`) lets ops detect if a tighter cancel-protection tier becomes necessary later.

### 7.7 Observe-only rollout

- **`billing_enforce_limits=false` is the default for the first 30 production days.** Meter increments, status flips, and notifications all fire — but the API layer's 402 mapping is bypassed, so chat and scheduled tasks proceed normally.
- **Observe-only audit entries carry `metadata.observe_only=true`.** The reconciliation script and rollout playbook use this to differentiate hypothetical-from-real enforcement during the observe window.
- **Day 31 flips early-access cohort.** 10 design-partner orgs first, monitored for 30 more days, then GA. Full playbook in `runbooks/rollout.md`.
- **Rollback triggers** documented in `runbooks/rollback.md`: >2% reconciliation drift, >5 customer-reported billing complaints / day, Stripe webhook backlog >5 min. Rollback is `billing_enforce_limits=false` first; `billing_show_subscription_ui=false` if UI-side issue; `billing_enabled=false` only as a last resort (it disables `/internal/status` reads, which would default-fail consumers to inactive).

### 7.8 Manual override

- **Mandatory `reason` ≥20 characters** on every action. Audit captures the actor's `user_id`, the action, params, prior state, and reason.
- **Four actions:** `credit_tokens` (subtract from current window; reactivate if drops below limit), `uplift_cap` (raise current window's allowance for the rest of the month), `force_downgrade` (immediately end Stripe Subscription, revert to Free), `force_status` (set status + reason_message; used for incident response).
- **Internal-staff allow-list** is the only auth gate. Source TBD between auth-provider group claim and Firestore allow-list (`implementation-plan.md` §10 Q1 of BL-PRD-05).
- **No automated refunds.** Refunds are a `credit_tokens` manual override + a manual Stripe Dashboard refund, until and unless a future PRD ships a self-serve refund flow.

### 7.9 Firestore layout (Shape B + Shape C)

- `billing_pricing/v1` — Shape C (global, not org-scoped). Frozen config; bumped via new doc on v2.
- `billing_stripe_events/{stripe_event_id}` — Shape C. 180-day TTL policy. Idempotency journal.
- `organizations/{org_id}/billing_profile/profile` — Shape B singleton subcollection.
- `organizations/{org_id}/usage_windows/{YYYY-MM}` — Shape B. Created lazily on first usage in the period.
- `organizations/{org_id}/usage_windows/{YYYY-MM}/seen_traces/{trace_id}` — Shape B. 24-hour TTL. Trace-id idempotency for `meter_increment`.
- `organizations/{org_id}/accounts/{account_id}/usage_daily/{YYYY-MM-DD}` — Shape B. Created lazily.
- `organizations/{org_id}/status/current` — Shape B singleton subcollection. **Read-hot.**
- `organizations/{org_id}/billing_audit/{audit_id}` — Shape B. Composite index: `(event ASC, timestamp DESC)`.
- `organizations/{org_id}/billing_reconciliation/{date}` — Shape B. Daily report row.
- `billing_monthly_reset_marker/{YYYY-MM}` — Shape C. Per-period idempotency marker for the reset job.
- `billing_rate_limits/{org_id}/{endpoint}` — Shape B. Sliding-window event log; trimmed in-place.

### 7.10 Feature-flag structure

- **Component-level kill switches:** `billing_enabled` (master — public + UI endpoints; `/internal/status` is unconditional), `billing_enforce_limits` (separate gate so observe-only mode works), `billing_show_subscription_ui` (Subscription tab visibility, defaults off until BL-PRD-04 ready).
- **All three flags ship targeted-rollout-capable** so the BL-PRD-06 early-access cohort can be enabled as a flag-target group without a full GA flip.
- **`billing_enabled=false` defaults all gated endpoints to "active"** for downstream consumers (so disabling billing during an incident does not lock everyone out). The implementation in BL-PRD-02's `check_status` checks the flag first and returns `active` synthetic status if billing is disabled.

### 7.11 Standard shape for a project PRD in [`projects/`](./projects/)

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
- When BL-PRD-06 completes: remove [PLANNED] tags, update Status to "Active," append a Verification section (E2E results + 30-day reconciliation drift + first-paying-customer date) at the end of §7, and cross-link from DESIGN-REVIEW-LOG.
- When a new component starts using Billing (e.g., a new LLM-consuming surface): add a row under §3.2 Depended On By and verify the consumer follows the §7.3 status-cache invalidation contract (if it mutates status) and the §7.4 token definition (if it meters tokens).
- When a new pricing-table version (v2) ships: do NOT modify §7.5; instead add a paragraph documenting the v1→v2 transition and the per-subscription pinning behavior. Keep v1 details as the canonical reference until v1 has zero subscribers.
- When a new Stripe webhook event type is handled: update §2.3 (API contracts) and §7.2 (idempotency contract sweep).
- When a new manual-override action is added: update §7.8 with the new action + audit shape.
- When a new runbook is authored in runbooks/: link it from §2.1.
- When the rollout playbook reaches a milestone (early-access enabled, GA): update §7.7.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
