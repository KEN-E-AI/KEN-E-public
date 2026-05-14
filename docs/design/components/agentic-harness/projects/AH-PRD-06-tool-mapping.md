# AH-PRD-06 — Per-Agent Tool Mapping

**Status:** Proposed
**Owner team:** Core AI / Agent Platform (backend + frontend)
**Blocked by:** AH-PRD-02 (agent factory + `accounts/{account_id}/agent_configs/{config_id}` overlay path)
**Parallel with:** SK-PRD-02 / SK-PRD-04 (skills attach into the same form rows and share the ≤30-tool cap)
**Blocks:** Future narrow-specialist PRDs that want per-agent tool curation rather than entire-server attachment
**Estimated effort:** 3 PRs. PR-A (backend, merged in #472) ≈ 3–4 days. PR-B (frontend, in review at #473) ≈ 2–3 days. PR-C (`default_global` function-tool wiring) ≈ 0.5–1 day.

---

## 1. Context

Today an agent's tool roster is **coarse-grained**: each `agent_configs/{id}` document references entire MCP servers via `mcp_servers: list[str]`, and the agent factory wires every tool that server exposes (`app/adk/agents/agent_factory/roster.py:125-215`). Users have no way to attach a single tool from a server. The Workflows > Agents create and edit forms reserve two locked `DisabledPlaceholderRow`s for "Skills" and "Sandbox code execution" (AH-PRD-02 §2 Phase 3) — neither has a row for individual tools, because the model didn't exist.

This PRD adds **per-tool selection** as a first-class concept on every agent:

1. **Account creation seeds a global default tool set.** Every new account starts with a set of built-in function tools (e.g., `create_visualization`, `transfer_to_agent`) available immediately — no integration required. Implemented as a static catalogue rather than a Firestore seed; see §4.
2. **Integration connection expands the account's tool inventory.** When a user completes OAuth for a platform via Integrations (IN-PRD-02+), the tools belonging to that platform's MCP server become available to attach to any agent on the account. Integration ↔ MCP server is 1:1 today (Integrations README §2.1).
3. **Agent configuration picks individual tools.** The Agents tab's create + edit forms grow a tool-picker section that renders the account's available tools grouped by source, lets the user toggle which the agent receives, and writes the selection to a new `tool_ids: list[str]` field on the agent config.

The agent factory in AH-PRD-02 explicitly deferred per-account MCP-server rosters as out of scope (§5.5 Open questions: "Per-account MCP server rosters would require the factory to run at session creation time — out of scope"). This PRD does **not** reverse that decision at the server level — server attachment remains a global concern. Instead, it adds a tool-level allowlist that is applied at agent construction by filtering the toolsets the factory already builds. Build-time assembly is preserved.

The cap-enforcement code at `roster.py:55-77` (`_tool_count_for_server`) already assumes each MCP server's individual tools will eventually be catalogued in `tools.yaml`. Today only `google_analytics_mcp` is populated (8 tools); every other server falls back to the documented "count = 1, log a warning" path. Authoring the YAML for every shipped server has been a known follow-up — this PRD makes it load-bearing.

## 2. Scope

### In scope — PR-A (Backend: data model + factory + endpoint)

- Extend `app/adk/tools/registry/config/tools.yaml` to catalogue every shipped MCP server's tools (per-tool metadata: `name`, `description`, `category`, `mcp_server`, `keywords`, `estimated_tokens`).
- Add a top-level `function_tools:` section to the same YAML for built-in function tools that don't require an integration, each tagged `default_global: true`.
- Add `tool_ids: list[str] | None` to four Pydantic models in `api/src/kene_api/models/agent_config_models.py`: `AgentConfig`, `AgentConfigCreate`, `AgentConfigOverlayUpdate`, `MergedAgentConfig`. Semantics: `None` = legacy (all tools from attached servers), `[]` = no tools, `[…]` = explicit allowlist.
- Server-side validators on Create/Update: each tool ID must reference a catalogued tool; the count must be ≤ `MAX_TOOLS_PER_SPECIALIST` (30, `roster.py:29`).
- Agent factory tool-filtering: extend `resolve_specialist_roster()` (`roster.py:125`) to accept `tool_ids` and filter both the per-server `McpToolset`s and the function-tools list down to the allowlist. Plumb from `builder.py`.
- MCP toolset wrapping: extend `build_toolset_for_doc()` (`mcp.py:327`) to accept an optional `allowed_tool_names` set. Forward to ADK's `McpToolset.tool_filter` if supported; otherwise wrap and filter `get_tools()`.
- New endpoint `GET /api/v1/accounts/{account_id}/tools` returning the account's tool inventory, tagged by source (`global_default` / `integration`) and gated on the account's `platform_connections/*` status.
- Hardcoded `platform_id → mcp_server_id` map inside the new service (e.g., `google_analytics → google_analytics_mcp`); promoted to `PlatformDefinition` (Integrations) in a follow-up.

### In scope — PR-B (Frontend: tool picker UI)

- New `AgentToolPicker` component (`frontend/src/pages/workflows/agents/AgentToolPicker.tsx`) — grouped, searchable, multi-select list backed by `useAccountTools(accountId)`. Empty integration sections link to `/settings/integrations`.
- Integrate the picker into `AgentCreatePage` and `AgentEditView`. The picker lives between the existing form fields and the disabled "Skills" / "Sandbox code execution" rows (both stay reserved for SK-PRD-04).
- Extend `MergedAgentConfig`, `AgentConfigCreatePayload`, and `AgentConfigUpdatePayload` TS types with `tool_ids: string[] | null`.

### In scope — PR-C (Backend: wire `default_global` function tools through the factory)

PR-A shipped the per-server filtering path but left a latent gap: `app/adk/agents/agent_factory/hierarchy.py:325` hardcodes `function_tools=[]` when calling `resolve_specialist_roster`, so the `function_tools:` section of `tools.yaml` is fully wired into the catalogue but **never reaches any constructed agent**. This was always part of AH-PRD-06's intent — the §4 backward-compatibility table below already implies function tools are part of the default roster — but the implementation was deferred. PR-C closes it.

- `hierarchy.py` Step 6c: replace `function_tools=[]` with `ToolRegistry.list_default_global_tools()` (or equivalent — surface the actual `FunctionTool` instances, not just metadata). `tool_ids` semantics are unchanged: `None` keeps the function tools alongside every server tool; `[…]` filters them by `function.{name}` membership; `[]` removes them. The existing PR-A function-tool filter in `roster.py` continues to do the right thing once a non-empty list is plumbed.
- AH-PRD-04 (data visualization) is the immediate beneficiary — `create_visualization()` becomes reachable from every factory-built specialist without each specialist declaring the tool. AH-PRD-04 Story 2.4-2 explicitly described this as "the factory's default function-tool roster" and is depending on it.
- No model, API, or frontend change. The picker UI from PR-B is already correct — its inventory response shows `function.create_visualization` and persisted `tool_ids` round-trip cleanly; PR-C is what makes those bits actually drive runtime behaviour for factory-built agents.

### Out of scope

- **Server-level attachment UI** — `mcp_servers: list[str]` remains a backend concern; users see tools, not servers. AH-PRD-02's defer on per-account server rosters is preserved.
- **Skills attachment / sandbox code execution** — owned by SK-PRD-02 and SK-PRD-04. The two disabled placeholder rows stay disabled.
- **Per-account default agent seeding** — `automatically_available: bool` (AH-PRD-02 §4) continues to govern which agents auto-attach. This PRD does not change that mechanic.
- **Live MCP `list_tools()` endpoint** — the API process does not connect to MCP servers. The tool catalogue is the static YAML. A live-discovery fallback is a future option (see §9 open questions).
- **Tool inventory Firestore subcollection** — the inventory is computed on-demand from the static catalogue + the account's `platform_connections/*`. Nothing new is written on account creation; no migration is needed.
- **Promoting `platform_id → mcp_server_id` to `PlatformDefinition`** — defer to an Integrations follow-up; hardcode it here.
- **Unifying the `strategy_agent` construction path with the factory** — agents built via `app/adk/agents/strategy_agent/config_loader.py:create_agent_from_firestore_config` (notably `marketing_researcher` and `marketing_formatter`) read the same Firestore documents but go through a separate code path that strips `tool_ids` and `mcp_servers` before construction. That gap is described under **Known limitations** below and tracked separately as **[AH-PRD-07](./AH-PRD-07-unify-strategy-agent-construction.md)**.

### Known limitations after PR-A/B/C ship

- **Strategy-agent specialists silently ignore `tool_ids` and `mcp_servers`.** Agents constructed via `app/adk/agents/strategy_agent/config_loader.py:create_agent_from_firestore_config` (specifically `marketing_researcher` and `marketing_formatter`, plus any future agent reaching ADK's `Agent.from_config()` via this loader) filter the Firestore doc down to ADK's `LlmAgentConfig` allowed keys before validation (`strategy_agent/config_loader.py:148-149`). `tool_ids` and `mcp_servers` aren't in that allow-list, so they're dropped — tools for these agents come from hand-wired call sites (e.g., `agent.tools = [AgentTool(agent=google_search_agent)]` in `marketing_agents.py:270`). The picker UI on `/workflows/agents` will persist `tool_ids` to the same Firestore doc, but that selection has no runtime effect for these agents until [AH-PRD-07](./AH-PRD-07-unify-strategy-agent-construction.md) bridges the two construction paths.
- **Surfaces affected:** any specialist created in `app/adk/agents/strategy_agent/` (today: `marketing_researcher`, `marketing_formatter`, plus the orchestrator's helper agents). Specialists built via `app/adk/agents/agent_factory/hierarchy.py:build_hierarchy` (the AH-PRD-02 path) are unaffected — `tool_ids` works correctly there.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | The agent factory + the `accounts/{account_id}/agent_configs/{config_id}` overlay path. PR-A modifies `resolve_specialist_roster`, `build_toolset_for_doc`, and `builder.py` — files this PRD created. | This component |
| **[Integrations](../../integrations/README.md)** | Per-account `platform_connections/{connection_id}` documents are the gating signal for whether an MCP server's tools are "available" to an account. PR-A's new service reads them directly. No new endpoints in Integrations are required. | `../../integrations/README.md` §2.1 |
| Existing `ToolRegistry` | `app/adk/tools/registry/tool_registry.py` + `config/tools.yaml`. PR-A extends both. `roster.py:_tool_count_for_server` already assumes this catalogue exists and warns when an MCP server is uncatalogued — extending it lights up the existing fallback path. | [Review 22 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md) |
| Existing `MAX_TOOLS_PER_SPECIALIST` | `roster.py:29`. The cap is enforced at the logical-count level today; PR-A's validator enforces it at the API boundary too. | This component |
| Existing `require_account_access` | `api/src/kene_api/auth/` — the new endpoint reuses this dependency. | `api/CLAUDE.md` |
| Figma design | Tool-picker UI (grouped accordion, per-group select-all, search). | Figma Make file |

Notes on adjacent work (no hard dependency):

- **[Skills SK-PRD-02 / SK-PRD-04](../../skills/projects/)** — Skills attach via `skill_ids` and count against the same 30-tool cap. The two PRDs share form real-estate but don't share data. Coordinate on form layout if both ship in the same window.
- **Integrations follow-up** — promoting the `platform_id → mcp_server_id` map onto `PlatformDefinition` belongs in an Integrations PRD, not here. No such project exists today; the map lives inside `account_tools_service.py` until then (§9 risk).

## 4. Data contract

### Firestore

No new collections, no new subcollections, no new fields outside `agent_configs/*`.

| Path | Change | Scope |
|------|--------|-------|
| `agent_configs/{config_id}` | Add optional field `tool_ids: list[str] \| None = None` | Global |
| `accounts/{account_id}/agent_configs/{config_id}` | Same field on the overlay shape | Per-account |

`tool_ids` is treated by the existing overlay merge the same way `skill_ids` is today (AH-PRD-02 §5.2): present on the overlay → wins; absent → falls back to global. The implementation will need to mirror the existing `mcp_servers` / `skill_ids` merge path in `routers/agent_configs.py:_merge_from_data` (which lifts those fields out of the raw Firestore doc onto `MergedAgentConfig` even though they aren't declared on `AgentConfig` — see §9 open question).

### Tool catalogue

The source of truth is `app/adk/tools/registry/config/tools.yaml`, extended to two top-level sections:

```yaml
tools:
  # MCP-attached tools. Each tool's availability is gated on whether the account
  # has connected the integration that owns the tool's `mcp_server`.
  - name: list_ga_accounts
    description: ...
    category: analytics
    mcp_server: google_analytics_mcp
    # ...existing fields (parameters, permissions, keywords, estimated_tokens)...
  - name: list_google_ads_campaigns
    mcp_server: google_ads_mcp
    # ...

function_tools:
  # Non-MCP function tools. Always available to every account.
  - name: create_visualization
    description: Render a Vega-Lite chart artifact.
    category: general
    default_global: true
    estimated_tokens: 200
```

`ToolDefinition` (`tool_schema.py`) grows two optional fields:

- `source: Literal["mcp", "function"]` — derived from which section the tool was loaded from.
- `default_global: bool = False` — only meaningful on `function_tools` entries; signals "always available, no integration required."

### Tool ID format

Single string-typed namespace, used wherever `tool_ids` appears:

- MCP tools: `{mcp_server_id}.{tool_name}` — e.g., `google_analytics_mcp.list_ga_accounts`.
- Function tools: `function.{tool_name}` — e.g., `function.create_visualization`.

Max 80 characters per ID (enforced via `Annotated[str, Field(max_length=80)]`).

### Backward-compatibility semantics

| Stored value | Factory behaviour |
|---|---|
| `tool_ids is None` (existing agents) | No tool-level filtering. Every tool from every attached `mcp_servers` server is included **plus every `default_global: true` entry from `function_tools:`** (PR-C). Matches AH-PRD-04 Story 2.4-2's "default function-tool roster" expectation. |
| `tool_ids == []` | Agent has no tools. Function tools NOT included. |
| `tool_ids == ["…", "…"]` | Only listed tools are included; everything else is filtered out, including function tools not in the list. |

The factory branches on `is None` vs. "set" — empty list is meaningfully different from "not set."

### Account inventory response shape

```json
{
  "tools": [
    {
      "tool_id": "google_analytics_mcp.list_ga_accounts",
      "name": "list_ga_accounts",
      "description": "List Google Analytics accounts...",
      "category": "analytics",
      "source": "integration",
      "mcp_server": "google_analytics_mcp",
      "integration_platform": "google_analytics"
    },
    {
      "tool_id": "function.create_visualization",
      "name": "create_visualization",
      "description": "Render a Vega-Lite chart artifact.",
      "category": "general",
      "source": "global_default",
      "mcp_server": null,
      "integration_platform": null
    }
  ]
}
```

## 5. Implementation outline

### 5.1 File inventory

| Action | File | PR |
|--------|------|-----|
| Modify | `app/adk/tools/registry/config/tools.yaml` — add `function_tools:` section; backfill every shipped MCP server's tools | A |
| Modify | `app/adk/tools/registry/tool_schema.py` — add `source: Literal["mcp", "function"]` and `default_global: bool` to `ToolDefinition` | A |
| Modify | `app/adk/tools/registry/tool_registry.py` — load both YAML sections; expose `list_function_tools()` and `list_default_global_tools()` | A |
| Modify | `app/adk/agents/agent_factory/mcp.py` — accept optional `allowed_tool_names` on `build_toolset_for_doc`; forward to `McpToolset.tool_filter` or wrap | A |
| Modify | `app/adk/agents/agent_factory/roster.py` — `resolve_specialist_roster` accepts `tool_ids: list[str] \| None`; filters toolsets + function tools | A |
| Modify | `app/adk/agents/agent_factory/builder.py` — plumb `tool_ids` from the loaded `AgentConfig` into the roster resolver | A |
| Modify | `app/adk/agents/agent_factory/hierarchy.py` (Step 6c) — replace hardcoded `function_tools=[]` with the default-global function tools from `ToolRegistry.list_default_global_tools()` so `create_visualization` and future built-ins reach every factory-built specialist | C |
| Modify | `api/src/kene_api/models/agent_config_models.py` — add `tool_ids` to `AgentConfig`, `AgentConfigCreate`, `AgentConfigOverlayUpdate`, `MergedAgentConfig` | A |
| Modify | `api/src/kene_api/routers/agent_configs.py` — accept + merge `tool_ids`; add validator (catalogue + cap) | A |
| Create | `api/src/kene_api/models/tool_models.py` — `AccountToolEntry`, `AccountToolsResponse` | A |
| Create | `api/src/kene_api/services/account_tools_service.py` — pure-logic inventory composer; reads `tools.yaml` + `platform_connections/*`; holds the hardcoded `platform_id → mcp_server_id` map | A |
| Create | `api/src/kene_api/routers/account_tools.py` — single `GET /api/v1/accounts/{account_id}/tools` endpoint | A |
| Modify | `api/src/kene_api/main.py` — register the new router | A |
| Create | tests under `api/tests/` + `app/adk/agents/agent_factory/tests/` | A |
| Create | `frontend/src/lib/api/tools.ts` — typed client | B |
| Create | `frontend/src/queries/tools.ts` — `useAccountTools(accountId)` | B |
| Modify | `frontend/src/lib/api/agentConfigs.ts` — extend `MergedAgentConfig` + Create/Update payload types | B |
| Create | `frontend/src/pages/workflows/agents/AgentToolPicker.tsx` | B |
| Modify | `frontend/src/pages/workflows/AgentCreatePage.tsx` — add `tool_ids` to schema + payload; render picker | B |
| Modify | `frontend/src/pages/workflows/agents/AgentEditView.tsx` — add `tool_ids` to `EDITABLE_FIELDS`; render picker | B |
| Create | tests for the new picker component + form integration | B |

### 5.2 Inventory composition (PR-A)

`account_tools_service.compose_inventory(account_id, db) -> AccountToolsResponse`:

1. Read the catalogue once via the existing `ToolRegistry` (or a small parallel loader in the API process — `app/adk/...` is not currently importable from the API; trivial `yaml.safe_load` of the same file path is acceptable).
2. Emit every entry from `function_tools:` (tagged `source="global_default"`) unconditionally.
3. Read `accounts/{account_id}/platform_connections/*` from Firestore. For each connection with `status == "connected"`, look up the bound `mcp_server_id` from the hardcoded map; emit every catalogued tool whose `mcp_server` matches (tagged `source="integration"`, `integration_platform=<platform_id>`).
4. Return the assembled list. The endpoint does not filter; the frontend renders all entries grouped by `mcp_server` (or by "Built-in" for function tools).

### 5.3 Factory filtering (PR-A)

`resolve_specialist_roster(specialist_name, *, mcp_toolsets, function_tools, mcp_server_ids, tool_ids, registry=None)`:

- When `tool_ids is None` → existing behaviour (return `[*mcp_toolsets.values(), *function_tools]`).
- When `tool_ids` is set:
  - For each `(server_id, toolset)` in `mcp_toolsets`, derive `allowed = {name for id in tool_ids if id.startswith(f"{server_id}.") for name in [id.split(".", 1)[1]]}`. If `allowed` is empty for that server, drop the toolset entirely. Otherwise, pass `allowed` to the toolset (either at construction in PR-A's modified `build_toolset_for_doc`, or by wrapping the toolset's `get_tools()` if ADK doesn't support `tool_filter`).
  - Filter `function_tools` to those whose qualifier is `function.{tool.name}` in `tool_ids`.
- Cap-check still runs at the end; when `tool_ids` is set the count is simply `len(tool_ids)`.

### 5.4 Auth + validation (PR-A)

- `GET /accounts/{account_id}/tools` requires the standard `require_account_access` dependency (same as AH-PRD-02's CRUD endpoints).
- `tool_ids` validation in Create/Update:
  - Every ID must be `function.<name>` for a tool present in the catalogue's `function_tools` OR `<mcp_server>.<tool_name>` for a tool present in `tools:` whose `mcp_server` matches.
  - Length cap: `len(tool_ids) <= 30`.
  - Note: validation does **not** check whether the tool is currently available to the account. An account that disconnects an integration retains its agent's `tool_ids` until edited. The factory will silently drop unavailable tools at construction time and log a warning.

### 5.5 ADK `McpToolset.tool_filter` verification (PR-A)

Verify during implementation whether the installed ADK version accepts a `tool_filter` argument on `McpToolset` (or exposes equivalent constructor wiring). Two acceptable outcomes:

- **Supported** → extend `build_toolset_for_doc(server_id, doc, *, allowed_tool_names=None)` to pass it through.
- **Not supported** → wrap the returned `McpToolset` in a thin adapter that intercepts `get_tools()` (or whichever lifecycle method ADK uses to surface tools to `LlmAgent`) and filters by name. Adapter lives in the same `mcp.py` module.

Either outcome is contained inside `agent_factory/mcp.py`; the public surface (`build_toolset_for_doc`) gains one optional kwarg.

## 6. API contract

| Method | Path | Purpose | New / changed |
|--------|------|---------|---------------|
| `GET` | `/api/v1/accounts/{account_id}/tools` | List the account's available tools (global default + integration-gated) | New |
| `POST` | `/api/v1/accounts/{account_id}/agent-configs/` | Accepts optional `tool_ids` field | Changed (AH-PRD-02 endpoint) |
| `PUT` | `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | Accepts optional `tool_ids` field | Changed (AH-PRD-02 endpoint) |
| `GET` | `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | Response includes `tool_ids` | Changed (AH-PRD-02 endpoint) |

Validation failures on `tool_ids` produce FastAPI 422 with per-ID `detail` entries (mapped onto the form by `mapServerErrors` introduced in PR #471).

## 7. Acceptance criteria

1. **Tool catalogue extended.** `tools.yaml` includes per-tool entries for every MCP server registered under `mcp_server_configs/` in dev. A new top-level `function_tools:` section lists at minimum `create_visualization` tagged `default_global: true`. `ToolRegistry.list_function_tools()` and `list_default_global_tools()` return the expected entries.
2. **`tool_ids` on agent config.** All four Pydantic models (`AgentConfig`, `AgentConfigCreate`, `AgentConfigOverlayUpdate`, `MergedAgentConfig`) declare `tool_ids: list[str] | None`. The merge in `routers/agent_configs.py:_merge_from_data` populates `MergedAgentConfig.tool_ids` from the overlay when present and the global when absent, mirroring how `mcp_servers` / `skill_ids` flow today.
3. **Catalogue + cap validator.** `POST` and `PUT` reject `tool_ids` containing IDs absent from the catalogue, or whose length exceeds 30, with a 422 detail naming the offending field. Tools whose owning integration is currently disconnected pass validation (per §5.4 note).
4. **Factory tool filtering.** Given an agent whose `tool_ids = ["google_analytics_mcp.list_ga_accounts"]` and `mcp_servers = ["google_analytics_mcp"]`, the factory's roster contains exactly one tool (`list_ga_accounts`) from that toolset. `tool_ids = None` continues to wire every tool from every attached server. `tool_ids = []` wires zero tools.
5. **Function-tool gating.** When `tool_ids` is set and does not include `function.create_visualization`, the function tool is not present in the agent's roster. When `tool_ids is None`, function tools are included exactly as they are today.
6. **Inventory endpoint shape + auth.** `GET /api/v1/accounts/{account_id}/tools` returns `AccountToolsResponse`. Function tools are always present. MCP tools appear only when the account has a `connected` `platform_connections/{platform_id}` doc whose `platform_id` maps to the tool's `mcp_server`. Unauthorized callers receive 403.
7. **Frontend client + query.** `useAccountTools(accountId)` returns the typed response shape, keyed on `accountId`. Loading + error states are surfaced to the picker.
8. **Tool picker UX.** `AgentToolPicker` renders a `Built-in` group for function tools plus one group per `mcp_server` represented in the response. Each group has a select-all toggle and a per-tool checkbox. A search input filters tools by name and description (case-insensitive). Empty integration groups render a "Connect [Platform name]" link to `/settings/integrations`.
9. **Form integration — Create.** The picker appears in `AgentCreatePage` between the description field and the existing disabled placeholder rows. The submit payload includes `tool_ids` as an array (or omitted when the user has made no selection — see §9 open question on `None` vs. `[]`).
10. **Form integration — Edit.** The picker appears in `AgentEditView` in the same position. `tool_ids` is dirty-tracked alongside other editable fields and included in the `PUT` payload only when changed. Saving without touching the picker does not write `tool_ids`.
11. **Legacy agent load behaviour.** Loading an agent that was last saved before this PRD (`tool_ids is None` in Firestore) into the edit view pre-selects every currently-available tool from the agent's attached servers — so a no-op save preserves prior runtime behaviour. The frontend may convert `None` → "pick all current" only at load time; subsequent state changes write the explicit list.
12. **Default function tools wired through the factory (PR-C).** Every specialist built via `agent_factory/hierarchy.py:build_hierarchy` with `tool_ids = None` includes every `default_global: true` entry from `function_tools:` in its roster (today: `create_visualization`; future entries auto-propagate). When `tool_ids = []` no function tools are wired; when `tool_ids = ["function.x", …]` only listed `function.{name}` entries are wired (existing PR-A behaviour). Verify by spying on the `tools=` argument to `build_agent` for a representative specialist.

## 8. Test plan

### Unit (PR-A)

- `account_tools_service.compose_inventory` — given a fake catalogue + fake connections, returns the expected inventory shape; function tools always present; integration-gated tools appear only when connection is `connected`.
- `roster.resolve_specialist_roster` — `tool_ids is None` returns full roster; `tool_ids = []` returns zero tools; `tool_ids = ["server.name"]` returns exactly that one tool; cap is enforced.
- `mcp.build_toolset_for_doc` — when `allowed_tool_names` is provided, the toolset surfaces only the listed tools (verify via the ADK passthrough or the wrapper, whichever path lands).
- Pydantic validators — `tool_ids` catalogue and cap checks pass valid inputs and reject invalid ones.

### Integration (PR-A)

- `GET /accounts/{id}/tools` end-to-end: seed `platform_connections/google_analytics_mcp` (connected) → response includes GA tools + function tools; without the connection → only function tools; unauthorized caller → 403.
- Agent CRUD round-trip with `tool_ids`: `POST` create with `tool_ids = […]` → persist → `GET` returns the list on `MergedAgentConfig` → `PUT` clears to `[]` → `GET` returns `[]`.
- Cap rejected at the API boundary: `POST` with 31 IDs → 422.

### Frontend (PR-B)

- `AgentToolPicker.test.tsx` — render with mocked `useAccountTools`; toggle a single tool; select-all on a group; search filter narrows the list; empty integration group renders the connect link.
- `AgentCreatePage.test.tsx` — extend the existing test: pick two tools, assert payload includes `tool_ids`.
- `AgentEditView.test.tsx` — dirty tracking: not touching the picker → `tool_ids` absent from PUT; toggling once → present.

### Manual verification

- Dev server: create a fresh agent → tool picker shows function-tools group + any connected-integration groups; pick a subset; save; reopen edit view → selection persists.
- Disconnect an integration; reload an agent that referenced its tools → picker shows the tools as unselected (or annotated as unavailable, depending on §9 UX choice); save → backend persists.
- Agent runtime smoke (requires deploy): create an agent with `tool_ids` restricting GA to `list_ga_accounts`, send a query that would normally trigger `query_ga_report` → factory log / trace confirms only `list_ga_accounts` is wired.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| **ADK `McpToolset.tool_filter` may not exist on the installed ADK version.** | PR-A §5.5 — verify during implementation; fall back to a wrapper around `get_tools()` in the same module. Contained inside `agent_factory/mcp.py`. |
| **`mcp_servers` / `skill_ids` merge mystery.** `MergedAgentConfig.mcp_servers` is populated today but `AgentConfig` (storage shape) does not model it. Likely populated via `_merge_from_data` lifting fields straight from the raw doc. | Audit `_merge_from_data` in `routers/agent_configs.py` before implementing the `tool_ids` merge; mirror whichever pattern already works for `mcp_servers` and `skill_ids`. |
| **Tools whose integration was disconnected.** An agent's `tool_ids` may reference tools that are no longer "available" to the account. | Backend: validator does not gate on availability (a user can keep their selection across temporary disconnects). Factory: drops unavailable tools at construction with a warning. Frontend: render previously-selected-but-unavailable tools with a "reconnect to use" affordance (precise UX TBD during PR-B). |
| **`null` vs `[]` UX on first save of a legacy agent.** Backend treats `null` as "no filter" but `[]` as "no tools." If the picker writes `[]` whenever a user opens the edit view and doesn't make a change, legacy agents lose every tool on save. | Pre-select all currently-available tools when loading an agent whose stored `tool_ids is None`; only emit `tool_ids` in the PUT payload when the user actually toggles something (AC #10 + AC #11). |
| **30-tool cap interaction with skills.** SK-PRD-02 counts skills against the same 30-tool cap. If SK-PRD-04 and this PRD ship close together, a user could overflow the cap from two different form sections. | Both PRDs reference `MAX_TOOLS_PER_SPECIALIST`. The Create/Update validator should reject when `len(tool_ids) + len(skill_ids) > 30`. Cross-PRD coordination needed if the two ship in the same release window. |
| **`platform_id → mcp_server_id` map drift.** A new MCP server added under a different platform mapping wouldn't show up in the inventory until the hardcoded map is updated. | Short-term: keep the map in `account_tools_service.py` adjacent to the catalogue extension. Long-term: promote to `PlatformDefinition` on the Integrations side (out of scope here). |

### Open questions

- **Q:** Should the picker offer an explicit "Use all tools from attached servers" toggle that maps to `tool_ids = null`? → Defer to PR-B. Initial proposal: no — picking nothing means "no tools" and `null` is reserved for the legacy-load path. Revisit if the friction is high.
- **Q:** Should the inventory endpoint also include "available but already attached at the agent level" hints to support the picker rendering current selection? → No — the picker is given both the inventory and the agent's `tool_ids`; cross-reference is a client concern.
- **Q:** When an integration is disconnected, should agents that reference its tools be automatically updated? → No. Manual edit only; the factory drops gracefully. Revisit if support burden materializes.

## 10. Reference

- Upstream: [AH-PRD-02 (Agent Factory)](./AH-PRD-02-agent-factory.md), [Integrations README](../../integrations/README.md)
- Adjacent: [SK-PRD-02 (Agent Integration)](../../skills/projects/SK-PRD-02-agent-integration.md), [SK-PRD-04 (Agent Builder Controls)](../../skills/projects/SK-PRD-04-agent-builder-controls.md)
- Architecture: `docs/KEN-E-System-Architecture.md` §2.5 (Tool-assignment & routing model)
- Component README: [`agentic-harness/README.md`](../README.md) §2.5 (Tool-assignment & routing model — cap + curated rosters)
- MCP architecture: [`../mcp-architecture.md`](../mcp-architecture.md) §6 (Firestore config schema)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; C-2, C-4, C-5, C-6, C-8; T-1, T-3, T-4, T-5
