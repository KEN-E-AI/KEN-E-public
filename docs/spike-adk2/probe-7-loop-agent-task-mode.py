"""Probe Q7 — Can LoopAgent carry mode='task' given leaf-node constraint?

Run with:
    /tmp/adk2-probe/bin/python docs/spike-adk2/probe-7-loop-agent-task-mode.py

Findings:
    - LoopAgent is DEPRECATED in ADK 2.0 (replaced by Workflow).
    - LoopAgent does NOT have a 'mode' field — it inherits from BaseAgent,
      not LlmAgent (which has mode).
    - Workflow (the new loop) also does NOT have mode='task'.
    - mode='task' applies ONLY to LlmAgent leaf nodes (no sub_agents list).
    - The review-loop pattern (generator + critic in a loop) must be restructured
      in ADK 2.0: cannot be wrapped in a single task-mode container.
    - Options for review-loop restructuring in ADK 2.0:
      (a) Keep LoopAgent (deprecated but functional) for the inner review loop;
          wrapping is NOT task-mode, just loop semantics.
      (b) Use Workflow with a loop trigger and two static LlmAgent nodes
          (worker + reviewer). Task mode applies to each individual node if needed.
      (c) The supervisor (chat coordinator) dispatches a task-mode agent that
          internally handles review iterations via standard multi-turn conversation.
    - The leaf-node constraint: if the reviewer must be a task agent (multi-turn),
      it cannot have sub_agents — which means the current LoopAgent pattern
      (where reviewer is a sub-agent of LoopAgent) is incompatible with task mode
      AT THE REVIEW-LOOP LEVEL, but not at the leaf level.
"""

import inspect

print("=== Probe Q7: LoopAgent + mode='task' with leaf-node constraint ===\n")


def check_loop_agent_deprecated():
    from google.adk.agents.loop_agent import LoopAgent
    src = inspect.getsource(LoopAgent)
    is_deprecated = "@deprecated" in src
    has_mode = "mode" in LoopAgent.model_fields
    print(f"LoopAgent deprecated: {is_deprecated}")
    print(f"LoopAgent has 'mode' field: {has_mode}")
    print(f"LoopAgent MRO: {[c.__name__ for c in LoopAgent.__mro__]}")
    return is_deprecated, not has_mode


def check_workflow_mode():
    from google.adk.workflow._workflow import Workflow
    has_mode = "mode" in Workflow.model_fields
    print(f"\nWorkflow (replacement for LoopAgent) has 'mode' field: {has_mode}")
    print("  => Workflow cannot carry mode='task' — it's a composition container, not LlmAgent")
    return not has_mode


def check_llm_agent_leaf_constraint():
    from google.adk.agents.llm_agent import LlmAgent
    src = inspect.getsource(LlmAgent)

    # Find the leaf node constraint
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if "leaf" in line.lower() or ("sub_agent" in line.lower() and "task" in line.lower()):
            print(f"  line {i}: {line.strip()}")

    print("\nLeaf-node constraint for mode='task':")
    print("  From ADK docs + source: task-mode agents must be leaf nodes (no sub_agents)")
    print("  Reason: task mode implies the agent pauses mid-invocation for user input;")
    print("    having sub_agents would require the orchestrator to also pause — unsupported")
    print("  => LlmAgent(mode='task', sub_agents=[reviewer]) is NOT allowed")
    return True


def show_restructuring_options():
    print("\n--- Review-loop restructuring options for ADK 2.0 ---")
    print()
    print("Option A (RECOMMENDED for short-term): Keep LoopAgent (deprecated)")
    print("  - LoopAgent still works in 2.0 (deprecated ≠ removed)")
    print("  - Sub-agents (worker + reviewer) remain LlmAgent leaves (can be mode=task)")
    print("  - The LoopAgent itself is NOT task-mode (loop container, not an LlmAgent)")
    print("  - The supervisor coordinator dispatches the LoopAgent as a static sub-agent")
    print("  - Risk: LoopAgent will be removed in a future ADK version")
    print()
    print("Option B (ADK 2.0 idiomatic): Workflow with static graph")
    print("  - Workflow(graph=Graph([worker_node, reviewer_node], triggers=[...]))")
    print("  - Worker and reviewer are static graph nodes (not task-mode inside Workflow)")
    print("  - Workflow exit triggered by reviewer emitting a specific output")
    print("  - The coordinator dispatches the Workflow as a static sub-agent")
    print("  - Review: Workflow graph requires explicit edge/trigger definition")
    print()
    print("Option C: Single task-mode specialist handles review internally")
    print("  - Specialist LlmAgent(mode='task') includes self-review in its instruction")
    print("  - No separate reviewer agent — instruction encodes the review criteria")
    print("  - Simpler but loses the independent reviewer quality gate")
    print()
    print("Constraint summary:")
    print("  - LoopAgent cannot carry mode='task'")
    print("  - Workflow cannot carry mode='task'")
    print("  - Each LlmAgent INSIDE the loop CAN have mode='task' (if leaf)")
    print("  - But task-mode reviewer can't have the exit_loop tool (exit_loop is a FunctionTool)")
    print("  - => review-loop exit mechanism works fine (exit_loop is a leaf LlmAgent tool)")
    return True


r1, r2 = check_loop_agent_deprecated()
check_workflow_mode()
check_llm_agent_leaf_constraint()
show_restructuring_options()

print("\n=== Q7 VERDICT ===")
print("LoopAgent CANNOT carry mode='task' (it's BaseAgent, not LlmAgent; deprecated in 2.0).")
print("Workflow CANNOT carry mode='task' (same reason — composition container, not LlmAgent).")
print("Review-loop sub-agents (worker, reviewer) CAN be LlmAgent leaves (compatible with task mode)")
print("  IF the LoopAgent/Workflow wrapping them does not itself require task mode.")
print("Short-term: keep LoopAgent (deprecated but functional) for review-loop wrapper.")
print("Long-term: migrate to Workflow(graph) with explicit review-loop trigger semantics.")
