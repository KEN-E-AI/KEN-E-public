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

### 2.4 Duplicate Context Loading Code

There are **two separate implementations** of the Neo4j context loading logic:

1. **API-side** (`api/src/kene_api/routers/chat.py` lines 52-170): An async version using the API's Neo4j service. Fetches `voice_tone_description`, `personality_description`, `mission_description` as free-text description fields.

2. **Agent-side** (`app/adk/agents/utils/context_loader.py` lines 339-395): A sync version using a direct Neo4j connection. Fetches structured fields like `tone_attributes`, `do_list`, `dont_list`, `traits`, `mission_statement`, `core_values`.

These two implementations query **different fields** from the same Neo4j nodes and format the results differently. Only the API-side version (1) is used at runtime for the KEN-E chat agent.

## 3. Summary of Key Files

| File | Role |
|---|---|
| `app/adk/agents/ken_e_agent.py` | Agent definition (hardcoded instructions, tools, callbacks) |
| `app/adk/agents/strategy_agent/config_loader.py` | Firestore config loader (only `model` used by KEN-E) |
| `api/src/kene_api/routers/chat.py` | Context injection at request time (lines 331-400, 1442, 1800) |
| `shared/context_utils.py` | Pure functions for context formatting and injection |
| `app/adk/agents/utils/context_loader.py` | Agent-side context loader (not used by KEN-E chat flow) |
