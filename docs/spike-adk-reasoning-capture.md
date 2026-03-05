# Spike 1.12.1: ADK Callbacks for LLM Reasoning Capture

**Status**: Investigation complete
**ADK Version tested**: 1.14.1 (installed), API targets >=1.23.0
**Date**: 2026-02-24

## Summary

ADK's `after_model_callback` provides direct access to the LLM's response content before tool dispatch, making it the primary mechanism for capturing reasoning text.

## Key Findings

### 1. `after_model_callback` Signature

```python
after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse
) -> Optional[LlmResponse]
```

- Fires **after the LLM responds but before the response is processed** (tool dispatch, etc.)
- `LlmResponse.content` is a `google.genai.types.Content` object containing the model's text output
- When the model decides to call a tool, the response may include a text part with reasoning + a function_call part
- Returning `None` passes the response through unchanged; returning an `LlmResponse` replaces it

### 2. `LlmResponse` Structure

```python
LlmResponse(
    content: Content,               # Model's text + function calls
    modelVersion: str,              # e.g., "gemini-2.0-flash"
    groundingMetadata: GroundingMetadata,
    finishReason: FinishReason,
    usageMetadata: GenerateContentResponseUsageMetadata,
    customMetadata: dict[str, Any], # Can be used for custom data
    # ... other fields
)
```

`Content.parts` is a list that can contain:
- `Part(text="reasoning text...")` — the model's reasoning
- `Part(function_call=FunctionCall(...))` — tool invocation

### 3. `CallbackContext` Access

```python
CallbackContext:
    .state              # Session state (dict-like) — read/write
    .agent_name         # Current agent name
    .user_id            # Current user ID
    .session            # Full session object
    .invocation_id      # Current invocation ID
    .user_content       # The user's input Content
```

### 4. Recommended Approach for Reasoning Capture

```python
async def capture_reasoning(
    ctx: CallbackContext, llm_response: LlmResponse
) -> None:
    """after_model_callback that stashes LLM reasoning text in session state."""
    if not llm_response.content or not llm_response.content.parts:
        return None

    reasoning_parts = []
    for part in llm_response.content.parts:
        if hasattr(part, "text") and part.text:
            reasoning_parts.append(part.text)

    if reasoning_parts:
        reasoning_text = "\n".join(reasoning_parts)
        # Store in session state for downstream consumption
        ctx.state["_last_reasoning"] = reasoning_text

    return None  # Pass response through unchanged
```

### 5. Stashing Reasoning for `before_tool_callback`

Since `after_model_callback` fires before tool dispatch, we can store reasoning in `ctx.state`:

1. `after_model_callback` → extracts text parts → writes `ctx.state["_last_reasoning"]`
2. `before_tool_callback` → reads `tool_context.state["_last_reasoning"]` → logs/traces it

Both callbacks share the same session state, so state propagation is automatic.

### 6. `before_tool_callback` Access

The existing `before_tool_callback` in `app/adk/security/hooks.py` already accesses `tool_context.state`. The reasoning text stored in step 5 would be available at `tool_context.state.get("_last_reasoning")`.

## Risks & Considerations

1. **Gemini function call responses**: When Gemini decides to call a tool, the response typically includes BOTH a text part (reasoning) and a function_call part. The text part contains the model's reasoning. However, this behavior may vary by model version.

2. **Multi-turn reasoning**: In multi-turn conversations, the reasoning from the previous turn is overwritten. If Sprint 5 needs historical reasoning, we'd need to accumulate in a list.

3. **Performance**: The callback adds minimal overhead — just text extraction and state write. No LLM calls.

4. **No modification**: Returning `None` from `after_model_callback` ensures the response is passed through unchanged. Never modify the response for reasoning capture.

## Recommendation for Sprint 5

- **1.12.2**: Implement `capture_reasoning` callback and register on KEN-E and strategy agents
- **1.12.3**: Add Weave span attributes for reasoning text (truncated to prevent large trace payloads)
- **1.12.4**: Build reasoning viewer in trace UI

## Existing Code References

- `app/adk/security/hooks.py:177` — existing `adk_before_tool_callback` (accesses `tool_context.state`)
- `app/adk/tracking/callbacks.py:56` — existing `adk_after_tool_callback` (reads state timing data)
- `app/adk/agents/ken_e_agent.py:75-76` — callback registration on Agent
