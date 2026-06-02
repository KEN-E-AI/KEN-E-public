# W&B Weave Span Structure Specification for KEN-E

> **Status:** Draft
> **Version:** 1.2
> **Last Updated:** 2026-02-06
> **Related:** MER-E Design Doc Sections 6.2, 6.4, 10.2, 11.6, 13

## 1. Purpose

This document specifies the required span hierarchy, naming conventions, metadata, and context fields that KEN-E agents must emit to W&B Weave. It serves as the contract between KEN-E (trace producer) and MER-E (trace consumer).

**Tracing Approach:** KEN-E uses the **Weave Python SDK** (`weave.op()` decorators + `weave.attributes()`) as the primary tracing mechanism. OpenTelemetry (OTEL) provides supplementary auto-captured GenAI spans (model, token usage, temperature) once the Pydantic serialization bug is resolved (see Section 4.5).

MER-E consumes these traces for:
- **Output evaluation** (current) — extracting structured outputs for human and LLM scoring
- **Tool call evaluation** (Feature 3.5) — assessing tool selection, query quality, and result utilization
- **Structural issue detection** (Feature 4.6) — identifying anti-patterns in agent behavior
- **Multi-step workflow evaluation** (Section 13) — evaluating step sequences and trajectories

## 2. Span Hierarchy

Every KEN-E execution MUST produce a span tree with the following structure. The depth varies by agent architecture (strategy agents are typically 3 levels; orchestrator agents go to 4).

```
Root: Session Invocation
├── L1: Orchestrator Agent Run
│   ├── L2: Sub-Agent Run (e.g., business_strategy)
│   │   ├── L3: LLM Call (Gemini)
│   │   ├── L3: Tool Call (e.g., google_search)
│   │   │   └── L4: Nested tool/LLM calls (if any)
│   │   ├── L3: LLM Call (Gemini)
│   │   └── L3: Tool Call (e.g., firestore_read)
│   ├── L2: Sub-Agent Run (e.g., marketing_strategy)
│   │   └── ...
│   └── L2: Sub-Agent Run (e.g., competitive_strategy)
│       └── ...
```

### Level Definitions

| Level | What it represents | ADK equivalent |
|-------|-------------------|----------------|
| Root | Top-level session invocation | The outermost `Runner.run()` call |
| L1 | Orchestrator agent processing | `adk.agent.<OrchestratorClass>` |
| L2 | Sub-agent delegation | `adk.agent.<SubAgentClass>` |
| L3 | Individual LLM or tool call | `adk.llm.*` or `adk.tool.*` |
| L4 | Nested calls within a tool | Child spans of an L3 tool call |

### Strategy Agents vs. Orchestrator Agents

KEN-E has two agent architectures with different trace shapes:

**Strategy Agents** (e.g., `business_strategy_format`):
```
Root
└── L1: Strategy Agent Run
    ├── L2: LLM Call (generate_content / chat.completions)
    └── L2: Tool Call (if any)
```

**Orchestrator Agents** (e.g., multi-agent pipeline):
```
Root
└── L1: Orchestrator Run
    ├── L2: Sub-Agent Run (business_strategy)
    │   ├── L3: LLM Call
    │   └── L3: Tool Call
    ├── L2: Sub-Agent Run (marketing_strategy)
    │   └── ...
    └── L2: Sub-Agent Run (competitive_strategy)
        └── ...
```

MER-E extractors handle both: `OutputExtractor.get_subagent_output()` checks the root call output first (`output[subagent][field]`), then falls back to child call output (`output[field]`).

## 3. Span Naming Conventions


### ADK Native Names vs. MER-E Expectations

ADK uses dot-notation span names. MER-E's current `ToolCallExtractor` uses colon-prefix matching. The table below documents the mapping:

| Span Type | ADK Native Name | MER-E Current Pattern | Recommended Resolution |
|-----------|----------------|----------------------|----------------------|
| Agent | `adk.agent.<ClassName>` | `agent:<agent_id>` | Match via `attributes.agent_id` |
| Tool | `adk.tool.<tool_name>` | `tool:<tool_name>` | Match via `attributes.type == "tool"` or `adk.tool.` prefix |
| LLM | `generate_content` / `chat.completions` | `llm:<model_name>` | Exclude via known LLM op_name patterns |
| Formatter | `<subagent>_format` | Not matched | Identified by `_format` suffix in op_name |
| Per-turn dispatch (AH-PRD-09) | `delegate_to_specialist` *(deprecated for supervisor-orchestrated turns — see §14 and AH-PRD-05)* | Not previously present | Match `op_name == "delegate_to_specialist"` exactly; replaces `dispatch_to_*` pattern — see §14 |
| `task_delegation` | supervisor-orchestration per-task delegation span; emitted when coordinator delegates to a `mode='task'` specialist (AH-PRD-05) | Not previously present | Match `span.name == "task_delegation"` + `attributes.task_id` presence — see AH-PRD-05-trace-contract-diff.md |
| `fanout` | supervisor-orchestration parallel fan-out span; emitted for each `ctx.run_node` + `asyncio.gather` parallel execution group (AH-PRD-05) | Not previously present | Match `span.name == "fanout"` + `attributes.task_ids` presence |

### Identification Strategy

MER-E extractors SHOULD use **attributes-based identification** rather than relying solely on `op_name` prefixes. This makes extraction resilient to naming convention changes across ADK versions.

**For tool calls**, match using this priority order:
1. `op_name` starts with `tool:` (current Weave convention)
2. `op_name` starts with `adk.tool.` (ADK convention)
3. `attributes.type == "tool"`
4. Heuristic: structured inputs without `messages`/`prompt` keys

**For agent spans**, match using:
1. `op_name` starts with `agent:` or `adk.agent.`
2. `attributes.agent_id` is present
3. `config.labels.adk_agent_name` is set

**For LLM calls**, exclude using known patterns:
- `generate_content` (Gemini via Vertex AI)
- `chat.completions` / `openai.chat.completions.parse` (OpenAI-compatible)
- `adk.llm.*`

### MER-E Code Updates Required

The following code needs updating to support ADK naming (tracked separately from this spec):

| File | Change Needed |
|------|--------------|
| `mer_e/adapters/ken_e/tool_calls/tool_call_extractor.py:121-167` | `_is_tool_call()`: Add `adk.tool.` prefix check |
| `mer_e/adapters/ken_e/tool_calls/tool_call_extractor.py:137-142` | `agent_patterns`: Add `adk.agent.`, `adk.llm.` exclusions |
| `mer_e/adapters/ken_e/tool_calls/tool_call_extractor.py:191-195` | `_extract_single_tool_call()`: Strip `adk.tool.` prefix |

## 4. Required Metadata Per Span Level


### 4.1 Root Span (Session Invocation)

These attributes MUST be set on the root span. They enable trace filtering, A/B test segmentation, and workflow evaluation.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | Yes | KEN-E account that triggered the execution |
| `session_id` | string | Yes | Chat/workflow session identifier |
| `user_id` | string | No | User within the account |
| `environment` | enum | Yes | `"development"` \| `"staging"` \| `"canary"` \| `"production"` |
| `rollout_percentage` | int | Yes (default: 100) | 0-100, percentage of traffic on this variant. Defaults to 100 until canary/A/B infrastructure is introduced. |
| `workflow_id` | string | Conditional | Required for multi-step workflows (Section 13) |
| `workflow_type` | string | Conditional | `"keyword_analysis"` \| `"campaign_creation"` \| `"performance_report"` \| etc. |

**Validation:** MER-E's `validate_trace_compliance()` enforces `account_id`, `session_id`, `environment`, and `rollout_percentage` on every trace. Missing required fields cause a compliance failure.

### 4.2 L1 — Orchestrator Agent Span

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Unique agent identifier (e.g., `"orchestrator"`) |
| `agent_version` | string | Yes | Semantic version (e.g., `"v1.2.3"`) |
| `experiment_id` | string | Yes | `"baseline"` or specific experiment ID |
| `variant_name` | string | Yes | Variant being tested |
| `routing_decisions` | object | No | Which sub-agents were selected and why |

**Version format:** Must match `^v?\d+\.\d+\.\d+(-[\w.]+)?$` per `TraceMetadata.agent_version`. Sourced from Firestore agent config `metadata.version`, which must be standardized to semver format.

### 4.3 L2 — Sub-Agent Span

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | string | Yes | Sub-agent identifier (e.g., `"business_strategy"`) |
| `agent_version` | string | Yes | Semantic version |
| `agent_goal` | string | No* | What the sub-agent was asked to accomplish |
| `model_used` | string | No | LLM model name (e.g., `"gemini-2.0-flash"`) |
| `temperature` | float | No | Temperature setting (0.0-2.0) |
| `max_output_tokens` | int | No | Token limit |
| `step_type` | string | Conditional | Required for workflow eval: `"research"` \| `"generation"` \| `"analysis"` \| `"execution"` |

**Output:** The sub-agent's structured output MUST be available via `call.output`. Output extractors rely on this to extract evaluatable items (34 output types across 4 subagent categories).

*`agent_goal` becomes required when tool call evaluation (Feature 3.5) is active, as it propagates to tool call context.

### 4.4 L3 — Tool Call Span

Tool call spans carry the richest metadata because they serve both current extraction and future tool chain evaluation.

#### Core Fields (Required Now)

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `tool_name` | string | Yes | Name of the tool invoked |
| `input` | object | Yes | Full tool input (not summarized) |
| `output` | object | Yes | Full tool output (not summarized) |
| `timing.duration_ms` | int | Yes | Execution time in milliseconds |
| `status` | string | Yes | `"success"` \| `"error"` |
| `error` | string | Conditional | Error message if `status == "error"` |

#### Context Fields (Required for Feature 3.5+)

These fields enable tool call evaluation per the design doc (Section 6.4.1):

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `context.agent_id` | string | Yes | Which agent invoked this tool |
| `context.agent_goal` | string | Yes | The agent's current objective |
| `context.reasoning` | string | Yes | Why the agent chose this tool |
| `context.previous_tool_calls` | string[] | Yes | List of prior tool_call span IDs in this agent's chain |

See [Section 5](#5-context-block-capture-strategy) for implementation guidance on capturing these fields.

#### Tool Call Evaluation Factors

These are the evaluation criteria MER-E applies to tool calls (Section 6.4.2):

| Factor | Question | Type |
|--------|----------|------|
| Relevance | Was this the right tool for the current subtask? | Boolean |
| Query Quality | Was the tool input well-formed and specific? | 1-5 Scale |
| Timing | Was this tool called at the right point in the workflow? | Boolean |
| Necessity | Was this tool call necessary, or redundant? | Boolean |
| Result Utilization | Did the agent effectively use the tool's output? | 1-5 Scale |

All five factors require full (unsummarized) `input` and `output` to evaluate.

#### 4.4.1 Code Execution Parts (Gemini Built-in)

When the Analytics Specialist uses Gemini's built-in code execution, the `generate_content` response contains additional part types interleaved with text parts. These are NOT separate L3 spans — they are content parts within the existing `generate_content` span.

| Part Type | Key Fields | Description |
|-----------|-----------|-------------|
| `executable_code` | `code` (string) | Python source code generated by the model |
| `code_execution_result` | `output` (string), `outcome` (enum: `OUTCOME_OK` \| `OUTCOME_FAILED`) | Stdout/stderr from execution and success/failure status |

#### Trace Structure

```
L3: generate_content span
    response.candidates[0].content.parts = [
        Part(text="Let me calculate the percentage change..."),
        Part(executable_code=ExecutableCode(code="pct_change = ((new - old) / old) * 100\nprint(f'{pct_change:.1f}%')")),
        Part(code_execution_result=CodeExecutionResult(output="23.5%", outcome="OUTCOME_OK")),
        Part(text="Website traffic increased by 23.5% month-over-month.")
    ]
```

#### MER-E Extraction Guidance

- **Detection:** Scan `response.candidates[].content.parts[]` for parts with `executable_code` or `code_execution_result` fields
- **Pairing:** Each `executable_code` part is immediately followed by its `code_execution_result`. Pair them sequentially.
- **Evaluation:** Cross-check the code logic against the stated analysis, verify `OUTCOME_OK`, and validate that results are consistent with source data from preceding tool calls

#### Key Difference from Tool Calls

Code execution parts do NOT produce separate L3 spans and do NOT have separate timing. They are part of the LLM's response generation, not a tool invocation with its own span. This means:
- No `tool_name`, `duration_ms`, or `status` fields — those are tool call span attributes
- No `before_tool_callback` / `after_tool_callback` firing
- Timing is subsumed within the L3 LLM call span's duration

See harness design doc Section 9.2.1 for the KEN-E perspective on code execution traces.

### 4.5 L3 — LLM Call Span

LLM call metadata is auto-captured by ADK's OpenTelemetry GenAI conventions when OTEL is enabled.

> **Note:** OTEL is currently disabled in staging/production (`OTEL_SDK_DISABLED=true`) due to a Pydantic serialization bug where `opentelemetry-instrumentation-google-genai` calls `BaseModel.model_dump()` on Pydantic classes instead of instances. The fields below will be available once the OTEL bug is resolved (Feature 7: OTEL Re-enablement). See ADK >= 1.23.0 for a potential fix.

| Attribute | Type | Source | Description |
|-----------|------|--------|-------------|
| `gen_ai.system` | string | Auto | `"vertex_ai"` or `"openai"` |
| `gen_ai.request.model` | string | Auto | Model name |
| `gen_ai.usage.input_tokens` | int | Auto | Prompt tokens |
| `gen_ai.usage.output_tokens` | int | Auto | Completion tokens |
| `gen_ai.request.temperature` | float | Auto | Temperature setting |

**Content capture:** Controlled by `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. Set to `true` in development and staging for debugging and MER-E evaluation. Set to `false` in production to protect user data privacy — LLM prompts and responses are NOT included in production traces. Span metadata (model, token counts, temperature, duration) is still captured.

### 4.6 REST API Spans (Skills Component)

REST API spans are **not children of any agent span** — they are produced by the FastAPI HTTP tier and are **siblings to L1 orchestrator spans**. MER-E can correlate them with the agent-side `skill.list` / `skill.load` / `skill.load_resource` spans (owned by SK-PRD-02) by matching `account_id`.

Reference: `docs/design/components/skills/projects/SK-PRD-01-skills-backend.md` §7 AC-12.

#### Op Names

| Op Name | HTTP Method | Path |
|---------|-------------|------|
| `api.skills.create` | POST | `/api/v1/accounts/{account_id}/skills` |
| `api.skills.list` | GET | `/api/v1/accounts/{account_id}/skills` |
| `api.skills.get` | GET | `/api/v1/accounts/{account_id}/skills/{skill_id}` |
| `api.skills.get_content` | GET | `/api/v1/accounts/{account_id}/skills/{skill_id}/content` |
| `api.skills.get_resource` | GET | `/api/v1/accounts/{account_id}/skills/{skill_id}/resources/{rel_path}` |
| `api.skills.update` | PUT | `/api/v1/accounts/{account_id}/skills/{skill_id}` |
| `api.skills.delete` | DELETE | `/api/v1/accounts/{account_id}/skills/{skill_id}` |
| `api.skills.validate` | POST | `/api/v1/accounts/{account_id}/skills/validate` |

#### Common Attributes (all 8 spans)

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | string | Yes | The account owning the skills collection |

#### Per-Span Attributes

| Op Name | Extra Attributes | Notes |
|---------|-----------------|-------|
| `api.skills.create` | `skill_id: str`, `bundle_bytes: int`, `file_count: int` | `skill_id` is pre-allocated in the route handler before the span is opened; `weave.attributes()` is called there so all attrs land on the correct span |
| `api.skills.list` | — | No extra attributes beyond `account_id` |
| `api.skills.get` | `skill_id: str` | |
| `api.skills.get_content` | `skill_id: str`, `version: int` (when request pins one) | `version` is omitted (not null) when the request did not pin a version |
| `api.skills.get_resource` | `skill_id: str`, `version: int` (when request pins one) | Same omit-not-null rule as `get_content` |
| `api.skills.update` | `skill_id: str`, `bundle_bytes: int`, `file_count: int` | `current_version` is omitted — reading it pre-span would require an extra Firestore round-trip; the post-bump version is not available until inside the Firestore transaction |
| `api.skills.delete` | `skill_id: str`, `archived: bool` | `archived` is always `True` — it reflects the operation's intent, not the GCS-move outcome |
| `api.skills.validate` | `bundle_bytes: int`, `file_count: int` | No `skill_id` — validation creates no state |

#### Span Coverage

Spans for `api.skills.create`, `api.skills.update`, and `api.skills.validate` are opened **after** the multipart request body has been parsed. Requests that fail body parsing — for example, an oversized upload or malformed multipart — are rejected by FastAPI/Starlette with HTTP 413 or 422 before the handler emits its span and will therefore **not** appear in MER-E's `api.skills.*` data. MER-E should correlate on successful-request volume (requests that reached the handler), not on total request-attempt volume, when scoring skill API usage.

## 5. Context Block Capture Strategy


The design doc (Section 6.4.1) requires a `context` block on tool calls that ADK does not capture by default. This section specifies how KEN-E should implement each field.

### 5.1 Capturing `context.agent_goal`

**Source:** The orchestrator's delegation prompt or the sub-agent's task description.

**Implementation approach:**
1. When the orchestrator delegates to a sub-agent, extract the goal from the delegation message
2. Store it as a span attribute on the sub-agent span: `attributes.agent_goal`
3. Propagate to all tool call spans within that sub-agent's execution

**Example:**
```python
# In KEN-E agent setup
with weave.attributes({"agent_goal": "Research competitive landscape for Acme Corp"}):
    result = sub_agent.run(task)
```

### 5.2 Capturing `context.reasoning`

**Source:** The LLM's function-call decision in its response.

**Implementation approach:**
1. When the LLM returns a function call response, inspect the response for reasoning text
2. The text preceding or accompanying the function call declaration is the reasoning
3. Attach to the subsequent tool call span as `attributes.context_reasoning`

**Note:** This requires intercepting the LLM response before tool dispatch. In ADK, this may be possible via a custom callback or middleware that inspects `LlmResponse.candidates[].content.parts[]` for both text and function_call parts.

> **Feasibility caveat:** ADK does not currently expose a documented pre-tool-dispatch hook. A spike investigation is required to determine the viable approach. Alternative: extract reasoning retroactively from conversation history available in `ToolContext`.

### 5.3 Capturing `context.previous_tool_calls`

**Source:** Runtime tracking of tool call span IDs per agent execution.

**Implementation approach:**
1. Maintain a per-agent list of completed tool call span IDs during execution
2. Before each tool call, snapshot the current list and attach as `attributes.context_previous_tool_calls`
3. After the tool call completes, append its span ID to the list

**Example:**
```python
class ToolCallTracker:
    """Tracks tool call chain within a single agent execution."""

    def __init__(self):
        self._call_ids: list[str] = []

    def before_tool_call(self, span) -> list[str]:
        """Return previous call IDs and register on span."""
        previous = list(self._call_ids)
        span.set_attribute("context.previous_tool_calls", previous)
        return previous

    def after_tool_call(self, span_id: str):
        """Record completed tool call."""
        self._call_ids.append(span_id)
```

## 6. Full vs. Summarized Data

### Current State

MER-E's `InstrumentedTool` wrapper currently stores `input_summary` and `output_summary`, truncated to 200 characters via `_summarize_value()`. This is insufficient for Feature 3.5 (Tool Usage Analyzer), which needs full inputs to assess query quality and full outputs to assess result utilization.

### Requirements

| Data Type | Storage | Rationale |
|-----------|---------|-----------|
| Tool call `input` | **Full** (not summarized) | Required for Query Quality evaluation |
| Tool call `output` | **Full** (not summarized) | Required for Result Utilization evaluation |
| LLM message content | Configurable | Controlled by `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` |

### Size Mitigation

- Tool I/O is typically small (< 10KB per call) and safe to store in full
- LLM content is larger (prompt + completion can be 50KB+); use the GenAI content flag to control
- If a tool returns exceptionally large output (> 100KB), truncate with a marker: `{"_truncated": true, "size_bytes": 524288, "preview": "..."}`

### Retention Policy

Per the design doc (Section 6.6):

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| Raw traces (including full tool I/O) | 90 days | W&B Weave |
| Extracted outputs | 1 year | BigQuery |
| Evaluation results | Indefinite | Firestore + BigQuery |
| Aggregated metrics | Indefinite | BigQuery |

## 7. Compatibility with Existing MER-E Extractors


### Works Today (No Changes Needed)

**Output extraction** via `OutputExtractor.get_subagent_output()`:
- Reads `call.output` on root or sub-agent calls
- ADK populates `call.output` with the agent's structured response
- All 34 output extractors across 4 subagent categories work with this pattern

**Call tree traversal** via `call.children()`:
- Weave's OTLP ingestion creates proper parent-child relationships from OpenTelemetry context
- `ToolCallExtractor._get_child_calls()` handles multiple access patterns: `call.children`, `call._children`, `call.child_calls()`

**Agent identification** in `QueuePopulatorService`:
- Strategy agents identified by op_name suffix (e.g., `business_strategy_format`)
- Orchestrator agents identified by `config.labels.adk_agent_name`
- LLM calls identified by `generate_content` or `chat.completions` op_names

### Needs Updating in MER-E

These changes are required to support ADK-native span naming. They are tracked separately from this spec.

#### `ToolCallExtractor._is_tool_call()` (tool_call_extractor.py:121-167)

**Current behavior:** Checks for `tool:` prefix; excludes `agent:`, `llm:`, `chain:`, `chat:` prefixes.

**Required change:** Also match `adk.tool.*` as a tool call. Also exclude `adk.agent.*` and `adk.llm.*`.

```python
# Add to agent_patterns exclusion list
agent_patterns = [
    "agent:",
    "llm:",
    "chain:",
    "chat:",
    "adk.agent.",   # ADK agent spans
    "adk.llm.",     # ADK LLM spans
]

# Add to tool detection
if op_name.startswith("tool:") or op_name.startswith("adk.tool."):
    return True
```

#### `ToolCallExtractor._extract_single_tool_call()` (tool_call_extractor.py:169-274)

**Current behavior:** Strips `tool:` prefix to get `tool_name`. Extracts `agent_id` from attributes.

**Required changes:**
1. Also strip `adk.tool.` prefix
2. Extract context fields from attributes: `context_agent_goal`, `context_reasoning`, `context_previous_tool_calls`

```python
# Tool name extraction
if op_name.startswith("tool:"):
    tool_name = op_name[5:]
elif op_name.startswith("adk.tool."):
    tool_name = op_name[9:]
else:
    tool_name = op_name

# Context block extraction (new)
context = {}
if hasattr(call, "attributes"):
    attrs = call.attributes or {}
    if attrs.get("context_agent_goal"):
        context["agent_goal"] = attrs["context_agent_goal"]
    if attrs.get("context_reasoning"):
        context["reasoning"] = attrs["context_reasoning"]
    if attrs.get("context_previous_tool_calls"):
        context["previous_tool_calls"] = attrs["context_previous_tool_calls"]
```

#### `ToolCall` Model (core/models.py:38-74)

**Current fields:** `tool_name`, `inputs`, `outputs`, `duration_ms`, `span_id`, `parent_span_id`, `is_error`, `error_message`, `timestamp`, `agent_id`

**Fields to add:**
```python
agent_goal: str | None = None
"""The agent's stated objective when it made this tool call."""

reasoning: str | None = None
"""Why the agent chose this tool (from LLM response)."""

previous_tool_calls: list[str] | None = None
"""Span IDs of prior tool calls in the agent's chain."""
```

#### `ToolCallMetadata` Model (trace_instrumentation/models.py:184-258)

**Current fields:** `tool_name`, `parent_agent_id`, `input_summary`, `output_summary`, `status`, `error`, `duration_ms`, `started_at`

**Fields to add:**
```python
input_full: dict | None = None
"""Full tool input (replaces input_summary for evaluation)."""

output_full: dict | list | str | None = None
"""Full tool output (replaces output_summary for evaluation)."""

agent_goal: str | None = None
"""The invoking agent's current objective."""

reasoning: str | None = None
"""Why the agent selected this tool."""

previous_tool_calls: list[str] | None = None
"""Span IDs of prior tool calls in this chain."""
```

## 8. Threading and Parallel Agents


ADK supports `ParallelAgent` which runs sub-agents concurrently. This affects trace structure.

### OpenTelemetry Context Propagation

- Each async task in ADK carries its parent OpenTelemetry context automatically
- Parallel sub-agent spans appear as siblings under the same parent (L1 orchestrator)
- Weave's OTLP receiver reconstructs parallel branches correctly from `parent_span_id`

### Verification Needed

| Scenario | Expected Behavior | How to Verify |
|----------|-------------------|---------------|
| `ParallelAgent` with 3 sub-agents | 3 sibling L2 spans under L1 | Check Weave UI trace view |
| Python `asyncio.gather()` | Same as ParallelAgent | Check parent context propagation |
| Python `ThreadPoolExecutor` | Context may not propagate | Test explicitly; use `contextvars` if needed |
| Nested parallel agents | Proper L2 → L3 nesting within each branch | Check span tree depth |

### Known Risk

If KEN-E uses raw Python threads (not `asyncio` or ADK's `ParallelAgent`), OpenTelemetry context propagation requires explicit handling:

```python
from opentelemetry import context

# Capture current context before spawning thread
ctx = context.get_current()

def thread_target():
    # Restore context in new thread
    token = context.attach(ctx)
    try:
        # Agent work here...
    finally:
        context.detach(token)
```

## 9. Multi-Step Workflow Support (Section 13)


For multi-step workflows (e.g., keyword analysis → campaign creation → performance report), additional metadata enables trajectory and workflow-level evaluation.

### Additional Root Span Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `workflow_id` | string | Unique identifier for the workflow instance |
| `workflow_type` | string | Workflow template (e.g., `"keyword_analysis"`) |

### Additional Sub-Agent Span Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `step_type` | string | `"research"` \| `"generation"` \| `"analysis"` \| `"execution"` |
| `step_index` | int | Position in the workflow sequence (0-based) |
| `depends_on_steps` | string[] | Step IDs this step required as input |

### Workflow Evaluation Data Flow

```
Trace Spans (Weave)
    ↓ extract
StepEvaluation per sub-agent span
    ↓ aggregate
WorkflowEvaluation (task completion, quality, trajectory)
    ↓ store
Firestore: workflow_evaluations collection
```

### Workflow-Type Weight Configuration

Per the design doc (Section 13.4), different workflow types weight steps differently:

| Workflow Type | Step Weights |
|--------------|-------------|
| `keyword_analysis` | research=0.4, analysis=0.3, recommendation=0.3 |
| `campaign_creation` | brief_generation=0.2, content_generation=0.5, scheduling=0.1, deployment=0.2 |
| `performance_report` | data_retrieval=0.2, analysis=0.4, insight_generation=0.4 |

## 10. KEN-E Implementation Checklist


This checklist is ordered by priority. Items 1-4 are needed for current MER-E functionality. Items 5-8 enable future evaluation features.

### Immediate (Current Output Evaluation)

- [ ] **1. Weave SDK tracing initialized** — `weave.init()` called for all agent entry points (chatbot and strategy). Metadata attached via `weave.attributes()`.
- [ ] **2. Root span metadata** — Set `account_id`, `session_id`, `environment`, `rollout_percentage` via `weave.attributes()` or OTel span attributes on every execution
- [ ] **3. Sub-agent identification** — Every sub-agent span carries `agent_id` and `agent_version` in attributes
- [ ] **4. Structured output** — Sub-agent `call.output` contains the full structured response (not summarized)

### Near-Term (Tool Call Evaluation — Feature 3.5)

- [ ] **5. Full tool I/O** — Store complete `input` and `output` on tool call spans (not truncated summaries)
- [ ] **5b. Code execution trace extraction** — Extend `ToolCallExtractor` to detect `executable_code` and `code_execution_result` parts within `generate_content` spans. Pair code with results for evaluation. See Section 4.4.1.

- [ ] **6. Tool call context: agent_goal** — Propagate the agent's objective to tool call span attributes
- [ ] **7. Tool call context: reasoning** — Extract LLM reasoning for tool selection and attach to tool call spans
- [ ] **8. Tool call context: previous_tool_calls** — Track and attach the chain of prior tool call span IDs

### Future (Multi-Step Workflow Evaluation — Section 13)

- [ ] **9. Workflow metadata** — Set `workflow_id` and `workflow_type` on root span for multi-step workflows
- [ ] **10. Step metadata** — Set `step_type`, `step_index`, `depends_on_steps` on sub-agent spans within workflows

### Development/Debugging

- [x] **11. LLM content capture** — `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` in development and staging, `false` in production (user data privacy). Implemented in Feature 1.14 (Stories 1.14.2, 1.14.3).
- [ ] **12. Trace verification** — After instrumentation changes, verify trace hierarchy in Weave UI for a sample execution
- [ ] **13. Extractor compatibility** — Run MER-E's `ToolCallExtractor` against a sample trace to validate field extraction

## 11. Trace Compliance Validation


MER-E includes a trace compliance validator (`mer_e/adapters/ken_e/trace_instrumentation/validation.py`) that programmatically checks traces against these requirements.

### Required Fields (Compliance Failure if Missing)

| Field | Validation |
|-------|-----------|
| `agent_id` | Non-empty string |
| `agent_version` | Matches `^v?\d+\.\d+\.\d+(-[\w.]+)?$` |
| `account_id` | Non-empty string |
| `session_id` | Non-empty string |

### Fields with Defaults (Warning if Missing)

| Field | Default | Validation |
|-------|---------|-----------|
| `experiment_id` | `"baseline"` | String |
| `variant_name` | `"baseline"` | String |
| `environment` | `"production"` | One of: development, staging, canary, production |
| `rollout_percentage` | `100` | Integer 0-100 |

### Optional Fields (Validated Only if Present)

| Field | Validation |
|-------|-----------|
| `user_id` | String |
| `model_used` | String |
| `temperature` | Float 0.0-2.0 |
| `max_output_tokens` | Integer >= 1 |

### Phase 1 Success Metrics

| Metric | Target |
|--------|--------|
| Tool calls extracted per trace | > 90% |
| Trace metadata compliance | 100% |
| End-to-end pipeline functional | Yes |

## 12. Example: Complete Trace

Below is a simplified example of a compliant trace for a business strategy agent execution:

```json
{
  "span_name": "session_invocation",
  "attributes": {
    "account_id": "acc_123",
    "session_id": "sess_456",
    "user_id": "user_789",
    "environment": "production",
    "rollout_percentage": 100
  },
  "children": [
    {
      "span_name": "adk.agent.BusinessStrategyOrchestrator",
      "attributes": {
        "agent_id": "business_strategy_orchestrator",
        "agent_version": "v2.1.0",
        "experiment_id": "baseline",
        "variant_name": "baseline"
      },
      "children": [
        {
          "span_name": "adk.agent.BusinessResearcher",
          "attributes": {
            "agent_id": "business_researcher",
            "agent_version": "v1.3.0",
            "agent_goal": "Research competitive landscape for Acme Corp",
            "model_used": "gemini-2.0-flash",
            "temperature": 0.3
          },
          "output": {
            "company_overview_summary": "Acme Corp is a ...",
            "swot_analysis": { "strengths": [...], "weaknesses": [...] }
          },
          "children": [
            {
              "span_name": "adk.tool.google_search",
              "attributes": {
                "tool_name": "google_search",
                "status": "success",
                "context.agent_id": "business_researcher",
                "context.agent_goal": "Research competitive landscape for Acme Corp",
                "context.reasoning": "Need to find recent market data for Acme Corp's industry",
                "context.previous_tool_calls": []
              },
              "input": {
                "query": "Acme Corp cloud security market share 2026",
                "num_results": 10
              },
              "output": {
                "results": [
                  { "title": "...", "snippet": "...", "url": "..." }
                ]
              },
              "timing": { "duration_ms": 1850 }
            },
            {
              "span_name": "generate_content",
              "attributes": {
                "gen_ai.system": "vertex_ai",
                "gen_ai.request.model": "gemini-2.0-flash",
                "gen_ai.usage.input_tokens": 3200,
                "gen_ai.usage.output_tokens": 1800
              }
            },
            {
              "span_name": "adk.tool.firestore_read",
              "attributes": {
                "tool_name": "firestore_read",
                "status": "success",
                "context.agent_id": "business_researcher",
                "context.agent_goal": "Research competitive landscape for Acme Corp",
                "context.reasoning": "Retrieve existing company profile to avoid redundant research",
                "context.previous_tool_calls": ["span_id_of_google_search"]
              },
              "input": {
                "collection": "companies",
                "document_id": "acme_corp"
              },
              "output": {
                "name": "Acme Corp",
                "industry": "Cloud Security"
              },
              "timing": { "duration_ms": 120 }
            }
          ]
        }
      ]
    }
  ]
}
```

## 14. AH-PRD-09 Per-Turn Dispatch

AH-PRD-09 (Per-Turn Dispatch Agent) introduces a single unified `delegate_to_specialist`
entry-point tool.  This section documents the trace shape change it produces and the
attributes MER-E extractors should consume.

### 14.1 Span Hierarchy

```
KEN-E root agent invocation
└── LLM call(s)
└── delegate_to_specialist                ← single entry point (one per specialist call in turn)
    └── specialist_run                    ← per-call child
        ├── load_config_from_firestore    ← present on cache miss; absent on cache hit
        └── review_loop_iteration (0..N)  ← present when acceptance_criteria is non-empty
```

Compare to the pre-AH-PRD-09 shape, where each specialist produced its own
`dispatch_to_<specialist_name>` span at the same level.

### 14.2 Per-Span Attributes

#### `delegate_to_specialist`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `specialist_name` | `str` | Yes | Firestore `doc_id` of the resolved specialist |
| `cache_hit` | `bool` | Yes | `true` when the `LlmAgent` was served from the LRU cache; `false` on a fresh build |
| `mcp_pool_hit` | `bool` | No (future) | MCP connection-pool hit — populated by AH-62; absent in this release |

Written by `set_delegate_attrs()` in `app/adk/agents/utils/review_pipeline_tracing.py`.

#### `specialist_run`

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `acceptance_criteria` | `str` | Yes | Review-loop criteria forwarded from caller; empty string for single-pass mode |
| `exit_reason` | `str` | Yes | `"approved"` or `"max_iterations"` |
| `total_iterations` | `int` | Yes | Number of complete review iterations; `0` for single-pass |
| `output_key_prefix` | `str` | Yes | Pipeline key prefix (e.g. `"{doc_id}_review"`) |

These attributes existed under `dispatch_to_<specialist>` pre-AH-PRD-09; they now
appear one level deeper, under `specialist_run`.

#### `review_loop_iteration`

Unchanged from pre-AH-PRD-09.  See §7 for the existing extractor guidance.

### 14.3 Relation to §2 Span Hierarchy

The `delegate_to_specialist` span is emitted at the **L2** position (sub-agent
delegation level) in the hierarchy described in §2.  `specialist_run` is its L3
child; `review_loop_iteration` is L4.

### 14.4 MER-E Extractor Guidance

For the canonical post-AH-75 trace shape:

1. **Stop matching `dispatch_to_*` span names** — update any extractor query of the form
   `span["name"].startswith("dispatch_to_")` to `span["name"] == "delegate_to_specialist"`.

2. **Read `specialist_name` from the outer span** (`delegate_to_specialist.summary`),
   not from the span name itself.

3. **Read review-loop attributes from `specialist_run`** (one level deeper than before):
   `acceptance_criteria`, `exit_reason`, `total_iterations`, `output_key_prefix`.

4. **`cache_hit` is a new attribute** — include it in any cache-efficiency metrics or
   latency attribution analysis.

5. **Validate against the canonical fixture** at
   `app/adk/tracking/tests/fixtures/delegate_to_specialist_trace.json` and run
   `app/adk/tracking/tests/test_delegate_to_specialist_fixture.py` before the cutover.

### 14.5 Fixture Pointer

```
app/adk/tracking/tests/fixtures/delegate_to_specialist_trace.json
```

The fixture includes all required attributes for `delegate_to_specialist`,
`specialist_run`, and `review_loop_iteration`.  The conformance test suite at
`app/adk/tracking/tests/test_delegate_to_specialist_fixture.py` asserts schema
compliance and is wired into the standard pytest run.

**Supervisor-orchestration dispatch shape (AH-PRD-05, target post-ADK-2.0 unpin):** Multi-task supervisor-orchestrated turns produce a different span hierarchy. See [AH-PRD-05-trace-contract-diff.md](design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md) for the MER-E contract diff. Key differences: the root agent span contains coordinator task-ledger spans; each task produces a `task_delegation` sub-span with `usage_metadata` on the outer stream natively; fan-out branches are `fanout` spans containing parallel `task_delegation` children.

---

## 15. Skills Component Runtime Spans (SK-PRD-02)

SK-PRD-02 (Agent Factory — Skills & Sandbox Integration) adds five Weave spans emitted
by the agent-runtime layer and by the process-wide `SandboxPool`.  These spans are
distinct from the HTTP-tier spans documented in §4.6: §4.6 covers the FastAPI REST
surface (`api.skills.*`); this section covers agent-side callbacks and pool internals.
MER-E can correlate both surfaces by matching `account_id` — see §4.6 for the
cross-correlation guidance.

Reference: `docs/design/components/skills/projects/SK-PRD-02-agent-integration.md`
§4 (skill span contract) and §4.6 (sandbox_pool span contract).

### 15.1 Span Hierarchy

```
L1 — root agent invocation
└── L2 — sub-agent / specialist run
    ├── skill.list           ← emitted by skill_spans_before_tool_callback when
    │                           list_skills fires (or by the degraded-path helper
    │                           when all skills failed to load — see AC-2a)
    ├── skill.load           ← emitted when load_skill fires
    ├── skill.load_resource  ← sibling of skill.load (not a child); the
    │                           SkillToolset dispatches it as a separate tool call
    │                           in the same turn. `state["active_skill_id"]` is set
    │                           by a prior load_skill success, so it is logically
    │                           scoped to the active skill window even though the
    │                           Weave call graph is flat at this level.
    └── (tool calls, LLM calls, …)

pool internal (no agent-turn parent)
├── sandbox_pool.get     ← emitted by SandboxPool.get_or_create() (diagnostic /
│                           test accessor); parent is whatever Weave call is on
│                           the stack when the factory calls _build_code_executor()
├── sandbox_pool.lease   ← emitted by SandboxPool.lease().__aenter__(); fires on
│                           every execute_code call via LeasedSandboxExecutor.
│                           Carries refcount_after, cleared_tmp, tmp_clear_failed,
│                           client_cache_hit.
│                           tmp_clear_failed is on this span (not sandbox_pool.get)
│                           because _clear_tmp now fires only at the 0→1 refcount
│                           transition inside lease() (SK-42 CLOBBER fix).
├── sandbox_pool.release ← emitted by SandboxPool.lease().__aexit__(); fires after
│                           each execute_code call completes. Carries refcount_after
│                           and triggered_pending_evict (True when a deferred
│                           eviction fired because refcount reached 0).
└── sandbox_pool.evict   ← emitted by SandboxPool.evict(); fires during LRU cap
                            enforcement (after a miss), idle-TTL sweep (background
                            task), or direct caller invocation. LRU-eviction spans
                            appear adjacent to the sandbox_pool.get that triggered
                            them. Carries deferred=True when eviction was deferred
                            because refcount > 0 at eviction time.
```

### 15.2 Per-Span Attributes

#### `skill.list`

Emitted by `skill_spans_before_tool_callback` in `app/adk/tracking/skill_spans.py` when
the `list_skills` tool fires.  Also emitted by `_emit_total_failure_span`
(`skill_spans.py:109-152`) when the agent sidecar marks a build-time failure — in that
case `skill_count` is `0`, `skill_ids` is `[]`, and one or both of the failure flags is
present.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account whose skills collection was queried |
| `skill_count` | `int` | Yes | Number of skills whose L1 metadata was loaded at agent construction time. `0` on the degraded failure path. |
| `skill_ids` | `list[str]` | Yes | Ordered list of `skill_id` UUIDs for every skill in the constructed `SkillToolset`. Empty list on the degraded failure path. |
| `skill_owner_type` | `enum "account" \| "system"` | Yes | Owner type of the skills returned. Currently always `"account"` — SK-PRD-05 will introduce `"system"` for predefined skills without changing this attribute's presence or position. |
| `skill_load_total_failure` | `bool` | No | Present and `true` only when every requested skill failed to load at agent construction time (AC-2a). Absent on the happy path. |
| `skill_load_timeout` | `bool` | No | Present and `true` only when the 30-second sandbox-build worker bridge fired before any skill could load. Absent on the happy path. |

#### `skill.load`

Emitted when the `load_skill` tool fires.  Output-side attribute `instruction_bytes` is
attached on `finish_call` when the response carries an `instructions` field.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account owning the skill |
| `skill_id` | `str` | Yes | UUID of the skill being loaded. Set to `"unknown"` when the name-to-ID resolution in the sidecar fails. |
| `skill_name` | `str` | Yes | The kebab-case skill name passed by the LLM to `load_skill` (truncated to 256 chars) |
| `skill_version` | `int` | Yes | The version number of the skill loaded. `0` when version is unavailable from the sidecar. |
| `skill_owner_type` | `enum "account" \| "system"` | Yes | Owner type of the loaded skill. Currently always `"account"` — see `skill.list` note above. |
| `instruction_bytes` | `int` | No | Byte length of the SKILL.md instructions returned in the response. Attached on `finish_call`; absent when the response carries no `instructions` field. |

#### `skill.load_resource`

Emitted when the `load_skill_resource` tool fires.  Output-side attribute
`resource_bytes` is attached on `finish_call`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account owning the skill |
| `skill_id` | `str` | Yes | UUID of the skill that owns the resource. Set to `"unknown"` when resolution fails. |
| `rel_path` | `str` | Yes | Relative path of the requested resource within the skill bundle (e.g., `references/style-guide.md`). Truncated to 256 chars. |
| `skill_owner_type` | `enum "account" \| "system"` | Yes | Owner type. Currently always `"account"`. |
| `resource_bytes` | `int` | No | Byte length of the resource content returned. Attached on `finish_call`; absent when the response carries no content field. |

#### `sandbox_pool.get`

Emitted by `SandboxPool.get_or_create()` in
`app/adk/agents/agent_factory/sandbox_pool.py`.  This method is now a **diagnostic /
test accessor** — production callers use `lease()`.  Span is emitted after any LRU cap
enforcement.  Emission occurs outside the per-key stripe lock to keep the lock window
tight.

> **SK-42 note:** `tmp_clear_failed` was removed from this span when `_clear_tmp` moved
> to the 0 → 1 refcount transition inside `lease()`.  MER-E alert rules that match
> `sandbox_pool.get where tmp_clear_failed=true` should migrate to
> `sandbox_pool.lease where tmp_clear_failed=true`.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account whose sandbox was requested |
| `config_id` | `str` | Yes | The agent-config document ID (`AgentConfig.name`) used as the pool key |
| `cache_hit` | `bool` | Yes | `true` when an existing executor was returned from the pool; `false` when a new one was constructed |
| `pool_size_after` | `int` | Yes | Number of entries in the pool at span-emit time. Sampled outside the lock — concurrent inserts may shift the count by ±1. |

#### `sandbox_pool.lease`

Emitted by `SandboxPool.lease().__aenter__()` in
`app/adk/agents/agent_factory/sandbox_pool.py`.  Fires on every `execute_code` call
routed through `LeasedSandboxExecutor` (SK-42).  Emission occurs after construction /
any `_clear_tmp` call and before yielding the executor to the caller.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account whose sandbox was leased |
| `config_id` | `str` | Yes | The agent-config document ID used as the pool key |
| `refcount_after` | `int` | Yes | Refcount after this lease was acquired. `1` means this caller is the only active lease; `>1` means concurrent `execute_code` calls are in-flight on the same sandbox. |
| `cleared_tmp` | `bool` | Yes | `true` if `_clear_tmp` was called and succeeded on this lease acquisition (only possible on the 0 → 1 transition when `_CLEAR_TMP_ON_REUSE=True`). |
| `tmp_clear_failed` | `bool` | Yes | `true` if `_clear_tmp` raised on this lease acquisition (SK-35 defence-in-depth degraded — cross-session `/tmp` data may not have been purged). MER-E should alert on `count(sandbox_pool.lease where tmp_clear_failed=true) > 0` over a 5-minute window (see SK-9 §Q3 High disposition). |
| `client_cache_hit` | `bool` | Yes | `true` if `_clear_tmp` reused the lru-cached `vertexai.Client` (SK-43) on this lease acquisition; `false` on a cache miss (first construction for the `(project, location)` pair) **and** whenever no clear ran (refcount ≥ 1, or `_CLEAR_TMP_ON_REUSE=False`). Best-effort under concurrency — a hit credited by a concurrent `_clear_tmp` may be attributed to the wrong span; MER-E should aggregate over time windows. Watch for the hit rate dropping below ~95%, which signals multi-region / multi-project churn against `maxsize=2`. |

#### `sandbox_pool.release`

Emitted by `SandboxPool.lease().__aexit__()` in
`app/adk/agents/agent_factory/sandbox_pool.py`.  Fires after every `execute_code` call
completes (or raises).  Emission occurs after the refcount is decremented.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account whose sandbox was released |
| `config_id` | `str` | Yes | The agent-config document ID used as the pool key |
| `refcount_after` | `int` | Yes | Refcount after this lease was released. `0` means no active callers; the entry is idle and eligible for TTL eviction. |
| `triggered_pending_evict` | `bool` | Yes | `true` if this release triggered a deferred eviction (`pending_evict=True` was set while `refcount > 0` and refcount just reached 0). When `true`, `aclose()` was called and the pool entry was removed. |

#### `sandbox_pool.evict`

Emitted by `SandboxPool.evict()`.  Fires on LRU cap enforcement (reason `"lru"`), idle
TTL expiry (reason `"ttl"`), and explicit caller-driven eviction (reason `"manual"`).
No-op evictions (key not present) still emit this span; `pool_size_after` remains
accurate.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account whose sandbox was evicted |
| `config_id` | `str` | Yes | The agent-config document ID used as the pool key |
| `reason` | `enum "lru" \| "ttl" \| "manual"` | Yes | Why the entry was evicted: `"lru"` — LRU cap enforcement; `"ttl"` — idle TTL sweep; `"manual"` — direct external call to `evict()` |
| `pool_size_after` | `int` | Yes | Number of entries remaining in the pool after the eviction |
| `deferred` | `bool` | Yes | `true` when eviction was deferred because `refcount > 0` at eviction time. The executor is kept alive; the actual `aclose()` fires when the last lease holder releases (reflected in a `sandbox_pool.release` span with `triggered_pending_evict=true`). |

### 15.3 Relation to §2 Span Hierarchy

The three `skill.*` spans (`skill.list`, `skill.load`, `skill.load_resource`) appear at
the **L3 tool-call level** inside an L2 sub-agent run — the same level as the existing
`adk.tool.*` spans.  They are emitted from ADK `before_tool` / `after_tool` callbacks
rather than from ADK's built-in tool dispatch, so their `op_name` does **not** carry the
`adk.tool.` prefix.

The `sandbox_pool.*` spans are emitted from pool internals and are not scoped to any
agent turn.  `sandbox_pool.get` and `sandbox_pool.evict` fire during `build_agent` /
`specialist_runtime.resolve_agent`.  `sandbox_pool.lease` and `sandbox_pool.release`
fire on every `execute_code` call via `LeasedSandboxExecutor`; their Weave parent is
whatever agent-turn call is on the stack at that moment.  MER-E should correlate all
pool spans with the enclosing session by `account_id`, analogous to the HTTP-tier
correlation described in §4.6.

### 15.4 MER-E Extractor Guidance

1. **Match skill spans by exact `op_name`** — `skill.list`, `skill.load`,
   `skill.load_resource`.  These names carry **no** `adk.tool.` prefix.  Do not match
   them with a `startswith("adk.tool.")` filter.

2. **Match pool spans by exact `op_name`** — `sandbox_pool.get`,
   `sandbox_pool.lease`, `sandbox_pool.release`, `sandbox_pool.evict`.
   Alert on `sandbox_pool.lease where tmp_clear_failed=true` (SK-35 defence-in-depth
   degraded); the attribute moved from `sandbox_pool.get` in SK-42.

3. **`skill_owner_type` is always present** (value `"account"` in v1) and should be
   consumed as an enum, not a boolean.  When SK-PRD-05 (Predefined Skill Foundation)
   ships, the value set widens to `"account" | "system"` with no other change to this
   section.  Extractors should avoid hard-coding `"account"` as the only valid value.

4. **Failure-mode detection:** A `skill.list` span with `skill_load_total_failure: true`
   or `skill_load_timeout: true` indicates a degraded session where no skills were
   available to the agent.  Score these sessions accordingly in quality metrics.

---

## 16. Per-Turn Available-Specialist Roster Span (CH-58)

Emitted once per agent turn by `specialists_span_before_agent_callback` in
`app/adk/tracking/specialists_spans.py`.  The span records the exact specialist
set that was attached to `root_agent.sub_agents` at turn start — which is also
the set that was rendered into the "## Available Specialists" prompt block —
giving MER-E ground-truth availability data for routing-quality evaluation.

### 16.1 Span Hierarchy

```
ken_e_agent (L1 — root)
└── specialists.list  (L2 — emitted from before_agent_callback, before any tool call)
```

The span is emitted in `before_agent_callback` (not `before_tool_callback`), so
its `op_name` does **not** carry the `adk.tool.` prefix.

### 16.2 Per-Span Attributes

#### `specialists.list`

Emitted by `specialists_span_before_agent_callback` in
`app/adk/tracking/specialists_spans.py`.  One span per agent turn.  Fires after
`attach_specialists_before_agent_callback` populates session state.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `account_id` | `str` | Yes | The account the turn was executed for. Defaults to `"unknown"` when absent from session state. |
| `specialist_count` | `int` | Yes | Number of specialists available this turn. `0` when no specialists are configured for the account. |
| `specialists` | `list[{name, description, agent_id}]` | Yes | Per-specialist array. May be `[]` when no specialists are configured. See §16.3 for the entry shape. |

#### Per-entry shape for `specialists`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | The ADK agent name used by `transfer_to_agent`. Equals `agent_id` by ADK contract (see §16.4). |
| `description` | `str` | Yes | Human-readable description of the specialist (from Firestore `agent_configs`). Truncated to 1024 chars at capture time. Empty string when the agent has no description. |
| `agent_id` | `str` | Yes | The Firestore `agent_configs` doc ID. Equals `name` by ADK contract (see §16.4). MER-E may join roster entries to `agent_config` / version / deployment history on either field. |

### 16.3 Position in Hierarchy

`specialists.list` is a direct child of the L1 `ken_e_agent` root span, at the
same level as the L2 sub-agent spans described in §14.  It is emitted from a
`before_agent_callback` so it always precedes any tool-call or sub-agent spans
within the same turn.

### 16.4 `agent_id` ↔ `name` Equivalence

`agent_id` and `name` carry the same value in all v1 deployments.  This is an
ADK contract: `_build_specialist` assigns `name=doc_id` to every specialist
(see `specialist_runtime.py:510-512`), and the name is preserved through the
`LoopAgent` wrapper (`specialist_runtime.py:572`) and the `transfer_to_agent`
lookup (`specialist_runtime.py:626`).

Both fields are emitted so MER-E can:
- Join on `agent_id` for lookups against `agent_config` history.
- Join on `name` for correlation with `delegate_to_specialist` spans (which use
  the agent name as the transfer target).

A future ADK release that decouples `name` from `doc_id` would surface as a
contract-version bump in this section.  The test `test_agent_id_equals_name_invariant`
in `app/adk/tracking/tests/test_specialists_spans.py` is the in-code regression guard.

### 16.5 Empty vs Missing Semantics

Two distinct signals:

| Condition | `specialists.list` span present? | Meaning |
|-----------|----------------------------------|---------|
| `state["_available_specialists"] == []` | **Yes** (`specialist_count: 0`) | Legitimate — no specialists configured for this account yet. |
| `"_available_specialists"` key absent from state | **No** | **Degradation signal** — capture failed or callback wiring was bypassed. |

MER-E alert recommendation: a `ken_e_agent` root span with **no** `specialists.list`
child indicates a degraded capture path.  The absence should be treated as a
missing-data issue, not as "zero specialists were available."

### 16.6 MER-E Extractor Guidance

1. Match by exact `op_name`: `specialists.list`.  No `adk.tool.` prefix.
2. The span is a **direct child** of the `ken_e_agent` root span.
3. `specialists` array entries each carry `{name, description, agent_id}`.
   Join on `agent_id` for `agent_config` lookups; join on `name` for routing
   span correlation.
4. `specialist_count == 0` with `specialists == []` is a valid turn state, not
   an error.  Only the **absence** of the span itself signals degradation.

**For supervisor-orchestrated turns (AH-PRD-05 target):** Task-mode `usage_metadata` appears on the outer stream natively (AH-99 probe-1 + probe-4 confirmed). Extract `usage_metadata` from task-mode events using the same `extract_billable_tokens` helper — the field placement is unchanged; only the span context changes. Coordinator-to-task-specialist call boundaries are marked by the `task_delegation` span boundary. See [AH-PRD-05-trace-contract-diff.md](design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md) for the full extractor-migration guidance and MER-E validation checklist.

---

## 13. Glossary

| Term | Definition |
|------|-----------|
| **ADK** | Google Agent Development Kit — the framework KEN-E agents are built with |
| **OTLP** | OpenTelemetry Protocol — the wire format for sending traces to Weave |
| **Span** | A single unit of work in a trace (e.g., one tool call, one LLM call) |
| **Trace** | The complete tree of spans from a single execution |
| **op_name** | The operation name on a Weave call/span |
| **Output Extractor** | MER-E component that parses agent output into evaluatable items |
| **ToolCallExtractor** | MER-E component that extracts tool invocations from trace trees |
| **Weave Call** | W&B Weave's representation of a span, accessed via the Weave Python SDK |
