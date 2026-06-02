# AH-PRD-11 — Agent Reasoning & Inference Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Agentic Harness
**Initiative:** Data Residency (US + EU)
**Blocked by:** [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) (regional-cell foundation — region registry + `account_id → region` resolver), [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) (per-turn dispatch — the runtime that owns the before-agent callback, `SandboxPool`, and the resolved-specialist graph this PRD threads region through)
**Blocks:** —
**Estimated effort:** 5–7 days of code + a hard external gate (EU Agent Engine GA) that can move launch viability outside the team's control

> **Gating reality — read first.** This is a **launch blocker** (design doc §6.1) but it is **gated on an external GA event**: whether **Vertex AI Agent Engine is GA in a European region** by launch. This is design-doc **open Q1**, the single hardest dependency in the whole program. If Agent Engine is *not* GA in an EU region by launch, EU agent reasoning, sandbox execution, and session state **cannot** be made resident in time — and per the §6.1 gating rule, **EU sign-ups must be gated** behind a feature flag (a Feature-Flags concern, named but out of scope here) and only US sign-ups open. The code in this PRD is written so that flipping the EU cell on is a config change once GA lands; until then the EU cell config is absent and every account resolves to US.

> **Program context.** Data residency is *not* a new component. This slice is homed in Agentic Harness, carries the next `AH-PRD` number, and reuses the keystone foundation from [DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) rather than reinventing routing. Read [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §1–§4 (esp. §2 D1/D3/D4/D6, §3.2 cell table, §3.4 reference pattern, §3.5 model-endpoint strategy) and §5 (gap register) before this PRD. This project closes **R-03, R-04, R-16** (logical slice **DR-PRD-01**, design doc §7).

> **ADK 2.0 sequencing (Review 45).** This PRD threads `data_region` through `builder.py`, `sub_agent_attacher.py`, `sandbox_pool.py`, `deploy_ken_e.py`, and `chat.py` — the same chat-tree surfaces the **ADK 2.0 migration ([AH-PRD-13](./AH-PRD-13-adk2-foundation.md))** rewrites. Sequence after AH-PRD-13 (or coordinate closely) to avoid rework; the EU agent runtime deploys on ADK 2.0, and the sandbox residency relies on AH-PRD-13's sandbox-on-2.0 re-validation.

---

## 1. Context

KEN-E's agent reasoning/inference plane is the densest concentration of EU-content egress in the residency audit: three of the eight launch blockers (§6.1) live here. The account already carries the routing key — `data_region` (US / EU) — but the agent runtime ignores it entirely:

- **R-03 — model inference is global/ambient.** Agents are built with bare model strings (`builder.py:465` — `model=config.model`), so the genai client resolves to whatever `GOOGLE_CLOUD_LOCATION` the Agent Engine runtime injects (the engine's deploy region). An EU account's prompts are processed at the US endpoint. The Vertex `global` endpoint gives no processing-location guarantee, so it is disallowed for EU (design doc D4). A per-environment resolver **already exists** — `app/adk/agents/agent_factory/model_routing.py` `resolve_model_location(environment, data_region)` / `apply_model_location_env()`, shipped in PR #751 for the dev→`global` slice closing AH-86 — and `resolve_model_location` already takes a `data_region` parameter as the documented extension hook (`model_routing.py:62-95`), but it is currently called with **no** `data_region` (`sub_agent_attacher.py:376`). This PRD wires the account's region into that call for staging/prod.
- **R-04 — reasoning + sandbox + session plane is pinned us-central1.** The Agent Engine is deployed against `VERTEX_AI_LOCATION` (`deploy_ken_e.py:296-304`); the code-execution sandbox resource name and its `vertexai.Client` read `VERTEX_AI_LOCATION` from the env (`sandbox_pool.py:78-81`, `sandbox_pool.py:98-131`); and chat session creation runs against the engine's `location` (`chat.py:374-376`, `chat.py:482-486`). All three are single-region. An EU account's reasoning, its sandbox-executed code (which sees account data), and its conversation context all run in the US.
- **R-16 — session state holds regulated content in a US-hosted store.** `create_conversation` loads `organization_context` (from Neo4j) and `ga_credentials` (OAuth access/refresh tokens + selected GA properties) and writes them into the ADK session's `initial_state` (`chat.py:543-697`), then persists them via `VertexAiSessionService.create_session` (`chat.py:710-712`). Because `VertexAiSessionService` is bound to the engine's project + location (`chat.py:482-486`), the session state physically lives wherever the engine lives — today, the US. R-16 is therefore **closed transitively** by R-04: routing the session service to the EU engine for EU accounts moves the state to the EU cell.

**The mechanism caveat that shapes the whole design (design doc §3.5).** Two distinct variables must not be conflated:

| Variable | Controls | How it must be set |
|---|---|---|
| `GOOGLE_CLOUD_LOCATION` | Vertex AI **model-serving** endpoint (the genai client) | The Agent Engine runtime **injects** this (= engine deploy region), and the baked `.env` is loaded with `load_dotenv(override=False)`, so a `.env` value is **inert**. Must be applied **in-process at agent startup** via `os.environ[...]` before the first model client is built. |
| `VERTEX_AI_LOCATION` | Agent **Engine / session / sandbox** region (`vertexai.init`, `VertexAiSessionService`, `SandboxPool`) | A separate var; set per regional deployment + read per acquisition. **Not** touched by the model-location resolver. |

The runtime hook for the in-process application is the root agent's **before-agent callback** (`sub_agent_attacher.py:346` `attach_specialists_before_agent_callback`), which AH-PRD-09 already uses to call `apply_model_location_env()` (`sub_agent_attacher.py:365-382`) — the earliest guaranteed-to-fire entrypoint in the managed runtime (the prebuilt agent graph is unpickled and `build_hierarchy()` never re-runs). This PRD threads the per-turn account's `data_region` into that existing call.

**No existing data is migrated.** The EU cell is green-field (design doc open Q7); no US-resident sessions are moved. Standing up the EU Agent Engine and routing new EU traffic to it is the whole job.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (D1/D3/D4/D6), §3.2 (cell table), §3.5 (model-endpoint strategy + mechanism caveat).

## 2. Scope

### In scope

- **Production per-region model routing (R-03).** Extend the existing `apply_model_location_env()` call in the before-agent callback (`sub_agent_attacher.py:376`) to pass the per-turn account's `data_region`, so an EU account's genai client builds against `europe-west1` and a US account against `us-central1`. Reuse `resolve_model_location` unchanged (`development → global` already correct; this PRD activates the `data_region` branch for staging/prod). The region is read from session state (`account_id` is already on `callback_context.state`, `sub_agent_attacher.py:422`) — resolve it via the foundation resolver, never via a blocking I/O call inside the callback (see §4.4).
- **EU Agent Engine (R-04).** Deploy a second Agent Engine in the EU region (gated on Q1 GA). Thread `data_region` / region through the deploy path (`deploy_ken_e.py:296-304`, `405-423`) so a single deploy invocation can target a region, and persist the EU engine's resource id under a region-suffixed Secret Manager key (`KEN_E_ENGINE_ID_EU`).
- **Sandbox acquisition routing (R-04).** Make `SandboxPool` region-aware: `_sandbox_resource_name` (`sandbox_pool.py:78-81`) and `_get_vertexai_client` (`sandbox_pool.py:98-131`) must use the region resolved from the leasing `account_id` instead of the ambient `VERTEX_AI_LOCATION`, and the pool key (`(account_id, config_id)`, `sandbox_pool.py:137`) is already account-scoped so an EU and US sandbox never collide.
- **Session creation routing (R-04 / R-16).** Make `AgentEngineClient` select the regional engine id + location from the selected account's region (`chat.py:374-376`, `chat.py:477-486`, `chat.py:530-532`), so `VertexAiSessionService` (and therefore the persisted `initial_state` carrying `organization_context` + `ga_credentials`) lands in the account's home cell.
- **Reuse the foundation.** All region decisions go through DM-PRD-09's `resolve_account_region(account_id) -> Region` and the `Region` enum / `CELLS` map (`shared/residency/regions.py`, `routing.py`). This PRD adds **no** new region registry.

### Out of scope

- **The dev→`global` model slice (AH-86).** Already shipped in PR #751 (`model_routing.py`); this PRD only activates the production `data_region` branch.
- **Observability residency (R-02, R-12)** — content-capture off + EU trace/log sink. Separate sibling slice **[AH-PRD-12]** (`./AH-PRD-12-observability-residency.md`, DR-PRD-02). The `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` flag (`deploy_ken_e.py:367-370`) is its concern, not this PRD's.
- **MCP server region routing (R-15)** — `mcp.py` URLs are a Phase-1 follow-up (post-launch), not a launch blocker; owned by a separate agentic-harness Phase-1 slice per [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §7, **not** folded into this PRD.
- **Firestore / Neo4j / KMS / Redis / BigQuery regionalization** — DM-PRD-09 (Firestore), KG-PRD-07 (Neo4j), IN-PRD-08 (KMS/tokens), CH-PRD-07 / BL-PRD-07 (Redis / usage). This PRD consumes the foundation resolver only.
- **Migrating existing US sessions to EU** — green-field (Q7); supervised region migration is DM-PRD-10.
- **Gating EU sign-ups behind a feature flag** — the §6.1 gating rule when Q1 is unresolved is a Feature-Flags concern, wired when the EU cell is verified end-to-end.

## 3. Dependencies

- **[DM-PRD-09](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) complete** — provides `Region` / `CELLS` / `normalize_region` (`shared/residency/regions.py`) and `resolve_account_region(account_id)` (`shared/residency/routing.py`), the `account_id → region` directory, and `data_region` immutability. This PRD adds the *agent-plane* `CellConfig` fields it needs (regional Agent Engine id + `VERTEX_AI_LOCATION`) to the same registry rather than a parallel map.
- **[AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) shipped** — owns the before-agent callback (`sub_agent_attacher.py:346`), the per-turn `account_id`-in-state contract (`sub_agent_attacher.py:422`), and `SandboxPool` (`sandbox_pool.py`). This PRD threads region through those existing surfaces.
- **Reference pattern:** `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region → (resource, location)` map) — the canonical shape; `model_routing.py:62-95` is its agent-plane analogue and is already in the tree.
- **External / open — Q1 (hard gate):** Vertex AI Agent Engine EU GA. The model-routing slice (R-03) does **not** depend on Q1 (regional model endpoints exist today); the engine/sandbox/session slice (R-04/R-16) **does**.

## 4. Data contract

### 4.1 Agent-plane cell config (extends the DM-PRD-09 registry)

The keystone `CellConfig` already carries `region` / `gcp_project_id` / `location` (DM-PRD-09 §4.1). This PRD adds the agent-plane fields consumed here:

```python
# shared/residency/regions.py  (fields ADDED to the existing CellConfig)
@dataclass(frozen=True)
class CellConfig:
    region: Region
    gcp_project_id: str
    firestore_database_id: str
    location: str                      # already present (us-central1 / europe-west1)
    # --- added by AH-PRD-11 ---
    agent_engine_secret_key: str       # Secret Manager key holding this cell's engine id,
                                        #   e.g. "KEN_E_ENGINE_ID" (US) / "KEN_E_ENGINE_ID_EU"
    vertex_ai_location: str            # engine/session/sandbox region for vertexai.init / VertexAiSessionService
```

`vertex_ai_location` and `location` are equal per cell today (US→`us-central1`, EU→`europe-west1`) but are kept as distinct fields because one is the *model-serving* string (the `GOOGLE_CLOUD_LOCATION` value resolved by `model_routing`) and the other is the *engine/session/sandbox* region — the two vars the mechanism caveat forbids conflating.

### 4.2 Model-serving location resolution (R-03)

Unchanged resolver; new call argument.

| Environment / cell | `resolve_model_location(env, data_region)` → | Applied via |
|---|---|---|
| `development` / `dev` | `"global"` | `apply_model_location_env()` (already shipped) |
| staging / prod, US account | `"us-central1"` | `apply_model_location_env(data_region="US")` |
| prod, EU account | `"europe-west1"` | `apply_model_location_env(data_region="EU")` |

The `data_region` is sourced per turn from `resolve_account_region(account_id)` where `account_id = callback_context.state["account_id"]` (`sub_agent_attacher.py:422`).

### 4.3 Engine / sandbox / session region selection (R-04 / R-16)

```python
# shared/residency/routing.py  (NEW helper; mirrors get_firestore_for_account)
def get_agent_cell_for_account(account_id: str) -> CellConfig:
    """Return the agent-plane CellConfig (engine id + vertex_ai_location) for
    the account's home cell. Reuses resolve_account_region(); per-region cached."""
```

- **Session/engine:** `AgentEngineClient` selects `CellConfig.agent_engine_secret_key` + `CellConfig.vertex_ai_location` from `get_agent_cell_for_account(selected_account_id)` (`chat.py:530-532`) before constructing `VertexAiSessionService` (`chat.py:482-486`).
- **Sandbox:** the lease/`get_or_create` caller (`sandbox_pool.py:231`, `346`) already passes `account_id`; the pool resolves `vertex_ai_location` from it for `_sandbox_resource_name` and `_get_vertexai_client`.
- **Session state contents are unchanged** — `organization_context` + `ga_credentials` (`chat.py:692-697`) carry the same shape; only the cell they persist into changes. R-16 is satisfied by R-04's session-service routing, with no schema change.

### 4.4 Concurrency / non-blocking constraint

The before-agent callback runs inside ADK's async invocation flow and **must not block** (the dispatch design degrades on any callback error, `sub_agent_attacher.py:437`). `resolve_account_region` is the foundation's directory fast-path (DM-PRD-09 §4.4) and must resolve from session state / its per-region cache, not a synchronous Neo4j read on the hot path. If region cannot be resolved, fall back to `DEFAULT_REGION` (US) — fail-safe to the existing behavior, never to the EU cell.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `shared/residency/regions.py` — add `agent_engine_secret_key` + `vertex_ai_location` to `CellConfig`; populate `CELLS` from env per deployment |
| Modify | `shared/residency/routing.py` — add `get_agent_cell_for_account(account_id)` (per-region cached; reuses `resolve_account_region`) |
| Modify | `app/adk/agents/agent_factory/sub_agent_attacher.py` (`365-382`, `422`) — resolve the per-turn region from `state["account_id"]` and pass it: `apply_model_location_env(data_region=region)` (R-03) |
| Modify | `app/adk/agents/agent_factory/sandbox_pool.py` (`56-82`, `98-131`, `231`, `346-403`) — resolve `vertex_ai_location` per lease from `account_id` instead of the ambient `VERTEX_AI_LOCATION`; keep the `(account_id, config_id)` key (R-04) |
| Modify | `api/src/kene_api/routers/chat.py` (`374-376`, `477-486`, `530-532`) — select engine id + `VERTEX_AI_LOCATION` from `get_agent_cell_for_account(selected_account_id)`; `VertexAiSessionService` follows (R-04/R-16) |
| Modify | `app/adk/deploy_ken_e.py` (`257-304`, `405-423`) — accept a target region; init Vertex AI + create/update the engine in that region; persist its id under the cell's `agent_engine_secret_key` |
| Modify | `app/adk/.env.production` / `deployment/terraform/` — add `KEN_E_ENGINE_ID_EU` Secret Manager entry + EU Agent Engine staging bucket (gated on Q1) |
| Create | `app/adk/agents/agent_factory/tests/test_model_routing_data_region.py` — prod EU/US `apply_model_location_env(data_region=...)` |
| Create | `app/adk/agents/agent_factory/tests/test_sandbox_pool_region.py` — per-region resource name + client; US/EU isolation |
| Create | `api/tests/unit/test_agent_cell_routing.py` — `get_agent_cell_for_account` per-region selection + cache |
| Create | `api/tests/integration/test_chat_session_region.py` — EU account session created against EU engine/location |

## 6. API contract

No new public HTTP surface; this PRD adds internal DI/runtime contracts and constrains the deploy path.

| Contract | Consumed by | Source of truth |
|---|---|---|
| `apply_model_location_env(data_region=resolve_account_region(account_id))` applied in-process in the before-agent callback | The genai model client (per-turn) | `app/adk/agents/agent_factory/sub_agent_attacher.py`, `model_routing.py:62-95` |
| `get_agent_cell_for_account(account_id) -> CellConfig` (engine secret key + `vertex_ai_location`) | `AgentEngineClient`, `SandboxPool` | `shared/residency/routing.py` |
| `CellConfig.agent_engine_secret_key` / `.vertex_ai_location` | Deploy path, session service, sandbox pool | `shared/residency/regions.py` |
| `deploy_ken_e.py --env <env> --region <us\|eu>` deploys one engine per cell; persists id under the cell's secret key | Release/CI deploy | `app/adk/deploy_ken_e.py` |

## 7. Acceptance criteria

1. In a non-dev environment, the before-agent callback resolves the per-turn account's region from `state["account_id"]` and calls `apply_model_location_env` such that an **EU** account sets `GOOGLE_CLOUD_LOCATION="europe-west1"` and a **US** account sets `"us-central1"`; `development` is unaffected (still `"global"`).
2. The model-serving location is set **in-process** (via `os.environ`), not from `.env` — a `GOOGLE_CLOUD_LOCATION` baked into `.env` does not change the resolved value (regression test for the `load_dotenv(override=False)` inertness).
3. `resolve_model_location` and the `GOOGLE_CLOUD_LOCATION` (model) path never set or read `VERTEX_AI_LOCATION`, and vice-versa — the two variables are independently asserted (the mechanism caveat).
4. `get_agent_cell_for_account` returns the EU cell's engine secret key + `europe-west1` for an EU account and the US cell's for a US account; called twice for the same region it returns the same cached config (one entry per `Region`).
5. `SandboxPool` builds the sandbox resource name + `vertexai.Client` at the leasing account's `vertex_ai_location`: an EU account's sandbox resource path contains `europe-west1`; a US account's contains `us-central1`; the pool keeps them as distinct `(account_id, config_id)` entries (no cross-region reuse).
6. `AgentEngineClient` for an EU `selected_account_id` constructs `VertexAiSessionService` against the EU engine id + `europe-west1`, so `create_session` persists `initial_state` (`organization_context`, `ga_credentials`) in the EU cell; a US account uses the US engine (R-16 verified via the engine/location the session service is bound to).
7. `deploy_ken_e.py --region eu` initializes Vertex AI and creates/updates the engine in the EU region and writes its id to `KEN_E_ENGINE_ID_EU`; `--region us` (default) preserves today's behavior and `KEN_E_ENGINE_ID`.
8. If region resolution fails or no EU cell config is present (pre-Q1-GA), every account resolves to `DEFAULT_REGION` (US) — fail-safe; no path silently routes to a non-existent EU engine.
9. **Operator-verified (not CI-gated, gated on Q1 GA):** an EU account's chat turn shows its reasoning, sandbox execution, and session state in the EU region; no EU prompt/response reaches a US model endpoint or US-hosted session.
10. `make lint` passes. The new/extended unit + integration tests pass.
11. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit

- `test_model_routing_data_region.py`: table over (`environment`, `data_region`) → expected location, incl. prod EU→`europe-west1`, prod US→`us-central1`, dev→`global` (any region) (AC-1); `.env`-inertness regression — set `GOOGLE_CLOUD_LOCATION` in env, assert `apply_model_location_env` overrides it (AC-2); assert no `VERTEX_AI_LOCATION` access in the model path (AC-3).
- `test_agent_cell_routing.py`: `get_agent_cell_for_account` per-region selection + one-config-per-`Region` cache, reusing a mocked `resolve_account_region` (AC-4); fail-safe to `DEFAULT_REGION` when resolution raises or the EU cell is absent (AC-8).
- `test_sandbox_pool_region.py`: `_sandbox_resource_name` / `_get_vertexai_client` use the resolved region (mock the resolver); EU vs US accounts produce distinct resource paths and pool entries; `_get_vertexai_client` is cached per `(project, location)` (AC-5).
- `sub_agent_attacher` callback: mocks `resolve_account_region` from `state["account_id"]`, asserts `apply_model_location_env` is called with the resolved `data_region`, and that a resolver exception is swallowed + falls back to US without blocking the turn (AC-1, AC-8, non-blocking constraint §4.4).

### Integration (mocked Vertex / session service; no live engine)

- `test_chat_session_region.py`: for an EU `selected_account_id`, assert `AgentEngineClient` selects the EU engine id + `europe-west1` and `VertexAiSessionService` is constructed with them, with `initial_state` containing `organization_context` + `ga_credentials` (AC-6); a US account selects the US engine (parity).
- Deploy-path: invoke `deploy_ken_e.py` region selection with `vertexai.init` + `agent_engines.create/update` mocked; assert region + secret-key wiring for `--region eu` vs `--region us` (AC-7).

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Q1 (EU Agent Engine GA) does not land by launch** — R-04/R-16 cannot be made resident | The model-routing slice (R-03) ships independently. Code fail-safes to US when no EU cell config is present (AC-8). Per §6.1, EU sign-ups are gated (Feature-Flags) until the EU cell is verified — under-promise beats a residency violation (D6). |
| Region resolution adds latency / blocks the hot before-agent callback | `resolve_account_region` uses the foundation's directory fast-path / per-region cache (DM-PRD-09 §4.4), not a synchronous Neo4j read; the callback already swallows + degrades on any error (`sub_agent_attacher.py:437`). |
| Conflating `GOOGLE_CLOUD_LOCATION` (model) and `VERTEX_AI_LOCATION` (engine/session/sandbox) reintroduces the inert-`.env` bug | Two distinct `CellConfig` fields; AC-3 asserts the paths never cross; `model_routing.py` already documents the split (`model_routing.py:29-34`). |
| Sandbox pool reuses a US-region executor for an EU account (or vice-versa) | Pool key is `(account_id, config_id)` and account→region is immutable (DM-PRD-09 D5), so an account never changes cell mid-life; AC-5 asserts isolation. |
| A second engine doubles deploy surface + cost; engine ids drift between secret keys | One `deploy_ken_e.py` invocation per region writes exactly one cell-keyed secret; the existing update-not-recreate guard (`deploy_ken_e.py:400-413`) is preserved per region. |

### Open questions (carry from design doc §8)

- **Q1 — hard gate:** is Vertex AI Agent Engine GA in a European region by launch? Determines whether R-04/R-16 ship or EU sign-ups gate. **Decides this PRD's launch viability.**
- **Q6 — EU region:** confirm `europe-west1` for the EU Agent Engine / sandbox / session plane (matches the GCS reference + DM-PRD-09), or a specific member-state region for sovereignty.
- **Q5 — org/region scope:** can one org hold accounts in both cells? If yes, a single chat turn's `selected_account_id` is the authoritative routing key (already the case here); if org is region-pinned, routing is identical but simpler. Does not block this PRD.

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 (D1/D3/D4/D6), §3.2 (cell table), §3.4 (reference pattern), §3.5 (model-endpoint strategy + mechanism caveat), §5 (R-03/R-04/R-16), §6.1 (launch gating), §7 (DR-PRD-01).
- Foundation PRD: [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS` / `normalize_region`, `resolve_account_region`, `data_region` immutability.
- Sibling Agentic Harness slice: [`./AH-PRD-12-observability-residency.md`](./AH-PRD-12-observability-residency.md) (R-02/R-12 — content capture + trace/log sink).
- Dispatch runtime this PRD threads through: [`./AH-PRD-09-per-turn-dispatch.md`](./AH-PRD-09-per-turn-dispatch.md).
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS regional routing); agent-plane analogue already in tree: `app/adk/agents/agent_factory/model_routing.py` (PR #751, AH-86 dev slice).
- Refactor targets: `app/adk/agents/agent_factory/builder.py:465`, `app/adk/agents/agent_factory/sub_agent_attacher.py:365-382,422`, `app/adk/agents/agent_factory/sandbox_pool.py:56-82,98-131,231-403`, `app/adk/deploy_ken_e.py:296-304,405-423`, `api/src/kene_api/routers/chat.py:374-376,477-486,530-532,588-697,710-712`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-3, PY-7; T-1, T-3, T-4, T-6.
