"""Per-turn root-agent tool and sub-agent reconciler (AH-100 + AH-116).

Extends the per-turn specialist sync pattern established by
:mod:`app.adk.agents.agent_factory.sub_agent_attacher` to the root agent's
``tools`` list **and** agent-as-tool ``sub_agents``.

Before AH-100, AH-98 wired ``build_hierarchy()`` to resolve ``ken_e_chatbot.
tool_ids`` **once at deploy time** via ``resolve_specialist_roster``. That
resolution is frozen into the deployed artifact; editing the Firestore doc
afterwards has no effect until the next ``make backend``. This module adds a
``before_agent_callback`` that re-evaluates ``tool_ids`` on every turn (within
the 60 s ``get_cached_merged_config`` TTL) and replaces ``root.tools`` when the
resolved list differs — the same hot-reload horizon admins expect for
``instruction`` and specialist edits.

AH-116 (ADK 2.0 agent-as-tool migration):
    On ADK 2.0, ``AgentTool.run_async`` discards inner sub-agent events
    (GitHub ``google/adk-python#3984``, OPEN) — so agent-as-tool entries
    wrapped as ``AgentTool`` lose their ``usage_metadata`` and trace steps.
    AH-114 migrated the registry so ``resolve_agent_subagents`` returns
    ``LlmAgent(mode='task')`` instances instead of ``AgentTool`` instances.

    AH-116 wires that into this per-turn reconciler:

    * After ``resolve_specialist_roster(...)`` returns, the resolved list is
      partitioned on ``isinstance(item, LlmAgent)``.  ``LlmAgent`` items
      (agent-as-tool entries) are reconciled into ``root.sub_agents`` via
      ``_reconcile_agent_subagents``; non-LlmAgent items continue to flow
      into ``root.tools`` via the existing ``[:]`` slice.
    * The reconcile is *name-scoped*: ``_reconcile_agent_subagents`` only
      touches names that the registry exposes as agent-as-tool catalogue
      entries — specialists pinned by ``attach_specialists_before_agent_callback``
      are passed through untouched.  The two callbacks are therefore
      complementary and may coexist in the same ``sub_agents`` list without
      interfering with each other.
    * The populated-guard (hash-hit early-return) is extended: it now requires
      ``root.tools`` to be non-empty OR at least one agent-as-tool sub_agent
      to be present, so a fresh per-turn ADK 2.0 clone (which starts with
      ``tools=[]`` AND empty sub_agents) still triggers a re-resolve.

ADK behaviour confirmation (google-adk==1.27.5 — AH-100 Task 1 spike):
    ``base_agent.run_async`` fires ``_handle_before_agent_callback`` *before*
    ``_run_async_impl`` (``base_agent.py:291``). ``_process_agent_tools`` reads
    ``agent.tools`` directly at LLM-request build time without a pre-invocation
    snapshot (``base_llm_flow.py:418-441``). Therefore a ``root.tools``
    replacement inside ``before_agent_callback`` IS honoured on the same turn.
    See ``tests/test_root_tools_attacher_adk_smoke.py`` for the static-proof
    and live-Runner confirmation tests.

ADK 2.0 re-validation (google-adk==2.0.0 — AH-108 Task 1 probe):
    ``Runner._run_node_async`` in ADK 2.0 creates a per-turn clone of the root
    agent via ``build_node().clone()``.  The ``before_agent_callback`` fires
    on the clone's invocation context (``_invocation_context.agent`` IS the
    clone), so mutating ``agent.tools`` inside the callback IS visible to
    ``_process_agent_tools`` on the same turn — the LLM request carries the
    injected tool declarations (Path 1 confirmed, probe PASSES).
    The clone is discarded after the turn; mutations do NOT propagate back to
    the original agent object.
    Two consistency cleanups apply (mirroring ``sub_agent_attacher.py``,
    AH-104 / AH-105):
    (a) In-place slice assignment ``root.tools[:] = resolved_tools`` so the
        list object identity is preserved (``sub_agent_attacher.py:398``).
    (b) Populated-guard: the hash-hit early-return also requires
        ``root.tools`` to be non-empty (or agent-as-tool sub_agents present)
        so a fresh per-turn clone (which starts with empty lists) still gets
        its surface resolved even when the config hash has not changed
        (``sub_agent_attacher.py:284``).

Per-process safety note (cf. ``sub_agent_attacher.py:48-51``):
    Agent Engine deploys one root instance per worker process. Mutating
    ``root.tools`` and ``root.sub_agents`` is therefore process-local. Because
    there is exactly one slot per process, the applied-config hash is a single
    process-global slot (``_applied_hash``) keyed to that live slot — NOT a
    per-account map, which would serve one account stale tools left in the
    shared slot by another account on the same worker (see ``_applied_hash``
    for the full rationale). Concurrent turns for the same account serialise
    via the per-account stripe lock inherited from
    ``specialist_runtime.block_lock_for``.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, cast

from google.adk.agents import BaseAgent, LlmAgent

from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError
from app.adk.agents.agent_factory.roster import (
    RosterCapExceededError,
    resolve_specialist_roster,
)
from app.adk.agents.agent_factory.specialist_runtime import block_lock_for
from app.adk.agents.utils.config_cache import get_cached_merged_config
from app.adk.tools.registry.agent_tool_registry import (
    resolve_agent_subagents,
    resolve_isolated_agent_tools,
)
from app.adk.tools.registry.tool_registry import get_default_registry
from shared.account_id_utils import validate_account_id

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.genai import types

logger = logging.getLogger(__name__)

# Single process-global slot: the content_hash of the ``MergedAgentConfig``
# currently reflected in ``root.tools``. There is exactly ONE ``root`` (and
# therefore one ``root.tools`` slot) per worker process, so the applied hash
# MUST be a single slot too — NOT keyed per account.
#
# A per-account map (the original AH-100 shape, mirrored from
# ``sub_agent_attacher``) serves stale tools when one worker handles multiple
# accounts sequentially:
#
#     turn 1  acct A (tool_ids=[X]) → miss → root.tools=[X], fp[A]=hashA
#     turn 2  acct B (tool_ids=[Y]) → miss → root.tools=[Y], fp[B]=hashB
#     turn 3  acct A (unchanged)    → fp[A] HIT → early return
#                                    → root.tools is still [Y]   ← A gets B's tools
#
# No concurrency needed; plain sequential interleaving on one process is enough.
# Keying the hash to the live ``root.tools`` slot instead makes any account
# switch (which changes the config hash) force a re-resolve — correct over fast.
# On a hit the resolver is skipped, so a no-op turn costs one comparison; and
# accounts that resolve to the same effective config (e.g. no overlay → global)
# share the slot and skip the re-resolve entirely.
#
# Residual concurrency note: a single shared ``root.tools`` mutated per turn is
# still racy across *concurrent* turns for different accounts (per-account
# stripe locks don't mutually exclude). That window is inherited from
# ``sub_agent_attacher`` (same shared-root shape) and tracked separately; this
# slot fixes the sequential stale read above, which needs no concurrency.
_applied_hash: str | None = None


def _reset_applied_hash_for_tests() -> None:
    """Reset the applied-hash slot.  For test isolation only."""
    global _applied_hash
    _applied_hash = None


def _hash_config(config: Any) -> str:
    """Return a sha256 hex digest of ``config``'s JSON representation.

    Duplicated locally from ``specialist_runtime._content_hash`` (the
    simple no-reviewer-model branch) so this module does not depend on a
    private symbol from a sibling module.
    """
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()


def _agent_subagent_names_present(root: LlmAgent, owned_names: set[str]) -> bool:
    """True iff ``root.sub_agents`` contains at least one agent-as-tool entry.

    Used by the populated-guard so a fresh per-turn ADK 2.0 clone with empty
    ``tools`` AND empty agent-as-tool sub_agents triggers a re-resolve even
    when the config hash has not changed (mirrors the ``root.tools`` leg of
    the guard at ``_attach_locked:240``).
    """
    return any(getattr(sub, "name", None) in owned_names for sub in root.sub_agents)


def _reconcile_agent_subagents(
    root: LlmAgent,
    desired_by_name: dict[str, LlmAgent],
    owned_names: set[str],
) -> bool:
    """Reconcile ``root.sub_agents`` for agent-as-tool entries only.

    Mirrors :func:`app.adk.agents.agent_factory.sub_agent_attacher._reconcile`
    but only operates on entries whose name is in *owned_names* (the set of
    names the registry exposes as agent-tool catalogue entries). Sub-agents
    managed by ``attach_specialists_before_agent_callback`` (i.e. names NOT in
    *owned_names*) are passed through untouched, preserving two-callback
    coexistence.

    Args:
        root: The root agent whose ``sub_agents`` list is reconciled in-place.
        desired_by_name: Mapping of ``{name: LlmAgent}`` that should be present
            under *owned_names* after the reconcile.
        owned_names: Set of bare agent-tool catalogue names (e.g.
            ``{"google_search", "numerical_analyst"}``).  Only entries in this
            set are touched; others are left alone.

    Returns:
        ``True`` if ``root.sub_agents`` was mutated; ``False`` if the reconcile
        pass was a no-op (every desired entry was already present with the same
        identity).
    """
    from app.adk.agents.agent_factory.sub_agent_attacher import (
        _clear_parent,
        _set_parent,
    )

    remaining_desired = dict(desired_by_name)  # copy so we can consume
    existing = list(root.sub_agents)
    changed = False
    keep: list[Any] = []

    for sub in existing:
        sub_name = getattr(sub, "name", None)
        if sub_name is None or sub_name not in owned_names:
            # Not an agent-as-tool entry — preserve untouched.
            keep.append(sub)
            continue
        wanted = remaining_desired.get(sub_name)
        if wanted is sub:
            # Same name, same instance — already correct.
            keep.append(sub)
            remaining_desired.pop(sub_name)  # consumed
        elif wanted is None:
            # No longer desired — drop and clear parent pointer.
            _clear_parent(sub, root)
            changed = True
        else:
            # Fresh instance (factory mints a new one each call) — drop old,
            # the new instance is added below via remaining_desired.
            _clear_parent(sub, root)
            changed = True

    for new_sub in remaining_desired.values():
        _set_parent(new_sub, root)
        keep.append(new_sub)
        changed = True

    if changed:
        root.sub_agents[:] = keep

    return changed


# ---------------------------------------------------------------------------
# Public helpers (mirroring sub_agent_attacher.attach_account_specialists)
# ---------------------------------------------------------------------------


def attach_root_tools(
    root_agent: BaseAgent,
    account_id: str | None,
) -> None:
    """Synchronise ``root_agent.tools`` with the current ``ken_e_chatbot.tool_ids``
    for ``account_id``.

    Idempotent: calling repeatedly with the same arguments is a no-op once the
    current config is reflected on the root agent.

    This function never raises. Every failure mode (Firestore outage,
    ``RosterCapExceededError``, unknown tool ID) logs at ERROR/WARNING and
    leaves ``root_agent.tools`` unchanged — the callback never blocks the turn.

    Args:
        root_agent: The deployed root ``BaseAgent`` whose ``tools`` will be
            reconciled.
        account_id: Per-account overlay key.  ``None`` means no account context
            (e.g. the first turn before ``account_id`` lands in session state);
            the global config is used in that case.  Unlike
            ``attach_account_specialists``, which returns early on ``None``
            (leaving sub_agents stable), this function continues to apply the
            global config on ``None`` so the root always starts with a resolved
            tool list from the first turn.
    """
    if not _has_tools_attr(root_agent):
        logger.error(
            "[ATTACH-ROOT-TOOLS] root_agent %r has no tools attribute; skipping.",
            getattr(root_agent, "name", "<unnamed>"),
        )
        return

    validated_account_id: str | None = None
    if account_id is not None:
        try:
            validated_account_id = validate_account_id(account_id)
        except ValueError:
            logger.warning(
                "[ATTACH-ROOT-TOOLS] Invalid account_id %r in session state; "
                "using global config.",
                account_id,
            )
            validated_account_id = None

    # Use ``None`` as the lock key for no-account turns so they serialise on
    # the same stripe without using a synthetic string key that could theoretically
    # collide with a valid account ID ("global" matches [a-zA-Z0-9_-]{1,128}).
    with block_lock_for(validated_account_id):
        _attach_locked(root_agent, validated_account_id)


def _attach_locked(
    root_agent: BaseAgent,
    account_id: str | None,
) -> None:
    """Critical section of :func:`attach_root_tools`.

    Caller holds the per-account (or ``None``-keyed) stripe lock.
    """
    global _applied_hash

    # ``root_agent`` is always the LlmAgent root (``attach_root_tools`` guards
    # with ``_has_tools_attr``); narrow it so mypy sees ``tools``, which lives
    # on ``LlmAgent`` rather than ``BaseAgent``.
    root = cast("LlmAgent", root_agent)

    # 1. Fetch the cached merged config (same source as the InstructionProvider).
    try:
        config = get_cached_merged_config("ken_e_chatbot", account_id, ttl_seconds=60)
    except FirestoreConnectionError as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] Firestore error fetching root config (account=%r): %s",
            account_id,
            exc,
        )
        return
    except Exception as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] Unexpected error fetching root config "
            "(account=%r): %s",
            account_id,
            exc,
            exc_info=True,
        )
        return

    # 2. Collect agent_tool_names from the in-memory registry (cheap — no I/O).
    #    Used by the populated-guard and the name-scoped reconcile below.
    _registry = get_default_registry()
    agent_tool_names: set[str] = {t.name for t in _registry.list_agent_tools()}

    # 3. Applied-hash check: skip the full resolve when both ``root.tools`` and
    #    agent-as-tool sub_agents already reflect this exact config version.
    #    Single global slot (see ``_applied_hash``): an account switch changes
    #    ``content_hash`` and forces a re-resolve so one account never serves
    #    another's surface from the shared slot.
    #
    #    ADK 2.0 populated-guard (extended from AH-108 to cover sub_agents):
    #    On ADK 2.0, Runner clones the root agent per turn; the clone starts
    #    with ``tools=[]`` AND empty ``sub_agents``. Without the guard a hash
    #    hit would early-return and leave the clone with an empty surface.
    #    Requiring ``root.tools`` to be non-empty OR an agent-as-tool sub_agent
    #    to be present forces a re-resolve on any freshly-cloned turn.
    content_hash = _hash_config(config)
    if _applied_hash == content_hash and (
        root.tools or _agent_subagent_names_present(root, agent_tool_names)
    ):
        return  # No-op: root surface already reflects this config version.

    # 4. Resolve the tool list via the shared roster resolver.
    #    Uses the same call AH-98's build_hierarchy performs so the ≤30-tool
    #    cap, agent-tool opt-in semantics, and registry resolution are identical
    #    at deploy-time and at runtime.
    #    AH-116: resolve_agent_subagents returns task-mode LlmAgent instances
    #    (not AgentTool); the partition below routes them to sub_agents.
    try:
        _roster = resolve_specialist_roster(
            "ken_e",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_subagents=resolve_agent_subagents(_registry),
            # AH-PRD-15 re-plan: isolated AgentTools (google_search /
            # numerical_analyst) flow into ``.tools`` and are reconciled onto
            # ``root.tools`` below as regular tools — no ``_TaskAgentTool``.
            isolated_agent_tools=resolve_isolated_agent_tools(_registry),
            tool_ids=getattr(config, "tool_ids", None),
            registry=_registry,
        )
    except RosterCapExceededError as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] RosterCapExceededError for root config "
            "(account=%r): %s — root surface unchanged; applied hash NOT updated.",
            account_id,
            exc,
        )
        # Do NOT update the applied hash so the next turn retries.
        return
    except Exception as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] Unexpected error resolving root tools "
            "(account=%r): %s — root surface unchanged; applied hash NOT updated.",
            account_id,
            exc,
            exc_info=True,
        )
        return

    # 5. AH-116 + AH-115: RosterResolution already separates non-agent tools
    #    from task-mode LlmAgent sub_agents — no partition needed.
    #    LlmAgent items live in sub_agents so ADK 2.0 auto-injects
    #    request_task_<name> on the LLM call; non-LlmAgent items are regular
    #    tools (MCP toolsets, function tools) that continue to live in root.tools.
    #    AH-133: supervisor function tools are appended AFTER the roster resolve
    #    so they bypass the admin tool_ids filter and remain platform-invariant
    #    across every per-turn reconcile (mirrors the build-time pattern in
    #    hierarchy.py).
    #    Registry identity: _REGISTRY stores one FunctionTool singleton per name.
    #    _tools_equal uses identity (is) comparison, so if root.tools already
    #    holds the same instances the slice assignment is skipped — no
    #    accumulation.  A module reload replaces the registry entries, causing
    #    a fresh identity-miss and a correct re-resolve.
    from app.adk.agents.orchestration.supervisor import get_supervisor_function_tools

    resolved_non_agent: list[Any] = (
        list(_roster.tools) + get_supervisor_function_tools()
    )
    agent_subs_desired: dict[str, LlmAgent] = {
        sub.name: sub for sub in _roster.sub_agents if sub.name is not None
    }

    # 6. Reconcile agent-as-tool sub_agents (name-scoped; specialists untouched).
    #    This sets parent pointers and keeps root.sub_agents in sync; it does NOT
    #    touch root.tools (step 7 owns the full tools list).
    _reconcile_agent_subagents(root, agent_subs_desired, agent_tool_names)

    # 7. Rebuild root.tools = resolved non-agent tools + a ``_TaskAgentTool`` for
    #    every task-mode sub-agent now present in root.sub_agents (AH-117).
    #    ADK injects these delegation tools ONLY in ``LlmAgent.model_post_init``,
    #    which never re-runs on the per-turn clone, so attaching a task-mode
    #    sub-agent post-construction leaves the parent with no dispatchable tool:
    #    ``canonical_tools`` / ``_extract_task_delegation_fcs`` read it from
    #    ``root.tools`` alone, so without this the LLM never sees
    #    ``request_task_<name>`` and the delegation (plus its billing) never
    #    fires. We wrap whatever instance the reconcile placed in
    #    ``root.sub_agents`` so the tool and the executable sub-agent stay
    #    consistent. Identity comparison (``is``) detects the fingerprint-miss
    #    case; equality (``==``) would be unreliable for ADK tool objects without
    #    a defined __eq__.
    from app.adk.agents.agent_factory.sub_agent_attacher import (
        _make_task_agent_tool,
    )

    desired_tools: list[Any] = list(resolved_non_agent)
    for sub in root.sub_agents:
        if getattr(sub, "name", None) in agent_subs_desired:
            task_tool = _make_task_agent_tool(sub)
            if task_tool is not None:
                desired_tools.append(task_tool)

    current_tools: list[Any] = list(root.tools)
    if not _tools_equal(current_tools, desired_tools):
        root.tools[:] = desired_tools
        logger.debug(
            "[ATTACH-ROOT-TOOLS] root.tools reconciled (account=%r): "
            "%d → %d tool(s) (incl. %d task-mode delegation tool(s)).",
            account_id,
            len(current_tools),
            len(desired_tools),
            len(desired_tools) - len(resolved_non_agent),
        )

    _applied_hash = content_hash


def _tools_equal(a: list[Any], b: list[Any]) -> bool:
    """True iff ``a`` and ``b`` carry the same tools in the same order.

    Comparison is by identity (``is``) for ADK tool objects that may not
    implement ``__eq__``. Two lists are equal when they have the same length
    and every corresponding element is the same object.
    """
    if len(a) != len(b):
        return False
    return all(x is y for x, y in zip(a, b, strict=False))


def _has_tools_attr(obj: Any) -> bool:
    """True iff *obj* exposes a mutable ``tools`` list-like attribute."""
    tools = getattr(obj, "tools", None)
    return isinstance(tools, list)


# ---------------------------------------------------------------------------
# ADK before_agent_callback bridge
# ---------------------------------------------------------------------------


def attach_root_tools_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Root ``before_agent_callback`` that syncs ``root.tools`` per turn.

    Designed to be passed to :func:`build_agent` via
    ``additional_before_agent_callbacks=[..., attach_root_tools_before_agent_callback, ...]``.

    Reads ``account_id`` from ``callback_context.state`` and calls
    :func:`attach_root_tools` against the root agent. Always returns ``None``
    so the agent proceeds normally. Errors are swallowed — a resolver failure
    must not block the turn.
    """
    try:
        account_id: str | None = callback_context.state.get("account_id")
        # ``_invocation_context`` is a private ADK attribute with no public
        # accessor for the executing agent in the pinned version; see the
        # ADK-version caveat in
        # ``sub_agent_attacher.attach_specialists_before_agent_callback``. This
        # callback is only attached to the root, so the agent on the invocation
        # context IS the root.
        # ADK 2.0: `_invocation_context.agent` now has type `BaseNode | None`
        # because `BaseAgent` is a subtype of `BaseNode`; cast to `BaseAgent`
        # because this callback is only wired onto the root (a `BaseAgent`).
        root_agent = cast(BaseAgent, callback_context._invocation_context.agent)
        attach_root_tools(root_agent, account_id)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "[ATTACH-ROOT-TOOLS] before_agent_callback raised unexpectedly; "
            "root.tools for this turn may be stale. %s",
            exc,
        )
    return None
