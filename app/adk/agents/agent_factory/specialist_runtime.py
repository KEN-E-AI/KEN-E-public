"""Per-turn specialist resolver for the per-dispatch-agent surface (AH-PRD-09).

Replaces the deploy-time factory model (AH-PRD-02) with a per-turn resolution
path: specialists are resolved from Firestore on each turn (TTL-cached) rather
than baked into the deployed agent artifact.

Four public entry points:

* ``resolve_config`` — TTL-cached ``MergedAgentConfig`` fetch via
  ``get_cached_merged_config``.
* ``resolve_agent`` — LRU-cached ``LlmAgent`` keyed by
  ``(doc_id, account_id, content_hash)``.  Content-hash invalidation means any
  field change to the Firestore config drops the stale ``LlmAgent`` and triggers
  a rebuild on next access.
* ``run`` — dispatch a query to a resolved specialist.  Mirrors
  ``_build_dispatch`` from ``dispatch.py``: review pipeline when
  ``acceptance_criteria`` is non-empty, single-pass via
  ``invoke_agent_with_retry`` otherwise.  Never re-raises — returns an error
  string so the root agent receives graceful degradation.
* ``available_specialists_provider`` — ``InstructionProvider``-compatible
  callable ``(ReadonlyContext) -> str``; returns the "## Available Specialists"
  Markdown block for injection into the root agent's system prompt.

Design notes:
* ``_AgentCache`` is a plain ``collections.OrderedDict``-backed LRU capped at
  256 entries with its own ``threading.Lock``.  The lock is separate from the
  config-cache stripe lock: config reads and agent construction are independent
  critical sections.
* Content hash: ``sha256(MergedAgentConfig.model_dump_json().encode()).hexdigest()``.
  Any field change produces a new hash; the stale ``LlmAgent`` entry is evicted
  on next LRU access via natural ``OrderedDict`` displacement rather than explicit
  deletion.
* Phase 2 (AH-59): ``_build_specialist`` fetches MCP server docs directly from
  Firestore (one ``get()`` per server ID) and calls ``build_toolset_for_doc``.
  Phase 3 (AH-62) will replace this with ``McpToolsetPool.get(server_id)``.
* ``available_specialists_provider`` filters to ``visible_in_frontend=True``
  configs so strategy-pipeline and other hidden agents are excluded from the
  block shown to the root agent.
"""

# NOTE: do NOT add `from __future__ import annotations` here. Dispatch closures
# and InstructionProvider callables passed to LlmAgent are cloudpickled into the
# Agent Engine deployment artifact; deferred (string) annotations don't survive
# the round-trip. Resolving annotations at definition time (no future import)
# matches the pattern in dispatch.py. See the dispatch.py header comment for the
# full ADK/cloudpickle rationale (verified during AH-17 smoke testing).

import collections
import copy
import hashlib
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext

from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.utils.config_cache import get_cached_merged_config
from app.utils.weave_observability import safe_weave_op
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
    """Thread-safe LRU cache for resolved ``LlmAgent`` objects.

    Keyed by ``(doc_id, account_id | None, content_hash)``.  Capped at
    ``maxsize`` entries; the least-recently-used entry is evicted when at
    capacity.  Uses a dedicated ``threading.Lock`` — separate from the
    config-cache stripe locks — because agent construction (the critical
    section on miss) is independent of config fetches.

    Single-flight on cache miss: ``get_or_build`` holds the lock across the
    check-and-populate window so N concurrent cold reads for the same key
    call *builder* exactly once rather than N times (thundering-herd fix).
    """

    def __init__(self, maxsize: int = _AGENT_CACHE_MAX) -> None:
        self._maxsize = maxsize
        self._store: collections.OrderedDict[tuple[str, str | None, str], LlmAgent] = (
            collections.OrderedDict()
        )
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str | None, str]) -> LlmAgent | None:
        """Return the cached agent for *key*, or ``None`` on miss.

        Promotes *key* to the MRU end on hit.
        """
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def put(self, key: tuple[str, str | None, str], agent: LlmAgent) -> None:
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
        builder: Callable[[], LlmAgent],
    ) -> LlmAgent:
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


def _build_specialist(config: MergedAgentConfig, name: str) -> LlmAgent:
    """Construct a new ``LlmAgent`` from a ``MergedAgentConfig``.

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
            # MAX_TOOLS_PER_SPECIALIST is a module-level constant in roster;
            # log the value the resolver actually enforced rather than
            # duplicating the import.
            len(toolsets),
        )
        raise

    return build_agent(config, name=name, tools=tools, config_doc_id=None)


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
) -> LlmAgent:
    """Return a cached ``LlmAgent`` for ``(doc_id, account_id)``.

    Fetches the ``MergedAgentConfig``, computes a content-hash, and returns
    the cached ``LlmAgent`` if one exists with the same
    ``(doc_id, account_id, content_hash)``.  On hash mismatch (config changed
    since last build), a new ``LlmAgent`` is constructed and inserted into the
    LRU cache; the stale entry is evicted naturally when the cache reaches
    capacity.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        account_id: Per-account overlay key.  ``None`` loads the global config.
        ttl_seconds: TTL for the underlying config cache.

    Returns:
        A ready-to-use ``LlmAgent`` with tools wired according to the config.

    Raises:
        Any exception that :func:`resolve_config` or :func:`_build_specialist`
        raises (Firestore errors, roster-cap exceeded, MCP schema errors, …).
    """
    config = resolve_config(doc_id, account_id, ttl_seconds)
    content_hash = _content_hash(config)
    cache_key: tuple[str, str | None, str] = (doc_id, account_id, content_hash)

    return _specialists_cache.get_or_build(
        cache_key, lambda: _build_specialist(config, doc_id)
    )


@safe_weave_op(name="specialist_run")
def run(
    doc_id: str,
    query: str,
    *,
    account_id: str | None = None,
    acceptance_criteria: str = "",
    tool_context: Any | None = None,
    ttl_seconds: int = 60,
) -> str:
    """Resolve and run a specialist, returning the response string.

    Mirrors ``_build_dispatch`` from ``dispatch.py``:

    * When *acceptance_criteria* is non-empty (after sanitisation and the
      ``MAX_CRITERIA_CHARS`` cap), runs the full review-loop pipeline via
      ``build_review_pipeline`` + ``invoke_pipeline``, emits per-iteration
      Weave spans, and returns the ``result`` string from the pipeline outcome.
    * When *acceptance_criteria* is empty, delegates directly to
      ``invoke_agent_with_retry`` using ``DEFAULT_RETRY_CONFIG``.

    Never re-raises — logs the error and returns an error string so the root
    agent receives graceful degradation instead of an unhandled exception.

    Args:
        doc_id: Specialist Firestore document ID.
        query: The query to send to the specialist.
        account_id: Per-account overlay key.
        acceptance_criteria: Optional review-loop acceptance criteria.
        tool_context: Optional ADK ``ToolContext`` from the calling tool.
            When provided, its state is snapshotted and forwarded as the
            initial pipeline state.
        ttl_seconds: TTL for the underlying config and agent caches.

    Returns:
        The specialist's response string, or an error sentinel string on failure.
    """
    from app.adk.agents.utils.agent_retry import (
        DEFAULT_RETRY_CONFIG,
        invoke_agent_with_retry,
    )
    from app.adk.agents.utils.criteria_utils import (
        MAX_CRITERIA_CHARS,
        sanitise_criteria,
    )
    from app.adk.agents.utils.review_pipeline import (
        _check_hallucinated_approval,
        build_review_pipeline,
        extract_iterations,
        extract_pipeline_result,
        get_reviewer_name,
        get_worker_name,
    )
    from app.adk.agents.utils.review_pipeline_tracing import (
        emit_iteration_span,
        set_pipeline_attrs,
    )
    from app.adk.agents.utils.supervisor_utils import invoke_pipeline

    try:
        specialist = resolve_agent(doc_id, account_id, ttl_seconds)
    except Exception as exc:
        logger.error(
            "[SPECIALIST-RUN] Failed to resolve specialist %r: %s",
            doc_id,
            exc,
            exc_info=True,
        )
        return f"Error: specialist {doc_id!r} unavailable"

    initial_state: dict[str, Any] | None = (
        copy.deepcopy(tool_context.state.to_dict())
        if tool_context is not None
        else None
    )

    output_key_prefix = f"{doc_id}_review"

    criteria = acceptance_criteria.strip()
    if len(criteria) > MAX_CRITERIA_CHARS:
        logger.warning(
            "[SPECIALIST-RUN] acceptance_criteria truncated from %d to %d chars",
            len(criteria),
            MAX_CRITERIA_CHARS,
        )
        criteria = criteria[:MAX_CRITERIA_CHARS]
    criteria = sanitise_criteria(criteria)

    try:
        if criteria:
            logger.info(
                "[SPECIALIST-RUN] Building review pipeline for %r (criteria length=%d).",
                doc_id,
                len(criteria),
            )
            pipeline = build_review_pipeline(
                specialist=specialist,
                acceptance_criteria=criteria,
                output_key_prefix=output_key_prefix,
            )
            _text, final_state, events = invoke_pipeline(
                pipeline, query, state=initial_state
            )
            _check_hallucinated_approval(events, output_key_prefix)
            outcome = extract_pipeline_result(final_state, output_key_prefix)
            worker_name = get_worker_name(specialist)
            reviewer_name = get_reviewer_name(output_key_prefix)
            iterations = extract_iterations(
                events, worker_name, reviewer_name, output_key_prefix
            )
            for it in iterations:
                emit_iteration_span(
                    it.iteration, it.specialist_output, it.reviewer_output
                )
            set_pipeline_attrs(
                criteria, final_state, output_key_prefix, len(iterations)
            )
            if not outcome.get("approved"):
                logger.warning(
                    "[SPECIALIST-RUN] Review loop exhausted iterations for %r without approval; "
                    "returning last draft.",
                    doc_id,
                )
            return outcome["result"]

        logger.info(
            "[SPECIALIST-RUN] Single-pass dispatch for %r (no acceptance_criteria).",
            doc_id,
        )
        return invoke_agent_with_retry(
            specialist,
            query,
            state=initial_state,
            retry_config=DEFAULT_RETRY_CONFIG,
        )

    except Exception as exc:
        logger.error(
            "[SPECIALIST-RUN] Error running specialist %r: %s",
            doc_id,
            exc,
            exc_info=True,
        )
        return f"Error dispatching to {doc_id}: specialist unavailable"


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

    specialists: dict[str, LlmAgent] = {}
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
