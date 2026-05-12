"""
Config loader for the agent factory.

Reads agent configurations from Firestore and merges per-account overlay
documents on top of global base configs. This is the Phase 1 implementation
(AH-10); agent construction (build_agent) lands in AH-15.
"""

import os
from typing import Literal

from google.auth import default as google_auth_default
from google.cloud import firestore
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class AgentFactoryConfigError(Exception):
    """Base exception for agent factory config errors."""


class ConfigNotFoundError(AgentFactoryConfigError):
    """Raised when the requested config document does not exist in Firestore."""


class ConfigValidationError(AgentFactoryConfigError):
    """Raised when the config document fails Pydantic validation."""


class FirestoreConnectionError(AgentFactoryConfigError):
    """Raised when a Firestore operation fails unexpectedly."""


class MergedAgentConfig(BaseModel):
    # AH-40: strict — flatten storage shape, reject the legacy nested
    # ``generate_content_config`` wrapper so backfill misses fail loud.
    model_config = ConfigDict(extra="forbid")

    instruction: str
    model: str

    description: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    code_execution_enabled: bool = False
    mcp_servers: list[str] = Field(default_factory=list)

    skill_ids: list[str] = Field(default_factory=list)
    sandbox_code_executor_enabled: bool = False
    response_schema: dict | None = None

    # Phase 3 (AH-18 / PRD §4) — Global config flags
    available_to_copy: bool = True
    automatically_available: bool = True
    visible_in_frontend: bool = True

    based_on_version: int | None = None
    customization_status: Literal["default", "customized", "custom_agent"] = "default"

    metadata: dict | None = None


# Storage-internal fields that live on Firestore docs but are not part of
# the ``MergedAgentConfig`` schema. ``_build_config`` strips these before
# validation since ``extra="forbid"`` would otherwise reject them.
#
# ``deployment_status`` is written by MER-E (sister repo) onto the shared
# ``agent_configs/{id}`` docs. The factory doesn't consume it; strip it
# so an MER-E-touched doc still validates here.
_STORAGE_INTERNAL_FIELDS: frozenset[str] = frozenset(
    {"name", "created_at", "updated_at", "created_by", "deployment_status"}
)


def _resolve_project_id(project_id: str | None) -> str:
    if project_id:
        return project_id
    return os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")


def _build_firestore_client(project_id: str) -> firestore.Client:
    credentials, _ = google_auth_default()
    return firestore.Client(project=project_id, credentials=credentials)


def _doc_to_dict_or_none(doc: firestore.DocumentSnapshot) -> dict | None:
    if not doc.exists:
        return None
    return doc.to_dict() or {}


def load_agent_config(
    config_id: str,
    account_id: str | None = None,
    project_id: str | None = None,
) -> MergedAgentConfig:
    """Load and optionally merge a per-account overlay on top of a global agent config.

    Args:
        config_id: Document ID in the ``agent_configs`` collection.
        account_id: When provided, reads ``accounts/{account_id}/agent_configs/{config_id}``
            and merges it (overlay wins per top-level field) with the global doc.
        project_id: GCP project ID. Resolved via argument → env var
            ``GOOGLE_CLOUD_PROJECT_ID`` → ``"ken-e-dev"``.

    Returns:
        Validated ``MergedAgentConfig`` with ``customization_status`` and
        ``based_on_version`` set according to which documents were found.

    Raises:
        ConfigNotFoundError: Neither global nor overlay document exists.
        ConfigValidationError: The merged dict fails Pydantic validation.
        FirestoreConnectionError: An unexpected error occurred communicating with Firestore.
    """
    resolved_project_id = _resolve_project_id(project_id)

    try:
        db = _build_firestore_client(resolved_project_id)
    except Exception as e:
        raise FirestoreConnectionError(
            f"Failed to connect to Firestore for project {resolved_project_id!r}: {e}"
        ) from e

    try:
        config = _load_and_merge(db, config_id, account_id)
        logger.info(
            f"Loaded agent config {config_id!r} "
            f"(account={account_id!r}, status={config.customization_status!r})"
        )
        return config
    except (ConfigNotFoundError, ConfigValidationError):
        raise
    except Exception as e:
        raise FirestoreConnectionError(
            f"Unexpected Firestore error loading config {config_id!r}: {e}"
        ) from e


def _load_and_merge(
    db: firestore.Client,
    config_id: str,
    account_id: str | None,
) -> MergedAgentConfig:
    global_data = _doc_to_dict_or_none(
        db.collection("agent_configs").document(config_id).get()
    )

    if account_id is None:
        if global_data is None:
            raise ConfigNotFoundError(
                f"Config {config_id!r} not found in agent_configs"
            )
        return _build_config(global_data, "default", None)

    overlay_data = _doc_to_dict_or_none(
        db.collection("accounts")
        .document(account_id)
        .collection("agent_configs")
        .document(config_id)
        .get()
    )

    if global_data is not None and overlay_data is not None:
        merged = {**global_data, **overlay_data}
        bov = overlay_data.get("based_on_version")
        return _build_config(merged, "customized", bov)

    if global_data is not None and overlay_data is None:
        return _build_config(global_data, "default", None)

    if global_data is None and overlay_data is not None:
        bov = overlay_data.get("based_on_version")
        return _build_config(overlay_data, "custom_agent", bov)

    raise ConfigNotFoundError(
        f"Config {config_id!r} not found globally or under account {account_id!r}"
    )


def _build_config(
    raw: dict,
    status: Literal["default", "customized", "custom_agent"],
    based_on_version: int | None,
) -> MergedAgentConfig:
    doc_dict = dict(raw)
    doc_dict.pop("based_on_version", None)
    doc_dict.pop("customization_status", None)
    # Strip storage-internal fields not in the model. ``extra="forbid"`` (AH-40)
    # would otherwise reject them.
    for storage_field in _STORAGE_INTERNAL_FIELDS:
        doc_dict.pop(storage_field, None)

    try:
        config = MergedAgentConfig.model_validate(doc_dict)
    except ValidationError as e:
        raise ConfigValidationError(
            f"Config validation failed: {e}"
        ) from e

    config.based_on_version = based_on_version
    config.customization_status = status
    return config


def list_account_agent_configs(
    account_id: str,
    project_id: str | None = None,
) -> list[str]:
    """Return the sorted union of global and per-account agent config IDs.

    Args:
        account_id: Account whose overlay collection is scanned.
        project_id: GCP project ID. Resolved via argument → env var
            ``GOOGLE_CLOUD_PROJECT_ID`` → ``"ken-e-dev"``.

    Returns:
        Sorted list of unique config document IDs visible to this account.

    Raises:
        FirestoreConnectionError: An unexpected error occurred communicating with Firestore.
    """
    resolved_project_id = _resolve_project_id(project_id)

    try:
        db = _build_firestore_client(resolved_project_id)
    except Exception as e:
        raise FirestoreConnectionError(
            f"Failed to connect to Firestore for project {resolved_project_id!r}: {e}"
        ) from e

    try:
        global_ids = {ref.id for ref in db.collection("agent_configs").list_documents()}
        account_ids = {
            ref.id
            for ref in db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .list_documents()
        }
        return sorted(global_ids | account_ids)
    except Exception as e:
        raise FirestoreConnectionError(
            f"Unexpected Firestore error listing configs for account {account_id!r}: {e}"
        ) from e
