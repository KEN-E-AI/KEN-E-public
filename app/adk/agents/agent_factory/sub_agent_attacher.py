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

* Lists every visible specialist for *account_id* via
  :func:`config_loader.list_account_agent_configs`, resolves each through
  :func:`specialist_runtime.resolve_agent` (LRU-cached;
  content-hash-keyed), and ensures each resolved ``BaseAgent`` appears in
  ``root_agent.sub_agents`` exactly once.

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
  from ``specialist_runtime`` (:func:`_block_lock_for`). Concurrent turns
  for the same account serialise; turns for different accounts do not
  contend.

Per-process safety: Agent Engine deploys one root instance per worker
process. Mutating ``root.sub_agents`` is therefore process-local. The
``_specialists_cache`` is also process-local, so cache eviction and
sub_agents reconcile stay in sync without distributed coordination.
"""

import logging
from typing import Any

from google.adk.agents import BaseAgent

from app.adk.agents.agent_factory.config_loader import (
    FirestoreConnectionError,
    list_account_agent_configs,
)
from app.adk.agents.agent_factory.specialist_runtime import (
    _block_lock_for,
    resolve_agent,
    resolve_config,
)
from shared.account_id_utils import validate_account_id

logger = logging.getLogger(__name__)


def attach_account_specialists(
    root_agent: BaseAgent,
    account_id: str | None,
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
    """
    if not _has_sub_agents_attr(root_agent):
        logger.error(
            "[ATTACH-SPECIALISTS] root_agent %r has no sub_agents attribute; "
            "skipping.",
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

    with _block_lock_for(validated_account_id):
        _attach_locked(root_agent, validated_account_id)


def _attach_locked(root_agent: BaseAgent, account_id: str) -> None:
    """Critical section of :func:`attach_account_specialists`.

    Caller holds the per-account stripe lock.
    """
    try:
        doc_ids = list_account_agent_configs(account_id)
    except FirestoreConnectionError as exc:
        logger.error(
            "[ATTACH-SPECIALISTS] Failed to list configs (account=%r): %s",
            account_id,
            exc,
        )
        return

    desired: dict[str, BaseAgent] = {}
    for doc_id in doc_ids:
        try:
            config = resolve_config(doc_id, account_id)
            if not config.visible_in_frontend:
                continue
            desired[doc_id] = resolve_agent(doc_id, account_id)
        except Exception as exc:
            # Mirror available_specialists_provider's policy: log and drop the
            # offender so the prompt block and the sub_agents set agree.
            logger.warning(
                "[ATTACH-SPECIALISTS] Could not resolve specialist %r "
                "(account=%r): %s",
                doc_id,
                account_id,
                exc,
                exc_info=True,
            )

    _reconcile(root_agent, desired)


def _reconcile(
    root_agent: BaseAgent, desired: dict[str, BaseAgent]
) -> None:
    """Mutate ``root_agent.sub_agents`` to match ``desired`` (keyed by name).

    Removes entries whose name is absent from *desired* OR whose current
    instance differs from the desired one (config-hash drift produced a
    fresh agent). Adds entries that are missing. Existing entries that
    match by identity are left alone — same agent, same parent pointer,
    no work.
    """
    existing: list[BaseAgent] = list(root_agent.sub_agents)
    desired_by_name = dict(desired)

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
        else:
            # Name still visible but a fresh instance has replaced it
            # (content_hash drift on a config edit). Drop the stale, keep the
            # desired below.
            _clear_parent(sub, root_agent)

    # Add anything still in desired_by_name (either net-new or replaced).
    for new_sub in desired_by_name.values():
        _set_parent(new_sub, root_agent)
        keep.append(new_sub)

    root_agent.sub_agents = keep


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
