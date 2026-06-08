"""Supervisor-orchestration utilities for AH-PRD-05.

Pure-function substrate consumed by the root coordinator when it decomposes a
multi-specialist user request into a TODO ledger.  Nothing in this module
touches ADK session state, Firestore, or any I/O — every function is
deterministic and easily unit-testable.

Public surface:
  - ``compute_dependency_levels(items)`` — Kahn topological sort over the
    ``depends_on`` DAG; returns a list-of-id-lists partitioned by depth or
    an ``"ERROR: ..."`` string on cycle / dangling ref.
  - ``validate_ledger(items, known_specialist_ids, max_items)`` — composes
    the three validation checks (cap, unknown specialist, cycle/dangling-dep).
  - ``MAX_LEDGER_ITEMS`` — soft cap constant (12).
  - ``SUPERVISOR_INSTRUCTION_FRAGMENT`` — Markdown string fragment spliced
    into the root agent's instruction suffix by ``hierarchy.py``.
  - ``get_supervisor_function_tools()`` — returns the two ledger-management
    ``FunctionTool`` instances needed by the coordinator.
"""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_LEDGER_ITEMS: int = 12

# ---------------------------------------------------------------------------
# compute_dependency_levels
# ---------------------------------------------------------------------------


def compute_dependency_levels(
    items: list[dict[str, Any]],
) -> list[list[str]] | str:
    """Partition task IDs into dependency levels via Kahn's algorithm.

    Level 0 contains tasks with no dependencies.  Level N contains tasks
    whose every dependency is in a level < N.  Tasks at the same level have
    no ordering constraint between them and can be fanned out in parallel.

    Args:
        items: List of dicts, each carrying:
            - ``item_id`` (str) — unique task identifier.
            - ``depends_on`` (list[str]) — IDs of upstream tasks that must
              complete before this one starts.  Missing or ``None`` is treated
              as ``[]``.

    Returns:
        ``list[list[str]]`` — one inner list per dependency level on success.
        Empty input returns ``[]``.  Single-task with no deps returns ``[[id]]``.

        ``str`` — an ``"ERROR: ..."`` string when:
        - ``depends_on`` references an ``item_id`` not present in ``items``
          (dangling dependency).
        - A cycle exists in the ``depends_on`` DAG.
    """
    if not items:
        return []

    # Build id → deps mapping and validate references first.
    id_to_deps: dict[str, list[str]] = {}
    all_ids: set[str] = set()
    for item in items:
        item_id: str = item.get("item_id", "")
        raw_deps = item.get("depends_on") or []
        id_to_deps[item_id] = list(raw_deps)
        all_ids.add(item_id)

    # Dangling-dependency check.
    for item_id, deps in id_to_deps.items():
        for dep in deps:
            if dep not in all_ids:
                return (
                    f"ERROR: depends_on references unknown item_id {dep!r} "
                    f"in task {item_id!r}."
                )

    # Kahn's algorithm — in-degree tracking.
    in_degree: dict[str, int] = dict.fromkeys(all_ids, 0)
    # predecessors: which tasks point *to* this one (reverse adjacency).
    successors: dict[str, list[str]] = {iid: [] for iid in all_ids}
    for item_id, deps in id_to_deps.items():
        for dep in deps:
            in_degree[item_id] += 1
            successors[dep].append(item_id)

    queue: deque[str] = deque(
        iid for iid in all_ids if in_degree[iid] == 0
    )
    levels: list[list[str]] = []
    visited: int = 0

    while queue:
        # All IDs currently at depth 0 form one level.
        level_size = len(queue)
        current_level: list[str] = []
        for _ in range(level_size):
            iid = queue.popleft()
            current_level.append(iid)
            visited += 1
            for successor in successors[iid]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)
        levels.append(sorted(current_level))  # sort for deterministic output

    if visited != len(all_ids):
        cycle_ids = sorted(iid for iid in all_ids if in_degree[iid] > 0)
        return f"ERROR: cyclic depends_on detected: {cycle_ids!r}."

    return levels


# ---------------------------------------------------------------------------
# validate_ledger
# ---------------------------------------------------------------------------


def validate_ledger(
    items: list[dict[str, Any]],
    known_specialist_ids: set[str],
    max_items: int = MAX_LEDGER_ITEMS,
) -> str | None:
    """Validate a supervisor TODO ledger post-normalization.

    Composes three checks in order:
    1. Soft-cap: ``len(items) > max_items`` → error.
    2. Unknown specialist: any item's ``assignee`` not in ``known_specialist_ids``
       (only when ``known_specialist_ids`` is non-empty) → error.
    3. Cyclic / dangling deps: delegates to ``compute_dependency_levels`` and
       propagates its error string verbatim.

    Args:
        items: Normalized ``TodoItem`` dicts (post ``_normalize_items``).
        known_specialist_ids: Set of valid specialist ``doc_id`` strings sourced
            from ``session.state["_available_specialists"]``.  When empty the
            unknown-specialist check is skipped (Firestore-degraded / test path).
        max_items: Soft cap on ledger size.  Defaults to ``MAX_LEDGER_ITEMS``.

    Returns:
        ``None`` on success; an ``"ERROR: ..."`` string on any failure.
    """
    if len(items) > max_items:
        return (
            f"ERROR: supervisor ledger exceeds soft cap of {max_items} items "
            f"({len(items)} items provided). Larger work belongs in Project Tasks."
        )

    # Duplicate item_id check — must run before Kahn's sort, which silently
    # overwrites the first entry's dependency list when two items share an ID.
    seen_ids: set[str] = set()
    for item in items:
        item_id = item.get("item_id", "")
        if item_id in seen_ids:
            return f"ERROR: duplicate item_id {item_id!r} in supervisor ledger."
        seen_ids.add(item_id)

    if known_specialist_ids:
        for item in items:
            assignee = item.get("assignee")
            if assignee is not None and assignee not in known_specialist_ids:
                item_id = item.get("item_id", "<unknown>")
                return (
                    f"ERROR: unknown specialist {assignee!r} in task {item_id!r}. "
                    "Use a specialist from the Available Specialists block in your instructions."
                )

    dep_result = compute_dependency_levels(items)
    if isinstance(dep_result, str):
        return dep_result

    return None


# ---------------------------------------------------------------------------
# SUPERVISOR_INSTRUCTION_FRAGMENT
# ---------------------------------------------------------------------------

SUPERVISOR_INSTRUCTION_FRAGMENT: str = """\
## Multi-Task Decomposition

You are an `LlmAgent(mode='chat')` coordinator. When the user's request requires
multiple specialists or phases, decompose it into a TODO ledger before delegating.

### When to decompose

**Use the supervisor model** (write a `supervisor_ledger` and then delegate) when
the request:
- Requires data or actions from **two or more different specialists**, OR
- Requires a **synthesized result** across independent specialist outputs, OR
- Involves a **spend-changing or irreversible action** that must be approved before
  execution (e.g. updating ad budgets, modifying campaign settings).

**Fall through to `transfer_to_agent`** (no ledger, no supervisor machinery)
when:
- The request can be fully handled by a **single specialist** in one call. This is
  the common case — do NOT write a ledger for single-specialist queries.

### How to write the ledger

Call `set_todo_list` with `list_id="supervisor_ledger"`. Each item MUST include:

| Field | Required | Description |
|-------|----------|-------------|
| `item_id` | Yes | Unique short slug (e.g. `"ga_data"`, `"synthesis"`) |
| `text` | Yes | Human-readable task title shown in the UI |
| `assignee` | Yes | Specialist `doc_id` (e.g. `"google_analytics_specialist"`) |
| `query` | Yes | The task query passed verbatim to the specialist |
| `criteria` | Yes | Acceptance criteria for the per-task review loop |
| `depends_on` | Yes | List of upstream `item_id`s (empty `[]` for root tasks) |
| `result_key` | Yes | `session.state` key where the specialist writes output (e.g. `"ga_result"`) |
| `status` | No | Default: `"pending"` |

Include `"requires_approval"` verbatim in `criteria` for any task that makes
irreversible changes (budget updates, campaign edits, data writes).

### Soft cap

The ledger is capped at **12 items**. Work that exceeds 12 tasks belongs in
**Project Tasks** (ask the user to create a Project Plan instead).

### Worked example — budget optimisation flow

```
set_todo_list(
  list_id="supervisor_ledger",
  title="Increase budgets for best-performing Meta Ads campaigns",
  items=[
    {
      "item_id": "ga_engagement",
      "text": "Pull GA engagement data for Meta Ads traffic",
      "assignee": "google_analytics_specialist",
      "query": "Retrieve weekly engaged sessions and bounce rate for visitors
                arriving from Meta Ads campaigns over the last 4 weeks.",
      "criteria": "Data covers ≥4 weeks; bounce rate and engaged sessions per
                   campaign are present.",
      "depends_on": [],
      "result_key": "ga_result"
    },
    {
      "item_id": "meta_spend",
      "text": "Pull Meta Ads campaign spend and performance",
      "assignee": "meta_ads_specialist",
      "query": "Retrieve last-4-week spend, impressions, and clicks per
                campaign from Meta Ads.",
      "criteria": "Spend and click data present for ≥1 active campaign.",
      "depends_on": [],
      "result_key": "meta_result"
    },
    {
      "item_id": "synthesis",
      "text": "Identify best-performing campaigns and propose budget changes",
      "assignee": "google_analytics_specialist",
      "query": "Using {ga_result} and {meta_result}, identify the top 3 Meta
                Ads campaigns by engaged sessions and propose specific budget
                increases (percentage and absolute amount).",
      "criteria": "Recommendations reference specific campaign names; budget
                   proposals are actionable and within ±20 % of current spend.",
      "depends_on": ["ga_engagement", "meta_spend"],
      "result_key": "synthesis_result"
    },
    {
      "item_id": "budget_update",
      "text": "Apply approved budget increases in Meta Ads",
      "assignee": "meta_ads_specialist",
      "query": "Apply the budget changes from {synthesis_result}.",
      "criteria": "requires_approval; budgets updated for each campaign listed
                   in synthesis_result.",
      "depends_on": ["synthesis"],
      "result_key": "budget_update_result"
    }
  ]
)
```

After calling `set_todo_list`, proceed to delegate each ready task (per its
`depends_on` level). Tasks at the same level can run in parallel.
"""


# ---------------------------------------------------------------------------
# get_supervisor_function_tools
# ---------------------------------------------------------------------------


def get_supervisor_function_tools() -> list[Any]:
    """Return the two ledger-management FunctionTool instances.

    Resolves ``set_todo_list`` and ``update_todo_list`` from the
    function-tool registry.  The registration side-effect fires when
    ``app.adk.tools.todo_list_tools`` is imported; ``hierarchy.py`` imports
    that module at the top level, so the registry is populated before
    ``build_hierarchy`` calls this function.

    Returns:
        List of exactly two ``FunctionTool`` objects in the order
        ``[set_todo_list, update_todo_list]``.  Returns an empty list if
        either tool is not registered (logs a warning per tool).
    """
    import logging

    from app.adk.tools.registry.function_tool_registry import get_function_tool

    _log = logging.getLogger(__name__)

    tools: list[Any] = []
    for name in ("set_todo_list", "update_todo_list"):
        tool = get_function_tool(name)
        if tool is None:
            _log.warning(
                "Supervisor function tool %r is not registered; "
                "import app.adk.tools.todo_list_tools before calling "
                "get_supervisor_function_tools().",
                name,
            )
        else:
            tools.append(tool)
    return tools
