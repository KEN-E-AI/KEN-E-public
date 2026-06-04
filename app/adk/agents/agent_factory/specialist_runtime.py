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


def _content_hash(
    config: MergedAgentConfig,
    resolved_reviewer_model: str | None = None,
) -> str:
    """Return a sha256 hex digest of ``config``'s JSON representation.

    Any field change (instruction, model, temperature, mcp_servers, …)
    produces a new hash, causing the cached ``LlmAgent`` to be superseded on
    the next ``resolve_agent`` call.

    Args:
        config: The merged agent configuration.
        resolved_reviewer_model: When non-``None``, folded into the hash input
            so that a change to the harness-wide default (AH-93,
            ``system_settings/harness``) propagates to already-cached
            ``LoopAgent`` review pipelines within the TTL window.  The
            per-specialist override from AH-92 is already part of
            ``config.model_dump_json()`` (it is a ``MergedAgentConfig``
            field), so it does not need separate folding.  Only pass a
            non-``None`` value when the specialist uses a review pipeline
            (``config.default_acceptance_criteria`` is set); non-review
            specialists should pass ``None`` to avoid unnecessary cache churn
            on every harness-default flip.
    """
    base = config.model_dump_json()
    if resolved_reviewer_model is not None:
        payload = f"{base}|reviewer={resolved_reviewer_model}"
    else:
        payload = base
    return hashlib.sha256(payload.encode()).hexdigest()


def _resolve_reviewer_model(config: MergedAgentConfig) -> str:
    """Return the reviewer model to use for *config*'s review pipeline (AH-93).

    Resolution chain (highest priority first):

    1. ``config.reviewer_model`` — per-specialist override (AH-92).
    2. ``harness_default_reviewer_model()`` — harness-wide Firestore knob (AH-93).
    3. ``DEFAULT_REVIEWER_MODEL`` — code-level constant (AH-PRD-01 floor).

    The result is resolved **once per ``resolve_agent`` call** and threaded
    into both ``_content_hash`` and ``_build_specialist`` so the two sites
    always see the same value within a single turn (avoids a race if the 60 s
    TTL window expires between the two reads).
    """
    from app.adk.agents.utils.review_pipeline import DEFAULT_REVIEWER_MODEL
    from app.adk.agents.utils.system_settings import harness_default_reviewer_model

    if config.reviewer_model and config.reviewer_model.strip():
        return config.reviewer_model.strip()
    harness_default = harness_default_reviewer_model()
    return harness_default if harness_default else DEFAULT_REVIEWER_MODEL


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


def block_lock_for(account_id: str | None) -> threading.Lock:
    """Return the stripe lock for *account_id*.

    Caller must pre-validate via ``validate_account_id``, or pass ``None`` as the
    dedicated no-account stripe key (``root_tools_attacher`` uses ``None`` so a
    no-account turn cannot collide with a real account literally named
    ``"global"``). ``hash(None)`` is a stable constant, so the ``None`` key maps
    to one consistent stripe.
    """
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
    resolved_reviewer_model: str | None = None,
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
    from app.adk.tools.registry.agent_tool_registry import resolve_agent_tools
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

    # AH-28: track whether any MCP server for this specialist uses ga_oauth.
    # When True, ga_oauth_after_tool_callback is appended to the specialist's
    # after_tool chain so 401 responses from the GA MCP server set
    # _requires_reauth in session state and return a user-visible error.
    # Gating on auth_type (not on config_id) means future custom GA-tool-
    # equipped agents (AH-95) automatically inherit the same reauth handling.
    _has_ga_oauth_server: bool = False

    # AH-95 (Option A): when a user-built custom agent sets tool_ids but leaves
    # mcp_servers empty (AH-PRD-06 §2 — "users see tools, not servers"), derive
    # the server set from the tool_ids prefixes so the toolset loop runs.
    # Triggers only when mcp_servers is falsy AND tool_ids is non-None
    # (the non-None guard preserves legacy tool_ids=None → "every tool" semantics).
    #
    # Security invariants that must not be removed (defence-in-depth):
    # 1. ``_VALID_DOC_ID_RE`` validates each derived server_id before any Firestore
    #    read — rejects injected paths even if a direct Firestore write bypassed
    #    the API's catalogue-validation gate.
    # 2. The ``enabled=True`` check in ``_build_fn`` is the authoritative gate;
    #    a Firestore doc for a retired or non-existent server must stay
    #    ``enabled=False`` to prevent residual access.
    effective_mcp_servers: list[str] = config.mcp_servers or (
        list(per_server_allowed.keys()) if per_server_allowed is not None else []
    )

    if effective_mcp_servers:
        project_id = _resolve_project_id(None)
        db = _build_firestore_client(project_id)

        for server_id in effective_mcp_servers:
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

            # AH-28: lightweight auth_type read — placed after the tool_ids guard
            # so we only read Firestore for servers that will actually be used
            # (avoids an N+1 read for tool-filter-skipped servers).  Fail-safe on
            # any error (missing doc, network blip) — worst case the callback is
            # not attached for this server.
            if not _has_ga_oauth_server:
                try:
                    _snap = db.collection(MCP_COLLECTION).document(server_id).get()
                    if _snap.exists:
                        _server_doc = _snap.to_dict() or {}
                        if _server_doc.get("auth_type") == "ga_oauth":
                            _has_ga_oauth_server = True
                except Exception:
                    logger.warning(
                        "Could not read auth_type for MCP server %r; "
                        "ga_oauth callback will not be attached for this server",
                        server_id,
                    )

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

    # AH-98: resolve the full catalogue of agent-as-a-tool instances (e.g.
    # ``google_search``). The roster resolver attaches them opt-in — only when
    # the spec's ``tool_ids`` lists ``agent.{name}`` — except for any tagged
    # ``default_global``, which attach like default-global function tools.
    agent_tools = resolve_agent_tools(get_default_registry())

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
            agent_tools=agent_tools,
            tool_ids=config.tool_ids,
        )
    except RosterCapExceededError:
        logger.exception(
            "Specialist %r exceeds the %d-tool roster cap; raising.",
            name,
            MAX_TOOLS_PER_SPECIALIST,
        )
        raise

    # AH-28: attach ga_oauth_after_tool_callback to any specialist whose MCP
    # roster includes a server with auth_type=="ga_oauth".  The callback detects
    # 401 responses at the tool boundary, sets _requires_reauth / _reauth_service
    # in session state, and replaces the raw MCP error with a user-visible
    # message.  Gating on auth_type (not on config_id) means custom GA-tool-
    # equipped agents (AH-95) inherit the same handling automatically.
    _additional_after_tool: list[Any] = []
    if _has_ga_oauth_server:
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        _additional_after_tool.append(ga_oauth_after_tool_callback)

    specialist = build_agent(
        config,
        name=name,
        account_id=account_id,
        tools=tools,
        config_doc_id=name,
        additional_after_tool_callbacks=_additional_after_tool or None,
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

    # AH-35: Build the after_agent_callback for Weave span attribute injection.
    # The callback is wired to run immediately BEFORE weave_after_agent_callback
    # (which finishes and pops the agent's span) so weave.get_current_call()
    # resolves to THIS specialist's own span, not the parent/root span.  See
    # _wire_specialist_span_callbacks below.  The closure captures build-time
    # values; cache_hit is always False at build time (the agent is freshly
    # constructed on every cache miss).  Subsequent turns that serve this same
    # agent from the LRU cache reuse the same callback object with
    # cache_hit=False — this is an accepted approximation documented in AH-35
    # §Risks.
    #
    # NOTE: accurate total_iterations tracking is deferred (AH-35). The
    # important per-span attributes are specialist_name, agent_kind, exit_reason,
    # and cache_hit; total_iterations >= 0 satisfies the trace-structure test.
    def _make_specialist_after_agent_callback(
        _specialist_name: str,
        _criteria: str,
        _prefix: str,
        _agent_kind: str,
    ) -> Callable[[Any], None]:
        def _specialist_after_agent_callback(
            callback_context: Any,
        ) -> None:
            from app.adk.agents.utils.review_pipeline_tracing import (
                set_specialist_span_attrs,
            )

            try:
                state_obj = getattr(callback_context, "state", None)
                if state_obj is not None and hasattr(state_obj, "to_dict"):
                    final_state: dict[str, Any] = state_obj.to_dict()
                elif state_obj is not None:
                    final_state = dict(state_obj)
                else:
                    final_state = {}
            except Exception as _exc:
                logger.debug(
                    "after_agent_callback: failed to read state for %r "
                    "— exit_reason will default to 'approved': %s",
                    _specialist_name,
                    _exc,
                )
                final_state = {}

            set_specialist_span_attrs(
                specialist_name=_specialist_name,
                criteria=_criteria,
                final_state=final_state,
                prefix=_prefix,
                total_iterations=0,  # NOTE: accurate counting deferred (AH-35)
                cache_hit=False,  # always False at build time; see module docstring
                agent_kind=_agent_kind,
            )

        return _specialist_after_agent_callback

    def _as_callback_list(value: Any) -> list[Any]:
        """Normalise ADK's ``None | Callable | list[Callable]`` to a list.

        Typed as ``list[Any]`` because the chain mixes callbacks with different
        ADK signatures — the sync AH-35 callback alongside the async
        ``weave_before``/``weave_after`` span callbacks.
        """
        if value is None:
            return []
        if callable(value):
            return [value]
        return list(value)

    def _wire_specialist_span_callbacks(
        agent: Any,
        ah35_callback: Callable[[Any], None],
        *,
        add_weave_span: bool,
    ) -> None:
        """Attach ``ah35_callback`` so it writes onto THIS agent's own Weave span.

        The AH-35 callback must run BEFORE ``weave_after_agent_callback`` —
        which finishes and pops the agent's span — otherwise
        ``weave.get_current_call()`` resolves to the parent (root) span instead
        of this specialist's.  We therefore INSERT the callback immediately
        before ``weave_after_agent_callback`` rather than appending it.

        ``add_weave_span=True`` (the review ``LoopAgent`` path): the agent has no
        Weave span of its own, so we also wire ``weave_before``/``weave_after``
        onto it.  That produces a dedicated span named after the specialist
        ``doc_id`` that wraps the worker/reviewer children — matching
        ``trace-structure-spec.md §14`` — and the AH-35 attrs land on it.

        Pre-installed callbacks are preserved (the chain is normalised to a
        list, not replaced).
        """
        from app.adk.tracking.callbacks import (
            weave_after_agent_callback,
            weave_before_agent_callback,
        )

        after = _as_callback_list(agent.after_agent_callback)

        if add_weave_span:
            before = _as_callback_list(agent.before_agent_callback)
            if weave_before_agent_callback not in before:
                before.insert(0, weave_before_agent_callback)
            agent.before_agent_callback = before
            if weave_after_agent_callback not in after:
                after.append(weave_after_agent_callback)

        if weave_after_agent_callback in after:
            after.insert(after.index(weave_after_agent_callback), ah35_callback)
        else:
            # No weave span finisher present — write last (best effort).
            after.append(ah35_callback)
        agent.after_agent_callback = after

    if not criteria:
        # Single-pass path: the raw LlmAgent already carries
        # weave_after_agent_callback (from build_agent); insert ours before it.
        _cb = _make_specialist_after_agent_callback(
            _specialist_name=name,
            _criteria="",
            _prefix="",
            _agent_kind="single_pass",
        )
        _wire_specialist_span_callbacks(specialist, _cb, add_weave_span=False)
        return specialist

    from app.adk.agents.utils.criteria_utils import (
        MAX_CRITERIA_CHARS,
        sanitise_criteria,
    )
    from app.adk.agents.utils.review_pipeline import (
        DEFAULT_REVIEWER_MODEL,
        build_review_pipeline,
    )

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

    # AH-93: use the pre-resolved reviewer model threaded from ``resolve_agent``
    # when available (covers the chain: per-specialist override → harness default
    # → code constant).  When ``_build_specialist`` is called directly (e.g.
    # from tests) without going through ``resolve_agent``, fall back to the
    # AH-92 per-specialist config field, then to DEFAULT_REVIEWER_MODEL.
    # Use ``is not None`` (not just truth check) so an empty string, were one
    # ever produced by a future caller, falls through rather than being silently
    # used as the model identifier.
    if resolved_reviewer_model is not None:
        reviewer_model: str = resolved_reviewer_model
    elif config.reviewer_model and config.reviewer_model.strip():
        reviewer_model = config.reviewer_model.strip()
    else:
        reviewer_model = DEFAULT_REVIEWER_MODEL

    pipeline = build_review_pipeline(
        specialist=specialist,
        acceptance_criteria=criteria,
        output_key_prefix=f"{name}_review",
        reviewer_model=reviewer_model,
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

    # AH-35: attach the callback to the LoopAgent (pipeline), not the inner
    # specialist worker, so it fires once per outer dispatch — not once per
    # review iteration.  The bare LoopAgent has no Weave span of its own, so
    # add_weave_span=True wires weave_before/after onto it: the attrs land on a
    # dedicated doc_id-named span that wraps the worker/reviewer children.
    _cb_loop = _make_specialist_after_agent_callback(
        _specialist_name=name,
        _criteria=criteria,
        _prefix=f"{name}_review",
        _agent_kind="loop_pipeline",
    )
    _wire_specialist_span_callbacks(pipeline, _cb_loop, add_weave_span=True)

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

    # AH-93: resolve the reviewer model once here — before the hash — so both
    # the cache-key computation and the specialist build see the same value
    # within a single turn (avoids a race if the 60 s system-settings TTL
    # expires between the two sites).  Gate to review-pipeline specialists only
    # so non-review specialists' cache keys are unaffected by harness-default
    # changes.
    criteria = (config.default_acceptance_criteria or "").strip()
    resolved_reviewer: str | None = (
        _resolve_reviewer_model(config) if criteria else None
    )

    content_hash = _content_hash(config, resolved_reviewer_model=resolved_reviewer)
    cache_key: tuple[str, str | None, str] = (doc_id, account_id, content_hash)

    # Note: this probe is outside the cache's internal lock, so a concurrent
    # first-call can cause a genuine hit to be reported as a miss — the same
    # accepted inaccuracy as mcp_pool.py:221-225. Metric accuracy over time is
    # unaffected; individual entries may be one event stale under contention.
    cache_hit = _specialists_cache.get(cache_key) is not None
    agent = _specialists_cache.get_or_build(
        cache_key,
        lambda: _build_specialist(
            config,
            doc_id,
            account_id,
            session_state=session_state,
            resolved_reviewer_model=resolved_reviewer,
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
    ``(ReadonlyContext) -> str``.

    Delegation gate (AH-82): the block lists only specialists with
    ``ken_e_sub_agent=True`` — enforced on both the fast and slow paths below
    (fast path via the attached sub-agent set; slow path via the filter in the
    fallback loop).  ``visible_in_frontend`` is intentionally NOT a filter here;
    it controls Workflows-page UI visibility only.  An agent with
    ``visible_in_frontend=False, ken_e_sub_agent=True`` appears in this block and
    is delegatable, while one with ``visible_in_frontend=True,
    ken_e_sub_agent=False`` is shown on the Workflows page but is not delegatable
    from chat.

    **AH-86 fast path (primary):** When ``context.state["_available_specialists"]``
    is present and non-empty (written by ``attach_specialists_before_agent_callback``
    in ``sub_agent_attacher.py`` before this provider runs), the block is built
    directly from those dicts via
    :func:`assemble_specialists_block_from_state` — with NO call to
    ``list_account_agent_configs_cached``, ``resolve_config``, or
    ``resolve_agent``.  This eliminates the event-loop-blocking
    ``future.result()`` calls inside ``_build_specialist`` / ``_build_skill_toolset``
    that caused the "chat hangs on Reasoning…, no text" symptom.

    **Fallback (slow path):** When ``_available_specialists`` is absent or empty
    (e.g. the before-agent callback did not run, or in tests that exercise the
    full resolution chain), the provider falls back to the existing Firestore
    list + per-specialist ``resolve_agent`` path, with the same ``_block_cache``
    TTL and error-isolation semantics as before AH-86.

    Agents that fail to resolve (slow path only) are logged and excluded from
    the block rather than surfacing as errors to the root agent.

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
        assemble_specialists_block_from_state,
    )

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

    # ------------------------------------------------------------------
    # AH-86 fast path: build block from session state without Firestore
    # ------------------------------------------------------------------
    # ``attach_specialists_before_agent_callback`` writes
    # ``state["_available_specialists"]`` as a list of
    # ``{"name", "description", "agent_id"}`` dicts before ADK invokes this
    # instruction provider.  When present and non-empty, use those dicts
    # directly — no Firestore list, no resolve_config, no resolve_agent, no
    # future.result() blocking.
    state_specialists: list[dict[str, Any]] | None = session_state.get(
        "_available_specialists"
    )
    if state_specialists:
        logger.debug(
            "[AVAILABLE-SPECIALISTS] Fast path: building block from "
            "%d state dicts (no Firestore/agent resolution).",
            len(state_specialists),
        )
        return assemble_specialists_block_from_state(state_specialists)

    # ------------------------------------------------------------------
    # Slow path (fallback): full Firestore list + resolve_agent resolution
    # ------------------------------------------------------------------
    # Reached when _available_specialists is absent (before-agent callback
    # did not run) or empty (no specialists registered for this account).
    # Preserves all pre-AH-86 behaviour: _block_cache TTL, account_id
    # validation, FirestoreConnectionError isolation.
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
    # AH-84: carry human name + title from the resolved config so the slow
    # path produces the same enriched bullets as the fast path.
    metadata: dict[str, dict[str, str | None]] = {}
    for doc_id in doc_ids:
        try:
            config = resolve_config(doc_id, account_id)
            # AH-82: filter on the explicit delegation gate, not visible_in_frontend.
            # visible_in_frontend drives Workflows-page UI visibility only.
            if not config.ken_e_sub_agent:
                continue
            agent = resolve_agent(doc_id, account_id, session_state=session_state)
            specialists[doc_id] = agent
            metadata[doc_id] = {"human_name": config.name, "title": config.title}
        except Exception as exc:
            logger.warning(
                "[AVAILABLE-SPECIALISTS] Could not resolve specialist %r (account=%r): %s",
                doc_id,
                account_id,
                exc,
                exc_info=True,
            )

    block = assemble_available_specialists_block(specialists, metadata=metadata)
    with block_lock_for(account_id):
        _block_cache[account_id] = (block, time.monotonic() + _BLOCK_CACHE_TTL)
    return block
