"""Supervisor-orchestration utilities for AH-PRD-05.

Consumed by the root coordinator when it decomposes a multi-specialist user
request into a TODO ledger and manages approval checkpoints.

Public surface:
  - ``compute_dependency_levels(items)`` — Kahn topological sort over the
    ``depends_on`` DAG; returns a list-of-id-lists partitioned by depth or
    an ``"ERROR: ..."`` string on cycle / dangling ref.
  - ``validate_ledger(items, known_specialist_ids, max_items)`` — composes
    the three validation checks (cap, unknown specialist, cycle/dangling-dep).
  - ``select_ready_tasks(items, completed_ids)`` — returns the sorted list of
    ``item_id``s that are ready to dispatch right now (deps satisfied, status
    pending).  AH-141.
  - ``BRANCH_ERROR_SENTINEL_PREFIX`` — prefix string for branch-failure
    sentinel values written to ``result_key`` in session state.  AH-141.
  - ``mark_branch_failure(state, result_key, error_message)`` — writes the
    sentinel to ``state[result_key]`` when a branch fails.  AH-141.
  - ``make_branch_failure_sentinel_after_agent_callback(specialist_name)`` —
    returns an ``after_agent_callback`` that fires on a task-mode specialist
    and writes the sentinel when ``result_key`` is absent from state.
    Imported by ``specialist_runtime._build_specialist``.  AH-141.
  - ``MAX_LEDGER_ITEMS`` — soft cap constant (12).
  - ``SUPERVISOR_INSTRUCTION_FRAGMENT`` — Markdown string fragment spliced
    into the root agent's instruction suffix by ``hierarchy.py``.
  - ``wrap_task_in_review(specialist, criteria, result_key)`` — optionally
    wraps a ``mode='task'`` specialist in a ``LoopAgent`` review pipeline when
    ``criteria`` is non-empty; returns the specialist unchanged for empty/None
    criteria (single-pass path).
  - ``pending_supervisor_state_provider(ctx)`` — reads
    ``session.state["pending_supervisor_tasks"]`` and returns a Markdown block
    for the coordinator's prompt when a checkpoint is pending.  Reads ctx.state.
  - ``get_supervisor_function_tools()`` — returns the five ledger-management
    and approval-checkpoint ``FunctionTool`` instances needed by the coordinator.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent, LlmAgent

MAX_LEDGER_ITEMS: int = 12

# Sentinel prefix written to result_key when a branch fails (AH-141).
BRANCH_ERROR_SENTINEL_PREFIX: str = "ERROR: "

# Ledger list_id + terminal statuses for the transfer_to_agent guard (AH-160).
SUPERVISOR_LEDGER_LIST_ID: str = "supervisor_ledger"
_TERMINAL_LEDGER_STATUSES: frozenset[str] = frozenset({"completed", "failed"})

_log = logging.getLogger(__name__)

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

    queue: deque[str] = deque(iid for iid in all_ids if in_degree[iid] == 0)
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
# select_ready_tasks (AH-141)
# ---------------------------------------------------------------------------


def select_ready_tasks(
    items: list[dict[str, Any]],
    completed_ids: set[str],
) -> list[str]:
    """Return sorted ``item_id``s that are ready to dispatch right now.

    A task is ready when ALL of:
    - Its ``depends_on`` set is a subset of ``completed_ids``.
    - Its ``status`` is ``"pending"`` (missing ``status`` is treated as
      ``"pending"``; any other value — ``"completed"``, ``"dispatched"``,
      ``"awaiting_review"``, ``"failed"`` — excludes the task).

    Args:
        items: List of TODO-ledger dicts.  Each may carry ``item_id``
            (str), ``depends_on`` (list[str] | None), and ``status`` (str).
        completed_ids: Set of ``item_id``s whose work is already done.

    Returns:
        Sorted list of ``item_id`` strings — deterministic output.
        Returns ``[]`` on empty input.
    """
    _PENDING_STATUS = "pending"
    ready: list[str] = []
    for item in items:
        item_id: str = item.get("item_id", "")
        if not item_id:
            continue
        status: str = item.get("status") or _PENDING_STATUS
        if status != _PENDING_STATUS:
            continue
        deps: list[str] = list(item.get("depends_on") or [])
        if set(deps).issubset(completed_ids):
            ready.append(item_id)
    return sorted(ready)


# ---------------------------------------------------------------------------
# mark_branch_failure (AH-141)
# ---------------------------------------------------------------------------


def mark_branch_failure(
    state: dict[str, Any],
    result_key: str,
    error_message: str,
) -> None:
    """Write a branch-failure sentinel to ``state[result_key]``.

    Semantics:
    - Writes ``f"{BRANCH_ERROR_SENTINEL_PREFIX}{error_message}"`` when
      ``result_key`` is absent from state (no real result to protect).
    - Overwrites an existing sentinel-prefixed value (last-writer-wins on
      repeated failures; the new reason replaces the old one).
    - Is a no-op when ``state[result_key]`` already holds a non-sentinel
      value (real result preserved — never overwrite a good result).
    - Mutates ``state`` in place; returns ``None``.
    - Is idempotent w.r.t. the final state when called with the same
      ``error_message`` twice.

    Args:
        state: Mutable session-state dict (``callback_context.state`` or a
            plain ``dict`` in tests).
        result_key: The key whose value advertises the branch outcome to the
            coordinator.
        error_message: Human-readable reason for the failure.  Combined with
            ``BRANCH_ERROR_SENTINEL_PREFIX`` to form the sentinel string.
    """
    existing = state.get(result_key)
    if existing is not None and not str(existing).startswith(
        BRANCH_ERROR_SENTINEL_PREFIX
    ):
        # Real result is already present — preserve it.
        return
    state[result_key] = f"{BRANCH_ERROR_SENTINEL_PREFIX}{error_message}"


# ---------------------------------------------------------------------------
# make_branch_failure_sentinel_after_agent_callback (AH-141)
# ---------------------------------------------------------------------------


def make_branch_failure_sentinel_after_agent_callback(
    specialist_name: str,
) -> Any:
    """Return an ``after_agent_callback`` that writes a sentinel on branch failure.

    The callback is wired onto task-mode specialist ``LlmAgent`` instances by
    ``specialist_runtime._build_specialist`` (AH-141).  It fires after the
    specialist completes (successfully or not) and checks whether its
    ``result_key`` was written.  If absent, it writes the sentinel via
    ``mark_branch_failure``.

    Matching logic: the callback walks ``state["todo_lists"]["supervisor_ledger"]``
    (if present) looking for the first item whose ``assignee == specialist_name``
    AND whose ``status`` is not in ``{"completed", "failed"}``.  This identifies
    the in-flight ledger item for this branch so the correct ``result_key``
    receives the sentinel.

    No-op semantics:
    - When no ``supervisor_ledger`` is in ``state["todo_lists"]`` (single-
      specialist ``transfer_to_agent`` turns are unaffected — AH-145 regression
      guard).
    - When no matching in-flight item is found.
    - When ``result_key`` already holds a non-sentinel value (real result).
    - Defensive ``try/except`` around all state reads so a malformed ledger
      never crashes the turn.

    Args:
        specialist_name: ``doc_id`` of the task-mode specialist being built.
            Used to match the ``assignee`` field in the ledger.

    Returns:
        A synchronous callable with the signature
        ``(callback_context: Any) -> None`` suitable for ADK's
        ``after_agent_callback``.
    """
    _TERMINAL_STATUSES = {"completed", "failed"}

    def _sentinel_callback(callback_context: Any) -> None:
        try:
            state_obj = getattr(callback_context, "state", None)
            if state_obj is None:
                return
            # Read via to_dict() for safe iteration; write via __setitem__ on the
            # live proxy so the session state is actually mutated (not just a copy).
            if hasattr(state_obj, "to_dict"):
                state_view: dict[str, Any] = state_obj.to_dict()
            elif isinstance(state_obj, dict):
                state_view = state_obj
            else:
                state_view = dict(state_obj)

            todo_lists = state_view.get("todo_lists")
            if not todo_lists:
                return
            ledger_items = todo_lists.get("supervisor_ledger")
            if not ledger_items:
                return

            # Find the first in-flight item assigned to this specialist.
            for item in ledger_items:
                if item.get("assignee") != specialist_name:
                    continue
                if item.get("status") in _TERMINAL_STATUSES:
                    continue
                result_key: str | None = item.get("result_key")
                if not result_key:
                    continue
                # Read `existing` from the live proxy (not the snapshot) to close
                # the TOCTOU window: a concurrent branch may write the real result
                # between the to_dict() snapshot and this write.
                if isinstance(state_obj, dict):
                    existing = state_obj.get(result_key)
                elif hasattr(state_obj, "get"):
                    existing = state_obj.get(result_key)
                else:
                    existing = state_view.get(result_key)

                if existing is None or str(existing).startswith(
                    BRANCH_ERROR_SENTINEL_PREFIX
                ):
                    sentinel = (
                        f"{BRANCH_ERROR_SENTINEL_PREFIX}specialist {specialist_name!r} "
                        f"completed without writing {result_key!r}"
                    )
                    # Write via the live state proxy (ADK StateProxy has __setitem__).
                    if isinstance(state_obj, dict):
                        state_obj[result_key] = sentinel
                    elif hasattr(state_obj, "__setitem__"):
                        state_obj[result_key] = sentinel
                break
        except Exception:
            _log.warning(
                "branch_failure_sentinel_callback: could not write sentinel for specialist %r; "
                "branch failure may not be detected by the coordinator.",
                specialist_name,
                exc_info=True,
            )

    return _sentinel_callback


# ---------------------------------------------------------------------------
# transfer_to_agent ledger guard (AH-160)
# ---------------------------------------------------------------------------

_TRANSFER_TOOL_NAME: str = "transfer_to_agent"


def _extract_ledger_items(state: Any) -> list[dict[str, Any]]:
    """Return the ``supervisor_ledger`` items from session state, or ``[]``.

    Reads ``state["todo_lists"]["supervisor_ledger"]["items"]`` — the shape
    written by ``set_todo_list`` in ``todo_list_tools.py``.  Defensive against a
    bare-list legacy value and any non-dict/non-list garbage so a malformed
    ledger never raises in the ``before_tool_callback`` hot path.

    Args:
        state: ADK session-state proxy (``to_dict()`` / ``.get()``) or a plain
            ``dict`` in tests.

    Returns:
        List of item dicts (possibly empty).
    """
    try:
        if hasattr(state, "to_dict"):
            view: Any = state.to_dict()
        elif isinstance(state, dict):
            view = state
        elif hasattr(state, "get"):
            view = state
        else:
            return []
        todo_lists = view.get("todo_lists")
        if not isinstance(todo_lists, dict):
            return []
        entry = todo_lists.get(SUPERVISOR_LEDGER_LIST_ID)
        if isinstance(entry, dict):
            items = entry.get("items")
        elif isinstance(entry, list):
            items = entry
        else:
            return []
        return [it for it in (items or []) if isinstance(it, dict)]
    except Exception:
        return []


def has_active_supervisor_ledger(state: Any, *, min_items: int = 2) -> bool:
    """Return ``True`` when an in-execution multi-task supervisor ledger exists.

    "Active" means the ``supervisor_ledger`` carries at least ``min_items``
    items AND at least one item is NOT in a terminal status
    (``completed`` / ``failed``; a missing status is treated as ``pending``).
    A ledger whose items are all terminal — a finished prior-turn workflow — is
    NOT active, so a later single-specialist ``transfer_to_agent`` is unaffected.
    The single-specialist fast path writes no ledger at all, so it never trips
    this check.

    Args:
        state: ADK session-state proxy or plain ``dict``.
        min_items: Minimum item count to qualify as a multi-task ledger
            (default 2; a degenerate 1-item ledger does not count).

    Returns:
        ``True`` iff a multi-task ledger with at least one non-terminal item is
        present.
    """
    items = _extract_ledger_items(state)
    if len(items) < min_items:
        return False
    return any(
        (it.get("status") or "pending") not in _TERMINAL_LEDGER_STATUSES for it in items
    )


async def transfer_to_agent_ledger_guard_before_tool_callback(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
) -> dict[str, Any] | None:
    """ADK ``before_tool_callback``: forbid ``transfer_to_agent`` during ledger execution.

    AH-160.  ``transfer_to_agent`` is one-way — once the coordinator has written
    a multi-item ``supervisor_ledger`` it MUST drive execution via the task-mode
    delegation tools (each named after the specialist's ``doc_id``) so control
    returns after each task.  Fan-out
    (AH-141), synthesis, and the spend-approval checkpoint (AH-144) all depend on
    the coordinator keeping control.  The coordinator LLM has been observed
    rationalising a single ``transfer_to_agent`` instead (PR-evidence: AH-160) —
    the instruction fragment forbids it, but prose is not a hard guarantee.  This
    callback is the deterministic guard.

    Behaviour:
    * Returns ``None`` (allow) for every tool other than ``transfer_to_agent``.
    * Returns ``None`` (allow) for ``transfer_to_agent`` when no active multi-item
      ledger exists — the single-specialist fast path (AH-145) is untouched.
    * When an active multi-item ledger IS present, returns a blocking error dict.
      ADK feeds that dict back to the model as the tool result, so the coordinator
      re-plans and dispatches by calling the specialist's ``doc_id``-named tool
      in the same turn.

    Args:
        tool: The ADK ``BaseTool`` about to run (``.name`` inspected).
        args: The tool-call arguments (``agent_name`` read for the log line).
        tool_context: ADK ``ToolContext``; ``.state`` is read.  A context without
            a usable ``state`` degrades open (returns ``None``).

    Returns:
        ``None`` to allow execution; a blocking ``dict`` (``error`` / ``message``)
        to reject the transfer.
    """
    if getattr(tool, "name", "") != _TRANSFER_TOOL_NAME:
        return None

    state = getattr(tool_context, "state", None)
    if state is None:
        return None
    if not has_active_supervisor_ledger(state):
        return None

    target = args.get("agent_name") if isinstance(args, dict) else None
    _log.info(
        "AH-160: blocked transfer_to_agent(agent_name=%r) — active multi-task "
        "supervisor_ledger present; steering coordinator to the specialist's "
        "doc_id-named delegation tool.",
        target,
    )
    return {
        "error": "transfer_to_agent_disabled_during_supervisor_ledger",
        "message": (
            "transfer_to_agent is disabled while a multi-task supervisor_ledger "
            "is active. transfer_to_agent is one-way and would hand off control "
            "before the remaining ledger tasks run — breaking parallel fan-out, "
            "synthesis, and the approval checkpoint. Dispatch each ready task by "
            "calling its assignee's delegation tool instead — the tool whose name "
            "is the specialist's doc_id (e.g. google_analytics_specialist), one "
            "FunctionCall per ready task in the same turn. Only fall back to "
            "transfer_to_agent for a single-task, no-ledger query."
        ),
    }


# ---------------------------------------------------------------------------
# SUPERVISOR_INSTRUCTION_FRAGMENT
# ---------------------------------------------------------------------------

SUPERVISOR_INSTRUCTION_FRAGMENT: str = """\
## Multi-Task Decomposition

You are an `LlmAgent(mode='chat')` coordinator. Each available specialist is
exposed to you as a **delegation tool whose name is exactly the specialist's
`doc_id`** (e.g. a tool literally named `google_analytics_specialist`). Calling
that tool runs the specialist and **returns its result to you** — it is
call-and-return, so you keep control. Throughout this section, "**dispatch task T
to specialist S**" means: emit a `FunctionCall` whose **`name` is S's `doc_id`**
(for example `google_analytics_specialist`), with the task query in `args`. There
is **no** `request_task_<id>` tool — do NOT prefix the name; call the specialist's
`doc_id` directly. `transfer_to_agent` is NOT used for specialist dispatch.

### When to decompose

The trigger for the supervisor model is **how many steps the work takes and
whether it needs approval — NOT how many distinct specialists are involved.** A
request that takes multiple steps, or gates an irreversible action behind
approval, uses the supervisor model **even when one specialist would perform
every task** (e.g. several `google_analytics_specialist` tasks).

**Use the supervisor model** (write a `supervisor_ledger`, then dispatch each task
by calling its assignee's `doc_id`-named tool) when the request involves **any**
of:
- **Multiple distinct steps or phases** that must be tracked or sequenced — e.g.
  pull data → synthesize → recommend — **even if a single specialist performs them
  all**.
- A **synthesized result** built from two or more separate analyses or data pulls.
- Data or actions from **two or more different specialists**.
- A **spend-changing or irreversible action** that must be approved before
  execution (updating ad budgets, modifying campaigns, writing data). Approval
  gating is ONLY possible on the supervisor path — a bare specialist call cannot
  pause for approval without a ledger.

**Fast path** (no ledger, no supervisor machinery) ONLY when the request is a
**single self-contained step**: one specialist can fully answer it in one
delegation, there is no multi-step plan, and no approval gate. Call the
specialist's tool (named by its `doc_id`) directly (no ledger). This is the common
case (e.g. "what were my top traffic sources last week?") — do NOT write a ledger
for a single self-contained question.

> **Do not collapse a multi-step request into a single specialist call.**
> "One specialist can do all of it" is **not** a reason to skip the ledger. If the
> work has multiple steps or an approval gate, you MUST write a `supervisor_ledger`
> and dispatch each task via its assignee's `doc_id`-named tool. Handing the whole
> multi-step request to one specialist without a ledger loses synthesis and approval
> checkpointing — the specialist cannot pause for approval or report back to you.

> **HARD RULE — never `transfer_to_agent` once a ledger exists.** `transfer_to_agent`
> is **one-way**: it hands the conversation to the specialist and you do **not** get
> control back, so the remaining tasks, the synthesis, and the approval checkpoint
> never run. `transfer_to_agent` is NOT for specialist dispatch at all (specialists
> are reachable only by calling their `doc_id`-named tool). The moment you have
> written a `supervisor_ledger`, you are committed to task-mode dispatch — you MUST
> dispatch every ready task by calling its assignee's `doc_id`-named tool, **even
> when all tasks share the same assignee** (e.g. several `google_analytics_specialist`
> tasks). "Only one specialist is involved" is **not** a reason to use
> `transfer_to_agent` once a multi-task ledger exists. The runtime enforces this: a
> `transfer_to_agent` call while a multi-task ledger is active is rejected, and you
> must re-dispatch by calling the specialist's `doc_id`-named tool.

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

### Dispatching ready tasks (parallel vs. sequential)

**Dispatch every ledger task by calling its assignee's `doc_id`-named tool —
never `transfer_to_agent`** (see the HARD RULE above).

After writing the ledger, determine the **ready group** for the current
dependency level — every task whose `depends_on` is fully satisfied AND whose
`status` is `"pending"`.

**Parallel group (two or more ready tasks):** emit **one FunctionCall per ready
task in the SAME turn, each named after that task's assignee `doc_id`**.  The
framework dispatches them concurrently via `ctx.run_node`.  Wait for the
function-response from every dispatched task before proceeding to the next
dependency level.

**Single ready task:** emit a single FunctionCall named after the assignee `doc_id`.

**Sequential tasks:** a task whose `depends_on` contains an `item_id` that is
not yet completed is NOT part of the current ready group — delegate it only
after all its upstream tasks have returned results.

**Partial-failure handling:** if a task returns a result that starts with
`ERROR: `, the branch failed.  Do NOT retry the failed task in this turn.
Proceed with the remaining ready tasks and surface partial results to the user.

#### Worked example — parallel fan-out

After writing the budget-optimisation ledger above, the coordinator emits
**two specialist-tool calls in the same turn** (each named after the assignee's
`doc_id`) to fan out `ga_engagement` and `meta_spend` in parallel (both have
`depends_on: []`):

```
# Turn 1 — parallel fan-out for the two root tasks (tool name == assignee doc_id):
google_analytics_specialist(query="Retrieve weekly engaged sessions...")
meta_ads_specialist(query="Retrieve last-4-week spend...")

# Both respond; then the coordinator emits the next ready task (synthesis):
# Turn 2 — sequential: synthesis depends on both root tasks:
google_analytics_specialist(query="Using {ga_result} and {meta_result}...")
```

### Approval Checkpoints

When the next ready task has `"requires_approval"` in its `criteria`, **do
NOT dispatch it**.  Instead:

1. Call `save_pending_supervisor_tasks(remaining=[...], completed_results={...})`
   where `remaining` is the list of tasks not yet executed (including the
   approval-required task) and `completed_results` maps each completed task's
   `result_key` to its output value.
2. Return a conversational approval request to the user that summarises exactly
   what will happen if approved (e.g. which campaigns will have their budgets
   increased and by how much).  Stop — do not call any specialist in this turn.

When the user's next turn indicates approval (e.g. "yes", "approved",
"go ahead"):

1. Call `resume_pending_supervisor_tasks()`.  The saved checkpoint is returned
   and the key is cleared in one call.
2. Parse the returned JSON.  Resume delegation from `remaining[0]` using the
   `completed_results` as the prior outputs already in context.

When the user rejects the pending workflow, changes the subject, or after a
resumed workflow completes (whether successful or failed):

1. Call `clear_pending_supervisor_tasks()`.

**Pending Supervisor Tasks section:** whenever a `## Pending Supervisor Tasks`
section appears in your prompt (injected by the instruction suffix), you MUST
address it before writing a fresh ledger.  If the user's message approves,
call `resume_pending_supervisor_tasks()` and continue.  If the user changes
topic or rejects, call `clear_pending_supervisor_tasks()` and proceed normally.
"""


# ---------------------------------------------------------------------------
# wrap_task_in_review
# ---------------------------------------------------------------------------


def wrap_task_in_review(
    specialist: LlmAgent,
    criteria: str | None,
    result_key: str,
) -> BaseAgent:
    """Optionally wrap a task-mode specialist in a Generator-Critic review loop.

    This helper bridges the ``TodoItem`` domain (supervisor-orchestration) to the
    generic ``build_review_pipeline()`` primitive.  It is a pure transform:

    * Empty / whitespace-only / ``None`` ``criteria`` → returns ``specialist``
      unchanged (single-pass delegation, no review loop).
    * Non-empty ``criteria`` → calls ``build_review_pipeline(specialist, criteria,
      output_key_prefix=result_key)``, renames the resulting ``LoopAgent`` to
      ``specialist.name`` and sets its ``description`` to ``specialist.description``,
      then returns the ``LoopAgent``.  This keeps the dispatch identifier stable
      (ADK's ``transfer_to_agent`` / ``attach_task_subagent`` locates agents by
      name) whether or not the review loop is active.

    The ``output_key_prefix=result_key`` convention (PRD §7 AC-4) means the
    worker writes to ``f"{result_key}_draft"`` and the reviewer writes to
    ``f"{result_key}_feedback"``, matching the session-state layout the
    coordinator reads when synthesizing results.

    Before calling ``build_review_pipeline``, ``criteria`` is truncated to
    ``MAX_CRITERIA_CHARS`` (2000 chars) and run through ``sanitise_criteria``
    to strip Unicode confusables, Bidi override marks, and invisible formatting
    characters — the same sanitization applied by ``specialist_runtime.py:860``
    and ``dispatch_handlers.py:101`` to prevent prompt structure injection.

    Callers are responsible for ``attach_task_subagent`` wiring and Weave-span
    callback attachment — this helper is a construction primitive only (mirrors
    the separation of ``_build_specialist`` from ``_wire_specialist_span_callbacks``
    in ``specialist_runtime.py:911-919``).

    Args:
        specialist: The ``mode='task'`` specialist to wrap.  Must have a string
            or callable ``instruction`` (requirement inherited from
            ``build_review_pipeline``).
        criteria: Acceptance criteria for the review loop.  ``None``, ``""``, or
            whitespace-only → single-pass (specialist returned unchanged).  A
            non-empty string is passed verbatim to ``build_review_pipeline``.
        result_key: Session-state key the coordinator reads for this task's
            output (e.g. ``"ga_result"``).  Used verbatim as
            ``output_key_prefix``.  Must satisfy the ``^[a-z][a-z0-9_]{0,63}$``
            pattern enforced by ``build_review_pipeline``; any ``result_key``
            accepted by ``_normalize_items`` in ``todo_list_tools.py`` satisfies
            that pattern.

    Returns:
        ``specialist`` (unchanged) when criteria is empty/None.
        A ``LoopAgent`` (with ``name == specialist.name`` and
        ``description == specialist.description``) when criteria is non-empty.

    Raises:
        TypeError / ValueError: propagated from ``build_review_pipeline`` on
            invalid inputs (e.g. ``result_key`` not matching the prefix pattern,
            sentinel tokens in criteria).
    """
    if not criteria or not criteria.strip():
        return specialist

    from app.adk.agents.utils.criteria_utils import (
        MAX_CRITERIA_CHARS,
        sanitise_criteria,
    )
    from app.adk.agents.utils.review_pipeline import build_review_pipeline

    if len(criteria) > MAX_CRITERIA_CHARS:
        criteria = criteria[:MAX_CRITERIA_CHARS]
    criteria = sanitise_criteria(criteria)

    pipeline = build_review_pipeline(
        specialist=specialist,
        acceptance_criteria=criteria,
        output_key_prefix=result_key,
    )
    pipeline.name = specialist.name
    pipeline.description = specialist.description
    return pipeline


# ---------------------------------------------------------------------------
# pending_supervisor_state_provider
# ---------------------------------------------------------------------------

_PROMPT_RESULT_VALUE_MAX_LEN: int = 500

# Sentinel tokens that must not appear in rendered fields — stripping prevents
# an adversarially-crafted specialist output from injecting a fake
# "## Pending Supervisor Tasks" block into the coordinator's prompt, which
# could cause it to execute unapproved spend-changing actions.
_PENDING_PROMPT_BLOCKED: tuple[str, ...] = (
    "## Pending Supervisor Tasks",
    "### Remaining Tasks",
    "### Completed Results",
)


def _sanitize_prompt_field(s: str, max_len: int = _PROMPT_RESULT_VALUE_MAX_LEN) -> str:
    """Strip control-token prefixes and truncate for safe prompt rendering.

    Defense-in-depth only, not a complete prompt-injection defense: it strips the
    specific ``_PENDING_PROMPT_BLOCKED`` headers this block emits, but a specialist
    output could still contain other authoritative-looking markdown (a different
    ``#`` heading, ``SYSTEM:`` lines, etc.). Acceptable because the rendered values
    come from KEN-E's own specialists — an internal trust boundary — not end users.
    """
    for token in _PENDING_PROMPT_BLOCKED:
        s = s.replace(token, "")
    if len(s) > max_len:
        s = s[:max_len] + "... [truncated]"
    return s


def pending_supervisor_state_provider(ctx: Any) -> str:
    """Return a Markdown summary of pending supervisor tasks for the coordinator.

    When ``session.state["pending_supervisor_tasks"]`` is set, returns a
    ``## Pending Supervisor Tasks (Awaiting Approval)`` block so the coordinator
    always sees the checkpoint in its prompt and cannot miss it.  When the key is
    absent, returns ``""`` (no prompt injection).

    Each completed-result value is truncated to
    ``_PROMPT_RESULT_VALUE_MAX_LEN`` characters with a ``"... [truncated]"``
    suffix to avoid prompt-bloat while still showing the coordinator the shape
    of the data it collected.

    Args:
        ctx: ADK context whose ``.state`` dict is read (or any object whose
            ``state`` attribute supports ``dict(state)`` / ``.get()``).

    Returns:
        Empty string when no pending checkpoint exists.
        Markdown block starting with ``## Pending Supervisor Tasks`` otherwise.
    """
    # Single source of truth for the key lives in todo_list_tools (the module
    # that owns save/resume/clear). Imported lazily to avoid the
    # tools↔orchestration import cycle (mirrors todo_list_tools' own lazy import
    # of validate_ledger).
    from app.adk.tools.todo_list_tools import _PENDING_SUPERVISOR_TASKS_KEY

    # ``ctx.state`` shape varies by ADK context type: a ``ReadonlyContext`` (the
    # instruction-suffix path this provider runs on) exposes a ``MappingProxyType``
    # that ``dict()`` casts cleanly, whereas a ``CallbackContext``/``ToolContext``
    # exposes ADK's ``State`` object, which has ``__getitem__`` but no
    # ``keys()``/``__iter__`` — ``dict(State)`` raises. Prefer ``to_dict()`` when
    # present (mirrors ``available_specialists_provider`` in
    # ``specialist_runtime.py``) so a future ADK release that aligns
    # ``ReadonlyContext.state`` with ``CallbackContext.state`` cannot silently drop
    # this spend-gating checkpoint block. A genuinely unreadable context still
    # degrades to "" — but loudly, since a vanished checkpoint is unsafe here.
    try:
        raw_state = ctx.state
        state: dict[str, Any] = (
            raw_state.to_dict() if hasattr(raw_state, "to_dict") else dict(raw_state)
        )
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "pending_supervisor_state_provider could not read ctx.state; "
            "rendering no checkpoint block this turn",
            exc_info=True,
        )
        return ""

    pending = state.get(_PENDING_SUPERVISOR_TASKS_KEY)
    if not pending or not isinstance(pending, dict):
        return ""

    remaining: list[dict[str, Any]] = pending.get("remaining") or []
    completed_results: dict[str, Any] = pending.get("completed_results") or {}
    saved_at: str = pending.get("saved_at", "")

    lines: list[str] = [
        "## Pending Supervisor Tasks (Awaiting Approval)",
        "",
    ]
    if saved_at:
        lines.append(f"_Saved at: {saved_at}_")
        lines.append("")

    if remaining:
        lines.append("### Remaining Tasks")
        for i, item in enumerate(remaining, start=1):
            # Sanitize all rendered fields to strip control-token prefixes that
            # could allow a specialist output to inject a fake pending-tasks block.
            item_id = _sanitize_prompt_field(str(item.get("item_id", f"item_{i}")), 128)
            title = _sanitize_prompt_field(str(item.get("text", "(no title)")), 256)
            assignee = _sanitize_prompt_field(
                str(item.get("assignee") or "(none)"), 128
            )
            depends_on = item.get("depends_on") or []
            dep_str = f", depends_on: {depends_on}" if depends_on else ""
            lines.append(f"{i}. `{item_id}` — {title} (assignee: {assignee}{dep_str})")
        lines.append("")

    if completed_results:
        lines.append("### Completed Results")
        for key, value in completed_results.items():
            safe_key = _sanitize_prompt_field(str(key), 128)
            safe_val = _sanitize_prompt_field(str(value))
            lines.append(f"- `{safe_key}`: {safe_val}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# get_supervisor_function_tools
# ---------------------------------------------------------------------------


def get_supervisor_function_tools() -> list[Any]:
    """Return the five ledger-management and approval-checkpoint FunctionTool instances.

    Resolves ``set_todo_list``, ``update_todo_list``,
    ``save_pending_supervisor_tasks``, ``resume_pending_supervisor_tasks``,
    and ``clear_pending_supervisor_tasks`` from the function-tool registry.
    The registration side-effect fires when ``app.adk.tools.todo_list_tools``
    is imported; ``hierarchy.py`` imports that module at the top level, so the
    registry is populated before ``build_hierarchy`` calls this function.

    Returns:
        List of up to five ``FunctionTool`` objects in the order
        ``[set_todo_list, update_todo_list, save_pending_supervisor_tasks,
        resume_pending_supervisor_tasks, clear_pending_supervisor_tasks]``.
        Returns tools that are registered; logs a warning per missing tool.
        AH-144 added save/resume/clear pending tools.
    """
    import logging

    from app.adk.tools.registry.function_tool_registry import get_function_tool

    _log = logging.getLogger(__name__)

    tools: list[Any] = []
    for name in (
        "set_todo_list",
        "update_todo_list",
        "save_pending_supervisor_tasks",
        "resume_pending_supervisor_tasks",
        "clear_pending_supervisor_tasks",
    ):
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
