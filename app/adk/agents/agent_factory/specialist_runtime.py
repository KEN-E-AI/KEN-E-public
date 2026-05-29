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
  Phase 3 (AH-62): pool-backed checkout via ``McpToolsetPool`` (implemented).
* ``available_specialists_provider`` filters to ``ken_e_sub_agent=True``
  configs so strategy-pipeline and other workflow-only agents are excluded
  from the block shown to the root agent.  ``visible_in_frontend`` is
  unaffected by this filter — it governs Workflows-page UI visibility only.
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

import asyncio
import collections
import concurrent.futures
import hashlib
import json
import re
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.readonly_context import ReadonlyContext

from app.adk.agents.agent_factory._executors import get_pool_checkout_executor
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.mcp_pool import McpServerKind, McpToolsetPool
from app.adk.agents.utils.config_cache import get_cached_merged_config
from shared.account_id_utils import validate_account_id
from shared.structured_logging import get_structured_logger

# Firestore document IDs for MCP servers and specialist configs follow the same
# lowercase-identifier convention as specialist names in dispatch.py.
_VALID_DOC_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

logger = get_structured_logger(__name__)

# LRU capacity for the agent object cache.
_AGENT_CACHE_MAX: int = 256

# Timeout for checking out a single MCP toolset from the pool.  Mirrors the
# SandboxPool build timeout in builder.py.  On timeout the server is skipped
# for this specialist build (per-server skip, not a hard failure).
_MCP_POOL_CHECKOUT_TIMEOUT_SECONDS: int = 30

# Process-wide singleton — one pool per Cloud Run instance.  Mirrors the
# ``_DEFAULT_SANDBOX_POOL`` singleton pattern in builder.py:51.
# Tests inject a fresh pool or MagicMock via the ``mcp_pool=`` kwarg on
# ``_build_specialist`` so the module global is never mutated by test code.
# start() is called from attach_specialists_before_agent_callback (AH-78),
# which arms the idle-TTL background sweep on the first turn per process.
_DEFAULT_MCP_POOL: McpToolsetPool = McpToolsetPool()


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


def block_lock_for(account_id: str) -> threading.Lock:
    """Return the stripe lock for *account_id*. Caller must pre-validate via ``validate_account_id``."""
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
# list_account_agent_configs TTL cache
# ---------------------------------------------------------------------------
# Caches the raw ``list_account_agent_configs`` result by ``account_id`` so
# that ``available_specialists_provider`` and ``_attach_locked`` share one
# Firestore list call per TTL window rather than issuing independent calls.

_LIST_CACHE_TTL: int = 60
_ListCacheEntry = tuple[list[str], float]  # (doc_ids, expires_at_monotonic)
_list_cache: dict[str, _ListCacheEntry] = {}
_list_locks: list[threading.Lock] = [threading.Lock() for _ in range(32)]


def _list_lock_for(account_id: str) -> threading.Lock:
    return _list_locks[hash(account_id) % 32]


def list_account_agent_configs_cached(account_id: str) -> list[str]:
    """Return ``list_account_agent_configs(account_id)`` with TTL caching.

    Shares one Firestore list call between ``available_specialists_provider``
    and the ``sub_agent_attacher`` within the same TTL window.  The stripe
    lock is separate from ``block_lock_for`` so the two caches can be
    populated/invalidated independently.
    """
    from app.adk.agents.agent_factory.config_loader import (
        list_account_agent_configs,
    )

    now = time.monotonic()
    lock = _list_lock_for(account_id)
    with lock:
        entry = _list_cache.get(account_id)
        if entry is not None and now < entry[1]:
            return list(entry[0])  # defensive copy — callers must not mutate the cache
        doc_ids = list(list_account_agent_configs(account_id))
        _list_cache[account_id] = (doc_ids, now + _LIST_CACHE_TTL)
        return list(doc_ids)


def _clear_list_cache_for_tests() -> None:
    """Drop the list cache.  Acquires all stripes in index order."""
    for lock in _list_locks:
        lock.acquire()
    try:
        _list_cache.clear()
    finally:
        for lock in _list_locks:
            lock.release()


# ---------------------------------------------------------------------------
# Specialist construction (Phase 2 — direct Firestore MCP fetch)
# ---------------------------------------------------------------------------


def _build_specialist(
    config: MergedAgentConfig,
    name: str,
    account_id: str | None,
    session_state: Mapping[str, Any] | None = None,
    mcp_pool: McpToolsetPool | None = None,
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
    Phase 3 (AH-62): pool-backed path — checkout from ``McpToolsetPool`` via
    a ``asyncio.run`` + ``ThreadPoolExecutor`` bridge (same pattern as the
    sandbox pool in ``builder.py:344-368``).  The ``build_fn`` closure does the
    Firestore fetch + ``build_toolset_for_doc`` on a pool miss.  On timeout
    (30 s) the server is skipped for this specialist build (per-server skip).
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

    pool = mcp_pool if mcp_pool is not None else _DEFAULT_MCP_POOL

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
            if per_server_allowed is not None and not per_server_allowed.get(server_id):
                logger.debug(
                    "MCP server %r has no tool_ids match for specialist %r; skipping.",
                    server_id,
                    name,
                )
                continue

            # Phase 3 (AH-62): pool-backed checkout.
            # Compute creds_hash from session state so that credential rotation
            # produces a new pool key and forces a fresh SSE connection.
            # ``default=str`` coerces non-JSON-serialisable values (datetime,
            # bytes, set, custom objects) to a string representation rather
            # than aborting the entire specialist build with TypeError. The
            # creds substrate (``mcp_creds_*`` session-state keys) is written
            # by upstream auth flows the pool does not own; defensive coercion
            # keeps a hostile or future-extended payload from being a hard
            # failure mode for chat dispatch.
            cred_key = f"mcp_creds_{server_id}"
            creds_dict = (session_state or {}).get(cred_key, {})
            creds_hash = hashlib.sha256(
                json.dumps(creds_dict, sort_keys=True, default=str).encode()
            ).hexdigest()
            pool_key = (server_id, account_id or "", creds_hash)

            allowed_for_server: list[str] | None = (
                per_server_allowed[server_id]
                if per_server_allowed is not None
                else None
            )

            def _make_build_fn(
                sid: str,
                db_: Any,
                allowed_names: list[str] | None,
                specialist_name: str,
            ) -> Callable[[], Any]:
                def _build_fn() -> Any:
                    snap = db_.collection(MCP_COLLECTION).document(sid).get()
                    if not snap.exists:
                        raise MCPSchemaError(
                            f"MCP server doc {sid!r} not found in {MCP_COLLECTION!r}; "
                            f"skipping for specialist {specialist_name!r}"
                        )
                    doc = snap.to_dict() or {}
                    if doc.get("enabled") is not True:
                        raise MCPSchemaError(
                            f"MCP server {sid!r} is not enabled; "
                            f"skipping for specialist {specialist_name!r}"
                        )
                    if allowed_names is not None:
                        return build_toolset_for_doc(
                            sid, doc, allowed_tool_names=allowed_names
                        )
                    return build_toolset_for_doc(sid, doc)

                return _build_fn

            build_fn = _make_build_fn(server_id, db, allowed_for_server, name)

            def _runner(
                _pool: McpToolsetPool = pool,
                _key: tuple[str, ...] = pool_key,
                _fn: Callable[[], Any] = build_fn,
            ) -> Any:
                return asyncio.run(
                    _pool.get_or_create(
                        kind=McpServerKind.CLOUD_RUN,
                        key=_key,
                        build_fn=_fn,
                    )
                )

            # AH-77 Item F: reuse the process-wide singleton executor rather than
            # constructing a new ThreadPoolExecutor per server per specialist
            # build.  The executor's sole role is timeout enforcement via
            # future.result(timeout=...) — it is not used for parallelism.
            future = get_pool_checkout_executor().submit(_runner)
            try:
                toolsets[server_id] = future.result(
                    timeout=_MCP_POOL_CHECKOUT_TIMEOUT_SECONDS
                )
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "mcp_pool_checkout_timeout",
                    extra={
                        "server_id": server_id,
                        "specialist": name,
                        "timeout_s": _MCP_POOL_CHECKOUT_TIMEOUT_SECONDS,
                    },
                )
            except (MCPSchemaError, ValueError) as exc:
                logger.error(
                    "Failed to build toolset for MCP server %r (specialist %r): %s",
                    server_id,
                    name,
                    exc,
                )
            except Exception:
                logger.error(
                    "Unexpected error checking out MCP toolset for server %r "
                    "(specialist %r)",
                    server_id,
                    name,
                    exc_info=True,
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
        config, name=name, account_id=account_id, tools=tools, config_doc_id=name
    )

    # AH-75: prevent multi-turn "stuck on specialist" routing. ADK's Runner
    # picks the agent for each new user turn via ``_find_agent_to_run``
    # (runners.py), which resumes the last non-user agent if
    # ``_is_transferable_across_agent_tree`` returns True. That helper walks
    # ``parent_agent`` upward looking for any agent with
    # ``disallow_transfer_to_parent=True``; with the default (False) on both
    # the specialist and the root, every user turn after the first stays
    # with the specialist instead of returning to the root for re-routing.
    # Setting the flag on the specialist short-circuits the walk so each new
    # user message returns to the root.
    #
    # The wrapped path (LoopAgent below) bottoms out the walk naturally
    # because ``LoopAgent`` does not expose ``disallow_transfer_to_parent``
    # — but we set the flag here BEFORE wrapping anyway so the worker
    # ``LlmAgent`` inside the LoopAgent inherits it (build_review_pipeline
    # propagates the specialist's full field set to the worker). The flag
    # has no other effect: AH-75 specialists never call transfer_to_agent
    # themselves, so disabling parent-transfer is safe.
    specialist.disallow_transfer_to_parent = True

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
    session_state: Mapping[str, Any] | None = None,
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
        session_state: Current ADK session state mapping.  Used by Phase 3
            (AH-62) to derive per-server credential hashes for
            ``McpToolsetPool`` key computation.  ``None`` is treated as an
            empty mapping (all creds hashes default to the hash of ``{}``).

    Returns:
        A ready-to-use ``BaseAgent`` with tools wired according to the config.

    Raises:
        Any exception that :func:`resolve_config` or :func:`_build_specialist`
        raises (Firestore errors, roster-cap exceeded, MCP schema errors, …).
    """
    config = resolve_config(doc_id, account_id, ttl_seconds)
    content_hash = _content_hash(config)
    cache_key: tuple[str, str | None, str] = (doc_id, account_id, content_hash)

    # Note: this probe is outside the cache's internal lock, so a concurrent
    # first-call can cause a genuine hit to be reported as a miss — the same
    # accepted inaccuracy as mcp_pool.py:221-225. Metric accuracy over time is
    # unaffected; individual entries may be one event stale under contention.
    cache_hit = _specialists_cache.get(cache_key) is not None
    agent = _specialists_cache.get_or_build(
        cache_key,
        lambda: _build_specialist(
            config, doc_id, account_id, session_state=session_state
        ),
    )
    # account_id is intentionally omitted — see AH-77 Item E; only non-tenant
    # identifiers are emitted in long-retention telemetry logs.
    logger.info(
        "specialist_agent_resolved",
        extra={"json_fields": {"name": doc_id, "agent_cache_hit": cache_hit}},
    )
    return agent


def available_specialists_provider(context: ReadonlyContext) -> str:
    """Return the ``## Available Specialists`` Markdown block for the root agent.

    Designed as an ADK ``InstructionProvider``-compatible callable
    ``(ReadonlyContext) -> str``.  Reads ``account_id`` from session state,
    lists all agent configs visible to the account, resolves each to a
    ``LlmAgent``, filters to ``ken_e_sub_agent=True`` (the chat-delegation
    gate introduced in AH-82), and formats the result using
    :func:`assemble_available_specialists_block` from ``dispatch.py``.

    Note: ``visible_in_frontend`` is intentionally NOT used as a filter here.
    It controls Workflows-page UI visibility only.  An agent with
    ``visible_in_frontend=False, ken_e_sub_agent=True`` will appear in this
    block and be delegatable, while one with
    ``visible_in_frontend=True, ken_e_sub_agent=False`` will be shown in the
    Workflows page but will not be delegatable from chat.

    Agents that fail to resolve are logged and excluded from the block rather
    than surfacing as errors to the root agent.

    Args:
        context: ADK ``ReadonlyContext`` providing ``context.state``.

    Returns:
        Formatted Markdown string starting with ``"## Available Specialists\\n\\n"``.
    """
    from app.adk.agents.agent_factory.config_loader import (
        FirestoreConnectionError,
    )
    from app.adk.agents.agent_factory.dispatch import (
        assemble_available_specialists_block,
    )

    account_id: str | None = context.state.get("account_id")
    # Phase 3 (AH-62): capture session state once so it can be threaded into
    # resolve_agent → _build_specialist for creds-hash key computation.
    #
    # ADK-version dependency: ``ReadonlyContext.state`` currently returns a
    # ``MappingProxyType`` over ``session.state`` (readonly_context.py), which
    # ``dict()`` casts cleanly. ``CallbackContext.state`` returns ADK's
    # ``State`` object instead, which has ``__getitem__`` but no ``keys()`` /
    # ``__iter__``; ``dict(state)`` on that raises ``KeyError: 0``. The
    # ``attach_specialists_before_agent_callback`` bridge uses
    # ``state.to_dict()`` for exactly this reason — see
    # ``sub_agent_attacher.py``. We mirror that defence here so a future ADK
    # release that aligns ``ReadonlyContext.state`` with ``CallbackContext.state``
    # (or any other shape exposing ``to_dict()``) does not silently break the
    # specialists block. Regression coverage:
    # ``test_real_adk_state_session_state_forwarded`` below.
    state = context.state
    session_state: Mapping[str, Any] = (
        state.to_dict() if hasattr(state, "to_dict") else dict(state)
    )

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
    with block_lock_for(account_id):
        cached = _block_cache.get(account_id)
        if cached is not None and now < cached[1]:
            return cached[0]

    try:
        doc_ids = list_account_agent_configs_cached(account_id)
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
            # AH-82: filter on the explicit delegation gate, not visible_in_frontend.
            # visible_in_frontend drives Workflows-page UI visibility only.
            if not config.ken_e_sub_agent:
                continue
            agent = resolve_agent(doc_id, account_id, session_state=session_state)
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
    with block_lock_for(account_id):
        _block_cache[account_id] = (block, time.monotonic() + _BLOCK_CACHE_TTL)
    return block
