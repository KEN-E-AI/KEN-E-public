# Agent-as-Tool Capability + Google Web Search — Design Note

**Type:** Design note for a single Linear issue — **not** a project PRD (no `projects/` entry, no Linear project).
**Linear issue:** AH-98 (`[KEN-E] Agentic Harness`)
**Builds on:** [AH-PRD-06 — Per-Agent Tool Mapping](./projects/AH-PRD-06-tool-mapping.md) (the `tool_ids` allowlist, `tools.yaml` catalogue, `GET /accounts/{id}/tools` inventory endpoint, Workflows tool picker, and ≤30-tool cap this work extends) · [AH-PRD-09 — Per-Turn Dispatch](./projects/AH-PRD-09-per-turn-dispatch.md) (`specialist_runtime` + root build path).
**Effort:** ~2–4 days, single engineer. One backend-centric change (ADK schema + registry + resolver), plus small API-catalogue and frontend-verification touches.

---

## 1. Context

KEN-E's strategy researchers already have Google web search, implemented as an **agent-as-a-tool**: `create_google_search_agent()` (`app/adk/agents/strategy_agent/agents.py`) builds a leaf `Agent(name="google_search_agent", model="gemini-2.5-flash", tools=[google_search])`, and the researchers attach it via `AgentTool(agent=google_search_agent)`. This isolation is mandatory — the ADK built-in `google_search` tool cannot be combined with other tools or an `output_schema` in the same agent, so it lives in a dedicated leaf agent and is exposed as an agent-as-tool.

The root agent (`ken_e`, Firestore config `ken_e_chatbot`) has `tools=[]` and no web-search capability today; it only delegates to specialists (`company_news_agent`, `google_analytics_agent`) via ADK's native `transfer_to_agent` ([AH-PRD-09](./projects/AH-PRD-09-per-turn-dispatch.md)).

[AH-PRD-06](./projects/AH-PRD-06-tool-mapping.md) shipped the per-agent tool-assignment rails end-to-end: a static catalogue (`tools.yaml`), an account inventory endpoint (`GET /api/v1/accounts/{account_id}/tools` → `account_tools_service.compose_inventory`), the Workflows tool picker (`frontend/src/pages/workflows/agents/AgentToolPicker.tsx`), and a per-agent `tool_ids` allowlist validated against the catalogue and capped at 30. But those rails understand **only two tool kinds**:

| Kind | `ToolDefinition.source` | Catalogue id | Resolved instance |
|------|-------------------------|--------------|-------------------|
| MCP tool | `"mcp"` | `{mcp_server}.{tool}` | `McpToolset` (integration-gated) |
| Function tool | `"function"` | `function.{name}` | `FunctionTool` (attachable only when `default_global: true`) |

An `AgentTool` (agent-as-a-tool) is neither. Two concrete gaps block making Google Search a picker-selectable tool:

1. **No representation.** `ToolDefinition.source` is `Literal["mcp", "function"]` (`app/adk/tools/registry/tool_schema.py`), and the function instance registry is typed `dict[str, FunctionTool]` (`app/adk/tools/registry/function_tool_registry.py`). An `AgentTool` fits neither cleanly.
2. **No opt-in attach path.** `compose_inventory` only surfaces `default_global: true` function tools, and `resolve_specialist_roster` can only *narrow* the default-global set — its function-tool candidate list is `resolve_default_global_tools()`, so a non-default tool can **never** be attached even when its id is present in `tool_ids` (`app/adk/agents/agent_factory/roster.py`). There is currently no way to assign a tool that is not already on by default.

This design note specifies a first-class **agent-as-tool** kind (`source="agent"`), the **opt-in attach path** the new kind needs, and registers **Google Web Search** as the first such tool — selectable from the Workflows picker and assignable to any agent via `tool_ids`. Parallelism is already free: ADK 1.27.5 executes multiple tool calls from a single model turn concurrently (`handle_function_call_list_async` → `asyncio.gather`, `google/adk/flows/llm_flows/functions.py`), so an agent that emits several `agent.google_search` calls in one turn runs them in parallel with no extra machinery.

## 2. Scope

### In scope

- Add `"agent"` to `ToolDefinition.source` and the matching `_validate_source_consistency` rules.
- Add an `agent_tools:` section to `tools.yaml` with a single entry: `google_search`, `source: agent`, `default_global: false`.
- Add an **agent-tool instance registry** (parallel to `function_tool_registry.py`) that registers `AgentTool(agent=create_google_search_agent())` and is imported at startup so the registration side effect runs before rosters resolve.
- Extend the roster resolver so agent tools are candidates filtered by `agent.{name} ∈ tool_ids` (opt-in: candidate set is **all** catalogued agent tools, not just default-global), counted toward the ≤30 cap, and the `per_server_allowed_tools` reserved-prefix set excludes `"agent"`.
- Teach both catalogue parsers (the ADK `ToolRegistry` loader and the API's independent `account_tools_service` parser) about the `agent_tools:` section; surface agent tools in the inventory as `source="global_default"` so the picker groups them under "Built-in"; add `agent.{name}` to `list_known_tool_ids` so config validation accepts the selection.
- Relocate / share `create_google_search_agent()` so the catalogue tool does not import from the `strategy_agent` package (e.g. a shared `app/adk/agents/shared/` or `app/adk/tools/agent_tools/` module; the strategy agents keep importing it from the new home).

### Out of scope

- **Feature-flag gating. No flag.** KEN-E has **no live production users yet**, so the catalogue entry ships unconditionally — no kill switch, no targeted rollout. (Revisit only if a later capability needs dark-launch after GA.)
- Replacing the strategy researchers' existing hardcoded `AgentTool` wiring — they keep working as-is; this work only changes where `create_google_search_agent()` is imported from.
- A non-Gemini / raw-SERP search backend. This reuses the Gemini-grounded built-in `google_search`.
- Closing the *function*-tool opt-in gap (non-default `function` tools still cannot be attached). The new agent-tool path is built correct-by-construction for opt-in; generalising the function path is a separate follow-up.

### Rollout decision (giving the root agent web search)

Once `agent.google_search` is a real catalogue id, giving it to the root agent ("Kinney") is a config change (`tool_ids` on `ken_e_chatbot`) — **but** the root is built with `tools=[]` in `app/adk/agents/agent_factory/hierarchy.py` and bypasses the specialist roster path. Routing the root build through the same agent-tool resolution is the clean end state and is **included** here as §5.4; if descoped, the alternative is a one-line hardcoded `AgentTool` on the root. Either way it is separable from the user-facing picker work.

## 3. Dependencies

| Dependency | Why |
|---|---|
| [AH-PRD-06](./projects/AH-PRD-06-tool-mapping.md) | Provides the catalogue, inventory endpoint, picker, `tool_ids` field + validator, and the ≤30 cap this work extends. Hard prerequisite. |
| [AH-PRD-09](./projects/AH-PRD-09-per-turn-dispatch.md) | `specialist_runtime` is where agent-tool candidates get resolved per turn; the root-build path (`hierarchy.py`) is where §5.4 wires the root's `tool_ids`. |
| ADK ≥ 1.27.5 (pinned) | Parallel tool-call execution (`functions.py`) + `AgentTool` + built-in `google_search`. Already the repo pin. |
| `create_google_search_agent()` | Reused unchanged; only its module home moves. |

## 4. Data contract

### `ToolDefinition` schema (`app/adk/tools/registry/tool_schema.py`)

Extend the `source` literal and validation:

- `source: Literal["mcp", "function", "agent"]` — `"agent"` denotes a tool whose runtime instance is an ADK `AgentTool` wrapping a leaf sub-agent.
- `_validate_source_consistency`: `source="agent"` requires `mcp_server=None` (same rule as `function`); `default_global=True` remains allowed only for `function` and `agent` built-ins (Google Search ships `default_global: false`).

### Catalogue (`app/adk/tools/registry/config/tools.yaml`)

New third top-level section:

```yaml
agent_tools:
  # Tools whose runtime instance is an ADK AgentTool wrapping a leaf sub-agent.
  # Always surfaced in the picker (Built-in group); attached only when an
  # agent's tool_ids lists them (opt-in).
  - name: google_search
    description: >-
      Search the public web via Google and return grounded results. Assignable
      to any agent. The agent may issue several google_search calls in a single
      turn — they run in parallel.
    category: research
    source: agent
    default_global: false
    keywords: [search, web, google, research, lookup, news, current, public]
    estimated_tokens: 200
```

### Tool ID format

Reserved third namespace, consistent with AH-PRD-06's single string namespace:

- Agent tools: `agent.{tool_name}` — e.g. `agent.google_search`.

### Backward-compatibility / attach semantics

| Stored `tool_ids` | Agent-tool behaviour |
|---|---|
| `None` (existing agents) | Only `default_global: true` agent tools are attached. `google_search` is `default_global: false` → **not** attached. No behavioural change for any existing agent. |
| `[]` | No tools, including no agent tools. |
| `[…, "agent.google_search", …]` | `google_search` AgentTool is attached, counted as 1 toward the ≤30 cap. |

### Inventory response shape (`AccountToolEntry`)

Agent tools are emitted with `source="global_default"` (so the existing picker groups them under "Built-in") and `mcp_server=null`, `integration_platform=null`:

```json
{
  "tool_id": "agent.google_search",
  "name": "google_search",
  "description": "Search the public web via Google and return grounded results...",
  "category": "research",
  "source": "global_default",
  "mcp_server": null,
  "integration_platform": null
}
```

## 5. Implementation outline

### 5.1 File inventory

| Action | File | Note |
|--------|------|------|
| Modify | `app/adk/tools/registry/tool_schema.py` | Add `"agent"` to `source` literal; extend `_validate_source_consistency`. |
| Modify | `app/adk/tools/registry/config/tools.yaml` | Add `agent_tools:` section with the `google_search` entry. |
| Modify | `app/adk/tools/registry/tool_registry.py` | `load_from_config` parses `agent_tools:` (loads with `source="agent"`); add `list_agent_tools()`. |
| Create | `app/adk/tools/registry/agent_tool_registry.py` | Mirror of `function_tool_registry.py`: `register_agent_tool(name, AgentTool)` / `get_agent_tool` / `resolve_agent_tools(registry)` / `clear_agent_tool_registry` (test-only). Holds `dict[str, AgentTool]`. |
| Create | `app/adk/agents/shared/google_search_tool.py` (or `app/adk/tools/agent_tools/`) | New home for `create_google_search_agent()`; registers `AgentTool(agent=create_google_search_agent())` under `"google_search"` at import. |
| Modify | `app/adk/agents/strategy_agent/agents.py` | Re-export / import `create_google_search_agent` from the new home (no behaviour change for strategy agents). |
| Modify | `app/adk/agents/agent_factory/hierarchy.py` | Import the registering module at startup (same pattern as function-tool modules) so the side effect fires before `build_hierarchy` resolves rosters. |
| Modify | `app/adk/agents/agent_factory/roster.py` | See §5.2 — thread agent tools through `resolve_specialist_roster`, fix `per_server_allowed_tools` reserved prefixes, include agent tools in the cap count. |
| Modify | `app/adk/agents/agent_factory/specialist_runtime.py` | Resolve agent-tool candidates (`resolve_agent_tools`) and pass into `resolve_specialist_roster`. |
| Modify | `api/src/kene_api/services/account_tools_service.py` | `_parse_catalogue` reads `agent_tools`; `compose_inventory` emits them (`source="global_default"`, `tool_id=agent.{name}`) unconditionally; `list_known_tool_ids` adds `agent.{name}`. ⚠ This parser is intentionally independent of the ADK package — keep it in sync with the `ToolRegistry` loader. |
| Verify | `frontend/src/pages/workflows/agents/AgentToolPicker.tsx` | Confirm it groups by the API `source` field (no hardcoded built-in list); a `global_default` agent tool should appear under "Built-in" with no change. |
| Create | tests under `app/adk/.../tests/` + `api/tests/` | See §8. |

### 5.2 Roster resolution (`roster.py`)

- `resolve_specialist_roster(...)` gains an `agent_tools: list[Any]` parameter (the full set of catalogued agent-tool instances).
  - `tool_ids is None` → include only `default_global: true` agent tools (Google Search excluded).
  - `tool_ids` set → keep agent tools whose `agent.{name}` is in `tool_ids`; append after MCP + function tools.
- `per_server_allowed_tools(...)` currently skips ids whose prefix is `"function"`. Extend the reserved set to `{"function", "agent"}` so `agent.google_search` is not mis-grouped as an MCP server literally named `agent`. **(Load-bearing — missing this routes the id into the MCP path.)**
- Cap count (`count_specialist_tool_roster` / the `tool_ids` defensive branch) includes `len(agent_tools_kept)`.

### 5.3 Startup registration

`create_google_search_agent()` is reused verbatim from its new shared home. The registering module calls `register_agent_tool("google_search", AgentTool(agent=create_google_search_agent()))` at import; `hierarchy.py` imports it at startup (identical convention to the function-tool modules). The `AgentTool`'s `.name` must equal `google_search` so the `agent.{name}` filter matches.

### 5.4 Root-agent wiring (optional, included)

Route the root build in `hierarchy.py` through the same agent-tool resolution so the root's `tool_ids` (on `ken_e_chatbot`) can include `agent.google_search`, instead of the current hardcoded `tools=[]`. If descoped, fall back to a hardcoded `AgentTool(agent=create_google_search_agent())` on the root. Either way, instruct the root that it may issue multiple `google_search` calls in one turn for independent sub-questions (they run in parallel).

## 6. API contract

No new endpoints. Existing AH-PRD-06 surface gains agent-tool entries:

| Method | Path | Change |
|--------|------|--------|
| `GET` | `/api/v1/accounts/{account_id}/tools` | Response now includes `agent.*` entries (`source="global_default"`). |
| `POST` / `PUT` | `/api/v1/accounts/{account_id}/agent-configs/{…}` | `tool_ids` accepts `agent.{name}` ids (validated against the catalogue by the existing `_reject_unknown_tool_ids`). |

## 7. Acceptance criteria

1. **Schema.** `ToolDefinition.source` accepts `"agent"`; an `agent` tool with `mcp_server != None` is rejected by validation; an `agent` tool round-trips through `ToolRegistry.load_from_config`.
2. **Catalogue.** `tools.yaml` has an `agent_tools:` section with `google_search` (`source: agent`, `default_global: false`); `ToolRegistry.list_agent_tools()` returns it.
3. **Instance registry.** `resolve_agent_tools()` returns an `AgentTool` whose `.name == "google_search"` after the registering module is imported; a missing registration is skipped with a logged warning (parity with `resolve_default_global_tools`).
4. **Opt-in attach.** An agent with `tool_ids = ["agent.google_search"]` has exactly one agent tool (`google_search`) in its resolved roster. An agent with `tool_ids = None` has **no** `google_search` (it is not default-global). `tool_ids = []` → zero tools.
5. **Reserved-prefix routing.** `per_server_allowed_tools(["agent.google_search"])` returns `{}` (or omits `agent`), i.e. no phantom MCP server named `agent` is created.
6. **Cap.** `agent.google_search` counts as 1 against the ≤30 cap; an agent at the cap plus one agent tool raises `RosterCapExceededError`.
7. **Inventory + validation.** `GET /accounts/{id}/tools` includes `agent.google_search` with `source="global_default"` for every account regardless of integrations; `POST`/`PUT` accept `tool_ids` containing `agent.google_search` and still reject unknown ids.
8. **Picker.** The Workflows tool picker shows Google Search under "Built-in"; selecting it persists `agent.google_search` to the agent's `tool_ids`.
9. **Parallelism.** An agent assigned `agent.google_search` that emits ≥2 `google_search` calls in one model turn executes them concurrently (covered by an ADK behaviour assertion / trace check).
10. **No flag.** The capability ships with no feature-flag gate; no flag key is registered.

## 8. Test plan

### Unit
- `tool_schema`: `source="agent"` validation (valid + the `mcp_server` rejection).
- `tool_registry`: loads `agent_tools:`; `list_agent_tools()`.
- `agent_tool_registry`: register / resolve / overwrite-warning / clear.
- `roster`: opt-in attach matrix (`None` / `[]` / `["agent.google_search"]`); `per_server_allowed_tools` reserved-prefix; cap counting incl. agent tools.

### Integration
- `account_tools_service.compose_inventory`: agent tool present for an account with no integrations; `list_known_tool_ids` includes `agent.google_search`.
- `agent-configs` `POST`/`PUT`: accepts `agent.google_search`; rejects `agent.bogus`.
- Factory end-to-end: build a specialist from a config carrying `tool_ids=["agent.google_search"]`; assert the roster contains the `AgentTool`.

### Manual
- In Workflows, create an agent, tick Google Search, save; confirm a chat turn fans out parallel searches and the trace shows a merged tool event.

## 9. Risks & open questions

- **Two catalogue parsers drift.** The API parses `tools.yaml` independently of the ADK package (by design). Adding `agent_tools:` to one and not the other silently breaks either the picker or resolution. *Mitigation:* a shared test asserting both parsers enumerate the same `agent.*` ids.
- **Shared AgentTool singleton under parallel calls.** One `AgentTool` instance is reused across concurrent invocations; each call gets its own `InvocationContext`, so this should be safe, but the strategy path only ever called it sequentially. *Mitigation:* concurrency smoke test (AC #9).
- **Cost / latency.** Each `google_search` call is a grounded `gemini-2.5-flash` sub-invocation. Opt-in (`default_global: false`) bounds blast radius to agents that explicitly select it.
- **Open:** Should `create_google_search_agent`'s model / temperature become catalogue-configurable, or stay code-pinned? Defer — code-pinned for now.
- **Open:** Confirm the picker has no hardcoded built-in allowlist; if it does, add one frontend line (else no frontend change).

## 10. Reference

- [AH-PRD-06 — Per-Agent Tool Mapping](./projects/AH-PRD-06-tool-mapping.md) — the rails this extends.
- [AH-PRD-09 — Per-Turn Dispatch Agent](./projects/AH-PRD-09-per-turn-dispatch.md) — `specialist_runtime` + root build.
- [Agentic Harness README §2.5](./README.md#25-tool-assignment--routing-model) — tool-assignment & routing model.
- [MCP Architecture](./mcp-architecture.md) — ADK internals; built-in tool constraints.
- Code: `app/adk/agents/strategy_agent/agents.py` (`create_google_search_agent`), `app/adk/tools/registry/function_tool_registry.py` (registry pattern to mirror), `app/adk/agents/agent_factory/roster.py` (resolver), `api/src/kene_api/services/account_tools_service.py` (inventory).
- ADK: `google/adk/flows/llm_flows/functions.py` (`handle_function_call_list_async` — parallel tool execution); `google.adk.tools.agent_tool.AgentTool`; `google.adk.tools.google_search`.
