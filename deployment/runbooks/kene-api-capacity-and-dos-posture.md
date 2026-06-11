# kene-api Capacity and DoS Posture Runbook

**Issue:** CH-73
**Last updated:** 2026-06-10
**Applies to:** `kene-api-staging` and `kene-api-prod` Cloud Run services

---

## Overview

`kene-api` is the **shared edge for all traffic** — auth, OAuth callbacks, billing,
notifications, integrations, and page loads — *plus* long-held chat SSE
(`POST /api/v1/chat/completions`, up to 3600 s Cloud Run wall, 1800 s app-layer
deadline). CH-72 (PR #976) raised the timeout to 3600 s; CH-73 pins the capacity
envelope so the shared edge cannot be starved by a burst of concurrent long SSE turns.

---

## Pinned Capacity Values

| Parameter | Staging | Prod | Notes |
|---|---|---|---|
| `--cpu` | 4 vCPU | 4 vCPU | Matches System Architecture §10.2 spec |
| `--memory` | 8 GiB | 8 GiB | Matches System Architecture §10.2 spec |
| `--concurrency` | 20 | 20 | SSE-appropriate (one slot per long-held connection) |
| `--max-instances` | 20 | 40 | Total slot budget: 400 / 800 |
| `--min-instances` | 0 (scale-to-zero) | 1 (warm-pool) | Prod warm-pool eliminates cold-start on login/OAuth |

### Sizing Rationale

Moderate-tier traffic estimate (System Architecture §10.3):

- ~1,000 fast requests/day → ~1.3 req/min mean, expected peak **~10–20 concurrent fast requests**
- Expected peak **~1–5 concurrent long SSE turns** (typical multi-step agent turn 30–180 s; worst-case AH-PRD-05 supervisor turns up to 1800 s app-layer)

With `concurrency=20` and `max-instances=40` on prod:

- Total slot budget = 20 × 40 = **800 slots**
- Fast-request headroom = 800 − 5 SSE slots = **795 slots** ≈ **80× the peak fast estimate**
- Starvation scenario (20 concurrent SSE turns filling one full instance) still leaves 39 × 20 = 780 slots for fast traffic

The prod `min-instances=1` warm-pool costs ~$252/mo at 4 vCPU (4 vCPU × 3600 s/hr × 730 hr/mo × $0.000024/vCPU-sec) but eliminates the 5–10 s cold-start tail on login and OAuth callbacks. See "Cost" below for the full estimate.

---

## DoS Controls (Three Layers)

### Layer 1 — Cloud Run instance ceiling (cost blast radius)

`--max-instances=40` (prod) / `=20` (staging) caps the maximum concurrent billable
instance-seconds under a sustained attack. A burst that exhausts the slot budget
results in Cloud Run returning HTTP 429 ("instance concurrency limit reached") rather
than scaling unboundedly.

**Tradeoff:** a lower `max-instances` reduces cost blast radius but *also* lowers the
saturation threshold. With `timeout=3600`, a slowloris-style attacker needs only
`concurrency × max-instances = 800` held connections to exhaust prod's budget — so
Cloud Armor (Layer 3) is the right upstream chokepoint, not a tight `max-instances`.

### Layer 2 — App-layer rate limiting and per-request deadline (abuse blast radius)

**`token_rate_limiter`** (owned by Agentic Harness, `api/src/kene_api/auth/rate_limiting.py`):

- 60 req/min, 1000 req/hr per authenticated user
- Key strategy: authenticated UID (sha256[:16] hash)
- `fail_open=True` — a Redis outage allows requests through; does not cascade to service outage
- Applied in `api/src/kene_api/auth/user_context.py:get_current_user_context()`
- Configured explicitly via env vars in both CD YAMLs: `KENE_TOKEN_RATE_LIMIT_PER_MINUTE=60`, `KENE_TOKEN_RATE_LIMIT_PER_HOUR=1000`

To tighten per-user limits without a redeploy, update `KENE_TOKEN_RATE_LIMIT_PER_MINUTE` /
`KENE_TOKEN_RATE_LIMIT_PER_HOUR` in the deploy's `--set-env-vars` and re-trigger the CD
pipeline. Values take effect on the next Cloud Run revision.

**App-layer per-request deadline** (`api/src/kene_api/routers/chat.py`, `asyncio.wait_for` on `agent_engine.stream_query`):

```python
stream_iterator = await asyncio.wait_for(
    loop.run_in_executor(None, lambda: self.agent_engine.stream_query(...)),
    timeout=1800.0,
)
```

The `asyncio.wait_for(timeout=1800.0)` deadline fires before the Cloud Run 3600 s wall,
so the application ends the request with a controlled error (logged, propagated to the
SSE client) rather than a 504. A stuck agent turn is killed at 1800 s, not 3600 s.

**`rate_limit_backend_override` feature flag** (emergency rollback to in-memory rate limiting):

If Redis becomes unavailable and the `SwitchableRateLimiter` circuit breaker is
causing noise, flip `rate_limit_backend_override` to `true` in `/admin/feature-flags`
(super-admin only). All `SwitchableRateLimiter` instances switch to their in-process
`LocalRateLimiter` fallback within ≤60 s. See `api/CLAUDE.md` §Rate Limiting for the
full rollback procedure.

### Layer 3 — Cloud Armor (deferred to CH-75)

Cloud Armor on Cloud Run requires fronting the service with a Serverless NEG + Global
Load Balancer — not a flag toggle. This changes the ingress model:

- `KENE_RATE_LIMIT_TRUSTED_HOPS` must be bumped from `1` → `2` (the GLB appends the
  real client IP as a second trusted hop in the XFF chain)
- Monthly cost: ~$18/mo Cloud Armor policy + ~$0.0075/HTTP request beyond the included tier
- Adds 1–5 ms global-anycast latency for non-regional clients

**Evaluation and rollout are tracked in CH-75.** Do not change `KENE_RATE_LIMIT_TRUSTED_HOPS`
until the GLB is in place — changing it without the GLB would route all requests to the
IP-sentinel bucket and break IP-keyed rate limiting.

---

## SSE-Endpoint Isolation (Long-Term Direction, CH-74)

The root cause of the starvation tension is running long-timeout SSE and fast requests
on the same Cloud Run service. The proper fix is splitting `POST /api/v1/chat/completions`
onto a dedicated `kene-api-sse-{env}` Cloud Run service:

- SSE service: `--timeout=3600`, `--concurrency=5–10`, `--max-instances=20` (sized for
  concurrent long turns, not fast traffic)
- Fast edge: `--timeout=60`, `--concurrency=80` (Cloud Run default), `--max-instances=40`
  (sized for high fan-out, short requests)

This lets each surface be sized independently so neither starves the other. Scope:
CD changes, frontend `VITE_API_BASE_URL` routing split, auth middleware sharing,
observability split. **Tracked in CH-74; out of scope for CH-73.**

The current `--max-instances=40` / `--concurrency=20` sizing in CH-73 is made with this
direction in mind — even if AH-PRD-05 supervisor-orchestration doubles the concurrent SSE
assumptions (1–5 → 10), the 800-slot budget keeps fast-request headroom > 10×.

---

## Operator Playbook

### Raise `--max-instances` quickly under load (no full redeploy needed)

```bash
# Prod — bump to 60 instances to absorb a traffic spike
gcloud run services update kene-api-prod \
  --region=us-central1 \
  --project=ken-e-production \
  --max-instances=60

# Staging
gcloud run services update kene-api-staging \
  --region=us-central1 \
  --project=ken-e-staging \
  --max-instances=30
```

This takes effect within ~30 s. The next CD deploy will reset the value to the YAML-pinned
number, so also update `deployment/cd/deploy-to-prod.yaml` (or `staging.yaml`) and
open a PR to persist the change.

### Confirm `min-instances=1` is honored on prod after deploy

```bash
gcloud run services describe kene-api-prod \
  --region=us-central1 \
  --project=ken-e-production \
  --format="value(spec.template.metadata.annotations)"
# Look for: run.googleapis.com/minScale: "1"
```

Or via Cloud Monitoring: `run.googleapis.com/container/instance_count` for
`kene-api-prod` should show ≥ 1 at all times after the CH-73 deploy.

### Verify capacity flags landed in the current revision

```bash
gcloud run revisions describe \
  $(gcloud run services describe kene-api-prod \
    --region=us-central1 --project=ken-e-production \
    --format="value(status.latestCreatedRevisionName)") \
  --region=us-central1 --project=ken-e-production \
  --format="value(spec.containerConcurrency,spec.template.metadata.annotations)"
```

Expected output includes `containerConcurrency: 20` and
`run.googleapis.com/maxScale: "40"`.

### Roll back to previous Cloud Run revision (if the deploy introduced a regression)

```bash
# Identify the prior revision
gcloud run revisions list \
  --service=kene-api-prod \
  --region=us-central1 \
  --project=ken-e-production \
  --limit=5

# Roll traffic back to the prior revision (e.g., kene-api-prod-00042-abc)
gcloud run services update-traffic kene-api-prod \
  --region=us-central1 \
  --project=ken-e-production \
  --to-revisions=kene-api-prod-00042-abc=100
```

---

## Cost Estimate (Prod, Moderate Tier)

| Item | Calculation | Monthly estimate |
|---|---|---|
| Warm-pool (min-instances=1) | 4 vCPU × 3600 s/hr × 730 hr/mo × $0.000024/vCPU-s | ~$253/mo |
| Burst capacity (autoscale above 1) | Already included in §10.3 Moderate-tier ~$864 estimate | ~$864/mo total |

The warm-pool cost is a subset of the §10.3 estimate (min-instances=1 vs. scale-to-zero
adds ~$253/mo for the always-on instance; the §10.3 row assumed 10,000 CPU-hours which
approximates 10 instances × 1,000 hours). The delta vs. scale-to-zero is the
`min-instances=1` premium — acceptable given the p99 benefit for login and OAuth.

---

## Related

- [`deployment/cd/staging.yaml`](../cd/staging.yaml) — staging CD YAML (capacity flags at `deploy-api-to-cloud-run` step)
- [`deployment/cd/deploy-to-prod.yaml`](../cd/deploy-to-prod.yaml) — prod CD YAML (capacity flags at `deploy-api-to-cloud-run` step)
- [`docs/KEN-E-System-Architecture.md`](../../docs/KEN-E-System-Architecture.md) §10.2 — compute requirements table
- `api/CLAUDE.md` §Rate Limiting — full rate-limiter architecture and `rate_limit_backend_override` rollback procedure
- [CH-73](https://linear.app/ken-e/issue/CH-73) — this capacity decision issue
- [CH-74](https://linear.app/ken-e/issue/CH-74) — SSE-endpoint isolation (long-term fix)
- [CH-75](https://linear.app/ken-e/issue/CH-75) — Cloud Armor evaluation
- [CH-72](https://linear.app/ken-e/issue/CH-72) — raised the timeout to 3600 s (PR #976)
