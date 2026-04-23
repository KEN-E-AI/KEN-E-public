# BL-PRD-01 — Core Model + Stripe Foundation

**Status:** Not started
**Owner team:** Billing component team (backend)
**Blocked by:** [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md) (Shape B convention + migration framework), [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-audit.md) (`AuditEntry` schema + `write_audit` helper)
**Parallel with:** none — Billing is a fresh component
**Blocks:** BL-PRD-02, BL-PRD-03
**Estimated effort:** 4 days backend

---

## 1. Context

Billing is KEN-E's monetization substrate — Stripe-backed subscriptions, the org-level token meter, monthly enforcement windows, and the org-status state machine that gates the rest of the product on overage or payment failure. See [`../implementation-plan.md`](../implementation-plan.md) for the full component design.

This project lays the foundation: every Pydantic shape, the Firestore layout (Shape B), the pricing-tier JSON checked into the repo + seed migration, per-env Stripe Price ID indirection through Secret Manager, Stripe Customer creation on org creation (with a back-fill migration for existing orgs), Free-tier defaults applied to every `BillingProfile`, and a `StubStripe` service for dev/tests. No real charges happen here — checkout, webhooks, and metering land in BL-PRD-02 and BL-PRD-03. The validation checkpoint is that every existing org has a Stripe Customer ID, the pricing-tier table round-trips through the Stripe Price ID lookup, and a stubbed checkout completes end-to-end against `StubStripe`.

Landing the substrate first lets BL-PRD-02 (meter) and BL-PRD-03 (Stripe lifecycle) ship in parallel — both depend on the data model and the stub being in place.

## 2. Scope

### In scope
- **Pydantic models** for `TierStop`, `BillingProfile`, `MonthlyUsageWindow`, `AccountUsageDaily`, `OrganizationStatus`, `BillingAuditEntry` (shapes in §4).
- **Firestore layout** — new collections `billing_pricing/*`, `billing_stripe_events/*`, plus subcollections under `organizations/{org_id}/` for billing profile, usage windows, daily account usage, status, and audit. Terraform composite indexes where needed.
- **Pricing-tier JSON** — `shared/billing/pricing-tiers.v1.json` checked into the repo. 41 stops, monotonic price + tokens. Schema-validated by a unit test on every CI run.
- **Pricing-tier seed migration** — `api/scripts/migrate_billing_pricing.py` reads the JSON, joins the env-specific Stripe Price IDs from Secret Manager, and writes `billing_pricing/v1`.
- **Stripe Price ID indirection** — per-env Secret Manager secret `stripe-price-ids-{env}` holding a JSON map `{stop_index: stripe_price_id}`. Resolved at boot and at migration time; never checked into the repo.
- **Stripe Customer creation hook** — `create_billing_profile_for_org(org_id)` called from the org-creation flow (a one-line patch into the existing org-create code path). Creates a Stripe Customer (placeholder, no payment method), creates a `BillingProfile` with `plan="free"`, allowance 500K, and writes a `subscription_created`-style audit entry of `event="profile_created"`.
- **Back-fill migration** — `api/scripts/migrate_billing_backfill.py` iterates every existing org without a `BillingProfile`, runs the same hook, and reports counts. Idempotent.
- **`StubStripe` service** — deterministic in-memory fake of `stripe.Customer`, `stripe.checkout.Session`, `stripe.Subscription`, `stripe.Webhook`. Drives dev / unit / integration tests without a Stripe account. Selected via `BILLING_STRIPE_DRIVER=stub` env var (default in dev/test, never in staging/prod).
- **`BillingAuditEntry` + `write_billing_audit`** wrapper over DM-PRD-07's `write_audit`. Lifecycle events persisted under `organizations/{org_id}/billing_audit/{audit_id}`.
- **Internal status read endpoint** — `GET /api/v1/internal/billing/status/{org_id}` (OIDC). Reads `OrganizationStatus`. In BL-PRD-01 it always returns `active` since no metering exists yet; the endpoint exists so BL-PRD-02 has a contract to fill in.
- **Public pricing-tier endpoint** — `GET /api/v1/billing/pricing-tiers` returning the 41 stops (without Stripe Price IDs) for the figma-export slider to start consuming a real API.
- **Weave spans** — `billing.profile_created`, `billing.status_check`, `billing.pricing_tier_lookup`. Bounded cardinality by `organization_id_hash`.
- **Feature flags** — register `billing_enabled` (master switch, default off in dev), `billing_enforce_limits` (default off — observe-only), `billing_show_subscription_ui` (default off).

### Out of scope
- Token metering + counter writes — BL-PRD-02.
- Status state machine transitions (anything beyond `active`) — BL-PRD-02.
- Real Stripe Checkout / webhook handling — BL-PRD-03.
- UI wiring of the slider / chart / banner — BL-PRD-04.
- Owner-only authorization on state-changing endpoints — BL-PRD-05 (no state-changing endpoints exist yet).
- Sales-handoff form — BL-PRD-06.
- Multi-currency, annual billing, trials, promo codes — see `../implementation-plan.md` §8 non-goals.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)** | Shape B convention + `api/scripts/_migrate_shape_b/resources.py` registry. New subcollections under `organizations/{org_id}/` are registered via this framework. | `../../data-management/README.md` |
| **[DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-audit.md)** | `AuditEntry` schema + `write_audit` helper. `BillingAuditEntry` subclasses with billing-specific event Literals. | `../../data-management/README.md` audit section |
| Existing org-creation flow | Single hook insertion — calls `create_billing_profile_for_org(org_id)` after the org doc is committed. | `api/src/kene_api/routers/organizations.py` (or wherever org create lives today) |
| Secret Manager | Per-env secret `stripe-price-ids-{env}` (map of `stop_index → stripe_price_id`); per-env `stripe-api-key-{env}` (placeholder, populated in BL-PRD-03); per-env `stripe-webhook-secret-{env}` (placeholder, populated in BL-PRD-03). | `deployment/terraform/` |
| Stripe (dev account) | A Stripe test-mode account with the 41 Prices created (one per tier stop). The Price IDs are written into Secret Manager. Manual one-time setup; documented in §5.5. | Stripe Dashboard |
| Existing API auth | OIDC-authed internal endpoint pattern reused from Integrations. | `api/src/kene_api/auth/` |

## 4. Data contract

### Pydantic shapes

```python
class TierStop(BaseModel):
    """Frozen pricing-table row. Loaded from billing_pricing/v1."""
    stop_index: int                         # 0..40 (v1)
    monthly_price_usd: int                  # whole dollars; 29, 59, ..., 4829
    monthly_token_allowance: int            # 1_000_000 .. 81_000_000
    stripe_price_id: str                    # resolved from Secret Manager at load

class BillingProfile(BaseModel):
    organization_id: str
    plan: Literal["free", "paid", "enterprise_invoice"]
    stripe_customer_id: str                 # always populated
    stripe_subscription_id: str | None      # None on Free
    current_tier_stop_index: int | None     # None on Free; 0..40 on paid
    monthly_token_allowance: int            # 500_000 on Free; tier value on paid; custom on enterprise
    billing_email: str
    created_at: datetime
    updated_at: datetime

class MonthlyUsageWindow(BaseModel):
    organization_id: str
    period_start: datetime                  # first of month, 00:00 UTC
    period_end: datetime
    tokens_used: int                        # rolled-up sum across accounts
    allowance_at_period_start: int          # snapshotted; mid-cycle upgrades raise this
    overage_triggered_at: datetime | None
    notification_75_sent: bool
    notification_exceeded_sent: bool

class AccountUsageDaily(BaseModel):
    account_id: str
    organization_id: str
    date: date                              # UTC day
    tokens_used: int
    by_user: dict[str, int]                 # user_id → tokens

class OrganizationStatus(BaseModel):
    organization_id: str
    status: Literal[
        "active",
        "approaching_limit",
        "inactive_overage",
        "inactive_past_due",
        "inactive_canceled",
    ]
    reason_message: str
    updated_at: datetime

class BillingAuditEntry(BaseModel):
    audit_id: str
    organization_id: str
    actor_id: str                           # user_id or "system:<subtype>"
    event: Literal[
        "profile_created", "subscription_created", "subscription_upgraded",
        "subscription_downgraded", "subscription_canceled", "payment_succeeded",
        "payment_failed", "status_changed", "manual_override",
        "enterprise_handoff_initiated",
    ]
    timestamp: datetime
    metadata: dict                          # no card numbers, no PII beyond user_id
```

### Firestore layout (Shape B)

| Path | Purpose |
|---|---|
| `billing_pricing/v1` | Frozen pricing table (41 stops); seeded by migration |
| `billing_stripe_events/{stripe_event_id}` | Webhook idempotency journal (populated by BL-PRD-03; created here as an empty collection with index ready) |
| `organizations/{org_id}/billing_profile/profile` | Single doc per org |
| `organizations/{org_id}/usage_windows/{YYYY-MM}` | Created lazily by BL-PRD-02 |
| `organizations/{org_id}/accounts/{account_id}/usage_daily/{YYYY-MM-DD}` | Created lazily by BL-PRD-02 |
| `organizations/{org_id}/status/current` | Materialized status doc; default `{status: "active", reason_message: ""}` |
| `organizations/{org_id}/billing_audit/{audit_id}` | Lifecycle audit log |

### Pricing-tier JSON schema

```json
{
  "version": 1,
  "stops": [
    { "stop_index": 0, "monthly_price_usd": 29, "monthly_token_allowance": 1000000 },
    { "stop_index": 1, "monthly_price_usd": 59, "monthly_token_allowance": 1500000 },
    ...
    { "stop_index": 40, "monthly_price_usd": 4829, "monthly_token_allowance": 81000000 }
  ]
}
```

A unit test asserts: 41 stops, indices 0..40 contiguous, prices strictly increasing, tokens strictly increasing, every stop matches the band-arithmetic in `../implementation-plan.md` §1.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `shared/billing/pricing-tiers.v1.json` |
| Create | `api/src/kene_api/models/billing.py` — all Pydantic shapes |
| Create | `api/src/kene_api/billing/__init__.py` |
| Create | `api/src/kene_api/billing/pricing.py` — JSON load + Stripe Price ID join from Secret Manager |
| Create | `api/src/kene_api/billing/profile.py` — `create_billing_profile_for_org`, `get_billing_profile`, `get_or_create_status` |
| Create | `api/src/kene_api/billing/audit.py` — `write_billing_audit` wrapper over DM-PRD-07 `write_audit` |
| Create | `api/src/kene_api/billing/stripe_client.py` — Stripe SDK wrapper + driver dispatch (`real` vs `stub`) |
| Create | `api/src/kene_api/billing/stub_stripe.py` — `StubStripe` in-memory fake |
| Create | `api/src/kene_api/routers/billing.py` — `GET /pricing-tiers`, `GET /internal/status/{org_id}` |
| Create | `api/scripts/migrate_billing_pricing.py` — seeds `billing_pricing/v1` |
| Create | `api/scripts/migrate_billing_backfill.py` — back-fills `BillingProfile` + Stripe Customer for existing orgs |
| Modify | `api/src/kene_api/routers/organizations.py` — call `create_billing_profile_for_org` after org doc commit |
| Modify | `deployment/terraform/firestore.tf` — composite index on `billing_audit` (`event, timestamp DESC`); `billing_stripe_events` standalone collection ready for BL-PRD-03 |
| Modify | `deployment/terraform/secret_manager.tf` — add `stripe-price-ids-{env}`, `stripe-api-key-{env}`, `stripe-webhook-secret-{env}` |
| Modify | `api/src/kene_api/main.py` — register router behind `billing_enabled` flag |
| Create | `api/tests/unit/billing/test_pricing.py`, `test_profile.py`, `test_audit.py`, `test_stub_stripe.py` |
| Create | `api/tests/integration/billing/test_org_create_creates_profile.py` |
| Create | `api/tests/integration/billing/test_backfill_migration.py` |

### 5.2 Org-creation hook

```text
on_org_created(org_id, owner_user_id, owner_email):
  1. profile_doc = BillingProfile(
       organization_id=org_id,
       plan="free",
       stripe_customer_id=stripe.customer.create(email=owner_email, metadata={org_id}).id,
       stripe_subscription_id=None,
       current_tier_stop_index=None,
       monthly_token_allowance=500_000,
       billing_email=owner_email,
       created_at=now(),
       updated_at=now(),
     )
  2. Firestore.write organizations/{org_id}/billing_profile/profile = profile_doc
  3. Firestore.write organizations/{org_id}/status/current = OrganizationStatus(
       status="active", reason_message="", updated_at=now())
  4. write_billing_audit(event="profile_created", actor_id=owner_user_id,
       metadata={"plan": "free", "stripe_customer_id": ...})
```

The Stripe call uses the configured driver (`StubStripe` in dev/test; real Stripe in staging/prod). On Stripe failure during org creation, abort the whole org-create operation and surface the error — billing profile is mandatory.

### 5.3 Back-fill migration

```text
migrate_billing_backfill():
  1. Iterate organizations/* where no billing_profile/profile exists.
  2. For each: resolve owner_email from organization metadata; call on_org_created.
  3. Report counts: { processed, created, errored }; idempotent — re-runs skip orgs already with profiles.
```

Run once per env after BL-PRD-01 deploys. A dry-run mode (`--dry-run`) prints the planned actions without writing.

### 5.4 `StubStripe` contract

`StubStripe` mirrors the subset of the Stripe SDK that BL-PRD-01..06 will touch:

```python
class StubStripe:
    customers: dict[str, StubCustomer]
    subscriptions: dict[str, StubSubscription]
    checkout_sessions: dict[str, StubCheckoutSession]
    webhook_signing_secret: str = "whsec_stub"

    class CustomerAPI:
        def create(self, email: str, metadata: dict) -> StubCustomer: ...
        def retrieve(self, customer_id: str) -> StubCustomer: ...
        def delete(self, customer_id: str) -> None: ...

    # Subscription, Checkout, Webhook surfaces filled in by BL-PRD-03.
```

For BL-PRD-01 only the Customer API is exercised. BL-PRD-03 adds Subscription / Checkout / Webhook surfaces.

### 5.5 One-time Stripe dev-account setup (manual)

Documented in `docs/design/components/billing/runbooks/stripe-dev-setup.md` (created here):

1. In Stripe test mode, create a Product `KEN-E Subscription`.
2. For each of the 41 tier stops, create a Price under that Product (`recurring`, monthly, USD, `unit_amount = monthly_price_usd * 100`, `lookup_key = ken-e-tier-{stop_index}`).
3. Export `{stop_index: price_id}` and write to `gcloud secrets versions add stripe-price-ids-dev --data-file=-`.
4. Repeat for staging and production accounts pre-launch.

Automation of this step is out of scope for v1 — pricing-table changes are a quarterly-at-most event and benefit from a manual checkpoint.

## 6. API contract

### Public

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/billing/pricing-tiers` | Returns `[{stop_index, monthly_price_usd, monthly_token_allowance}]`. Stripe Price IDs intentionally omitted (server-side only). Used by the figma-export slider in BL-PRD-04. |

### Internal (OIDC)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/internal/billing/status/{org_id}` | Returns `OrganizationStatus`. In BL-PRD-01 always `{status: "active"}` for any org with a profile. 30s in-process cache scaffolding here; cache-invalidate hook stub for BL-PRD-02/03 to call. |

`/pricing-tiers` is gated by `billing_show_subscription_ui` (so the figma-export tab can be hidden by flag). `/internal/status/{org_id}` is unconditional once `billing_enabled` is on (downstream services need the contract).

## 7. Acceptance criteria

1. **Pydantic shapes land** as specified in §4 under `api/src/kene_api/models/billing.py`. `BillingProfile.plan` Literal includes `enterprise_invoice` (placeholder for BL-PRD-06 sales handoff).
2. **Pricing-tier JSON unit-tested** — 41 stops, monotonic, matches band arithmetic. CI fails on tampering.
3. **Firestore layout + migration** — `migrate_billing_pricing.py` writes `billing_pricing/v1` from JSON + Secret Manager join. Composite index on `billing_audit` (`event, timestamp DESC`) provisioned. `billing_stripe_events` collection registered.
4. **Org-creation hook** — every new org gets a `BillingProfile` (`plan="free"`, allowance 500K), a Stripe Customer, an `OrganizationStatus` (`active`), and a `profile_created` audit entry, atomically with org creation.
5. **Back-fill migration** — `migrate_billing_backfill.py --dry-run` reports zero divergence after a real run; re-running the real migration is a no-op.
6. **`StubStripe` Customer round-trip** — unit test creates → retrieves → deletes a stub customer; org-creation integration test uses the stub by default.
7. **`/pricing-tiers` endpoint** — returns 41 stops without Stripe Price IDs; cached for 5 min server-side.
8. **`/internal/status/{org_id}` endpoint** — returns `active` for any org with a profile; 404 for orgs without one (defensive — should never happen post-back-fill); 30s cache in place.
9. **`write_billing_audit` integration** — delegates to DM-PRD-07's `write_audit`; unit test asserts no card-substring or PAN-shaped string ever appears in `metadata` (lint rule).
10. **Stripe driver dispatch** — `BILLING_STRIPE_DRIVER=stub` selects `StubStripe`; `=real` selects the Stripe SDK with API key from Secret Manager. Test asserts production builds fail to boot if `=stub` is set.
11. **Feature flag gate** — `billing_enabled=false` keeps user-facing `/pricing-tiers` returning 404; internal endpoints still respond.
12. **Weave spans emitted** — `billing.profile_created`, `billing.status_check`, `billing.pricing_tier_lookup` with expected attributes; no email or card substrings on any span.
13. **Production safety fence** — integration test sets `ENV=production` + `BILLING_STRIPE_DRIVER=stub`; service refuses to boot.

## 8. Test plan

### Unit
- Pricing-tier JSON: schema, count, monotonicity, band arithmetic.
- `BillingProfile` Pydantic validation (plan Literal narrow, allowance non-negative).
- `create_billing_profile_for_org` with `StubStripe`: customer ID populated, profile + status + audit written atomically.
- `write_billing_audit`: shape preserved, lint rule on metadata (no card substrings).
- Stripe driver dispatch: `stub` vs `real` env var resolution; production-fence test.
- 30s status cache: hit, expiry, manual invalidation API.

### Integration
- Org-creation E2E with `StubStripe`: hit org-create endpoint → confirm `BillingProfile`, `OrganizationStatus`, `Stripe Customer` (in stub), and `profile_created` audit entry exist.
- Back-fill migration: seed an org without a profile → run migration → confirm profile created, dry-run idempotent.
- `/pricing-tiers` endpoint returns 41 stops, omits `stripe_price_id`.
- `/internal/status/{org_id}` returns `active` and 30s-caches across two requests.

### Manual verification
- Dev-env: run `setup_local_dev.sh`, create an org via the API, inspect Firestore console, confirm `billing_profile/profile` exists with the expected shape and a placeholder Stripe Customer ID matching the `StubStripe` deterministic format.
- Staging: run the back-fill migration in `--dry-run` mode against the real org list, confirm count matches expectation.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Stripe Customer creation fails during org creation → broken half-state | Wrap org create + Stripe customer create + Firestore writes in a single transaction-or-compensate pattern: on Stripe failure abort the org create entirely; on Firestore failure delete the just-created Stripe customer. Tested explicitly. |
| Back-fill migration creates duplicate Stripe Customers if re-run carelessly | Idempotency keyed on existence of `BillingProfile`, not on a Stripe call. Re-runs skip orgs with profiles. Manual override script provided to reconcile if Stripe and Firestore drift. |
| Pricing-tier JSON tampered (deliberate or accidental) → wrong prices charged downstream | Unit test enforces the published table; CI fails on diff. Production migration requires a change to the JSON + a deploy + a manual re-run of `migrate_billing_pricing.py`. |
| Stripe Price ID map in Secret Manager out of sync with the JSON (e.g. JSON has 41 stops, secret has 40) | Migration validates 1:1 coverage; refuses to write `billing_pricing/v1` on mismatch. CI lint compares JSON length to a placeholder secret length per env (length-only — no IDs in CI). |
| `StubStripe` divergence from real Stripe SDK | Contract pinned to the methods we call; integration test for BL-PRD-03 will exercise both `stub` and `real` (test mode) drivers against the same scenarios. |
| Per-env Stripe Price ID indirection mistake (prod boots with dev IDs) | Boot-time assertion: secret name must contain `{env}`; refusal to boot if mismatch. Manual ops doc: rotation never crosses env. |
| `billing_pricing/v1` getting read on every request | `/pricing-tiers` endpoint cached server-side 5 min; downstream callers (`upgrade flow` in BL-PRD-03) read once at request start. |

### Open questions
- **Q:** Should `billing_email` default to the org-owner's email at creation, or be a separate field set during checkout? → **Proposal:** default to owner email at creation; allow editing in BL-PRD-04 UI; webhook events update from Stripe Customer if changed there. Decide before BL-PRD-04.
- **Q:** Where does the org-creation flow live today, and does it already do post-create hooks? → Implementation needs a hook point. Verify in spike before estimating; if no hook framework exists, add one (small, generic) here.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md), [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-audit.md)
- Downstream: [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md), [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)
- Stripe docs: [Customers API](https://stripe.com/docs/api/customers), [Prices API](https://stripe.com/docs/api/prices)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4; T-1, T-3, T-4, T-5
