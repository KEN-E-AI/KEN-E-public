"""Per-turn specialist resolver for the per-dispatch-agent surface
(AH-PRD-09 + AH-75).

Replaces the deploy-time factory model (AH-PRD-02) with a per-turn resolution
path: specialists are resolved from Firestore on each turn (TTL-cached) rather
than baked into the deployed agent artifact.

Three public entry points:

* ``resolve_config`` — TTL-cached ``MergedAgentConfig`` fetch via
  ``get_cached_merged_config``.
* ``resolve_agent`` — LRU-cached specialist ``BaseAgent`` keyed by
  ``(doc_id, account_id, content_hash)``.  Returns either a raw
  ``LlmAgent`` or a review-pipeline-wrapped ``LoopAgent`` (when
  ``config.default_acceptance_criteria`` is set) — both share the same
  ``.name == doc_id`` contract so ADK's ``transfer_to_agent`` resolves
  to either form through ``root.find_agent``. Content-hash invalidation
  means any field change to the Firestore config drops the stale agent
  and triggers a rebuild on next access.
* ``available_specialists_provider`` — ``InstructionProvider``-compatible
  callable ``(ReadonlyContext) -> str``; returns the "## Available Specialists"
  Markdown block for injection into the root agent's system prompt.

Design notes:
* ``_AgentCache`` is a plain ``collections.OrderedDict``-backed LRU capped at
  256 entries with its own ``threading.Lock``.  The lock is separate from the
  config-cache stripe lock: config reads and agent construction are independent
  critical sections.
* Content hash: ``sha256(MergedAgentConfig.model_dump_json().encode()).hexdigest()``.
  Any field change produces a new hash; the stale agent entry is evicted
  on next LRU access via natural ``OrderedDict`` displacement rather than explicit
  deletion.
* Phase 2 (AH-59): ``_build_specialist`` fetches MCP server docs directly from
  Firestore (one ``get()`` per server ID) and calls ``build_toolset_for_doc``.
  Phase 3 (AH-62) will replace this with ``McpToolsetPool.get(server_id)``.
* ``available_specialists_provider`` filters to ``visible_in_frontend=True``
  configs so strategy-pipeline and other hidden agents are excluded from the
  block shown to the root agent.
* AH-75: dispatch happens via ADK's native ``transfer_to_agent``; runtime
  attachment of resolved specialists to ``root.sub_agents`` lives in
  ``sub_agent_attacher`` (a sibling module), invoked from the root agent's
  ``before_agent_callback``.
"""

# NOTE: do NOT add `from __future__ import annotations` here. Dispatch closures
# and InstructionProvider callables passed to LlmAgent are cloudpickled into the
# Agent Engine deployment artifact; deferred (string) annotations don't survive
# the round-trip. Resolving annotations at definition time (no future import)
# matches the pattern in dispatch.py. See the dispatch.py header comment for the
# full ADK/cloudpickle rationale (verified during AH-17 smoke testing).

import collections
import hashlib
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.readonly_context import ReadonlyContext

from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.utils.config_cache import get_cached_merged_config
from shared.account_id_utils import validate_account_id

# Firestore document IDs for MCP servers and specialist configs follow the same
# lowercase-identifier convention as specialist names in dispatch.py.
_VALID_DOC_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

logger = logging.getLogger(__name__)

# LRU capacity for the agent object cache.
_AGENT_CACHE_MAX: int = 256


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


def _content_hash(config: MergedAgentConfig) -> str:
    """Return a sha256 hex digest of ``config``'s JSON representation.

    Any field change (instruction, model, temperature, mcp_servers, …)
    produces a new hash, causing the cached ``LlmAgent`` to be superseded on
    the next ``resolve_agent`` call.
    """
    return hashlib.sha256(config.model_dump_json().encode()).hexdigest()


# ---------------------------------------------------------------------------
# LRU agent cache
# ---------------------------------------------------------------------------


class _AgentCache:
    """Thread-safe LRU cache for resolved specialist ``BaseAgent`` objects.

    Keyed by ``(doc_id, account_id | None, content_hash)``.  Capped at
    ``maxsize`` entries; the least-recently-used entry is evicted when at
    capacity.  Uses a dedicated ``threading.Lock`` — separate from the
    config-cache stripe locks — because agent construction (the critical
    section on miss) is independent of config fetches.

    Entries are typed as ``BaseAgent`` rather than ``LlmAgent`` because
    ``_build_specialist`` may wrap the constructed ``LlmAgent`` in a
    ``build_review_pipeline`` ``LoopAgent`` when the config specifies a
    ``default_acceptance_criteria`` (AH-75 / AH-PRD-09 review-config).

    Single-flight on cache miss: ``get_or_build`` holds the lock across the
    check-and-populate window so N concurrent cold reads for the same key
    call *builder* exactly once rather than N times (thundering-herd fix).
    """

    def __init__(self, maxsize: int = _AGENT_CACHE_MAX) -> None:
        self._maxsize = maxsize
        self._store: collections.OrderedDict[tuple[str, str | None, str], BaseAgent] = (
            collections.OrderedDict()
        )
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str | None, str]) -> BaseAgent | None:
        """Return the cached agent for *key*, or ``None`` on miss.

        Promotes *key* to the MRU end on hit.
        """
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def put(self, key: tuple[str, str | None, str], agent: BaseAgent) -> None:
        """Insert or update *key* → *agent*, evicting the LRU entry if at capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            elif len(self._store) >= self._maxsize:
                self._store.popitem(last=False)  # evict LRU
            self._store[key] = agent

    def get_or_build(
        self,
        key: tuple[str, str | None, str],
        builder: Callable[[], BaseAgent],
    ) -> BaseAgent:
        """Return the cached agent for *key*, calling *builder* exactly once on miss.

        Holds the lock across the check-and-populate window (double-checked
        locking is unnecessary here because we never release between the two
        checks).  Concurrent callers for the same key block until the first
        build completes, then see the populated entry on their own check.
        """
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            agent = builder()
            if len(self._store) >= self._maxsize:
                self._store.popitem(last=False)  # evict LRU
            self._store[key] = agent
            return agent

    def clear(self) -> None:
        """Drop all cached agents.  Primarily for tests."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


_specialists_cache: _AgentCache = _AgentCache()


# ---------------------------------------------------------------------------
# Rendered "Available Specialists" Markdown block cache
# ---------------------------------------------------------------------------
# Caches the rendered block from ``available_specialists_provider`` by
# ``account_id``.  Without this cache, each invocation re-issues
# ``list_account_agent_configs`` + N ``resolve_config`` + N ``resolve_agent``
# calls.  TTL matches ``get_cached_merged_config`` so admin edits propagate on
# the same horizon as the rest of the cache hierarchy.

_BLOCK_CACHE_TTL: int = 60
_BlockCacheEntry = tuple[str, float]  # (rendered_block, expires_at_monotonic)
_block_cache: dict[str, _BlockCacheEntry] = {}
_block_locks: list[threading.Lock] = [threading.Lock() for _ in range(32)]


def _block_lock_for(account_id: str) -> threading.Lock:
    return _block_locks[hash(account_id) % 32]


def _clear_block_cache_for_tests() -> None:
    """Drop the rendered-block cache.  Acquires all stripes in index order."""
    for lock in _block_locks:
        lock.acquire()
    try:
        _block_cache.clear()
    finally:
        for lock in _block_locks:
            lock.release()


# ---------------------------------------------------------------------------
# Specialist construction (Phase 2 — direct Firestore MCP fetch)
# ---------------------------------------------------------------------------


def _build_specialist(
    config: MergedAgentConfig, name: str, account_id: str | None
) -> BaseAgent:
    """Construct a specialist ``BaseAgent`` from a ``MergedAgentConfig``.

    Returns an ``LlmAgent`` for single-pass dispatch. When
    ``config.default_acceptance_criteria`` is set (AH-75 / AH-PRD-09), wraps
    that ``LlmAgent`` in ``build_review_pipeline`` and returns the resulting
    ``LoopAgent`` instead — the wrap is decided at content-hash build time
    so review-config edits propagate through the resolver's existing
    invalidation path. The wrapped pipeline is renamed back to *name* so
    ADK's ``transfer_to_agent`` (which looks up sub-agents by name) finds
    it under the same identifier as the unwrapped specialist.

    Mirrors the pre-AH-PRD-09 specialist-build path from ``hierarchy.py`` (now
    deleted from the deploy-time loop) so the per-turn resolver preserves
    every shipped behaviour:

    * **AH-PRD-06 `tool_ids` MCP allowlist** — ``per_server_allowed_tools``
      derives the per-server bare-name list and threads it through
      ``build_toolset_for_doc(..., allowed_tool_names=...)`` so each
      ``McpToolset`` is constructed with ADK's native ``tool_filter`` rather
      than mutating ``tool_filter`` after the fact. Servers with no listed
      tools are skipped entirely so we don't pay the connection cost.
    * **AH-PRD-06 PR-C `default_global` function tools** —
      ``resolve_default_global_tools(get_default_registry())`` is resolved
      once and appended to every specialist's roster (e.g.
      ``create_visualization``). Filtered per-spec by
      ``resolve_specialist_roster`` when ``tool_ids`` is set.
    * **AH-PRD-02 §2.5 ≤30-tool roster cap** — ``resolve_specialist_roster``
      counts MCP tools individually (not toolsets-as-1 like the literal cap
      in ``builder.build_agent``) and raises ``RosterCapExceededError`` when
      a specialist would exceed the cap.

    Phase 2 (AH-59): fetches each MCP server document individually from
    Firestore and calls ``build_toolset_for_doc``.
    Phase 3 (AH-62): replace the per-server Firestore ``get()`` calls with
    ``McpToolsetPool.get(server_id)`` to reuse already-connected sessions.
    """
    from app.adk.agents.agent_factory.builder import build_agent
    from app.adk.agents.agent_factory.mcp import (
        MCP_COLLECTION,
        MCPSchemaError,
        _build_firestore_client,
        _resolve_project_id,
        build_toolset_for_doc,
    )
    from app.adk.agents.agent_factory.roster import (
        MAX_TOOLS_PER_SPECIALIST,
        RosterCapExceededError,
        per_server_allowed_tools,
        resolve_specialist_roster,
    )
    from app.adk.tools.registry.function_tool_registry import (
        resolve_default_global_tools,
    )
    from app.adk.tools.registry.tool_registry import get_default_registry

    # AH-PRD-06: when ``tool_ids`` is set, derive the per-server allowlist
    # used both to skip irrelevant servers below and to pass
    # ``allowed_tool_names=`` into ``build_toolset_for_doc``. ``None``
    # signals legacy behaviour (every tool from every attached server).
    per_server_allowed: dict[str, list[str]] | None = per_server_allowed_tools(
        config.tool_ids
    )

    toolsets: dict[str, Any] = {}

    if config.mcp_servers:
        project_id = _resolve_project_id(None)
        db = _build_firestore_client(project_id)

        for server_id in config.mcp_servers:
            try:
                if not _VALID_DOC_ID_RE.match(server_id):
                    logger.error(
                        "MCP server ID %r for specialist %r fails format validation; skipping",
                        server_id,
                        name,
                    )
                    continue
                # AH-PRD-06: skip servers with no tool_ids match — no point
                # paying the Firestore + connection cost for a toolset whose
                # tools are all filtered out downstream.
                if per_server_allowed is not None and not per_server_allowed.get(
                    server_id
                ):
                    logger.debug(
                        "MCP server %r has no tool_ids match for specialist %r; skipping.",
                        server_id,
                        name,
                    )
                    continue
                snap = db.collection(MCP_COLLECTION).document(server_id).get()
                if not snap.exists:
                    logger.warning(
                        "MCP server doc %r not found in %r; skipping for specialist %r",
                        server_id,
                        MCP_COLLECTION,
                        name,
                    )
                    continue
                doc = snap.to_dict() or {}
                if doc.get("enabled") is not True:
                    logger.warning(
                        "MCP server %r is not enabled; skipping for specialist %r",
                        server_id,
                        name,
                    )
                    continue
                if per_server_allowed is None:
                    toolsets[server_id] = build_toolset_for_doc(server_id, doc)
                else:
                    toolsets[server_id] = build_toolset_for_doc(
                        server_id,
                        doc,
                        allowed_tool_names=per_server_allowed[server_id],
                    )
            except (MCPSchemaError, ValueError) as exc:
                logger.error(
                    "Failed to build toolset for MCP server %r (specialist %r): %s",
                    server_id,
                    name,
                    exc,
                )

    # AH-PRD-06 PR-C: resolve ``default_global: true`` function tools (e.g.
    # ``create_visualization`` from AH-PRD-04) once per specialist build.
    # Filtered per-spec by ``resolve_specialist_roster`` when ``tool_ids``
    # is non-None; included verbatim otherwise.
    default_global_function_tools = resolve_default_global_tools(get_default_registry())

    # AH-PRD-02 §2.5: enforce the ≤30-tool logical cap and apply the
    # ``tool_ids`` filter to the assembled tool list. Raises
    # ``RosterCapExceededError`` (which propagates through ``resolve_agent``
    # / ``run``) when a specialist would exceed the cap — the deploy-time
    # path raised at deploy; here it raises on first dispatch.
    try:
        tools = resolve_specialist_roster(
            name,
            mcp_toolsets=toolsets,
            function_tools=default_global_function_tools,
            mcp_server_ids=list(toolsets.keys()),
            tool_ids=config.tool_ids,
        )
    except RosterCapExceededError:
        logger.exception(
            "Specialist %r exceeds the %d-tool roster cap; raising.",
            name,
            MAX_TOOLS_PER_SPECIALIST,
        )
        raise

    specialist = build_agent(
        config, name=name, account_id=account_id, tools=tools, config_doc_id=None
    )

    # AH-75 / AH-PRD-09: review-pipeline opt-in lives on the specialist's
    # Firestore config, not on the per-call dispatch surface. When set, wrap
    # the constructed LlmAgent in build_review_pipeline so every dispatch to
    # this specialist runs the worker/reviewer loop. The cache key
    # (doc_id, account_id, content_hash) already covers this — content_hash
    # incorporates default_acceptance_criteria via model_dump_json.
    criteria = (config.default_acceptance_criteria or "").strip()
    if not criteria:
        return specialist

    from app.adk.agents.utils.criteria_utils import (
        MAX_CRITERIA_CHARS,
        sanitise_criteria,
    )
    from app.adk.agents.utils.review_pipeline import build_review_pipeline

    if len(criteria) > MAX_CRITERIA_CHARS:
        logger.warning(
            "[BUILD-SPECIALIST] default_acceptance_criteria for %r truncated "
            "from %d to %d chars",
            name,
            len(criteria),
            MAX_CRITERIA_CHARS,
        )
        criteria = criteria[:MAX_CRITERIA_CHARS]
    criteria = sanitise_criteria(criteria)

    pipeline = build_review_pipeline(
        specialist=specialist,
        acceptance_criteria=criteria,
        output_key_prefix=f"{name}_review",
    )

    # Rename the LoopAgent to the specialist's doc_id so ADK's
    # transfer_to_agent (which calls root.find_agent(name)) locates the
    # wrapped pipeline under the same identifier the LLM sees in the
    # Available Specialists block. BaseAgent fields are mutable;
    # parent_agent / sub_agents are managed by the sub_agent_attacher.
    pipeline.name = name
    # Carry the specialist's description across so available_specialists_provider
    # surfaces the same user-facing string whether or not review is enabled.
    pipeline.description = specialist.description
    return pipeline


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_config(
    doc_id: str,
    account_id: str | None = None,
    ttl_seconds: int = 60,
) -> MergedAgentConfig:
    """Return the TTL-cached ``MergedAgentConfig`` for ``(doc_id, account_id)``.

    Thin wrapper over :func:`get_cached_merged_config`.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        account_id: Per-account overlay key.  ``None`` loads the global config.
        ttl_seconds: TTL passed through to the cache layer.

    Returns:
        Validated ``MergedAgentConfig``.

    Raises:
        ``ConfigNotFoundError``, ``ConfigValidationError``, or
        ``FirestoreConnectionError`` from the underlying loader — only when no
        stale cache entry exists to serve.
    """
    return get_cached_merged_config(doc_id, account_id, ttl_seconds)


def resolve_agent(
    doc_id: str,
    account_id: str | None = None,
    ttl_seconds: int = 60,
) -> BaseAgent:
    """Return a cached specialist ``BaseAgent`` for ``(doc_id, account_id)``.

    Fetches the ``MergedAgentConfig``, computes a content-hash, and returns
    the cached agent if one exists with the same
    ``(doc_id, account_id, content_hash)``.  On hash mismatch (config changed
    since last build), a new agent is constructed and inserted into the LRU
    cache; the stale entry is evicted naturally when the cache reaches
    capacity.

    Returns an ``LlmAgent`` for plain specialists or a ``LoopAgent``
    (review pipeline) when ``config.default_acceptance_criteria`` is set
    (AH-75 / AH-PRD-09). The returned agent's ``.name`` matches *doc_id*
    in both cases so ADK's ``transfer_to_agent`` finds it under one
    identifier.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        account_id: Per-account overlay key.  ``None`` loads the global config.
        ttl_seconds: TTL for the underlying config cache.

    Returns:
        A ready-to-use ``BaseAgent`` with tools wired according to the config.

    Raises:
        Any exception that :func:`resolve_config` or :func:`_build_specialist`
        raises (Firestore errors, roster-cap exceeded, MCP schema errors, …).
    """
    config = resolve_config(doc_id, account_id, ttl_seconds)
    content_hash = _content_hash(config)
    cache_key: tuple[str, str | None, str] = (doc_id, account_id, content_hash)

    return _specialists_cache.get_or_build(
        cache_key, lambda: _build_specialist(config, doc_id, account_id)
    )


def available_specialists_provider(context: ReadonlyContext) -> str:
    """Return the ``## Available Specialists`` Markdown block for the root agent.

    Designed as an ADK ``InstructionProvider``-compatible callable
    ``(ReadonlyContext) -> str``.  Reads ``account_id`` from session state,
    lists all agent configs visible to the account, resolves each to a
    ``LlmAgent``, filters to ``visible_in_frontend=True``, and formats the
    result using :func:`assemble_available_specialists_block` from
    ``dispatch.py``.

    Agents that fail to resolve are logged and excluded from the block rather
    than surfacing as errors to the root agent.

    Args:
        context: ADK ``ReadonlyContext`` providing ``context.state``.

    Returns:
        Formatted Markdown string starting with ``"## Available Specialists\\n\\n"``.
    """
    from app.adk.agents.agent_factory.config_loader import (
        FirestoreConnectionError,
        list_account_agent_configs,
    )
    from app.adk.agents.agent_factory.dispatch import (
        assemble_available_specialists_block,
    )

    account_id: str | None = context.state.get("account_id")

    if not account_id:
        logger.warning(
            "[AVAILABLE-SPECIALISTS] No account_id in session state; "
            "returning empty specialists block."
        )
        return "## Available Specialists\n\n- None registered."

    try:
        account_id = validate_account_id(account_id)
    except ValueError:
        logger.warning(
            "[AVAILABLE-SPECIALISTS] Invalid account_id %r in session state; "
            "returning empty specialists block.",
            account_id,
        )
        return "## Available Specialists\n\n- None registered."

    now = time.monotonic()
    with _block_lock_for(account_id):
        cached = _block_cache.get(account_id)
        if cached is not None and now < cached[1]:
            return cached[0]

    try:
        doc_ids = list_account_agent_configs(account_id)
    except FirestoreConnectionError as exc:
        logger.error(
            "[AVAILABLE-SPECIALISTS] Failed to list configs (account=%r): %s",
            account_id,
            exc,
        )
        return "## Available Specialists\n\n- None registered."

    specialists: dict[str, BaseAgent] = {}
    for doc_id in doc_ids:
        try:
            config = resolve_config(doc_id, account_id)
            if not config.visible_in_frontend:
                continue
            agent = resolve_agent(doc_id, account_id)
            specialists[doc_id] = agent
        except Exception as exc:
            logger.warning(
                "[AVAILABLE-SPECIALISTS] Could not resolve specialist %r (account=%r): %s",
                doc_id,
                account_id,
                exc,
                exc_info=True,
            )

    block = assemble_available_specialists_block(specialists)
    with _block_lock_for(account_id):
        _block_cache[account_id] = (block, time.monotonic() + _BLOCK_CACHE_TTL)
    return block
