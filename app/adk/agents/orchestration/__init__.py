"""Supervisor-orchestration package for AH-PRD-05.

Re-exports the public surface of ``supervisor.py`` so callers can use the
short form ``from app.adk.agents.orchestration import compute_dependency_levels``.
"""

from app.adk.agents.orchestration.supervisor import (
    BRANCH_ERROR_SENTINEL_PREFIX,
    MAX_LEDGER_ITEMS,
    SUPERVISOR_INSTRUCTION_FRAGMENT,
    compute_dependency_levels,
    get_supervisor_function_tools,
    make_branch_failure_sentinel_after_agent_callback,
    mark_branch_failure,
    select_ready_tasks,
    validate_ledger,
    wrap_task_in_review,
)

__all__ = [
    "BRANCH_ERROR_SENTINEL_PREFIX",
    "MAX_LEDGER_ITEMS",
    "SUPERVISOR_INSTRUCTION_FRAGMENT",
    "compute_dependency_levels",
    "get_supervisor_function_tools",
    "make_branch_failure_sentinel_after_agent_callback",
    "mark_branch_failure",
    "select_ready_tasks",
    "validate_ledger",
    "wrap_task_in_review",
]
