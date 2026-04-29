"""
Agent configuration loader with Firestore and Weave integration.

Loads agent configurations from Firestore and creates agents dynamically,
with full observability via Weave tracing.
"""

import logging
import os
from collections.abc import Callable
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.llm_agent_config import LlmAgentConfig
from google.adk.tools import AgentTool
from google.cloud import firestore

try:
    import weave

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False
    weave = None

logger = logging.getLogger(__name__)


# Custom exceptions for better error handling
class ConfigNotFoundError(Exception):
    """Raised when agent config document is not found in Firestore."""

    pass


class ConfigValidationError(Exception):
    """Raised when agent config format is invalid."""

    pass


class FirestoreConnectionError(Exception):
    """Raised when Firestore connection fails."""

    pass


def _weave_op(func: Callable) -> Callable:
    """Decorator that applies @weave.op only if Weave is available."""
    if WEAVE_AVAILABLE and weave:
        return weave.op()(func)
    return func


@_weave_op
def load_config_from_firestore(
    doc_id: str, project_id: str = "ken-e-dev"
) -> tuple[LlmAgentConfig, dict[str, Any]]:
    """
    Load agent configuration from Firestore.

    This function fetches the configuration document from Firestore,
    parses it into an LlmAgentConfig, and returns both the config
    and metadata for Weave tracing.

    Args:
        doc_id: Document ID in agent_configs collection
        project_id: GCP project ID

    Returns:
        Tuple of (LlmAgentConfig, metadata_dict)

    Raises:
        ConfigNotFoundError: If document doesn't exist
        ConfigValidationError: If config format is invalid
        FirestoreConnectionError: If Firestore connection fails
    """
    try:
        # Initialize Firestore client with explicit ADC
        # Agent Engine requires explicit credential configuration
        from google.auth import default
        credentials, _ = default()
        db = firestore.Client(project=project_id, credentials=credentials)

        # Fetch config document
        doc_ref = db.collection("agent_configs").document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            error_msg = f"Config document '{doc_id}' not found in Firestore"
            logger.error(error_msg)
            raise ConfigNotFoundError(error_msg)

        # Get document data
        config_data = doc.to_dict()

        if not config_data:
            error_msg = f"Config document '{doc_id}' is empty"
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)

        # Extract metadata (for Weave logging) and validate version
        metadata = config_data.get("metadata", {})
        from shared.trace_metadata import DEFAULT_VERSION, validate_semver

        raw_version = metadata.get("version")
        metadata["version"] = validate_semver(raw_version)
        if metadata["version"] == DEFAULT_VERSION and raw_version != DEFAULT_VERSION:
            logger.error(
                f"Firestore config '{doc_id}' has invalid version: {raw_version!r}. "
                f"Falling back to {DEFAULT_VERSION}. Fix the version in Firestore."
            )

        # Remove metadata from config data (not needed for LlmAgentConfig)
        config_dict = {k: v for k, v in config_data.items() if k != "metadata"}

        # Parse into LlmAgentConfig
        try:
            config = LlmAgentConfig.model_validate(config_dict)
        except Exception as e:
            error_msg = f"Failed to validate config for '{doc_id}': {e!s}"
            logger.error(error_msg)
            raise ConfigValidationError(error_msg) from e

        logger.info(
            f"Loaded config '{doc_id}' from Firestore "
            f"(version: {metadata.get('version', 'unknown')})"
        )

        # Log to Weave call.summary if available
        if WEAVE_AVAILABLE and weave:
            try:
                call = weave.get_current_call()
                if call:
                    call.summary["config_doc_id"] = doc_id
                    call.summary["config_version"] = metadata.get("version")
                    call.summary["variant_name"] = metadata.get("variant_name")
                    call.summary["model"] = config_dict.get("model")
            except Exception:
                pass  # Silently continue if Weave not initialized

        return config, metadata

    except (ConfigNotFoundError, ConfigValidationError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        error_msg = f"Firestore connection error while loading '{doc_id}': {e!s}"
        logger.error(error_msg)
        raise FirestoreConnectionError(error_msg) from e


@_weave_op
def create_agent_from_firestore_config(
    doc_id: str,
    google_search_agent: Any | None = None,
    output_schema: Any | None = None,
    project_id: str | None = None,
) -> Agent:
    """
    Create an ADK agent from Firestore configuration.

    This function loads the config from Firestore, creates the agent
    using Agent.from_config(), and adds tools/output_schema programmatically.
    All steps are traced to Weave for observability.

    Args:
        doc_id: Document ID in agent_configs collection
        google_search_agent: Optional Google search tool agent
        output_schema: Optional Pydantic model for output schema
        project_id: GCP project ID

    Returns:
        Configured Agent instance

    Raises:
        ConfigNotFoundError: If config document not found
        ConfigValidationError: If config format invalid
        FirestoreConnectionError: If Firestore unavailable
    """
    # Use environment-aware project ID if not provided
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")

    # Load config from Firestore
    config, metadata = load_config_from_firestore(doc_id, project_id)

    logger.info(
        f"Creating agent from Firestore config: {doc_id} "
        f"(version: {metadata.get('version', 'unknown')}, "
        f"model: {config.model})"
    )

    # DEBUG: Log system instructions preview for marketing agents (only at DEBUG level)
    if logger.isEnabledFor(logging.DEBUG) and doc_id in ["marketing_researcher", "marketing_formatter"]:
        instructions = getattr(config, "system_instruction", "")
        has_new_schema = 'customer_strategies' in instructions and 'ideal_customer_profiles: List' in instructions
        has_old_schema = 'product_categories' in instructions
        logger.debug(
            f"[DEBUG] {doc_id} config loaded: v{metadata.get('version', 'MISSING')}, "
            f"{len(instructions)} chars, schema={'NEW' if has_new_schema else 'OLD' if has_old_schema else 'UNKNOWN'}"
        )

    # Log config metadata to Weave using call.summary
    if WEAVE_AVAILABLE and weave:
        try:
            call = weave.get_current_call()
            if call:
                call.summary["agent_creation"] = doc_id
                call.summary["config_version"] = metadata.get("version", "unknown")
                call.summary["variant_name"] = metadata.get("variant_name", "unknown")
                call.summary["experiment_id"] = metadata.get("experiment_id", "unknown")
                call.summary["config_model"] = config.model
                call.summary["config_temperature"] = getattr(
                    config.generate_content_config, "temperature", None
                )
                call.summary["config_max_tokens"] = getattr(
                    config.generate_content_config, "max_output_tokens", None
                )
                call.summary["updated_by"] = metadata.get("updated_by", "unknown")
                call.summary["updated_at"] = metadata.get("updated_at", "unknown")
        except Exception:
            pass  # Silently continue if Weave not initialized

    # Create agent from config
    # Note: from_config expects a config_abs_path, we provide a virtual path
    agent = Agent.from_config(config, f"/firestore/agent_configs/{doc_id}")

    # Add tools programmatically (NOT from Firestore)
    if google_search_agent is not None:
        agent.tools = [AgentTool(agent=google_search_agent)]
        logger.info(f"Added google_search tool to agent '{doc_id}'")

    # Add output_schema programmatically (NOT from Firestore)
    if output_schema is not None:
        agent.output_schema = output_schema
        logger.info(f"Added output_schema to agent '{doc_id}'")

    logger.info(
        f"Created agent '{doc_id}' from Firestore config "
        f"(version: {metadata.get('version', 'unknown')})"
    )

    return agent


def get_current_config_metadata(
    doc_id: str, project_id: str = "ken-e-dev"
) -> dict[str, Any]:
    """
    Get metadata for a config document without loading the full config.

    Useful for logging which config versions are being used in orchestration.

    Args:
        doc_id: Document ID in agent_configs collection
        project_id: GCP project ID

    Returns:
        Metadata dictionary
    """
    try:
        # Use explicit credentials for Agent Engine compatibility
        from google.auth import default
        credentials, _ = default()
        db = firestore.Client(project=project_id, credentials=credentials)
        doc_ref = db.collection("agent_configs").document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return {"error": "config_not_found", "doc_id": doc_id}

        config_data = doc.to_dict()
        metadata = config_data.get("metadata", {})

        from shared.trace_metadata import DEFAULT_VERSION, validate_semver

        raw_version = metadata.get("version")
        normalized_version = validate_semver(raw_version)
        if normalized_version == DEFAULT_VERSION and raw_version != DEFAULT_VERSION:
            logger.error(
                f"Firestore config '{doc_id}' has invalid version: {raw_version!r}. "
                f"Falling back to {DEFAULT_VERSION}. Fix the version in Firestore."
            )

        gcc = config_data.get("generate_content_config") or {}
        return {
            "doc_id": doc_id,
            "version": normalized_version,
            "variant_name": metadata.get("variant_name", "baseline"),
            "experiment_id": metadata.get("experiment_id", "baseline"),
            "model": config_data.get("model", "unknown"),
            "temperature": gcc.get("temperature"),
            "max_output_tokens": gcc.get("max_output_tokens"),
            "updated_at": metadata.get("updated_at", "unknown"),
        }
    except Exception as e:
        logger.error(f"Failed to get metadata for '{doc_id}': {e}")
        return {"error": str(e), "doc_id": doc_id}
