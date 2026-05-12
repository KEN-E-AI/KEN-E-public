"""
Agent configuration management endpoints.

Provides CRUD operations for strategy agent configurations stored in Firestore.

Pydantic models for the ``agent_configs/{id}`` schema live in
``kene_api.models.agent_config_models``; this module re-exports them for
backwards compatibility with pre-Sprint-6 callers.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import firestore
from pydantic import Field, ValidationError

from shared.trace_metadata import parse_semver, validate_semver

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore
from ..models.agent_config_models import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigMetadata,
    AgentConfigOverlayUpdate,
    AgentConfigUpdate,
    ConfigAuditEntry,
    MergedAgentConfig,
)
from ..services.audit_service import log_config_action
from ..services.config_versioning import increment_version, sanitize_updated_by

_SEMVER_MAJOR_RE = re.compile(r"^v?(\d+)")

__all__ = [
    "ALLOWED_CONFIG_IDS",
    "AgentConfig",
    "AgentConfigCreate",
    "AgentConfigMetadata",
    "AgentConfigOverlayUpdate",
    "AgentConfigUpdate",
    "AgentConfigUpdateResponse",
    "ConfigAuditEntry",
    "MergedAgentConfig",
    "account_router",
    "router",
]


class AgentConfigUpdateResponse(AgentConfig):
    """PUT response: the updated AgentConfig plus any operator warnings.

    Extends ``AgentConfig`` (rather than nesting it) so existing callers that
    read top-level fields like ``response.model`` or ``response.metadata``
    keep working. Adding a new optional ``warnings`` list is additive.

    Per Sprint 6 AC-6.25, changes to ``model``, ``temperature`` or
    ``max_output_tokens`` cannot be picked up by the 60 s hot-reload cache
    (ADK bakes them in at agent construction) — those changes surface as a
    redeploy-required warning here so admins don't silently think the
    change is live.
    """

    warnings: list[str] = Field(
        default_factory=list,
        description="Operator warnings (e.g., redeploy required for model change).",
    )


# Fields whose runtime effect requires a pod/agent redeploy. Per Sprint 6
# Decision B, ONLY ``instruction`` propagates via the 60 s in-process cache
# because the ADK ``Agent`` constructor only accepts a callable for the
# ``instruction`` field. ``model``, ``temperature`` and ``max_output_tokens``
# are baked into the SDK ``GenerateContentConfig`` at construction time, so
# updates to any of them require a pod restart.
_REDEPLOY_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"model", "temperature", "max_output_tokens"}
)

# Storage-internal fields that live on Firestore docs but are not part of
# the ``MergedAgentConfig`` API contract. They must be stripped before
# Pydantic validation now that ``MergedAgentConfig`` uses ``extra="forbid"``.
_STORAGE_INTERNAL_FIELDS: frozenset[str] = frozenset(
    {"metadata", "created_at", "updated_at", "created_by"}
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-configs", tags=["agent-configs"])

# Allowlist of valid Firestore config doc IDs for agent configurations.
# These correspond to the config_doc_id and sub_config_doc_ids in
# app/adk/agents/registry.py. Keep in sync when agents are added/removed.
ALLOWED_CONFIG_IDS: set[str] = {
    "ken_e_chatbot",
    "company_news_agent",
    "google_analytics_agent",
    "business_researcher",
    "business_formatter",
    "competitive_researcher",
    "competitive_formatter",
    "marketing_researcher",
    "marketing_formatter",
    "brand_researcher",
    "brand_formatter",
}


# Version-bump + field-name sanitization helpers now live in
# ``services/config_versioning.py`` so ``routers/mcp_server_configs.py`` can
# import them without reaching across into another router's private API.
# Kept as backward-compatible aliases for any external callers / tests that
# still reference the underscored names.
_increment_version = increment_version
_sanitize_updated_by = sanitize_updated_by


def _build_firestore_updates(
    instruction: str | None = None,
    model: str | None = None,
    description: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    version: str | None = None,
    updated_at: str | None = None,
    updated_by: str | None = None,
    variant_name: str | None = None,
    experiment_id: str | None = None,
    notes: str | None = None,
) -> dict[str, str | int | float]:
    """
    Build type-safe Firestore update dictionary.

    ``temperature`` and ``max_output_tokens`` are written flat at the top
    level (AH-40). The legacy nested ``generate_content_config`` wrapper
    is no longer produced.

    Args:
        instruction: New instruction text
        model: New model identifier
        description: New description
        temperature: New temperature value
        max_output_tokens: New max tokens value
        version: New version string
        updated_at: Update timestamp
        updated_by: Email of updater
        variant_name: New variant name
        experiment_id: New experiment ID
        notes: Change notes

    Returns:
        Dictionary with Firestore update format (dot notation for metadata fields)
    """
    updates: dict[str, str | int | float] = {}

    if instruction is not None:
        updates["instruction"] = instruction

    if model is not None:
        updates["model"] = model

    if description is not None:
        updates["description"] = description

    if temperature is not None:
        updates["temperature"] = temperature

    if max_output_tokens is not None:
        updates["max_output_tokens"] = max_output_tokens

    if version is not None:
        updates["metadata.version"] = version

    if updated_at is not None:
        updates["metadata.updated_at"] = updated_at

    if updated_by is not None:
        updates["metadata.updated_by"] = updated_by

    if variant_name is not None:
        updates["metadata.variant_name"] = variant_name

    if experiment_id is not None:
        updates["metadata.experiment_id"] = experiment_id

    if notes is not None:
        updates["metadata.notes"] = notes

    return updates


def _snapshot_pre_image(
    current_config: dict[str, Any], update: AgentConfigUpdate
) -> dict[str, Any]:
    """Capture current values for every field the update touches.

    Reads ``temperature`` and ``max_output_tokens`` flat (AH-40).
    """
    snap: dict[str, Any] = {}

    if update.instruction is not None:
        snap["instruction"] = current_config.get("instruction")
    if update.model is not None:
        snap["model"] = current_config.get("model")
    if update.description is not None:
        snap["description"] = current_config.get("description")
    if update.temperature is not None:
        snap["temperature"] = current_config.get("temperature")
    if update.max_output_tokens is not None:
        snap["max_output_tokens"] = current_config.get("max_output_tokens")

    return snap


def _snapshot_post_image(
    updated_data: dict[str, Any], update: AgentConfigUpdate
) -> dict[str, Any]:
    snap: dict[str, Any] = {}

    if update.instruction is not None:
        snap["instruction"] = updated_data.get("instruction")
    if update.model is not None:
        snap["model"] = updated_data.get("model")
    if update.description is not None:
        snap["description"] = updated_data.get("description")
    if update.temperature is not None:
        snap["temperature"] = updated_data.get("temperature")
    if update.max_output_tokens is not None:
        snap["max_output_tokens"] = updated_data.get("max_output_tokens")

    return snap


def _diff_fields(
    pre: dict[str, Any],
    post: dict[str, Any],
    update: AgentConfigUpdate,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Return (fields_changed, changes) for fields the caller actually set.

    A field is "changed" if it was present in the update body and its value
    actually differs from the pre-image. This avoids logging no-op fields.
    """
    fields_changed: list[str] = []
    changes: dict[str, dict[str, Any]] = {}

    for field_name in pre:
        before = pre[field_name]
        after = post.get(field_name)
        if before != after:
            fields_changed.append(field_name)
            changes[field_name] = {"before": before, "after": after}

    return fields_changed, changes


def _build_redeploy_warnings(fields_changed: list[str]) -> list[str]:
    """Surface redeploy-required warnings for fields ADK bakes at construction."""
    warnings: list[str] = []
    for field_name in fields_changed:
        if field_name in _REDEPLOY_REQUIRED_FIELDS:
            warnings.append(
                f"Change to '{field_name}' requires a pod/agent redeploy to take "
                f"effect. The 60 s hot-reload cache only covers instruction and "
                f"temperature."
            )
    return warnings


@router.get("/", response_model=list[str])
async def list_agent_configs(
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> list[str]:
    """
    List all available agent configuration IDs.

    Requires super admin authentication.

    Args:
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        List of config document IDs

    Raises:
        401: Not authenticated
        403: Not a super admin
        500: Firestore error
    """
    # Only super admins can access agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config access attempt by user {user.user_id} ({user.email})"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access agent configurations",
        )

    try:
        configs = db.collection("agent_configs").stream()
        config_ids = [config.id for config in configs]

        logger.info(f"User {user.email} listed {len(config_ids)} agent configs")

        return sorted(config_ids)

    except Exception as e:
        logger.error(f"Failed to list agent configs: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to list agent configurations"
        ) from e


@router.get("/{config_id}", response_model=AgentConfig)
async def get_agent_config(
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> AgentConfig:
    """
    Get a specific agent configuration.

    Requires super admin authentication.

    Args:
        config_id: Agent config document ID (e.g., 'business_researcher')
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        Agent configuration with all fields

    Raises:
        400: Invalid config_id
        401: Not authenticated
        403: Not a super admin
        404: Config not found
        500: Firestore error
    """
    # Only super admins can access agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config read attempt by user {user.user_id} ({user.email}) for {config_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access agent configurations",
        )

    # Validate config_id against allowlist (security: prevent path traversal)
    if config_id not in ALLOWED_CONFIG_IDS:
        logger.warning(f"Invalid config_id attempted: {config_id} by user {user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_id. Must be one of: {', '.join(sorted(ALLOWED_CONFIG_IDS))}",
        )

    try:
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Configuration not found")

        config_data = doc.to_dict()

        # Parse into AgentConfig model
        logger.info(f"User {user.email} retrieved config: {config_id}")
        return AgentConfig(**config_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent config {config_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve agent configuration"
        ) from e


@router.put("/{config_id}", response_model=AgentConfigUpdateResponse)
async def update_agent_config(
    config_id: str,
    update: AgentConfigUpdate,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> AgentConfigUpdateResponse:
    """
    Update an agent configuration.

    Automatically increments version and updates metadata.
    Requires super admin authentication.

    Args:
        config_id: Agent config document ID
        update: Fields to update
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        Updated agent configuration

    Raises:
        400: Invalid config_id or invalid version format
        401: Not authenticated
        403: Not a super admin
        404: Config not found
        500: Firestore error
    """
    # Only super admins can modify agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config update attempt by user {user.user_id} ({user.email}) for {config_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can modify agent configurations",
        )

    # Validate config_id against allowlist (security: prevent path traversal)
    if config_id not in ALLOWED_CONFIG_IDS:
        logger.warning(
            f"Invalid config_id update attempted: {config_id} by user {user.email}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_id. Must be one of: {', '.join(sorted(ALLOWED_CONFIG_IDS))}",
        )

    try:
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Get current config
        current_config = doc.to_dict()
        current_metadata = current_config.get("metadata", {})

        # Determine new version
        # Note: format validation already done by Pydantic field_validator
        current_version_str = current_metadata.get("version")

        if update.version:
            new_version = validate_semver(update.version)

            # Prevent version downgrade
            if current_version_str:
                try:
                    current_parsed = parse_semver(validate_semver(current_version_str))
                    new_parsed = parse_semver(new_version)
                    if new_parsed < current_parsed:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Version downgrade not allowed: "
                            f"{new_version} < {validate_semver(current_version_str)}. "
                            f"Version must be greater than the current version.",
                        )
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot compare versions: current stored version "
                        f"'{current_version_str}' is not valid semver. "
                        f"Please contact an admin to fix the stored version. "
                        f"Error: {e}",
                    ) from e
        else:
            if not current_version_str:
                raise HTTPException(
                    status_code=400,
                    detail="No version found in config metadata. "
                    "Please set a version manually (e.g., v1.0.0).",
                )
            try:
                new_version = increment_version(current_version_str)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot auto-increment version: {e}. "
                    f"Current stored version '{current_version_str}' "
                    f"is not valid semver. Please set a valid version manually "
                    f"(e.g., v1.0.0).",
                ) from e

        # Sanitize updated_by field
        safe_updated_by = sanitize_updated_by(update.updated_by)

        # Build type-safe updates using helper function
        updates = _build_firestore_updates(
            instruction=update.instruction,
            model=update.model,
            description=update.description,
            temperature=update.temperature,
            max_output_tokens=update.max_output_tokens,
            version=new_version,
            updated_at=datetime.now(timezone.utc).isoformat(),
            updated_by=safe_updated_by,
            variant_name=update.variant_name,
            experiment_id=update.experiment_id,
            notes=update.notes,
        )

        # Snapshot pre-image for audit diff (Sprint 6 AC-6.9)
        pre_image = _snapshot_pre_image(current_config, update)

        # Apply updates
        doc_ref.update(updates)

        # Fetch and return updated config
        updated_doc = doc_ref.get()
        updated_data = updated_doc.to_dict()

        # Diff + audit write (failure non-fatal)
        post_image = _snapshot_post_image(updated_data, update)
        fields_changed, changes = _diff_fields(pre_image, post_image, update)
        await log_config_action(
            db=db,
            doc_type="agent_config",
            doc_id=config_id,
            action="updated",
            user=user,
            version_before=current_version_str,
            version_after=new_version,
            fields_changed=fields_changed,
            changes=changes,
        )

        # Redeploy warnings (Sprint 6 AC-6.25)
        warnings = _build_redeploy_warnings(fields_changed)

        logger.info(
            f"User {user.email} updated config {config_id} to version {new_version}"
        )

        return AgentConfigUpdateResponse(**updated_data, warnings=warnings)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent config {config_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update agent configuration"
        ) from e


@router.get("/{config_id}/history", response_model=list[ConfigAuditEntry])
async def get_agent_config_history(
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
    limit: int = Query(20, ge=1, le=100, description="Max entries to return"),
) -> list[ConfigAuditEntry]:
    """Return recent audit entries for an agent config, newest first.

    Reads from ``agent_configs/{config_id}/history/*`` subcollection written
    by ``log_config_action``. Per Sprint 6 AC-6.9 / Decision C.
    """
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can read agent config history",
        )

    if config_id not in ALLOWED_CONFIG_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_id. Must be one of: {', '.join(sorted(ALLOWED_CONFIG_IDS))}",
        )

    # FastAPI enforces `le=100` on the query-param, but that only runs at the
    # HTTP boundary; in-process callers could pass a wider value.
    if limit > 100:
        raise HTTPException(status_code=400, detail="limit must be <= 100")

    try:
        history_ref = (
            db.collection("agent_configs")
            .document(config_id)
            .collection("history")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [ConfigAuditEntry(**doc.to_dict()) for doc in history_ref.stream()]
    except Exception as e:
        logger.error(f"Failed to fetch history for {config_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve config history"
        ) from e


# ---------------------------------------------------------------------------
# Per-account agent-config CRUD (Phase 3 — AH-PRD-02 §6 / AC-11)
# ---------------------------------------------------------------------------

account_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/agent-configs",
    tags=["agent-configs"],
)


def _parse_based_on_version(version_str: str | None) -> int:
    """Parse major version component from a semver string, default 1 on failure."""
    if not version_str:
        return 1
    m = _SEMVER_MAJOR_RE.match(str(version_str))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 1


def _merge_from_data(
    config_id: str,
    global_data: dict | None,
    overlay_data: dict | None,
) -> MergedAgentConfig | None:
    """Shallow-merge pre-fetched global + overlay dicts into a MergedAgentConfig.

    Returns None when neither document exists.  Called by both ``_load_merged``
    (single-config fetch) and the list endpoint (bulk fetch, avoids N+1 reads).
    """
    if global_data is None and overlay_data is None:
        return None

    if global_data is not None and overlay_data is not None:
        merged = {**global_data, **overlay_data}
        status = "customized"
        bov = _parse_based_on_version(overlay_data.get("based_on_version"))
    elif global_data is not None:
        merged = dict(global_data)
        status = "default"
        bov = None
    else:
        # overlay_data is not None, global_data is None → custom_agent
        merged = dict(overlay_data)  # type: ignore[arg-type]
        status = "custom_agent"
        bov = _parse_based_on_version(overlay_data.get("based_on_version"))  # type: ignore[union-attr]

    # Strip storage-internal fields that aren't part of the API contract.
    # MergedAgentConfig uses extra="forbid" (AH-40), so a leftover nested
    # generate_content_config would fail validation here — that's the
    # intent, signalling a backfill miss.
    for storage_field in _STORAGE_INTERNAL_FIELDS:
        merged.pop(storage_field, None)
    merged.pop("based_on_version", None)
    merged.pop("customization_status", None)
    merged["config_id"] = config_id
    merged["customization_status"] = status
    merged["based_on_version"] = bov

    return MergedAgentConfig.model_validate(merged)


def _load_merged(
    db: firestore.Client,
    account_id: str,
    config_id: str,
) -> MergedAgentConfig | None:
    """Read global + per-account overlay docs from Firestore, then merge.

    Returns None when neither document exists (caller raises 404).
    Mirrors the merge semantics of ``app/adk/agents/agent_factory/config_loader.py``
    without taking a runtime dependency on the ``app/`` package.
    """
    global_doc = db.collection("agent_configs").document(config_id).get()
    overlay_doc = (
        db.collection("accounts")
        .document(account_id)
        .collection("agent_configs")
        .document(config_id)
        .get()
    )

    return _merge_from_data(
        config_id,
        global_doc.to_dict() if global_doc.exists else None,
        overlay_doc.to_dict() if overlay_doc.exists else None,
    )


@account_router.get("/", response_model=list[MergedAgentConfig])
async def list_account_agent_configs(
    account_id: str,
    visible_in_frontend: bool = Query(False, description="Filter to visible_in_frontend=true"),
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> list[MergedAgentConfig]:
    """List merged agent configs visible to an account.

    Returns globals where ``automatically_available=true`` UNION any
    per-account custom/overlay docs.  Optionally further restricted to
    ``visible_in_frontend=true`` via query param.

    Reads are allowed for any account member; writes require admin role.
    """
    if not user.has_account_access(account_id):
        raise HTTPException(status_code=403, detail="Access denied to this account")

    try:
        global_docs = {doc.id: doc.to_dict() for doc in db.collection("agent_configs").stream()}
        account_docs = {
            doc.id: doc.to_dict()
            for doc in db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .stream()
        }

        config_ids = set(account_docs.keys())
        for cid, data in global_docs.items():
            if data and data.get("automatically_available", True):
                config_ids.add(cid)

        # Build merges inline from already-fetched dicts — no per-config Firestore reads.
        # Skip docs that fail validation (e.g. a stray schema-placeholder doc lacking
        # required fields) so one malformed row doesn't take the whole list down.
        results: list[MergedAgentConfig] = []
        for cid in sorted(config_ids):
            try:
                merged = _merge_from_data(cid, global_docs.get(cid), account_docs.get(cid))
            except ValidationError as exc:
                logger.warning(
                    f"Skipping malformed agent config '{cid}' for account "
                    f"{account_id}: {exc}"
                )
                continue
            if merged is None:
                continue
            if visible_in_frontend and not merged.visible_in_frontend:
                continue
            results.append(merged)

        return results

    except Exception as e:
        logger.error(f"Failed to list agent configs for account {account_id}: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to list agent configurations") from e


@account_router.get("/{config_id}", response_model=MergedAgentConfig)
async def get_account_agent_config(
    account_id: str,
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> MergedAgentConfig:
    """Fetch the merged config for a specific agent in the context of an account."""
    if not user.has_account_access(account_id):
        raise HTTPException(status_code=403, detail="Access denied to this account")

    try:
        merged = _load_merged(db, account_id, config_id)
    except Exception as e:
        logger.error(f"Failed to load agent config {config_id} for account {account_id}: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent configuration") from e

    if merged is None:
        raise HTTPException(status_code=404, detail="Agent configuration not found")
    return merged


@account_router.post("/", response_model=MergedAgentConfig, status_code=201)
async def create_account_agent_config(
    account_id: str,
    body: AgentConfigCreate,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> MergedAgentConfig:
    """Create a custom agent scoped to this account.

    The server generates a ``custom_{uuid8}`` config_id.  Requires admin role.
    """
    if not user.has_account_access(account_id, required_roles=["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Admin role required to create agent configurations",
        )

    custom_id = f"custom_{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    doc_data: dict[str, Any] = {
        "name": body.name,
        "instruction": body.instruction,
        "model": body.model,
        "customization_status": "custom_agent",
        "created_at": now,
        "updated_at": now,
        "created_by": user.email,
    }
    if body.description is not None:
        doc_data["description"] = body.description
    if body.temperature is not None:
        doc_data["temperature"] = body.temperature
    if body.skill_ids:
        doc_data["skill_ids"] = body.skill_ids
    if body.sandbox_code_executor_enabled:
        doc_data["sandbox_code_executor_enabled"] = body.sandbox_code_executor_enabled

    try:
        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(custom_id)
            .set(doc_data)
        )
        logger.info(f"User {user.email} created custom agent {custom_id} for account {account_id}")
    except Exception as e:
        logger.error(f"Failed to create custom agent for account {account_id}: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to create agent configuration") from e

    merged = _load_merged(db, account_id, custom_id)
    if merged is None:
        raise HTTPException(status_code=500, detail="Created document not readable")
    return merged


@account_router.put("/{config_id}", response_model=MergedAgentConfig)
async def upsert_account_agent_config_overlay(
    account_id: str,
    config_id: str,
    body: AgentConfigOverlayUpdate,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> MergedAgentConfig:
    """Upsert a per-account overlay for an existing global agent config.

    Stores only the fields present in the body (sparse overlay).
    Records ``based_on_version`` from the global doc's ``metadata.version``.
    Requires admin role.
    """
    if not user.has_account_access(account_id, required_roles=["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Admin role required to modify agent configurations",
        )

    try:
        global_doc = db.collection("agent_configs").document(config_id).get()
        global_data = global_doc.to_dict() if global_doc.exists else None

        # Resolve based_on_version from global doc metadata
        bov: int = 1
        if global_data:
            metadata = global_data.get("metadata") or {}
            bov = _parse_based_on_version(metadata.get("version"))

        overlay_data: dict[str, Any] = {
            "based_on_version": bov,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user.email,
        }
        body_dict = body.model_dump(exclude_unset=True)
        overlay_data.update(body_dict)

        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
            .set(overlay_data, merge=True)
        )
        logger.info(
            f"User {user.email} upserted overlay for {config_id} on account {account_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to upsert overlay for {config_id} / account {account_id}: {e!s}"
        )
        raise HTTPException(status_code=500, detail="Failed to update agent configuration") from e

    merged = _load_merged(db, account_id, config_id)
    if merged is None:
        raise HTTPException(status_code=404, detail="Agent configuration not found")
    return merged


@account_router.delete("/{config_id}", status_code=204)
async def delete_account_agent_config(
    account_id: str,
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> None:
    """Delete a per-account agent config.

    For ``custom_*`` config IDs the custom document is deleted entirely.
    For non-custom config IDs the overlay is deleted (revert to global default).
    Requires admin role.
    """
    if not user.has_account_access(account_id, required_roles=["admin"]):
        raise HTTPException(
            status_code=403,
            detail="Admin role required to delete agent configurations",
        )

    try:
        overlay_ref = (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
        )
        overlay_doc = overlay_ref.get()

        if config_id.startswith("custom_"):
            if not overlay_doc.exists:
                raise HTTPException(status_code=404, detail="Custom agent configuration not found")
            overlay_ref.delete()
            logger.info(
                f"User {user.email} deleted custom agent {config_id} from account {account_id}"
            )
        else:
            # Revert to global: delete the overlay doc only
            if overlay_doc.exists:
                overlay_ref.delete()
            logger.info(
                f"User {user.email} reverted overlay for {config_id} on account {account_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete overlay for {config_id} / account {account_id}: {e!s}"
        )
        raise HTTPException(status_code=500, detail="Failed to delete agent configuration") from e
