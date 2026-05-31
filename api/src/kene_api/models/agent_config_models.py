"""Pydantic models for agent configurations stored in Firestore.

These models define the schema for documents in the ``agent_configs/{id}``
collection. They are consumed by:

* ``routers.agent_configs`` — admin CRUD endpoints (GET/PUT)
* ``app.adk.agents.strategy_agent.config_loader`` — agent loading at module import
* ``app.adk.agents.utils.config_cache`` (forthcoming, per Sprint 6 Decision B)

See Sprint 6 Design Decisions in Notion for rationale:

* Decision A — Firestore config schema
* Decision B — 60 s TTL hot-reload cache for instruction/temperature
* Decision C — Per-config history subcollection for audit trail
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from shared.agent_tool_limits import MAX_TOOLS_PER_SPECIALIST
from shared.trace_metadata import SEMVER_PATTERN

# Supported model identifiers. Updated as new Gemini/OpenAI models are released.
SUPPORTED_MODELS: frozenset[str] = frozenset(
    {
        # Gemini 3 models (latest, preview)
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        # Gemini 2.5 models (current stable). 2.0-flash and 2.0-flash-exp
        # were retired upstream and are intentionally not listed here.
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        # Gemini 1.5 models (stable fallback)
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        # OpenAI models (used by formatters)
        "gpt-4o",
        "gpt-4o-2024-08-06",
        "gpt-4o-mini",
        "o1-preview",
        "o1-mini",
    }
)

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Tool IDs are namespaced: ``<mcp_server>.<tool_name>`` for MCP tools (e.g.
# ``google_analytics_mcp.list_ga_accounts``) and ``function.<tool_name>`` for
# built-in function tools (e.g. ``function.create_visualization``). Both halves
# must look like a normalised snake_case identifier — matches the normalisation
# applied by ``ToolDefinition`` and the MCP server document IDs in Firestore.
_TOOL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def _validate_tool_ids_format(value: list[str] | None) -> list[str] | None:
    """Reject malformed tool IDs at the API boundary.

    Pydantic enforces the per-ID ``max_length=80`` and the list-level
    ``max_length=MAX_TOOLS_PER_SPECIALIST`` via ``Annotated[…]``; this validator
    adds the format check and duplicate-detection that don't fit in the type.
    Catalogue cross-check (does this tool actually exist?) happens at the
    router so the model stays free of YAML / Firestore dependencies.
    """
    if value is None:
        return value
    seen: set[str] = set()
    duplicates_set: set[str] = set()
    malformed: list[str] = []
    for tool_id in value:
        if not _TOOL_ID_PATTERN.match(tool_id):
            malformed.append(tool_id)
        if tool_id in seen:
            # Use a set so ``["x", "x", "x"]`` produces ``["x"]`` rather than
            # ``["x", "x"]`` in the error message. Each duplicate ID is
            # reported once.
            duplicates_set.add(tool_id)
        seen.add(tool_id)
    if malformed:
        raise ValueError(
            f"Invalid tool_ids — must be '<server_or_function>.<tool_name>': {malformed!r}"
        )
    if duplicates_set:
        raise ValueError(f"Duplicate tool_ids: {sorted(duplicates_set)!r}")
    return value


# AH-84: character allowlist for agent identity fields (``name``, ``title``).
# These values are interpolated verbatim into the root LLM's system prompt
# inside the Available Specialists block, so unrestricted printable ASCII
# (including newlines and Markdown structural characters) creates a prompt
# injection surface.  The allowlist covers the legitimate identity use-case:
# letters (including common locale variants), digits, spaces, hyphens,
# apostrophes, and periods.  A value like "BEN-E", "O'Brien", or
# "Research Lead 2.0" passes; "Ignore above\n##" does not.
_IDENTITY_CHARS_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 '\-\.]{1,64}$")

# Runtime max_length aligned with _MAX_IDENTITY_CHARS in dispatch.py.
_IDENTITY_MAX_LENGTH: int = 64

# AH-91: hard cap on default_acceptance_criteria length. Mirrors
# MAX_CRITERIA_CHARS in app/adk/agents/utils/criteria_utils.py — duplicated
# intentionally because the API must not import from app/ (see the merge-logic
# comment in routers/agent_configs.py). The ADK runtime additionally sanitises
# and truncates the value at review-pipeline build time; the API stores it
# verbatim and only enforces this length bound.
MAX_ACCEPTANCE_CRITERIA_CHARS: int = 2000

# AH-92: model used by the Generator-Critic reviewer inside the review pipeline.
# Mirrors DEFAULT_REVIEWER_MODEL in app/adk/agents/utils/review_pipeline.py —
# duplicated intentionally (API must not import from app/).
DEFAULT_REVIEWER_MODEL: str = "gemini-2.5-pro"


def _validate_identity_field(value: str | None) -> str | None:
    """Validate that an identity string (name or title) is prompt-safe.

    Returns the stripped value, or raises ``ValueError`` if the value contains
    characters outside the allowlist.
    """
    if value is None:
        return value
    stripped = value.strip()
    if not stripped:
        return None
    if not _IDENTITY_CHARS_RE.match(stripped):
        raise ValueError(
            "may only contain letters, digits, spaces, hyphens, apostrophes, "
            f"and periods — got: {stripped!r}"
        )
    return stripped


class AgentConfigMetadata(BaseModel):
    """Metadata for an agent configuration."""

    version: str = Field(..., description="Version number (e.g., v1.0, v1.1)")
    variant_name: str = Field(..., description="Descriptive variant name")
    experiment_id: str = Field(
        default="baseline", description="Experiment grouping identifier"
    )
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    updated_by: str = Field(..., description="Email or identifier of last updater")
    notes: str = Field(default="", description="Change notes or description")


class AgentConfig(BaseModel):
    """Complete agent configuration as stored in Firestore.

    `temperature` and `max_output_tokens` are flat top-level fields. The
    legacy nested `generate_content_config` wrapper was removed in AH-40.
    The nested ADK SDK shape is reconstructed only at the construction
    boundary (`agent_factory/builder.py` and `strategy_agent/config_loader.py`)
    when a `google.genai.types.GenerateContentConfig` is required.

    Identity is split into three fields:
      * ``config_id`` — the Firestore document ID. Immutable; the routing
        key used by the agent factory (passed to ``LlmAgent.name``).
      * ``title`` — user-editable role description (e.g. "Business Researcher").
      * ``name`` — user-editable human name (e.g. "Dave"). Optional.
    """

    name: str | None = Field(
        None,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Human name (e.g. 'Dave'). Optional.",
    )
    title: str | None = Field(
        None,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Role description (e.g. 'Business Researcher').",
    )
    model: str = Field(..., description="Model identifier")
    description: str = Field(..., description="Agent description")
    instruction: str = Field(..., description="Agent instruction/prompt")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=2500, ge=100, le=65535)
    tool_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional per-tool allowlist (AH-PRD-06). None=legacy "
            "(all tools from attached mcp_servers); []=no tools; "
            "[…]=explicit subset."
        ),
    )

    # AH-91 (surfaces AH-75 / AH-PRD-09 review-loop config). When set to a
    # non-empty string, the ADK runtime wraps the specialist in a worker/reviewer
    # review pipeline keyed on these criteria; None/empty = single-pass. Stored
    # verbatim — the runtime sanitises + truncates at pipeline-build time.
    default_acceptance_criteria: str | None = Field(
        None,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
        description=(
            "Review-loop acceptance criteria (AH-75 / AH-PRD-09). When set, the "
            "specialist runs a worker/reviewer loop against these criteria; "
            "None/empty disables the review pipeline."
        ),
    )

    # AH-92: model used by the Generator-Critic reviewer inside the review
    # pipeline (AH-75 / AH-PRD-09). None → runtime falls back to
    # DEFAULT_REVIEWER_MODEL. Stored verbatim — write models enforce the
    # supported-model allowlist; the read model does not to avoid silent doc
    # skipping if an out-of-band write stores an unrecognised value.
    reviewer_model: str | None = Field(
        None,
        description=(
            "Model for the review-loop reviewer agent (AH-92 / AH-PRD-09). "
            "None/omit = use DEFAULT_REVIEWER_MODEL. Only meaningful when "
            "default_acceptance_criteria is also set."
        ),
    )

    # AH-82: explicit chat-delegation gate, decoupled from UI visibility.
    # True (default) → delegatable from chat; False → excluded from
    # root.sub_agents and the Available Specialists block. Carried on the read
    # model so the global GET/PUT responses surface the stored value (docs that
    # predate the field load as the True default).
    ken_e_sub_agent: bool = True

    metadata: AgentConfigMetadata

    @field_validator("name", "title", mode="before")
    @classmethod
    def _validate_identity(cls, v: str | None) -> str | None:
        return _validate_identity_field(v)

    @field_validator("tool_ids")
    @classmethod
    def _validate_tool_ids(cls, v: list[str] | None) -> list[str] | None:
        return _validate_tool_ids_format(v)


class AgentConfigUpdate(BaseModel):
    """Request body for PUT /api/v1/agent-configs/{id}.

    All fields except ``updated_by`` are optional to allow partial updates.

    AH-PRD-06 note: ``tool_ids`` is intentionally NOT on this model. The
    global PUT endpoint is admin-only and edits the canonical
    ``agent_configs/{id}`` document; per-agent tool selection lives on the
    per-account overlay (see ``AgentConfigOverlayUpdate``). Adding
    ``tool_ids`` here would let an admin shape the global default, which
    isn't a customer scenario today — keep the surface narrow.
    """

    name: str | None = Field(
        None,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Human name (e.g. 'Dave'). Optional.",
    )

    title: str | None = Field(
        None,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Role description (e.g. 'Business Researcher').",
    )

    instruction: str | None = Field(
        None,
        min_length=10,
        max_length=50000,
        description="Agent instruction/prompt",
    )

    model: str | None = Field(
        None,
        pattern=r"^(gemini-[\d]+-[\w-]+|gemini-[\d\.]+[-\w]+|gpt-[\w-]+|o1-[\w-]+)$",
        description="Model identifier (Gemini or OpenAI model)",
    )

    description: str | None = Field(
        None, min_length=10, max_length=1000, description="Agent description"
    )

    temperature: float | None = Field(
        None, ge=0.0, le=1.0, description="Generation temperature (0.0-1.0)"
    )

    max_output_tokens: int | None = Field(
        None,
        ge=100,
        le=65535,
        description="Maximum output tokens (100-65535)",
    )

    version: str | None = Field(
        None,
        description="Version string in semver format (e.g., v1.0.0)",
    )

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("v"):
            v = f"v{v}"
        if not SEMVER_PATTERN.match(v):
            raise ValueError(
                f"Invalid version '{v}'. "
                f"Please use semver format, e.g. v1.0.0 or v2.1.3"
            )
        return v

    variant_name: str | None = Field(
        None, min_length=1, max_length=100, description="Descriptive variant name"
    )

    experiment_id: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Experiment grouping identifier",
    )

    updated_by: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email of person making update",
    )

    notes: str = Field(
        default="", max_length=5000, description="Notes about this change"
    )

    # AH-91: review-loop acceptance criteria (AH-75 / AH-PRD-09). Nullable —
    # the global PUT handler uses model_fields_set so omitting leaves the stored
    # value untouched while an explicit null clears it.
    default_acceptance_criteria: str | None = Field(
        None,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
        description=(
            "Review-loop acceptance criteria (AH-75 / AH-PRD-09). Omit to leave "
            "the existing value untouched; send null to clear (disable the "
            "review pipeline)."
        ),
    )

    # AH-92: reviewer model for the Generator-Critic loop (AH-75 / AH-PRD-09).
    # Nullable — the global PUT handler uses model_fields_set so omitting
    # leaves the stored value untouched while an explicit null resets to the
    # runtime default.
    reviewer_model: str | None = Field(
        None,
        pattern=r"^(gemini-[\d]+-[\w-]+|gemini-[\d\.]+[-\w]+|gpt-[\w-]+|o1-[\w-]+)$",
        description=(
            "Model for the review-loop reviewer agent (AH-92 / AH-PRD-09). "
            "Omit to leave the existing value untouched; send null to reset "
            "to DEFAULT_REVIEWER_MODEL."
        ),
    )

    # AH-82: explicit delegation gate — controls whether this agent is
    # attachable to root.sub_agents independent of visible_in_frontend.
    ken_e_sub_agent: bool | None = Field(
        None,
        description=(
            "True = delegatable from chat; False = excluded from sub_agents "
            "and Available Specialists block. Independent of visible_in_frontend."
        ),
    )

    @field_validator("name", "title", mode="before")
    @classmethod
    def _validate_identity(cls, v: str | None) -> str | None:
        return _validate_identity_field(v)

    @field_validator("updated_by")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """``updated_by`` must look like an email address."""
        if not _EMAIL_PATTERN.match(v):
            raise ValueError("updated_by must be a valid email address")
        return v

    @field_validator("model")
    @classmethod
    def validate_model_exists(cls, v: str | None) -> str | None:
        """Validate model ID is a known Gemini or OpenAI model."""
        if v is None:
            return v

        if v not in SUPPORTED_MODELS:
            gemini_models = sorted(
                m for m in SUPPORTED_MODELS if m.startswith("gemini")
            )
            openai_models = sorted(
                m for m in SUPPORTED_MODELS if not m.startswith("gemini")
            )
            raise ValueError(
                f"Model '{v}' is not supported.\n"
                f"Supported Gemini models: {', '.join(gemini_models)}\n"
                f"Supported OpenAI models: {', '.join(openai_models)}"
            )

        return v

    # AH-92: reviewer model must be a known supported model (same allowlist as
    # ``model``). Pattern on the field handles shape; this cross-checks the
    # exact supported set so an invented-but-structurally-valid string is
    # rejected at the write boundary.
    @field_validator("reviewer_model")
    @classmethod
    def validate_reviewer_model_exists(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_MODELS:
            raise ValueError(
                f"reviewer_model '{v}' is not supported. "
                f"Supported models: {sorted(SUPPORTED_MODELS)!r}"
            )
        return v


class ConfigAuditEntry(BaseModel):
    """Audit-trail entry for a single config change.

    Written to a per-config history subcollection at
    ``{collection}/{id}/history/{timestamp}`` after every successful PUT.

    ``doc_type`` distinguishes between agent configs and MCP server configs so
    a single reader can reconstruct history across both domains.

    See Sprint 6 Decision C for rationale.
    """

    action: str = Field(
        ..., description="One of: created, updated, deleted, viewed, reverted"
    )
    doc_type: str = Field(..., description="One of: agent_config, mcp_server_config")
    doc_id: str = Field(..., description="ID of the config document being audited")

    user_id: str = Field(..., description="Firebase UID of the user making the change")
    user_email: str = Field(..., description="Email of the user making the change")
    timestamp: str = Field(..., description="ISO-8601 timestamp of the change")
    request_id: str | None = Field(
        None, description="X-Request-Id for tracing, if available"
    )

    version_before: str | None = Field(
        None, description="Semver version of the config before this change"
    )
    version_after: str = Field(
        ..., description="Semver version of the config after this change"
    )

    fields_changed: list[str] = Field(
        default_factory=list,
        description="List of field names that changed (e.g., ['instruction', 'temperature'])",
    )
    changes: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Per-field before/after dictionary, e.g. "
            "{'temperature': {'before': 0.3, 'after': 0.5}}."
        ),
    )


class MergedAgentConfig(BaseModel):
    """Per-account merged agent config response.

    Returned by GET /api/v1/accounts/{account_id}/agent-configs/[{config_id}].
    Merges global ``agent_configs/{id}`` with any per-account overlay at
    ``accounts/{account_id}/agent_configs/{id}``.

    Uses ``extra="forbid"`` (AH-40) so any storage divergence — including the
    legacy nested ``generate_content_config`` wrapper — fails loud at validation
    time rather than silently dropping data. ``_merge_from_data`` is responsible
    for stripping storage-internal fields (see ``_STORAGE_INTERNAL_FIELDS`` in
    ``routers/agent_configs.py``) before validation.
    """

    model_config = {"extra": "forbid"}

    config_id: str = Field(..., description="Document ID of this agent config")
    name: str | None = Field(
        None,
        max_length=100,
        description="Human name (e.g. 'Dave'). Optional, user-editable.",
    )
    title: str | None = Field(
        None,
        max_length=100,
        description="Role description (e.g. 'Business Researcher'). User-editable.",
    )
    instruction: str = Field(..., description="Agent instruction/prompt")
    model: str = Field(..., description="Model identifier")

    description: str | None = Field(None, description="Agent description")

    # AH-91 (surfaces AH-75 / AH-PRD-09 review-loop config). Adding this field
    # is what un-hides agents whose Firestore doc carries it: under
    # extra="forbid" the doc previously failed validation and was silently
    # dropped from the list. Overlay value wins over global via the merge.
    #
    # Deliberately NOT length-bounded here (unlike the write models): this is the
    # read/merge model, and a hard max_length would re-introduce the very bug
    # this field fixes — a stored value over MAX_ACCEPTANCE_CRITERIA_CHARS
    # (written out-of-band by a seed or a future ADK write, since the runtime
    # only truncates at pipeline-build time, not at write time) would raise
    # ValidationError in _merge_from_data and the list endpoint would silently
    # skip the doc again. Stored values pass through verbatim on read; the write
    # surfaces (AgentConfig / *Create / *Update / *OverlayUpdate) enforce the cap.
    default_acceptance_criteria: str | None = Field(
        None,
        description=(
            "Review-loop acceptance criteria (AH-75 / AH-PRD-09). When set, the "
            "specialist runs a worker/reviewer loop against these criteria; "
            "None/empty disables the review pipeline."
        ),
    )

    # AH-92: model used by the Generator-Critic reviewer (AH-75 / AH-PRD-09).
    # Deliberately NOT pattern-validated here (read/merge model): an unrecognised
    # model stored out-of-band must still list, not fail validation silently.
    # The write surfaces (AgentConfigUpdate / Create / OverlayUpdate) enforce
    # the supported-model pattern.
    reviewer_model: str | None = Field(
        None,
        description=(
            "Model for the review-loop reviewer agent (AH-92 / AH-PRD-09). "
            "None = runtime falls back to DEFAULT_REVIEWER_MODEL."
        ),
    )

    temperature: float | None = Field(None, ge=0.0, le=1.0)
    max_output_tokens: int | None = Field(None, ge=100, le=65535)
    code_execution_enabled: bool = False
    mcp_servers: list[str] = Field(default_factory=list)

    skill_ids: list[str] = Field(default_factory=list)
    tool_ids: list[str] | None = Field(
        default=None,
        description=(
            "Per-tool allowlist (AH-PRD-06). None on legacy agents — preserved "
            "verbatim on load."
        ),
    )
    sandbox_code_executor_enabled: bool = False
    response_schema: dict | None = None

    # AH-89 — Gemini thought emission. None = thinking disabled; non-negative
    # int = explicit token budget (e.g. 2048); -1 = model picks dynamically.
    # Read model only — the Create/Update/Overlay write surfaces do not yet
    # expose this field (a future admin-UI story will add the form input).
    # The seed script (migrate_chatbot_to_firestore.py) is the source of truth.
    thinking_budget: int | None = None

    @field_validator("thinking_budget")
    @classmethod
    def _validate_thinking_budget(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v == -1:
            return v  # -1 = model picks budget dynamically
        if v < 0:
            raise ValueError(
                "thinking_budget must be None, -1 (dynamic), or a non-negative int"
            )
        return v

    # Phase 3 flags (AH-18)
    available_to_copy: bool = True
    automatically_available: bool = True
    visible_in_frontend: bool = True

    # AH-82: explicit delegation gate — decoupled from UI visibility.
    # True (default) → delegatable from chat; False → excluded from sub_agents
    # and the Available Specialists block even if visible_in_frontend=True.
    ken_e_sub_agent: bool = True

    # Discriminator populated by the merge logic
    customization_status: str = Field(
        default="default",
        description='One of "default", "customized", "custom_agent"',
    )
    based_on_version: int | None = Field(
        None,
        description="Major version of the global config this overlay was forked from",
    )


class AgentConfigCreate(BaseModel):
    """POST /api/v1/accounts/{account_id}/agent-configs/ request body.

    Creates a custom agent scoped to this account.  The server generates a
    ``custom_{uuid8}`` config_id; callers never set it.
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Role description (e.g. 'Business Researcher'). Required.",
    )
    name: str | None = Field(
        None,
        max_length=_IDENTITY_MAX_LENGTH,
        description="Human name (e.g. 'Dave'). Optional.",
    )
    instruction: str = Field(
        ..., min_length=10, max_length=50000, description="Agent instruction/prompt"
    )
    model: str = Field(..., description="Model identifier")

    description: str | None = Field(None, min_length=10, max_length=1000)
    temperature: float | None = Field(None, ge=0.0, le=1.0)
    skill_ids: list[Annotated[str, Field(max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    tool_ids: list[Annotated[str, Field(max_length=80)]] | None = Field(
        default=None,
        max_length=MAX_TOOLS_PER_SPECIALIST,
        description=(
            "Per-tool allowlist (AH-PRD-06). Omit / null = all tools from the "
            "agent's attached MCP servers; empty list = no tools; otherwise an "
            "explicit subset of <server>.<tool> / function.<tool> IDs."
        ),
    )
    sandbox_code_executor_enabled: bool = False

    # AH-91: optional review-loop acceptance criteria (AH-75 / AH-PRD-09) for a
    # custom agent. Omit / null = single-pass (no review loop).
    default_acceptance_criteria: str | None = Field(
        None,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
        description=(
            "Review-loop acceptance criteria (AH-75 / AH-PRD-09). When set, the "
            "custom agent runs a worker/reviewer loop against these criteria."
        ),
    )

    # AH-92: optional reviewer model for the Generator-Critic loop. Omit / null
    # = runtime falls back to DEFAULT_REVIEWER_MODEL.
    reviewer_model: str | None = Field(
        None,
        pattern=r"^(gemini-[\d]+-[\w-]+|gemini-[\d\.]+[-\w]+|gpt-[\w-]+|o1-[\w-]+)$",
        description=(
            "Model for the review-loop reviewer agent (AH-92 / AH-PRD-09). "
            "None/omit = use DEFAULT_REVIEWER_MODEL."
        ),
    )

    # AH-82: explicit delegation gate — True (default) means this custom agent
    # is delegatable from chat.
    ken_e_sub_agent: bool = True

    @field_validator("name", "title", mode="before")
    @classmethod
    def _validate_identity(cls, v: str | None) -> str | None:
        return _validate_identity_field(v)

    @field_validator("model")
    @classmethod
    def validate_model_exists(cls, v: str) -> str:
        if v not in SUPPORTED_MODELS:
            gemini_models = sorted(
                m for m in SUPPORTED_MODELS if m.startswith("gemini")
            )
            openai_models = sorted(
                m for m in SUPPORTED_MODELS if not m.startswith("gemini")
            )
            raise ValueError(
                f"Model '{v}' is not supported.\n"
                f"Supported Gemini models: {', '.join(gemini_models)}\n"
                f"Supported OpenAI models: {', '.join(openai_models)}"
            )
        return v

    # AH-92: same SUPPORTED_MODELS cross-check as model.
    @field_validator("reviewer_model")
    @classmethod
    def validate_reviewer_model_exists(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_MODELS:
            raise ValueError(
                f"reviewer_model '{v}' is not supported. "
                f"Supported models: {sorted(SUPPORTED_MODELS)!r}"
            )
        return v

    @field_validator("tool_ids")
    @classmethod
    def _validate_tool_ids(cls, v: list[str] | None) -> list[str] | None:
        return _validate_tool_ids_format(v)


class AgentConfigOverlayUpdate(BaseModel):
    """PUT /api/v1/accounts/{account_id}/agent-configs/{config_id} request body.

    All fields are optional — only fields present in the request body are
    written to the overlay document.  A body with zero fields writes an empty
    overlay doc (``customization_status="customized"``).
    """

    name: str | None = Field(None, max_length=_IDENTITY_MAX_LENGTH)
    title: str | None = Field(None, max_length=_IDENTITY_MAX_LENGTH)
    instruction: str | None = Field(None, min_length=10, max_length=50000)
    model: str | None = Field(None, max_length=100)
    description: str | None = Field(None, min_length=10, max_length=1000)
    temperature: float | None = Field(None, ge=0.0, le=1.0)
    max_output_tokens: int | None = Field(None, ge=100, le=65535)
    skill_ids: list[Annotated[str, Field(max_length=50)]] | None = Field(
        None, max_length=20
    )
    tool_ids: list[Annotated[str, Field(max_length=80)]] | None = Field(
        default=None,
        max_length=MAX_TOOLS_PER_SPECIALIST,
        description=(
            "Per-tool allowlist (AH-PRD-06). Omitting the field leaves any "
            "existing overlay value untouched; sending null clears the overlay "
            "back to legacy 'all tools' behaviour; sending a list (including "
            "[]) writes that exact selection."
        ),
    )
    sandbox_code_executor_enabled: bool | None = None

    # AH-91: per-account overlay for the review-loop acceptance criteria
    # (AH-75 / AH-PRD-09). Omitting the field leaves any existing overlay value
    # untouched (exclude_unset); sending null clears it; a string overlays the
    # global value.
    default_acceptance_criteria: str | None = Field(
        None,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
        description=(
            "Review-loop acceptance criteria (AH-75 / AH-PRD-09). Omit to leave "
            "the existing overlay value untouched; send null to clear; a string "
            "overlays the global default."
        ),
    )

    # AH-92: per-account overlay for the reviewer model (AH-75 / AH-PRD-09).
    # Omitting the field leaves any existing overlay value untouched
    # (exclude_unset); sending null resets to DEFAULT_REVIEWER_MODEL; a string
    # overlays the global default.
    reviewer_model: str | None = Field(
        None,
        pattern=r"^(gemini-[\d]+-[\w-]+|gemini-[\d\.]+[-\w]+|gpt-[\w-]+|o1-[\w-]+)$",
        description=(
            "Model for the review-loop reviewer agent (AH-92 / AH-PRD-09). "
            "Omit to leave the existing overlay value untouched; send null to "
            "reset to DEFAULT_REVIEWER_MODEL."
        ),
    )

    # AH-82: per-account overlay can set the delegation gate independently of
    # visible_in_frontend.  Omitting the field leaves the existing overlay value
    # untouched; explicit True/False writes that selection.
    ken_e_sub_agent: bool | None = Field(
        None,
        description=(
            "True = delegatable from chat; False = excluded from sub_agents "
            "and Available Specialists block. Independent of visible_in_frontend. "
            "Omit to leave the existing overlay value untouched."
        ),
    )

    @field_validator("name", "title", mode="before")
    @classmethod
    def _validate_identity(cls, v: str | None) -> str | None:
        return _validate_identity_field(v)

    @field_validator("model")
    @classmethod
    def validate_model_exists(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_MODELS:
            gemini_models = sorted(
                m for m in SUPPORTED_MODELS if m.startswith("gemini")
            )
            openai_models = sorted(
                m for m in SUPPORTED_MODELS if not m.startswith("gemini")
            )
            raise ValueError(
                f"Model '{v}' is not supported.\n"
                f"Supported Gemini models: {', '.join(gemini_models)}\n"
                f"Supported OpenAI models: {', '.join(openai_models)}"
            )
        return v

    # AH-92: same SUPPORTED_MODELS cross-check as model.
    @field_validator("reviewer_model")
    @classmethod
    def validate_reviewer_model_exists(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SUPPORTED_MODELS:
            raise ValueError(
                f"reviewer_model '{v}' is not supported. "
                f"Supported models: {sorted(SUPPORTED_MODELS)!r}"
            )
        return v

    @field_validator("tool_ids")
    @classmethod
    def _validate_tool_ids(cls, v: list[str] | None) -> list[str] | None:
        return _validate_tool_ids_format(v)


__all__ = [
    "DEFAULT_REVIEWER_MODEL",
    "MAX_ACCEPTANCE_CRITERIA_CHARS",
    "MAX_TOOLS_PER_SPECIALIST",
    "SUPPORTED_MODELS",
    "AgentConfig",
    "AgentConfigCreate",
    "AgentConfigMetadata",
    "AgentConfigOverlayUpdate",
    "AgentConfigUpdate",
    "ConfigAuditEntry",
    "MergedAgentConfig",
]
