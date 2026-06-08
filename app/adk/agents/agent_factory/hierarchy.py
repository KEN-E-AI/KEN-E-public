"""Hierarchy builder for the KEN-E agent factory (AH-PRD-09 Phase 2 + AH-75).

`build_hierarchy()` is the deploy-time entry point that builds the root agent
from Firestore configuration. Specialist agents are resolved per-turn by
``specialist_runtime`` rather than baked into the deploy artifact, reducing
deploy-time Firestore reads from N+1 to 1.

AH-75 (Approach 1) replaced the ``delegate_to_specialist`` function tool with
ADK's native ``transfer_to_agent`` + dynamically-managed ``sub_agents``. The
root carries no specialist-dispatch tool; a ``before_agent_callback`` wires
each turn's visible specialists into ``root.sub_agents`` before the LLM is
invoked, so ``transfer_to_agent(agent_name=<doc_id>)`` resolves natively.

  config_loader       (AH-10) — loads + merges the root MergedAgentConfig document
  builder             (AH-15) — constructs LlmAgent with standard ADK callbacks
  specialist_runtime  (AH-59) — available_specialists_provider per-turn provider
  sub_agent_attacher  (AH-75) — runtime sub_agents sync via before_agent_callback
  root_tools_attacher (AH-100) — runtime root.tools sync via before_agent_callback

Deploy-time only: call once in ``deploy_ken_e.py``.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import LlmAgent

import app.adk.tools.agent_tools.google_search  # agent-tool registration (AH-98)
import app.adk.tools.agent_tools.numerical_analyst  # agent-tool registration (AH-149)
import app.adk.tools.function_tools.create_visualization  # default_global registration
import app.adk.tools.todo_list_tools  # noqa: F401  # default_global registration
from app.adk.agents.agent_factory.builder import build_agent
from app.adk.agents.agent_factory.config_loader import (
    FirestoreConnectionError,
    _load_and_merge,
)
from app.adk.agents.agent_factory.model_routing import apply_model_location_env
from shared.account_id_utils import validate_account_id
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

ROOT_CONFIG_ID: str = "ken_e_chatbot"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(project_id: str | None) -> str:
    """Resolve the GCP project ID from the argument or environment.

    Resolution order:
    1. Explicit ``project_id`` argument.
    2. ``GOOGLE_CLOUD_PROJECT_ID`` environment variable.
    3. Hard-coded default ``"ken-e-dev"``.

    Args:
        project_id: Caller-supplied project ID, or ``None`` to use env/default.

    Returns:
        Non-empty project ID string.
    """
    return project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID") or "ken-e-dev"


def _build_firestore_client(project_id: str) -> Any:
    """Create and return a Firestore client for the given project.

    Lazy-imports ``google.auth`` and ``google.cloud.firestore`` so the module
    remains importable in environments where neither package is installed
    (mirrors the pattern in ``mcp.py``).

    Args:
        project_id: GCP project ID.

    Returns:
        ``google.cloud.firestore.Client`` instance.

    Raises:
        Any exception raised by ``google.auth.default()`` or
        ``firestore.Client()`` — callers should wrap in
        ``FirestoreConnectionError``.
    """
    from google.auth import default as google_auth_default
    from google.cloud import firestore

    credentials, _ = google_auth_default()
    return firestore.Client(project=project_id, credentials=credentials)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_hierarchy(
    account_id: str | None = None,
    *,
    project_id: str | None = None,
    db: Any | None = None,
) -> LlmAgent:
    """Build the KEN-E root agent from Firestore configuration.

    Per AH-PRD-09 + AH-75, the root agent carries **no** specialist-dispatch
    tool. Specialist agents are resolved per-turn by ``specialist_runtime`` and
    attached to ``root.sub_agents`` by ``attach_specialists_before_agent_callback``
    so ADK's built-in ``transfer_to_agent`` finds them via ``root.find_agent``.
    This preserves the AH-PRD-09 wins (Firestore-resolved-per-turn, ≤60s
    admin-edit propagation, no redeploy) while routing specialist events
    through ADK's native transfer mechanism so they propagate to the outer
    Runner's event stream (and to Chat + Billing consumers).

    Args:
        account_id: When provided, per-account overlay documents are merged on
            top of the global base config (same semantics as
            ``_load_and_merge``).  Must match ``[a-zA-Z0-9_-]{1,128}``; a
            ``ValueError`` is raised if the format is invalid.
        project_id: GCP project ID used when creating a Firestore client.
            Resolved via argument → ``GOOGLE_CLOUD_PROJECT_ID`` env var →
            ``"ken-e-dev"``.
        db: Pre-built Firestore client (for testing / dependency injection).
            When ``None`` a real client is created from ``project_id`` / env.

    Returns:
        Root ``LlmAgent`` (name ``"ken_e"``) with no specialist-dispatch tool;
        the per-turn Available Specialists block is wired via
        ``instruction_suffix_provider`` and the sub_agents list is populated
        per turn by ``attach_specialists_before_agent_callback``.

    Raises:
        ValueError: When ``account_id`` does not match the required format.
        FirestoreConnectionError: When ``db is None`` and a Firestore client
            cannot be created, or when a Firestore read fails unexpectedly.
        ConfigNotFoundError: When the ``ROOT_CONFIG_ID`` document is absent
            from both the global and account collections.
    """
    # Step 0 — force GOOGLE_CLOUD_LOCATION before any genai.Client is built.
    # ADK's Gemini model reads GOOGLE_CLOUD_LOCATION via os.environ at
    # api_client construction time (cached_property).  On Agent Engine the
    # platform injects this var equal to the engine's deploy region;
    # load_dotenv(..., override=False) cannot win against it.  We write it
    # explicitly here so the model-serving endpoint matches the environment
    # (dev → global, staging/prod → regional).  VERTEX_AI_LOCATION is a
    # separate variable used by vertexai.init() / sandbox_pool and is never
    # touched here.  See app/adk/agents/agent_factory/model_routing.py.
    apply_model_location_env()

    # Step 1 — validate account_id format before touching Firestore.
    if account_id is not None:
        account_id = validate_account_id(account_id)

    # Step 2 — resolve Firestore client.
    if db is None:
        resolved_project_id = _resolve_project_id(project_id)
        try:
            db = _build_firestore_client(resolved_project_id)
        except Exception as exc:
            raise FirestoreConnectionError(
                f"Failed to connect to Firestore for project {resolved_project_id!r}: {exc}"
            ) from exc

    # Step 3 — load root config only. Specialists are resolved per-turn by
    # specialist_runtime; no N+1 read at deploy time.
    root_config = _load_and_merge(db, ROOT_CONFIG_ID, account_id)
    logger.info("Loaded root agent config %r.", ROOT_CONFIG_ID)

    # Step 4 — build the root agent.
    #
    # * instruction_suffix_provider renders the Available Specialists block
    #   per-turn from the TTL-cached Firestore data so admin edits propagate
    #   within 60 s without a redeploy.
    # * additional_before_agent_callbacks wires the same per-turn data into
    #   root.sub_agents via attach_specialists_before_agent_callback. The
    #   "Available Specialists" block and the transfer-target set stay in
    #   sync because both walk the same list_account_agent_configs +
    #   resolve_config(visible_in_frontend) pipeline.
    # * specialists_span_before_agent_callback MUST come AFTER
    #   attach_specialists_before_agent_callback.  The attach callback writes
    #   session.state["_available_specialists"]; the span callback reads it.
    #   Reversing the order would leave the state key absent on every turn,
    #   causing the span callback to take the "missing-key → degradation signal"
    #   branch — which would look identical to a real capture failure (CH-58).
    #
    # Lazy import: avoids circular import at module-load time since
    # agent_factory/__init__.py imports both hierarchy and specialist_runtime,
    # and specialist_runtime imports config_cache which imports agent_factory.
    # AH-98: the root is delegation-only (no MCP servers, no function tools),
    # but it MAY be granted opt-in agent-as-a-tool capabilities — e.g. web
    # search — by listing ``agent.{name}`` ids in ``ken_e_chatbot.tool_ids``.
    # Routing the root build through the shared roster resolver means an admin
    # can give Kinney web search via config alone, with no code change. When
    # ``tool_ids`` is unset the resolver returns ``[]`` (google_search is opt-in
    # / not default_global), preserving the historical ``tools=[]`` root.
    from app.adk.agents.agent_factory.root_tools_attacher import (
        attach_root_tools_before_agent_callback,
    )
    from app.adk.agents.agent_factory.roster import resolve_specialist_roster
    from app.adk.agents.agent_factory.specialist_runtime import (
        available_specialists_provider,
    )
    from app.adk.agents.agent_factory.sub_agent_attacher import (
        AlwaysTrueSubAgentList,
        attach_specialists_before_agent_callback,
        attach_task_subagent,
    )
    from app.adk.agents.orchestration.supervisor import (
        SUPERVISOR_INSTRUCTION_FRAGMENT,
        get_supervisor_function_tools,
    )
    from app.adk.tools.registry.agent_tool_registry import (
        resolve_agent_subagents,
        resolve_isolated_agent_tools,
    )
    from app.adk.tools.registry.tool_registry import get_default_registry
    from app.adk.tracking.callbacks import (
        adk_after_model_callback,
        capture_last_model_output_after_model_callback,
    )
    from app.adk.tracking.specialists_spans import (
        specialists_span_before_agent_callback,
    )

    _default_registry = get_default_registry()
    _root_roster = resolve_specialist_roster(
        "ken_e",
        mcp_toolsets={},
        function_tools=[],
        mcp_server_ids=[],
        agent_subagents=resolve_agent_subagents(_default_registry),
        # AH-PRD-15 re-plan: google_search / numerical_analyst resolve as isolated
        # AgentTools (built-in tool that cannot be a task-mode sub-agent) and flow
        # into ``.tools``; the task-mode lane above is dormant.
        isolated_agent_tools=resolve_isolated_agent_tools(_default_registry),
        tool_ids=getattr(root_config, "tool_ids", None),
        registry=_default_registry,
    )
    # RosterResolution.tools carries the isolated AgentTools (when opted in via
    # tool_ids); .sub_agents carries any task-mode sub-agents (currently none).
    # AH-133: supervisor function tools are appended AFTER resolve_specialist_roster
    # so they bypass the admin tool_ids filter and remain platform-invariant.
    root_function_tools = list(_root_roster.tools) + get_supervisor_function_tools()
    root_agent_subagents = _root_roster.sub_agents

    def _compose_root_instruction_suffix(ctx: Any) -> str:
        return (
            available_specialists_provider(ctx).rstrip()
            + "\n\n"
            + SUPERVISOR_INSTRUCTION_FRAGMENT
        )

    root_agent = build_agent(
        root_config,
        name="ken_e",
        account_id=account_id,
        tools=root_function_tools,
        config_doc_id=ROOT_CONFIG_ID,
        instruction_suffix_provider=_compose_root_instruction_suffix,
        additional_before_agent_callbacks=[
            attach_specialists_before_agent_callback,
            # Per-turn root-tools sync (AH-100): hot-reloads ``ken_e_chatbot.
            # tool_ids`` from the TTL-cached Firestore config so admin edits to
            # the root's tool list take effect within ~60 s without a redeploy.
            # Placed after attach_specialists so both attach callbacks are
            # grouped together before the tracing callback.
            attach_root_tools_before_agent_callback,
            # Ordering constraint: span callback reads the state key written by
            # the attach callback above — must remain AFTER it in this list.
            specialists_span_before_agent_callback,
        ],
        additional_after_model_callbacks=[
            # Ordering constraint: adk_after_model_callback captures thought
            # parts into state["_last_reasoning"] first so the value is
            # available to any future callback that reads it. It no longer
            # strips thought=True parts (AH-89) — the streaming router
            # (chat.py) emits them on the event: reasoning SSE channel.
            # capture_last_model_output_after_model_callback filters
            # thought=True parts independently (see its body in callbacks.py),
            # so temp:_last_model_output contains only user-visible text.
            adk_after_model_callback,
            capture_last_model_output_after_model_callback,
        ],
    )
    logger.info("Built root agent %r.", "ken_e")

    # ADK 2.0 compatibility: ensure DynamicNodeScheduler is activated.
    # Runner._run_node_async checks bool(self.agent.sub_agents) on the original
    # root to decide whether to activate DynamicNodeScheduler. Without the
    # scheduler, transfer_to_agent events are yielded but not dispatched;
    # specialist LLM events never reach the outer stream (zero Billing/Chat
    # token counts). AlwaysTrueSubAgentList.__bool__ returns True even when
    # empty, so the scheduler is always active. build_node().clone() creates a
    # fresh regular [] for the per-turn clone, which _reconcile then populates
    # in-place per turn.
    root_agent.sub_agents = AlwaysTrueSubAgentList()

    # AH-116/AH-117: seed agent-as-tool task-mode sub_agents on the deploy-time
    # root. ``attach_task_subagent`` registers each one in ``root.sub_agents``,
    # sets its parent, AND injects the matching ``_TaskAgentTool`` into
    # ``root.tools`` — the latter is what ADK's per-turn clone shallow-copies so
    # the LLM can dispatch ``request_task_<name>`` (model_post_init, which is the
    # only other place that tool is created, already ran without these
    # sub-agents). The per-turn attach_root_tools_before_agent_callback still
    # reconciles them against hot-reloaded config each turn; this seed ensures
    # the original root carries the full surface for inspection and for any
    # non-cloning deploy path.
    for sub in root_agent_subagents:
        attach_task_subagent(root_agent, sub)

    return root_agent
