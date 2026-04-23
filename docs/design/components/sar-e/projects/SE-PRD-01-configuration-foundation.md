# SE-PRD-01 — Configuration Foundation + Setup State

**Status:** Draft — ready to start once DM-PRD-00, DM-PRD-07, and PR-PRD-08 ship
**Owner team:** SAR-E component team (backend)
**Blocked by:** DM-PRD-00 (Shape B convention + per-account subcollection fixtures — every SAR-E collection is Shape B from day one); DM-PRD-07 (`UserRole` + `require_role` dependency + `write_audit` helper — every mutation here writes an audit entry); PR-PRD-08 (`Campaign` + `CampaignObjective` enum — the four `FunnelObjective` values bind one-to-one to the campaign objectives)
**Blocks:** SE-PRD-02 (weekly ingestion reads `sar_e_config` + `EffectivenessKPI` + the setup-created automation); SE-PRD-03 (VAR training reads `FunnelStageMapping` + `ChannelCoverage`); SE-PRD-06 (analytical queries resolve historical mappings); PE-PRD-04 (Configuration tab); PE-PRD-05 (Setup Wizard)
**Estimated effort:** 4 days

---

## 1. Context

SAR-E is **opt-in per account**. An account must (a) connect at least one third-party integration (via Integrations) and (b) complete the Performance setup wizard that picks Effectiveness KPIs and maps them to funnel Objectives before any forecasting runs. Until that happens every SAR-E analytical and forecasting endpoint must short-circuit with an "empty / not-enabled" response. This PRD owns the config substrate that makes the opt-in gate real.

Three facts shape the design:

1. **The `sar_e_config` document is the single source of truth for forecasting enablement.** It lives at `accounts/{account_id}/sar_e_config` (Shape B, single doc per account). `GET /config/status` returns it as-is; `ForecastingEnabledGate` in Performance reads `enabled`; every downstream SAR-E endpoint checks `enabled=true` before computing. The account-creation hook seeds it with `enabled=false` so nothing runs until the wizard flips it.
2. **Wizard completion is one atomic transaction.** `POST /config/setup` seeds the `EffectivenessKPI` registry (4 rows), writes the `FunnelStageMapping` (1 doc + history v1), creates the `is_system=true` weekly ingestion automation on the Automations platform, kicks off the one-shot backfill plan, and flips `enabled=true` + `setup_wizard_completed=true` — all in a single Firestore transaction plus one orchestrator call. Partial failure rolls back; the wizard sees a clean success / failure response in under 5s p95.
3. **Funnel mapping has a history; targets do not.** Analytical queries (SE-PRD-06) resolve "what was the Consideration KPI during week 2026-W12?" by reading `FunnelMappingHistory`. Every mutation to the mapping bumps `version` and appends a history row; the mapping doc itself always holds the current version. Targets, by contrast, are superseded on edit without version retention (SE-PRD-05); the asymmetry is intentional — mapping changes alter the interpretation of historical data, Target changes do not.

No KPI catalog is global. Every `EffectivenessKPI` is per-account and tied to a specific `DataPipelineJob` (via `source_job_id`). A KPI can only be created when an underlying job exists for a connected integration — the wizard enforces this; post-wizard power-user KPI CRUD (`/config/effectiveness-kpis`) enforces the same check at the backend.

## 2. Scope

### In scope

- **Pydantic models** under `api/src/kene_api/models/sar_e_models.py`:
  - `EffectivenessKPI` (per-account; `source_job_id` FK to `DataPipelineJob`; `aggregation: sum|mean|weighted_mean`; `unit`; `typical_direction`; `is_active`; `created_via: setup_wizard|config_tab`)
  - `FunnelObjective` enum — re-exports from `PR-PRD-08.CampaignObjective` to keep the two in lockstep
  - `FunnelStageMapping` — `{mappings: dict[FunnelObjective, EffectivenessKPIId], version: int, updated_at, updated_by}` with a strict validator enforcing exactly 4 entries (one per Objective) + uniqueness of KPI ids
  - `FunnelMappingHistoryEntry` — snapshot of the mapping at each version, plus `diff_summary` and `updated_by`
  - `Threshold` — `{kpi_id, warn_low, warn_high, critical_low, critical_high}` with cross-field validator `critical_low ≤ warn_low ≤ warn_high ≤ critical_high` (nulls permitted anywhere in the chain)
  - `ChannelCoverage` + `ChannelCoveragePoint` — matrix of `{channel, week_start, has_data}` triples
  - `SarEConfig` — `{enabled, setup_wizard_completed, forecast_horizon_weeks, initial_backfill_weeks, updated_at, updated_by}`
- **`accounts/{account_id}/sar_e_config` account-creation hook** — extend the account-creation path in `api/src/kene_api/routers/accounts.py` (or the existing post-creation seed helper) to write the default `SarEConfig` with `enabled=false, setup_wizard_completed=false, forecast_horizon_weeks=12, initial_backfill_weeks=104`. Plus default empty `FunnelStageMapping` (no mappings, `version=0`) and default `Threshold` set (empty list — populated post-wizard when KPIs exist).
- **`/api/v1/sar-e/{account_id}/config/status`** read endpoint (`GET`) returning `SarEConfigStatus` — superset of `SarEConfig` with two joined fields: `connected_integrations: list[PlatformConnectionSummary]` (from Integrations) and `available_kpi_sources: list[AvailableKPISource]` (from Data Pipeline's job catalog filtered by currently-connected platforms). The Performance tab (PE-PRD-01) reads `enabled`; the wizard (PE-PRD-05) reads the two joined lists.
- **`/api/v1/sar-e/{account_id}/config/setup`** wizard-completion endpoint (`POST`) — body `{kpis: list[EffectivenessKPIInput], funnel_mapping: dict[FunnelObjective, EffectivenessKPIId], initial_backfill_weeks: int}`. In one Firestore transaction: (a) write each KPI under `accounts/{account_id}/effectiveness_kpis/{kpi_id}` with `created_via="setup_wizard"`; (b) write `FunnelStageMapping` v1 + `FunnelMappingHistory` v1; (c) flip `SarEConfig.enabled=true` + `setup_wizard_completed=true`. Outside the transaction (same request): (d) call the Automations service to create the `is_system=true` weekly ingestion automation (recurrence `0 7 * * 1 UTC`); (e) call the orchestrator to kick off the one-shot backfill plan. p95 target ≤5s; on any failure during (a-c) the transaction rolls back; on failure during (d-e) the endpoint surfaces a compensating-delete error and keeps `enabled=false` so the wizard can retry cleanly.
- **Post-setup config routers** under `/api/v1/sar-e/{account_id}/config/`:
  - `GET` + `PUT` `/funnel-mapping` — read current, replace-in-full; `PUT` bumps `version` and appends a history row
  - `GET` `/funnel-mapping/history` — version list for the Configuration-tab History drawer (PE-PRD-04); returns `list[FunnelMappingHistoryEntry]` most-recent-first, default page size 50
  - `GET` + `PUT` `/thresholds` — read list, replace-in-full
  - `GET` + `PUT` `/channel-coverage` — read matrix, replace-in-full (SE-PRD-02 backfills the matrix post-wizard; `PUT` is the manual-edit path)
  - `GET` + `POST` + `PATCH` + `DELETE` `/effectiveness-kpis[/{kpi_id}]` — post-setup CRUD (power users adding a KPI after the wizard); `POST` + `PATCH` validate that `source_job_id` resolves to a `DataPipelineJob` whose `output_schema` is compatible with the supplied `aggregation` / `unit`
- **Uniqueness + integrity validators**:
  - `FunnelStageMapping` validator — exactly 4 entries; every value must reference an existing `EffectivenessKPI` with `is_active=true`; no duplicate KPI ids across Objectives
  - `EffectivenessKPI.source_job_id` validator — job must exist; job's connector `platform_id` must have an active Integrations connection for the account
  - `Threshold` cross-field validator — `critical_low ≤ warn_low ≤ warn_high ≤ critical_high` (nulls allowed anywhere)
- **Audit integration (DM-PRD-07)** — every mutation (`/config/setup`, `PUT /funnel-mapping`, `PUT /thresholds`, `PUT /channel-coverage`, KPI CRUD) writes an `AuditEntry` via `write_audit(...)` with `before` / `after` diffs. Funnel-mapping changes additionally include the `diff_summary` string in the audit payload.
- **Role gating (DM-PRD-07)** — all mutation endpoints require `role >= editor`; `/config/setup` additionally requires `role >= admin` (kicking off backfill is an operation with cost implications). Reads are `role >= viewer`.
- **Tests**:
  - Unit tests for all validators (Funnel mapping uniqueness, Threshold inequality, KPI source-job compatibility)
  - Integration tests for every endpoint (happy path + role-denial + invalid-payload)
  - Transaction-rollback integration test for `/config/setup` — simulate an Automations service failure and assert no KPIs or mapping persist
  - Account-creation hook test — assert `sar_e_config` seeded correctly on new account

### Out of scope (handled by other PRDs)

- Weekly ingestion implementation, `KPIDataPoint` model, and the backfill plan itself (SE-PRD-02)
- `POST /config/backfill-plan` — the pre-submit probe that returns equalized backfill depth (SE-PRD-02 — this PRD only references the endpoint from the wizard's perspective)
- VAR training, baseline forecasts, or any statistical code (SE-PRD-03)
- Scenario propagation (SE-PRD-04)
- Target derivation specialist and target CRUD (SE-PRD-05)
- Analytical query endpoints (SE-PRD-06)
- Wizard-draft Firestore doc (`accounts/{account_id}/performance_wizard_draft`) — owned by PE-PRD-05
- Wizard-draft `DELETE /config/wizard-draft` endpoint — owned by PE-PRD-05
- Performance API bundle endpoints that proxy SAR-E reads (PE-PRD-01)
- Any frontend work — consumed by PE-PRD-04 (Configuration tab) and PE-PRD-05 (Setup Wizard)

## 3. Dependencies

- **DM-PRD-00 (Migration Foundation):** Shape B convention landed in `api/CLAUDE.md`; `_migrate_shape_b/resources.py` registry is the authoritative list of per-account subcollections. This PRD registers four new subcollections there (`effectiveness_kpis`, `funnel_mapping_history`, `thresholds`, `channel_coverage`) plus the `sar_e_config` single-doc path. The composite index definitions land in `deployment/terraform/firestore-indexes.tf` alongside the others DM-PRD-00 establishes.
- **DM-PRD-07 (Approval Workflow & Audit):** `UserRole` + `require_role(UserRole.EDITOR)` / `require_role(UserRole.ADMIN)` FastAPI dependencies; `write_audit(...)` helper. Every mutation endpoint here uses both.
- **PR-PRD-08 (Campaign Management):** exports `CampaignObjective` enum (`Problem Awareness | Brand Awareness | Consideration | Conversion`). SAR-E's `FunnelObjective` is a type-alias re-export — not a parallel enum — so any future Objective addition in PR-PRD-08 propagates automatically. The four per-objective fallback campaigns PR-PRD-08 seeds are what SE-PRD-06's cost-rollup queries aggregate against.
- **Integrations (read-only):** `GET /api/v1/internal/integrations/{account_id}/connections` returns the connected-platforms summary the `/config/status` endpoint joins into its response. No OAuth-flow coupling here — this PRD only reads the connection roster.
- **Data Pipeline (read-only):** `GET /api/v1/internal/data-pipeline/jobs?account_id={id}` returns the job catalog (global + per-account overlays). SAR-E filters by platforms the account has connected and exposes the filtered list as `available_kpi_sources` on `/config/status`. The KPI-source validator on `POST /config/effectiveness-kpis` calls this endpoint too.
- **Automations service (`TaskOrchestrator`-adjacent):** `create_system_automation(account_id, plan_spec)` is called by `/config/setup` step (d). The plan spec includes the weekly cron (`0 7 * * 1 UTC`) and a placeholder task graph that SE-PRD-02 will fill in with actual Data Pipeline extraction tasks. For this PRD's scope, the automation is created with a "stub" task graph — empty `tasks: []` — and SE-PRD-02 extends the `/config/setup` handler to compose the full extraction + ingestion DAG. The transaction semantics are documented once here; the graph content is SE-PRD-02's concern.
- **Existing files to study:**
  - `api/src/kene_api/models/` — Pydantic layout conventions
  - `api/src/kene_api/routers/accounts.py:968-997` — account-deletion sweep (interim measure until DM-PRD-05 `recursive_delete`; extend here to include the new subcollections)
  - `api/src/kene_api/routers/accounts.py` account-creation path — the seed-hook extension point
  - `api/src/kene_api/auth/` — `has_account_access` + role-check patterns
  - `api/src/kene_api/firestore.py` — Firestore client + transaction helpers
  - `docs/design/components/data-management/DESIGN-REVIEW-LOG.md` — Shape B subcollection registration pattern

## 4. Data contract

### 4.1 Pydantic models

```python
# api/src/kene_api/models/sar_e_models.py
from datetime import datetime, date
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from kene_api.models.project_tasks_models import CampaignObjective

# Type-alias re-export — keep in lockstep with PR-PRD-08
FunnelObjective = CampaignObjective


class EffectivenessKPI(BaseModel):
    kpi_id: str                                              # stable; not a branded type on the backend
    account_id: str
    display_name: str
    source_job_id: str                                       # FK → DataPipelineJob
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    typical_direction: Literal["up_is_good", "down_is_good", "neutral"]
    aggregation: Literal["sum", "mean", "weighted_mean"]
    is_active: bool = True
    created_via: Literal["setup_wizard", "config_tab"]
    created_at: datetime
    updated_at: datetime


class FunnelStageMapping(BaseModel):
    account_id: str
    mappings: dict[FunnelObjective, str] = Field(..., min_length=4, max_length=4)
    version: int                                             # 0 = unset; ≥1 = populated
    updated_at: datetime
    updated_by: str                                          # user_id

    @model_validator(mode="after")
    def enforce_uniqueness_and_completeness(self) -> "FunnelStageMapping":
        if self.version == 0:
            return self                                      # account-creation seed — empty mapping permitted
        if set(self.mappings.keys()) != set(FunnelObjective):
            raise ValueError("mapping must contain exactly the four FunnelObjective values")
        if len(set(self.mappings.values())) != 4:
            raise ValueError("each EffectivenessKPI may be mapped to at most one FunnelObjective")
        return self


class FunnelMappingHistoryEntry(BaseModel):
    account_id: str
    version: int
    mappings: dict[FunnelObjective, str]
    diff_summary: str                                        # e.g., "Consideration: kpi_abc → kpi_def"
    updated_at: datetime
    updated_by: str


class Threshold(BaseModel):
    account_id: str
    kpi_id: str
    warn_low: float | None = None
    warn_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None

    @model_validator(mode="after")
    def enforce_inequality(self) -> "Threshold":
        ordered = [self.critical_low, self.warn_low, self.warn_high, self.critical_high]
        populated = [v for v in ordered if v is not None]
        if populated != sorted(populated):
            raise ValueError("thresholds must satisfy critical_low ≤ warn_low ≤ warn_high ≤ critical_high")
        return self


class ChannelCoveragePoint(BaseModel):
    channel: str
    week_start: date
    has_data: bool


class ChannelCoverage(BaseModel):
    account_id: str
    matrix: list[ChannelCoveragePoint]
    updated_at: datetime
    updated_by: str


class SarEConfig(BaseModel):
    account_id: str
    enabled: bool = False
    setup_wizard_completed: bool = False
    forecast_horizon_weeks: int = 12
    initial_backfill_weeks: int = 104
    updated_at: datetime
    updated_by: str
```

### 4.2 `/config/status` response shape

```python
class PlatformConnectionSummary(BaseModel):
    platform_id: str
    connection_id: str
    status: Literal["connected", "expired", "revoked", "error"]
    external_account_label: str | None


class AvailableKPISource(BaseModel):
    source_job_id: str
    display_name: str
    platform_id: str
    unit_suggestion: Literal["count", "currency", "percent", "duration_seconds"]


class SarEConfigStatus(BaseModel):
    enabled: bool
    setup_wizard_completed: bool
    forecast_horizon_weeks: int
    initial_backfill_weeks: int
    connected_integrations: list[PlatformConnectionSummary]
    available_kpi_sources: list[AvailableKPISource]
    updated_at: datetime
```

### 4.3 `/config/setup` request + response

```python
class EffectivenessKPIInput(BaseModel):
    kpi_id: str                                              # generated client-side (ULID) or server-side if omitted
    display_name: str
    source_job_id: str
    unit: Literal["count", "currency", "percent", "duration_seconds"]
    typical_direction: Literal["up_is_good", "down_is_good", "neutral"]
    aggregation: Literal["sum", "mean", "weighted_mean"]


class SetupRequest(BaseModel):
    kpis: list[EffectivenessKPIInput] = Field(..., min_length=4, max_length=8)
    funnel_mapping: dict[FunnelObjective, str]               # values are kpi_ids from `kpis[]`
    initial_backfill_weeks: int = Field(..., ge=4, le=104)

    @model_validator(mode="after")
    def mapping_references_supplied_kpis(self) -> "SetupRequest":
        supplied = {k.kpi_id for k in self.kpis}
        if not set(self.funnel_mapping.values()).issubset(supplied):
            raise ValueError("funnel_mapping references KPIs not in kpis[]")
        return self


class SetupResponse(BaseModel):
    enabled: bool
    setup_wizard_completed: bool
    automation_id: str                                       # id of the created `is_system=true` plan
    backfill_plan_run_id: str                                # id of the one-shot backfill PlanRun kicked off
```

### 4.4 Firestore layout (Shape B)

| Path | Shape | Purpose |
|---|---|---|
| `accounts/{account_id}/sar_e_config` | single doc | `SarEConfig` |
| `accounts/{account_id}/effectiveness_kpis/{kpi_id}` | subcollection | `EffectivenessKPI` entries |
| `accounts/{account_id}/funnel_mapping` | single doc | current `FunnelStageMapping` (v0 on account creation, vN after edits) |
| `accounts/{account_id}/funnel_mapping_history/{version}` | subcollection | `FunnelMappingHistoryEntry` per version |
| `accounts/{account_id}/thresholds/{kpi_id}` | subcollection | `Threshold` per KPI |
| `accounts/{account_id}/channel_coverage` | single doc | `ChannelCoverage` (full matrix) |

Composite indexes (Terraform):

- `effectiveness_kpis` — `(is_active ASC, display_name ASC)` for the Configuration tab's dropdown
- `funnel_mapping_history` — `(version DESC)` for the History drawer
- `thresholds` — none (single-doc reads per kpi_id suffice)

Add all five collection paths to `_migrate_shape_b/resources.py` so DM-PRD-00's seed-fixtures helper wires them into integration tests.

## 5. API surface owned here

| Method | Path | Purpose | Role |
|---|---|---|---|
| `GET` | `/api/v1/sar-e/{account_id}/config/status` | Read `SarEConfigStatus` (+ joined integrations + KPI sources) | viewer |
| `POST` | `/api/v1/sar-e/{account_id}/config/setup` | Wizard-completion transaction | admin |
| `GET` | `/api/v1/sar-e/{account_id}/config/funnel-mapping` | Current mapping | viewer |
| `PUT` | `/api/v1/sar-e/{account_id}/config/funnel-mapping` | Replace mapping; bumps version + history | editor |
| `GET` | `/api/v1/sar-e/{account_id}/config/funnel-mapping/history?limit=50` | Version list | viewer |
| `GET` | `/api/v1/sar-e/{account_id}/config/thresholds` | All thresholds | viewer |
| `PUT` | `/api/v1/sar-e/{account_id}/config/thresholds` | Replace thresholds in full | editor |
| `GET` | `/api/v1/sar-e/{account_id}/config/channel-coverage` | Current matrix | viewer |
| `PUT` | `/api/v1/sar-e/{account_id}/config/channel-coverage` | Replace matrix in full | editor |
| `GET` | `/api/v1/sar-e/{account_id}/config/effectiveness-kpis` | List KPIs | viewer |
| `POST` | `/api/v1/sar-e/{account_id}/config/effectiveness-kpis` | Add a KPI (post-wizard) | editor |
| `PATCH` | `/api/v1/sar-e/{account_id}/config/effectiveness-kpis/{kpi_id}` | Edit a KPI (display_name, thresholds, is_active) | editor |
| `DELETE` | `/api/v1/sar-e/{account_id}/config/effectiveness-kpis/{kpi_id}` | Soft-delete (sets `is_active=false`) — forbidden if mapped | editor |

All endpoints live in `api/src/kene_api/routers/sar_e_config.py`. Mount at `/api/v1/sar-e/` in `api/src/kene_api/main.py`.

## 6. Implementation outline

| Action | File |
|---|---|
| Create | `api/src/kene_api/models/sar_e_models.py` — every Pydantic model in §4.1–§4.3 |
| Create | `api/src/kene_api/services/sar_e_config_service.py` — transaction body for `/config/setup`; helpers for `bump_funnel_mapping`, `replace_thresholds`, `replace_channel_coverage`, KPI CRUD; each helper writes audit + returns the persisted row |
| Create | `api/src/kene_api/routers/sar_e_config.py` — FastAPI router with all 13 endpoints |
| Create | `api/src/kene_api/services/sar_e_integrations_client.py` — thin internal HTTP client to Integrations `/connections` + Data Pipeline `/jobs` reads used by `/config/status` and the KPI-source validator |
| Create | `api/src/kene_api/services/sar_e_automation_seeder.py` — wraps the Automations `create_system_automation` call; returns the `plan_id`; SE-PRD-02 extends it with the real task graph |
| Modify | `api/src/kene_api/routers/accounts.py` — account-creation hook: after the account doc writes, seed `sar_e_config` (defaults) + empty `funnel_mapping` (v0) + empty `channel_coverage` |
| Modify | `api/src/kene_api/routers/accounts.py:968-997` — extend the enumerated deletion sweep to include `sar_e_config`, `effectiveness_kpis/*`, `funnel_mapping`, `funnel_mapping_history/*`, `thresholds/*`, `channel_coverage` (interim; removed once DM-PRD-05 ships `recursive_delete`) |
| Modify | `api/src/kene_api/main.py` — mount `sar_e_config.router` |
| Modify | `api/src/_migrate_shape_b/resources.py` — register the five new subcollection paths |
| Modify | `deployment/terraform/firestore-indexes.tf` — composite indexes in §4.4 |
| Create | `api/tests/unit/test_sar_e_models.py` — validator coverage |
| Create | `api/tests/unit/test_sar_e_config_service.py` — service-layer transaction rollback + audit-write assertions |
| Create | `api/tests/integration/test_sar_e_config_endpoints.py` — every endpoint, happy + role-denial + invalid-payload paths |
| Create | `api/tests/integration/test_account_creation_sar_e_seed.py` — asserts new account has `sar_e_config` with `enabled=false` |
| Create | `api/tests/integration/test_sar_e_config_setup_rollback.py` — simulate Automations failure → assert no KPIs or mapping persist |

### 6.1 `/config/setup` transaction body

Pseudocode — `sar_e_config_service.complete_setup(account_id, request, user_id)`:

```python
async def complete_setup(account_id: str, request: SetupRequest, user_id: str) -> SetupResponse:
    # Phase 1 — Firestore transaction (atomic)
    async with firestore_client.transaction() as txn:
        # Pre-validation: every source_job_id must exist & be compatible with (aggregation, unit)
        for kpi in request.kpis:
            await _validate_source_job(account_id, kpi, txn)

        now = datetime.utcnow()
        for kpi in request.kpis:
            txn.set(
                _kpi_doc(account_id, kpi.kpi_id),
                EffectivenessKPI(
                    **kpi.model_dump(),
                    account_id=account_id,
                    is_active=True,
                    created_via="setup_wizard",
                    created_at=now,
                    updated_at=now,
                ).model_dump(mode="json"),
            )

        mapping = FunnelStageMapping(
            account_id=account_id,
            mappings=request.funnel_mapping,
            version=1,
            updated_at=now,
            updated_by=user_id,
        )
        txn.set(_mapping_doc(account_id), mapping.model_dump(mode="json"))
        txn.set(_mapping_history_doc(account_id, 1), _mapping_to_history(mapping, diff_summary="initial"))

        txn.update(
            _config_doc(account_id),
            {
                "enabled": True,
                "setup_wizard_completed": True,
                "initial_backfill_weeks": request.initial_backfill_weeks,
                "updated_at": now,
                "updated_by": user_id,
            },
        )

        await write_audit(
            txn,
            account_id=account_id,
            user_id=user_id,
            action="sar_e.setup.complete",
            before=None,
            after={"kpi_count": len(request.kpis), "mapping_version": 1},
        )

    # Phase 2 — side effects (non-transactional; idempotent on retry)
    try:
        automation_id = await automation_seeder.create_weekly_ingestion_automation(
            account_id, kpi_ids=[k.kpi_id for k in request.kpis]
        )
        backfill_run_id = await automation_seeder.trigger_one_shot_backfill(
            account_id, kpi_ids=[k.kpi_id for k in request.kpis],
            weeks=request.initial_backfill_weeks,
        )
    except Exception as exc:
        # Compensating rollback — flip enabled back to false; the wizard retries
        await _reset_to_pre_setup(account_id, user_id)
        raise HTTPException(503, f"setup side-effects failed; retry the wizard. ({exc})") from exc

    return SetupResponse(
        enabled=True,
        setup_wizard_completed=True,
        automation_id=automation_id,
        backfill_plan_run_id=backfill_run_id,
    )
```

### 6.2 Funnel-mapping versioning

Every `PUT /config/funnel-mapping` call:
1. Reads the current mapping (version `N`).
2. Computes `diff_summary` against the new mapping (e.g., `"Consideration: kpi_abc → kpi_def; Conversion: kpi_xyz → kpi_qrs"`). If there is no diff, short-circuit with `304 Not Modified` (idempotency).
3. In a single transaction:
   - Writes the new `FunnelStageMapping` doc with `version = N+1`.
   - Writes `FunnelMappingHistoryEntry` at `funnel_mapping_history/{N+1}` with the snapshot + diff.
   - Writes audit entry with before/after.
4. Invalidates downstream Performance API caches via a small internal event (the Performance API's `/configuration` + `/analysis` + `/simulations` bundles set `Cache-Control: no-store` on the next read; no Redis here — the caches are in-process TanStack Query state on the frontend, invalidated client-side per PE-PRD-04 §5.4).

### 6.3 Account-creation seed hook

Extend the post-create path in `routers/accounts.py`. After the `accounts/{account_id}` doc is written:

```python
await sar_e_config_service.seed_defaults(
    account_id=new_account_id,
    user_id=creator_user_id,
)
# Writes:
#   accounts/{account_id}/sar_e_config          → SarEConfig(enabled=false, setup_wizard_completed=false, horizon=12, backfill_weeks=104)
#   accounts/{account_id}/funnel_mapping        → FunnelStageMapping(mappings={}, version=0)
#   accounts/{account_id}/channel_coverage      → ChannelCoverage(matrix=[])
# Does not write thresholds (no KPIs yet) or history (no version to record)
```

The seed is idempotent (`set` with a pre-read merge: if `sar_e_config` already exists, leave it alone — supports re-running the hook safely during data-backfill).

### 6.4 KPI source-job compatibility validator

When a KPI is created (`POST /config/effectiveness-kpis` or `POST /config/setup`), the service fetches `DataPipelineJob.{id}` and asserts:

- The job exists and is enabled for the account.
- The job's connector's `platform_id` has an active Integrations connection for the account.
- The job's `output_schema.fields` includes a numeric field compatible with the requested `aggregation`:
  - `sum` / `mean` / `weighted_mean` all require a numeric field
  - `weighted_mean` additionally requires a `weight` field declared on the job
- The `unit` declared on the KPI is one the job advertises as permitted (an optional `unit_suggestions: list[str]` field on `DataPipelineJob`; if missing, any unit is accepted with a warning logged via `sar_e.kpi_source_unit_unknown`).

Validation errors return `422 Unprocessable Entity` with a structured body pointing at the offending field.

## 7. Acceptance criteria

1. **Account creation seeds defaults.** Creating a new account via `POST /api/v1/accounts/` produces a Firestore state where `accounts/{account_id}/sar_e_config` exists with `enabled=false, setup_wizard_completed=false, forecast_horizon_weeks=12, initial_backfill_weeks=104`, `funnel_mapping` exists with `version=0, mappings={}`, and `channel_coverage` exists with empty `matrix`.
2. **`GET /config/status` pre-wizard.** On a freshly seeded account with no connected integrations, returns `{enabled: false, setup_wizard_completed: false, forecast_horizon_weeks: 12, initial_backfill_weeks: 104, connected_integrations: [], available_kpi_sources: []}`.
3. **`GET /config/status` with integrations.** After connecting Google Analytics via Integrations + seeding at least one `DataPipelineJob` for the account, `/config/status` returns a non-empty `connected_integrations` + non-empty `available_kpi_sources`, still `enabled=false`.
4. **`POST /config/setup` happy path.** Submitting 4 valid KPIs + a valid mapping + `initial_backfill_weeks=52` returns `{enabled: true, setup_wizard_completed: true, automation_id, backfill_plan_run_id}` within 5s; Firestore now has 4 `effectiveness_kpis` docs + `funnel_mapping` v1 + `funnel_mapping_history/1` + the `is_system=true` automation created with recurrence `0 7 * * 1 UTC`; audit entry `sar_e.setup.complete` is written.
5. **`POST /config/setup` validator rejection.** Submitting 4 KPIs where two share the same `source_job_id` + a mapping that points at 3 distinct KPIs (duplicating one) returns `422` with field-scoped errors; Firestore is unchanged.
6. **`POST /config/setup` transaction rollback.** If the Automations `create_system_automation` call fails after the transaction commits, the endpoint returns `503` and the account's `sar_e_config.enabled` is reset to `false`; subsequent wizard retries succeed cleanly (the transaction can re-run without duplicate-id conflicts because KPIs are idempotent on `kpi_id`).
7. **`PUT /config/funnel-mapping` bumps version + history.** Replacing Consideration's KPI produces `funnel_mapping.version = N+1`, a new `funnel_mapping_history/{N+1}` entry with `diff_summary = "Consideration: kpi_abc → kpi_def"`, and an audit entry. Repeating the same PUT returns `304 Not Modified` and does not bump version.
8. **`GET /config/funnel-mapping/history` returns most-recent-first.** Three sequential edits produce entries at `v2`, `v3`, `v4`; the history endpoint returns them ordered `v4 → v3 → v2 → v1` (omitting v0 when unset was seeded).
9. **`PUT /config/thresholds` enforces inequality.** Submitting a threshold with `warn_low=10, critical_low=20` returns `422`; submitting `critical_low=null, warn_low=10, warn_high=100, critical_high=null` succeeds; partial updates overwrite the full list (SAR-E replaces atomically).
10. **KPI CRUD post-wizard.** `POST /config/effectiveness-kpis` with a valid `source_job_id` succeeds; `POST` with a job whose `platform_id` is disconnected returns `422`; `DELETE` on a KPI currently mapped in `FunnelStageMapping` returns `409 Conflict`; `DELETE` on an unmapped KPI soft-deletes (`is_active=false`) and is preserved for historical analytical queries.
11. **Role gating.** `/config/setup` as a viewer returns `403`; `/config/funnel-mapping PUT` as a viewer returns `403`; reads are accessible to any account member.
12. **Audit trail.** Every mutation in AC #4, #7, #9, #10 produces an `AuditEntry` visible in `accounts/{account_id}/audit/` (DM-PRD-07 layout) with before/after diffs.
13. **Recursive deletion.** `DELETE /api/v1/accounts/{account_id}` removes every SAR-E subcollection created here (verified by an integration test inspecting Firestore post-delete); the interim enumerated sweep in `routers/accounts.py` is marked with a `# TODO(DM-PRD-05)` pointing at the replacement path.
14. **Shape B registration.** `pytest api/_migrate_shape_b/tests/test_resources.py::test_all_paths_registered` passes with the five new paths present.
15. **Lint + tooling gates.** `make lint`, `mypy`, `ruff`, and `codespell` all clean.

## 8. Test plan

**Unit tests — models** (`test_sar_e_models.py`):
- `FunnelStageMapping` v0 permits empty mapping; v≥1 requires 4 unique entries
- `FunnelStageMapping` rejects duplicate KPI ids (two Objectives mapped to the same KPI)
- `Threshold` accepts null-sparse chains; rejects `critical_low=20, warn_low=10`; rejects `warn_high=50, critical_high=30`
- `SetupRequest` rejects a mapping referencing a KPI not in `kpis[]`
- `EffectivenessKPI` cross-field: `aggregation="weighted_mean"` + no `weight` field in source job → validator on the service layer surfaces a 422 (tested at service level, not model level — model doesn't have access to the job catalog)

**Unit tests — service** (`test_sar_e_config_service.py`):
- `complete_setup` writes all 4 KPIs + mapping v1 + history v1 + flips `enabled=true` in a single transaction (use `firestore` emulator + inspect the transaction's write set)
- `complete_setup` rollback: mock Automations to raise → assert `sar_e_config.enabled` is back to `false` + no KPIs remain
- `bump_funnel_mapping` with a no-op diff returns `None` and does not write anything
- `replace_thresholds` overwrites the full per-KPI list atomically (old thresholds absent in the new payload are deleted)
- `replace_channel_coverage` replaces the full matrix

**Integration tests — endpoints** (`test_sar_e_config_endpoints.py`):
- One end-to-end test per endpoint under both happy + role-denial paths
- `/config/status` joins integrations + available KPI sources correctly (seed fixtures for both)
- `/config/setup` happy path verifies automation creation + backfill kickoff happen exactly once
- `/config/funnel-mapping PUT` idempotency: same payload twice → second returns 304
- KPI CRUD lifecycle: create → mapped into mapping → delete attempt → 409 → unmap → delete → soft-deleted (is_active=false)

**Integration tests — account lifecycle**:
- New account: assert `sar_e_config` + `funnel_mapping` v0 + `channel_coverage` exist; no KPIs, no thresholds, no history
- Account deletion: seed a fully configured account (KPIs + mapping v3 + thresholds + coverage + audit entries) → `DELETE /accounts/{id}` → assert all SAR-E subcollections empty

**Integration tests — transaction rollback** (`test_sar_e_config_setup_rollback.py`):
- Patch `automation_seeder.create_weekly_ingestion_automation` to raise `ServiceUnavailable`
- `POST /config/setup` → expect 503
- Assert `sar_e_config.enabled=false`, `funnel_mapping.version=0`, `effectiveness_kpis` empty
- Second call to `/config/setup` (with `automation_seeder` unpatched) → succeeds cleanly (no leftover state)

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Transaction + side-effect atomicity.** Firestore transaction commits but Automations call fails — SAR-E is half-configured. | `_reset_to_pre_setup` compensates by flipping `enabled=false` + deleting the written KPIs + mapping. The wizard treats 503 as retryable. Integration test asserts clean recovery. Longer-term: move the automation creation into an outbox/events pattern (out of scope for v1 — the wizard retry is acceptable UX). |
| **Funnel mapping history growth.** An account editing the mapping 50 times per year produces 50 history rows. | Trivial volume. No compaction planned; retention is indefinite (needed for analytical-query historical resolution in SE-PRD-06). |
| **KPI soft-delete collides with mapping.** A user deletes a KPI that's mapped, then the mapping references a missing-from-active KPI. | `DELETE` returns 409 if mapped; the UI must unmap first. Enforced at the service layer + tested. |
| **Per-objective alignment with PR-PRD-08.** If PR-PRD-08 adds a 5th `CampaignObjective` value later, `FunnelStageMapping` validators break on live accounts (4 entries required). | Re-export of `CampaignObjective` plus validator test that locks the expected set on the `FunnelObjective` alias. Any expansion is an explicit coordinated migration — documented in the SAR-E component README once it's drafted. |
| **Account-deletion sweep ordering.** The enumerated sweep in `routers/accounts.py` now spans many subcollections; order matters (cannot delete `sar_e_config` before the hook would silently re-seed it if account-creation is idempotent in an unexpected way). | Deletion runs after the account doc itself is gone; the seed hook only fires on account creation. No re-seed risk. Integration test covers the order. Ship DM-PRD-05 `recursive_delete` to retire the sweep entirely. |
| **`/config/status` cost on cold cache.** Joins Integrations + Data Pipeline catalog on every read. | Small N (≤5 integrations, ≤50 jobs). No caching in v1. Revisit if the wizard + Configuration tab together produce obvious load. |
| **KPI source-job compatibility validator over-triggers.** If Data Pipeline's `output_schema` conventions evolve, the validator may reject valid KPIs. | Validator is lenient: unknown-unit KPIs succeed with a warning log; only the aggregation/weight check is hard. Data Pipeline owns the output-schema contract and will communicate any changes. |
| **Wizard-completion audit payload size.** 4 KPIs × their full definitions in the audit entry could bloat the audit doc. | Audit payload stores only `kpi_count` + `mapping_version` in the `after` field; full KPI definitions are retrievable via the main collection. Confirmed against DM-PRD-07's shape. |

### Open questions

1. **Should `/config/setup` accept 5–8 KPIs (extras mapped outside the 4 Objectives) for future expansion, or enforce exactly 4?** Current model caps at 8 in the request but only requires the mapping to cover 4; extras are seeded as `is_active=true` but unmapped. Confirm with product at kickoff — first-pass behavior is permissive.
2. **How does the KPI source-job validator handle jobs with `output_schema` that's a nested object rather than flat fields?** Current implementation flattens one level; deeper nesting is rejected. Revisit if Data Pipeline ships nested-schema jobs before SE-PRD-02.
3. **Should deletion of a KPI also cascade to `Threshold` for that KPI?** Current plan: yes, soft-delete the KPI + hard-delete the threshold row in the same transaction. Confirm at kickoff.
4. **`/config/status` `available_kpi_sources` — should we include globally-available jobs even if the account has no connection to their platform?** No — filter by connected platforms only. Users see only what they can actually enable; reduces confusion.

## 10. Reference

- Parent plan: [`../implementation-plan.md`](../implementation-plan.md) §6 SE-PRD-01
- Upstream: [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md), [DM-PRD-07](../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md), [PR-PRD-08](../../project-tasks/projects/PR-PRD-08-campaign-management.md)
- Downstream: [SE-PRD-02](./SE-PRD-02-weekly-kpi-ingestion.md), [SE-PRD-03](./SE-PRD-03-var-baseline.md), [SE-PRD-06](./SE-PRD-06-analytical-query-layer.md), [PE-PRD-04](../../performance/projects/PE-PRD-04-configuration-tab.md), [PE-PRD-05](../../performance/projects/PE-PRD-05-setup-wizard.md)
- CLAUDE.md rules in scope: BP-1, BP-2; C-1, C-2, C-4; PY-1, PY-2, PY-3, PY-5, PY-7; D-2, D-5; T-1, T-3, T-4, T-5, T-7, T-8; G-1
