# BL-PRD-03 — Stripe Checkout + Subscription Lifecycle

**Status:** Not started
**Owner team:** Billing component team (backend)
**Blocked by:** [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)
**Parallel with:** [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md) — both depend only on BL-PRD-01
**Blocks:** BL-PRD-04, BL-PRD-05
**Estimated effort:** 6 days backend

---

## 1. Context

This project plugs Stripe into the foundation. It builds the Stripe Checkout session creation, the webhook handler with signature verification + idempotency, all six event handlers we care about, mid-cycle proration, scheduled-at-period-end downgrade and cancel, Stripe Tax, the past-due grace period, the payment-failure email, and the Stripe Customer Portal session for self-serve card updates.

Before this PRD, every paid plan was a placeholder. After, an org admin can complete a real Stripe Checkout (test mode in CI; live in prod) and see their `BillingProfile` flip to `paid` with the correct `current_tier_stop_index`, allowance, and Stripe Subscription ID — within seconds of the webhook firing.

The hardest correctness concern is webhook idempotency: Stripe retries failed deliveries with the same `event.id` for up to 3 days. Every handler must be idempotent against re-delivery, and the `billing_stripe_events` journal is the dedup mechanism. The hardest reliability concern is the upgrade-staleness UX: a user expects their plan to apply immediately after Stripe Checkout returns. We achieve this by invalidating the status cache on `checkout.session.completed` *and* by writing the new `BillingProfile.monthly_token_allowance` synchronously inside the same handler.

## 2. Scope

### In scope
- **`POST /api/v1/billing/{org_id}/checkout-session`** — body `{tier_stop_index}`. Server creates a Stripe Checkout Session in `subscription` mode with the matching Price ID, customer-prefilled, with `success_url` and `cancel_url` deep-linking back to the Subscription tab. Returns `{checkout_url}` for the frontend to redirect to. Auth deferred to BL-PRD-05; here, any authenticated user can call.
- **`POST /api/v1/internal/billing/stripe-webhook`** — Stripe-signed; handles event types `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`. Verifies signature against `stripe-webhook-secret-{env}`. Idempotent via `billing_stripe_events/{event.id}` journal. Returns 200 within 5s.
- **`POST /api/v1/billing/{org_id}/subscription/change`** — body `{tier_stop_index}`. For an existing subscription, calls `stripe.subscription.modify(...)` with `proration_behavior="create_prorations"`. Synchronously updates `BillingProfile.monthly_token_allowance` and `MonthlyUsageWindow.allowance_at_period_start` (mid-cycle upgrade raises this immediately so the user can keep working). Invalidates status cache.
- **`POST /api/v1/billing/{org_id}/subscription/cancel`** — calls `stripe.subscription.modify(cancel_at_period_end=True)`. Local state remains `paid` until the period ends; the `customer.subscription.deleted` webhook flips it to Free.
- **`POST /api/v1/billing/{org_id}/customer-portal-session`** — creates a Stripe Customer Portal session limited to **payment method update + invoice download only** (plan changes and cancellation are handled in-app, not in the portal — see `../implementation-plan.md` §10 Q8). Returns `{portal_url}`.
- **Stripe Tax enabled** — Checkout Sessions created with `automatic_tax: { enabled: true }`. US + EU minimum coverage; finance handles registration before launch.
- **Past-due grace period** — when `invoice.payment_failed` fires, set `status = "inactive_past_due"` only if `attempt_count >= 4` *or* `next_payment_attempt is null` (Stripe Smart Retries exhausted). Until then, status remains `paid`+`active` and the user keeps working. After grace exhaustion, banner appears + email + status flip; on `invoice.payment_succeeded` after recovery, flip back to `active` + invalidate cache + audit.
- **Payment-failure email** — sent via SendGrid (existing email service) on every `invoice.payment_failed`, not just exhaustion. Templated; deep-links to Customer Portal for card update.
- **Webhook handler resilience** — every handler wraps state mutations in a Firestore transaction; idempotency checked first by reading `billing_stripe_events/{event.id}`; writing the event row at the end of successful processing. On handler error, return 500; Stripe retries; idempotency ensures correctness.
- **Subscription change flow on upgrade after Free** — Free orgs don't have a `stripe_subscription_id`. The first paid checkout creates one via Checkout Session. Subsequent upgrades/downgrades use `subscription.modify`. The `change` endpoint detects "no subscription yet" and routes to checkout instead.
- **Audit entries** — `subscription_created`, `subscription_upgraded`, `subscription_downgraded`, `subscription_canceled`, `payment_succeeded`, `payment_failed` — all written via `write_billing_audit` with `actor_id="system:webhook"` and `metadata.stripe_event_id` for traceability.
- **Notifications** — `Payment Failed` (per failure event); `Subscription Updated` (on plan change taking effect).
- **Weave spans** — `billing.checkout_session_created`, `billing.webhook_received` (`{event_type, processing_latency_ms, idempotent_replay}`), `billing.subscription_change`, `billing.payment_outcome`.

### Out of scope
- Org-admin authorization on state-changing endpoints (via DM-PRD-07's `require_role(OrgRole.ADMIN, scope="org")`) — BL-PRD-05.
- Manual override admin endpoint — BL-PRD-05.
- Stripe API outage handling specifics (status decisions never call Stripe live) — BL-PRD-05.
- Sales handoff for >81M tokens — BL-PRD-06.
- Annual billing, promo codes, trials — non-goals (`../implementation-plan.md` §8).
- Frontend wiring of the upgrade button to this endpoint — BL-PRD-04 (this PRD ships the API contract).

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)** | `BillingProfile`, `OrganizationStatus`, `billing_stripe_events` collection, `StubStripe`, `write_billing_audit`, pricing-tier table with Stripe Price IDs. | This component |
| **[BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)** | `invalidate_status_cache(org_id)` so plan-change handlers can force the cache fresh. (Soft — if BL-PRD-02 hasn't shipped yet, the call is a no-op stub.) | This component |
| **Notifications** (existing) | `create_notification("Payment Failed", ...)` and `create_notification("Subscription Updated", ...)`. | Existing notifications service |
| **Email service** (existing) | SendGrid templated send for payment failure. Template ID stored in Secret Manager (`sm://billing-payment-failed-template-id-{env}`). | `api/CLAUDE.md` Email Service Setup |
| **Stripe (real account, test mode in CI)** | API key in `stripe-api-key-{env}`; webhook signing secret in `stripe-webhook-secret-{env}`; both populated by ops pre-launch. Stripe CLI used in CI to forward webhooks to the test environment. | Stripe Dashboard |
| **Cloud Run / API ingress** | Webhook endpoint must be publicly reachable + receive the raw request body for signature verification (no body parsing before sig check). | `api/src/kene_api/main.py` |

## 4. Data contract

### No new Pydantic shapes

This PRD uses only the shapes from BL-PRD-01. New behavior is encoded in handlers, not schemas. Two new fields appear in `BillingAuditEntry.metadata` by convention:

- `stripe_event_id`: the originating Stripe event for traceability
- `proration_invoice_id`: when a mid-cycle change generates a proration invoice

### Webhook idempotency journal

```text
billing_stripe_events/{event.id}:
  event_type: str                  # e.g. "customer.subscription.updated"
  received_at: datetime
  processed_at: datetime
  processing_outcome: Literal["success", "ignored", "error"]
  org_id: str | None               # resolved from the event payload
  notes: str                       # short human note: "upgraded tier 5 → tier 12"
```

Read at the start of every handler; if `processed_at` is set and `processing_outcome != "error"`, return 200 immediately (idempotent replay). Written at the end on success.

### Event handler routing

| Stripe event | Effect |
|---|---|
| `checkout.session.completed` | Resolve org from `client_reference_id`; set `BillingProfile.plan="paid"`, `current_tier_stop_index`, `stripe_subscription_id`, `monthly_token_allowance`; bump `MonthlyUsageWindow.allowance_at_period_start`; invalidate cache; audit `subscription_created`; notify `Subscription Updated`. |
| `customer.subscription.created` | Defensive duplicate of the above; handler is a no-op if `BillingProfile.stripe_subscription_id` already matches. |
| `customer.subscription.updated` | Re-derive `current_tier_stop_index` from the subscription's active price; if changed → audit `subscription_upgraded` or `subscription_downgraded` based on direction; update `monthly_token_allowance`; invalidate cache; notify. If `cancel_at_period_end` flipped, audit `subscription_canceled` (informational, not yet effective). |
| `customer.subscription.deleted` | Subscription period ended after a cancel. Set `plan="free"`, `current_tier_stop_index=null`, `stripe_subscription_id=null`, `monthly_token_allowance=500_000`; if current usage >500K → set `status="inactive_overage"`; invalidate cache; audit. |
| `invoice.payment_succeeded` | If status was `inactive_past_due` → flip to `active`; invalidate cache; audit `payment_succeeded`. |
| `invoice.payment_failed` | Audit `payment_failed`; send SendGrid email to `billing_email`; notify. If Smart Retries exhausted (`attempt_count >= 4` or `next_payment_attempt is null`) → set `status="inactive_past_due"`, reason "Payment failed; update card to continue"; invalidate cache. |

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/billing/stripe_client.py` — extend `StubStripe` with Subscription / CheckoutSession / Webhook surfaces; real-driver wiring of `stripe.checkout.Session.create`, `stripe.subscription.modify`, `stripe.billing_portal.Session.create`, `stripe.Webhook.construct_event` |
| Create | `api/src/kene_api/billing/checkout.py` — `create_checkout_session(org_id, tier_stop_index)` |
| Create | `api/src/kene_api/billing/subscription.py` — `change_subscription`, `cancel_subscription` |
| Create | `api/src/kene_api/billing/portal.py` — `create_customer_portal_session` (configured to disable plan-change features) |
| Create | `api/src/kene_api/billing/webhooks.py` — handler dispatch + idempotency journal |
| Create | `api/src/kene_api/billing/handlers/checkout_session_completed.py` |
| Create | `api/src/kene_api/billing/handlers/subscription_lifecycle.py` (created, updated, deleted) |
| Create | `api/src/kene_api/billing/handlers/invoice_payment.py` (succeeded, failed + grace logic) |
| Create | `api/src/kene_api/billing/email.py` — SendGrid wrapper for payment-failure template |
| Modify | `api/src/kene_api/routers/billing.py` — add `/checkout-session`, `/subscription/change`, `/subscription/cancel`, `/customer-portal-session`, `/internal/stripe-webhook` |
| Modify | `api/src/kene_api/main.py` — raw-body middleware for the webhook route (sig verification needs raw bytes) |
| Modify | `deployment/terraform/secret_manager.tf` — promote `stripe-api-key-{env}`, `stripe-webhook-secret-{env}`, `billing-payment-failed-template-id-{env}` from placeholder to populated |
| Modify | `deployment/terraform/firestore.tf` — TTL policy on `billing_stripe_events` (180 days; long enough for audit, short enough to bound) |
| Create | `api/tests/unit/billing/test_webhook_idempotency.py`, `test_checkout.py`, `test_subscription_change.py`, `test_grace_period.py` |
| Create | `api/tests/integration/billing/test_stripe_full_lifecycle.py` (Free → checkout → paid → upgrade → downgrade → cancel → Free) |
| Create | `api/tests/integration/billing/test_payment_failure_recovery.py` |
| Create | `api/tests/integration/billing/test_webhook_signature_verification.py` |
| Create | `docs/design/components/billing/runbooks/webhook-debugging.md` |

### 5.2 Checkout session flow

```text
create_checkout_session(org_id, tier_stop_index, requesting_user_id):
  1. Read BillingProfile for org.
  2. Look up TierStop by index from billing_pricing/v1; resolve stripe_price_id.
  3. Call stripe.checkout.Session.create(
       mode="subscription",
       customer=billing_profile.stripe_customer_id,
       line_items=[{price: stripe_price_id, quantity: 1}],
       client_reference_id=org_id,                        # resolved by webhook
       success_url=APP_BASE_URL + "/settings/organization/subscription?status=success",
       cancel_url=APP_BASE_URL + "/settings/organization/subscription?status=canceled",
       automatic_tax={"enabled": True},
       metadata={"org_id": org_id, "tier_stop_index": tier_stop_index, "actor_user_id": requesting_user_id},
     )
  4. Return {checkout_url: session.url}
```

`client_reference_id=org_id` is the canonical link; the webhook handler does not need to look up `metadata` to resolve.

### 5.3 Webhook handler skeleton

```text
POST /internal/billing/stripe-webhook:
  raw_body, signature = request.body(), request.headers["Stripe-Signature"]
  try:
    event = stripe.Webhook.construct_event(raw_body, signature, STRIPE_WEBHOOK_SECRET)
  except SignatureError:
    return 400 "invalid signature"

  existing = read billing_stripe_events/{event.id}
  if existing and existing.processing_outcome == "success":
    return 200 "idempotent replay"

  try:
    handler = HANDLERS.get(event.type)
    if not handler:
      write billing_stripe_events/{event.id} = {..., outcome: "ignored"}
      return 200
    org_id, notes = handler(event)
    write billing_stripe_events/{event.id} = {..., outcome: "success", org_id, notes}
    return 200
  except Exception as e:
    write billing_stripe_events/{event.id} = {..., outcome: "error", notes: str(e)[:500]}
    log.exception(...)
    return 500   # Stripe will retry
```

### 5.4 Customer Portal configuration

In the Stripe Dashboard (one-time setup, per env), the Customer Portal is configured with:

- **Payment methods**: enabled
- **Invoice history**: enabled
- **Subscription updates**: **disabled** (KEN-E in-app slider is the source of truth)
- **Subscription cancellation**: **disabled** (in-app cancel only)
- **Customer information updates**: enabled (email, address — important for Tax)

Configuration captured in `docs/design/components/billing/runbooks/stripe-portal-config.md` so a re-create from scratch is repeatable.

### 5.5 Past-due grace period logic

```text
on invoice.payment_failed:
  audit "payment_failed", metadata={..., attempt_count, next_payment_attempt}
  send_payment_failure_email(billing_profile.billing_email, ...)
  create_notification("Payment Failed", ...)
  if attempt_count >= 4 or next_payment_attempt is None:
    set OrganizationStatus.status = "inactive_past_due"
    set OrganizationStatus.reason_message = "Payment failed; update your card to continue"
    invalidate_status_cache(org_id)
    audit "status_changed", metadata={from: prior_status, to: "inactive_past_due", trigger: "payment_failure_exhausted"}
```

Stripe Smart Retries default schedule (3, 5, 7 days) means exhaustion at attempt 4 = ~15 days after the initial failure. Past-due window is therefore approximately 15 days. Configurable via `BILLING_PAST_DUE_ATTEMPT_THRESHOLD` env var (default 4) for env-specific tuning.

## 6. API contract

### Public

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/billing/{org_id}/checkout-session` | Body `{tier_stop_index}` → `{checkout_url}`. |
| `POST` | `/api/v1/billing/{org_id}/subscription/change` | Body `{tier_stop_index}` → 204. Errors: 400 if no active subscription (frontend should call checkout instead). |
| `POST` | `/api/v1/billing/{org_id}/subscription/cancel` | → 204. Schedules cancellation at period end. |
| `POST` | `/api/v1/billing/{org_id}/customer-portal-session` | → `{portal_url}`. |

### Internal

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/billing/stripe-webhook` | Stripe-signed; idempotent. Returns 200 quickly, errors trigger Stripe retry. |

All public routes are gated by `billing_enabled`. The webhook is unconditional — even with `billing_enabled=false` we accept events (so we don't lose state if the flag is toggled mid-month).

## 7. Acceptance criteria

1. **Free → paid via Checkout E2E** — test using `StubStripe`: org admin POSTs `/checkout-session` → server creates session → simulated `checkout.session.completed` webhook → org's `BillingProfile.plan == "paid"`, `current_tier_stop_index == requested`, `stripe_subscription_id` populated, `monthly_token_allowance` raised, `MonthlyUsageWindow.allowance_at_period_start` raised, status cache invalidated, `subscription_created` audit + `Subscription Updated` notification fired.
2. **Webhook signature verification** — request with invalid signature → 400; valid signature → handler runs.
3. **Webhook idempotency** — same `event.id` posted twice → second call short-circuits with 200 "idempotent replay"; state mutated exactly once.
4. **Mid-cycle upgrade with proration** — paid org POSTs `/subscription/change` to a higher tier → `stripe.subscription.modify` called with `proration_behavior="create_prorations"` → `customer.subscription.updated` webhook → allowance raised synchronously, `subscription_upgraded` audit, notification.
5. **Mid-cycle downgrade** — paid org POSTs `/subscription/change` to a lower tier → modify with `proration_behavior="none"` and `billing_cycle_anchor="now"` is **not** used; instead, schedule the change for end of period via `proration_behavior="none"`. Allowance does NOT decrease until `customer.subscription.updated` fires at period end.
6. **Cancel at period end** — paid org POSTs `/subscription/cancel` → `stripe.subscription.modify(cancel_at_period_end=True)` → `customer.subscription.updated` arrives with `cancel_at_period_end=true` → audit `subscription_canceled` (informational); plan still `paid`. At period end, `customer.subscription.deleted` arrives → plan `free`, allowance 500K, status `inactive_overage` if current usage >500K (else `active`).
7. **Customer Portal session** — POST returns a Stripe-issued URL; manual verification confirms portal shows payment + invoices only (no plan-change UI).
8. **Past-due grace period** — `invoice.payment_failed` with `attempt_count=1` → status remains `active`, email sent, notification fired; `attempt_count=4` → status `inactive_past_due`, banner copy correct, cache invalidated.
9. **Recovery from past-due** — after `inactive_past_due`, an `invoice.payment_succeeded` event flips status back to `active`, invalidates cache, writes audit.
10. **Stripe Tax enabled** — Checkout Session creation request asserted to include `automatic_tax={enabled: true}`.
11. **Webhook handler returns 500 on error → Stripe retry succeeds idempotently** — inject a transient Firestore error into a handler; assert 500; replay → 200 with state correctly applied.
12. **Pricing-tier resolution** — `/checkout-session` with an invalid `tier_stop_index` (e.g. -1, 41) → 400 with descriptive error.
13. **No subscription → change endpoint behavior** — paid endpoint called when `stripe_subscription_id is null` → 400 `{error: "no_active_subscription", hint: "use checkout-session to start a subscription"}`.
14. **Webhook raw-body preservation** — middleware verified to pass raw bytes to signature verification; structured-body parsing happens after verification.
15. **TTL on `billing_stripe_events`** — Terraform asserts 180-day TTL policy applied.

## 8. Test plan

### Unit
- `create_checkout_session`: correct Stripe params; bad tier_stop_index rejected.
- `change_subscription`: correct proration mode for upgrade vs downgrade; no-active-subscription branch.
- Webhook signature verification: valid, invalid, missing header.
- Each handler in isolation: idempotency journal read + write; correct audit shape; correct notification fan-out.
- Past-due threshold logic: `attempt_count=1` no flip, `attempt_count=4` flip, exhausted-via-`next_payment_attempt=null` flip.
- Customer Portal session: configuration ID resolved per env.

### Integration (uses `StubStripe`)
- Full lifecycle E2E (AC #1, #4, #5, #6): Free → checkout → paid → upgrade → downgrade scheduled → cancel → Free at period end.
- Idempotency replay (AC #3): every event type replayed, state unchanged.
- Past-due → recovery (AC #8 + #9).
- Webhook 500 → retry (AC #11) using a fault-injection middleware.

### Stripe-CLI integration tests (CI, test-mode account)
- Real Stripe CLI forwards webhooks to a CI-deployed instance; one full Free → paid → cancel cycle exercised against actual Stripe test mode. Catches divergence between `StubStripe` and the real SDK.

### Manual verification
- Dev: configure Stripe test-mode keys; run a real checkout in a browser; confirm paid state in Firestore; trigger a test failed payment via Stripe Dashboard; confirm grace period behavior.
- Customer Portal smoke test: create portal session, follow URL, confirm only allowed actions visible.
- Email rendering: trigger payment-failure email in dev, verify SendGrid template renders correctly.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Webhook signature secret leaked or rotated | Per-env secret; rotation runbook supports two valid secrets simultaneously for a 24h window (Stripe lets you have two webhook endpoints, or `construct_event` supports a list of secrets — use the latter). |
| `StubStripe` diverges from real Stripe SDK on edge case | Stripe-CLI integration test in CI catches divergence per release. Pinned SDK version. |
| Webhook handler slow → Stripe times out | Handlers complete in <2s p95 by design (Firestore writes only, no LLM calls); CI timing test. If we ever exceed 5s we offload to a background task and respond 200 immediately. |
| Mid-cycle upgrade leaves allowance ambiguous (raised in our system before Stripe charges) | Acceptable: we err in the customer's favor (give access immediately on `checkout.session.completed`); Stripe's invoice settles correctly. |
| Customer Portal accidentally enabled with cancel/plan-change | Configuration captured in runbook + checked at boot via Stripe API call asserting expected feature set. |
| Stripe outage: checkout creation fails | Surface a clear "Try again in a few minutes" UI. Status decisions never depend on a live Stripe call (gates read materialized `OrganizationStatus`), so existing customers are unaffected. |
| Free users abuse checkout-session creation (DoS via spam) | BL-PRD-05 adds rate limits + admin-only auth. v1 mitigation: rely on auth requirement that user is in the org. |
| Idempotency journal write fails after handler succeeds → next replay re-runs the handler | Each handler is itself idempotent against the underlying state (e.g. setting `BillingProfile.plan = "paid"` for a customer already on paid is a no-op). The journal is defense-in-depth; double-applying a handler does not corrupt state. |
| Currency mismatch (Stripe Customer in EUR, our prices in USD) | All Customers created with `currency="usd"` in BL-PRD-01; checkout enforces same currency. Multi-currency deferred (`../implementation-plan.md` §8). |
| Refund creating a credit balance the user doesn't see in our UI | Refunds are an ops process via Stripe Dashboard for v1; documented in `../implementation-plan.md` §8 + risk row in §9. Future PRD can surface credit balance in UI. |

### Open questions
- **Q:** Should `billing_email` on the `BillingProfile` be the source-of-truth, or should we sync from Stripe Customer.email on every webhook? → **Proposal:** Stripe is source-of-truth for `email` (since payment receipts go from Stripe); KEN-E syncs on every relevant event. Decide before BL-PRD-04 wiring.
- **Q:** Past-due threshold (`BILLING_PAST_DUE_ATTEMPT_THRESHOLD`) default 4 vs. industry-typical longer? → **Proposal:** 4 (≈15 days) for v1; revisit at BL-PRD-06 based on first month of customer behavior. Decide before launch.
- **Q:** Should we expose the proration preview to the user before they confirm an upgrade? Stripe provides `stripe.invoices.upcoming` for this. → **Proposal:** yes for v2 polish; v1 just shows the new monthly price and trusts Stripe to settle correctly. Out of scope here, flag for BL-PRD-04.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)
- Parallel: [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)
- Downstream: [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md), [BL-PRD-05](./BL-PRD-05-failure-modes-permissions.md)
- Stripe docs: [Checkout Sessions](https://stripe.com/docs/api/checkout/sessions), [Webhooks](https://stripe.com/docs/webhooks), [Customer Portal](https://stripe.com/docs/customer-management), [Smart Retries](https://stripe.com/docs/billing/revenue-recovery/smart-retries)
- Email service: `api/CLAUDE.md` Email Service Setup
- CLAUDE.md rules in scope: PY-1, PY-3, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4, C-7; T-3, T-4, T-5
