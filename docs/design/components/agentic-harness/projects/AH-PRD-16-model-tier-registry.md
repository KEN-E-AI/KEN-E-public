# AH-PRD-16 — Model Tier Registry, Resolution & Deprecation Guard

**Status:** Proposed (spec)
**Owner team:** Core AI / Agent Platform (backend + frontend)
**Blocked by:** — (builds on [AH-PRD-06](./AH-PRD-06-tool-mapping.md) `agent_configs.model` field + [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) per-turn resolver; both shipped/in-progress, no hard block)
**Blocks:** A fast-follow PRD that consolidates the remaining ~50 raw model pins (strategy agents, evals, compaction, standalone) and coordinates the MER-E global-doc migration onto tiers.
**Release:** Later release — proposed **2 (Task Automation)** at the earliest; safe-model-upgrade infrastructure with no R1/R2 product dependency, so it can float to any post-R1 slot. PO to confirm sequencing.
**Decision record:** origin — PR #830 review (GA tool-name reconciliation) follow-up; DESIGN-REVIEW-LOG entry to be added on acceptance.

> **Why this is its own PRD.** Today every agent's model is a raw, hand-pinned string (`gemini-2.5-flash`, …) scattered across ~50 code sites and Firestore docs, with **no check that a pinned model is still served**. When Google deprecates a model, the first signal is a production failure. There is also no fallback when a model's endpoint is unavailable. This PRD introduces a **model-tier abstraction** (`Fastest` / `Smartest` / `Goldilocks`) backed by a single source of truth, an ordered primary→fallback list per tier, and an automated availability guard — so model swaps become a reviewed code change with no user-facing churn, and deprecations are caught before prod.

---

## 1. Context

A model id reaches an ADK agent as a raw string passed to `LlmAgent(model=...)` (`app/adk/agents/agent_factory/builder.py:485`). That string originates from one of three unrelated places:

1. **`agent_configs/{id}.model`** (Firestore) — for factory-built specialists; MER-E (sister repo) authors the global docs, the API/UI authors per-account overlays. Validated on write against `SUPPORTED_MODELS` (`api/src/kene_api/models/agent_config_models.py`), but the read side accepts any string (AH-40).
2. **`system_settings/harness.default_reviewer_model`** (Firestore) — the review-pipeline reviewer, resolved by `_resolve_reviewer_model` (`specialist_runtime.py:134`) with a 3-tier fallback: per-config override → harness knob → `DEFAULT_REVIEWER_MODEL` code constant (`review_pipeline.py:30`).
3. **Hardcoded constants in code** — the two leaf agent-tools (`numerical_analyst.py:50`, `google_search.py:33`, both `gemini-2.5-flash`), the compaction summarizer (`deploy_ken_e.py:339`), strategy agents, evals, and standalone agents (~50 sites total).

None of these validate that the model is currently served, and only the reviewer model has a runtime-editable, central knob. `model_routing.py` selects the Vertex *endpoint location* (`global` vs regional) and is **orthogonal** to model selection — this PRD does not touch it, but the tier registry must account for its interaction (e.g. `gemini-3.5-flash` is only served on the `global` endpoint and 404s on regional, which the tier fallback list resolves naturally).

The reviewer-model mechanism (#2) is the proven, in-repo pattern this PRD generalizes: a **code default with a Firestore override and TTL caching**. We extend it from "one reviewer model" to "named tiers, each an ordered list of concrete models," and route specialists, the reviewer, and the leaf tools through one resolver.

**User-facing goal:** in the Workflows → Agents configuration UI, replace the raw model dropdown with three options — **Fastest**, **Smartest**, **Goldilocks** — plus an Advanced affordance to pin an exact model. A user never has to track deprecations: developers swap the concrete model behind a tier in code, and every agent on that tier follows.

## 2. Scope

### In scope

- **Tier registry (single source of truth).** New `app/adk/agents/utils/model_tiers.py`: a `ModelTier` type (`fastest` / `smartest` / `goldilocks`), a code-level `MODEL_TIERS` mapping each tier to an **ordered list** of concrete model ids (primary → fallback…), a `DEFAULT_TIER`, and an optional Firestore override in `system_settings/harness.model_tiers` (mirrors `default_reviewer_model`; code is the floor, Firestore is the no-deploy emergency override).
- **Resolver.** `resolve_model(value: str | None) -> str`: tier → first **available** model in the ordered list (per the availability snapshot, §below); raw model → returned as-is (Advanced override / legacy); `None` → `DEFAULT_TIER`. One function, called everywhere a model string is needed.
- **Layer 1 — availability/deprecation guard.** `app/adk/agents/utils/model_availability.py`: a TTL-cached, stale-on-error snapshot of models served in the current project/region (Vertex `models.list`). Two consumers: (a) the resolver, for **build-time** fallback selection; (b) a CI check + scheduled job that fails/alerts when any model referenced by a tier (or the inventoried pins) is **not served** in a given environment, plus a Cloud Monitoring alert on model-not-found errors in prod.
- **Layer 3a — leaf tools through tiers.** `numerical_analyst` and `google_search` resolve their model via a tier (default per tool), overridable via `system_settings/harness` and effective without redeploy (requires the agent-tool registry to build leaf tools per roster-resolution — see §5).
- **Layer 3b — reviewer through tiers.** `_resolve_reviewer_model` returns a tier (default `smartest`), routed through `resolve_model`, preserving the existing override precedence.
- **Layer 3c — `agent_configs.model` accepts tiers.** The builder resolves the stored value via `resolve_model` at construction; raw models keep working. API validation accepts a tier **or** a `SUPPORTED_MODELS` entry.
- **Frontend tier selector.** Workflows → Agents Create/Edit replace the raw-model `Select` with a 3-tier selector + an Advanced disclosure for an exact model; the list view shows the tier label (or `Custom (gemini-2.5-pro)` for raw pins). Behind a feature flag.

### Out of scope (deferred to the fast-follow PRD)

- Consolidating the remaining ~50 raw pins in `strategy_agent/**`, `evaluations/scorers/**`, `agent_standalone_embedded.py`, `company_news_chatbot`, and the compaction summarizer onto tiers.
- The MER-E sister-repo migration of global `agent_configs` docs from raw models to tiers. (Non-breaking: the resolver accepts raw models, so MER-E migrates on its own schedule.)
- **Live, per-call failover** (retry the next model mid-conversation on a 404/5xx). ADK bakes the model into the agent at construction; build-time selection is this PRD's resilience target. Per-call failover is its own effort.
- Changes to `model_routing.py` (endpoint location) and per-token billing logic.

## 3. Dependencies

| Dependency | Why |
|---|---|
| `system_settings/harness` + `system_settings.py` (AH-93) | Pattern + storage location reused for `model_tiers`; TTL/stale-on-error helper mirrored. |
| `agent_configs.model` (AH-PRD-06) + API validators | The field whose accepted values expand to tiers. |
| `specialist_runtime._build_specialist` / `builder.py:485` | Where `resolve_model` is invoked before `LlmAgent(model=...)`. |
| `agent_tool_registry.py` (AH-98) | Must support per-resolution construction of leaf tools so a tier-knob change is effective without redeploy. |
| **UI component** (Workflows → Agents page) | Owns the tier-selector UI; cross-component (see [ui/README](../../ui/README.md)). |
| **Feature Flags** | Gates the frontend tier-selector rollout. |
| **MER-E** (sister repo) | Authors global `agent_configs`; coordinate (non-blocking) — resolver's accept-both keeps it decoupled. |
| Vertex AI `models.list` (per project/region) | Source for the availability snapshot + guard. Requires read permission on the runtime/CI service accounts. |

## 4. Data Contract

```python
# app/adk/agents/utils/model_tiers.py
ModelTier = Literal["fastest", "smartest", "goldilocks"]

# Code floor (single source of truth). Ordered: primary first, fallbacks after.
MODEL_TIERS: dict[ModelTier, list[str]] = {
    "fastest":    ["gemini-3.5-flash", "gemini-2.5-flash"],
    "goldilocks": ["gemini-2.5-flash", "gemini-2.0-flash"],
    "smartest":   ["gemini-2.5-pro",   "gemini-2.5-flash"],
}
DEFAULT_TIER: ModelTier = "goldilocks"
```

- **`system_settings/harness.model_tiers`** *(optional)*: `dict[str, list[str]]` — same shape; when present, overrides the code map for that tier (emergency model swap without deploy). Read with the existing 60 s TTL + stale-on-error helper.
- **`resolve_model(value: str | None) -> str`** — pure resolution + availability fallback; returns a raw model id for `LlmAgent(model=...)`.
- **API** (`agent_config_models.py`): `validate_model_exists` accepts `value in MODEL_TIERS or value in SUPPORTED_MODELS`. `MergedAgentConfig.model` stays `str` (tier **or** model — no Firestore schema migration).
- **Frontend** (`agentConfigs.ts`): `ModelTier` union + a `TIER_LABELS` map (`fastest → "Fastest"`, …); `model` DTO field unchanged (`string`).

## 5. Implementation Outline

| File | Action |
|---|---|
| `app/adk/agents/utils/model_tiers.py` | **New.** `MODEL_TIERS`, `DEFAULT_TIER`, `resolve_model()`, `system_settings` override read. |
| `app/adk/agents/utils/model_availability.py` | **New.** TTL-cached `served_models(project, location)` via Vertex `models.list`; stale-on-error. |
| `app/adk/agents/agent_factory/builder.py` | Resolve `config.model` via `resolve_model()` before `LlmAgent(model=...)`. |
| `app/adk/agents/agent_factory/specialist_runtime.py` | `_resolve_reviewer_model` returns a tier (`smartest`), routed through `resolve_model`; fold resolved value into the content-hash as today. |
| `app/adk/tools/agent_tools/numerical_analyst.py`, `google_search.py` | Replace hardcoded `gemini-2.5-flash` with `resolve_model(<tier>)`. |
| `app/adk/tools/registry/agent_tool_registry.py` | Register a **builder** (callable) rather than a constructed singleton, so leaf tools rebuild per roster-resolution and pick up tier-knob changes (cache-keyed like specialists). |
| `api/src/kene_api/models/agent_config_models.py` | `validate_model_exists` accepts a tier or a supported model. |
| `deployment/ci/` + scheduler job | **New.** Availability guard: assert every tier model is served per env; alert on drift. Cloud Monitoring alert on prod model-not-found. |
| `frontend/src/pages/workflows/agents/AgentEditView.tsx`, `AgentCreatePage.tsx`, `AgentsListView.tsx`, `lib/api/agentConfigs.ts` | Tier selector + Advanced override; list shows tier label; `TIER_LABELS`. |

## 6. API Contract

No new endpoints. Existing `POST`/`PUT` `…/agent-configs/…` accept a tier value in `model` (validated as tier-or-supported-model). `GET` returns the stored value verbatim (tier or model); the frontend maps tiers to labels. Internal-only: the runtime resolves tier→concrete model at agent construction — never exposed in the API surface.

## 7. Acceptance Criteria

1. `model_tiers.resolve_model()` returns the primary model for a tier, the first **available** model when the primary is absent from the snapshot, the raw value unchanged for an Advanced/legacy model id, and `DEFAULT_TIER`'s resolution for `None`; the all-unavailable case returns the last candidate and logs an error.
2. The Firestore `system_settings/harness.model_tiers` override supersedes the code map per tier, with the same 60 s TTL + stale-on-error behavior as `default_reviewer_model`.
3. `model_availability.served_models()` returns the served-model set for a project/region, TTL-cached, and serves stale on a transient Vertex error rather than failing the build.
4. The deprecation guard fails CI (and alerts on its schedule) when any tier's model is not served in a target environment; a Cloud Monitoring alert fires on prod model-not-found errors.
5. `numerical_analyst` and `google_search` resolve their model through a tier; changing `system_settings/harness.model_tiers` changes their served model within the TTL **without a redeploy**.
6. The reviewer model resolves through the tier system (`smartest`) while preserving per-config-override → harness-knob → code-default precedence.
7. A specialist whose `agent_configs.model` is a tier builds with the resolved concrete model; an existing raw-model doc still builds unchanged; API validation accepts a tier or a supported model and rejects anything else.
8. The Workflows → Agents Create/Edit UI shows the 3 tiers + an Advanced exact-model option, the list view shows the tier label (or `Custom (model)`), and the selector is gated by a feature flag.

## 8. Test Plan

- **Unit:** `resolve_model` truth table (tier, raw passthrough, `None`, primary-unavailable→fallback, all-unavailable); override-beats-code; availability snapshot TTL + stale-on-error. Guardrail test (mirrors AH-149): every model in `MODEL_TIERS` ∈ `SUPPORTED_MODELS`, and the migrated agents introduce no new raw pins (CI grep guard).
- **Integration:** build a specialist whose `model` is `"smartest"` and assert the constructed `LlmAgent.model` is the resolved concrete id; same for the two leaf tools via the registry builder; reviewer resolves through tiers.
- **Guard:** the availability check, run against a fixture served-set, fails when a tier model is missing and passes when present.
- **Frontend:** Create/Edit render the tier selector + Advanced; round-trip a tier and a raw model; list view label rendering; flag-off falls back to the legacy dropdown.
- **E2E (dev):** set a tier on an agent in the UI, confirm a chat turn uses the resolved model (trace/log), then flip `system_settings/harness.model_tiers` and confirm the change takes effect within the TTL.

## 9. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Leaf AgentTools are import-time singletons; runtime editability needs per-resolution rebuild. | Registry-builder change (§5); fall back to startup-resolution for v1 if the rebuild proves costly (documented trade-off). |
| MER-E writes raw models to global docs (cross-repo). | Resolver accepts raw models → non-breaking; coordinate MER-E tier adoption in the fast-follow. |
| `gemini-3.5-flash` only on the `global` endpoint (interacts with `model_routing.py`). | Tier fallback list (`fastest` → `gemini-2.5-flash`) covers regional envs; document the endpoint/tier interaction. |
| Availability snapshot staleness → a just-deprecated model still selected. | Short TTL + the scheduled guard + prod model-not-found alert as backstop. |
| Token metering keys on the concrete model. | Resolution happens before the agent runs; the resolved model is what's metered — add a regression check. |

**Open questions:**
1. Exact initial tier→model mappings (the §4 lists are proposed) — confirm `smartest`/`goldilocks` picks and revisit when `gemini-3.5-pro` lands.
2. Per-environment tier overrides (dev lacks `gemini-3.5-flash`) — rely solely on availability fallback, or add explicit per-env maps?
3. Store the tier in the existing `model` field (proposed, no migration) vs. a dedicated `model_tier` field (cleaner typing, requires migration + MER-E coordination)?
4. Should the Advanced raw-model override be visible to all users or gated to super-admins?

## 10. Reference

- [AH-PRD-06](./AH-PRD-06-tool-mapping.md) — `agent_configs.model` + API validation surface.
- [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) — per-turn resolver where specialist model resolution occurs.
- Reviewer-model pattern: `specialist_runtime._resolve_reviewer_model`, `app/adk/agents/utils/system_settings.py`, `review_pipeline.DEFAULT_REVIEWER_MODEL`.
- Endpoint routing (orthogonal): `app/adk/agents/agent_factory/model_routing.py`.
- Origin: PR #830 review (GA tool-name reconciliation) — the deprecation-visibility gap that motivated this project.

## 11. Linear issue breakdown

| # | Issue | AC | Notes |
|---|---|---|---|
| 1 | `model_tiers.py`: registry + `resolve_model()` + `DEFAULT_TIER` + unit truth table | 1 | Foundation; no behavior change yet. |
| 2 | `system_settings/harness.model_tiers` override read (mirror reviewer knob) | 2 | |
| 3 | `model_availability.py`: served-model snapshot (TTL + stale-on-error); wire into resolver | 3 | |
| 4 | Deprecation guard: CI check + scheduled job + prod model-not-found alert | 4 | The safety net. |
| 5 | Route reviewer model through tiers (`smartest`) preserving precedence | 6 | |
| 6 | Leaf tools (`numerical_analyst`, `google_search`) on tiers + registry-builder rebuild | 5 | Includes the singleton→builder change. |
| 7 | `agent_configs.model` accepts tiers; builder resolves at construction; API validation | 7 | **back-compat: raw models still build.** |
| 8 | Frontend tier selector + Advanced override + list label, behind a feature flag | 8 | UI component; flag-gated. |
