# SE-PRD-05 — Target Derivation Specialist

**Status:** Blocked — resumes once SE-PRD-03, SE-PRD-04, and AH-PRD-02 ship
**Owner team:** SAR-E component team + Agentic Harness liaison (backend)
**Blocked by:** SE-PRD-03 (`Baseline` reads for the `get_baseline` tool); SE-PRD-04 (`/scenarios` reads for scenario evaluation tooling); AH-PRD-02 (agent factory assembles the `performance_forecasting` specialist from `agent_configs/performance_forecasting` — this PRD is the first factory-built narrow specialist in the SAR-E component)
**Blocks:** SE-PRD-06 (analytical queries surface the specialist's methodology-note field); SE-PRD-07 (end-to-end + A/B harness); PE-PRD-03 (Simulations tab's Run → Save-as-Targets flow); PE-PRD-06 (Targets tab drill-down)
**Estimated effort:** 4 days

---

## 1. Context

Baselines tell users what the funnel is likely to do if they change nothing. Targets tell users what to aim for given the activities they've planned. The difference is reasoning: "Consideration is baselined at 12k weekly views; you have the summer promotion in week 5 that historically lifted Consideration by 20-40%; a reasonable target is 15k for weeks 5-8." That reasoning is an LLM specialist call, not a statistical function.

This PRD delivers the specialist, the tools it uses, the Target data model, and the CRUD API behind it. Four facts shape the design:

1. **Reasoning belongs to the specialist; math belongs to SAR-E's stats code.** The specialist (`performance_forecasting`, Gemini 2.0 Pro via Vertex AI) reads the baseline, reads the calendar, reads historical "pulses" (prior promotion / holiday weeks with measured lift), optionally evaluates 1–3 scenarios via SE-PRD-04's `/scenarios` endpoint, and proposes per-KPI-per-week `Target` values with `reasoning` + `methodology_note`. It never computes forecasts itself; those are tool outputs.
2. **"Statistical association only" is an invariant.** The specialist's system prompt forbids the words `caused`, `because`, `due to` (and variants), requires every Target to include a `methodology_note` phrasing the relationship as association / correlation, and is schema-validated to reject responses missing the field. SE-PRD-07's methodology audit greps the codebase for the banned phrases; the specialist's `response_schema` enforces shape.
3. **Targets supersede on edit — no version history.** `POST /targets` and `PATCH /targets/{id}` with a conflicting `(kpi_id, period)` overwrite the prior target; an audit entry records the before/after. This is in contrast to `FunnelStageMapping` (SE-PRD-01), which retains version history — mapping changes alter interpretation of historical data, Target changes do not. Implementation-plan §10 resolves this; PE-PRD-03's Simulations "Save Forecast as Targets" flow depends on it.
4. **Idempotency on `derivation_context_hash`.** The specialist's output is deterministic given `{baseline_snapshot, calendar_snapshot, historical_pulses_snapshot}`. Hashing these inputs lets us dedupe repeat derivation requests (e.g., a user opens Simulations → clicks Run, closes, reopens → clicks Run again with no changes) without paying Gemini Pro twice. The hash is stored on each derived Target; a second `POST /targets/derive` with the same hash returns the previously derived payload (from an in-process cache with 10-minute TTL).

## 2. Scope

### In scope

- **`performance_forecasting` Firestore agent config** at `agent_configs/performance_forecasting`:
  - `model: "gemini-2.0-pro"`
  - `temperature: 0.2` (deterministic reasoning)
  - `instruction: InstructionProvider` that loads the system prompt from `app/adk/agents/performance_forecasting/system_prompt.py` and injects organization context per AH-PRD-02's pattern
  - `description: "Derives per-KPI-per-week Target values by comparing the VAR baseline against planned calendar activities and historical similar periods. Used by the Performance Simulations tab."` (root agent uses this for routing — see AH-PRD-02 §5)
  - `mcp_servers: []` (no MCP — tools are local function tools)
  - `response_schema: DerivedTargetsResponse` (strict JSON-schema validation at the ADK layer)
  - `code_execution_enabled: false`
  - `skill_ids: []`, `sandbox_code_executor_enabled: false` (forward-compat fields from AH-PRD-02, not used here)
  - `available_to_copy: false` (internal specialist; not forkable)
  - `automatically_available: true`
  - `visible_in_frontend: false` (managed centrally; not on Workflows > Agents)
- **Tool module** `app/adk/agents/performance_forecasting/tools.py` with four `FunctionTool`-wrapped functions:
  - `get_baseline(kpi_ids: list[str]) -> dict[str, list[ForecastPoint]]` — reads `Baseline.horizon` for the requested KPIs via the Performance API's internal `/forecasts/baseline` surface (cached per-call via tool_context)
  - `get_calendar_summary(start_week: date, end_week: date) -> CalendarSummary` — reads project-tasks Calendar activities in the window; returns totals + categorized lists (`tasks`, `campaigns`, `holidays`, `promotions`, `events`) from PR-PRD-07's category field
  - `get_historical_pulses(objective: FunnelObjective, lookback_weeks: int = 52) -> list[HistoricalPulse]` — finds prior weeks in the account's history where the mapped KPI deviated meaningfully from its contemporaneous forecast (threshold: ≥1.5σ lift or drop); annotates each with the overlapping Calendar category (if any); returns up to 20 pulses ordered most-recent-first
  - `save_targets(targets: list[DerivedTarget]) -> SaveTargetsResult` — **advisory only**; flagged by a `dry_run=True` default — the specialist cannot persist targets directly. The specialist's job is to produce the `DerivedTarget` list in its structured response; the HTTP handler of `/targets/derive` decides whether and how to persist. This tool is retained for symmetry + future use but no-ops in v1.
- **Target data model** in `api/src/kene_api/models/sar_e_models.py`:
  - `DateRange { start: date, end: date }` — inclusive; for weekly-scoped targets `start == Monday; end == Sunday`
  - `Target { target_id, account_id, kpi_id, period: DateRange, value, baseline_value, derived_by: "specialist" | "user_edit", derivation_context_hash, reasoning: str | None, methodology_note: str | None, created_at, created_by }`
  - `DerivedTarget` — the specialist's structured output per-target: `{kpi_id, objective, period, value, baseline_value, reasoning, methodology_note, derivation_context_hash}`
  - `DerivedTargetsResponse` — the full structured output the specialist returns: `{targets: list[DerivedTarget], overall_confidence: Literal["low", "medium", "high"], methodology_note: str}` (the response-level methodology note is a summary; per-target `methodology_note` is specific)
- **`/api/v1/sar-e/{account_id}/targets/derive`** (POST) — body `{period_start: date, period_end: date}` (inclusive 12-week window snapped to ISO weeks; defaults to `next_monday` through `next_monday + 12 weeks`). Dispatches the `performance_forecasting` specialist via the agent factory's generated `dispatch_to_performance_forecasting()`. Returns `DerivedTargetsResponse` — the caller (PE-PRD-03) decides whether to persist.
- **`/api/v1/sar-e/{account_id}/targets` CRUD**:
  - `GET /targets` — list active targets filtered by `?start_week=…&end_week=…&kpi_id=…`; soft-deleted targets excluded by default; pagination via `limit/offset` (default 48)
  - `GET /targets/{target_id}` — single target with full reasoning + methodology_note (for the Targets tab drill-down, PE-PRD-06)
  - `POST /targets` — persist a single target; if a prior target exists for the same `(kpi_id, period)`, supersede it (deletion + new write in one transaction + audit entry); otherwise fresh write
  - `PATCH /targets/{target_id}` — edit `value` (typically used when a user adjusts a specialist-derived target); supersede semantics with a new `target_id` or overwrite-in-place — see §5.4
  - `DELETE /targets/{target_id}` — soft-delete (`is_active=false` on the doc); preserved for audit + trendline rendering
- **Strict JSON-schema response validation** — ADK's `response_schema` is set to `DerivedTargetsResponse`; on parse failure, retry up to 2× with the same prompt; on third failure, the endpoint returns a 502 with a `fallback_available: true` flag indicating the caller should use baseline values as targets with a UI warning
- **Idempotency cache** — `derivation_context_hash = sha256(json.dumps({baseline_snapshot, calendar_snapshot, historical_pulses_snapshot}, sort_keys=True))`; in-process LRU with 10-minute TTL caches the `DerivedTargetsResponse` by hash + account_id
- **`methodology_note` enforcement**:
  - At response-schema level: `methodology_note` is a required non-empty string field on every `DerivedTarget` and on the response-level `DerivedTargetsResponse`
  - At prompt level: the system prompt includes a hard instruction to phrase all relationships as "associated with", "correlated with", "historically coincided with" — never "caused", "because", "due to", or imperatives suggesting determinism
  - At runtime validation: a post-response lint checks each `methodology_note` + `reasoning` field against a banned-phrase regex (`\b(caused|because|due to|causes|causing|leads to|results in)\b`, case-insensitive). On hit, retry with a reminder system message; on second failure, strip the offending phrase server-side and log `sar_e.target_derivation.methodology_drift`
- **Weave span `sar_e.target_derivation`** — attributes `{account_id_hash, kpi_count, period_start, period_end, overall_confidence, retry_count, derivation_context_hash, duration_ms, cache_hit}`. No raw reasoning strings in attributes (large + potentially PII-adjacent)
- **Tests**:
  - Unit: `get_historical_pulses` heuristic (1.5σ threshold, category overlap)
  - Unit: `derivation_context_hash` stability across runs + ordering
  - Unit: methodology-note banned-phrase regex
  - Integration: full derivation flow against a seeded account with known calendar + baseline; assert schema compliance + no banned phrases
  - Integration: supersede-on-edit — two sequential `POST /targets` for the same `(kpi_id, period)` → exactly one active row
  - Integration: response-schema retry behavior (mock Gemini to return malformed JSON twice + valid once → endpoint succeeds with `retry_count=2`)
  - Integration: 20 golden-path eval cases under `tests/evals/performance_forecasting/` — each case is a seeded account + expected `overall_confidence` + expected direction (target > baseline vs. target < baseline) — SE-PRD-07 extends this with the full eval harness
  - Perf: `/targets/derive` p95 ≤30s (implementation-plan §11)

### Out of scope (handled by other PRDs)

- VAR training, baseline math (SE-PRD-03)
- IRF / scenario propagation (SE-PRD-04)
- Analytical read surfaces (SE-PRD-06)
- Simulations UI, "Save Forecast as Targets" user flow (PE-PRD-03)
- Targets tab UI + drill-down drawer (PE-PRD-06)
- Auto-re-derive on calendar change — v1 is user-triggered (implementation-plan §5.4)
- Model A/B framework — SE-PRD-07 owns; this PRD ships Gemini 2.0 Pro as the sole production choice
- Agent factory infrastructure — AH-PRD-02; this PRD registers a config and is assembled by the existing factory

## 3. Dependencies

- **SE-PRD-03:** `Baseline` docs at `accounts/{account_id}/baselines/{kpi_id}` (read by `get_baseline` tool); `FunnelStageMapping` + `EffectivenessKPI` (read to validate `kpi_id` / `objective` references in the specialist's output)
- **SE-PRD-04:** `POST /scenarios` (not wired as a tool in v1 — the specialist's reasoning over planned-vs-baseline does not require running new scenarios; it reads historical pulses + baseline. Revisit if the specialist's accuracy plateaus and scenario evaluation would help — flagged as open question §9)
- **AH-PRD-02 (Agent Factory):** `agent_configs/performance_forecasting` is a factory-assembled agent; `dispatch_to_performance_forecasting(...)` is generated; `response_schema` validation is ADK's
- **Project Tasks (PR-PRD-07):** Calendar activities with `category in ["holiday", "promotion", "event", "task"]`; read via existing `/plans/*` endpoints in `get_calendar_summary`
- **Agentic Harness runtime:** Gemini 2.0 Pro via Vertex AI; ADK's `FunctionTool` + `response_schema`; `@safe_weave_op` decorator
- **DM-PRD-07:** role gating + audit helper reused from SE-PRD-01
- **Existing files to study:**
  - `app/adk/agents/strategy_agent/` — factory-built agent pattern with tools
  - `app/adk/tools/` — tool function conventions
  - `api/src/kene_api/routers/sar_e_forecasts.py` (SE-PRD-03 / SE-PRD-04) — router layout

## 4. Data contract

### 4.1 Target + derivation models

```python
class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def start_before_end(self) -> "DateRange":
        if self.start > self.end:
            raise ValueError("start must be <= end")
        return self


class DerivedTarget(BaseModel):
    kpi_id: str
    objective: FunnelObjective
    period: DateRange
    value: float = Field(..., ge=0)
    baseline_value: float = Field(..., ge=0)
    reasoning: str = Field(..., min_length=20)
    methodology_note: str = Field(..., min_length=20)
    derivation_context_hash: str


class DerivedTargetsResponse(BaseModel):
    targets: list[DerivedTarget] = Field(..., min_length=1)
    overall_confidence: Literal["low", "medium", "high"]
    methodology_note: str = Field(..., min_length=30)        # response-level summary


class Target(BaseModel):
    target_id: str                                           # ULID
    account_id: str
    kpi_id: str
    period: DateRange
    value: float
    baseline_value: float                                    # captured at derivation time
    derived_by: Literal["specialist", "user_edit"]
    derivation_context_hash: str
    reasoning: str | None
    methodology_note: str | None
    is_active: bool = True
    created_at: datetime
    created_by: str                                          # user_id
```

### 4.2 Derive endpoint

```python
class DeriveRequest(BaseModel):
    period_start: date | None = None                         # default: next Monday
    period_end: date | None = None                           # default: period_start + 12 weeks - 1 day


class DeriveResponse(BaseModel):
    targets: list[DerivedTarget]                             # as returned by the specialist
    overall_confidence: Literal["low", "medium", "high"]
    methodology_note: str
    cache_hit: bool
    retry_count: int
    duration_ms: int
```

### 4.3 Tool result models

```python
class CalendarSummary(BaseModel):
    window: DateRange
    total_tasks: int
    total_planned_cost: float
    campaigns: list[dict]                                    # [{campaign_id, name, objective, task_count}]
    holidays: list[dict]                                     # [{week_start, name}]
    promotions: list[dict]                                   # [{week_start, end_week, name, description}]
    events: list[dict]                                       # [{week_start, name, description}]
    tasks: list[dict]                                        # [{week_start, channel, cost, campaign_id}]  — summarized


class HistoricalPulse(BaseModel):
    week_start: date
    kpi_id: str
    actual_value: float
    expected_value: float                                    # what the contemporaneous VAR had forecast (via historical Baseline if available; else contemporaneous mean)
    deviation_sigmas: float                                  # (actual - expected) / training_sigma
    direction: Literal["lift", "drop"]
    overlapping_calendar_categories: list[Literal["holiday", "promotion", "event"]]
    overlapping_campaign_names: list[str]                    # at most 3, for context
```

### 4.4 Firestore layout

| Path | Shape | Purpose |
|---|---|---|
| `accounts/{account_id}/targets/{target_id}` | subcollection | `Target` entries; supersede-on-edit (prior doc hard-deleted in the supersede transaction) |

Register `targets` in `_migrate_shape_b/resources.py`. Composite index: `(kpi_id ASC, period.start ASC, is_active ASC)` for the Targets tab list query.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `api/src/kene_api/models/sar_e_models.py` — add `DateRange`, `DerivedTarget`, `DerivedTargetsResponse`, `Target`, derive request/response, `CalendarSummary`, `HistoricalPulse` |
| Create | `app/adk/agents/performance_forecasting/__init__.py` + `system_prompt.py` + `tools.py` — tool functions + system prompt |
| Create | Firestore seed: `agent_configs/performance_forecasting` doc per §2 in-scope specification (seeded via `api/scripts/seed_agent_configs.py` or adjacent — confirm convention at kickoff) |
| Create | `api/src/kene_api/services/sar_e_historical_pulses.py` — pulse-detection heuristic |
| Create | `api/src/kene_api/services/sar_e_target_derivation.py` — orchestrator: compute context hash, check cache, dispatch to specialist, validate response, run methodology lint, return `DeriveResponse` |
| Create | `api/src/kene_api/services/sar_e_target_service.py` — CRUD + supersede-on-edit transaction |
| Create | `api/src/kene_api/routers/sar_e_targets.py` — `/targets/derive` + full CRUD |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_targets.router` |
| Modify | `api/src/_migrate_shape_b/resources.py` — register `targets` |
| Modify | `deployment/terraform/firestore-indexes.tf` — composite index in §4.4 |
| Create | `app/adk/agents/performance_forecasting/test_tools.py` |
| Create | `api/tests/unit/test_sar_e_historical_pulses.py` |
| Create | `api/tests/unit/test_sar_e_methodology_lint.py` |
| Create | `api/tests/unit/test_sar_e_derivation_context_hash.py` |
| Create | `api/tests/integration/test_sar_e_targets_derive.py` |
| Create | `api/tests/integration/test_sar_e_targets_crud.py` |
| Create | `tests/evals/performance_forecasting/` — 20 golden-path cases (seeded accounts + expected shape) |

### 5.1 System prompt outline

```
You are the Performance Forecasting Specialist for KEN-E. Your job is to propose
per-KPI-per-week Target values for the next 12 weeks given: (a) the VAR baseline
forecast, (b) the planned calendar of marketing activities, and (c) historical
"pulses" — prior weeks where each KPI meaningfully deviated from its expected
value.

RULES — NEVER VIOLATE:

1. You MUST phrase all relationships as statistical associations, not causation.
   - Allowed: "associated with", "correlated with", "historically coincided with", "tends to co-occur with"
   - BANNED: "caused", "because", "due to", "leads to", "results in", "causes", "causing"
   - This rule is not about softening language — it is a methodological invariant.
     The VAR model estimates associations, not causal effects.

2. Every Target must include a `methodology_note` explaining the associational
   reasoning in one or two sentences.

3. Never recommend a Target that would violate the KPI's `typical_direction`
   without an explicit justification. For `up_is_good` KPIs, Targets below
   baseline require explicit reasoning. For `down_is_good`, the reverse.

4. When the `overall_confidence` would be "low", you MUST set each Target's
   `value` within ±15% of its baseline; do not speculate large deviations
   under low confidence.

5. Use the tools to ground your reasoning. Do not invent baseline or historical
   values. Call get_baseline first, then get_calendar_summary, then
   get_historical_pulses for each FunnelObjective.

OUTPUT SCHEMA: return a DerivedTargetsResponse with one DerivedTarget per
(kpi_id, ISO-week) pair for the 12 weeks × 4 KPIs window (48 targets).
...
```

Full prompt lives in `app/adk/agents/performance_forecasting/system_prompt.py` as a string constant.

### 5.2 `get_historical_pulses` heuristic

```python
def get_historical_pulses(
    account_id: str,
    objective: FunnelObjective,
    lookback_weeks: int = 52,
) -> list[HistoricalPulse]:
    mapping = await get_funnel_mapping(account_id)
    kpi_id = mapping.mappings[objective]

    # Load weekly actuals for the lookback window
    actuals = await read_time_series(account_id, kpi_id, is_partial=False,
                                     from_week=today - timedelta(weeks=lookback_weeks))

    # Compute per-week "expected" using a simple 4-week trailing mean (cheap + stable);
    # a full historical VAR re-fit would be the correct form but is cost-prohibitive here.
    # The 4-week mean is conservative and acknowledged as an approximation.
    expected = _rolling_mean(actuals, window=4)
    sigma = _training_window_sigma(actuals)

    pulses = []
    for point, exp in zip(actuals, expected):
        if exp is None or sigma == 0:
            continue
        deviation = (point.value - exp) / sigma
        if abs(deviation) < 1.5:
            continue
        pulses.append(HistoricalPulse(
            week_start=point.week_start,
            kpi_id=kpi_id,
            actual_value=point.value,
            expected_value=exp,
            deviation_sigmas=deviation,
            direction="lift" if deviation > 0 else "drop",
            overlapping_calendar_categories=await _overlapping_categories(account_id, point.week_start),
            overlapping_campaign_names=await _overlapping_campaigns(account_id, point.week_start, limit=3),
        ))
    return sorted(pulses, key=lambda p: p.week_start, reverse=True)[:20]
```

The 4-week trailing mean approximation is honest about its limitations — the specialist's `methodology_note` says "historical pulses are detected relative to a 4-week rolling mean, which approximates the trend". Improving this to a per-historical-week refit is deferred.

### 5.3 `derivation_context_hash` + cache

```python
def compute_derivation_context_hash(
    baseline_bundle: BaselineBundle,
    calendar_summary: CalendarSummary,
    historical_pulses_by_objective: dict[FunnelObjective, list[HistoricalPulse]],
) -> str:
    payload = {
        "baselines": {k: [p.model_dump(mode="json") for p in b.horizon] for k, b in baseline_bundle.baselines.items()},
        "model_version": next(iter(baseline_bundle.baselines.values())).model_version,
        "calendar": calendar_summary.model_dump(mode="json"),
        "pulses": {
            obj.value: [p.model_dump(mode="json") for p in pulses]
            for obj, pulses in historical_pulses_by_objective.items()
        },
    }
    canon = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode()).hexdigest()
```

Cache key: `(account_id, context_hash)`. TTL: 10 minutes. Cache stores the validated `DerivedTargetsResponse`.

### 5.4 CRUD supersede semantics

`POST /targets`:
1. Query `targets` where `kpi_id=… AND period.start=… AND period.end=… AND is_active=true`
2. In a single transaction:
   - If a prior target exists, mark its `is_active=false` AND delete it (per implementation-plan §3.4 "no version history retained") — we soft-delete for audit purposes only, then hard-delete after the audit entry writes. Equivalently: a single `delete`.
   - Write the new target with a fresh `target_id` (ULID)
   - Write audit entry via `write_audit(parent_kind="account", parent_id=account_id, audit_subcollection="sar_e_audit", resource_type="target", action="target_save", ...)` (DM-PRD-07's registered action). The `before_state` / `after_state` payload distinguishes supersede (prior row in `before_state`) from create (`before_state=None`); no separate action name needed.
3. Response: `Target` with HTTP 200 (supersede) or 201 (create)

`PATCH /targets/{target_id}`:
- Edits are treated as `POST` with the existing `(kpi_id, period)` — the PATCH body specifies the new `value` (and optionally `reasoning`), and the handler delegates to the supersede path with `derived_by="user_edit"`. No in-place update; consistent with supersede contract.
- Note: the response `target_id` on PATCH may differ from the request `target_id` (because the supersede creates a new doc). PE-PRD-06's Targets-tab drill-down reads via `target_id` after PATCH — PE-PRD-06 §6.2 handles the cache refetch.

`DELETE /targets/{target_id}`:
- Soft-delete: set `is_active=false`. Not removed from Firestore (audit retention).
- Subsequent `POST /targets` for the same `(kpi_id, period)` writes a fresh row; the soft-deleted row is left alone.

### 5.5 Response-schema retry flow

```python
async def dispatch_to_specialist(request: DeriveRequest, ...) -> DerivedTargetsResponse:
    for attempt in range(3):
        try:
            raw = await dispatch_to_performance_forecasting(context=..., acceptance_criteria=None)
            parsed = DerivedTargetsResponse.model_validate(json.loads(raw))
            if _methodology_lint_passes(parsed):
                return parsed
            # Send a reminder and retry
            context.append_system_message(
                "Your previous response contained banned causation language. "
                "Re-emit the response using only associational phrasing."
            )
        except (ValidationError, json.JSONDecodeError):
            # ADK typically retries once internally; this outer loop adds 2 more
            continue
    raise HTTPException(502, "target derivation failed validation after 3 attempts; fallback available")
```

### 5.6 Methodology lint

```python
BANNED_PHRASES = re.compile(
    r"\b(caused|because|due to|causes|causing|leads to|results in)\b",
    flags=re.IGNORECASE,
)

def _methodology_lint_passes(response: DerivedTargetsResponse) -> bool:
    for target in response.targets:
        if BANNED_PHRASES.search(target.reasoning or "") or BANNED_PHRASES.search(target.methodology_note or ""):
            return False
    if BANNED_PHRASES.search(response.methodology_note):
        return False
    return True
```

## 6. API contract (owned here)

| Method | Path | Purpose | Role |
|---|---|---|---|
| `POST` | `/api/v1/sar-e/{account_id}/targets/derive` | Specialist derivation of 48 per-KPI-per-week targets | editor |
| `GET` | `/api/v1/sar-e/{account_id}/targets?start_week&end_week&kpi_id&limit&offset` | List active targets | viewer |
| `GET` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Single target with full reasoning | viewer |
| `POST` | `/api/v1/sar-e/{account_id}/targets` | Persist (create or supersede) | editor |
| `PATCH` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Edit via supersede | editor |
| `DELETE` | `/api/v1/sar-e/{account_id}/targets/{target_id}` | Soft-delete | editor |

## 7. Acceptance criteria

1. **Agent config exists post-deploy.** `agent_configs/performance_forecasting` exists with model=`gemini-2.0-pro`, `response_schema` referring to `DerivedTargetsResponse`, and `visible_in_frontend=false`.
2. **Factory builds the specialist.** `agent_factory.build_hierarchy()` includes a specialist with dispatch `dispatch_to_performance_forecasting`. The root agent's instruction block lists it.
3. **Derive happy path.** On an account with 52 weeks of history + a 12-week calendar window containing 2 promotions + 1 holiday, `POST /targets/derive` returns 48 `DerivedTarget`s in ≤30s p95, each with non-empty `reasoning` + `methodology_note`, `overall_confidence` is non-null, no banned phrases appear anywhere in the response.
4. **Idempotency cache.** Two consecutive `POST /targets/derive` calls with the same context produce the same `DerivedTargetsResponse` and the second returns with `cache_hit: true` without invoking Gemini (asserted via Weave span count).
5. **Context hash changes on calendar edit.** After the happy-path derivation, adding a new calendar activity → re-derive returns `cache_hit: false` and a possibly-different target set (hash changed).
6. **Schema retry.** Mock the specialist to emit malformed JSON on the first call → endpoint retries, succeeds on the second call, returns with `retry_count: 1`. Mock 3 failures → endpoint returns 502 with `fallback_available: true`.
7. **Methodology lint.** Mock the specialist to include "because of the promotion" in one target's reasoning → endpoint rejects, sends a reminder, and retries; final response has no banned phrases.
8. **No-mapping gate.** `POST /targets/derive` on an account with `FunnelStageMapping.version=0` returns 422 with "forecasting not set up; complete the wizard first".
9. **No-baseline gate.** `POST /targets/derive` on an account with no baselines yet returns 409 with "baseline not yet available; wait for backfill + retrain to complete".
10. **Supersede-on-edit.** `POST /targets` with `(kpi_id=X, period_start=W1, period_end=W2)` when a prior target exists for the same key → prior doc is absent, new doc written, audit entry with `action="target_save"` (DM-PRD-07 registry) and the prior row in `before_state` indicating supersede. Query `GET /targets?kpi_id=X&start_week=W1` → exactly 1 row.
11. **No version history.** After 5 sequential supersedes, Firestore has exactly 1 active row for the key; 0 soft-deleted rows (hard-deletion confirmed).
12. **PATCH uses supersede.** `PATCH /targets/{id}` with `{value: 15000}` → response has a new `target_id` + `derived_by: "user_edit"`; old id is gone.
13. **DELETE is soft.** `DELETE /targets/{id}` → row has `is_active=false`; subsequent `POST` for the same `(kpi_id, period)` writes a new row without affecting the soft-deleted one.
14. **List filtering.** `GET /targets?start_week=A&end_week=B&kpi_id=X` returns only active targets matching the filter.
15. **Role gating.** Derive / create / patch / delete require editor; list / get require viewer. Unauthorized → 403.
16. **Weave span.** `sar_e.target_derivation` appears with documented attributes; `account_id_hash` not `account_id`; no reasoning strings in attributes.
17. **20 golden-path evals.** `pytest tests/evals/performance_forecasting/` passes — each case's expected `overall_confidence` + per-target directions match within a documented tolerance.
18. **`grep` audit.** `grep -rn 'caused\|because\|due to' api/src/kene_api/routers/sar_e_targets.py api/src/kene_api/services/sar_e_target_derivation.py` returns zero matches. (Audit on the code, not on user-facing reasoning — that's response-level linted.)
19. **Shape B + index.** `targets` registered in resources; composite index deployed.
20. **Tooling gates.** `make lint`, `mypy`, `ruff`, `codespell`, pytest pass.

## 8. Test plan

**Unit tests — historical pulses** (`test_sar_e_historical_pulses.py`):
- Synthetic 52-week series with a known lift week → detected with `deviation_sigmas` positive + `direction="lift"`
- No-deviation series → empty pulse list
- Category overlap: pulse week coincides with a Calendar promotion → `overlapping_calendar_categories` contains `"promotion"`
- Threshold: deviation <1.5σ → excluded

**Unit tests — methodology lint** (`test_sar_e_methodology_lint.py`):
- `DerivedTargetsResponse` with clean phrasing → passes
- One target's reasoning containing "because" → fails
- Response-level `methodology_note` with "caused" → fails
- Case-insensitivity: "Because of" / "BECAUSE" → both caught
- False-positive guard: "association with X" and "the week following the promotion" are allowed

**Unit tests — context hash** (`test_sar_e_derivation_context_hash.py`):
- Same inputs → same hash across two runs + across Python restarts
- Calendar edit (adding one activity) → hash changes
- Ordering of inputs is irrelevant (dict key order shouldn't matter)
- `None` vs. `[]` in historical pulses → different hashes

**Integration tests — derive** (`test_sar_e_targets_derive.py`):
- Happy path with live Gemini (marked `@pytest.mark.gemini`) — skipped in fast CI, runs in nightly
- Mocked-Gemini tests: schema retry (1 fail → 1 pass), methodology retry, full failure → 502
- Cache: 2 calls → 1 Gemini invocation (assertion on Weave span emitter)
- Gate tests: no mapping → 422; no baseline → 409
- `period_start`/`period_end` not on Monday/Sunday → snapped to enclosing ISO weeks

**Integration tests — CRUD** (`test_sar_e_targets_crud.py`):
- Create → get → supersede → get returns new row only
- PATCH → get with new id succeeds; old id 404
- DELETE → is_active=false; subsequent create with same key writes fresh row
- Filter query returns only matching + active rows

**Eval harness** (`tests/evals/performance_forecasting/`):
- 20 seed scripts creating accounts with known histories, mappings, and calendars
- Per-case expected `overall_confidence` (`low` if <26 weeks; `medium` if 26-52; `high` if >52)
- Per-target direction assertions: "target > baseline" where a promotion is planned; "target ≈ baseline" for weeks without planned activity
- Tolerance: `abs(target - baseline) / baseline <= 0.3` for low-confidence cases; `<= 0.5` for high-confidence

**Perf test**:
- 10 sequential `/targets/derive` calls on a warmed pool → p95 ≤30s
- Cache-hit path: p95 ≤200ms

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Gemini Pro cost at scale.** Each derivation is ~15k input tokens + ~3k output = ~$0.15 at current pricing. 1000 accounts × 1 derivation/week = $600/month. | `derivation_context_hash` dedupe + 10min in-process cache handles repeat clicks. SE-PRD-07's A/B framework enables migration to Flash for low-value derivations. |
| **Response-schema drift.** Gemini may emit JSON that validates but carries unexpected field semantics. | Unit tests on a curated set of historical responses lock the shape. If the API version changes, the regression is caught in CI. |
| **Methodology lint false negatives.** Phrases like "attributable to" or "drove" are not in the banned list but suggest causation. | Banned-phrase list is deliberately narrow for v1; broader lint in SE-PRD-07's audit. Prompt-level enforcement is the primary safeguard. |
| **Historical-pulse heuristic is crude.** 4-week trailing mean is a weak expectation. | Honest about limitations in the specialist's methodology note. A future PRD could add per-historical-week VAR refits; out of scope for v1. |
| **Supersede-on-edit loses user intent.** A user edits a target to 15k, later wants to "go back" to the specialist's original 12k. | SAR-E does not retain history — UI can re-trigger `/targets/derive` + show the fresh specialist value. Target history is a documented non-feature. |
| **Cache staleness across baseline retrain.** A retrain changes baselines; in-flight derivations in the cache become stale. | Context hash includes `model_version`; retrain bumps version; old cache entries are naturally unreachable. |
| **Response-schema retry loops on persistent bad output.** 3 retries * 30s each = 90s max latency under pathological Gemini behavior. | Hard cap at 3 attempts; 502 response with `fallback_available: true` so the caller (PE-PRD-03) can propose baseline-as-target with a warning. |
| **`get_calendar_summary` payload size on busy accounts.** 500 tasks × full metadata in the prompt would blow past 30k tokens. | Summarize aggressively: per-campaign totals + categorized lists only; individual tasks summarized to ≤200 per call. |
| **ADK factory compatibility.** AH-PRD-02's factory pattern may not support `response_schema` as declared here. | Confirm at kickoff. If the factory needs an extension point for `response_schema`, this PRD files an issue + the Agentic Harness team plumbs it through.

### Open questions

1. **Should the specialist be allowed to call `/scenarios` as a tool?** Currently no — it reasons from baseline + calendar + pulses. Revisit after SE-PRD-07 evaluation: if targets are consistently off, a "evaluate_scenario(overrides)" tool could help. Would add ~3-5s per call.
2. **Target CRUD: should `PATCH` preserve `target_id`?** Currently PATCH supersedes with a new id, consistent with `POST`. PE-PRD-06 re-fetches by the new id. If the UI needs id-stability, we could do an in-place update — but then the "no version history" semantics leak into the UI (what does it mean to PATCH without retaining the prior?). First-pass: supersede with new id. Revisit if PE-PRD-06 hits friction.
3. **Should the overall `methodology_note` differ across `overall_confidence` levels?** The prompt encourages more cautious language in low-confidence cases. Explicit test in SE-PRD-07.
4. **Idempotency via HTTP headers (`Idempotency-Key`) vs. context hash.** Current plan: hash-based (deterministic from inputs, transparent to caller). If the UI wants explicit control, add an `Idempotency-Key` header that overrides the hash. Deferred.
5. **Eval expansion.** 20 golden-path cases is a floor. SE-PRD-07 can grow this to 50+. Confirm tolerance thresholds with product at kickoff.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-05
- Upstream: [SE-PRD-03](./SE-PRD-03-var-baseline.md), [SE-PRD-04](./SE-PRD-04-irf-scenarios.md), [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)
- Downstream: [SE-PRD-06](./SE-PRD-06-analytical-query-layer.md), [SE-PRD-07](./SE-PRD-07-integration-testing-and-polish.md), [PE-PRD-03](../../performance/projects/PE-PRD-03-simulations-tab.md), [PE-PRD-06](../../performance/projects/PE-PRD-06-targets-tab.md)
- Project Tasks Calendar categories: [PR-PRD-07](../../project-tasks/projects/PR-PRD-07-calendar-activities.md)
- Methodology-note audit pattern: `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` (MER-E framework — surfaces methodology adherence as a scoring signal)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-5, PY-7; C-1, C-2, C-4, C-7; D-2, D-5; T-1, T-3, T-4, T-5, T-6, T-7; G-1
