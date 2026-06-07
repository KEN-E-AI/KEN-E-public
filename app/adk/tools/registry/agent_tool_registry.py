"""Runtime registry mapping catalogued agent-tool names to task-mode ``LlmAgent`` factories.

AH-98 introduced a third tool kind — an *agent-as-a-tool* using ``AgentTool``. On ADK 2.0,
``AgentTool.run_async`` still discards inner sub-agent events (GitHub ``google/adk-python#3984``,
OPEN), so any ``agent.{name}`` tool materialised as an ``AgentTool`` loses its inner
``usage_metadata`` (uncounted tokens) and inner steps (missing spans): the AH-75 defect on the
most critical agents.

AH-114 migrates this registry to store task-mode ``LlmAgent(mode='task')`` *factories* instead.
ADK 2.0's task-mode dispatch (``request_task_<name>`` / ``complete_task``) propagates inner events
to the outer stream natively (AH-99 probe-1 / probe-4), restoring correct billing and trace coverage.

The registry stores factories (zero-arg callables that build a fresh task-mode ``LlmAgent``), not
built instances: ADK 2.0's ``BaseAgent`` enforces a single parent per sub-agent
(``__set_parent_agent_for_sub_agents`` raises ``already has a parent``), so a shared instance
could be attached to at most one specialist roster. Each :func:`resolve_agent_subagents` /
:func:`get_agent_subagent` call mints a fresh, parentless instance so the same catalogue entry can
be mounted on multiple specialists (and re-mounted across hot-reload rebuilds) without a re-parent
error. (The retired ``AgentTool`` was freely shareable — each ``run_async`` span its own
``InvocationContext`` — but the task-mode primitive is a plain sub-agent and is not.)

The new API is ``register_agent_subagent`` / ``get_agent_subagent`` / ``resolve_agent_subagents``.
The legacy ``register_agent_tool`` / ``resolve_agent_tools`` names remain importable as
compatibility shims until AH-115 / AH-116 update the consumer call sites.

Design reference: AH-PRD-15 §5 (Implementation Outline, row 1), AH-PRD-15 §7 AC #1 + #4.

Lifecycle:
  1. A module that implements an agent sub-agent (e.g.
     ``app/adk/tools/agent_tools/google_search.py``) calls
     :func:`register_agent_subagent` at import time.
  2. ``app/adk/agents/agent_factory/hierarchy.py`` imports those modules at
     startup so the registration side effects run before rosters resolve.
  3. ``specialist_runtime`` calls :func:`resolve_agent_subagents` per build; the
     resolver calls each registered factory to mint a *fresh* ``LlmAgent`` for
     every catalogued ``agent_tools:`` entry. Catalogue entries without a
     registered factory are skipped with a logged warning so the catalogue can
     lead the implementation.

The registry is a process-global singleton — tests should call
:func:`clear_agent_tool_registry` in setup or teardown to avoid leaking
fixtures into adjacent suites.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from google.adk.agents import LlmAgent

if TYPE_CHECKING:
    from app.adk.tools.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

# AgentTool may not exist on ADK 2.0 — import once at module level with a None
# sentinel so the isinstance guard in register_agent_subagent is not re-imported
# on every call.
try:
    from google.adk.tools.agent_tool import AgentTool as _AgentTool
except ImportError:
    _AgentTool = None  # type: ignore[assignment,misc]  # ADK 2.0 path


# Process-global registry. Keyed by the bare tool name (matches
# ``ToolDefinition.name`` and the ``tool_ids`` allow-list's ``agent.{name}``
# suffix). Values are *factories* — zero-arg callables that build a fresh
# task-mode ``LlmAgent`` on each call (AH-114). Storing factories, not built
# instances, is load-bearing: ADK 2.0's ``BaseAgent`` rejects attaching one
# sub-agent to more than one parent, so each resolve must mint a fresh,
# parentless instance (see module docstring).
#
# NOTE (AH-PRD-15 re-plan / AH-121): this task-mode lane is currently DORMANT.
# Both real agent-tools (google_search, numerical_analyst) wrap a built-in tool
# that Gemini forbids alongside any function declaration (search grounding /
# code execution), and ``mode='task'`` injects ``FinishTaskTool`` next to it →
# ``400 ... all search tools``. They are registered on the *isolated* lane below
# (``_ISOLATED_REGISTRY``) instead. The task-mode lane is kept for a future
# multi-tool agent-tool that can tolerate the injected delegation tool.
_REGISTRY: dict[str, Callable[[], LlmAgent]] = {}

# Process-global registry for the *isolated AgentTool* lane (AH-PRD-15 re-plan).
# Values are factories that build a fresh ``AgentTool`` wrapping a leaf whose LLM
# request carries ONLY its built-in tool (google_search grounding /
# code-execution). ``AgentTool`` is the only dispatch mechanism that isolates such
# a leaf (own sub-runner, no transfer/task tool injected). Because
# ``AgentTool.run_async`` drops the leaf's inner ``usage_metadata`` (#3984), each
# such leaf MUST carry the ``capture_agent_tool_usage`` after_model_callback so the
# tokens are still billed — :func:`register_isolated_agent_tool` enforces that.
_ISOLATED_REGISTRY: dict[str, Callable[[], Any]] = {}

# Warn-once latch for the legacy resolve_agent_tools deprecation shim.
_warned: bool = False

# Lock protecting all mutations to _REGISTRY and _warned. Production deploys
# run on Cloud Run where multiple async tasks may import agent-tool modules
# concurrently during instance init; without this lock a read-modify-write on
# _REGISTRY (overwrite check) or _warned (warn-once latch) would be non-atomic.
_REGISTRY_LOCK = threading.Lock()


def task_mode_supported() -> bool:
    """True when the installed ADK's ``LlmAgent`` declares a ``mode`` field (ADK 2.0+).

    Producer modules (e.g. ``agent_tools/google_search.py``) build their task-mode
    ``LlmAgent(mode='task')`` and call :func:`register_agent_subagent` as an
    import-time side effect. The strategy-supervisor deploy tree
    (``deploy_with_sys_version.py``) is FROZEN at ``google-adk==1.34.1`` and imports
    some of those modules (via the strategy ``agents.py`` re-exports). On 1.34.x
    ``LlmAgent`` has no ``mode`` field and its Pydantic model forbids extras, so
    constructing the task-mode sub-agent there raises ``ValidationError`` at import
    and crashes the strategy deploy-tree smoke test. Gate the construction +
    registration on this check so the ADK 2.0 chat tree registers task-mode
    sub-agents while the 1.34.x strategy tree skips them cleanly. See AH-PRD-15 §2
    and ``deployment/ci/scripts/verify_strategy_deploy_tree.py``.
    """
    return "mode" in LlmAgent.model_fields


def register_agent_subagent(name: str, factory: Callable[[], LlmAgent]) -> None:
    """Register a factory that builds a task-mode ``LlmAgent`` for a catalogued entry.

    ``factory`` is a zero-arg callable returning a fresh ``LlmAgent(mode='task')``
    (typically the producer's ``create_<name>_subagent`` constructor). The registry
    stores the *factory*, not a built instance: ADK 2.0 forbids attaching one
    sub-agent to more than one parent, so :func:`resolve_agent_subagents` calls the
    factory per build to mint a fresh, parentless instance for each roster.

    A single instance is constructed here at registration time to validate the
    contract (type / mode / name) so a bad producer fails loudly at import rather
    than at the first resolve. The agent's ``name`` must equal the catalogue
    ``name`` to catch drift between the catalogue id and the instance name early.

    Re-registering the same ``name`` overwrites the previous entry and logs at
    WARNING — in a production deploy this typically means two modules collide on
    a single catalogue name, which is a real bug worth surfacing loudly.

    Args:
        name: Bare tool name; must match the ``name`` field of the corresponding
            ``agent_tools:`` entry in ``tools.yaml``.
        factory: A zero-arg callable producing a task-mode ``LlmAgent``
            (``agent.mode == 'task'`` and ``agent.name == name``).

    Raises:
        TypeError: If the factory produces an ``AgentTool`` (or any non-``LlmAgent``).
        ValueError: If the produced agent's ``mode != 'task'``.
        ValueError: If the produced agent's ``name != name`` (catalogue-vs-instance drift).
    """
    sample = factory()

    if _AgentTool is not None and isinstance(sample, _AgentTool):  # type: ignore[unreachable]
        raise TypeError(
            "register_agent_subagent expects a factory producing an LlmAgent(mode='task'), "
            "got one producing an AgentTool. Build LlmAgent(name=..., mode='task', ...) instead. "
            "See AH-PRD-15 §5 and AH-114."
        )

    if not isinstance(sample, LlmAgent):
        raise TypeError(
            f"register_agent_subagent expects a factory producing an LlmAgent, got "
            f"{type(sample).__name__!r}. Build LlmAgent(name={name!r}, mode='task', ...)."
        )

    if sample.mode != "task":
        raise ValueError(
            f"register_agent_subagent requires mode='task', got mode={sample.mode!r} for "
            f"agent {sample.name!r}. Construct with LlmAgent(name={name!r}, mode='task', ...)."
        )

    if sample.name != name:
        raise ValueError(
            f"Catalogue name {name!r} does not match agent.name {sample.name!r}. "
            f"Stamp the catalogue name at construction: LlmAgent(name={name!r}, mode='task', ...). "
            f"Drift between catalogue id and instance name breaks roster resolution."
        )

    with _REGISTRY_LOCK:
        if name in _REGISTRY:
            logger.warning(
                "Task-mode sub-agent %r is being re-registered, overwriting the previous "
                "entry. Two modules claiming the same catalogue name is almost always a bug; "
                "if this is intentional (e.g. a test fixture), call "
                "``clear_agent_tool_registry()`` between registrations to silence this warning.",
                name,
            )
        _REGISTRY[name] = factory


def get_agent_subagent(name: str) -> LlmAgent | None:
    """Return a *fresh* task-mode ``LlmAgent`` for *name*, or ``None`` if unregistered.

    Each call invokes the registered factory, so the returned agent is a new,
    parentless instance safe to attach to a roster (ADK 2.0 forbids re-parenting a
    sub-agent). Two calls for the same name return distinct objects.
    """
    with _REGISTRY_LOCK:
        factory = _REGISTRY.get(name)
    return factory() if factory is not None else None


def resolve_agent_subagents(registry: ToolRegistry) -> list[LlmAgent]:
    """Return a *fresh* task-mode ``LlmAgent`` for every catalogued ``agent_tools`` entry.

    Iterates the catalogue's ``agent_tools:`` entries (via
    :meth:`ToolRegistry.list_agent_tools`) and calls each one's registered factory
    to build a new, parentless instance. Entries without a registered factory are
    skipped with a logged warning — this lets the catalogue and the implementation
    evolve at different paces (the warning surfaces the gap so a missing
    registration doesn't go unnoticed).

    A fresh instance is built per call (not a cached singleton) because ADK 2.0
    rejects attaching one sub-agent to more than one parent; the same catalogue
    entry may be mounted on several specialist rosters.

    Note: this returns *all* catalogued agent sub-agents, irrespective of
    ``default_global``. The roster resolver applies the per-agent ``tool_ids``
    allowlist (opt-in) on top — see ``agent_factory/roster.py``.

    Args:
        registry: The ToolRegistry to read catalogue entries from. Pass
            ``get_default_registry()`` in production; tests use a fake.

    Returns:
        Ordered list of freshly-built task-mode ``LlmAgent`` instances, matching
        catalogue (YAML) insertion order.
    """
    with _REGISTRY_LOCK:
        snapshot = dict(_REGISTRY)
        isolated_names = set(_ISOLATED_REGISTRY)
    resolved: list[LlmAgent] = []
    for tool_def in registry.list_agent_tools():
        factory = snapshot.get(tool_def.name)
        if factory is None:
            # No task-mode factory. Stay quiet when the entry is handled by the
            # isolated AgentTool lane (the normal case post-AH-PRD-15 re-plan) —
            # only warn for a catalogue entry with no implementation on EITHER lane.
            if tool_def.name not in isolated_names:
                logger.warning(
                    "Agent-tool %r is catalogued in tools.yaml but no factory is "
                    "registered on either the task-mode or isolated lane; skipping. "
                    "Register via ``register_isolated_agent_tool`` (built-in-tool "
                    "leaf) or ``register_agent_subagent`` (task-mode) from the module "
                    "that implements the tool — imported at startup from "
                    "``app/adk/agents/agent_factory/hierarchy.py``.",
                    tool_def.name,
                )
            continue
        resolved.append(factory())
    return resolved


# ---------------------------------------------------------------------------
# Isolated AgentTool lane (AH-PRD-15 re-plan / AH-121)
#
# google_search and numerical_analyst wrap a built-in tool (search grounding /
# code execution) that Gemini rejects alongside any function declaration. The
# only dispatch mechanism that isolates such a leaf is an ADK ``AgentTool`` (own
# sub-runner, no transfer/task tool injected). ``AgentTool.run_async`` drops the
# leaf's inner events incl. ``usage_metadata`` (#3984), so each isolated leaf MUST
# carry the ``capture_agent_tool_usage`` after_model_callback — registration
# enforces it so an isolated AgentTool can never be added without its billing.
# ---------------------------------------------------------------------------


def _leaf_has_billing_callback(agent_tool: Any) -> bool:
    """True iff the AgentTool's wrapped leaf carries ``capture_agent_tool_usage``.

    The leaf's ``after_model_callback`` may be a single callable or a list (ADK
    accepts both). Imported lazily to avoid an import-time dependency on the agent
    layer from this registry module (kept importable in minimal contexts).
    """
    try:
        from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
    except Exception:  # pragma: no cover - billing module always importable
        return False
    leaf = getattr(agent_tool, "agent", None)
    cb = getattr(leaf, "after_model_callback", None)
    if cb is capture_agent_tool_usage:
        return True
    if isinstance(cb, (list, tuple)):
        return capture_agent_tool_usage in cb
    return False


def register_isolated_agent_tool(name: str, factory: Callable[[], Any]) -> None:
    """Register a factory that builds an isolated ``AgentTool`` for *name*.

    ``factory`` is a zero-arg callable returning a fresh ``AgentTool`` whose
    ``.name`` equals *name* (``AgentTool`` inherits ``name=agent.name``, so the
    wrapped leaf must be named *name* to match the ``agent.{name}`` tool id) and
    whose wrapped leaf carries the ``capture_agent_tool_usage``
    after_model_callback.

    A single instance is built here to validate the contract loudly at import.

    Raises:
        TypeError: the factory does not produce an ``AgentTool``.
        ValueError: the AgentTool's ``name`` != *name* (catalogue/instance drift).
        ValueError: the wrapped leaf is missing the billing callback (would
            silently under-bill — the exact #3984 defect this lane prevents).
    """
    sample = factory()

    if _AgentTool is None or not isinstance(sample, _AgentTool):
        raise TypeError(
            "register_isolated_agent_tool expects a factory producing an AgentTool "
            f"(isolated built-in-tool leaf), got {type(sample).__name__!r}. Wrap a leaf "
            f"named {name!r} carrying after_model_callback=capture_agent_tool_usage in "
            "an AgentTool. See AH-PRD-15 §5."
        )

    if sample.name != name:
        raise ValueError(
            f"Catalogue name {name!r} does not match AgentTool.name {sample.name!r}. "
            f"Name the wrapped leaf {name!r} so the tool matches the agent.{name} id."
        )

    if not _leaf_has_billing_callback(sample):
        raise ValueError(
            f"Isolated AgentTool {name!r} is missing the capture_agent_tool_usage "
            "after_model_callback on its wrapped leaf. AgentTool.run_async drops the "
            "leaf's usage_metadata (#3984), so without the callback the tool's tokens "
            "go unbilled. Attach after_model_callback=capture_agent_tool_usage to the "
            "leaf. See app/adk/agents/agent_tool_billing.py and AH-PRD-15 §5."
        )

    with _REGISTRY_LOCK:
        if name in _ISOLATED_REGISTRY:
            logger.warning(
                "Isolated agent-tool %r is being re-registered, overwriting the "
                "previous entry. Two modules claiming the same catalogue name is "
                "almost always a bug.",
                name,
            )
        _ISOLATED_REGISTRY[name] = factory


def get_isolated_agent_tool(name: str) -> Any | None:
    """Return a *fresh* isolated ``AgentTool`` for *name*, or ``None`` if unregistered."""
    with _REGISTRY_LOCK:
        factory = _ISOLATED_REGISTRY.get(name)
    return factory() if factory is not None else None


def resolve_isolated_agent_tools(registry: ToolRegistry) -> list[Any]:
    """Return a *fresh* isolated ``AgentTool`` for every catalogued entry with one.

    Mirrors :func:`resolve_agent_subagents` but for the isolated lane. Iterates the
    catalogue's ``agent_tools:`` entries and calls each registered isolated factory.
    Entries without a registered isolated factory are skipped silently here — they
    may instead be registered on the task-mode lane (or not yet implemented); the
    per-lane resolvers each surface only their own entries. The roster resolver
    applies the per-agent ``tool_ids`` allowlist on top.
    """
    with _REGISTRY_LOCK:
        snapshot = dict(_ISOLATED_REGISTRY)
    resolved: list[Any] = []
    for tool_def in registry.list_agent_tools():
        factory = snapshot.get(tool_def.name)
        if factory is not None:
            resolved.append(factory())
    return resolved


# ---------------------------------------------------------------------------
# Legacy compatibility shims (AH-114 → AH-115 / AH-116 bridge)
#
# The three consumer import sites (hierarchy.py:208, specialist_runtime.py:398,
# root_tools_attacher.py:73) import these names at module load. Deleting them
# outright would crash those modules before AH-115 / AH-116 swap their imports.
# The shims keep the symbols importable; AH-120's no-AgentTool CI guard will
# surface any remaining dead-symbol usage after AH-115 / AH-116 land.
#
# ``register_agent_tool`` raises immediately so callers (producer modules) fail
# loudly at import time rather than silently registering nothing.
# ``resolve_agent_tools`` returns [] and warns once per process.
# ---------------------------------------------------------------------------


def register_agent_tool(name: str, tool: object) -> None:
    """Removed in AH-114 — use ``register_agent_subagent`` instead.

    .. deprecated::
        Raises ``NotImplementedError`` unconditionally. Migrate to
        ``register_agent_subagent(name, create_<name>_subagent)`` (pass the
        factory, not a built instance). See AH-PRD-15 §5 and AH-114.
    """
    raise NotImplementedError(
        "register_agent_tool removed in AH-114; use register_agent_subagent. "
        "Define a factory create_<name>_subagent() -> LlmAgent(name=<catalogue_name>, "
        "mode='task', ...) and call register_agent_subagent(<catalogue_name>, "
        "create_<name>_subagent). See AH-PRD-15 §5."
    )


def get_agent_tool(name: str) -> LlmAgent | None:
    """Removed in AH-114 — use ``get_agent_subagent`` instead.

    Forwarding alias; like :func:`get_agent_subagent`, returns a *fresh* instance
    on each call (not a cached singleton).
    """
    return get_agent_subagent(name)


def resolve_agent_tools(registry: ToolRegistry) -> list[object]:
    """Deprecation shim — returns ``[]`` and logs one WARNING per process.

    .. deprecated::
        Returns an empty list. Consumer call sites (``roster.py``,
        ``specialist_runtime.py``, ``root_tools_attacher.py``) must migrate to
        ``resolve_agent_subagents`` (AH-115 / AH-116).

        Effect during the bridge: ``agent.google_search`` is unassigned to any
        agent (its removal is a no-op), and ``agent.numerical_analyst`` — the only
        live assignment (the GA specialist's ``tool_ids``) — is dropped from its
        roster. The specialist-dispatch topology that consumes these rosters is
        *already* live on ADK 2.0 (``build_hierarchy`` → ``transfer_to_agent``);
        it is not gated. What AH-114 → AH-116 migrate is the *form* of the
        agent-tool (``AgentTool`` → task-mode sub-agent), and AH-121 is the prod
        cutover gate. So this shim removes ``agent.numerical_analyst`` from the
        live GA specialist until AH-115 / AH-116 re-attach it as a task-mode
        sub-agent.

        This IS a user-facing regression for the bridge window, not the removal
        of dead code. On ADK 2.0 ``AgentTool.run_async`` still returns the
        analyst's final answer text to the GA specialist (verified against the
        installed google-adk==2.0.0 source: it returns ``merged_text`` from the
        leaf's last content), so the user-facing math is correct today. What the
        AH-75 defect (GitHub #3984) drops is the inner code-exec events
        (``executable_code`` / ``code_execution_result``) and inner token usage —
        a billing + observability defect, NOT the answer. Because the GA
        specialist instruction forbids inline arithmetic, the chat-engine deploy
        carrying this shim must not precede AH-115 / AH-116. See AH-PRD-15 §5 and
        the AH-114 risk table.
    """
    global _warned
    with _REGISTRY_LOCK:
        should_warn = not _warned
        _warned = True
    if should_warn:
        logger.warning(
            "resolve_agent_tools is a deprecated shim (AH-114). It returns [] so "
            "agent.{name} tools are temporarily disabled on the ADK 2.0 path until "
            "AH-115 (specialist_runtime / roster) and AH-116 (root hot-reload) migrate "
            "their call sites to resolve_agent_subagents. The specialist-dispatch "
            "topology that consumes these rosters is already live on 2.0 (it is not "
            "gated); AH-114-116 migrate the agent-tool form (AgentTool -> task-mode "
            "sub-agent) and AH-121 cuts prod over. Migrate your call site to "
            "resolve_agent_subagents(registry) from "
            "app.adk.tools.registry.agent_tool_registry."
        )
    return []


def clear_agent_tool_registry() -> None:
    """Empty the registry and reset the deprecation-warning latch.

    Test-only — never call from production code.
    """
    global _warned
    with _REGISTRY_LOCK:
        _REGISTRY.clear()
        _ISOLATED_REGISTRY.clear()
        _warned = False


__all__ = [
    "clear_agent_tool_registry",
    # New task-mode API (AH-114)
    "get_agent_subagent",
    # Legacy shims — importable until AH-115 / AH-116 migrate consumers
    "get_agent_tool",
    # Isolated AgentTool lane (AH-PRD-15 re-plan / AH-121)
    "get_isolated_agent_tool",
    "register_agent_subagent",
    "register_agent_tool",
    "register_isolated_agent_tool",
    "resolve_agent_subagents",
    "resolve_agent_tools",
    "resolve_isolated_agent_tools",
    "task_mode_supported",
]
