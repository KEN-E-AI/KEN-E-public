# Review Loop & Workflow Orchestration — Implementation Plan

**Version:** 1.1
**Date:** March 18, 2026
**Status:** Proposed — for roadmap/story creation

> **Revised March 18, 2026 (v1.1)** — Structural corrections based on ADK 1.26.0 experiments: removed `SequentialAgent` wrappers inside `LoopAgent`, added `include_contents='none'` on reviewers and synthesizers, added `{key?}` optional template syntax, added pipeline wrappers for `ParallelAgent` branches, added synthesizer agent pattern, added 3 new risks (pitfalls).
**Decision:** [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e)

> **Status by phase (as of 2026-04-21):** Phases 1–3 are now tracked by [AH-PRD-01 — Review Loop Framework](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) (Release 2). Phase 4 (Multi-Step Workflow Support, Release 3) and Phase 5 (Observability & Monitoring, Release 5) have not yet been extracted into their own PRDs — this document remains the authoritative design source for both until those PRDs are written.

---

## 1. Overview

> **Roadmap:** [Feature 2.1: Review Loop Framework](../product-roadmap.md#21--review-loop-framework) — Release 2.0

This document is a comprehensive implementation plan for adding **review loops** and **multi-step workflow orchestration** to the KEN-E agent system. It is intended to be used as input for creating features and user stories in the product roadmap.

### Problem

The current dispatch pattern runs specialist agents once and relays their output verbatim to the user. There is no quality gate — the Root Agent cannot verify that a specialist's response meets the user's intent before presenting it. For complex, multi-step tasks that span multiple specialists, there is no mechanism for parallel data gathering, intermediate synthesis, user approval checkpoints, or phased execution.

### Solution

Use ADK's native workflow agents (LoopAgent, SequentialAgent, ParallelAgent) to implement a **Generator-Critic review loop** around every specialist delegation, and compose these loops into multi-step workflows with parallel execution and user approval checkpoints.

### Design References

| Document | Section | Content |
|----------|---------|---------|
| Harness Design Doc | 2.3.2 | Request flow with review loop |
| Harness Design Doc | 4.6 | Review Loop Pattern (Generator-Critic) |
| Harness Design Doc | 8.1 | Multi-Step Workflow Pattern |
| Harness Design Doc | 8.2 | ADK Implementation Details (factory code, composition patterns) |
| Harness Design Doc | 8.3 | ADK Pitfalls (validated rules from experiments) |
| Harness Design Doc | 8.4 | LLM Call Cost & Latency (total-time estimates) |
| `components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md` | — | Single-step review-loop execution PRD (this doc's Phases 1–3 realized) |
| Notion | Decision 21 | Full decision rationale |

---

## 2. ADK Constructs

All required constructs are available in ADK 1.26.0 (currently installed). No version upgrade needed for this feature.

| Construct | Import | Purpose |
|-----------|--------|---------|
| `LoopAgent` | `google.adk.agents.loop_agent` | Iterative cycle — runs sub-agents **sequentially** until `exit_loop` called or `max_iterations` reached. Checks `escalate` between each sub-agent — no `SequentialAgent` wrapper needed inside. |
| `SequentialAgent` | `google.adk.agents.sequential_agent` | Chains sub-agents in order with shared state. **Does not check `escalate`** — runs all sub-agents unconditionally. Use for pipeline wrapping and phase chaining, not inside `LoopAgent`. |
| `ParallelAgent` | `google.adk.agents.parallel_agent` | Runs independent sub-agents concurrently |
| `LlmAgent` | `google.adk.agents.llm_agent` | LLM-backed agent. Key parameters: `output_key` (writes text to session state), `include_contents` (set to `'none'` to exclude conversation history from context — agent sees only its instruction with template substitutions). |
| `output_key` | Parameter on `LlmAgent` | Writes agent's text output to a named session state key |
| `exit_loop` | Built-in tool on agents inside `LoopAgent` | Sets `escalate=True` in EventActions, terminates parent LoopAgent. Produces no text output — if the agent also has `output_key`, it extracts `""` (see pitfall below). |

### Key Behaviors

- **`output_key`**: Agent's text output is written to `session.state[output_key]`. Downstream agents read via `{key}` template substitution in their `instruction` string. Use `{key?}` (with `?`) for optional keys that may not exist on first iteration — resolves to empty string instead of `KeyError`.
- **`include_contents`**: Set to `'none'` on an `LlmAgent` to exclude conversation history from context. The agent sees only its instruction text with template substitutions. Critical for reviewers (evaluate only the draft, not history) and synthesizers (see only parallel outputs, not review loop back-and-forth).
- **`exit_loop`**: Only available to agents nested inside a `LoopAgent`. When called, sets `escalate=True` — the `LoopAgent` checks this between sub-agents and exits. **Important:** `exit_loop` is a tool call with no text, so `output_key` extracts `""` — never place `exit_loop` on the agent whose `output_key` holds important state.
- **`ParallelAgent`**: Runs all sub-agents concurrently. Each must write to a unique `output_key` to avoid state collisions. No automatic state synchronization — results are available in session state after all sub-agents complete.
- **`LoopAgent`**: Non-LLM orchestrator. Repeatedly runs its sub-agents **sequentially** until `exit_loop` is called or `max_iterations` is reached. Checks `escalate` between each sub-agent. Does not make its own LLM calls.
- **`SequentialAgent`**: Non-LLM orchestrator. Runs sub-agents in order. **Does not check `escalate`** — runs all sub-agents unconditionally regardless of `exit_loop` calls within them.

---

## 3. Architecture

### 3.1 Building Block: Review Pipeline

The atomic building block is a `LoopAgent` with specialist and reviewer as direct sub-agents (no `SequentialAgent` wrapper — `LoopAgent` iterates sequentially and checks `escalate` between each):

```
review_loop (LoopAgent, max_iterations=3)
├── specialist (LlmAgent, output_key="step_N_draft")
│     instruction: task + acceptance_criteria + {step_N_feedback?}
│     tools: [specialist-specific MCP/SDK tools]
└── reviewer (LlmAgent, output_key="step_N_feedback", include_contents='none')
      instruction: evaluate {step_N_draft} against acceptance_criteria
      tools: [exit_loop]
      APPROVED → call exit_loop (LoopAgent checks escalate, skips specialist, exits)
      NOT MET → write feedback to step_N_feedback (next iteration, specialist reads it)
```

Key details:
- **`include_contents='none'` on reviewer** — evaluates only the template-injected `{step_N_draft}`, not conversation history
- **`{step_N_feedback?}` (optional)** — on first iteration, no feedback exists; `?` resolves to empty string
- Each step uses a unique `output_key` suffix (e.g., `step_1a_draft`, `step_1b_draft`) to avoid state collisions in parallel execution
- **Artifact evaluation** — when a specialist calls `create_visualization()`, the reviewer evaluates both the text draft and any visualization artifacts. See [`data-visualization.md`](components/agentic-harness/data-visualization.md) Section 6.

### 3.2 Single-Step Delegation

For simple queries (e.g., "What's the latest company news?"):

```
Root Agent (LlmAgent)
  → generates acceptance criteria
  → calls search_company_news(query, acceptance_criteria)
    → dispatch handler builds:
        review_loop (LoopAgent, max_iterations=3)
        ├── news_specialist (output_key="draft")
        │     instruction: task + criteria + {review_feedback?}
        └── reviewer (output_key="review_feedback",
              include_contents='none', tools=[exit_loop])
    → invokes pipeline
    → returns approved draft to Root Agent
  → Root Agent presents to user
```

### 3.3 Multi-Step Workflow

For complex tasks (e.g., "Increase budgets for Meta Ads campaigns that result in the most engaged website visitors"):

```
Phase 1 — Data Gathering (ParallelAgent):
  Step 1a: Analytics Specialist → GA engagement data
  Step 1b: Execution Specialist → Meta Ads spend data

Phase 2 — Synthesis (Root Agent):
  Combines Phase 1 results → presents optimisation plan to user → waits for approval

Phase 3 — Execution (after user approval):
  Step 3: Execution Specialist → applies budget changes in Meta Ads
```

#### ADK Agent Tree

**Phase 1** (built and run in a single tool call):

```
data_gathering (ParallelAgent)
├── step_1a_pipeline (SequentialAgent)
│   └── step_1a_loop (LoopAgent, max_iterations=3)
│       ├── analytics_specialist (output_key="step_1a_draft")
│       │     instruction: task + criteria + {step_1a_feedback?}
│       └── step_1a_reviewer (output_key="step_1a_feedback",
│             include_contents='none', tools=[exit_loop])
│
└── step_1b_pipeline (SequentialAgent)
    └── step_1b_loop (LoopAgent, max_iterations=3)
        ├── execution_specialist (output_key="step_1b_draft")
        │     instruction: task + criteria + {step_1b_feedback?}
        └── step_1b_reviewer (output_key="step_1b_feedback",
              include_contents='none', tools=[exit_loop])
```

> **Pipeline wrappers:** Each `LoopAgent` is wrapped in a `SequentialAgent` ("pipeline") inside the `ParallelAgent`. This allows future pre/post steps per branch without restructuring the tree.

**Phase 2** — Synthesis (dedicated agent, not Root Agent):

```
synthesizer (LlmAgent, include_contents='none')
  instruction: "You are given completed research from two parallel analyses.
                Combine into an optimisation plan:
                Analytics findings: {step_1a_draft}
                Spend data: {step_1b_draft}"
```

- Synthesizer uses `include_contents='none'` with a strong instruction framing injected data as "completed research"
- Root Agent presents synthesised plan to user: "Here's my recommended plan... Shall I proceed?"

**Phase 3** (runs on next conversation turn after user approval):

```
step_3_pipeline (SequentialAgent)
└── step_3_loop (LoopAgent, max_iterations=3)
    ├── execution_specialist (output_key="step_3_draft")
    │     instruction: approved plan + {step_3_feedback?}
    └── step_3_reviewer (output_key="step_3_feedback",
          include_contents='none', tools=[exit_loop])
```

### 3.4 User Approval via Conversation Turns

User approval checkpoints do **not** require ADK `pause_invocation` infrastructure. The Root Agent's conversational nature handles this naturally:

- **Turn 1:** User asks → Root plans → runs Phase 1 → synthesises → presents to user
- **Turn 2:** User approves → Root runs Phase 3 → confirms changes

Workflow progress is tracked in **session state** between turns so the Root Agent knows where it left off.

### 3.5 Termination Rules

| Condition | Behavior |
|-----------|----------|
| Reviewer calls `exit_loop` | LoopAgent exits. Draft in `output_key` is the approved result. |
| `max_iterations` reached | LoopAgent exits. Last draft returned with soft warning. |
| Specialist tool failure | Error propagated via `output_key`. Reviewer sees error, can call `exit_loop` with failure note. |

### 3.6 Token & Latency Impact

| Scenario | Token overhead | Latency overhead |
|----------|---------------|-----------------|
| Single step, approved 1st pass | ~1,000 tokens | ~3-5s |
| Single step, 2 iterations | ~2,000 tokens | ~6-12s |
| Multi-step (3 phases) | ~3,000-9,000 tokens | ~15-45s total |
| Parallel steps (1a + 1b) | Same tokens as sequential | ~50% less latency (concurrent) |

These figures represent **overhead only** — the additional cost of running a review loop compared to a single-pass specialist invocation without review. They do not include the specialist's own token consumption or tool-call latency.

> For **total-time estimates** (including specialist LLM calls, tool execution, and review iterations), see the harness design doc Sections [4.6 — LLM Call Cost](../KEN-E-System-Architecture.md#46-review-loop-pattern-generator-critic-planned) and [8.4 — LLM Call Cost & Latency](../KEN-E-System-Architecture.md#84-llm-call-cost--latency), which provide per-scenario totals (e.g., 2 LLM calls / ~10-30s for first-pass approval, up to 6 calls / ~30-90s at max iterations).

---

## 4. File Inventory

### 4.1 New Files

| File | Purpose | Estimated Size |
|------|---------|---------------|
| `app/adk/agents/utils/review_pipeline.py` | Pipeline factories: `build_review_pipeline()`, `build_workflow_pipeline()` | ~200 lines |
| `app/adk/agents/utils/test_review_pipeline.py` | Unit tests for pipeline construction and execution | ~300 lines |

### 4.2 Modified Files

| File | Change | Risk |
|------|--------|------|
| `app/adk/agents/ken_e_agent.py` | Add `acceptance_criteria: str` to existing tool functions. Add `execute_workflow(steps)` tool. Update root instruction with criteria generation guidance. | Medium — touches root agent definition |
| `app/adk/agents/utils/dispatch_handlers.py` | Add `acceptance_criteria: str | None` parameter. When provided, build review pipeline and invoke. | Medium — touches dispatch logic |
| `app/adk/agents/utils/supervisor_utils.py` | Update `invoke_agent_sync()` to extract `output_key` values from final session state. Backward-compatible fallback to text concatenation. | Low — additive change |

### 4.3 Files NOT Changed

| File | Reason |
|------|--------|
| `app/adk/agents/company_news_chatbot/agent.py` | Specialist agent itself is unchanged — the review loop wraps it externally |
| `app/adk/agents/google_analytics_agent_v4.py` | Same — wrapped externally |
| `app/adk/agents/registry.py` | No registry changes needed |
| `deploy_ken_e.py` | No deployment changes needed |

---

## 5. Implementation Phases

### Phase 1: Review Pipeline Factory (Core Building Block)

> **Tracked by:** [AH-PRD-01 — Review Loop Framework](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) (R2). Read the PRD for the current implementation plan; this section remains as the design rationale and code-sample reference.

**Goal:** Create the reusable `build_review_pipeline()` function that constructs a LoopAgent with specialist and reviewer as direct sub-agents.

**Stories:**

#### Story 1.1: `build_review_pipeline()` Factory Function

**Description:** Create `app/adk/agents/utils/review_pipeline.py` with a factory function that constructs the review pipeline agent hierarchy.

**Acceptance Criteria:**
- Function signature: `build_review_pipeline(specialist: LlmAgent, acceptance_criteria: str, output_key_prefix: str, max_iterations: int = 3) -> LoopAgent`
- Creates a LoopAgent with specialist and reviewer as **direct sub-agents** (no SequentialAgent wrapper)
- Specialist instruction includes `{output_key_prefix}_feedback?` template (optional `?` suffix) for iteration feedback
- Reviewer instruction includes `{output_key_prefix}_draft` template for draft evaluation
- Reviewer uses `include_contents='none'` to evaluate only the template-injected draft
- Reviewer has `exit_loop` available as a tool (built-in when nested in LoopAgent)
- Specialist writes to `{output_key_prefix}_draft` via `output_key`
- Reviewer writes to `{output_key_prefix}_feedback` via `output_key`
- Each pipeline uses unique output_key prefixes to avoid state collisions
- Reviewer instruction template supports optional `{step_N_artifacts?}` variable for evaluating visualization artifacts produced by `create_visualization()`

**Implementation Notes:**
```python
def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str = "review",
    max_iterations: int = 3,
) -> LoopAgent:
    """Build a review loop: specialist produces draft, reviewer evaluates against criteria."""

    draft_key = f"{output_key_prefix}_draft"
    feedback_key = f"{output_key_prefix}_feedback"

    # Clone specialist with output_key and updated instruction
    specialist_with_output = LlmAgent(
        name=f"{specialist.name}_worker",
        model=specialist.model,
        instruction=f"""
{specialist.instruction}

ACCEPTANCE CRITERIA:
{acceptance_criteria}

PREVIOUS FEEDBACK (if any):
{{{feedback_key}?}}

Your task: produce output that meets ALL acceptance criteria. If feedback is provided,
address each point specifically.
""",
        tools=specialist.tools,
        output_key=draft_key,
    )

    reviewer = LlmAgent(
        name=f"{output_key_prefix}_reviewer",
        model="gemini-2.0-flash",
        include_contents='none',
        instruction=f"""
You are a quality reviewer. Evaluate the following draft against the acceptance criteria.

ACCEPTANCE CRITERIA:
{acceptance_criteria}

DRAFT TO REVIEW:
{{{draft_key}}}

If ALL criteria are met: call the exit_loop tool immediately.
If ANY criteria are NOT met: write specific, actionable feedback explaining what is missing
or incorrect. Do NOT call exit_loop.
""",
        output_key=feedback_key,
    )

    # No SequentialAgent wrapper — LoopAgent iterates sub-agents sequentially
    # and checks escalate between each (SequentialAgent would swallow escalate)
    return LoopAgent(
        name=f"{output_key_prefix}_loop",
        sub_agents=[specialist_with_output, reviewer],
        max_iterations=max_iterations,
    )
```

**Dependencies:** None (standalone function).

**Tests:**
- Pipeline construction produces correct agent hierarchy (LoopAgent → [specialist, reviewer] as direct sub-agents, no SequentialAgent)
- Reviewer has `include_contents='none'`
- Output keys are correctly assigned
- Unique prefixes prevent key collisions between multiple pipelines

---

#### Story 1.2: `invoke_agent_sync()` Output Key Extraction

**Description:** Update `supervisor_utils.py` to extract named `output_key` values from session state after pipeline invocation.

**Acceptance Criteria:**
- After invoking a pipeline, extract the draft value from session state using the expected `output_key`
- Backward-compatible: if no `output_key` found, fall back to existing text concatenation behavior
- Returns the approved draft text as a string

**Implementation Notes:**
```python
def extract_pipeline_result(session_state: dict, output_key_prefix: str) -> str | None:
    """Extract the approved draft from session state after pipeline execution."""
    draft_key = f"{output_key_prefix}_draft"
    return session_state.get(draft_key)
```

**Dependencies:** None.

**Tests:**
- Extracts correct value when output_key exists in state
- Returns None when output_key not in state
- Existing `invoke_agent_sync()` behavior unchanged when no output_key is used

---

#### Story 1.3: Unit Tests for Review Pipeline

**Description:** Create comprehensive unit tests for the review pipeline factory.

**Acceptance Criteria:**
- Test: pipeline construction produces correct hierarchy (LoopAgent > [specialist, reviewer] as direct sub-agents, no SequentialAgent)
- Test: mock specialist returns bad draft iteration 1, good draft iteration 2 — verify exit_loop called on iteration 2
- Test: `max_iterations=1` exhaustion — verify last draft returned without error
- Test: unique output_key prefixes across multiple pipelines — verify no key collisions
- Test: reviewer instruction contains correct acceptance criteria text
- Test: specialist instruction contains correct feedback template variable

**Dependencies:** Stories 1.1, 1.2.

---

### Phase 2: Single-Step Integration (Wire Into Existing Dispatch)

> **Tracked by:** [AH-PRD-01 — Review Loop Framework](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) (R2).

**Goal:** Integrate the review pipeline into existing dispatch handlers so that when acceptance criteria are provided, the specialist runs inside a review loop.

**Stories:**

#### Story 2.1: Add `acceptance_criteria` to Dispatch Handlers

**Description:** Add an optional `acceptance_criteria: str | None = None` parameter to dispatch functions in `dispatch_handlers.py`. When criteria are provided, wrap the specialist in a review pipeline before invocation.

**Acceptance Criteria:**
- `dispatch_to_company_news(query, tool_context, acceptance_criteria=None)` — updated signature
- `dispatch_to_google_analytics(query, tool_context, acceptance_criteria=None)` — updated signature
- When `acceptance_criteria is None`: existing single-pass behavior (backward compatible)
- When `acceptance_criteria` is provided: build review pipeline via `build_review_pipeline()`, invoke it, return approved draft
- Weave tracing via `@safe_weave_op()` still works with the new parameter

**Implementation Notes:**
```python
@safe_weave_op()
def dispatch_to_company_news(
    query: str,
    tool_context: ToolContext | None = None,
    acceptance_criteria: str | None = None,
) -> dict:
    # ... existing setup ...

    if acceptance_criteria:
        pipeline = build_review_pipeline(
            specialist=news_agent,
            acceptance_criteria=acceptance_criteria,
            output_key_prefix="news_review",
        )
        result = invoke_pipeline(pipeline, session_state)
        return {"result": result}

    # Existing single-pass behavior
    result = invoke_agent_sync(news_agent, query, session_state)
    return {"result": result}
```

**Dependencies:** Phase 1 complete.

**Tests:**
- Dispatch with `acceptance_criteria=None` — identical to current behavior
- Dispatch with criteria — review pipeline is built and invoked
- Weave traces include review loop sub-spans

---

#### Story 2.2: Add `acceptance_criteria` to Root Agent Tool Functions

**Description:** Add `acceptance_criteria: str` parameter to the tool wrapper functions in `ken_e_agent.py`.

**Acceptance Criteria:**
- `search_company_news(query: str, acceptance_criteria: str = "", tool_context: ToolContext | None = None)` — updated signature
- `query_google_analytics(query: str, acceptance_criteria: str = "", tool_context: ToolContext | None = None)` — updated signature
- Empty string treated as no criteria (backward compatible with LLM calls that don't provide criteria)
- Criteria string passed through to dispatch handler

**Dependencies:** Story 2.1.

**Tests:**
- Tool function called without criteria — no review loop
- Tool function called with criteria — criteria passed to dispatch handler

---

#### Story 2.3: Integration Test — Single-Step Review Loop

**Description:** End-to-end test of the single-step review loop flow.

**Acceptance Criteria:**
- Test: user message → root generates criteria → dispatch builds pipeline → specialist produces draft → reviewer approves → result returned
- Test: specialist produces bad draft → reviewer rejects → specialist iterates → reviewer approves on 2nd pass
- Test: max_iterations reached → last draft returned with warning
- Weave trace shows review loop iterations as sub-spans

**Dependencies:** Stories 2.1, 2.2.

---

### Phase 3: Enable Criteria Generation

> **Tracked by:** [AH-PRD-01 — Review Loop Framework](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) (R2).

**Goal:** Update the Root Agent's instruction to generate acceptance criteria before tool calls.

**Stories:**

#### Story 3.1: Update Root Agent Instruction

**Description:** Add criteria generation guidance to the root agent's base instruction so the LLM naturally produces acceptance criteria before calling specialist tools.

**Acceptance Criteria:**
- Root instruction includes guidance: "Before calling a specialist tool, generate 2-4 measurable acceptance criteria..."
- Guidance includes examples of good vs. bad criteria
- Criteria should be specific, measurable, and testable by a reviewer
- Instruction includes format guidance (e.g., numbered list)

**Implementation Notes:**
Add to the base instruction in `ken_e_agent.py`:

```
## Task Delegation

Before calling any specialist tool, generate 2-4 specific acceptance criteria that the
specialist's response must satisfy. Good criteria are:
- Measurable: "Include a table with columns: campaign name, sessions, engagement rate"
- Specific: "Cover the past 30 days of data"
- Testable: A reviewer can objectively determine if the criterion is met

Bad criteria (too vague):
- "Provide useful information"
- "Be comprehensive"

Pass your criteria as the `acceptance_criteria` parameter when calling the tool.
```

**Dependencies:** Story 2.2.

**Tests:**
- End-to-end: user message → root generates criteria (verify criteria are present in tool call) → pipeline runs → approved result returned
- Criteria generation does not significantly increase latency for simple queries

---

### Phase 4: Multi-Step Workflow Support

> **Roadmap:** [Feature 3.4: Multi-Step Workflows](../product-roadmap.md#34--multi-step-workflows) — Release 3.0
> **PRD status:** Not yet extracted into a PRD. This section is the authoritative design source until a dedicated AH-PRD is created.

**Goal:** Add the ability to decompose complex tasks into multi-step workflows with parallel execution and user approval checkpoints.

**Stories:**

#### Story 4.1: `build_workflow_pipeline()` Factory

**Description:** Create a factory function that constructs a workflow agent hierarchy from a dependency graph of steps.

**Acceptance Criteria:**
- Function signature: `build_workflow_pipeline(steps: list[WorkflowStep], specialists: dict[str, LlmAgent]) -> Agent`
- `WorkflowStep` dataclass: `id`, `specialist`, `query`, `criteria`, `depends_on: list[str]`
- Steps with no shared dependencies → wrapped in `ParallelAgent`
- Steps that depend on a prior step → run sequentially (after dependency completes)
- Steps with `approval_required: True` → excluded from pipeline (handled by Root Agent between turns)
- Each step wrapped in a review pipeline via `build_review_pipeline()`
- Returns the composed agent hierarchy

**Implementation Notes:**

```python
@dataclass
class WorkflowStep:
    id: str
    specialist: str
    query: str
    criteria: str
    depends_on: list[str] = field(default_factory=list)
    approval_required: bool = False

def build_workflow_pipeline(
    steps: list[WorkflowStep],
    specialists: dict[str, LlmAgent],
) -> Agent:
    """Build a workflow from a dependency graph of steps."""

    # Filter out approval-required steps (handled by Root Agent)
    executable_steps = [s for s in steps if not s.approval_required]

    # Group by dependency level
    # Level 0: steps with no dependencies (can run in parallel)
    # Level 1: steps that depend on level 0 steps
    # etc.

    levels = _compute_dependency_levels(executable_steps)

    level_agents = []
    for level_steps in levels:
        pipelines = []
        for step in level_steps:
            specialist = specialists[step.specialist]
            loop = build_review_pipeline(
                specialist=specialist,
                acceptance_criteria=step.criteria,
                output_key_prefix=f"step_{step.id}",
            )
            # Wrap each LoopAgent in a pipeline SequentialAgent for
            # future pre/post steps (matches Section 3.3 diagram)
            pipeline = SequentialAgent(
                name=f"step_{step.id}_pipeline",
                sub_agents=[loop],
            )
            pipelines.append(pipeline)

        if len(pipelines) == 1:
            level_agents.append(pipelines[0])
        else:
            level_agents.append(ParallelAgent(
                name=f"parallel_level_{levels.index(level_steps)}",
                sub_agents=pipelines,
            ))

    if len(level_agents) == 1:
        return level_agents[0]

    return SequentialAgent(
        name="workflow",
        sub_agents=level_agents,
    )
```

**Dependencies:** Phase 1 complete.

**Tests:**
- 2 parallel steps → ParallelAgent wrapping 2 pipeline SequentialAgents wrapping LoopAgents
- 1 step depending on 2 parallel steps → SequentialAgent(ParallelAgent, LoopAgent)
- Approval-required steps excluded from pipeline
- Step results accessible via unique output_keys in session state

---

#### Story 4.2: `execute_workflow()` Root Agent Tool

**Description:** Add an `execute_workflow(steps)` tool to the Root Agent that builds and invokes a workflow pipeline.

**Acceptance Criteria:**
- Tool signature: `execute_workflow(steps: str, tool_context: ToolContext | None = None) -> str`
- `steps` parameter is a JSON string containing an array of step objects
- Each step object: `{"id": "1a", "specialist": "analytics", "query": "...", "criteria": "...", "depends_on": []}`
- Tool parses steps, builds workflow pipeline, invokes it
- Returns combined results from all completed steps
- Steps with `approval_required: True` cause the tool to return intermediate results for user presentation

**Implementation Notes:**
```python
def execute_workflow(steps: str, tool_context: ToolContext | None = None) -> str:
    """Execute a multi-step workflow with review loops and parallel execution."""
    parsed_steps = json.loads(steps)
    workflow_steps = [WorkflowStep(**s) for s in parsed_steps]

    # Split into pre-approval and post-approval phases
    approval_idx = next(
        (i for i, s in enumerate(workflow_steps) if s.approval_required),
        len(workflow_steps)
    )

    pre_approval = workflow_steps[:approval_idx]

    # Build and execute pre-approval pipeline
    pipeline = build_workflow_pipeline(pre_approval, available_specialists)
    results = invoke_pipeline(pipeline, session_state)

    # Store workflow state for resumption after approval
    if approval_idx < len(workflow_steps):
        session_state["pending_workflow"] = {
            "remaining_steps": [s.__dict__ for s in workflow_steps[approval_idx + 1:]],
            "completed_results": results,
        }

    return results
```

**Dependencies:** Story 4.1, Phase 2 complete.

**Tests:**
- Single-phase workflow (no approval required) — all steps execute
- Multi-phase workflow — pre-approval steps execute, workflow state saved, post-approval steps pending
- Resumption after approval — pending steps execute correctly

---

#### Story 4.3: Update Root Agent Instruction for Workflow Planning

**Description:** Add workflow planning guidance to the Root Agent's instruction so it can decompose complex tasks into structured step plans.

**Acceptance Criteria:**
- Instruction includes guidance on when to use `execute_workflow` vs. single tool calls
- Includes examples of step decomposition with dependency graphs
- Guidance on identifying parallel-safe steps vs. sequential dependencies
- Guidance on identifying steps requiring user approval

**Implementation Notes:**
Add to the root instruction:

```
## Multi-Step Workflows

For complex tasks that require multiple specialists or phased execution:
1. Decompose the task into discrete steps
2. Identify which specialist handles each step
3. Define acceptance criteria for each step
4. Identify dependencies (which steps must complete before others can start)
5. Identify approval points (steps requiring user review before proceeding)
6. Call execute_workflow() with the step plan

Example: "Increase budgets for best-performing Meta Ads campaigns"
Steps:
  1a: Query GA for engagement by campaign (Analytics) - no dependencies
  1b: Query Meta Ads for spend by campaign (Execution) - no dependencies
  2:  Create optimisation plan (Root) - depends on 1a, 1b - approval required
  3:  Execute budget changes (Execution) - depends on 2
```

**Dependencies:** Story 4.2.

**Tests:**
- End-to-end: complex user request → Root decomposes into steps → workflow executes → user sees results

---

#### Story 4.4: Integration Test — Multi-Step Workflow

**Description:** End-to-end test of the multi-step workflow with parallel data gathering.

**Acceptance Criteria:**
- Test: 2 parallel data-gathering steps → both complete → results combined
- Test: user approval checkpoint — workflow pauses, returns intermediate results
- Test: workflow resumption after approval — remaining steps execute
- Test: one parallel step fails → other still completes → partial results returned
- Weave traces show parallel execution, review iterations, and phase boundaries

**Dependencies:** Stories 4.1, 4.2, 4.3.

---

### Phase 5: Observability & Monitoring

> **Roadmap:** [Feature 5.4: Advanced Workflow & Observability](../product-roadmap.md#54--advanced-workflow--observability) — Release 5.0
> **PRD status:** Not yet extracted into a PRD. This section is the authoritative design source until a dedicated AH-PRD is created.

**Goal:** Ensure review loop iterations and workflow execution are visible in tracing and monitoring.

**Stories:**

#### Story 5.1: Weave Trace Integration

**Description:** Ensure review loop iterations appear as sub-spans in Weave traces.

**Acceptance Criteria:**
- Each review loop iteration appears as a distinct span
- Specialist and reviewer sub-spans are visible within each iteration
- Draft content and review feedback are captured in span attributes
- Acceptance criteria are captured in the top-level pipeline span
- Exit condition (approved vs. max_iterations) is captured

**Dependencies:** Phase 2 complete.

**Tests:**
- Invoke review pipeline → verify Weave trace structure matches expected hierarchy
- Verify acceptance criteria appear in trace metadata

---

#### Story 5.2: User-Facing Progress Indicators

**Description:** For multi-step workflows, provide progress updates to the user during execution.

**Acceptance Criteria:**
- Multi-step workflows emit progress messages: "Gathering analytics data...", "Querying Meta Ads spend..."
- Progress messages are streamed to the user (not buffered until completion)
- Review loop iterations are invisible to the user (internal quality mechanism)

**Dependencies:** Phase 4 complete.

**Implementation Notes:**
Progress can be communicated via ADK's streaming callback mechanisms or by having the dispatch handler write progress markers to session state that the API layer can poll.

---

## 6. Dependency Graph

```
Phase 1 (Core Building Block)
├── Story 1.1: build_review_pipeline()
├── Story 1.2: output_key extraction
└── Story 1.3: Unit tests
      │
      ▼
Phase 2 (Single-Step Integration)
├── Story 2.1: Dispatch handler criteria parameter
├── Story 2.2: Root agent tool parameter
└── Story 2.3: Integration test
      │
      ▼
Phase 3 (Criteria Generation)
└── Story 3.1: Root agent instruction update
      │
      ▼
Phase 4 (Multi-Step Workflows)
├── Story 4.1: build_workflow_pipeline()
├── Story 4.2: execute_workflow() tool
├── Story 4.3: Root instruction update
└── Story 4.4: Integration test
      │
      ▼
Phase 5 (Observability)
├── Story 5.1: Weave trace integration
└── Story 5.2: Progress indicators
```

Phases 1-3 can ship independently. Phase 4 builds on Phase 2. Phase 5 is incremental.

---

## 7. Verification Checklist

| # | Test | Phase | Type |
|---|------|-------|------|
| 1 | `build_review_pipeline()` — mock specialist returns bad draft iter 1, good draft iter 2. Verify exit_loop called on iter 2. | 1 | Unit |
| 2 | `max_iterations=1` exhaustion. Verify last draft returned, no error. | 1 | Unit |
| 3 | `build_workflow_pipeline()` — 2 parallel steps + 1 sequential step. Verify ParallelAgent wraps the parallel pair. | 4 | Unit |
| 4 | Dispatch with criteria. Verify review loop runs and returns approved draft. | 2 | Integration |
| 5 | Dispatch with `acceptance_criteria=None`. Verify identical to current behavior. | 2 | Integration |
| 6 | Multi-step workflow with parallel data gathering. Verify both results extracted. | 4 | Integration |
| 7 | Workflow with approval checkpoint. Verify pause and resumption. | 4 | Integration |
| 8 | Weave traces show review iterations as sub-spans. | 5 | Integration |
| 9 | End-to-end: user message → root generates criteria → pipeline → approved result. | 3 | E2E |
| 10 | End-to-end: complex task → workflow decomposition → parallel execution → user approval → execution. | 4 | E2E |

---

## 8. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Latency increase** from review loops | Medium — each iteration adds 3-5s | Set `max_iterations=3` (cap at ~15s overhead). Root Agent can skip criteria for simple lookups. |
| **Token cost increase** | Low-Medium — ~1,000-3,000 extra tokens per delegation | Reviewer uses `gemini-2.0-flash` (cheapest model). Criteria generation adds ~200 tokens. |
| **LLM generates poor criteria** | Medium — vague criteria lead to rubber-stamp approvals | Instruction examples of good vs. bad criteria. Monitor via Weave traces. Iterate on instruction. |
| **State collisions in parallel execution** | High if not handled | Unique `output_key` prefix per step enforced by factory function. |
| **Review loop never exits** | Low — `max_iterations` cap prevents infinite loops | Default `max_iterations=3`. Return last draft with warning. |
| **Backward compatibility regression** | Medium | `acceptance_criteria=None` default preserves current behavior. Phase 2 tests verify this. |
| **`output_key` + `exit_loop` state overwrite** | Medium — `exit_loop` produces no text, so `output_key` extracts `""` and overwrites state key | Never place `exit_loop` on the agent whose `output_key` holds important state. In the review loop, the reviewer (not specialist) calls `exit_loop`. The reviewer's `output_key` is `feedback_key` — overwritten to `""` on exit, but only read on next iteration (which won't happen after exit). |
| **`SequentialAgent` swallows `escalate`** | High — reviewer's `exit_loop` signal ignored, specialist runs after approval | Place specialist and reviewer directly under `LoopAgent`, not inside a `SequentialAgent` wrapper. `LoopAgent` checks `escalate` between sub-agents; `SequentialAgent` does not. |
| **Synthesizer sees full conversation history** | Medium — confuses model with review loop back-and-forth from parallel branches | Use `include_contents='none'` on synthesizer agent with a strong instruction framing injected template data as "completed research." |
| **Artifact size in review context** | Low-Medium — large Vega-Lite specs with embedded data (>1,000 rows) could consume significant tokens in the reviewer's instruction template | Limit embedded data to summary/aggregated values in the artifact. Defer raw data to a separate `data_uri` field if specs exceed a size threshold. |

---

## 9. Estimation Summary

| Phase | Stories | Estimated Effort | Prerequisites |
|-------|---------|-----------------|---------------|
| Phase 1: Core Building Block | 3 | 2-3 days | None |
| Phase 2: Single-Step Integration | 3 | 2-3 days | Phase 1 |
| Phase 3: Criteria Generation | 1 | 1 day | Phase 2 |
| Phase 4: Multi-Step Workflows | 4 | 3-5 days | Phase 2 |
| Phase 5: Observability | 2 | 1-2 days | Phase 2+ |
| **Total** | **13** | **9-14 days** | |

---

## 10. Open Questions

| # | Question | Impact | When to Resolve |
|---|----------|--------|----------------|
| 1 | Should the reviewer model be configurable per specialist, or always use `gemini-2.0-flash`? | Low — cost optimization | Phase 1 |
| 2 | How should workflow progress be communicated to the streaming API? | Medium — UX | Phase 5 |
| 3 | Should there be a "fast path" that skips review loops for simple factual queries? | Medium — latency | Phase 3 |
| 4 | How does the review loop interact with the existing `ConversationSummarizer`? Will intermediate drafts and feedback inflate the conversation history? | Medium — token budget | Phase 2 |
| 5 | ~~Should workflow state (`pending_workflow`) be persisted to Firestore for crash recovery, or is session state sufficient?~~ **Answered:** Harness doc Sections 8.5-8.7 define the long-term Firestore persistence model (data model, persistence/recovery table, idempotency). Story 4.2's session-state `pending_workflow` is the initial incremental step; full Firestore persistence follows once the workflow framework matures. | Low — reliability | Phase 4 |
| 6 | What is the maximum number of steps a workflow should support? | Low — UX guardrail | Phase 4 |
| 7 | How do skills interact with review loops? Should the reviewer have access to the same skills as the specialist, or only evaluation-focused skills? | Low — skill architecture | Phase 1 (when skills are implemented) |
| 8 | How should visualization artifacts be formatted for reviewer evaluation? Should the reviewer see the full Vega-Lite spec JSON, a summary, or only the metadata? | Low-Medium — affects review quality and token budget | Phase 1 (when `create_visualization` is implemented) |

---

## References

- [Decision 21: Task Delegation with Review Loops](https://www.notion.so/32030fd6530281a8a30fc8e12c3f931e) — Notion Design Decision
- Harness Design Doc Section 4.6 — Review Loop Pattern (Generator-Critic)
- Harness Design Doc Section 8.1 — Multi-Step Workflow Pattern
- [`components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md`](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) — Single-step review-loop execution PRD
- [ADK LoopAgent Documentation](https://google.github.io/adk-docs/agents/workflow-agents/loop-agents/)
- [ADK Generator-Critic Pattern](https://google.github.io/adk-docs/agents/workflow-agents/loop-agents/#example-generator-critic-pattern)
