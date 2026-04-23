# AH-PRD-02 — Agent Factory

**Status:** Blocked
**Owner team:** Core AI / Agent Platform (backend + frontend)
**Blocked by:** AH-PRD-01 (dispatch generator imports `build_review_pipeline`), DM-PRD-00 (Shape B convention + `seed_shape_b_fixtures.py` for per-account agent-config overlay path)
**Parallel with:** AH-PRD-01 is the only hard upstream beyond DM-PRD-00; data-migration projects DM-PRD-01–DM-PRD-04 run on a separate path
**Blocks:** AH-PRD-03, PR-PRD-02 (planning agent assembled by factory), SK-PRD-02 (skills wire into factory), SK-PRD-04 (agent-builder replaces the disabled rows delivered here), KG-PRD-05 (strategy research agents consume factory dispatch)
**Estimated effort:** 11 stories across 3 phases (originally Sprint 9). Phases 1–2 ≈ 4–6 days; Phase 3 (UI + API) ≈ 4–5 days. Parallelizable across backend + frontend.

---

> **Credential-loading migration note.** This PRD ships the `_make_header_provider(auth_type)` pattern (§5.3) that reads OAuth tokens from ADK session state (`ga_credentials`, `google_ads_credentials`, etc.). The [Integrations](../../integrations/implementation-plan.md) component takes ownership of OAuth flows, encrypted token storage, refresh, and revocation starting with **IN-PRD-02**. **IN-PRD-06** retrofits this factory so `_make_header_provider` fetches tokens via `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` instead of reading session state. The closure signature and ADK `header_provider=` plumbing remain intact — only the credential source moves. **Ship AH-PRD-02 as specified; the swap is IN-PRD-06's responsibility, not this PRD's.**

## 1. Context

Today every specialist agent is constructed by a hand-written per-file factory (`create_google_analytics_agent()`, `create_ken_e_agent()`, etc.), and `deploy_ken_e.py` imports those singletons. Adding a new specialist requires writing and wiring new code. This project transforms the agent system into a **config-driven, multi-tenant architecture** — `agent_factory.build_hierarchy()` reads Firestore `agent_configs/{config_id}` + `mcp_servers/{server_id}` documents and assembles the full specialist hierarchy, including tool wiring, OAuth header providers, review-loop-aware dispatch functions, and per-account configuration overlays.

The project spans three phases. **Phase 1** introduces the config-driven constructor and the `account_id`-aware overlay loader that reads `accounts/{account_id}/agent_configs/{config_id}` first and shallow-merges overrides onto the global config. **Phase 2** adds MCP toolset creation from `mcp_servers` documents (with `specialist_categories` sharing one server across multiple specialists), a `_make_header_provider(auth_type)` factory for OAuth credential injection, `ToolRegistry.search()` wired into each specialist's `before_agent_callback` for per-turn tool filtering, and the dispatch-function generator that calls `build_review_pipeline()` from AH-PRD-01 when `acceptance_criteria` is provided. **Phase 3** adds three Firestore flags to the global config schema (`available_to_copy`, `automatically_available`, `visible_in_frontend`), the per-account agent-config CRUD API, and the Workflows > Agents frontend (listing, detail/customization, AgentCreatePage for custom agents). After this project, adding a specialist is a Firestore config change rather than a code change; every account can customize its agents without affecting other accounts.

The Google Analytics Specialist in [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md) is the first specialist assembled entirely through this factory — it is the validation checkpoint for the config-driven narrow-specialist pattern before it is replicated for Google Ads, Meta Ads, HubSpot, and future domain specialists.

## 2. Scope

### In scope — Phase 1 (Config-driven constructor)
- `app/adk/agents/agent_factory/` module: `build_hierarchy()`, `build_agent(config, account_id=None)`, config loaders with per-account overlay + shallow merge + `based_on_version` tracking
- Read `agent_configs/{config_id}` (global) + `accounts/{account_id}/agent_configs/{config_id}` (overlay/custom) + `mcp_servers/{server_id}` (global) from Firestore
- Forward-compat fields on `agent_configs`: `skill_ids: list[str] = []`, `sandbox_code_executor_enabled: bool = false` (pass-through only — lit up by Skills SK-PRD-02/04)

### In scope — Phase 2 (MCP + dispatch generation)
- `McpToolset` creation from `mcp_servers` documents; `specialist_categories` grouping; disabled servers excluded
- `_make_header_provider(auth_type)` closures for `ga_oauth`, `google_ads_oauth`, `hubspot_oauth`, `meta_ads_oauth`; unknown types fail fast at build time
- **Curated per-specialist tool rosters (≤30 tools each).** Each specialist receives a fixed list of tools at construction time, capped at 30 — no per-turn `tool_filter`, no `tool_filter_state` session-state key. The ToolRegistry is a **build-time metadata catalog** the factory reads to assemble those rosters; it is **not** a runtime routing index. Root-agent routing is specialist-description-based — see [README §2.5](../README.md#25-tool-assignment--routing-model).
- `dispatch_to_{specialist_name}()` generator with `@safe_weave_op()` tracing and `acceptance_criteria: str | None = None` plumbing; when provided, wraps specialist in `build_review_pipeline()` from AH-PRD-01; when `None`, preserves single-pass behavior
- **Root instruction assembly.** The factory injects an "Available specialists" block into the root agent's instruction, sourced from each `agent_configs/{id}.description`. This is what the root LLM reads to choose between `dispatch_to_*()` calls — see [README §2.5 Routing](../README.md#25-tool-assignment--routing-model).
- `deploy_ken_e.py` updated to call `agent_factory.build_hierarchy()` instead of importing individual agent singletons
- Factory unit tests (mock Firestore) + integration tests (end-to-end hierarchy build)

### In scope — Phase 3 (Multi-tenant overlay + UI)
- Three new boolean fields on global `agent_configs` documents: `available_to_copy`, `automatically_available`, `visible_in_frontend`; migration script backfills sensible defaults onto existing configs
- CRUD API under `/api/v1/accounts/{account_id}/agent-configs/`: list merged configs, read merged config, create/update overlay (stores only changed fields, tracks `based_on_version`), revert (single delete), create custom agent (`custom_` prefixed `config_id`)
- Account-admin authorization on all per-account endpoints
- Frontend `/workflows` route with Agents tab (listing: Name / Description / Model / customization indicator)
- Agent detail view — edit instruction / temperature / model / description; diff indicator vs. global default; "Revert to default" button; version-tracking of the forked global version
- `AgentCreatePage` — form-based creation of custom agents (name, instruction, model + optional temperature / description). Reserves two disabled rows ("Skills" and "Sandbox code execution") below the live fields with tooltip "Available in Feature 2.6" — Skills SK-PRD-04 swaps them for interactive controls
- Recursive deletion of `accounts/{account_id}/agent_configs/*` on account deletion (see §9 risk)

### Out of scope
- Skill attachment / sandbox code execution — delivered by [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) and [SK-PRD-04](../../skills/projects/SK-PRD-04-agent-builder-controls.md). This project ships only the disabled placeholder UI + pass-through config fields.
- The Google Analytics Specialist migration — owned by [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md).
- `build_workflow_pipeline()` multi-step orchestration — tracked separately for Release 3.
- Non-Firestore agent-discovery sources — factory reads Firestore only.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline()` is imported by the dispatch generator. The factory's dispatch functions call it when `acceptance_criteria` is provided. Hard prerequisite. | This component |
| **[DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)** | Shape B convention in `api/CLAUDE.md` + `accounts/{account_id}/` subcollection fixtures. The per-account overlay at `accounts/{account_id}/agent_configs/{config_id}` is a new Shape B subcollection; this project is the first feature to land directly on Shape B. | `../../data-management/README.md` §2.2 Data Flow |
| Existing Firestore config pattern | Current per-agent `load_config_from_firestore(config_doc_id)` in `app/adk/agents/ken_e_agent.py`, `google_analytics_agent_v4.py`, and the strategy supervisor. Factory generalizes this pattern. | See those source files for the current pattern; §5.2 below maps it to the new factory contract. |
| Existing `ToolRegistry` | `app/adk/tools/registry/tool_registry.py` — `search(user_query)` returns ranked tool metadata. The factory reads it at build time to assemble each specialist's ≤30-tool roster; not wired as a runtime filter. | [README §2.5](../README.md#25-tool-assignment--routing-model) |
| Existing `@safe_weave_op()` decorator | Preserved in generated dispatch functions for tracing. | `app/adk/tracking/` |
| Figma design | Workflows > Agents list + detail + AgentCreatePage specs (referenced in story 2.2-9, 2.2-10, 2.2-11). | Figma Make file |
| Account / Auth | Account-admin authorization on `/api/v1/accounts/{account_id}/agent-configs/*`. Reuses existing `has_account_access` + `is_super_admin` pattern. | `api/src/kene_api/auth/` |

## 4. Data contract

### Firestore

| Path | Shape | Scope | Source |
|------|-------|-------|--------|
| `agent_configs/{config_id}` | Global | Existing — unchanged collection name per Shape B carve-out for non-account-scoped configs | Phase 1 + 3 (3 new flags added in Phase 3) |
| `mcp_servers/{server_id}` | Global | Existing — unchanged; adds `specialist_categories: list[str]` field | Phase 2 |
| `accounts/{account_id}/agent_configs/{config_id}` | Shape B subcollection | Per-account overlay + custom agents (`custom_` prefix on `config_id` for user-authored) | Phase 3 |

### Agent config document fields (superset)

```python
# Existing in the codebase today — preserved as-is:
instruction: str
model: str                                 # e.g. "gemini-2.0-flash"
temperature: float | None
description: str | None
code_execution_enabled: bool = False       # Phase 2 — gates Gemini built-in code execution
mcp_servers: list[str]                     # Phase 2 — references to mcp_servers/{server_id} docs

# New in Phase 3 (global `agent_configs/{config_id}` only):
available_to_copy: bool = True             # account admins can fork this as the basis for a custom agent
automatically_available: bool = True       # auto-attached to accounts without opt-in
visible_in_frontend: bool = True           # appears on Workflows > Agents list

# New in Phase 1 — forward-compat pass-through for SK-PRD-02 / SK-PRD-04:
skill_ids: list[str] = []
sandbox_code_executor_enabled: bool = False

# New on per-account overlay documents:
based_on_version: int                      # which global version was forked (for drift detection + revert)
```

Overlay merge semantics: `global_config | account_overlay` — any field present on the overlay wins; missing fields fall back to global. A single delete of the overlay doc reverts to global behavior.

### Specialist tool rosters

Each specialist receives a **fixed curated tool list (≤30 tools)** at construction time, assembled from its `mcp_servers` references and any function tools. No `tool_filter_state`, no per-turn filtering. The ToolRegistry is a build-time metadata catalog consumed by the factory to resolve tool metadata. Root-agent routing is specialist-description-based — see [README §2.5](../README.md#25-tool-assignment--routing-model).

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `app/adk/agents/agent_factory/__init__.py` — `build_hierarchy()`, `build_agent()` |
| Create | `app/adk/agents/agent_factory/config_loader.py` — global + overlay + merge + `based_on_version` |
| Create | `app/adk/agents/agent_factory/mcp.py` — MCP toolset creation + `specialist_categories` grouping |
| Create | `app/adk/agents/agent_factory/header_provider.py` — `_make_header_provider(auth_type)` |
| Create | `app/adk/agents/agent_factory/dispatch.py` — `generate_dispatch_functions(specialists)` |
| Modify | `deploy_ken_e.py` — replace individual agent imports with `agent_factory.build_hierarchy()` |
| Create | `api/src/kene_api/routers/agent_configs.py` — `/api/v1/accounts/{account_id}/agent-configs/` CRUD |
| Create | `api/src/kene_api/models/agent_config_models.py` — Pydantic shapes |
| Create | `api/scripts/migrate_agent_config_flags.py` — backfill `available_to_copy` / `automatically_available` / `visible_in_frontend` on existing `agent_configs/*` docs |
| Create | `frontend/src/app/pages/workflows/agents/AgentsListView.tsx` |
| Create | `frontend/src/app/pages/workflows/agents/AgentEditView.tsx` — edit + diff indicator + Revert button. Reserves the two disabled rows (Skills + Sandbox) per SK-PRD-04 coordination |
| Create | `frontend/src/app/pages/workflows/agents/AgentCreatePage.tsx` — new-agent form; same disabled rows |
| Modify | `frontend/src/app/pages/workflows/WorkflowsLayout.tsx` — add Agents tab |
| Create | `frontend/src/app/lib/api/agentConfigs.ts` — typed API client + branded `AgentConfigId` |
| Modify | `api/src/kene_api/routers/accounts.py:968-997` — **see §9 risk**: temporarily extend the enumerated deletion sweep to include `accounts/{account_id}/agent_configs/*` until DM-PRD-05 ships `recursive_delete` |
| Create | `app/adk/agents/agent_factory/tests/test_factory.py` + `test_config_loader.py` + `test_mcp.py` + `test_dispatch_gen.py` |
| Create | `api/tests/integration/test_agent_configs_api.py` + `test_agent_config_overlay.py` |

### 5.2 Config-to-constructor mapping

| Firestore field | Agent constructor param | Notes |
|-----------------|-------------------------|-------|
| `agent_configs/{id}.instruction` | `instruction=` | String or `InstructionProvider` callable (closure reading `organization_context` from session state) |
| `agent_configs/{id}.model` | `model=` | e.g., `gemini-2.0-flash` |
| `agent_configs/{id}.temperature` | `generate_content_config=` | Wrapped in `GenerateContentConfig` |
| `agent_configs/{id}.description` | `description=` | Used by ADK for routing descriptions |
| `agent_configs/{id}.mcp_servers` | `McpToolset(...)` instances | List of `mcp_servers/{server_id}` refs; factory resolves each to a toolset |
| `mcp_servers/{id}.url` | `McpToolset(connection_params=SseConnectionParams(url=))` | SSE endpoint |
| `mcp_servers/{id}.auth_type` | `McpToolset(header_provider=)` | Maps to credential key in session state (see §5.3) |
| `mcp_servers/{id}.enabled` | Include/exclude from specialist | Disabled servers are not wired |
| `mcp_servers/{id}.specialist_categories` | Groups server into specialist(s) | A server can belong to multiple specialists |
| `agent_configs/{id}.code_execution_enabled` | `generate_content_config.tools` | If true, adds `Tool(code_execution=ToolCodeExecution())` to `GenerateContentConfig.tools` |
| `agent_configs/{id}.available_to_copy` *(Phase 3)* | Frontend only | Account admins can fork this as the basis for a custom agent |
| `agent_configs/{id}.automatically_available` *(Phase 3)* | Factory: include in account's hierarchy | Auto-attached to accounts without opt-in |
| `agent_configs/{id}.visible_in_frontend` *(Phase 3)* | API filter | Shown on Workflows > Agents list |
| `agent_configs/{id}.skill_ids` *(forward-compat pass-through)* | Pass-through — lit up by [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) | Default `[]`. Factory stores but does not yet act on this. |
| `agent_configs/{id}.sandbox_code_executor_enabled` *(forward-compat pass-through)* | Pass-through — lit up by [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) / [SK-PRD-04](../../skills/projects/SK-PRD-04-agent-builder-controls.md) | Default `False`. Distinct from `code_execution_enabled` (Gemini built-in). |
| `accounts/{account_id}/agent_configs/{id}.based_on_version` | Metadata | Records which global version the overlay was forked from; drives drift detection + revert. |

### 5.3 Header provider factory

Each `auth_type` maps to a session-state credential key and HTTP header format. The factory constructs a closure per MCP server:

```python
def _make_header_provider(auth_type: str) -> Callable[[ReadonlyContext], dict[str, str]]:
    """Create a header_provider closure for the given auth type."""
    CREDENTIAL_KEYS = {
        "ga_oauth": "ga_credentials",
        "google_ads_oauth": "google_ads_credentials",
        "hubspot_oauth": "hubspot_credentials",
        "meta_ads_oauth": "meta_ads_credentials",
    }
    if auth_type not in CREDENTIAL_KEYS:
        raise ValueError(f"Unknown auth_type: {auth_type}")
    state_key = CREDENTIAL_KEYS[auth_type]

    def header_provider(context: ReadonlyContext) -> dict[str, str]:
        creds = context.state.get(state_key, {})
        headers = {}
        if token := creds.get("access_token"):
            headers["Authorization"] = f"Bearer {token}"
        if tenant_id := creds.get("tenant_id"):
            headers["X-Tenant-ID"] = tenant_id
        return headers

    return header_provider
```

Generalizes the existing `_ga_header_provider()` pattern. Unknown `auth_type` values **fail fast at factory build time**, not at runtime — catches config typos before deploy.

> **Future replacement (IN-PRD-06).** The closure body is rewritten to call `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` (OIDC-authed) instead of reading `context.state[state_key]`. Session-state credential keys are removed; [Integrations](../../integrations/implementation-plan.md) owns the OAuth lifecycle end-to-end. The `auth_type` enum maps one-to-one to Integrations `platform_id` values (`ga_oauth` → `google_analytics`, `google_ads_oauth` → `google_ads`, etc.). The returned header shape, the `header_provider=` callsite, and the fail-fast-on-unknown-auth-type behavior are unchanged — existing consumers see no contract difference.

### 5.4 Dynamic agent creation: why pre-declared specialists

Validated in ADK experiments (`adk_experiments/experiment/dynamic-agent-*`, ADK v1.27.4). Three approaches were tested.

| Approach | Verdict | Why |
|----------|---------|-----|
| **Pre-declared specialists** (this PRD's factory) | **Recommended** | Static tree is easy to test, reason about, deploy. `model_post_init()` handles parent linkage automatically. Field validators catch duplicate names at construction. |
| **Ephemeral agents** (Runner pattern) | **Production-ready for sub-tasks** | A specialist spawns a focused ephemeral agent via `Runner` for a specific sub-task, then discards it. Clean lifecycle, no tree mutation. |
| **Persistent dynamic sub-agents** (`sub_agents.append`) | **Not recommended** | Manual `parent_agent` linkage required (undocumented, breaks `transfer_to_agent` if missed). Duplicate-name validation only fires at construction, not on runtime append. Module-level state fragility. |

**Runner pattern for ephemeral sub-tasks** — when a specialist needs a focused sub-agent for a specific task (e.g., analytics specialist running a targeted sub-query):

```python
async def run_sub_task(query: str, tool_context: ToolContext) -> str:
    ephemeral = LlmAgent(
        name="focused_sub_task",
        tools=[specific_tool],  # only relevant tools
        instruction="Answer this specific question with minimal context.",
    )
    runner = Runner(
        app_name=ephemeral.name,
        agent=ephemeral,
        session_service=InMemorySessionService(),
    )
    try:
        async for event in runner.run_async(...):
            if event.actions.state_delta:
                tool_context.state.update(event.actions.state_delta)
            if event.content:
                result = event.content
    finally:
        await runner.close()
    return result
```

**Benefits:** reduced context window, only relevant tools, clean lifecycle, state deltas forwarded to parent. **Does not mutate the persistent tree.**

**Pitfalls to avoid** (failure modes validated in the experiments):

1. **Manual `parent_agent` linkage.** `parent_agent` is set only in Pydantic `model_post_init()`. Dynamically appended agents don't get it → `root_agent` property returns wrong agent → `transfer_to_agent` breaks.
2. **Duplicate-name gap.** `validate_sub_agents_unique_names` only fires at construction. Runtime `sub_agents.append()` bypasses validation entirely.
3. **ADK v2 migration.** `transfer_to_agent` is being replaced by Task Mode (`Agent(mode='task')`). Any dynamic-creation patterns written today will need rework.

### 5.5 Factory limitations & open questions

| Concern | Current answer |
|---------|----------------|
| **Assembly timing** | Deploy time. Factory runs in `deploy_ken_e.py`. |
| **Config changes without redeploy** | Agent instructions/model can change via Firestore (the `InstructionProvider` reads config each turn). MCP server URLs and enabled/disabled flags require redeploy. |
| **Hot-reload** | Not supported on Agent Engine. `agent_engines.update()` redeploys the agent while preserving sessions. |
| **Per-account server sets** | Not supported. Per-account *customization* of instruction/model/temperature/description is supported via the Shape B overlay (§4). Per-account *MCP server rosters* (different server sets per account) would require the factory to run at session creation time — out of scope. |
| **Build-time failure** | If Firestore is unreachable at deploy, the build fails fast with a clear error. Fall-back to a bundled config snapshot is a follow-up, not in this PRD. |
| **Testing** | Config validation at factory build time (check all URLs resolve, `auth_type`s map to known credential keys). Integration test: build hierarchy from test config, assert agent count and tool count. |

## 6. API contract

New endpoints (all under account-admin authorization):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/accounts/{account_id}/agent-configs/` | List merged configs (global + overlay + custom) visible to the account |
| `GET` | `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | Fetch the merged config for a specific agent |
| `POST` | `/api/v1/accounts/{account_id}/agent-configs/` | Create a custom agent (generates `custom_` prefix on `config_id`) |
| `PUT` | `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | Upsert overlay — stores only changed fields |
| `DELETE` | `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | Revert overlay (deletes the overlay doc) for non-custom agents; full delete for `custom_*` |

URL path uses kebab-case `agent-configs` per REST convention; Firestore collection uses snake_case `agent_configs` (matches the global pattern). Router maps between them.

Response shape: `MergedAgentConfig` — Pydantic model union of global fields + overlay fields + a `customization_status: "default" | "customized" | "custom_agent"` discriminator + `based_on_version` (customized/custom only).

## 7. Acceptance criteria

1. **Agent factory construction:** Given an `agent_configs/{config_id}` document, the factory creates an `LlmAgent` with matching `model`, `instruction` (wrapped in `InstructionProvider`), `temperature`, `code_execution` config, and all four standard Weave callbacks wired (`before_agent_callback` also includes the `ToolRegistry.search` wrapper from §5).
2. **MCP toolset creation:** Given `mcp_servers/*` documents with `specialist_categories` and `enabled=true`, the factory creates `McpToolset` instances with correct `SseConnectionParams` and header providers. Disabled servers produce no toolsets.
3. **Server sharing:** Given an MCP server with `specialist_categories=["analytics","execution"]`, both the analytics and execution specialists receive an `McpToolset` for that server.
4. **Header provider:** Given `auth_type="ga_oauth"`, the header provider reads `ga_credentials` from session state and returns correct `Authorization` and `X-Tenant-ID` headers. Unknown `auth_type` raises a clear error at build time.
5. **Tool roster cap:** Every specialist built by the factory has a tool list of ≤30 tools resolved from its `mcp_servers` references at construction. Build fails fast if a specialist exceeds the cap — signals that the specialist's scope is too broad and should be split. No per-turn `tool_filter` is wired.
6. **Dispatch generation:** Given N specialists built by the factory, N `dispatch_to_{name}()` functions are generated with `@safe_weave_op()` decorators and registered as root-agent tools. Each supports review-loop mode (criteria provided) and single-pass mode (criteria=None). The root agent's instruction is assembled at factory time to include an "Available specialists" section listing each specialist's name + `description` for LLM-based routing.
7. **Deploy integration:** `deploy_ken_e.py` calls `agent_factory.build_hierarchy()` instead of importing individual agent singletons. The returned root agent has the correct structure for Agent Engine wrapping.
8. **Factory tests:** Unit tests verify agent count from config, MCP-server grouping, `code_execution` flag, disabled-server exclusion, `auth_type` validation, callback wiring, and dispatch-function count. Integration tests verify end-to-end `build_hierarchy()` from a seeded Firestore config.
9. **Multi-tenant overlay:** Given an `account_id`, the config loader checks `accounts/{account_id}/agent_configs/{config_id}` first, shallow-merges overrides onto the global config, and falls back to global when no override exists. User-created custom agents (account-only, no global counterpart) are discovered and included in the hierarchy.
10. **Global config flags:** Global `agent_configs/*` documents include `available_to_copy`, `automatically_available`, and `visible_in_frontend` boolean fields. The migration script backfills sensible defaults on all existing docs.
11. **CRUD API:** All five endpoints in §6 respond correctly; account-admin authorization is enforced; unauthorized callers receive `403`.
12. **Frontend list:** Workflows > Agents page renders available agents for the current account; each card shows name, description, model, and customization status (Default / Customized / Custom Agent). Filter to `visible_in_frontend=true` on the server.
13. **Frontend edit:** Admins can edit instruction, temperature, model, description from the detail view; a diff indicator shows changes vs. global default; Revert deletes the overlay; version tracking shows which global version was forked.
14. **AgentCreatePage:** Form-based creation of a custom agent (required: name, instruction, model; optional: temperature, description). Submission creates a `custom_` prefixed config_id via the API. Two disabled rows ("Skills" and "Sandbox code execution") appear beneath with tooltip "Available in Feature 2.6".
15. **Account-deletion cleanup (interim):** Until DM-PRD-05 ships, the enumerated sweep in `routers/accounts.py` includes `accounts/{account_id}/agent_configs/*`. Once DM-PRD-05 lands, `recursive_delete(accounts/{account_id})` covers this automatically and the interim code is removed. Integration test confirms no orphaned overlays after `DELETE /api/v1/accounts/{account_id}`.

## 8. Test plan

### Unit
- Factory: agent count matches config, `mcp_servers` grouping, disabled servers excluded, code-execution flag wired, all four callbacks attached, dispatch function count
- Config loader: global-only path, overlay-present path, custom-only path, shallow merge with multi-field overlay, `based_on_version` set correctly, missing global falls back appropriately
- Header provider: each known `auth_type` reads the correct session-state key and constructs correct headers; unknown `auth_type` raises `ValueError` at build time
- Dispatch generator: `acceptance_criteria=None` path invokes specialist directly; criteria-provided path builds pipeline via `build_review_pipeline()`

### Integration
- End-to-end `build_hierarchy()` from a seeded Firestore emulator config → correct agent tree, tool counts, callback wiring
- Overlay merge: seed global + overlay; build with `account_id` → merged config applied
- Custom agent discovery: seed a `custom_` prefixed overlay with no global counterpart → appears in hierarchy
- CRUD API round-trips: list → create overlay → get → revert → list (reverted); create custom → list (included) → delete
- Account-deletion sweep: seed account with overlays + custom; `DELETE /api/v1/accounts/{id}` → `accounts/{id}/agent_configs/*` empty afterward

### Manual verification
- Frontend: create custom agent via UI → appears on list; edit description → diff indicator shows; Revert → returns to default
- Pre-DM-PRD-05: manually inspect Firestore console after account deletion to confirm no orphaned overlay docs

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| **Account-deletion orphan bug** — the existing sweep at `routers/accounts.py:968-997` only deletes `strategy_docs_{account_id}`; custom agents and overlays under `accounts/{account_id}/agent_configs/*` would orphan until [DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) ships `recursive_delete`. | **This project extends the enumerated sweep to include `agent_configs` as a temporary measure.** When DM-PRD-05 lands, the extension is removed and `recursive_delete` covers all per-account subcollections. Integration-tested here (AC #15) and regression-tested in DM-PRD-05's no-orphans test. |
| Factory build failure at deploy time (Firestore unreachable) | Fail-fast with a clear error; fall-back to bundled config snapshot is a follow-up (not in scope). Deploy-time config is read once, so this is low-frequency. |
| `specialist_categories` field missing on existing `mcp_servers/*` docs | Migration step (documented in Phase 2) backfills `specialist_categories` onto each existing server doc based on current hardcoded wiring. |
| Circular overlay merge (global references overlay) | Loader reads global first, applies overlay second — direction is fixed; no recursion. |
| Custom agent name collision across accounts | `config_id` is `custom_{uuid}` (UUID-suffixed); account-scoped path prevents cross-account visibility. |
| Account-admin authorization regression | Reuses existing `has_account_access` + role check; integration test covers unauthorized caller → `403`. |

### Open questions
- **Q:** Should revert also offer "fork and un-fork" semantics (clone overlay as custom, then revert)? → Defer. Single Revert button is enough for v1.

## 10. Reference

- Upstream: [AH-PRD-01](./AH-PRD-01-review-loop-framework.md), [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)
- Downstream: [AH-PRD-03](./AH-PRD-03-google-analytics-specialist.md), [PR-PRD-02](../../project-tasks/projects/PR-PRD-02-planning-agent-and-tools.md), [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md), [SK-PRD-04](../../skills/projects/SK-PRD-04-agent-builder-controls.md), [KG-PRD-05](../../knowledge-graph/projects/KG-PRD-05-research-on-creation-refactor.md)
- MCP architecture: [`../mcp-architecture.md`](../mcp-architecture.md) §2 (ADK internals), §4 (platform decisions), §6 (Firestore config schema), §7 (MCPServerManager disposition).
- Harness design: `docs/KEN-E-System-Architecture.md` §4.3 (Tool type taxonomy)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4, C-5, C-6; T-1, T-3, T-4, T-5, T-6
