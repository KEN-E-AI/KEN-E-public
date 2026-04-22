# FF-PRD-01 — Data Model, Evaluation API, Backend SDK

**Status:** Ready to start
**Owner team:** Platform / Backend
**Blocked by:** — (component-entry project)
**Parallel with:** DM-PRD-00–06, AH-PRD-01, UI-PRD-01
**Blocks:** FF-PRD-02, FF-PRD-03
**Estimated effort:** 3–4 days

---

## 1. Context

Foundation project for the Feature Flags component. Produces the schema, the evaluation engine, and the Python helper that every backend caller — and indirectly every frontend caller, via the evaluate endpoint — depends on. No admin UI and no React hook ship in this PRD; both are downstream projects that consume what this one publishes.

The only architectural decisions made here that others inherit are (a) the targeting-rule precedence ladder, (b) the bucketing-entity choice (`account` default, `user` / `organization` opt-in), and (c) the evaluation-API contract. Once merged, FF-PRD-02 and FF-PRD-03 can start in parallel against the published Pydantic models.

See [`../README.md`](../README.md) §2 Architecture and §7 Conventions for the component-level design.

## 2. Scope

### In scope
- Pydantic models for `FeatureFlag`, `TargetingRules`, `EvaluationContext`, `FlagEvaluation`, `EvaluateRequest`, `EvaluateResponse`
- `FeatureFlagService` with `evaluate_batch(flag_keys, ctx) → dict[str, FlagEvaluation]`, evaluator, and in-process LRU cache (60 s TTL, keyed by `flag_key`)
- `is_feature_enabled(flag_key, ctx, default=False) → bool` ergonomic helper for routers/services
- Deterministic bucketing: `hash_bucket(flag_key, entity_id) → int` (0–99, sha256-based)
- `POST /api/v1/feature-flags/evaluate` authenticated endpoint
- `feature_flags/{flag_key}` + `feature_flag_audit/{audit_id}` Firestore collections (collections themselves — docs added by FF-PRD-02)
- One composite index on `feature_flag_audit` (`flag_key ASC, created_at DESC`) in `deployment/firestore.indexes.json`
- Unit tests for evaluator precedence, hashing, and cache behavior
- Integration tests against the Firestore emulator for the evaluate endpoint

### Out of scope
- Any admin / CRUD endpoints — owned by FF-PRD-02
- React hook, provider, dev URL-override — owned by FF-PRD-03
- Audit writer — owned by FF-PRD-02 (this PRD lands the collection + index only; no writes)
- Multi-variant flags, JSON flags, scheduled rollouts, experimentation analytics

## 3. Dependencies

- Existing `UserContext` and `get_current_user` dependency in `api/src/kene_api/auth/` — source of `user_id`, `email`, `organization_permissions`, `account_permissions`
- Existing Firestore client via `api/src/kene_api/firestore.py`
- Existing `@pytest.fixture` for the Firestore emulator (`api/tests/conftest.py`)
- Root `CLAUDE.md` §PY-1…PY-7, §D-1…D-5 apply

## 4. Data contract

### Pydantic models (`api/src/kene_api/models/feature_flag_models.py`)

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

FLAG_KEY_REGEX = r"^[a-z0-9][a-z0-9-]{2,63}$"

class TargetingRules(BaseModel):
    user_emails: list[str] = Field(default_factory=list)
    email_domains: list[str] = Field(default_factory=list)
    organization_ids: list[str] = Field(default_factory=list)
    account_ids: list[str] = Field(default_factory=list)
    rollout_percentage: int = Field(default=0, ge=0, le=100)

    @field_validator("user_emails", "email_domains")
    @classmethod
    def _lowercase(cls, v: list[str]) -> list[str]:
        return [s.lower() for s in v]

class FeatureFlag(BaseModel):
    key: str = Field(pattern=FLAG_KEY_REGEX)
    description: str
    default_enabled: bool
    is_active: bool = True
    targeting_rules: TargetingRules = Field(default_factory=TargetingRules)
    bucketing_entity: Literal["account", "organization", "user"] = "account"
    owner: str
    expected_ga_release: str | None = None
    created_at: datetime
    updated_at: datetime

class EvaluationContext(BaseModel):
    user_id: str
    user_email: str
    organization_id: str | None
    account_id: str | None

class FlagEvaluation(BaseModel):
    key: str
    enabled: bool
    reason: Literal[
        "kill_switch", "email_match", "domain_match",
        "org_match", "account_match", "rollout", "default", "unknown_flag",
    ]

class EvaluateRequest(BaseModel):
    flag_keys: list[str] = Field(min_length=1, max_length=100)

class EvaluateResponse(BaseModel):
    evaluations: dict[str, FlagEvaluation]
```

### Evaluation algorithm (reference implementation)

```python
def evaluate(flag: FeatureFlag, ctx: EvaluationContext) -> FlagEvaluation:
    if not flag.is_active:
        return FlagEvaluation(key=flag.key, enabled=flag.default_enabled, reason="kill_switch")

    rules = flag.targeting_rules
    email = ctx.user_email.lower()

    if email in rules.user_emails:
        return FlagEvaluation(key=flag.key, enabled=True, reason="email_match")

    domain = email.split("@", 1)[-1] if "@" in email else ""
    if domain and domain in rules.email_domains:
        return FlagEvaluation(key=flag.key, enabled=True, reason="domain_match")

    if ctx.organization_id and ctx.organization_id in rules.organization_ids:
        return FlagEvaluation(key=flag.key, enabled=True, reason="org_match")

    if ctx.account_id and ctx.account_id in rules.account_ids:
        return FlagEvaluation(key=flag.key, enabled=True, reason="account_match")

    if rules.rollout_percentage > 0:
        entity_id = {
            "account": ctx.account_id,
            "organization": ctx.organization_id,
            "user": ctx.user_id,
        }[flag.bucketing_entity]
        if entity_id and hash_bucket(flag.key, entity_id) < rules.rollout_percentage:
            return FlagEvaluation(key=flag.key, enabled=True, reason="rollout")

    return FlagEvaluation(key=flag.key, enabled=flag.default_enabled, reason="default")


def hash_bucket(flag_key: str, entity_id: str) -> int:
    import hashlib
    digest = hashlib.sha256(f"{flag_key}:{entity_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100
```

### API contract

```
POST /api/v1/feature-flags/evaluate
Auth: Firebase JWT (any authenticated user)
Request: { "flag_keys": ["new-ui", "automations-beta"] }
Response:
  200 {
    "evaluations": {
      "new-ui":          { "key": "new-ui",          "enabled": true,  "reason": "domain_match" },
      "automations-beta":{ "key": "automations-beta","enabled": false, "reason": "default" }
    }
  }
  422 Validation error (flag_keys empty or > 100 entries)
```

The server constructs `EvaluationContext` from the authenticated user — callers **cannot** pass context in the request body.

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/feature_flag_models.py` |
| Create | `api/src/kene_api/services/feature_flag_service.py` — service class, evaluator, LRU cache, hash_bucket, `is_feature_enabled` helper |
| Create | `api/src/kene_api/routers/feature_flags.py` — `POST /evaluate` endpoint |
| Modify | `api/src/kene_api/main.py` — register the new router |
| Modify | `deployment/firestore.indexes.json` — add `feature_flag_audit (flag_key ASC, created_at DESC)` |
| Create | `api/tests/unit/test_feature_flag_evaluator.py` |
| Create | `api/tests/unit/test_feature_flag_hash_bucket.py` |
| Create | `api/tests/integration/test_feature_flag_evaluate_endpoint.py` |
| Modify | `api/CLAUDE.md` — add short "Feature Flags" section with helper usage + kill-switch runbook |

### 5.1 Cache invalidation

Cache is keyed by `flag_key` and holds the resolved `FeatureFlag` (not an evaluation). Entries expire 60 s after write. No manual invalidation API in Release 1 — FF-PRD-02's admin writes rely on TTL-based propagation. Document the ≤60 s kill-switch SLO in `api/CLAUDE.md`.

### 5.2 `is_feature_enabled` ergonomics

```python
# Usage in a router:
from kene_api.services.feature_flag_service import is_feature_enabled

if await is_feature_enabled("automations-beta", user_context):
    # new path
else:
    # old path
```

The helper catches every exception raised by the service and returns the `default` argument (default `False`). A flag-system outage must never take down a caller.

## 6. API contract

See §4 — `POST /api/v1/feature-flags/evaluate`.

## 7. Acceptance criteria

1. `FeatureFlag`, `TargetingRules`, `EvaluationContext`, `FlagEvaluation`, `EvaluateRequest`, `EvaluateResponse` Pydantic models exist in `feature_flag_models.py` and match §4.
2. `FLAG_KEY_REGEX` is enforced on both create (422 on invalid key) and read (validation error surfaces the malformed doc) paths.
3. `hash_bucket(flag_key, entity_id)` is deterministic (unit test seeds 10 `(key, id)` pairs and asserts stable output across 1 000 invocations) and returns `0 ≤ n ≤ 99`.
4. Evaluator precedence matches the ladder in `../README.md` §7.2. Unit tests cover every branch including kill switch, email/domain/org/account match, rollout hit, rollout miss, and default fallback.
5. Rollout falls through to `default_enabled` when the `bucketing_entity_id` is missing from the context (e.g., `bucketing_entity="account"` but `account_id=None`).
6. `FeatureFlagService.evaluate_batch` returns one `FlagEvaluation` per requested key; unknown keys return `reason="unknown_flag", enabled=false`.
7. `is_feature_enabled(key, ctx)` returns the boolean from the service; if the service raises, the helper returns the `default` argument (default `False`).
8. In-process cache serves a second read for the same `flag_key` within 60 s without a Firestore round-trip (verified by counting Firestore client calls in the integration test). After 60 s, the cache reloads.
9. `POST /api/v1/feature-flags/evaluate` requires Firebase auth (401 without token). Authenticated users get back evaluations for their own context only; body cannot override `user_id` / `organization_id` / `account_id` (server ignores those fields if the client sends them).
10. The endpoint rejects requests with `flag_keys=[]` or `len(flag_keys) > 100` with a 422.
11. The new composite index appears in `deployment/firestore.indexes.json` and Terraform apply in dev shows it `READY` (operator-verified).
12. `api/CLAUDE.md` has a new "Feature Flags" section linking to the component README and documenting the kill-switch SLO.
13. `make lint` passes. All unit + integration tests pass via `pytest api/tests/`.

## 8. Test plan

### Unit tests (`api/tests/unit/`)

- `test_feature_flag_evaluator.py`:
  - kill switch returns `default_enabled` regardless of rules
  - email / domain / org / account allowlist paths (case-insensitive)
  - `bucketing_entity="account"` + matching account in rollout → `enabled=true, reason="rollout"`
  - `bucketing_entity="account"` + missing `account_id` → falls through to `default`
  - `bucketing_entity="user"` + 50% rollout → same user ID always hashes to the same bucket (determinism)
  - precedence: email match wins over rollout (test sets both and expects `reason="email_match"`)
  - unknown key returns `reason="unknown_flag", enabled=false`
- `test_feature_flag_hash_bucket.py`:
  - return value in `[0, 99]` for 10 000 random `(key, id)` pairs
  - same `(key, id)` → same bucket across 1 000 repeat calls
  - different keys produce different distributions for the same entity ID (spot-check 3 keys)

### Integration tests (`api/tests/integration/`)

- `test_feature_flag_evaluate_endpoint.py`:
  - seed `feature_flags/test-flag` in emulator with `targeting_rules.email_domains=["ken-e.ai"]`
  - call `POST /evaluate` with a `@ken-e.ai` token → `enabled=true, reason="domain_match"`
  - call `POST /evaluate` with a non-`@ken-e.ai` token → `enabled=false, reason="default"`
  - unauthenticated call → 401
  - `flag_keys=[]` → 422; `flag_keys=[<101 entries>]` → 422
  - client attempts to inject `user_id` / `account_id` in the body → server ignores them (test verifies evaluation uses the token's identity, not the body)
  - cache behavior: two successive calls for the same key issue exactly one Firestore read within 60 s

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Cache-coherence across Cloud Run instances — a kill-switch flip may take up to 60 s to fully propagate while old cache entries age out on every instance | Accept the 60 s SLO for Release 1; document in the runbook. If engineering needs tighter guarantees later, add a Firestore listener or Redis pub/sub (follow-up PRD). |
| A flag-system outage (Firestore unreachable) could block every caller that uses `is_feature_enabled` | `is_feature_enabled` catches all exceptions and returns the `default` argument. Service-level retries are not added — `default=False` is the safe floor. |
| Targeting on `user_email` / `email_domains` might leak PII into logs if we aren't careful | Do not log the evaluation context at `INFO` or above. Structured-log only the `flag_key` + `reason` in the evaluate endpoint. |
| `hash_bucket` collisions across flags for the same entity | Negligible because we salt with `flag_key`. Verified in unit tests. |
| A developer bucketing on `user` instead of `account` by mistake produces flickering behavior for multi-account users | Default the model field to `"account"` and surface a prominent tooltip in FF-PRD-02's admin UI. |

### Open questions

- **Q:** Should the evaluate endpoint include the server-resolved evaluation context in the response (for debugging)? → **Default: no.** Callers know their own identity. Adding it invites clients to depend on the payload.
- **Q:** Should we ship a Firestore-listener-based cache invalidation in Release 1? → **Default: no.** 60 s TTL is the SLO we're committing to; listener-based invalidation is a targeted upgrade if pain emerges.

## 10. Reference

- Parent component: [`../README.md`](../README.md) §2, §7
- Sibling PRDs: [FF-PRD-02](./FF-PRD-02-admin-api-and-ui.md), [FF-PRD-03](./FF-PRD-03-frontend-sdk-and-e2e.md)
- Root `CLAUDE.md` — §PY-1…PY-7 (Python), §D-1…D-5 (Database), §T-1…T-8 (Testing), §G-1 (Lint)
- `api/CLAUDE.md` — Firestore access patterns, super-admin auth
- Notion Design Decision — [Feature Flag Targeting Model](https://www.notion.so/<TBD>) (to be created alongside this PRD set)
