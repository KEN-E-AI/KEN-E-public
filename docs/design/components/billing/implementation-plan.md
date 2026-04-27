# Billing — Implementation Plan

**Status:** Draft — 2026-04-23
**Owner:** Billing component team (TBD)
**Proposed PRD prefix:** `BL-PRD-NN`
**Backend payment provider:** Stripe (Checkout + Subscriptions + Customer Portal + Tax)

---

## 1. What Billing is

The Billing component is KEN-E's **monetization substrate**. It owns the subscription tiers, the per-organization Stripe relationship, the token meter (per account → rolled up to org), the monthly enforcement window, the upgrade/downgrade flow, and the org-status state machine that gates the rest of the product when an organization exceeds its allowance or fails payment.

Five facts shape the design:

1. **Billing is org-scoped, not account-scoped.** An organization has one Stripe Customer and at most one active Stripe Subscription. Sub-accounts inherit the org's plan and contribute to its token total. This matches real-world buying behavior: the company pays, the marketing teams use.
2. **Free is "no Stripe Subscription."** Every org starts on Free with a 500K monthly token cap and no Stripe entity beyond a placeholder Customer. Paid plans correspond to one of N pre-modeled Stripe Prices; switching plans = updating the Subscription's price ID. There is no "Free" Stripe product.
3. **The meter is internal; Stripe never sees tokens.** Stripe knows what the org pays per month and nothing else. Token counts, rollup, monthly windows, and overage detection are all KEN-E concerns. This keeps Stripe's role minimal and avoids depending on Stripe's metered-billing reporting latency for enforcement.
4. **Status enforcement is centralized.** Chat, scheduled-task firing, and any LLM-consuming endpoint check `org.status` via one helper. When an org goes inactive (over-limit *or* past-due), every consumer fails fast with the same code path and the same user-facing notification.
5. **PCI scope is zero.** All card capture goes through Stripe Checkout (hosted page) or Stripe Customer Portal; KEN-E backend code never sees a card number, CVC, or full PAN. Webhooks deliver state changes; webhook signature verification is mandatory and idempotency is required because Stripe retries.

## 2. What exists today (before Billing)

This is a greenfield component. Today there is a hardcoded "Professional / $299" placeholder in the Settings UI and no payment processing anywhere in the codebase. The Subscription tab UX has been prototyped in `docs/figma-export/src/app/components/SubscriptionTab.tsx` (tiered slider, daily-usage chart, sales handoff above $4,829). That UX is the contract this plan delivers a real backend for.

| Upstream | What it gives us |
|---|---|
| **DM-PRD-00** (Migration Foundation) | Shape B convention + migration framework for new `billing_*` collections. |
| **DM-PRD-07** (Approval & Audit) | `AuditEntry` schema for billing-lifecycle events (subscription changes, refunds, manual overrides). |
| **Notifications** (existing) | New categories: `Approaching Token Limit`, `Token Limit Exceeded`, `Payment Failed`, `Subscription Updated`. |
| **W&B Weave tracing** (existing, see `docs/trace-structure-spec.md`) | Spans already emit token counts; the meter increments alongside span emission, not by re-querying Weave. |
| **Email service** (SendGrid, see `api/CLAUDE.md`) | Payment-failure and dunning emails. |
| **Feature Flags** (existing) | `billing_enabled` for staged rollout; `billing_kill_switch` for emergency cutover. |
| **GCP Secret Manager** | Stripe API keys, webhook signing secrets, per-env Price ID maps. |

## 3. Data model

### 3.1 Pydantic shapes

```python
class TierStop(BaseModel):
    """One row in the pricing table. Frozen config; ships in repo."""
    stop_index: int                          # 0..40 in v1; 0 = base paid tier
    monthly_price_usd: int                   # whole dollars, e.g. 29, 59, ..., 4829
    monthly_token_allowance: int             # e.g. 1_000_000, 1_500_000, ..., 81_000_000
    stripe_price_id_dev: str                 # populated per env via Secret Manager indirection
    stripe_price_id_staging: str
    stripe_price_id_prod: str

class BillingProfile(BaseModel):
    """One per organization. Created on org creation."""
    organization_id: str
    plan: Literal["free", "paid", "enterprise_invoice"]
    stripe_customer_id: str                  # always populated, even on Free (placeholder customer)
    stripe_subscription_id: str | None       # None on Free; set on paid
    current_tier_stop_index: int | None      # None on Free; 0..40 on paid
    monthly_token_allowance: int             # 500_000 on Free; tier value on paid; custom on enterprise
    billing_email: str
    created_at: datetime
    updated_at: datetime

class MonthlyUsageWindow(BaseModel):
    """One per (organization, calendar month). Created lazily on first usage."""
    organization_id: str
    period_start: datetime                   # first of month, 00:00 UTC
    period_end: datetime                     # first of next month, 00:00 UTC
    tokens_used: int                         # rolled-up sum across all accounts
    allowance_at_period_start: int           # snapshotted; mid-cycle upgrades raise it
    overage_triggered_at: datetime | None    # set when tokens_used first crosses allowance
    notification_75_sent: bool
    notification_exceeded_sent: bool

class AccountUsageDaily(BaseModel):
    """One per (account, day). Powers the daily-usage chart."""
    account_id: str
    organization_id: str
    date: date                               # UTC day
    tokens_used: int                         # daily sum
    by_user: dict[str, int]                  # user_id → tokens (for break-by-user chart)

class OrganizationStatus(BaseModel):
    """Materialized view; updated by the meter + webhook handlers. Read-hot."""
    organization_id: str
    status: Literal[
        "active",
        "approaching_limit",   # ≥75% allowance used
        "inactive_overage",    # exceeded allowance on Free or paid
        "inactive_past_due",   # Stripe payment failed beyond grace
        "inactive_canceled",   # subscription canceled, period ended
    ]
    reason_message: str                      # user-facing copy surfaced in the inactive banner
    updated_at: datetime

class BillingAuditEntry(BaseModel):
    audit_id: str
    organization_id: str
    actor_id: str                            # user_id, "system:webhook", "system:monthly_reset"
    event: Literal[
        "subscription_created", "subscription_upgraded", "subscription_downgraded",
        "subscription_canceled", "payment_succeeded", "payment_failed",
        "status_changed", "manual_override", "enterprise_handoff_initiated",
    ]
    timestamp: datetime
    metadata: dict                           # e.g. {from_tier: 5, to_tier: 12, stripe_event_id: "evt_..."}
```

### 3.2 Firestore layout (Shape B)

| Path | Purpose |
|---|---|
| `billing_pricing/v1` | Frozen pricing table (41 stops); seeded by migration. |
| `organizations/{org_id}/billing_profile` | Single doc; one per org. |
| `organizations/{org_id}/usage_windows/{YYYY-MM}` | Monthly aggregate; created lazily. |
| `organizations/{org_id}/accounts/{account_id}/usage_daily/{YYYY-MM-DD}` | Daily per-account aggregate. |
| `organizations/{org_id}/status` | Materialized status doc; read on every gated request. |
| `organizations/{org_id}/billing_audit/{audit_id}` | Lifecycle audit log. |
| `billing_stripe_events/{stripe_event_id}` | Idempotency journal — every webhook recorded; reprocessing is a no-op. |

The pricing table doc is config, not state — versioned by document name (`v1`, `v2`, ...) so that historical subscriptions reference a frozen tier definition even if we later change the slider.

### 3.3 Pricing tiers — single source of truth

The 41 tier stops are defined in a JSON file checked into the repo (`shared/billing/pricing-tiers.v1.json`) and consumed by:

- **Frontend** (`SubscriptionTab.tsx`): drives the slider stops, labels, and helper text.
- **Backend** (`api/src/kene_api/billing/`): validates upgrade requests, looks up Stripe Price IDs.
- **Migration** (`billing_pricing/v1` doc): seeded from the JSON at first deploy.

Stripe Price IDs are *not* in the JSON — they live per-environment in Secret Manager (`stripe-price-ids-{env}`) and are joined to the JSON at boot. This avoids checking dev/staging/prod IDs into the repo and avoids a stale-config failure mode where prod points at a dev Price.

### 3.4 Execution model

- **Deployment target:** colocated with the main API (FastAPI router). Webhook handler runs in the same process.
- **Token meter increment:** synchronous Firestore distributed-counter write, called from the same code path that emits a Weave token-usage span. The meter is a sibling of the span emission, not a downstream consumer of it — so an in-flight Weave outage never silently un-bills a customer. (Trace-id is included in the meter row for later reconciliation.)
- **Daily/monthly aggregation:** the per-call increment hits an account's *daily* counter and the org's *monthly* counter in a single Firestore transaction. No batch rollup job is needed for v1.
- **Status check:** `OrganizationStatus.status` is read on every gated request through a 30-second in-process cache (Redis-free). The cache is invalidated on overage detection and on every webhook that touches subscription state, so user-visible reactivation after an upgrade is sub-second.
- **Webhook handler:** receives Stripe events at `POST /api/v1/internal/billing/stripe-webhook`; verifies signature against `STRIPE_WEBHOOK_SECRET`; checks `billing_stripe_events/{event.id}` for idempotency; processes; writes the event doc. Returns 200 within 5s or Stripe retries.
- **Monthly reset:** Cloud Scheduler hits `POST /api/v1/internal/billing/monthly-reset` at 00:05 UTC on the 1st of every month. Idempotent: if already run for the month, no-op. Resets all `OrganizationStatus` docs whose status was `inactive_overage` back to `active`, creates the new `MonthlyUsageWindow`, and clears notification-sent flags.
- **Observability:** Weave spans for `billing.meter_increment`, `billing.status_check`, `billing.webhook_received`, `billing.subscription_change`. Cardinality bound by `organization_id_hash`.

## 4. API surface

### User-facing (subscription management)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/billing/{org_id}/profile` | Current plan, allowance, billing email, payment-method summary. |
| `GET` | `/api/v1/billing/{org_id}/usage/current` | This month's tokens used, allowance, status. |
| `GET` | `/api/v1/billing/{org_id}/usage/daily?from=&to=&breakdown=none\|account\|user` | Daily aggregates feeding the chart. |
| `GET` | `/api/v1/billing/pricing-tiers` | Public — returns the 41-stop table for the slider. |
| `POST` | `/api/v1/billing/{org_id}/checkout-session` | Body: `{tier_stop_index}`. Returns Stripe Checkout URL. Auth: org admin only (DM-PRD-07's `require_role(OrgRole.ADMIN, scope="org")`). |
| `POST` | `/api/v1/billing/{org_id}/subscription/change` | Body: `{tier_stop_index}`. Mid-cycle change for an existing subscription (proration). Auth: org admin only. |
| `POST` | `/api/v1/billing/{org_id}/subscription/cancel` | Schedules cancellation at period end. Auth: org admin only. |
| `POST` | `/api/v1/billing/{org_id}/customer-portal-session` | Returns a Stripe Customer Portal URL for card updates / invoice history. |
| `POST` | `/api/v1/billing/{org_id}/sales-handoff` | Body: `{estimated_tokens, contact_message}`. Routes to sales (CRM ticket + email). |

### Internal (service-to-service)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/billing/meter-increment` | OIDC. Body: `{org_id, account_id, user_id, tokens, trace_id}`. Atomic increment + status check + (if newly over) status flip + notification fan-out. |
| `GET` | `/api/v1/internal/billing/status/{org_id}` | OIDC. Cached 30s. Returns `OrganizationStatus`. |
| `POST` | `/api/v1/internal/billing/stripe-webhook` | Stripe-signed; idempotent. |
| `POST` | `/api/v1/internal/billing/monthly-reset` | Cloud Scheduler-triggered; idempotent per `YYYY-MM`. |

## 5. Interaction with existing + concurrent components

### 5.1 Agentic Harness

Every LLM-consuming agent invocation calls `billing.check_status(org_id)` before starting (a no-op cache hit on the hot path). On `inactive_*`, the runtime refuses with a typed exception that the API layer maps to HTTP 402 Payment Required + a structured error body the UI uses to render the inactive banner. After successful runs, the harness calls `billing.meter_increment(...)` with the token count from the LLM provider's response. This is the *only* place tokens are metered for chat — there is no global middleware that double-counts.

### 5.2 Project Tasks + Automations

The `TaskOrchestrator` checks `billing.check_status(org_id)` before firing any scheduled run. On `inactive_*`, it skips the run, marks the task as `skipped_billing`, and emits a notification (deduplicated per day to avoid spam during a long inactive period).

### 5.3 Data Pipeline

Deterministic platform-API extraction jobs (Google Ads, GA4, Meta) **do not count** against the token meter — they consume zero LLM tokens. They continue running while an org is inactive. This is intentional: data freshness shouldn't lapse just because an org's chat is paused. (Flagged as an open question; see §10.)

### 5.4 Notifications

Four new categories. All routed by Billing:

| Category | Trigger | Action |
|---|---|---|
| `Approaching Token Limit` | meter crosses 75% mid-month | one-shot per window |
| `Token Limit Exceeded` | meter ≥ 100% | one-shot per window; org goes inactive |
| `Payment Failed` | Stripe `invoice.payment_failed` webhook | sent to org owner; re-sent on each Stripe retry |
| `Subscription Updated` | upgrade / downgrade / cancel takes effect | informational |

### 5.5 UI

- The Subscription tab built in the figma-export becomes the production tab; pricing slider is fed by `/api/v1/billing/pricing-tiers`; chart by `/api/v1/billing/{org_id}/usage/daily`; "Upgrade Subscription" hits `/checkout-session` and redirects.
- A global app-shell banner appears whenever `organization.status != "active"`, with copy from `OrganizationStatus.reason_message` and a CTA deep-linking to the Subscription tab.
- The chat input is disabled with an inline explanation when status is inactive.

### 5.6 Feature Flags

Per-flag gating:

- `billing_enabled` — master switch; off in dev until BL-PRD-04 ships.
- `billing_enforce_limits` — separate kill switch for *enforcement* (so we can run the meter in observe-only mode for the first month and verify accuracy before turning gates on).
- `billing_show_subscription_ui` — gates the Subscription tab visibility.

### 5.7 Account / user lifecycle

- Org creation auto-creates a Stripe Customer (placeholder) and a Free `BillingProfile`.
- Org deletion deletes the Stripe Customer (which voids the Subscription), then deletes the local docs.
- User removal does not affect billing — only org owners can change subscription state, but billing is org-level.

## 6. Phasing

Six PRDs. Proposed prefix: `BL-PRD-NN`.

### BL-PRD-01 — Core model + Stripe foundation

**Delivers:** All Pydantic shapes; Firestore layout + migration; pricing-tier JSON committed to repo + `billing_pricing/v1` seed migration; per-env `stripe-price-ids-{env}` Secret Manager indirection; Stripe Customer creation on org creation (back-fill migration for existing orgs); `BillingProfile` defaults to Free; `StubStripe` service for dev/tests (deterministic in-memory fake of Customer / Subscription / Webhook). No real charges yet.

**Exit criteria:** every existing org has a `stripe_customer_id`; Free defaults applied; pricing-tier JSON unit-tested for monotonicity (price strictly increasing, tokens strictly increasing); `StubStripe` round-trips a fake checkout end-to-end.

**Blocked by:** DM-PRD-00, DM-PRD-07.

**Blocks:** BL-PRD-02, BL-PRD-03.

**Effort:** 4 days.

### BL-PRD-02 — Token meter + monthly enforcement

**Delivers:** `billing.meter_increment` hook wired into the Agentic Harness LLM-call path (alongside Weave span emission); `billing.check_status` helper + 30s in-process cache; `OrganizationStatus` materialized view + state machine (`active` ↔ `approaching_limit` ↔ `inactive_overage`); monthly-reset Cloud Scheduler job; daily/monthly counter writes via Firestore transactions; notifications for 75% + exceeded; observe-only mode (meter runs, status doesn't gate) controlled by `billing_enforce_limits` flag.

**Exit criteria:** meter accuracy ≥99.5% vs. Weave (reconciliation script); monthly reset runs idempotently in dev for two consecutive months without drift; in observe-only mode, no user-visible behavior changes; flipping `billing_enforce_limits` on causes a chat in an over-limit org to fail with 402 within 30s.

**Blocked by:** BL-PRD-01.

**Blocks:** BL-PRD-03, BL-PRD-04.

**Effort:** 5 days.

### BL-PRD-03 — Stripe Checkout + Subscription lifecycle

**Delivers:** `POST /checkout-session` endpoint creating a Stripe Checkout Session for the chosen tier; webhook handler with signature verification + idempotency journal; handlers for `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`; mid-cycle change endpoint with Stripe proration; downgrade scheduled at period end; cancel-at-period-end flow; Stripe Tax enabled (US + EU minimum); past-due grace period (7 days, configurable) before transitioning to `inactive_past_due`; payment-failure notification + email via SendGrid; Stripe Customer Portal session endpoint for self-serve card updates.

**Exit criteria:** Stripe test-mode E2E in CI: Free org → checkout → webhook → paid → upgrade → webhook → downgrade scheduled → cancel → revert to Free at period end. Webhook idempotency proven by replaying every event twice with no state drift. Failed payment transitions org to `inactive_past_due` after grace period.

**Blocked by:** BL-PRD-01, BL-PRD-02.

**Blocks:** BL-PRD-04, BL-PRD-05.

**Effort:** 6 days.

### BL-PRD-04 — Subscription Settings UI integration

**Delivers:** production wiring of the figma-export Subscription tab to real APIs; pricing slider sourced from `/api/v1/billing/pricing-tiers`; daily-usage chart fed by `/api/v1/billing/{org_id}/usage/daily` with the breakdown selector; "Upgrade Subscription" CTA invoking the checkout endpoint and redirecting to Stripe Checkout; "Manage payment method" deep-link to Stripe Customer Portal; sales-handoff form (>81M tokens) calling `/sales-handoff`; global app-shell inactive banner; chat input disabled state with structured reason message.

**Exit criteria:** a Free org owner can upgrade to a paid tier entirely self-serve in <2 minutes through the UI; a downgrade can be scheduled from the same page; the inactive banner appears within 30s of an over-limit event in production traffic.

**Blocked by:** BL-PRD-02, BL-PRD-03.

**Blocks:** BL-PRD-06.

**Effort:** 4 days.

### BL-PRD-05 — Failure modes + permissions

**Delivers:** org-admin authorization on every state-changing endpoint via DM-PRD-07's `require_role(OrgRole.ADMIN, scope="org")` (any org admin may upgrade/downgrade/cancel/handoff — the earlier owner/admin distinction is collapsed per BL-PRD-05 §1); `manual_override` admin endpoint (internal staff tool) for credit-back / temporary-uplift / forced-downgrade with mandatory `reason` audit field; Stripe API outage handling (transient errors don't lock customers out — gating decisions never depend on a live Stripe call, only on the materialized status doc); webhook replay tooling (re-process a date range from `billing_stripe_events`); rate-limit on `/checkout-session` and `/sales-handoff` (anti-abuse).

**Exit criteria:** Stripe outage simulation (`StubStripe` returns 503 for 10 minutes) causes zero false-inactive flips; non-admin org members attempting to upgrade get 403; manual override creates a `BillingAuditEntry` with reason captured.

**Blocked by:** BL-PRD-03.

**Blocks:** BL-PRD-06.

**Effort:** 3 days.

### BL-PRD-06 — Integration testing + sales handoff + go-live

**Delivers:** full E2E suite covering all six state-machine transitions; sales-handoff implementation (CRM ticket via existing integration *or* email-to-sales channel — pick in §10 Q9); production rollout playbook (observe-only meter for 30 days → enforce flag for early-access orgs → general availability); reconciliation report (Stripe invoices vs. local `BillingAuditEntry`); finance dashboard scaffolding (MRR, churn, conversion-from-Free) — minimum: a single SQL view + a Looker Studio link; runbooks for "customer says they were over-billed" and "Stripe webhook outage."

**Exit criteria:** verification report appended; reconciliation script reports zero discrepancies for 30 consecutive days; ≥1 paid customer onboarded end-to-end through the production UI without internal intervention.

**Blocked by:** BL-PRDs 01–05.

**Blocks:** —

**Effort:** 4 days.

## 7. Dependency graph

```
┌───────────────────┐       ┌───────────────────┐
│    DM-PRD-00      │       │    DM-PRD-07      │
│   (migration)     │       │  (audit schema)   │
└─────────┬─────────┘       └─────────┬─────────┘
          │                           │
          └─────────────┬─────────────┘
                        ▼
              ┌───────────────────┐
              │     BL-PRD-01     │  Core model + Stripe foundation
              └─────────┬─────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
  ┌───────────────────┐   ┌───────────────────┐
  │     BL-PRD-02     │   │     BL-PRD-03     │
  │ Meter + monthly   │   │ Stripe Checkout + │
  │ enforcement       │   │ subscription lifecycle
  └─────────┬─────────┘   └─────────┬─────────┘
            │                       │
            └───────────┬───────────┘
                        ▼
              ┌───────────────────┐       ┌───────────────────┐
              │     BL-PRD-04     │       │     BL-PRD-05     │
              │ Settings UI wiring│       │ Failure modes +   │
              │                   │       │ permissions       │
              └─────────┬─────────┘       └─────────┬─────────┘
                        │                           │
                        └─────────────┬─────────────┘
                                      ▼
                            ┌───────────────────┐
                            │     BL-PRD-06     │  E2E + sales handoff + go-live
                            └───────────────────┘
```

## 8. Non-goals

- **Per-account billing.** Billing is org-level only in v1. Accounts inherit. (Future: chargeback dashboards for finance teams that want internal cost-allocation, but no separate Stripe relationships.)
- **Annual billing / annual discount.** Monthly only. Adds Stripe Subscription Schedules + a discount story; defer.
- **Promo codes, coupons, referral credits.** Defer.
- **Trial period for paid tiers.** Free tier is the trial. Adds proration weirdness if shipped without care; defer.
- **Token roll-over.** Unused tokens expire at month-end. Clean monthly window keeps the meter and the UI honest.
- **Usage-based / pay-per-token billing.** Always tier-based; never charged per actual token used. Predictable bill is a feature.
- **Self-serve invoice billing.** v1 sales handoff is a CRM ticket / email; the actual invoice setup is manual on Stripe by ops staff. Full self-serve invoice flow deferred to a future BL-PRD-07.
- **Multi-currency.** USD only.
- **Billing for Data Pipeline platform-API costs.** Deterministic extraction jobs are not metered; we eat the per-API-call cost. Revisit if a customer hammers the pipeline; see §10 Q3.
- **Reseller / partner billing.** No marketplace, no agency-level rollup billing.
- **Automatic refunds.** Refunds are an ops process for v1 (admin uses the `manual_override` endpoint + a manual Stripe refund).

## 9. Risks

| Risk | Mitigation |
|---|---|
| Token-meter drift vs. Weave (consumer leak; we under-bill) | Daily reconciliation script (BL-PRD-02 exit criterion); 30-day observe-only window before enforcement. |
| Token-meter over-counts (we over-bill) | Idempotent increments keyed by `trace_id`; reconciliation report; manual-override path for credit-backs. |
| Stripe webhook delivery failure → state drift | `billing_stripe_events` idempotency journal + replay tooling (BL-PRD-05); webhook health alerting. |
| Stripe API outage prevents enforcement decisions | Status decisions are made from the materialized `OrganizationStatus` doc, never from a live Stripe call. Stripe outage degrades upgrade flow only, not active customers. |
| Webhook race: upgrade webhook arrives after a usage check denies a request | 30s status cache means worst-case 30s of false-inactive. Acceptable; documented in user-facing copy ("may take a moment to take effect after upgrade"). The `/subscription/change` endpoint also forces an immediate status-cache invalidate. |
| Mid-cycle proration confusion → "I paid but I see the wrong amount" | Stripe handles math; we surface Stripe's invoice preview before the user confirms an upgrade. |
| Customer exceeds limit while a chat is mid-stream | Active in-flight call completes; the meter increment that crosses the threshold flips status synchronously; the *next* call returns 402. |
| PCI scope creep — a developer adds a "let's collect card details ourselves" feature | Code-review gate; no card-handling libraries in `package.json`; lint rule blocking imports of `@stripe/stripe-js` outside the Subscription tab and the Customer Portal redirect. |
| Webhook signature secret leaked / rotated | Per-env `STRIPE_WEBHOOK_SECRET` in Secret Manager; rotation runbook; multi-secret support during rotation window. |
| Sole org admin leaves the company; no remaining admin to manage billing | Org-admin promotion via DM-PRD-07's member-CRUD API is the recovery path; super-admin (`@ken-e.ai`) can also use `/internal/billing/{org_id}/manual-override` to keep the org running while a new admin is appointed. |
| Free-tier abuse (creating many orgs to skirt the cap) | Email-domain heuristic + per-IP org-creation rate limit. Not a v1 blocker (KEN-E is invite-only at launch); revisit pre-GA. |
| "I want to upgrade *down* to Free mid-cycle" → Stripe credit balance | Cancel-at-period-end is the only downgrade-to-Free path; no mid-cycle credits. Documented in UI copy. |
| Time-zone confusion on monthly reset | Reset runs at 00:05 UTC; UI displays "Resets on {local-time formatted next-1st}". |

## 10. Open questions

These are the decisions that need a product call before PRDs are written.

1. **What counts as a "token"?** Input tokens, output tokens, cached input tokens, reasoning tokens (extended thinking), tool-use payloads? Stripe doesn't care, but the meter and the user-facing usage chart need a clear definition. Proposal: input + output + reasoning, *exclusive* of cached-input discount (we charge the un-cached price). Cached-token savings flow to KEN-E margin, not the customer. Decision needed.
2. **Sales-handoff destination.** §6 BL-PRD-06 needs to know: CRM ticket (HubSpot? Salesforce?), email to a `sales@ken-e.ai` distribution list, Slack channel webhook, or Calendly link? Cheapest v1 = email + Slack webhook. Most useful long-term = HubSpot ticket via the existing Integrations component (if HubSpot is connected at the org level — meta).
3. **Should Data Pipeline jobs count against the meter?** Currently planned: no. But a customer extracting a 90-day GA backfill across 12 properties does cost real money in Google API quota *and* Cloud Run minutes. Either: (a) accept it as a v1 cost, (b) cap pipeline-job run-rate per Free org, (c) introduce a separate "data refresh credits" meter. Decision needed before BL-PRD-04.
4. **Grace period for past-due.** Default proposal: 7 days. Some SaaS goes 14. Tradeoff: longer = more goodwill, more risk of bad debt.
5. **Notifications cadence on inactive orgs.** Once daily? Once on transition only? Risk of nag fatigue vs. risk of forgetting to upgrade.
6. **Org-admin authorization for billing (resolved).** With DM-PRD-07's `OrgRole = admin | member`, all state-changing billing actions (upgrade / downgrade / cancel / customer portal / sales handoff) require `OrgRole.ADMIN`. The earlier `owner` vs `admin` distinction is collapsed; see BL-PRD-05 §1 Role-model decision for rationale.
7. **Stripe Tax v. defer.** Proposal: enable in BL-PRD-03 (it's mostly a Stripe dashboard setting + a single API flag). Decision = how much manual tax work the finance team will accept v1.
8. **Customer Portal scope.** Stripe's hosted portal can do: card update, invoice download, plan change, cancellation. We probably want to *disable* plan change / cancellation in the portal so the in-app slider remains the source of truth (and so we capture intent in our own audit log). Decision: portal limited to card + invoices only?
9. **Sales-handoff output.** When the user submits the form at >81M tokens, what happens? Q2 covers the *channel*; this question is about the *content* — is the form data structured (tokens needed, billing contact, anticipated start date), or just a free-text "tell us more"? Determines BL-PRD-06 form fields.
10. **Refund policy.** For a customer who upgraded by mistake and used zero tokens, do we self-serve refund? Or always send to ops? Proposal: ops-only via `manual_override`. Documented in §8.
11. **Pricing-tier versioning.** When v2 of the pricing table ships (different stops, different prices), do existing subscriptions auto-migrate, stay on v1 forever, or get a UI prompt to opt in? Proposal: subscriptions stay on v1 (Stripe Price IDs are immutable in their reference); new subscribers see v2; UI shows "Switch to new pricing" CTA when beneficial. Big enough that it deserves its own future PRD.

## 11. Success criteria

- Stripe Checkout session creation → user-visible Stripe page in <3s p95.
- Webhook ingestion → Firestore write in <5s p95; Stripe never sees a 5xx more than once per 1k events.
- Token-meter accuracy ≥99.5% vs. Weave (daily reconciliation report).
- Self-serve upgrade rate ≥50% of paying customers (the rest land via sales-handoff).
- Status-flip latency on overage: <30s from the request that crosses the threshold to the next request being 402'd.
- Reactivation latency on upgrade: <5s from Stripe webhook receipt to the Subscription tab showing the new plan.
- Monthly reset runs successfully every 1st of month with zero manual intervention for 6 consecutive months post-launch.
- Zero PCI findings: card data never enters KEN-E backend logs, traces, or storage (verified by quarterly audit).
- Stripe outage of up to 1 hour: zero false-inactive flips; upgrade flow degrades gracefully with a "try again in a few minutes" message.
- Reconciliation discrepancy budget: <0.1% of monthly Stripe revenue unexplained by audit log after 30 days.
