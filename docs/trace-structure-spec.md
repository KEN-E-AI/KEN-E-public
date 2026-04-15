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

> **Roadmap:** [Feature 1.1.2: Tracing Hardening](product-roadmap.md#112--tracing-hardening) — Release 1.1

### ADK Native Names vs. MER-E Expectations

ADK uses dot-notation span names. MER-E's current `ToolCallExtractor` uses colon-prefix matching. The table below documents the mapping:

| Span Type | ADK Native Name | MER-E Current Pattern | Recommended Resolution |
|-----------|----------------|----------------------|----------------------|
| Agent | `adk.agent.<ClassName>` | `agent:<agent_id>` | Match via `attributes.agent_id` |
| Tool | `adk.tool.<tool_name>` | `tool:<tool_name>` | Match via `attributes.type == "tool"` or `adk.tool.` prefix |
| LLM | `generate_content` / `chat.completions` | `llm:<model_name>` | Exclude via known LLM op_name patterns |
| Formatter | `<subagent>_format` | Not matched | Identified by `_format` suffix in op_name |

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

> **Roadmap:** [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#25--mer-e-phase-0-trace-extraction), [Feature 3.5: MER-E Phase 1 — Quality Scoring](product-roadmap.md#35--mer-e-phase-1-quality-scoring) — Releases 2.0, 3.0

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

## 5. Context Block Capture Strategy

> **Roadmap:** [Feature 3.5: MER-E Phase 1 — Quality Scoring](product-roadmap.md#35--mer-e-phase-1-quality-scoring) — Release 3.0

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

> **Roadmap:** [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#25--mer-e-phase-0-trace-extraction), [Feature 3.5: MER-E Phase 1 — Quality Scoring](product-roadmap.md#35--mer-e-phase-1-quality-scoring) — Releases 2.0, 3.0

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

> **Roadmap:** [Feature 3.4: Multi-Step Workflows](product-roadmap.md#34--multi-step-workflows) — Release 3.0

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

> **Roadmap:** [Feature 3.4: Multi-Step Workflows](product-roadmap.md#34--multi-step-workflows), [Feature 5.4: Advanced Workflow & Observability](product-roadmap.md#54--advanced-workflow--observability) — Releases 3.0, 5.0

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

> **Roadmap:** [Feature 1.1.2: Tracing Hardening](product-roadmap.md#112--tracing-hardening), [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#25--mer-e-phase-0-trace-extraction) — Releases 1.1, 2.0

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

> **Roadmap:** [Feature 1.1.2: Tracing Hardening](product-roadmap.md#112--tracing-hardening), [Feature 2.5: MER-E Phase 0 — Trace Extraction](product-roadmap.md#25--mer-e-phase-0-trace-extraction) — Releases 1.1, 2.0

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
