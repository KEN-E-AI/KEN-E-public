"""Idempotent runtime attachment of resolved specialists to a root agent.

AH-75 / AH-PRD-09: the deploy-time factory is gone, but ADK's
``transfer_to_agent`` mechanism — the only ADK-native channel that
propagates a sub-agent's events to the outer Runner's stream — requires
candidate specialists to be reachable from ``root_agent`` via ``sub_agents``
at call time. This module bridges the runtime resolver
(:mod:`app.adk.agents.agent_factory.specialist_runtime`) and ADK's
sub-agent lookup so the resolvable-agent set stays in sync with the root's
"Available Specialists" prompt block per turn, without re-introducing the
deploy-time factory.

Invoked from the root agent's ``before_agent_callback`` so the
``sub_agents`` list is current by the time the LLM emits a
``transfer_to_agent(agent_name=...)`` call.

Behaviour:

* Lists every delegatable specialist for *account_id* via
  :func:`config_loader.list_account_agent_configs`, resolves each through
  :func:`specialist_runtime.resolve_agent` (LRU-cached;
  content-hash-keyed), and ensures each resolved ``BaseAgent`` appears in
  ``root_agent.sub_agents`` exactly once.

  Delegation gate: ``ken_e_sub_agent=True`` (AH-82).  The legacy
  ``visible_in_frontend`` flag is no longer used here; it governs
  Workflows-page UI visibility only.

* Reconcile pass: any entry already in ``root.sub_agents`` whose name does
  not match a currently visible specialist (e.g. the specialist was
  deleted in Firestore, or evicted from ``_specialists_cache`` after a
  config edit produced a fresh ``LlmAgent`` instance with the same name)
  is removed so ADK's transfer-target lookup matches the prompt block.

* Parent-agent invariant: ``BaseAgent.__set_parent_agent_for_sub_agents``
  runs only at construction (base_agent.py:611) and refuses to re-parent
  at that boundary. This module manages the invariant manually
  post-construction: if the resolved agent's ``parent_agent`` is ``None``
  or already points to *root_agent*, leave it alone; if it points
  somewhere else (only happens in test fixtures with multiple roots in
  one process), clear and re-set.

* Concurrency: wraps the work in the existing per-account stripe lock
  from ``specialist_runtime`` (:func:`block_lock_for`). Concurrent turns
  for the same account serialise; turns for different accounts do not
  contend.

Per-process safety: Agent Engine deploys one root instance per worker
process. Mutating ``root.sub_agents`` is therefore process-local. The
``_specialists_cache`` is also process-local, so cache eviction and
sub_agents reconcile stay in sync without distributed coordination.
"""

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from google.adk.agents import BaseAgent
from google.genai import types

# AH-117: ADK 2.0's task-delegation primitive. A chat-mode parent can only
# dispatch to a ``mode='task'`` sub-agent when a ``_TaskAgentTool`` for it is
# present in ``parent.tools`` — ADK creates that tool ONLY inside
# ``LlmAgent.model_post_init`` (llm_agent.py), and ``canonical_tools`` /
# ``_extract_task_delegation_fcs`` read it from ``parent.tools`` alone. Any path
# that attaches a task-mode sub-agent AFTER construction must therefore inject
# the tool itself (see :func:`attach_task_subagent`). Guarded import: the
# strategy deploy tree is frozen at ADK 1.34.x where this symbol is absent.
try:
    from google.adk.tools.agent_tool import _TaskAgentTool
except ImportError:  # pragma: no cover - ADK 1.34.x strategy deploy tree
    _TaskAgentTool = None  # type: ignore[assignment,misc]

from app.adk.agents.agent_factory.config_loader import (
    FirestoreConnectionError,
    MergedAgentConfig,
)
from app.adk.agents.agent_factory.model_routing import apply_model_location_env
from app.adk.agents.agent_factory.specialist_runtime import (
    _content_hash,
    block_lock_for,
    list_account_agent_configs_cached,
    resolve_agent,
    resolve_config,
)
from shared.account_id_utils import validate_account_id

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)


class AlwaysTrueSubAgentList(list):
    """A ``list`` subclass that is always truthy, even when empty.

    ADK 2.0 compatibility shim (AH-105 / AH-PRD-13 Foundation):

    ADK 2.0's ``Runner._run_node_async`` checks ``bool(self.agent.sub_agents)``
    on the **original** (pre-clone) root agent to decide whether to activate
    ``DynamicNodeScheduler``.  KEN-E's root is built with an empty ``sub_agents``
    list (specialists are attached per-turn by
    ``attach_specialists_before_agent_callback``), so without this shim the
    scheduler never activates on 2.0 — ``transfer_to_agent`` events are yielded
    but not dispatched, and specialist LLM events never reach the outer Runner
    stream (Chat/Billing token counts become zero).

    This subclass is assigned to ``root_agent.sub_agents`` immediately after the
    root agent is constructed in ``hierarchy.py``.  ``build_node().clone()``
    creates a fresh regular ``[]`` for each per-turn clone, which ``_reconcile``
    then populates in-place per turn via slice assignment (``sub_agents[:] =
    keep``).

    Inert on ADK 1.34.1:
    * ``_get_transfer_targets()`` iterates ``sub_agents`` — it never gates on
      ``bool(sub_agents)``.
    * ``BaseAgent.model_config`` has ``validate_assignment=False``, so assigning
      a ``list`` subclass is not coerced back to a plain ``list``; the mechanism
      works on both 1.34.1 and 2.0.

    Verified under ``.venv-adk2`` (google-adk==2.0.0): parity suite 24/24 with
    the shim; fails without it (Mode B total_billable=0).  See
    ``docs/spike-ah104-deploy-sandbox-weave.md`` §3.2 / §3.2.1.
    """

    def __bool__(self) -> bool:
        return True


# Single process-global slot: the (account_id, fingerprint) pair currently
# reflected in ``root.sub_agents`` — where ``fingerprint`` is the frozenset of
# (doc_id, content_hash) for the visible specialist set. There is exactly ONE
# ``root`` (and therefore one ``root.sub_agents`` slot) per worker process, so
# the applied state MUST be a single slot too — NOT keyed per account.
#
# A per-account map (the original shape) serves stale specialists when one
# worker handles multiple accounts sequentially:
#
#     turn 1  acct A (specialists SA) → miss → root.sub_agents=SA, fp[A]=FA
#     turn 2  acct B (specialists SB) → miss → root.sub_agents=SB, fp[B]=FB
#     turn 3  acct A (unchanged)      → fp[A] HIT → early return
#                                      → root.sub_agents is still SB  ← A delegates to B's agents
#
# No concurrency needed; plain sequential interleaving on one process is enough.
# Keying the applied state to the live ``root.sub_agents`` slot instead forces a
# re-resolve whenever the desired state differs from what is live — correct over
# fast. On a hit the resolver is skipped, so a no-op turn costs one comparison.
#
# Why the slot carries ``account_id`` and not just the fingerprint: a specialist
# instance binds its per-account MCP connection at *build* time
# (``_build_specialist`` pool_key = (server_id, account_id, creds_hash)) and is
# cached under (doc_id, account_id, content_hash). Two accounts with no
# per-account config overlay resolve a global specialist to a byte-identical
# ``MergedAgentConfig`` → identical content_hash → identical fingerprint, yet
# need distinct, account-bound instances. A fingerprint-only slot would HIT on
# that account switch and leave the previous account's credentialed specialist
# live — a cross-account leak (AH-102). Comparing the full (account_id,
# fingerprint) forces a reconcile on every account switch, even for a shared
# config. Single-account-per-process is unchanged: account_id is constant, so
# the comparison reduces to the fingerprint.
#
# Residual concurrency note: a single shared ``root.sub_agents`` mutated per
# turn is still racy across *concurrent* turns for different accounts (per-account
# stripe locks don't mutually exclude). That window is inherited from the
# shared-root shape and may warrant a separate design pass (per-turn sub-agent
# lists vs. mutating shared state). This slot fixes the sequential stale read
# above, which needs no concurrency.
#
# AH-100 (PR #805, commit f634f2ff) introduced the analogous ``_applied_hash``
# slot in ``root_tools_attacher.py``. This slot mirrors that single-slot pattern
# but additionally keys on account_id: root.tools are account-independent, so
# AH-100 may share the slot across same-config accounts; specialists carry
# per-account credentials and cannot.
_applied_state: tuple[str, frozenset[tuple[str, str]]] | None = None


def _reset_applied_state_for_tests() -> None:
    """Reset the applied-state slot.  For test isolation only."""
    global _applied_state
    _applied_state = None


def attach_account_specialists(
    root_agent: BaseAgent,
    account_id: str | None,
    session_state: Mapping[str, Any] | None = None,
) -> None:
    """Synchronise ``root_agent.sub_agents`` with the visible specialists for
    ``account_id``.

    Idempotent: calling repeatedly with the same arguments is safe and a
    no-op once the visible specialist set is reflected on the root.

    The function never raises; per-specialist resolution failures are
    logged and the failed specialist is omitted from ``sub_agents`` (the
    "Available Specialists" prompt block applies the same policy, so the
    prompt and the resolvable set agree).

    Args:
        root_agent: The deployed root agent whose ``sub_agents`` will be
            mutated. Must be a ``BaseAgent`` subclass with a mutable
            ``sub_agents`` attribute.
        account_id: Per-account overlay key. ``None`` (no account in
            session state) is treated as "no visible specialists" and
            simply runs a reconcile pass that drops any stale entries.
        session_state: Current ADK session state mapping.  Forwarded to
            ``resolve_agent`` → ``_build_specialist`` for Phase 3 (AH-62)
            creds-hash key computation.  ``None`` is treated as an empty
            mapping.
    """
    if not _has_sub_agents_attr(root_agent):
        logger.error(
            "[ATTACH-SPECIALISTS] root_agent %r has no sub_agents attribute; skipping.",
            getattr(root_agent, "name", "<unnamed>"),
        )
        return

    if account_id is None:
        # No account context — keep root.sub_agents stable. Don't reconcile
        # globally; multiple sessions may share the same root with different
        # account_ids over the process lifetime, and dropping every
        # sub_agent on a no-account turn would thrash the cache.
        return

    try:
        validated_account_id = validate_account_id(account_id)
    except ValueError:
        logger.warning(
            "[ATTACH-SPECIALISTS] Invalid account_id %r in session state; "
            "skipping attach.",
            account_id,
        )
        return

    with block_lock_for(validated_account_id):
        _attach_locked(root_agent, validated_account_id, session_state=session_state)


def _attach_locked(
    root_agent: BaseAgent,
    account_id: str,
    session_state: Mapping[str, Any] | None = None,
) -> None:
    """Critical section of :func:`attach_account_specialists`.

    Caller holds the per-account stripe lock.
    """
    global _applied_state

    try:
        doc_ids = list_account_agent_configs_cached(account_id)
    except FirestoreConnectionError as exc:
        logger.error(
            "[ATTACH-SPECIALISTS] Failed to list configs (account=%r): %s",
            account_id,
            exc,
        )
        return

    # Compute a fingerprint of (doc_id, content_hash) for all visible configs.
    # This is cheap — resolve_config is TTL-cached; the hash is a pure function
    # of the already-fetched config. If the applied slot already records this
    # (account_id, fingerprint) pair, root.sub_agents is already in sync for this
    # account and we can skip the full reconcile pass.
    #
    # Single global slot (see ``_applied_state``): the slot is compared as
    # (account_id, fingerprint), so an account switch forces a re-resolve even
    # when the fingerprint is identical (shared global config) — one account
    # never serves another's account-bound specialists from the shared slot.
    # Caller holds block_lock_for(account_id) which serialises same-account reads
    # and writes; CPython's GIL protects the single object-reference read/write
    # across accounts.
    visible_configs: dict[str, MergedAgentConfig] = {}
    for doc_id in doc_ids:
        try:
            config = resolve_config(doc_id, account_id)
            # AH-82: filter on the explicit delegation gate.
            # visible_in_frontend governs Workflows-page UI visibility only.
            if not config.ken_e_sub_agent:
                continue
            visible_configs[doc_id] = config
        except Exception as exc:
            logger.warning(
                "[ATTACH-SPECIALISTS] Could not resolve config %r (account=%r): %s",
                doc_id,
                account_id,
                exc,
                exc_info=True,
            )

    new_fingerprint: frozenset[tuple[str, str]] = frozenset(
        (doc_id, _content_hash(cfg)) for doc_id, cfg in visible_configs.items()
    )
    # ADK 2.0: a fresh per-turn clone has empty sub_agents; only skip reconcile
    # when root_agent.sub_agents is already populated, else the empty clone
    # never gets specialists even on a fingerprint hit.
    if _applied_state == (account_id, new_fingerprint) and root_agent.sub_agents:
        return

    desired: dict[str, BaseAgent] = {}
    for doc_id, _config in visible_configs.items():
        try:
            desired[doc_id] = resolve_agent(
                doc_id, account_id, session_state=session_state
            )
        except Exception as exc:
            # Mirror available_specialists_provider's policy: log and drop the
            # offender so the prompt block and the sub_agents set agree.
            logger.warning(
                "[ATTACH-SPECIALISTS] Could not resolve specialist %r (account=%r): %s",
                doc_id,
                account_id,
                exc,
                exc_info=True,
            )

    try:
        changed = _reconcile(root_agent, desired)
    except Exception:
        # Do not commit the fingerprint — an incomplete reconcile must be
        # retried on the next turn rather than silently treated as settled.
        logger.exception(
            "[ATTACH-SPECIALISTS] _reconcile raised unexpectedly (account=%r); "
            "fingerprint NOT committed.",
            account_id,
        )
        return
    # Only commit the slot for specialists that were successfully resolved so a
    # transient resolve_agent failure does not permanently suppress retry. The
    # next turn's comparison (for any account) sees the (account_id, fingerprint)
    # that is currently live in root.sub_agents.
    _applied_state = (
        account_id,
        frozenset(
            (doc_id, _content_hash(visible_configs[doc_id])) for doc_id in desired
        ),
    )

    # AH-75 (reviewer feedback): the "Available Specialists" prompt block is
    # cached for ~60 s by ``specialist_runtime._block_cache``. If a specialist
    # is dropped or replaced here mid-TTL, the cached block would still list
    # the stale name, the LLM could emit ``transfer_to_agent(agent_name=<stale>)``,
    # and ADK's ``find_agent`` would fail. Invalidate the cached block on any
    # change so the next instruction-provider call re-renders against the
    # current visible set. We hold the per-account stripe lock at the caller
    # (``attach_account_specialists``) — same lock that guards block-cache
    # writes — so this mutation is safe.
    if changed:
        # Imported here to avoid pulling specialist_runtime's full module into
        # the import graph at module load (this module is already imported by
        # hierarchy.py at the deploy-time top of the graph).
        from app.adk.agents.agent_factory.specialist_runtime import _block_cache

        _block_cache.pop(account_id, None)


def _reconcile(root_agent: BaseAgent, desired: dict[str, BaseAgent]) -> bool:
    """Mutate ``root_agent.sub_agents`` to match ``desired`` (keyed by name).

    Removes entries whose name is absent from *desired* OR whose current
    instance differs from the desired one (config-hash drift produced a
    fresh agent). Adds entries that are missing. Existing entries that
    match by identity are left alone — same agent, same parent pointer,
    no work.

    Returns:
        ``True`` if ``root_agent.sub_agents`` was mutated (an entry was
        dropped, replaced, or added); ``False`` if the reconcile pass was a
        no-op (every desired entry was already present with the same
        identity). Callers use the flag to decide whether downstream caches
        keyed on the sub_agents set need invalidation.
    """
    existing: list[BaseAgent] = list(root_agent.sub_agents)
    desired_by_name = dict(desired)
    changed = False

    keep: list[BaseAgent] = []
    for sub in existing:
        sub_name = getattr(sub, "name", None)
        if sub_name is None:
            keep.append(sub)
            continue
        wanted = desired_by_name.get(sub_name)
        if wanted is sub:
            # Same name, same instance — already correct.
            keep.append(sub)
            desired_by_name.pop(sub_name)  # consumed
        elif wanted is None:
            # Name no longer visible: drop. Clear parent pointer so a future
            # attach to the same name can succeed if the specialist returns.
            _clear_parent(sub, root_agent)
            changed = True
        else:
            # Name still visible but a fresh instance has replaced it
            # (content_hash drift on a config edit). Drop the stale, keep the
            # desired below.
            _clear_parent(sub, root_agent)
            changed = True

    # Add anything still in desired_by_name (either net-new or replaced).
    for new_sub in desired_by_name.values():
        _set_parent(new_sub, root_agent)
        keep.append(new_sub)
        changed = True

    # ADK 2.0: update IN-PLACE so the scheduler's model_copy() shallow-copy
    # holders (which share the list object) see the per-turn specialists via
    # find_agent().  Attribute reassignment would update the root's own
    # attribute but leave the shallow-copy holders with the original (empty)
    # list — transfer_to_agent lookups would then fail silently.
    root_agent.sub_agents[:] = keep
    return changed


def _set_parent(sub: BaseAgent, root_agent: BaseAgent) -> None:
    """Set ``sub.parent_agent`` to *root_agent*, tolerating prior parenting.

    BaseAgent enforces single-parenting only at construction (see
    :mod:`google.adk.agents.base_agent`); post-construction the field is a
    plain assignable attribute. Production has one root per process, so
    re-parenting only happens in test fixtures.
    """
    current = getattr(sub, "parent_agent", None)
    if current is root_agent:
        return
    if current is not None:
        logger.debug(
            "[ATTACH-SPECIALISTS] Re-parenting specialist %r from %r to %r",
            getattr(sub, "name", "<unnamed>"),
            getattr(current, "name", "<unnamed>"),
            getattr(root_agent, "name", "<unnamed>"),
        )
    sub.parent_agent = root_agent


def _clear_parent(sub: BaseAgent, root_agent: BaseAgent) -> None:
    """Clear ``sub.parent_agent`` if it currently points to *root_agent*.

    Used when removing *sub* from ``root_agent.sub_agents`` so a future
    attach (under any root) won't see a stale parent pointer.
    """
    if getattr(sub, "parent_agent", None) is root_agent:
        sub.parent_agent = None


def _has_sub_agents_attr(obj: Any) -> bool:
    """True iff *obj* exposes a mutable ``sub_agents`` list-like attribute."""
    sub_agents = getattr(obj, "sub_agents", None)
    return isinstance(sub_agents, list)


# ---------------------------------------------------------------------------
# AH-117: post-construction task-mode sub-agent attachment
#
# ADK injects the ``_TaskAgentTool`` (the marker that makes a chat-mode parent
# able to dispatch ``request_task_<name>`` to a ``mode='task'`` sub-agent) ONLY
# in ``LlmAgent.model_post_init``. ``canonical_tools`` and
# ``_extract_task_delegation_fcs`` then read it from ``parent.tools`` — never
# from ``sub_agents``. So appending a task-mode sub-agent to ``sub_agents``
# after construction (which every production attach site does) leaves the parent
# with no dispatchable tool: the real LLM never sees ``request_task_<name>`` and
# the delegation — plus its inner ``usage_metadata`` — never fires. These
# helpers replicate model_post_init's injection so the production paths actually
# work, and set the parent pointer consistently on every path.
# ---------------------------------------------------------------------------


def _make_task_agent_tool(sub: BaseAgent) -> Any | None:
    """Return a ``_TaskAgentTool`` wrapping *sub*, or ``None`` on ADK < 2.0.

    ``_TaskAgentTool(sub).name == sub.name`` (it inherits ``AgentTool``'s
    ``name=agent.name``), which is the key ``_extract_task_delegation_fcs``
    matches the delegation function-call against.
    """
    if _TaskAgentTool is None:
        return None  # type: ignore[unreachable]  # ADK 1.34.x: symbol absent
    return _TaskAgentTool(sub)


def _remove_task_tool(parent: BaseAgent, sub_name: str) -> None:
    """Drop the ``_TaskAgentTool`` named *sub_name* from ``parent.tools`` in place."""
    if _TaskAgentTool is None:
        return  # type: ignore[unreachable]  # ADK 1.34.x: symbol absent
    tools = getattr(parent, "tools", None)
    if not isinstance(tools, list):
        return
    tools[:] = [
        t
        for t in tools
        if not (
            isinstance(t, _TaskAgentTool) and getattr(t, "name", None) == sub_name
        )
    ]


def attach_task_subagent(parent: BaseAgent, sub: BaseAgent) -> None:
    """Attach task-mode *sub* to *parent* the way ``model_post_init`` would.

    Appends *sub* to ``parent.sub_agents`` (in place when it is a list, so the
    ``AlwaysTrueSubAgentList`` shim and any shallow-copy holders are preserved),
    sets ``sub.parent_agent``, and appends the matching ``_TaskAgentTool`` to
    ``parent.tools`` so the parent's LLM can actually dispatch to it.
    """
    subs = getattr(parent, "sub_agents", None)
    if isinstance(subs, list):
        subs.append(sub)
    else:  # pragma: no cover - parents always carry a list in practice
        parent.sub_agents = [*list(subs or []), sub]
    _set_parent(sub, parent)
    tool = _make_task_agent_tool(sub)
    tools = getattr(parent, "tools", None)
    if tool is not None and isinstance(tools, list):
        tools.append(tool)


def detach_task_subagent(parent: BaseAgent, sub_name: str) -> None:
    """Reverse of :func:`attach_task_subagent` for the entry named *sub_name*.

    Clears the parent pointer, removes the sub-agent from ``parent.sub_agents``
    (in place), and removes its ``_TaskAgentTool`` from ``parent.tools``.
    """
    subs = getattr(parent, "sub_agents", None)
    if isinstance(subs, list):
        for sub in list(subs):
            if getattr(sub, "name", None) == sub_name:
                _clear_parent(sub, parent)
        subs[:] = [s for s in subs if getattr(s, "name", None) != sub_name]
    _remove_task_tool(parent, sub_name)


# ---------------------------------------------------------------------------
# ADK before_agent_callback bridge
# ---------------------------------------------------------------------------


def attach_specialists_before_agent_callback(
    callback_context: "CallbackContext",
) -> "types.Content | None":
    """Root ``before_agent_callback`` that syncs ``sub_agents`` per turn.

    Designed to be passed to :func:`build_agent` via
    ``additional_before_agent_callbacks=[attach_specialists_before_agent_callback]``.

    Reads ``account_id`` from ``callback_context.state`` and calls
    :func:`attach_account_specialists` against the root agent (resolved
    from ``callback_context._invocation_context.agent``, which is the
    agent whose callback fired — i.e. the root, since this callback is
    only attached to the root).

    Always returns ``None`` so the agent proceeds normally. Errors are
    swallowed (the underlying :func:`attach_account_specialists` already
    logs + degrades on every failure mode) so an attach failure cannot
    block the turn.
    """
    # AH-86: pin the Vertex model-serving endpoint for THIS runtime process.
    # ``build_hierarchy()`` (the other call site) runs only in the deploy
    # process and the local ``adk run`` path; the managed Agent Engine runtime
    # unpickles the prebuilt agent graph and never re-runs build_hierarchy, so
    # ``GOOGLE_CLOUD_LOCATION`` must be (re)applied here.  This before-agent
    # callback is the earliest guaranteed-to-fire runtime entrypoint (same
    # rationale as the pool initialisation below) and runs before the root
    # agent's first ``generate_content`` call this turn — so the genai client's
    # ``cached_property`` reads the corrected location.  Idempotent (logs only
    # on change); defensive so a resolver failure can never block the turn.
    try:
        apply_model_location_env()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "[ATTACH-SPECIALISTS] apply_model_location_env() raised; "
            "model-serving location may be stale: %s",
            exc,
        )

    # Pool initialisation (per-turn idempotent) — arm the background idle-TTL
    # sweeps on first turn inside the Agent Engine process.  start() is
    # idempotent on both pools; subsequent calls cost one branch check.  No
    # ADK-exposed AdkApp startup hook exists in the pinned version; this
    # callback is the closest guaranteed-to-fire entrypoint on the Agent
    # Engine surface.
    #
    # MCP pool (AH-78): start() calls asyncio.ensure_future(_sweep_loop()),
    # which requires a running event loop.  The callback fires from within
    # ADK's async invocation flow, so a loop IS in scope.  Separate
    # try/except from the SandboxPool block below so a failure in one pool
    # does not mask a failure in the other.
    try:
        from app.adk.agents.agent_factory.specialist_runtime import _DEFAULT_MCP_POOL

        _DEFAULT_MCP_POOL.start()
    except Exception as exc:
        logger.warning(
            "[ATTACH-SPECIALISTS] McpToolsetPool.start() raised; sweep may be dormant: %s",
            exc,
        )

    # SandboxPool (SK-37): start() spawns a daemon thread and needs no event
    # loop, so it is safe to call from this (or any) entrypoint.
    # start() is idempotent (sandbox_pool.py checks ``if self._sweep_thread
    # is not None and self._sweep_thread.is_alive()``), so the per-turn call
    # costs one branch check after the first invocation.
    try:
        from app.adk.agents.agent_factory.builder import _DEFAULT_SANDBOX_POOL

        _DEFAULT_SANDBOX_POOL.start()
    except Exception as exc:
        logger.warning(
            "[ATTACH-SPECIALISTS] SandboxPool.start() raised; sweep may be dormant: %s",
            exc,
        )

    try:
        account_id = callback_context.state.get("account_id")
        # NOTE: must use ``state.to_dict()`` — ADK's ``State`` exposes
        # ``__getitem__`` but no ``keys()`` / ``__iter__``, so ``dict(state)``
        # falls back to integer indexing and raises ``KeyError: 0``.
        session_state: Mapping[str, Any] = callback_context.state.to_dict()
        # ADK-version dependency: ``CallbackContext._invocation_context`` is a
        # private attribute and could be renamed in a future ADK release. We
        # use it here because there is no public accessor for the executing
        # agent on CallbackContext as of the version pinned by KEN-E. If ADK
        # later exposes a public ``callback_context.agent``, switch to it.
        # This callback is only attached to the root agent (see
        # hierarchy.build_hierarchy), so the agent on the invocation context
        # IS the root.
        # ADK 2.0: `_invocation_context.agent` now has type `BaseNode | None`
        # because `BaseAgent` is a subtype of `BaseNode`; cast to `BaseAgent`
        # because this callback is only wired onto the root (a `BaseAgent`).
        root_agent = cast(BaseAgent, callback_context._invocation_context.agent)
        attach_account_specialists(root_agent, account_id, session_state=session_state)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "[ATTACH-SPECIALISTS] before_agent_callback raised unexpectedly; "
            "specialists for this turn may be stale. %s",
            exc,
        )
    # Capture the per-turn specialist roster for W&B Weave tracing (CH-58).
    #
    # This write MUST happen every turn — including fingerprint-cache-hit turns
    # where ``_attach_locked`` returns early without touching ``root_agent.sub_agents``.
    # Reading from ``root_agent.sub_agents`` (not from a local variable inside
    # ``_attach_locked``) ensures the state always reflects the live attached set
    # regardless of whether the reconcile pass ran.
    #
    # ``agent_id == agent.name`` by ADK contract: ``_build_specialist`` assigns
    # ``name=doc_id`` and the name is preserved through the LoopAgent wrapper
    # (specialist_runtime.py:510-512, 572, 626). Both fields are emitted so
    # MER-E can join on either; a future ADK release that decouples them would
    # surface as a contract-version bump in docs/trace-structure-spec.md §16.
    # AH-84: capture human name + title alongside the existing specialist metadata
    # so the Available Specialists block can render the enriched identity clauses
    # (fast path via assemble_specialists_block_from_state).
    #
    # resolve_config is TTL-cached (60 s) and the cache is warm from the
    # _attach_locked call above (same turn, same account_id), so each lookup
    # here costs a single cache-hit — negligible versus the I/O the turn incurs.
    # We read account_id independently from the callback context rather than
    # relying on the outer try-block's variable to avoid a NameError if that
    # block raised before the assignment.
    try:
        _state_account_id: str | None = callback_context.state.get("account_id")
        # ADK 2.0: cast from BaseNode | None to BaseAgent (callback only wired on root).
        root_agent = cast(BaseAgent, callback_context._invocation_context.agent)
        sub_agents: list[Any] = getattr(root_agent, "sub_agents", None) or []

        specialists_state: list[dict[str, Any]] = []
        for a in sub_agents:
            entry: dict[str, Any] = {
                "name": a.name,
                "description": str(getattr(a, "description", "") or "")[:1024],
                "agent_id": a.name,
                "human_name": None,
                "title": None,
            }
            try:
                cfg = resolve_config(a.name, _state_account_id)
                entry["human_name"] = cfg.name
                entry["title"] = cfg.title
            except Exception as _cfg_exc:
                logger.warning(
                    "[ATTACH-SPECIALISTS] resolve_config(%r, %r) failed while "
                    "building _available_specialists; human_name/title will be "
                    "absent for this specialist: %s",
                    a.name,
                    _state_account_id,
                    _cfg_exc,
                )
            specialists_state.append(entry)

        callback_context.state["_available_specialists"] = specialists_state
    except Exception as exc:
        logger.warning(
            "[ATTACH-SPECIALISTS] Failed to capture _available_specialists "
            "in session state: %s",
            exc,
        )
    return None
