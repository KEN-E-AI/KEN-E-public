# AH-PRD-10 — Rate-Limiter Rework: User-Keyed Identity + Shared State

> **Linear Project:** AH-PRD-10 under [KEN-E] Agentic Harness
> **Status:** Shipped (R1)
> **Owner team:** Core AI
> **Blocked by:** —
> **Parallel with:** any other AH-PRD work (low surface-area overlap)
> **Blocks:** DM-104 (the e2e flake half), any future per-user quota work
> **Estimated effort:** ~5–7 days (6 issues — 4 serially, 2 in parallel; details in §5)

## 1. Context

### 1.1 What's broken

The current `RateLimiter` at `api/src/kene_api/rate_limiter.py` has three architectural defects, each independent and each load-bearing for a real prod failure mode:

1. **IP-keyed only.** `_get_client_id()` returns the first IP in `X-Forwarded-For` or `request.client.host`. Every request from the same egress IP shares one bucket. **Production consequence:** NAT'd users (corporate networks, mobile carrier CGNAT, VPN endpoints) all share a single rate-limit bucket; one noisy client on a corporate network DoSes every other legitimate user behind the same egress. **CI consequence:** e2e tests all bind to 127.0.0.1, so every parallel test request shares one bucket — surfaces as the periodic Playwright flake that DM-104 partially covers and that CH-54 tactically band-aided in PR #665.
2. **In-memory only.** State is `defaultdict(list[float])` of timestamps per client. Two consequences:
   - **Lost on restart.** Every Cloud Run cold start zeros the bucket — a real attacker just waits for a deploy or scaling event.
   - **Per-instance, not per-service.** With N Cloud Run instances, the effective limit is N × the configured threshold. The "60/min" `token_rate_limiter` is actually 60×N/min in prod. **The same multiplier applies to every wired limiter** — and the day a server-side login endpoint exists, the `auth_rate_limiter`'s "10/min" brute-force ceiling would likewise be 10×N/min. (Today `auth_rate_limiter` and `password_reset_rate_limiter` are unwired — see §3.1 — so the multiplier currently bites only `token`, `progress`, and `recaptcha`.) The Redis migration fixes this for every limiter it backs, not just `token_rate_limiter`.
3. **`X-Forwarded-For` is trusted blindly.** The header is client-controllable; any unauthenticated request can spoof a different IP by setting the header. There's no trusted-proxy-hop count and no validation against the actual ingress chain.

### 1.2 Why now

CH-54 (merged PR #665 on 2026-05-26) made the per-minute / per-hour thresholds env-configurable as a **tactical** unblock for an e2e Playwright flake. It is documented as tactical only — see the inline note at `rate_limiting.py:14-18`. The architectural concerns above remain. Ken called this out in the 2026-05-27 morning message: *"token_rate_limiter is IP-keyed only. Real prod bug (NAT'd users share buckets); e2e flake was the visible proxy. CH-54 ships tactical D today; the rework needs a component-home decision."* This PRD is that rework.

### 1.3 Why agentic-harness as the home

Ken's call (2026-05-27): *"Can you scope out a project and add it to the agentic-harness component to resolve this?"*

The implementation lives at `api/src/kene_api/{rate_limiter.py,auth/rate_limiting.py}` — physically in the API package, not under `app/adk/agents/`. Three reasons agentic-harness is still the right home:

1. **Every chat turn flows through the harness, and the harness's only protection against request-flood DoS is this limiter.** The README §1 frames the component as the path every user message takes; the limiter is the gate at the front of that path. Owning it puts the gate's design under the team that understands the load profile.
2. **No better fit in the current 15-component map.** Data Management is data-shape work; Performance is the analytics page; Skills/Project Tasks/etc. all consume agents downstream. A new "Platform" component for cross-cutting middleware would be a larger ownership change than this single limiter warrants.
3. **Future per-user quota work belongs here too.** Once we're user-keyed, downstream PRDs (per-account chat quotas, per-tier billing limits in Billing) can layer on the same key-derivation infrastructure. Concentrating that ownership in agentic-harness avoids each consuming component reinventing it.

**Provisional home caveat:** the implementation lives entirely under `api/src/kene_api/` — no source file in `agentic-harness/` proper. The home is defensible per the three reasons above + Ken's call, but if a future "Platform" or "API Core" component is ever formalized (covering cross-cutting middleware: rate-limiting, telemetry, request lifecycle), this PRD's deliverables would naturally migrate there. Document the placement as **provisional** to avoid confusion in future ownership discussions.

## 2. Scope

### In scope

- **Replace `_get_client_id()` with a pluggable key strategy.** Authenticated requests use the Firebase UID from `UserContext`; unauthenticated requests fall back to IP with a `trusted_hops` validation against `X-Forwarded-For`.
- **Move state to Redis (Memorystore in prod).** The existing Redis Memorystore instance hosts the buckets; this PRD does not add new infrastructure, only consumes existing Redis. **Important async caveat:** the existing `redis_client.py` exposes a sync `redis.Redis` client. The new `RedisRateLimiter` runs in the async FastAPI dependency chain, so it MUST use `redis.asyncio.Redis` (the `redis-py` async client) OR wrap sync calls in `asyncio.to_thread` — calling sync Redis from an async path blocks the event loop. AH-PRD-10 #2 introduces an async-compatible Redis access layer for the limiter; the existing sync client stays in place for non-async consumers.
- **Per-limiter fail-open vs in-process fallback on Redis outage.** Throughput limiters (`token_rate_limiter`, `progress_rate_limiter`) fail-open during Redis outage — a Redis outage should not cascade to a service outage for non-security-critical paths. **Security-critical limiters** (`auth_rate_limiter`, `password_reset_rate_limiter`, `recaptcha_rate_limiter`) fall back to the **in-process `LocalRateLimiter`** during Redis outage — preserves per-instance brute-force defense (N×limit/min across N instances is still far better than zero protection). The fallback is automatic via a `fallback_on_redis_error: bool | LocalRateLimiter` constructor parameter on `RedisRateLimiter`.
- **Split the 5 existing limiters into two key-strategy buckets.** Three stay IP-keyed by design (`auth_rate_limiter` = pre-login brute-force defense, `password_reset_rate_limiter` = before identity is established, `recaptcha_rate_limiter` = unauthenticated endpoint). Two move to user-keyed with IP-fallback (`token_rate_limiter` = authenticated requests, `progress_rate_limiter` = authenticated polling).
- **Harden `X-Forwarded-For` parsing** behind a `trusted_proxy_hops: int` configuration (default 1 for Cloud Run's standard single-hop ingress). Take the IP at position `len(chain) - trusted_proxy_hops`, refuse to accept spoofed client-supplied prefixes.
- **Backward-compatible env vars.** `KENE_TOKEN_RATE_LIMIT_PER_MINUTE` / `KENE_TOKEN_RATE_LIMIT_PER_HOUR` from CH-54 continue to work; new env vars (`KENE_RATE_LIMIT_REDIS_PREFIX`, `KENE_RATE_LIMIT_TRUSTED_HOPS`) add configuration without breaking existing deploys.
- **Update `auth/user_context.py:297` call site** to inject the UserContext into the limiter's key-derivation closure so the authenticated key strategy can read the UID.
- **Migration plan for e2e** so DM-104's e2e flake half is structurally fixed (per-user buckets instead of one shared 127.0.0.1 bucket) and the CH-54 tactical env-var overrides can be removed from `start_e2e_stack.sh`.

### Out of scope

- **New rate-limiter features** (per-tier limits, dynamic quotas, billing integration, per-endpoint custom limits). Future PRDs in Billing or a follow-up here can layer those on; this PRD ships the substrate, not the policies.
- **Re-tuning the numerical thresholds.** The current values (60/min, 1000/hour for `token_rate_limiter`; 10/min, 50/hour for `auth_rate_limiter`; etc.) carry over unchanged. After user-keying, "60/min" means 60-per-user-per-minute — a different policy from before (was 60-per-IP-per-minute). Whether 60 is still the right number under the new semantics is a separate policy question for a future PRD; this PRD ships the substrate.
- **The `auth_rate_limiter` brute-force semantics.** IP-keying stays correct for that one — the user identity doesn't exist pre-login. No behavioral change there (other than the Redis-backing win the migration gives it for free).
- **Internal service-to-service callers (no Firebase UID).** The `authenticated_key_strategy` falls back to `_validated_ip_key` when `ctx` is `None`, so internal callers continue to be IP-keyed. If a future PRD adds explicit internal-caller identity (e.g. a per-service token claim), the strategy can be extended to read it; out of scope here.
- **Distributed-system-grade rate-limit guarantees** (e.g. exact-counts across regions). The Redis-backed limiter is best-effort consistent — race conditions inside a 60s window are acceptable for this use case.
- **Re-architecting the API middleware stack.** The limiter is called from `auth/user_context.py:297` today; this PRD changes what it does but not where it's called from.
- **Removing the in-memory limiter implementation.** Keep `RateLimiter` (in-memory) as a `LocalRateLimiter` for unit tests + local dev that doesn't want a Redis dependency. The new `RedisRateLimiter` is the prod path.

## 3. Dependencies

- **Existing Redis instance** (Memorystore for prod, local Redis for dev — already used by `cache-ttl-proxy` and the cached_user_context layer). No new infrastructure.
- **`UserContext` model** at `api/src/kene_api/auth/user_context.py` — read-only; the key-strategy closure needs `.uid`.
- **Existing env-var pattern** (CH-54): `KENE_*` namespace. New vars follow the same convention.
- **DM-104** (CI flake trio triage) — this PRD's e2e migration delivers a structural fix for the e2e half. DM-104 is **not** a blocker; it captures the broader CI-flake context that informed this PRD's scope.
- **No PRD-level blockers.** The implementation can land in parallel with any other AH-PRD work — the surface area is `api/src/kene_api/rate_limiter.py` + 2-3 callers, no overlap with the agent-runtime PRDs (AH-PRD-01..09).

### 3.1 Limiter call-site inventory (verified against `main`, 2026-05-28)

This PRD touches 6 limiters. Three are **live** (wired to a real request path today); two are **dormant dead-code** (defined but never invoked); one is **new** (introduced by AH-C). Enumerated here so the wiring surface is unambiguous (resolves Ken review Comment 1).

| Limiter | Status | Defined at | Call site(s) | Key strategy after rework |
|---|---|---|---|---|
| `token_rate_limiter` (60/min, 1000/hr) | **live** | `auth/rate_limiting.py:19` | `auth/user_context.py:297` → `_apply_rate_limiting` (the default authenticated token-verify path) | user-keyed + IP fallback |
| `progress_rate_limiter` (120/min, 2000/hr) | **live** | `rate_limiter.py:95` | `auth/dependencies.py:260` (authenticated polling path) | user-keyed + IP fallback |
| `recaptcha_rate_limiter` (5/min, 20/hr) | **live** | `rate_limiter.py:88` | `routers/auth.py:53` (`POST /api/v1/auth/verify-recaptcha`) — **direct call, no audit log today** (see §6.4 / AC-16) | IP-keyed |
| `auth_rate_limiter` (10/min, 50/hr) | **dormant — 0 call sites** | `auth/rate_limiting.py:9` | none (no server-side login/signup endpoint — Firebase client SDK owns login) | IP-keyed *if/when wired* |
| `password_reset_rate_limiter` (3/min, 10/hr) | **dormant — 0 call sites** | `auth/rate_limiting.py:26` | none (no server-side password-reset endpoint — Firebase client SDK owns reset) | IP-keyed *if/when wired* |
| `bad_token_rate_limiter` (10/min, 50/hr) | **new (AH-C)** | created in AH-C | `auth/user_context.py:~93` (bad-token exception path) | IP-keyed |

**Dormant-limiter resolution (Ken review Comment 1):** Ken's review flagged `password_reset_rate_limiter` as dead code; verification surfaced that `auth_rate_limiter` is **equally unwired**. Both guard server-side endpoints (`/login`, `/password-reset`) that **do not exist** — KEN-E's login and password-reset flows run entirely in the Firebase client SDK. So Ken's suggested "wire it into the password-reset router" is not actionable (there is no router to wire to), and creating those endpoints is out of scope for a rate-limiter rework. This PRD therefore:
- migrates the two dormant limiters to the new key-strategy/backend substrate **for parity only** (so they are correct the day a server-side endpoint is ever added); and
- scopes their AC-10 / AC-13 fail-closed + emergency-cap semantics as **forward-looking** — they bind only once a call site exists.

Whether to instead **delete** the two dormant limiters (vs. keep them dormant-but-migrated) is a small reversible call deferred to AH-A's first comment-thread review; see the §9 open question. It does not block the rest of the project.

## 4. Data contract

### 4.1 Redis key shape

```
Key:   kene:ratelimit:{limiter_name}:{window}:{client_key}
Value: ZSET of (unique_request_id, timestamp_score) — see §4.6 for the unique-id rationale
TTL:   window_seconds + 60 (auto-expire well after the window slides past)

where:
  limiter_name ∈ {auth, bad_token, token, password_reset, recaptcha, progress}  // 6 limiters per v4
  window ∈ {minute, hour}
  client_key = uid:{sha256(user_id)[:16]}  OR  ip:{validated_ip}  OR  ip:_no_xff_chain_  (sentinel for short-chain fallback)
```

Example: `kene:ratelimit:token:minute:uid:a1b2c3d4e5f60718` for the authenticated token limiter's per-minute bucket for one user (the UID is hashed to prevent injection via lawful-but-unusual UID chars).

**Why ZSET (sorted set) not list:** the sliding-window check needs to count entries newer than `now - window`, then trim older entries. ZSET's `ZRANGEBYSCORE` + `ZREMRANGEBYSCORE` are both O(log N) operations on the indexed timestamp, where today's `[req_time for req_time in requests if req_time > cutoff_time]` is O(N) per check.

**Why hash the UID** (v4 correction E): Firebase UIDs are normally `[A-Za-z0-9]{28}`, but the OIDC path can carry arbitrary `sub` values from external providers — including legal characters like `:` that would collide key segments. `sha256(user_id)[:16]` (64 bits of collision resistance, plenty for rate-limit-bucket isolation) is the bounded-cardinality + injection-safe representation. The full UID is still available to the audit logger via `UserContext`; only the Redis key uses the hash.

**Why two keys per limiter (minute + hour)** (v4 correction L): each limiter has both a per-minute and a per-hour limit. The atomic Lua script operates on both keys (`KEYS[1]=minute_key, KEYS[2]=hour_key`) and returns the most-restrictive count for header computation. Two separate non-atomic Lua calls would lose the atomicity guarantee for the hour window.

### 4.2 Key-strategy closure type

```python
# api/src/kene_api/rate_limiter.py
import hashlib
from collections.abc import Callable

from fastapi import Request

from .auth.models import UserContext  # type: ignore[import]

KeyStrategy = Callable[[Request, UserContext | None], str]

def authenticated_key_strategy(request: Request, ctx: UserContext | None) -> str:
    if ctx is None:
        # Two cases reach here: (a) an authenticated limiter ran on a path that
        # didn't resolve a UserContext — a code bug (limiter applied before
        # context resolution); or (b) an internal service-to-service caller
        # without a Firebase UID. Both fall back to IP-keyed — degrades
        # gracefully rather than failing the request — but the fallback is
        # LOGGED so case (a) regressions aren't silent (Ken review Comment 4).
        # If/when internal callers need a distinct identity, extend this
        # strategy rather than introducing a separate one.
        logger.warning(
            "ratelimit.authenticated_strategy_no_ctx path=%s "
            "(falling back to IP — investigate caller)",
            request.url.path,
        )
        return _validated_ip_key(request)
    # Hash the UID to (a) prevent injection via lawful-but-unusual UID chars
    # (OIDC `sub` claims may contain `:`), (b) bound key cardinality, and
    # (c) avoid leaking the raw UID into Redis (operational defense-in-depth
    # — the audit logger still has the full UID via UserContext).
    uid_hash = hashlib.sha256(ctx.user_id.encode("utf-8")).hexdigest()[:16]
    return f"uid:{uid_hash}"

def ip_only_key_strategy(request: Request, ctx: UserContext | None) -> str:
    return _validated_ip_key(request)

def _validated_ip_key(request: Request) -> str:
    """Trusted-hops-aware X-Forwarded-For parse. See §4.3."""
```

**v4 correction D applied:** `ctx.user_id` (correct attribute name) not `ctx.uid` (which doesn't exist on `UserContext`).

**v4 correction E applied:** UID hashed before key composition.

### 4.3 X-Forwarded-For trust model

Cloud Run's GFE appends the immediate client IP to `X-Forwarded-For` as the LAST entry. With `trusted_hops=1` (Cloud Run default), the client IP is `chain[-1]`. With `trusted_hops=N`, the client IP is `chain[-N]` (we trust the last N entries because they were added by infrastructure we control; entries before that are client-supplied and could be spoofed).

```python
def _validated_ip_key(request: Request) -> str:
    trusted_hops = int(os.environ.get("KENE_RATE_LIMIT_TRUSTED_HOPS", "1"))
    xff = request.headers.get("X-Forwarded-For", "")
    chain = [ip.strip() for ip in xff.split(",") if ip.strip()]

    if len(chain) >= trusted_hops:
        # Take the IP that's `trusted_hops` positions from the end.
        # Cloud Run, trusted_hops=1: chain = [..., client_ip] → chain[-1] is the client.
        # Two-hop infra, trusted_hops=2: chain = [..., client_ip, lb1] → chain[-2] is the client.
        client_ip = chain[-trusted_hops]
        return f"ip:{client_ip}"

    # Fewer hops than expected — request didn't traverse the configured proxy chain.
    # v4 correction G: do NOT fall back to request.client.host on Cloud Run — that's
    # the load-balancer IP, not the client. Falling back to it collapses every request
    # into one shared bucket. Use a sentinel key + WARNING log so ops sees the chain
    # drift; the sentinel'd requests get a shared (intentionally degraded) bucket which
    # the operator can address by fixing the ingress chain.
    logger.warning(
        "ratelimit.xff_fallback expected_hops=%d actual_hops=%d path=%s xff=%s",
        trusted_hops, len(chain), request.url.path, xff,
    )
    return "ip:_no_xff_chain_"
```

**Reference implementation:** mirrors Uvicorn's `ProxyHeadersMiddleware` (`uvicorn.middleware.proxy_headers`) — same trusted-hops-from-end semantics. We don't reuse Uvicorn's middleware directly because it mutates `request.client.host` globally; we want the limiter-scoped derivation without touching `request.client` for other middleware.

**Cloud Run chain note (v4 — architect Important #5; reframed per Ken review Comment 3):** `KENE_RATE_LIMIT_TRUSTED_HOPS=1` is correct for the **current** topology — verified against `deployment/terraform/` on 2026-05-27: **no Global External Application Load Balancer** sits in front of Cloud Run (no `google_compute_global_forwarding_rule` / `url_map` / `backend_service`), so prod is direct Cloud Run ingress and the immediate client IP is `chain[-1]`. If a GLB is ever added (e.g. HTTPS termination on a custom domain), the chain becomes `[client_ip, glb_ip]` and `trusted_hops=2` is correct. Because there is nothing to "verify against" in the current topology, the acceptance bar is **"a runbook entry exists"** (in `api/CLAUDE.md`, delivered by AH-E) instructing an operator to re-verify and bump `KENE_RATE_LIMIT_TRUSTED_HOPS` if/when a GLB is introduced — *not* "verify before AH-71 merges." The wrong value silently keys requests off the wrong IP (defense-in-depth weakening, not catastrophic).

**Sentinel-bucket DoS hardening (Ken review Comment 3):** the `ip:_no_xff_chain_` sentinel is a *shared* bucket — every short-chain request lands in it. If it inherited a normal per-limiter threshold (e.g. 60/min for `token`), an attacker who knows the deployment topology could deliberately omit the expected proxy chain to crowd the sentinel and weaponize it against any legitimate user momentarily dropped into it by an ingress hiccup. Mitigation: a single shared sentinel key `kene:ratelimit:_sentinel_` carries its own **aggressive cap — 5/min across all sentinel hits regardless of which limiter is reporting** — checked *before* the per-limiter check whenever `client_key == "ip:_no_xff_chain_"`. Abuse is self-bounded, ops still gets the WARNING-log signal, and momentary-drift users degrade gracefully instead of being weaponized. See AC-19.

### 4.4 Env vars (additive)

| Var | Default | Purpose |
|---|---|---|
| `KENE_TOKEN_RATE_LIMIT_PER_MINUTE` | 60 | Existing (CH-54) — preserved |
| `KENE_TOKEN_RATE_LIMIT_PER_HOUR` | 1000 | Existing (CH-54) — preserved |
| `KENE_RATE_LIMIT_BACKEND` | `redis` in prod/staging, `memory` in dev/test | Selects backend; `memory` keeps the legacy `LocalRateLimiter` for local dev without a Redis dependency. **Also exposed as a feature flag** for instant rollback without redeploy (see §9). |
| `KENE_RATE_LIMIT_REDIS_PREFIX` | `kene:ratelimit` | Key prefix; namespace isolation if multiple services share a Redis instance |
| `KENE_RATE_LIMIT_TRUSTED_HOPS` | 1 | X-Forwarded-For trust depth (Cloud Run = 1 ingress hop) |

**Redis connection vars (already exist in the codebase — reused, not redefined here):** `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB` (per `api/src/kene_api/redis_client.py`). The PRD reuses the existing 4-var pattern — no `REDIS_URL` introduction. The async limiter constructs its own `redis.asyncio.Redis` client from the same 4 vars.

### 4.5 Response headers (server → client)

The new limiter exposes the de-facto-standard rate-limit headers on every limited response (both 200 OK and 429):

| Header | Source | Notes |
|---|---|---|
| `X-RateLimit-Limit` | the configured `requests_per_minute` (or `_per_hour` when that's the binding window) | Constant for the limiter |
| `X-RateLimit-Remaining` | `limit - ZCARD(key)` after the current request is counted | Cheap with ZSET — the count is already computed during the check |
| `X-RateLimit-Reset` | epoch seconds when the oldest entry in the bucket ages out (`ZRANGEBYSCORE key 0 +inf WITHSCORES LIMIT 0 1` → `score + window`) | Cheap with ZSET; today's limiter can't compute this without a full scan |
| `Retry-After` (on 429 only) | accurate seconds until the bucket frees a slot — `X-RateLimit-Reset - now` | Replaces today's fixed `Retry-After: 60` |

Frontend can swap blind exponential backoff for accurate scheduled retry. The `Retry-After` accuracy is the one place where the ZSET design is materially better than alternatives.

**Information-disclosure consideration (security Medium #1):** `X-RateLimit-Remaining` gives an attacker an exact attempts-remaining oracle. For `token_rate_limiter` (60/min/user) this is benign — leaks per-user request rate, which is observable anyway. For IP-keyed security-critical limiters (`auth`, `bad_token`, `password_reset`, `recaptcha`), the limiter MUST omit `X-RateLimit-Remaining` on 200 OK responses and only include it on the 429 response (the attacker already knows they hit the limit at that point). Implementation: `RateLimiter.emit_remaining_on_success: bool` flag, default `True` for user-keyed limiters, default `False` for IP-keyed security-critical limiters.

### 4.6 Atomic Lua script — operational ordering

The two-window Lua script (operates on `KEYS[1]=minute_key, KEYS[2]=hour_key`) must execute steps in this strict order to satisfy the X-RateLimit-Reset accuracy requirement (architect Important #2):

```
For each of the two windows (in sequence; same logic):
  1. ZREMRANGEBYSCORE key 0 (now - window)        # trim stale entries
  2. ZRANGEBYSCORE key 0 +inf WITHSCORES LIMIT 0 1 # READ oldest_score BEFORE add
  3. ZCARD key                                     # count existing entries
  4. If count >= limit: return (allowed=False, count, oldest_score)
  5. ZADD key now "{now}:{uuid4().hex[:8]}"        # unique member to prevent same-score collision (security Medium #2)
  6. EXPIRE key (window + 60)                      # bounded lifetime

Return (allowed=True, count + 1, oldest_score)
```

**Why `ZADD` uses a unique member** (security Medium #2): if two concurrent requests in the same `time.time()` tick (sub-µs precision under load) compute the same `now`, plain `ZADD now now` would be a no-op for the second (member already exists), letting attackers slip an extra request through. The unique suffix (`uuid4().hex[:8]` or a Redis-side `INCR`) ensures every request adds a distinct entry.

**Why `EXPIRE` is the LAST step** (security Medium #3): if the script crashes between earlier steps (Redis OOM, network drop), the key still has whatever TTL it had from a prior invocation — so it eventually expires. If EXPIRE were first and ZADD failed, the bucket would still age out correctly. Net: EXPIRE-last is safer because every successful path sets it; only the no-add path (count >= limit) skips the EXPIRE — and that path doesn't add anything to extend the bucket lifetime.

**Two-window header computation (v4 correction L):** the Lua script returns BOTH windows' counts; the FastAPI layer picks the more-restrictive window for `X-RateLimit-Limit` / `X-RateLimit-Remaining` / `X-RateLimit-Reset`. Typically the per-minute window dominates; per-hour kicks in for burst-then-quiet traffic patterns.

## 5. Implementation outline

6 issues; 4 sequential (AH-A → AH-B1 → AH-B2 → AH-C) then 2 in parallel (AH-D, AH-E); ~5–7 days total with one engineer, ~3–4 with two. (AH-B was split into **AH-B1 + AH-B2** per Ken review Comment 2 — the original XL bundled ~8 correctness surfaces into one un-reviewable PR.)

| # | Issue (work item) | Size | Depends on | Files |
|---|-------------------|------|------------|-------|
| AH-A | **Extract `KeyStrategy` + `LocalRateLimiter` rename.** Move the existing in-memory `RateLimiter` to `class LocalRateLimiter` with **`async def check_rate_limit`** (v4 correction A — uniform async interface for both backends). Add `KeyStrategy = Callable[[Request, UserContext \| None], str]` + the 3 built-in strategies. UID hashing per §4.2 (v4 correction E). `_validated_ip_key` returns sentinel key + WARNING log on short chains (v4 correction G — no `request.client.host` fallback). | M | — | `api/src/kene_api/rate_limiter.py`, `api/src/kene_api/auth/rate_limiting.py` |
| AH-B1 | **`RedisRateLimiter` core (ZSET, async, 2-key Lua).** New `class RedisRateLimiter` with `async def check_rate_limit` using `redis.asyncio.Redis`. 2-key Lua script per §4.6 (KEYS[1]=minute, KEYS[2]=hour) — atomic across both windows. Unique-suffixed ZADD members (security Medium #2). EXPIRE last (security Medium #3). `X-RateLimit-*` headers per §4.5 with the `emit_remaining_on_success` flag (security Medium #1). Shared sentinel cap per §4.3 (AC-19). `fakeredis.aioredis` dev dep + CI fixture. | L | AH-A | `api/src/kene_api/rate_limiter.py`, `api/tests/{unit,integration}/test_rate_limiter.py`, `api/pyproject.toml` |
| AH-B2 | **`SwitchableRateLimiter` + resilience.** Wrapper that reads the `rate_limit_backend_override` feature flag **per request** and delegates to Redis or in-process Local (v4 correction B — resolves architect Critical #2). Circuit breaker (v4 correction I — opens after K=10 consecutive Redis errors, 60s cooldown). Emergency cap on `LocalRateLimiter` fallback for security-critical limiters (v4 correction H). Audit-log + Cloud Monitoring alert on every `rate_limit_backend_override` flip (v4 correction K). Splits cleanly from AH-B1: depends on AH-B1's public interface, not its internals. | M | AH-B1 | `api/src/kene_api/rate_limiter.py`, `api/tests/{unit,integration}/test_rate_limiter.py` |
| AH-C | **Wire `UserContext` into all LIVE limiter call sites.** Update every `check_rate_limit` invocation in `auth/user_context.py` (the `_apply_rate_limiting` sites ~51 / ~93 / ~305) + `routers/auth.py:53` (v4 correction F — the recaptcha call site) to `await limiter.check_rate_limit(request, ctx_or_none)`. Assign the appropriate `KeyStrategy` to all 6 limiter instances in `auth/rate_limiting.py` + `rate_limiter.py` (the 2 dormant limiters — `auth`, `password_reset`, see §3.1 — get a strategy for parity but stay unwired). Add the new `bad_token_rate_limiter` (v4 correction C) and route the bad-token exception path (`user_context.py:~93`) through it (10/min IP) instead of `token_rate_limiter`'s 60/min IP-fallback — restores the 10/min brute-force ceiling (security Critical #1). Thread the audit logger into the limiters per §6.4 (Option A) so every 429 — including recaptcha's — emits `log_rate_limit_exceeded` (AC-16). | M | AH-A, AH-B2 | `api/src/kene_api/auth/{rate_limiting.py,user_context.py}`, `api/src/kene_api/routers/auth.py`, `api/src/kene_api/rate_limiter.py` |
| AH-D | **E2E migration + drop CH-54 tactical overrides.** Update `deployment/ci/scripts/start_e2e_stack.sh` to remove the `KENE_TOKEN_RATE_LIMIT_PER_MINUTE=10000` env-var overrides; the user-keyed strategy gives each test user their own bucket so 60/min is plenty. Add a regression test that proves DM-104's e2e flake half is fixed (concurrent requests from different test users don't share a bucket). | S | AH-C | `deployment/ci/scripts/start_e2e_stack.sh`, `frontend/e2e/...` |
| AH-E | **Docs + observability.** Update `api/CLAUDE.md` with the new env-var matrix + the trusted-hops model, **including the GLB re-verification runbook entry per §4.3** (the operator must bump `KENE_RATE_LIMIT_TRUSTED_HOPS=2` if a Global LB is ever added in front of Cloud Run — this is the acceptance bar for the trusted-hops concern). Add a one-paragraph "Rate limiting" subsection to `docs/design/components/agentic-harness/README.md` §2 + §7 (Conventions and Constraints). Emit a structured log (INFO) when `_validated_ip_key` falls back due to fewer X-Forwarded-For hops than expected — gives ops visibility into chain-config drift. | S | AH-C (D can run in parallel) | `api/CLAUDE.md`, `docs/design/components/agentic-harness/README.md`, `api/src/kene_api/rate_limiter.py` |

## 6. API contract

### 6.1 `RateLimiter` constructor (backward-compatible)

```python
class LocalRateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 10,
        requests_per_hour: int = 100,
        key_strategy: KeyStrategy = ip_only_key_strategy,
        limiter_name: str = "default",
        audit_logger: AuditLogger | None = None,  # §6.4 — limiter owns the 429 audit call
    ) -> None: ...

    async def check_rate_limit(
        self,
        request: Request,
        ctx: UserContext | None = None,
    ) -> None: ...
```

### 6.2 `RedisRateLimiter` constructor (new)

```python
class RedisRateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        requests_per_hour: int,
        redis_client: Redis,
        key_strategy: KeyStrategy,
        limiter_name: str,
        key_prefix: str = "kene:ratelimit",
        audit_logger: AuditLogger | None = None,  # §6.4 — limiter owns the 429 audit call
    ) -> None: ...

    async def check_rate_limit(
        self,
        request: Request,
        ctx: UserContext | None = None,
    ) -> None:
        """Same semantics + raise shape as LocalRateLimiter — HTTPException(429) on exceed."""
```

### 6.3 Factory helper

```python
def build_rate_limiter(
    name: str,
    requests_per_minute: int,
    requests_per_hour: int,
    key_strategy: KeyStrategy = ip_only_key_strategy,
) -> LocalRateLimiter | RedisRateLimiter:
    """Reads KENE_RATE_LIMIT_BACKEND and returns the correct concrete limiter."""
```

All existing call sites (`auth/user_context.py:297` + the live limiter instances) migrate to the factory; the 429 response shape (`HTTPException(status_code=429, detail="...", headers={"Retry-After": "..."}))`) is unchanged.

### 6.4 Audit-logger threading (Option A — limiter owns the audit call)

**Decision (resolves Ken review Comment 5):** the limiter holds an optional `audit_logger` and fires `AuditLogger.log_rate_limit_exceeded` **itself** on every 429, rather than relying on each call site to wrap the check. This satisfies AC-16 uniformly across every wired limiter with no external wrapper and no per-call-site divergence — chosen over Option B (keep the external `_apply_rate_limiting` wrapper) because the recaptcha path never went through that wrapper.

The existing signature (`auth/audit_logger.py:181`) is unchanged:

```python
async def log_rate_limit_exceeded(
    self,
    ip_address: str,
    endpoint: str | None = None,
    user_id: str | None = None,
) -> None: ...
```

Threading inside the limiter on a 429:
- `ip_address` ← the IP from the same `_validated_ip_key(request)` derivation (always available, even for user-keyed limiters).
- `endpoint` ← `request.url.path`.
- `user_id` ← `ctx.user_id` when a `UserContext` was supplied, else `None`.

This closes the current gap where `recaptcha_rate_limiter.check_rate_limit(request)` at `routers/auth.py:53` raises 429 **without** any audit-log entry — it bypasses `_apply_rate_limiting`, which is the only place audit logging happens today (`user_context.py:54`/`:96`). After the rework the recaptcha limiter carries its own `audit_logger` and logs uniformly; AH-C removes the now-redundant external `_apply_rate_limiting` audit call to avoid double-logging. `AuditLogger` is imported from `api/src/kene_api/auth/audit_logger.py`.

## 7. Acceptance criteria

1. **NAT'd-user case is fixed.** Two test users (different `firebase_uid`) sharing the same egress IP can each issue up to `requests_per_minute` requests without affecting the other's bucket. Verified by integration test against real Redis.
1a. **Per-user limits are additive, not capped.** 5 distinct authenticated users on the same IP collectively issue `5 × requests_per_minute` requests in a minute without any 429. Verified by integration test. (Catches the regression where someone re-introduces an IP-level cap on top of the per-user buckets.)
2. **E2E parallel-requests case is fixed.** Concurrent Playwright requests from different test-user logins don't share a bucket; the CH-54 `KENE_TOKEN_RATE_LIMIT_PER_MINUTE=10000` override is removed from `start_e2e_stack.sh` and CI stays green at the canonical 60/min default.
3. **Authenticated vs unauthenticated split is enforced.** Auth/password-reset/recaptcha limiters stay IP-keyed (no behavioral change for brute-force-defense use case); token/progress limiters use the user-keyed strategy with IP-fallback for unauthenticated requests that somehow reach them.
4. **Cross-instance consistency.** A request that exceeds the limit on Cloud Run instance A is also blocked on instance B within the same window. Verified by integration test that sends N+1 requests across two simulated instances against shared Redis.
5. **`X-Forwarded-For` spoofing is blocked.** A request with a hand-crafted `X-Forwarded-For` longer than `trusted_proxy_hops` is keyed off the validated source IP, not the spoofed prefix. Verified by unit test.
6. **Backward compatibility.** Existing env vars (`KENE_TOKEN_RATE_LIMIT_PER_MINUTE` / `KENE_TOKEN_RATE_LIMIT_PER_HOUR`) continue to work without code changes to deploys. Existing 429 response shape is byte-identical.
7. **Local-dev path works without Redis.** `KENE_RATE_LIMIT_BACKEND=memory` keeps the `LocalRateLimiter` path; unit tests + dev server boot without a Redis connection.
8. **Observability.** Trusted-hops-fallback events emit a structured INFO log; rate-limit-exceeded events emit a structured WARNING log with `limiter_name`, `client_key`, `window`. (No PII beyond the UID/IP that's already in the bucket key.) Prometheus counters (`ratelimit_429_total{limiter_name}`, `ratelimit_redis_errors_total{limiter_name}`, `ratelimit_local_fallback_total{limiter_name}`) are exposed via the existing `api/src/kene_api/metrics/` pattern (matches `oauth_metrics.py`).
   - The `authenticated_key_strategy` ctx-None fallback (a user-keyed limiter that received no `UserContext`) emits a structured **WARNING** log with the request path, so a regression that applies a user-keyed limiter before context resolution is not silent. Verified by unit test asserting the log fires on a ctx-None call. (Ken review Comment 4.)
9. **Response headers on every limited response.** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` are set on 200 OK responses; `Retry-After` (with the accurate seconds-until-bucket-frees value, not a fixed 60) is set on 429. Verified by integration test against real Redis.
10. **Security-critical limiter fail-closed behavior.** When Redis is unavailable, `auth_rate_limiter`, `password_reset_rate_limiter`, and `recaptcha_rate_limiter` fall back to the in-process `LocalRateLimiter` (preserves per-instance brute-force defense). `token_rate_limiter` and `progress_rate_limiter` fail-open. Verified by integration test that injects Redis ConnectionError.
11. **Feature-flag rollback path.** The `KENE_RATE_LIMIT_BACKEND` env var is mirrored by a feature flag (`rate_limit_backend_override` in the existing `feature_flags` Firestore collection) so an operator can flip the active backend (redis ↔ memory) without a redeploy. Verified by integration test that toggles the flag at runtime and observes the active limiter switch within the next request. Implementation: the flag is read PER-REQUEST inside `SwitchableRateLimiter.check_rate_limit` — NOT at `build_rate_limiter` startup time (resolves architect Critical #2).
12. **Flag-flip audit + alert.** Every write to `rate_limit_backend_override` emits a CRITICAL audit-log entry via `AuditLogger` with actor identity + previous value + new value, AND fires a Cloud Monitoring alert. Verified by integration test that toggles the flag and asserts both side effects. (v4 correction K — security High #1.)
13. **Emergency cap during Redis-outage fallback.** When `auth_rate_limiter` / `bad_token_rate_limiter` / `password_reset_rate_limiter` / `recaptcha_rate_limiter` fall back to in-process `LocalRateLimiter`, the configured limits are divided by 10 (e.g. `auth_rate_limiter` 10/min becomes 1/min per instance). Verified by fault-injection test that asserts the divided limit applies during fallback. (v4 correction H — security High #2.)
14. **Circuit breaker for Redis errors.** `SwitchableRateLimiter` tracks consecutive Redis errors; after K=10 errors the circuit opens (skip Redis, go straight to LocalRateLimiter fallback) for 60s; on re-close, one probe request goes through. Verified by fault-injection test that confirms the K-th error switches to fallback without invoking Redis. (v4 correction I — security High #3.)
15. **No `request.client.host` fallback on Cloud Run.** When X-Forwarded-For chain is shorter than `KENE_RATE_LIMIT_TRUSTED_HOPS`, `_validated_ip_key` returns `ip:_no_xff_chain_` sentinel + emits a WARNING log (not INFO). Verified by unit test that asserts the sentinel + log on a short-chain request. (v4 correction G — security High #4.)
16. **AuditLogger extended to all 429 sites.** `AuditLogger.log_rate_limit_exceeded` is invoked from EVERY 429-emission site — not just `_apply_rate_limiting`. Includes `recaptcha_rate_limiter.check_rate_limit` at `routers/auth.py:53`. Verified by integration test that asserts a Firestore `security_audit_logs` write per 429 event. (v4 correction J — security High #5.)
17. **6th limiter `bad_token_rate_limiter` separates bad-token brute-force ceiling from authenticated-throughput ceiling.** New 10/min, 50/hour IP-keyed limiter applied at the `_verify_and_decode_token` exception path (`user_context.py:~93`); the bad-token failure mode no longer falls through to `token_rate_limiter`'s 60/min IP-fallback ceiling. Verified by integration test that submits 11 bad Firebase tokens from one IP → 11th gets 429. (v4 correction C — security Critical #1.)
18. **Adversarial UID handling.** Unit tests cover UID injection attempts: UIDs containing `:`, UIDs with unicode, 1KB-length UIDs, empty-string UID. All produce non-colliding distinct `kene:ratelimit:{}:{}:uid:<hash>` keys via the sha256 hashing per §4.2. (v4 correction E — security Critical #3.)
19. **Shared sentinel bucket is self-bounding.** Requests that fall into the `ip:_no_xff_chain_` sentinel (X-Forwarded-For chain shorter than `KENE_RATE_LIMIT_TRUSTED_HOPS`) are additionally capped by a single shared `kene:ratelimit:_sentinel_` bucket at 5/min across all sentinel hits regardless of which limiter is reporting, checked *before* the per-limiter check. Verified by integration test: 6 sentinel-keyed requests in a minute → the 6th gets a 429 even when each individual limiter's threshold is higher. (Ken review Comment 3.)

## 8. Test plan

### Unit (no Redis)
- `LocalRateLimiter` regression tests — every existing test continues to pass after the `class` rename. New tests for `key_strategy` injection.
- `_validated_ip_key` table-driven tests for X-Forwarded-For parsing: 0 hops, 1 hop, 2 hops, spoofed prefix, empty header, malformed entries.
- `authenticated_key_strategy` returns `uid:...` when ctx is present, falls back to `ip:...` when ctx is None.

### Integration (Redis emulator)
- `RedisRateLimiter` sliding-window correctness — exactly `requests_per_minute` allowed in 60s, 1 extra blocked, then unblocked after the window slides.
- ZSET key TTL is set to `window + 60` and the key expires when nothing's written for that long.
- Two `RedisRateLimiter` instances pointing at the same Redis share state correctly (validates AC-4).
- Atomic check-and-add Lua script — no race when 10 concurrent requests arrive in the same tick.

### E2E
- DM-104 e2e flake regression: parallel Playwright runs from different test-user logins all stay green at 60/min default; no shared bucket. (Run 3 times back-to-back to prove flake elimination.)
- `KENE_RATE_LIMIT_BACKEND=memory` in dev: API server boots, accepts requests, rate-limits correctly without a Redis connection.

### Manual (one-time, post-deploy)
- Staging-deploy + verify the limiter logs show user-keyed buckets (uid prefix) for authenticated requests and ip-keyed buckets for `/auth/login`. Spot-check on Cloud Logging.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Redis outage takes down the rate limiter | **Per-limiter behavior** (not universal fail-open as v1 of this PRD proposed). Throughput limiters (`token`, `progress`) fail-open — allow request + log ERROR. Security-critical limiters (`auth`, `password_reset`, `recaptcha`) fall back to in-process `LocalRateLimiter` — preserves per-instance brute-force defense (N×limit/min across N instances >> zero protection). Feature flag for instant rollback to memory backend if Redis-backed path misbehaves. |
| `fakeredis` is not currently a CI fixture | AH-PRD-10 #2 adds `fakeredis` as a dev dependency + the corresponding `pytest` fixture in `api/tests/conftest.py`. Integration tests reuse the existing `pytest.mark.integration` marker. ~30 lines of setup. |
| ZSET cardinality blow-up if user-keyed unbounded | TTL on the bucket key (window + 60s) ensures stale buckets auto-expire. Total active keys ≤ active users × 6 limiters × 2 windows (the 2 dormant limiters write no keys until wired, so this is a conservative upper bound); even at 100K MAU that's ~1M keys with ~hour TTL — well within Memorystore Standard tier limits. |
| Cold-start cost of the first Redis round-trip | Reuses the existing Redis client pool; first call cost is ~5ms for a single ZADD + EXPIRE, dominated by serialization. Acceptable on the auth path (already ~50ms total). |
| `trusted_proxy_hops` mis-configured for non-Cloud-Run deploys | Default is 1 (Cloud Run); env var override per environment. Structured INFO log fires when the actual chain length doesn't match expected, surfacing config drift. |
| Existing in-flight CH-54 env-var consumers (e.g. local-dev scripts) break | AH-D's CI-script update is gated behind the user-keyed AC-2 verification; if e2e flakes return, revert that one PR and re-investigate. The env vars themselves stay supported. |
| Race between AH-PRD-09 (in flight) touching `auth/user_context.py` and this PRD's AH-C call-site update | AH-PRD-09 Phases 2–3 don't touch `user_context.py:297`. Coordinate with AH-PRD-09 owner if either Phase 4 or Phase 5 starts pulling on that file. |
| Deploy window — some Cloud Run instances run the old in-memory limiter while others run the new Redis-backed one during the rolling deploy | The dual-generation window is **not** sub-30s in the general case (Ken review Comment 6): Cloud Run rolling deploys can run several minutes when min-instance retention, slow startup probes, or high instance counts are in play — measure the real median per-service via `gcloud run services describe kene-api-{env}` + recent rollout history rather than assuming a number. During the window the two generations don't share state, so a user could briefly get up to 2×limit. **Operator mitigation that eliminates the double-dip entirely:** set `KENE_RATE_LIMIT_BACKEND=memory` *first* (forces every instance — old binary and new — onto `LocalRateLimiter`), let the deploy complete, then flip the flag to `redis`. This cutover sequence is documented in the AH-C / AH-D rollout notes. Absent the mitigation, the brief 2×limit is still acceptable for a non-revenue-critical limiter on a service with no live customers. |
| Memorystore tier capacity under rate-limiter additional load | ~3 Redis ops per check (ZADD + ZREMRANGEBYSCORE + ZCARD via the atomic Lua script). At 1K req/sec, that's 3K Redis ops/sec — well within Memorystore Standard tier's ~10K ops/sec ceiling. No tier upgrade needed for this PRD's scope. |
| Implementation defect: sync `redis.Redis` called from async path blocks the event loop | AH-PRD-10 #2 explicitly uses `redis.asyncio.Redis` (the `redis-py` async client) for the new `RedisRateLimiter` — NOT the existing sync `redis_client.py` pool. The PRD §2 Scope section calls this out. Existing sync client stays in place for non-async consumers (no migration of those). |
| Inducible Redis outage as a DoS escalator — attacker DoSes Memorystore to trigger fail-open on `token_rate_limiter` / `progress_rate_limiter` and to weaken `auth_rate_limiter` to N×limit/min | Three layers of defense: (1) circuit breaker (v4 I) — limiter switches to fallback after K=10 consecutive Redis errors, avoiding cascading per-request Redis retries that amplify the attack; (2) emergency cap (v4 H) — security-critical limiters' effective ceiling drops by 10× during fallback; (3) Memorystore is VPC-internal, so externally-induced Redis outage requires an attacker with VPC-internal network access — already a much-higher attack-difficulty bar. |
| Flag-flip is a single-toggle path to disable all rate limiting | Every write to `rate_limit_backend_override` emits a CRITICAL audit-log entry + Cloud Monitoring alert (AC-12). Write access is restricted to super-admin via the existing feature-flag admin UI permission model. A compromised super-admin remains a higher-impact problem than this specific defense, but the audit trail gives ops the signal to revert. |
| AC-6 "byte-identical" 429 response shape is incompatible with the new X-RateLimit-* headers | AC-6 scoped to **response body byte-identical**; new headers are additive-only. Clients that don't honor the new headers see the same behavior as today; clients that DO honor them get accurate `Retry-After`. (Architect Suggestion S-3.) |

### Open questions

- **Q: Does any external system rely on the existing IP-keyed behavior as a coarse abuse-detection signal?** Need a quick survey of the API logs to confirm no one's parsing the 429 response shape with an IP-key assumption. **Defer to AH-A's first comment-thread review.**
- **Q: Should `progress_rate_limiter` (120/min, 2000/hour for polling) move to authenticated-keyed even though some polling endpoints may be unauthenticated?** Need an audit of `progress_rate_limiter` call sites. **Defer to AH-C scoping.**
- **Q: What's the right way to test the feature-flag rollback path in CI?** The flag toggle happens at runtime, but integration tests bring up a fresh app instance. **Defer to AH-PRD-10 #5 — likely a fixture that pre-toggles before the test request.**
- **Q: Delete the two dormant limiters (`auth_rate_limiter`, `password_reset_rate_limiter`) or keep them dormant-but-migrated?** Both are dead code today (no server-side login/reset endpoint — see §3.1). Keeping them migrated costs ~nothing and leaves the substrate ready; deleting them removes misleading "security-critical" framing. **Defer to AH-A's first comment-thread review** — a small reversible call that doesn't block the project. (Ken review Comment 1.)

## 10. Reference

- **Tactical predecessor:** CH-54 in [PR #665](https://github.com/KEN-E-AI/KEN-E/pull/665) — made thresholds env-configurable; documented as tactical only. This PRD is the architectural follow-up Ken called for in his 2026-05-27 message.
- **Visible failure mode:** DM-104 (CI flake trio triage; deferred work) covers the e2e Playwright flake half of this issue's symptom set. This PRD ships the structural fix; DM-104 still owns the other two flakes (lychee, bigtable).
- **Current source files (pre-rework):**
  - `api/src/kene_api/rate_limiter.py` — the `RateLimiter` class to be split + extended (also defines `recaptcha_rate_limiter` + `progress_rate_limiter`).
  - `api/src/kene_api/auth/rate_limiting.py` — defines `auth` (dormant), `token` (live), `password_reset` (dormant) limiters.
  - **Call sites:** see the §3.1 inventory for the authoritative live/dormant/new breakdown (`user_context.py:297`, `dependencies.py:260`, `routers/auth.py:53`).
  - `deployment/ci/scripts/start_e2e_stack.sh` — the CH-54 tactical env-var overrides to be removed in AH-D.
- **Component README convention to update (AH-E):** `docs/design/components/agentic-harness/README.md` §2 (architecture diagram should add the rate-limit gate), §7 (Conventions and Constraints — new "Rate limiting" subsection).
- **Sibling PRDs (informational, no dependency):** AH-PRD-09 (per-turn dispatch — touches `app/adk/agents/`, not the API middleware; no overlap).
