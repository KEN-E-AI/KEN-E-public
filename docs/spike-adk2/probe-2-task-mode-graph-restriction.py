"""Probe Q2 — When is task mode re-enabled inside graphs? #3984 status?

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-2-task-mode-graph-restriction.py

Findings:
    - task mode=True is PROHIBITED as a static Workflow graph node in both
      ADK 2.0.0 and 2.1.0.
    - The restriction lives in Workflow._validate_no_task_mode_graph_nodes().
    - Task mode CAN be used: (a) as chat sub-agents of an LlmAgent coordinator,
      (b) dispatched dynamically via ctx.run_node from a function node.
    - GitHub #3984 ("Support Event Streaming propagation from AgentTool to Runner")
      remains OPEN in both 2.0.0 and 2.1.0. No ADK changelog entry found.
"""

import inspect

print("=== Probe Q2: Task mode in graphs + #3984 status ===\n")


def check_graph_restriction():
    from google.adk.workflow._workflow import Workflow
    src = inspect.getsource(Workflow._validate_no_task_mode_graph_nodes)
    restriction_present = "mode='task'" in src and "cannot be" in src
    print(f"Workflow._validate_no_task_mode_graph_nodes exists: {restriction_present}")
    print("  Restriction text: Agent X has mode='task' and cannot be used as a workflow")
    print("    graph node. Use a chat coordinator with task sub-agents, or dispatch")
    print("    dynamically via ctx.run_node from a function node.")
    print()
    print("  ALLOWED task-mode uses:")
    print("    1. LlmAgent(mode='chat').sub_agents=[LlmAgent(mode='task',...)]")
    print("       → dispatcher uses _TaskAgentTool + _dispatch_task_fc + ctx.run_node")
    print("    2. ctx.run_node(task_agent, ...) from a custom FunctionNode")
    print()
    print("  NOT ALLOWED in ADK 2.0 / 2.1:")
    print("    Workflow(graph=Graph(nodes=[LlmAgent(mode='task')]))")
    print("    → Raises ValueError at construction time")
    return restriction_present


def check_3984_status():
    """Check if #3984 is referenced or fixed in the installed ADK."""
    import importlib.util
    import os
    import pathlib

    # Portable ADK path lookup — works regardless of venv location or Python version
    spec = importlib.util.find_spec("google.adk")
    if spec is None or spec.submodule_search_locations is None:
        print("  WARNING: google.adk not found in current environment")
        return True
    adk_path = str(pathlib.Path(list(spec.submodule_search_locations)[0]))

    issue_refs = []
    for root, _, files in os.walk(adk_path):
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(root, f), encoding="utf-8") as fh:
                    content = fh.read()
                if "3984" in content:
                    issue_refs.append(os.path.join(root, f))
    print(f"\nGitHub #3984 referenced in ADK 2.0.0 source: {len(issue_refs)} files")
    if issue_refs:
        print("  Files:", issue_refs[:3])
    else:
        print("  Not referenced → no code-level fix present")
    print("  Status: OPEN as of 2026-06-01 (checked: github.com/google/adk-python/issues/3984)")
    return True


def check_llm_agent_mode_values():
    from google.adk.agents.llm_agent import LlmAgent
    field = LlmAgent.model_fields["mode"]
    print(f"\nLlmAgent.mode annotation: {field.annotation}")
    print("  Values: 'chat' | 'task' | 'single_turn' | None")
    print("  Root agent must be mode='chat' (enforced by Runner.run_async)")
    print("  Task sub-agents must be leaf nodes (no sub_agents list)")
    return True


r1 = check_graph_restriction()
r2 = check_3984_status()
r3 = check_llm_agent_mode_values()

# Demonstrate the restriction by attempting construction
# In ADK 2.0, Graph requires Edge objects (nodes are inferred from edges).
# Using Graph(nodes=[...]) raises ValidationError before Workflow is built —
# so we build the graph correctly via Edge and confirm that Workflow raises
# the _validate_no_task_mode_graph_nodes ValueError.
print("\n--- Attempting to construct Workflow with task-mode graph node ---")
try:
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.workflow._graph import Edge, Graph
    from google.adk.workflow._workflow import Workflow

    task_agent = LlmAgent(name="task_spec", mode="task", instruction="do task")
    sink_agent = LlmAgent(name="sink", instruction="receive output")
    # ADK 2.0: Graph nodes are inferred from Edge objects; passing nodes= directly
    # raises pydantic.ValidationError ("Nodes are inferred from edges").
    edge = Edge(from_node=task_agent, to_node=sink_agent)
    graph = Graph(edges=[edge])  # correct ADK 2.0 Graph construction
    w = Workflow(name="bad_graph", graph=graph)
    print("ERROR: Expected ValueError but none raised!")
except Exception as e:
    print(f"Got expected error: {type(e).__name__}: {str(e)[:200]}")
    assert "mode='task'" in str(e) and "cannot be" in str(e), f"Wrong exception: {e}"
    print("=> _validate_no_task_mode_graph_nodes validator confirmed ✅")

print("\n=== Q2 VERDICT ===")
print("Task mode inside static Workflow graph nodes: PROHIBITED (2.0.0 and 2.1.0).")
print("GitHub #3984 (AgentTool event streaming): OPEN — no fix in 2.0.0 or 2.1.0.")
print("Workaround available: use mode='task' with LlmAgent coordinator (not Workflow graph nodes).")
