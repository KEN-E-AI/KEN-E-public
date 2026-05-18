# ADK 1.27.5 Chat Callback Spike — Confirmed Findings

**Date:** 2026-05-18
**Author:** Dev Team (CH-7)
**ADK version:** `google-adk==1.27.5` (resolved in `app/adk/uv.lock`; lower-bound specifier `>=1.27.4` in `pyproject.toml`)
**Spike script:** `scripts/spike_adk_callbacks.py` (runs without GCP credentials or LLM)

---

## 1. Purpose

This spike empirically answers the three questions that gate CH-PRD-01 (session metadata substrate) implementation:

| Question | Answer |
|----------|--------|
| a. Exact `before_agent_callback` / `after_agent_callback` signatures? | `(callback_context: CallbackContext) -> Optional[types.Content]` (sync or async) |
| b. Do these callbacks fire on nested sub-agents, or only on the registered agent? | **Per-agent only** — a callback fires only for the agent it is registered on |
| c. Is `callback_context._invocation_context.agent.parent_agent is None` the canonical root-detection idiom? | **Yes, confirmed** |

---

## 2. Empirical Output

All four experiments passed on the first run:

```
=== ADK 1.27.5 Callback Spike ===

=== Experiment 1: callbacks on root only ===
  CALLBACK FIRED: label='root.before'   agent='root'   parent_agent='None'  invocation_id='e-581922c5-069d-'
  CALLBACK FIRED: label='root.after'    agent='root'   parent_agent='None'  invocation_id='e-581922c5-069d-'
  Firing order: ['root.before', 'root.after']
  ✓ Only root.before / root.after fired (nested had no callbacks).

=== Experiment 2: callbacks on every agent (AH-PRD-02 pattern) ===
  CALLBACK FIRED: label='root.before'     agent='root'    parent_agent='None'  invocation_id='e-4fb2017f-88e9-'
  CALLBACK FIRED: label='nested.before'   agent='nested'  parent_agent='root'  invocation_id='e-4fb2017f-88e9-'
  CALLBACK FIRED: label='nested.after'    agent='nested'  parent_agent='root'  invocation_id='e-4fb2017f-88e9-'
  CALLBACK FIRED: label='root.after'      agent='root'    parent_agent='None'  invocation_id='e-4fb2017f-88e9-'
  ✓ root.parent_agent = None  (None ↔ is root)
  ✓ nested.parent_agent = 'root'  (non-None ↔ is nested)

=== Experiment 3: root-only guard via parent_agent check ===
  root_guard_log: ['processed:root2']
  ✓ Root-only guard works: nested.before skipped; root.before ran.

=== Experiment 4: CallbackContext attribute inventory ===
  agent_name: 'simple'
  invocation_id: 'e-a9813286-5774-4571-95f2-a804265db523'
  has_state: True
  has_invocation_context: True
  inv_ctx.agent.name: 'simple'
  inv_ctx.agent.parent_agent: None
  ✓ CallbackContext provides .agent_name (public) and ._invocation_context.agent.parent_agent (private)

=== All experiments passed ===
```

---

## 3. Confirmed Findings

### 3.1 Callback signature

```python
from typing import Optional
from google.adk.agents.callback_context import CallbackContext  # alias for Context in 1.27.5
from google.genai import types

def my_before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    ...
    return None  # None → agent runs normally; Content → short-circuits the agent
```

Both sync and async variants are accepted:

```python
# From base_agent.py source (google-adk 1.27.5):
_SingleAgentCallback: TypeAlias = Callable[
    [CallbackContext],
    Union[Awaitable[Optional[types.Content]], Optional[types.Content]],
]
BeforeAgentCallback = Union[_SingleAgentCallback, list[_SingleAgentCallback]]
AfterAgentCallback  = Union[_SingleAgentCallback, list[_SingleAgentCallback]]
```

### 3.2 Callbacks are per-agent registrations

A callback registered on agent A fires **only** when agent A runs. When a `SequentialAgent` (or any parent) calls `sub_agent.run_async(ctx)`, ADK fires the *sub-agent's own* registered callbacks — not the parent's.

**Implication for CH-PRD-01:** The `before_agent_callback` / `after_agent_callback` that writes and closes the `chat_sessions` row must be registered on the root `ken_e_agent`. It does not need to be registered on every sub-agent.

**Implication for AH-PRD-02 pattern:** AH-PRD-02 registers Weave-tracing callbacks on every factory-built specialist. When those specialists are run as sub-agents of `ken_e_agent`, their Weave callbacks fire independently per specialist — they are not inherited from the root. This is working as intended; each specialist gets its own trace span.

### 3.3 Firing order when callbacks are registered on every agent

```
root.before_agent_callback
  nested.before_agent_callback
  nested.after_agent_callback
root.after_agent_callback
```

The root `after_agent_callback` fires only after all sub-agents have finished.

### 3.4 Root detection: `parent_agent` (NOT `parent`)

The correct attribute on `BaseAgent` is `parent_agent`:

```python
# base_agent.py line 125 (google-adk 1.27.5):
parent_agent: Optional[BaseAgent] = Field(default=None, init=False, exclude=True)
```

The attribute is set by `_create_invocation_context` to the parent's `BaseAgent` instance (or `None` for the root).

**Root-detection idiom:**
```python
def before_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    inv_ctx = getattr(callback_context, "_invocation_context", None)
    agent = getattr(inv_ctx, "agent", None) if inv_ctx else None
    if getattr(agent, "parent_agent", None) is not None:
        return None  # skip nested invocations

    # root-only logic here
    ...
```

**PRD §5.2 erroneously used `invocation_context.agent.parent`** — this attribute does not exist. The correct path is `invocation_context.agent.parent_agent`. CH-PRD-01 has been amended to reflect this.

### 3.5 CallbackContext attribute inventory

| Attribute | Type | Access | Notes |
|-----------|------|--------|-------|
| `callback_context.agent_name` | `str` | Public property | Shortcut for `_invocation_context.agent.name` |
| `callback_context.invocation_id` | `str` | Public property | Full UUID format |
| `callback_context.state` | `State` | Public | Read/write session state |
| `callback_context._invocation_context` | `InvocationContext` | Private | Required for `parent_agent`, `session`, `user_id` |
| `callback_context._invocation_context.agent` | `BaseAgent` | Private | Current agent; has `.parent_agent` |
| `callback_context._invocation_context.session` | `Session` | Private | `.id` gives session ID |
| `callback_context._invocation_context.user_id` | `str` | Private | User identifier |

The private `_invocation_context` access follows the pattern already established in `app/adk/tracking/callbacks.py` (weave callbacks).

---

## 4. CH-PRD-01 Callback Design (Validated)

### 4.1 `before_agent_callback` — open the `chat_sessions` row

Fires once per invocation on the root agent. Responsible for:
- Extracting `session_id`, `user_id` from `_invocation_context.session.id` and `_invocation_context.user_id`
- Extracting `account_id` from `callback_context.state.get("account_id")`
- Writing or upserting the `chat_sessions` Firestore row (`is_agent_running=True`, `turn_started_at=now`)

```python
def chat_before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    inv_ctx = getattr(callback_context, "_invocation_context", None)
    agent = getattr(inv_ctx, "agent", None) if inv_ctx else None
    if getattr(agent, "parent_agent", None) is not None:
        return None  # root-only guard

    session_id = inv_ctx.session.id if inv_ctx and inv_ctx.session else "unknown"
    user_id = getattr(inv_ctx, "user_id", "unknown") if inv_ctx else "unknown"
    account_id = callback_context.state.get("account_id", "unknown")

    # upsert chat_sessions row (async-safe via fire-and-forget or sync Firestore client)
    # NOTE: production implementation must guard each _invocation_context chain step with
    # getattr(..., None) — follow the pattern in tracking/callbacks.py lines 141–149.
    ...
    return None
```

### 4.2 `after_agent_callback` — close the `chat_sessions` row

Fires once per invocation after the root agent (and all sub-agents) finish. Responsible for:
- Marking `is_agent_running=False`
- Recording `turn_completed_at=now`
- Triggering summary/title generation if needed

The root-detection guard is identical; `parent_agent is not None → return None`.

### 4.3 Registration

These callbacks are registered **on the root `ken_e_agent` only**:

```python
agent = Agent(
    name="ken_e_agent",
    ...
    before_agent_callback=chat_before_agent_callback,
    after_agent_callback=chat_after_agent_callback,
)
```

Sub-agents do not need them because the root's after-callback fires only after all sub-agents have completed (confirmed by Experiment 1 + Experiment 2).

---

## 5. PRD Amendment Required

**`CH-PRD-01-session-metadata-substrate.md` — 6 occurrences replaced (`agent.parent` → `agent.parent_agent`):**

| Location | Context |
|----------|---------|
| §2 "Root-only firing" narrative (×2) | Guard description + spike question (b) |
| §5.2 "Day-1 spike deliverable" intro | Root-guard description |
| §5.2 `on_agent_start` / `on_agent_stop` pseudocode (×2) | `if invocation_context.agent.parent_agent is not None: return` |
| §7 AC-19 acceptance criterion | Integration test guard assertion |
| §9 risk-table mitigation row | `agent.parent_agent is None` canonical detection |

All six occurrences confirmed replaced. Amendment is tracked in CH-7 and applied in the same PR as this spike document.

---

## 6. Fallback Plan

The `_invocation_context` field is a private ADK API. If a future ADK version renames or removes it:

**Primary fallback:** Use `callback_context.agent_name` (public) for the agent name. For session/user IDs, `callback_context.state` may hold copies if the API already writes them there.

**Secondary fallback:** `BaseAgent.parent_agent` is set by `_create_invocation_context`. If the private field is inaccessible, check whether `callback_context.invocation_id` correlates with the session — ADK may expose a public `session_id` property in a future version.

**Monitoring:** Run `scripts/spike_adk_callbacks.py` as part of any ADK version bump (`uv lock` change for `google-adk` in `app/adk/uv.lock`). The spike script is intentionally kept dependency-light (no GCP credentials required) so it can run in CI.

**Note:** The `tracking/callbacks.py` Weave callbacks already access `_invocation_context` in production (`session.id`, `user_id` extraction at lines 142–151). This spike confirms no new private-API surface is introduced — the CH-PRD-01 pattern reuses the existing access pattern.
