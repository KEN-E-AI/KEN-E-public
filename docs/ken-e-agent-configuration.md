# KEN-E Agent Configuration

This document explains how the KEN-E chat agent is configured, which settings are hardcoded vs. stored in Firestore, and how organization context is injected into every user message.

## 1. Agent Definition

The KEN-E agent is defined in:

**`app/adk/agents/ken_e_agent.py`**

The `create_ken_e_agent()` function (line 29) builds a Google ADK `Agent` instance with a model, system instructions, tools, and callbacks.

### 1.1 What Comes From Firestore

The function calls `load_config_from_firestore("ken_e_chatbot")` (line 40) which fetches the `ken_e_chatbot` document from the `agent_configs` Firestore collection.

**Only the model name is used from Firestore** (line 41):

```python
config, metadata = load_config_from_firestore(config_doc_id)
model = config.model  # e.g. "gemini-2.0-flash"
```

If the Firestore load fails, it falls back to `"gemini-2.0-flash"` (line 51).

The Firestore document also contains the following fields, **all of which are ignored**:

| Firestore Field | Used? | Notes |
|---|---|---|
| `model` | Yes | Only field consumed by `create_ken_e_agent()` |
| `instruction` | **No** | Overridden by hardcoded instruction (lines 77-149) |
| `description` | **No** | Not read |
| `name` | **No** | Agent name is hardcoded as `"ken_e"` (line 73) |
| `generate_content_config` | **No** | `temperature` and `max_output_tokens` are not passed to the Agent |
| `metadata` | Logged only | Version and variant are logged but not used functionally |

### 1.2 What Is Hardcoded

The following are defined directly in `app/adk/agents/ken_e_agent.py`:

- **Agent name**: `"ken_e"` (line 73)
- **System instruction**: The full prompt (lines 77-149), covering:
  - Agent identity and persona
  - Organization context parsing instructions
  - Capability 1: Company News & Business Intelligence
  - Capability 2: Google Analytics & Website Data
  - Routing instructions and examples
  - Strategy documents note
- **Tools**: `search_company_news` and `query_google_analytics` (line 150), defined as wrapper functions (lines 54-70) that delegate to `dispatch_to_company_news` and `dispatch_to_google_analytics`
- **Callbacks**: `adk_before_tool_callback` and `adk_after_tool_callback` (lines 75-76)

### 1.3 Unused Firestore Infrastructure

`app/adk/agents/strategy_agent/config_loader.py` contains a `create_agent_from_firestore_config()` function (line 144) that **does** use the full Firestore config including instructions via `Agent.from_config()` (line 218). This function is used by other agents (e.g., strategy agents) but is **not** used by the KEN-E chat agent.

## 2. Organization Context Injection

The KEN-E system instruction references `[ORGANIZATION CONTEXT]` that is "included with every message." This context is not part of the agent definition — it is injected by the API layer at request time.

### 2.1 Injection Entry Points

Context injection happens in the chat router for both endpoints:

**`api/src/kene_api/routers/chat.py`**

- **Non-streaming endpoint**: calls `inject_context_into_message()` at line 1442
- **Streaming endpoint**: calls `inject_context_into_message()` at line 1800

Both pass the user's `account_id` (or the first accessible account as fallback, lines 1437-1439 and 1795-1797).

### 2.2 The Injection Function

`inject_context_into_message()` (line 331) performs two types of context injection:

#### Organization Context (Always Injected)

1. Calls `load_organization_context_from_neo4j(account_id)` (line 361)
2. This function (line 52) runs a Cypher query against Neo4j that fetches:
   - **Account node**: `account_id`, `company_name`, `company_overview`, `industry`, `websites`, `customer_regions`
   - **BrandIdentity node** (via `FOLLOWS_THESE_BRAND_GUIDELINES`): voice/tone description, personality description, mission description
3. Formats the data as markdown with YAML frontmatter (lines 112-139)
4. Calls `inject_organization_context(formatted_input, org_context)` (line 363) which wraps it in delimiters

#### Campaign Context (Conditionally Injected)

1. Only injected if the user's message contains campaign-related keywords (line 388)
2. Keyword list defined in `shared/context_utils.py` lines 49-69 (e.g., "campaign", "roi", "ctr", "budget")
3. Currently returns **mock data** — real Neo4j campaign queries are not yet implemented (`api/src/kene_api/routers/chat.py` line 173)

### 2.3 Message Format After Injection

After injection, the user's message is transformed by `inject_organization_context()` in `shared/context_utils.py` (line 72) into:

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

**Voice & Tone:**
Professional, data-driven...

**Brand Personality:**
Innovative, approachable...

**Mission & Values:**
To empower businesses with...
[END CONTEXT]

<original user message>
```

If campaign context is also triggered, a `[CAMPAIGN CONTEXT]...[END CAMPAIGN CONTEXT]` block is appended as well (`shared/context_utils.py` line 91).

### 2.4 Triple Injection Problem

Organization context is currently injected in **three separate places**, leading to redundant token usage:

1. **Session creation** (`api/src/kene_api/routers/chat.py` line 805) — org context is fetched from Neo4j/Redis and stored in `initial_state["organization_context"]` in the ADK session state.

2. **Every message** (`api/src/kene_api/routers/chat.py` lines 1442/1800) — `inject_context_into_message()` fetches the context again (from Redis/Neo4j) and prepends it as `[ORGANIZATION CONTEXT]...[END CONTEXT]` to the user message. This repeats ~1,500 tokens in every message in the conversation history.

3. **Tool dispatch** (`app/adk/agents/utils/dispatch_handlers.py` lines 57-63, 141-144) — when KEN-E calls a sub-agent tool, the dispatch handler reads org context back from session state and injects it again into the query passed to the sub-agent.

The per-message fetch (step 2) is cached in Redis with a 15-minute TTL (`ORG_CONTEXT_TTL_SECONDS = 900`, line 41), so it does not hit Neo4j on every message. However, the context string is still prepended to every user message, accumulating repeated tokens in the conversation history.

### 2.5 Duplicate Context Loading Code

There are **two separate implementations** of the Neo4j context loading logic:

1. **API-side** (`api/src/kene_api/routers/chat.py` lines 52-170): An async version using the API's Neo4j service. Fetches `voice_tone_description`, `personality_description`, `mission_description` as free-text description fields.

2. **Agent-side** (`app/adk/agents/utils/context_loader.py` lines 339-395): A sync version using a direct Neo4j connection. Fetches structured fields like `tone_attributes`, `do_list`, `dont_list`, `traits`, `mission_statement`, `core_values`.

These two implementations query **different fields** from the same Neo4j nodes and format the results differently. Only the API-side version (1) is used at runtime for the KEN-E chat agent.

## 3. Session State

The KEN-E chat agent uses ADK session state to persist data across messages within a conversation. Session state is a key-value store managed by `VertexAiSessionService`. The LLM does **not** automatically see session state — values must be explicitly surfaced via template placeholders (`{key}`) in instructions, an `InstructionProvider` callable, or read programmatically in tools/callbacks via `tool_context.state`.

### 3.1 State Populated at Session Creation

When a new chat session is created (`api/src/kene_api/routers/chat.py` lines 648-808), the API builds an `initial_state` dict and passes it to the ADK session:

| Key | Type | Source | Line |
|---|---|---|---|
| `account_id` | string | Validated from user context or request parameter | 665 |
| `accessible_accounts` | list[string] | All account IDs the authenticated user can access | 666 |
| `organization_context` | string | Org context markdown loaded from Neo4j/Redis (company info + brand voice, ~1,500 tokens) | 805 |
| `ga_credentials` | dict | OAuth credentials from Firestore: `{access_token, refresh_token, tenant_id, selected_property_ids, selected_properties, expires_at}` | 808 |

The `organization_context` and `ga_credentials` are loaded in parallel via `asyncio.gather()` (line 798), with Redis caching to avoid repeated Neo4j/Firestore queries across sessions.

### 3.2 State Written During Session

Callbacks and tools write additional keys during the session:

| Key | Type | Written By | File:Line | Purpose |
|---|---|---|---|---|
| `ga_credentials` | dict | `_refresh_ga_token_if_needed()` | `app/adk/security/hooks.py:78` | Updates `access_token` and `expires_at` when the GA token is expired |
| `_tool_start_time` | float | `adk_before_tool_callback()` | `app/adk/security/hooks.py:199` | Tracks tool execution duration for usage metrics |
| `_requires_reauth` | bool | `adk_before_tool_callback()` | `app/adk/security/hooks.py:212` | Signals to the API that the user needs to re-authenticate (one-shot flag, cleared at `chat.py:2206`) |
| `_reauth_service` | string | `adk_before_tool_callback()` | `app/adk/security/hooks.py:213` | Identifies which service needs re-auth, e.g. `"google-analytics"` (one-shot flag, cleared at `chat.py:2207`) |

### 3.3 How Session State Is Currently Used

Session state is **not** referenced in the agent's system instruction. Instead, it is read programmatically by tool functions and callbacks:

- **Tool dispatch handlers** (`app/adk/agents/utils/dispatch_handlers.py`) read `tool_context.state` to get `account_id` (line 48/119), `organization_context` (line 58/142), `ga_credentials` (line 120), and `campaign_context` (line 147).
- **Security hooks** (`app/adk/security/hooks.py`) read and write `ga_credentials` for token refresh and set re-auth flags.

This means the `organization_context` stored in session state at creation is only consumed by dispatch handlers to re-inject into sub-agent queries — it is never used to inform the KEN-E agent's own instruction or LLM context directly.

## 4. Next Steps (Improvements)

Improvements to address in future sessions, ordered by priority.

### 4.1 Use Firestore Config Fully

`create_ken_e_agent()` loads the Firestore `ken_e_chatbot` document but only reads `config.model`. The `instruction`, `name`, `description`, and `generate_content_config` fields are all ignored and hardcoded instead. The agent should either:

- Use `create_agent_from_firestore_config()` (which already exists in `config_loader.py` line 144) to build the agent entirely from Firestore config, or
- At minimum, read `config.instruction` and use it as the system prompt so that instructions can be updated in Firestore without redeploying.

**Files:** `app/adk/agents/ken_e_agent.py` lines 38-51, 72-151

### 4.2 Eliminate Per-Message Context Injection

Organization context (~1,500 tokens) is prepended to every user message, accumulating repeated tokens across the conversation history (see Section 2.4). This should be replaced with a single injection at session start using one of these approaches:

- **Dynamic instruction callable**: The ADK `Agent` `instruction` parameter accepts a callable that receives the `InvocationContext`, which has access to session state. The org context (already stored in session state at creation, line 805) could be read once per invocation and included in the system instruction — without repeating it in every message.
- **Session-state reference**: Keep the current session-state storage but update the system instruction to tell the agent to read organization context from session state, letting the ADK framework handle it per-invocation.

Either approach eliminates the per-message `inject_context_into_message()` calls (lines 1442/1800) and the redundant re-injection in `dispatch_handlers.py` (lines 57-63, 141-144). The Redis caching layer for org context would still be useful at session creation time but would no longer need to be consulted on every message.

**Files:** `api/src/kene_api/routers/chat.py` lines 331-400, 805, 1442, 1800; `app/adk/agents/utils/dispatch_handlers.py` lines 57-63, 141-144; `app/adk/agents/ken_e_agent.py` line 77

### 4.3 Consolidate Duplicate Context Loading

There are two separate Neo4j context loaders that query different fields from the same nodes (see Section 2.5). This is also relevant to Section 3.3 — the `organization_context` stored in session state was loaded by the API-side implementation and is never refreshed if the agent-side loader returns different data.. These should be consolidated into a single implementation to avoid drift and ensure consistent context formatting.

**Files:** `api/src/kene_api/routers/chat.py` lines 52-170, `app/adk/agents/utils/context_loader.py` lines 339-395

### 4.4 Fix MCP Session Cancel Scope Crash

The Google Analytics MCP client crashes with `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`. This is a known `anyio`/`mcp` SDK issue where the SSE client's cancel scope is entered in one asyncio task but exited in another. The ADK's `session_context.py` triggers this during teardown. This causes GA tool calls to fail silently, resulting in unhelpful error messages to the user.

Investigate whether upgrading the `mcp` SDK, `anyio`, or the ADK resolves this. The error originates in:
- `google/adk/tools/mcp_tool/session_context.py` line 149 (`_run` method)
- `mcp/client/sse.py` line 159 (`sse_client` context manager)

### 4.5 Fix ADK EventsCompactionConfig Version Mismatch

The deployed Reasoning Engine crashes with `AttributeError: 'EventsCompactionConfig' object has no attribute 'token_threshold'`. This indicates the installed ADK version expects a `token_threshold` field that doesn't exist on the deployed `EventsCompactionConfig` class. The crash occurs in:
- `google/adk/apps/compaction.py` line 338
- `google/adk/runners.py` line 435

This needs a redeployment with matching ADK SDK versions, or pinning the ADK version to one that is compatible with the Reasoning Engine runtime.

## 5. Summary of Key Files

| File | Role |
|---|---|
| `app/adk/agents/ken_e_agent.py` | Agent definition (hardcoded instructions, tools, callbacks) |
| `app/adk/agents/strategy_agent/config_loader.py` | Firestore config loader (only `model` used by KEN-E) |
| `api/src/kene_api/routers/chat.py` | Session creation (lines 648-808), context injection (lines 331-400, 1442, 1800) |
| `app/adk/agents/utils/dispatch_handlers.py` | Tool dispatch to sub-agents, reads session state for context re-injection |
| `app/adk/security/hooks.py` | Before/after tool callbacks, GA token refresh, re-auth flags in session state |
| `shared/context_utils.py` | Pure functions for context formatting and injection |
| `app/adk/agents/utils/context_loader.py` | Agent-side context loader (not used by KEN-E chat flow) |
