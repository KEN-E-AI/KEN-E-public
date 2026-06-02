"""Per-turn root-agent tool reconciler (AH-100).

Extends the per-turn specialist sync pattern established by
:mod:`app.adk.agents.agent_factory.sub_agent_attacher` to the root agent's
``tools`` list. Whereas ``sub_agent_attacher`` keeps ``root.sub_agents`` in
sync with the current visible-specialist set, this module keeps ``root.tools``
in sync with the current ``ken_e_chatbot.tool_ids`` Firestore config.

Before AH-100, AH-98 wired ``build_hierarchy()`` to resolve ``ken_e_chatbot.
tool_ids`` **once at deploy time** via ``resolve_specialist_roster``. That
resolution is frozen into the deployed artifact; editing the Firestore doc
afterwards has no effect until the next ``make backend``. This module adds a
``before_agent_callback`` that re-evaluates ``tool_ids`` on every turn (within
the 60 s ``get_cached_merged_config`` TTL) and replaces ``root.tools`` when the
resolved list differs — the same hot-reload horizon admins expect for
``instruction`` and specialist edits.

ADK behaviour confirmation (google-adk==1.27.5 — Task 1 spike):
    ``base_agent.run_async`` fires ``_handle_before_agent_callback`` *before*
    ``_run_async_impl`` (``base_agent.py:291``). ``_process_agent_tools`` reads
    ``agent.tools`` directly at LLM-request build time without a pre-invocation
    snapshot (``base_llm_flow.py:418-441``). Therefore a ``root.tools``
    replacement inside ``before_agent_callback`` IS honoured on the same turn.
    See ``tests/test_root_tools_attacher_adk_smoke.py`` for the static-proof
    and live-Runner confirmation tests.

Per-process safety note (cf. ``sub_agent_attacher.py:48-51``):
    Agent Engine deploys one root instance per worker process. Mutating
    ``root.tools`` is therefore process-local. Because there is exactly one
    ``root.tools`` slot per process, the applied-config hash is a single
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

from google.adk.agents import BaseAgent

from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError
from app.adk.agents.agent_factory.roster import (
    RosterCapExceededError,
    resolve_specialist_roster,
)
from app.adk.agents.agent_factory.specialist_runtime import block_lock_for
from app.adk.agents.utils.config_cache import get_cached_merged_config
from app.adk.tools.registry.agent_tool_registry import resolve_agent_tools
from app.adk.tools.registry.tool_registry import get_default_registry
from shared.account_id_utils import validate_account_id

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent
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
            "[ATTACH-ROOT-TOOLS] Firestore error fetching root config "
            "(account=%r): %s",
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

    # 2. Applied-hash check: skip the full resolve when ``root.tools`` already
    #    reflects this exact config. Single global slot (see ``_applied_hash``):
    #    an account switch changes ``content_hash`` and forces a re-resolve, so
    #    one account never serves another's tools from the shared slot.
    content_hash = _hash_config(config)
    if _applied_hash == content_hash:
        return  # No-op: root.tools already reflects this config version.

    # 3. Resolve the tool list via the shared roster resolver.
    #    Uses the same call AH-98's build_hierarchy performs so the ≤30-tool
    #    cap, agent-tool opt-in semantics, and registry resolution are identical
    #    at deploy-time and at runtime.
    try:
        _registry = get_default_registry()
        resolved_tools = resolve_specialist_roster(
            "ken_e",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=resolve_agent_tools(_registry),
            tool_ids=getattr(config, "tool_ids", None),
            registry=_registry,
        )
    except RosterCapExceededError as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] RosterCapExceededError for root config "
            "(account=%r): %s — root.tools unchanged; applied hash NOT updated.",
            account_id,
            exc,
        )
        # Do NOT update the applied hash so the next turn retries.
        return
    except Exception as exc:
        logger.error(
            "[ATTACH-ROOT-TOOLS] Unexpected error resolving root tools "
            "(account=%r): %s — root.tools unchanged; applied hash NOT updated.",
            account_id,
            exc,
            exc_info=True,
        )
        return

    # 4. Replace root.tools only when the resolved list differs from the current.
    #    Identity comparison (``is``) detects the fingerprint-miss case where the
    #    same tool objects are re-resolved; equality (``==``) would be unreliable
    #    for ADK tool objects without a defined __eq__.  We compare the tool
    #    *list* by identity of each element rather than by list identity, because
    #    the resolver always produces a fresh list even on a cache hit.
    current_tools: list[Any] = list(root.tools)
    if _tools_equal(current_tools, resolved_tools):
        # Lists are semantically the same — record the applied hash so the next
        # turn for this config skips straight to the hash-hit branch.
        _applied_hash = content_hash
        return

    root.tools = resolved_tools
    _applied_hash = content_hash
    logger.debug(
        "[ATTACH-ROOT-TOOLS] root.tools reconciled (account=%r): "
        "%d → %d tool(s).",
        account_id,
        len(current_tools),
        len(resolved_tools),
    )


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
        root_agent = callback_context._invocation_context.agent
        attach_root_tools(root_agent, account_id)
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception(
            "[ATTACH-ROOT-TOOLS] before_agent_callback raised unexpectedly; "
            "root.tools for this turn may be stale. %s",
            exc,
        )
    return None
