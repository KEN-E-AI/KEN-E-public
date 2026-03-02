# Sprint 3b: Agent Config & Context Optimization

## 1. Sprint Goal

> Allow a user of the application to discuss his company strategy with KEN-E with < 5 second response time from the chatbot, and retrieve data from Google Analytics.

**Sprint Number:** 3.5
**SCRUM Team:** Core AI
**Velocity:** 37 story points (9 stories)

---

## 2. Background: How KEN-E Works Today

### 2.1 Agent Configuration

The KEN-E chat agent is defined in `app/adk/agents/ken_e_agent.py`. The `create_ken_e_agent()` function (line 29) builds a Google ADK `Agent` instance with a model, system instructions, tools, and callbacks.

**What comes from Firestore:** The function calls `load_config_from_firestore("ken_e_chatbot")` (line 40) which fetches the `ken_e_chatbot` document from the `agent_configs` Firestore collection. However, **only the model name is used** (line 41). If the load fails, it falls back to `"gemini-2.0-flash"` (line 51).

The Firestore document contains several additional fields that are all ignored:

| Firestore Field | Used? | Notes |
|---|---|---|
| `model` | Yes | Only field consumed by `create_ken_e_agent()` |
| `instruction` | **No** | Overridden by hardcoded instruction (lines 77-149) |
| `description` | **No** | Not read |
| `name` | **No** | Agent name is hardcoded as `"ken_e"` (line 73) |
| `generate_content_config` | **No** | `temperature` and `max_output_tokens` are not passed to the Agent |
| `metadata` | Logged only | Version and variant are logged but not used functionally |

**What is hardcoded** in `app/adk/agents/ken_e_agent.py`:

- **Agent name**: `"ken_e"` (line 73)
- **System instruction**: The full prompt (lines 77-149), covering agent identity, organization context parsing, two capabilities (Company News, Google Analytics), routing instructions, and examples
- **Tools**: `search_company_news` and `query_google_analytics` (line 150), wrapper functions (lines 54-70) that delegate to `dispatch_to_company_news` and `dispatch_to_google_analytics`
- **Callbacks**: `adk_before_tool_callback` and `adk_after_tool_callback` (lines 75-76)

**Existing but unused infrastructure:** `app/adk/agents/strategy_agent/config_loader.py` contains `create_agent_from_firestore_config()` (line 144) which **does** use the full Firestore config including instructions via `Agent.from_config()` (line 218). This function is used by other agents (e.g., strategy agents) but is **not** used by the KEN-E chat agent.

### 2.2 Organization Context Flow

The KEN-E system instruction references `[ORGANIZATION CONTEXT]` that is "included with every message." This context is not part of the agent definition — it is injected by the API layer at request time.

**Injection entry points** — Context injection happens in the chat router (`api/src/kene_api/routers/chat.py`):

- **Non-streaming endpoint**: calls `inject_context_into_message()` at line 1442
- **Streaming endpoint**: calls `inject_context_into_message()` at line 1800

Both pass the user's `account_id` (or the first accessible account as fallback, lines 1437-1439 and 1795-1797).

**The injection function** — `inject_context_into_message()` (line 331) performs two types of injection:

1. **Organization context (always injected):**
   - Calls `load_organization_context_from_neo4j(account_id)` (line 361)
   - Runs a Cypher query against Neo4j fetching Account node (`account_id`, `company_name`, `company_overview`, `industry`, `websites`, `customer_regions`) and BrandIdentity node (`voice_tone_description`, `personality_description`, `mission_description`)
   - Formats as markdown with YAML frontmatter (lines 112-139)
   - Wraps in `[ORGANIZATION CONTEXT]...[END CONTEXT]` delimiters

2. **Campaign context (conditionally injected):**
   - Only if the message contains campaign-related keywords (line 388; keyword list in `shared/context_utils.py` lines 49-69)
   - Currently returns **mock data** — real Neo4j campaign queries are not yet implemented (line 173)
   - If triggered, a `[CAMPAIGN CONTEXT]...[END CAMPAIGN CONTEXT]` block is appended (`shared/context_utils.py` line 91)

**Message format after injection:**

```
[ORGANIZATION CONTEXT]
---
account_id: abc123
company: Acme Corp
industry: Technology
---

# Company Context
Acme Corp is a technology company...

## Brand Voice & Communication Style
**Voice & Tone:** Professional, data-driven...
**Brand Personality:** Innovative, approachable...
**Mission & Values:** To empower businesses with...
[END CONTEXT]

<original user message>
```

### 2.3 Session State

The KEN-E chat agent uses ADK session state to persist data across messages within a conversation. Session state is a key-value store managed by `VertexAiSessionService`. The LLM does **not** automatically see session state — values must be explicitly surfaced via template placeholders (`{key}`) in instructions, an `InstructionProvider` callable, or read programmatically in tools/callbacks via `tool_context.state`.

**State populated at session creation** (`api/src/kene_api/routers/chat.py` lines 648-808):

| Key | Type | Source | Line |
|---|---|---|---|
| `account_id` | string | Validated from user context or request parameter | 665 |
| `accessible_accounts` | list[string] | All account IDs the authenticated user can access | 666 |
| `organization_context` | string | Org context markdown from Neo4j/Redis (~1,500 tokens) | 805 |
| `ga_credentials` | dict | OAuth credentials from Firestore (`access_token`, `refresh_token`, `tenant_id`, `selected_property_ids`, `selected_properties`, `expires_at`) | 808 |

The `organization_context` and `ga_credentials` are loaded in parallel via `asyncio.gather()` (line 798), with Redis caching to avoid repeated Neo4j/Firestore queries across sessions.

**State written during session:**

| Key | Type | Written By | Purpose |
|---|---|---|---|
| `ga_credentials` | dict | `_refresh_ga_token_if_needed()` (`hooks.py:78`) | Updates `access_token` and `expires_at` on token expiry |
| `_tool_start_time` | float | `adk_before_tool_callback()` (`hooks.py:199`) | Tracks tool execution duration for usage metrics |
| `_requires_reauth` | bool | `adk_before_tool_callback()` (`hooks.py:212`) | Signals user needs to re-authenticate (one-shot flag, cleared at `chat.py:2206`) |
| `_reauth_service` | string | `adk_before_tool_callback()` (`hooks.py:213`) | Identifies which service needs re-auth, e.g. `"google-analytics"` (one-shot flag, cleared at `chat.py:2207`) |

**How session state is currently used:** Session state is **not** referenced in the agent's system instruction. It is only read programmatically:

- **Tool dispatch handlers** (`dispatch_handlers.py`) read `tool_context.state` for `account_id` (line 48/119), `organization_context` (line 58/142), `ga_credentials` (line 120), and `campaign_context` (line 147).
- **Security hooks** (`hooks.py`) read and write `ga_credentials` for token refresh and set re-auth flags. The `organization_context` in session state is only consumed by dispatch handlers to re-inject into sub-agent queries — it never informs the KEN-E agent's own LLM context directly.

---

## 3. Problems Identified

### 3.1 No Single Source of Truth for Agents

**Impact:** Adding a new agent requires updating 5 separate locations (agent file, Firestore document, `ALLOWED_CONFIG_IDS` allowlist, `__init__.py` exports, upload script). There is no single source of truth for what agents exist, and no validation to catch missing Firestore configs.

KEN-E has ~13 agents scattered across multiple files with inconsistent configuration patterns. Some use Firestore config, others are fully hardcoded. The API security allowlist (`ALLOWED_CONFIG_IDS` in `agent_configs.py`) is a manually maintained hardcoded set that must be kept in sync with agent definitions. As the system scales to dozens of agents, this becomes a significant developer experience and reliability problem.

Additionally, the `create_ken_e_agent()` function loads the Firestore `ken_e_chatbot` document but only reads `config.model`. The `instruction`, `name`, `description`, and `generate_content_config` fields are all present in Firestore but ignored — the agent's system prompt is hardcoded as a 72-line string literal in `ken_e_agent.py` (lines 77-149). A fully functional `create_agent_from_firestore_config()` already exists in `config_loader.py` (line 144) and is used by other agents, but the KEN-E agent does not use it.

### 3.2 Redundant Context Injection (Triple Injection)

**Impact:** ~1,500 tokens of organization context are repeated in every message in the conversation history, increasing latency and cost proportionally to conversation length.

Organization context is currently injected in **three separate places**:

1. **Session creation** (`chat.py` line 805) — context is fetched from Neo4j/Redis and stored in `initial_state["organization_context"]` in the ADK session state.

2. **Every message** (`chat.py` lines 1442/1800) — `inject_context_into_message()` fetches the context again (from Redis/Neo4j) and prepends it as `[ORGANIZATION CONTEXT]...[END CONTEXT]` to the user message. This repeats ~1,500 tokens in every message in the conversation history.

3. **Tool dispatch** (`dispatch_handlers.py` lines 57-63, 141-144) — when KEN-E calls a sub-agent tool, the dispatch handler reads org context back from session state and injects it again into the query passed to the sub-agent.

The per-message fetch (step 2) is cached in Redis with a 15-minute TTL (`ORG_CONTEXT_TTL_SECONDS = 900`), so it does not hit Neo4j on every message. However, the context string is still prepended to every user message, accumulating repeated tokens.

**Solution approach:** The ADK `Agent` `instruction` parameter accepts a callable that receives the `InvocationContext`, which has access to session state. The org context (already stored in session state at creation) could be read once per invocation and included in the system instruction — without repeating it in every message. This eliminates the per-message `inject_context_into_message()` calls and the redundant re-injection in dispatch handlers.

### 3.3 Duplicate Context Loading Code

**Impact:** Two divergent implementations query different fields from the same Neo4j nodes, creating risk of inconsistent context and increased maintenance burden.

There are two separate implementations of the Neo4j context loading logic:

1. **API-side** (`chat.py` lines 52-170): An async version using the API's Neo4j service. Fetches `voice_tone_description`, `personality_description`, `mission_description` as free-text description fields.

2. **Agent-side** (`context_loader.py` lines 339-395): A sync version using a direct Neo4j connection. Fetches structured fields like `tone_attributes`, `do_list`, `dont_list`, `traits`, `mission_statement`, `core_values`.

Only the API-side version is used at runtime for the KEN-E chat agent. The agent-side loader returns different data that is never seen by the chat flow.

### 3.4 MCP Session Crash (Google Analytics Unavailable)

**Impact:** GA tool calls fail silently, causing the user to receive unhelpful error messages like "The tool requires a tenant ID, which I do not have" instead of analytics data. This is the primary blocker for the "retrieve data from Google Analytics" part of the sprint goal.

The Google Analytics MCP client crashes with `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`. This is a known `anyio`/`mcp` SDK issue where the SSE client's cancel scope is entered in one asyncio task but exited in another. The ADK's `session_context.py` triggers this during teardown.

The error originates in:
- `google/adk/tools/mcp_tool/session_context.py` line 149 (`_run` method)
- `mcp/client/sse.py` line 159 (`sse_client` context manager)

### 3.5 ADK Version Mismatch

**Impact:** The deployed Reasoning Engine crashes on session compaction, degrading long conversations.

The deployed environment crashes with `AttributeError: 'EventsCompactionConfig' object has no attribute 'token_threshold'`. The installed ADK version expects a `token_threshold` field that doesn't exist on the deployed `EventsCompactionConfig` class.

The crash occurs in:
- `google/adk/apps/compaction.py` line 338
- `google/adk/runners.py` line 435

This needs a redeployment with matching ADK SDK versions, or pinning the ADK version to one compatible with the Reasoning Engine runtime.

### 3.6 No Latency Observability

**Impact:** We cannot verify the < 5 second response time goal without instrumentation, and we cannot proactively detect MCP connection failures.

There is currently no structured latency tracking for the end-to-end chat request pipeline, and no health monitoring for MCP server connections. Without these, performance regressions go unnoticed until users report them.

---

## 4. User Stories

### 4.1 New Stories

| ID | Title | Points | Priority | Solves Problem |
|---|---|---|---|---|
| 1.16.3 | Create Agent Registry | 5 | High | 3.1 No Source of Truth |
| 1.16.4 | Derive API Allowlist from Agent Registry | 3 | High | 3.1 No Source of Truth |
| 1.16.5 | Add Agent Registry CI Validation Tests | 3 | High | 3.1 No Source of Truth |
| 1.1.4 | Eliminate Per-Message Context Injection | 8 | High | 3.2 Triple Injection |
| 1.1.5 | Consolidate Duplicate Context Loaders | 5 | Medium | 3.3 Duplicate Loaders |
| 1.3.6 | Fix MCP Session Cancel Scope Crash | 5 | High | 3.4 MCP Crash |
| 1.16.2 | Fix ADK EventsCompactionConfig Version Mismatch | 3 | High | 3.5 ADK Mismatch |

### 4.2 Stories Moved from Sprint 4

| ID | Title | Points | Priority | Solves Problem |
|---|---|---|---|---|
| 1.3.5 | Wire Health Monitor into API Lifecycle | 2 | High | 3.6 No Observability |
| 1.7.2 | Latency Metrics | 3 | High | 3.6 No Observability |

### 4.3 Story Details

**1.16.3 — Create Agent Registry** (Feature: 1.16 - Agent Configuration Management)

*As a developer, I want a centralized agent registry that declares every agent in the system so that there is a single source of truth for what agents exist, their categories, Firestore config doc IDs, and module paths.*

Acceptance Criteria:
- `agent_registry.py` exists at `app/adk/agents/agent_registry.py` with zero external dependencies (stdlib only: `dataclasses`, `enum`)
- `AgentCategory` enum defined with values: CHAT, ANALYTICS, NEWS, STRATEGY_RESEARCHER, STRATEGY_FORMATTER, SEARCH, SUPERVISOR, ORCHESTRATOR
- `AgentEntry` dataclass defined with fields: `name`, `config_doc_id` (str | None), `category`, `description`, `module_path`, `factory_function`, `is_top_level` (default False)
- `AGENT_REGISTRY` is an immutable `tuple[AgentEntry, ...]` containing all 13 current agents
- Helper functions exist: `get_all_config_doc_ids()`, `get_agents_by_category()`, `get_top_level_entries()`, `get_agents_missing_firestore_config()`
- `make lint` passes with new code

Key files: `app/adk/agents/agent_registry.py` (new)

---

**1.16.4 — Derive API Allowlist from Agent Registry** (Feature: 1.16 - Agent Configuration Management)

*As a developer, I want the API security allowlist (ALLOWED_CONFIG_IDS) to be automatically derived from the agent registry so that adding a new agent with a Firestore config automatically makes it accessible via the API without manually updating the allowlist.*

Acceptance Criteria:
- `ALLOWED_CONFIG_IDS` in `api/src/kene_api/routers/agent_configs.py` is replaced with `get_all_config_doc_ids()` from the registry (no more hardcoded set)
- API startup logs a validation message from the registry (warnings for agents without Firestore configs, not errors)
- `validate_registry_at_startup()` is called in the FastAPI lifespan in `api/src/kene_api/main.py`
- Existing API tests (`api/tests/test_agent_configs.py`) still pass with derived allowlist
- `GET /api/v1/agent-configs/` returns the same list of config IDs as before
- `make lint` passes

Depends on: 1.16.3

Key files: `api/src/kene_api/routers/agent_configs.py` lines 24-34; `api/src/kene_api/main.py`

---

**1.16.5 — Add Agent Registry CI Validation Tests** (Feature: 1.16 - Agent Configuration Management)

*As a developer, I want CI tests that validate the agent registry is consistent with the rest of the codebase so that adding a new agent without updating the registry or missing a Firestore config is caught automatically before merge.*

Acceptance Criteria:
- `test_agent_registry.py` exists at `app/adk/agents/tests/test_agent_registry.py`
- Test: no duplicate agent names in registry
- Test: no duplicate config_doc_ids (excluding None)
- Test: `ALLOWED_CONFIG_IDS` in API router equals registry-derived set
- Test: every `is_top_level=True` agent appears in `__init__.py.__all__`
- Test: all STRATEGY_RESEARCHER and STRATEGY_FORMATTER agents have a `config_doc_id`
- Test: no empty descriptions in any registry entry
- Test: each `module_path` is importable (or at least exists as a file)
- All tests pass with `pytest app/adk/agents/tests/test_agent_registry.py -v`
- `make lint` passes

Depends on: 1.16.3

Key files: `app/adk/agents/tests/test_agent_registry.py` (new)

---

**1.1.4 — Eliminate Per-Message Context Injection** (Feature: 1.1 - Context Manager)

*As a system architect, I want organization context to be injected once via a dynamic instruction callable instead of prepended to every user message, so that we eliminate ~1,500 repeated tokens per message in conversation history.*

Acceptance Criteria:
- Organization context is injected via ADK dynamic instruction callable (`InstructionProvider`) reading from session state
- `inject_context_into_message()` calls removed from `chat.py` non-streaming (line 1442) and streaming (line 1800) endpoints
- Context re-injection removed from `dispatch_handlers.py` (lines 57-63, 141-144)
- Organization context still available to sub-agents via session state
- Token usage per conversation reduced by ~1,500 tokens per message after the first
- All existing chat functionality preserved (company news and GA queries work correctly)
- Integration tests verify context is available to the agent and sub-agents

Key files: `api/src/kene_api/routers/chat.py` lines 331-400, 805, 1442, 1800; `app/adk/agents/utils/dispatch_handlers.py` lines 57-63, 141-144; `app/adk/agents/ken_e_agent.py` line 77

---

**1.1.5 — Consolidate Duplicate Context Loaders** (Feature: 1.1 - Context Manager)

*As a developer, I want a single implementation of the Neo4j organization context loader so that context format is consistent and maintenance burden is reduced.*

Acceptance Criteria:
- Single context loading implementation replaces both API-side (`chat.py` lines 52-170) and agent-side (`context_loader.py` lines 339-395) versions
- All Neo4j fields from both implementations are included (free-text descriptions AND structured fields like `tone_attributes`, `do_list`, `dont_list`)
- Context format is consistent regardless of which code path triggers the load
- Redis caching preserved with existing TTLs
- Unit tests verify field coverage and format consistency
- No regression in agent responses when using consolidated loader

Key files: `api/src/kene_api/routers/chat.py` lines 52-170; `app/adk/agents/utils/context_loader.py` lines 339-395

---

**1.3.6 — Fix MCP Session Cancel Scope Crash** (Feature: 1.3 - MCP Manager)

*As a user, I want Google Analytics tool calls to complete reliably so that I receive accurate analytics data instead of error messages about missing tenant IDs.*

Acceptance Criteria:
- `RuntimeError: Attempted to exit cancel scope in a different task` no longer occurs during GA MCP tool calls
- GA tool calls complete successfully and return data to the user
- Fix addresses root cause in `anyio`/`mcp` SDK cancel scope handling
- MCP SSE connection lifecycle is properly managed across async tasks
- Integration test verifies GA tool call round-trip succeeds
- Error messages to user are actionable if GA query fails for legitimate reasons

Key files: `google/adk/tools/mcp_tool/session_context.py` line 149; `mcp/client/sse.py` line 159; `app/adk/mcp_config/config/mcp_servers.yaml`

---

**1.16.2 — Fix ADK EventsCompactionConfig Version Mismatch** (Feature: 1.16 - Agent Configuration Management)

*As a developer, I want the deployed ADK version to match the Reasoning Engine runtime so that EventsCompactionConfig does not crash with a missing `token_threshold` attribute.*

Acceptance Criteria:
- `AttributeError: 'EventsCompactionConfig' object has no attribute 'token_threshold'` no longer occurs
- ADK SDK version is pinned in requirements to a version compatible with the Reasoning Engine runtime
- Deployment succeeds without compaction-related errors
- Session compaction works correctly after fix
- Version compatibility documented in deployment notes

Key files: `google/adk/apps/compaction.py` line 338; `google/adk/runners.py` line 435

---

**1.3.5 — Wire Health Monitor into API Lifecycle** (Feature: 1.3 - MCP Manager)

*Moved from Sprint 4.* Ensures MCP connection health is monitored at the API layer, enabling proactive detection of GA server failures.

---

**1.7.2 — Latency Metrics** (Feature: 1.7 - Observability)

*Moved from Sprint 4.* Adds structured latency tracking across the chat request pipeline, enabling us to measure and verify the < 5 second response time goal.

---

## 5. Key Files Reference

| File | Role |
|---|---|
| `app/adk/agents/ken_e_agent.py` | Agent definition (hardcoded instructions, tools, callbacks) |
| `app/adk/agents/agent_registry.py` | Central agent registry — single source of truth for all 13 agents |
| `app/adk/agents/tests/test_agent_registry.py` | CI validation tests for registry consistency |
| `app/adk/agents/strategy_agent/config_loader.py` | Firestore config loader (only `model` used by KEN-E; `create_agent_from_firestore_config()` exists but unused) |
| `api/src/kene_api/routers/chat.py` | Session creation (lines 648-808), context injection (lines 331-400, 1442, 1800) |
| `app/adk/agents/utils/dispatch_handlers.py` | Tool dispatch to sub-agents, reads session state for context re-injection |
| `app/adk/security/hooks.py` | Before/after tool callbacks, GA token refresh, re-auth flags in session state |
| `shared/context_utils.py` | Pure functions for context formatting and injection |
| `app/adk/agents/utils/context_loader.py` | Agent-side context loader (not used by KEN-E chat flow) |
| `app/adk/mcp_config/config/mcp_servers.yaml` | MCP server connection configuration (GA SSE endpoint) |

## 6. Success Criteria

This sprint is complete when:

1. **Strategy discussion works** — A user can ask KEN-E about their company strategy and receive a contextually relevant response informed by their organization's brand voice, industry, and business overview.
2. **Response time < 5 seconds** — End-to-end chat response latency is measurably under 5 seconds for typical queries, verified by the latency metrics instrumentation added in this sprint.
3. **Google Analytics data retrieval works** — A user can ask "How many website visitors did we have last week?" and receive actual GA4 data in response, without cancel scope crashes or misleading error messages.
4. **Agent config is manageable** — A centralized agent registry serves as the single source of truth for all agents; the API allowlist is derived automatically and CI tests enforce consistency.
5. **No token waste** — Organization context appears once in the LLM context per invocation, not repeated in every message in the conversation history.
