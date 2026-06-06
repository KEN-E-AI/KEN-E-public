"""Build-time skill metadata sidecar.

Stores per-agent build-time facts (``skill_load_total_failure``,
``skill_load_timeout``, ``skill_name_index``) without mutating the ADK
``LlmAgent`` Pydantic model.  SK-27 reads via ``get_skill_build_metadata`` when
emitting the ``skill.list`` Weave span and when seeding
``state["skills_allowed_tools"]`` at turn start (SK-PRD-02 §7 AC-2a).

Keying — ``(account_id, agent.name)``
-------------------------------------
``agent.name`` alone is NOT a safe key.  Specialists are cached per
``(doc_id, account_id, content_hash)`` (``specialist_runtime.resolve_agent``),
so two accounts that attach *different* skills to the same specialist ``doc_id``
produce two distinct agent objects that share a ``name``.  Keying by ``name``
alone collapses them into one slot: the last account to build wins, and every
other account's turn then seeds ``state["skills_allowed_tools"]`` from the wrong
account's ``skill_name_index``.  Because ``skill_tool_filter`` degrades *open*
when the active ``skill_id`` is absent from that map, a stale cross-account slot
silently stops enforcing the skill tool-allowlist.  Keying by
``(account_id, agent.name)`` restores per-account isolation.

Why not ``id(agent)``?  ADK 2.0's graph engine clones the agent via
``model_copy()`` before each invocation; the clone carries the same ``name`` but
a different ``id()``, so an ``id()``-keyed sidecar always misses at callback
time.  ``(account_id, agent.name)`` is both clone-stable (a read from the clone
hits the original's entry) and account-isolated.

Bounded growth — ``weakref.finalize``
--------------------------------------
Only ``build_agent`` records, and it records on the *original* cached specialist
(clones never record).  We register a finalizer on that object so the entry is
dropped when the specialist falls out of the ``resolve_agent`` LRU and is
garbage-collected — tying sidecar lifetime to specialist lifetime, so we never
evict an entry whose specialist is still serving turns (that would degrade the
allowlist open).  A per-key *owner id* guards the content-hash-change handoff: a
fresh build for the same ``(account_id, name)`` re-claims the slot, and the stale
object's finalizer then no-ops so it cannot delete the newer data.

``_METADATA_SOFT_CAP`` is a backstop canary: under normal operation the
finalizers keep the dict bounded by the live specialist set; crossing the cap
means the finalizers are not firing (a leak regression) and emits a one-shot
WARNING.
"""

from __future__ import annotations

import logging
import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent

logger = logging.getLogger(__name__)

# Key = (account_id, agent.name).  account_id may be None for global builds, but
# those never record skill data (skills load only when account_id is set — see
# builder.build_agent), so a None-keyed entry is effectively unused.
_MetadataKey = tuple[str | None, str]

_metadata: dict[_MetadataKey, dict[str, Any]] = {}
# id() of the agent object that currently owns each slot.  Guards the finalizer
# against deleting a newer build's data after a content-hash change re-claims the
# same (account_id, name).
_owner: dict[_MetadataKey, int] = {}

# Backstop canary, well above the live bound (resolve_agent LRU cap 256, times
# the concurrently-served accounts).  Crossing it means the weakref finalizers are
# not evicting entries for GC'd specialists — a leak regression — so we WARN
# once rather than grow without bound.
_METADATA_SOFT_CAP = 1024
_soft_cap_warned: bool = False


def _key(agent: LlmAgent, account_id: str | None) -> _MetadataKey:
    return (account_id, agent.name)


def _release(key: _MetadataKey, owner_id: int) -> None:
    """Drop ``key`` iff ``owner_id`` still owns the slot.

    A newer build for the same ``(account_id, name)`` re-claims ownership; in
    that case the stale object's finalizer must NOT delete the fresh data, so it
    no-ops here.
    """
    if _owner.get(key) == owner_id:
        _owner.pop(key, None)
        _metadata.pop(key, None)


def record_skill_build_metadata(
    agent: LlmAgent, account_id: str | None, **fields: Any
) -> None:
    """Attach build-time skill metadata for ``(account_id, agent)``.

    Merges with prior calls for the same key.  Called once per specialist build
    (``build_agent``) under the per-account stripe lock, so concurrent writes to
    the same key are serialised by the caller.
    """
    global _soft_cap_warned
    key = _key(agent, account_id)
    owner_id = id(agent)
    if _owner.get(key) != owner_id:
        # First record for this key, or a fresh build (new object, e.g. after a
        # config/content-hash change) taking over the slot — reset and re-own.
        _owner[key] = owner_id
        _metadata[key] = {}
        # Evict when the *original* cached specialist is GC'd (dropped from the
        # resolve_agent LRU).  Clones read via the same key but never record, so
        # reads survive cloning; only this object's collection clears the entry.
        try:
            weakref.finalize(agent, _release, key, owner_id)
        except TypeError:
            # Agent does not support weakref under this ADK version; eviction
            # degrades to the soft-cap canary below.  The (account_id, name)
            # keying — the correctness fix — still applies.
            pass
    _metadata[key].update(fields)
    if len(_metadata) > _METADATA_SOFT_CAP and not _soft_cap_warned:
        _soft_cap_warned = True
        logger.warning(
            "skill_metadata_dict_exceeded_expected_bound",
            extra={
                "size": len(_metadata),
                "soft_cap": _METADATA_SOFT_CAP,
                "reason": (
                    "(account_id, agent.name) sidecar exceeded its expected "
                    "bound; weakref finalizers may not be evicting entries for "
                    "GC'd specialists — investigate a leak."
                ),
            },
        )


def get_skill_build_metadata(
    agent: LlmAgent, account_id: str | None
) -> dict[str, Any]:
    """Return a copy of the metadata for ``(account_id, agent)`` (``{}`` if none)."""
    return dict(_metadata.get(_key(agent, account_id), {}))
