#!/usr/bin/env python3
"""
Deployment script for KEN-E chat agent.
Deploys the frontend-facing agent for company news and analytics.

Usage:
    python deploy_ken_e.py --env dev
    python deploy_ken_e.py --env staging
    python deploy_ken_e.py --env prod
"""

import argparse
import importlib.metadata
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Repo root must be on sys.path before any `app.adk.*` import so this script
# resolves correctly when run from inside `app/adk/` (as the CD step does).
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import vertexai
from google.adk.agents.context_cache_config import ContextCacheConfig

# ADK App configuration imports
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.adk.models import Gemini
from google.adk.plugins import ReflectAndRetryToolPlugin
from vertexai import agent_engines

from app.adk.deploy_packaging import assemble_deploy_tree

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from shared.secrets import get_env_or_secret
except ImportError:
    logger.warning("Could not import shared secrets utility, will copy .env as-is")
    get_env_or_secret = None

# Environment to GCP project mapping
ENV_CONFIG = {
    "dev": {
        "project_id": "ken-e-dev",
        "project_number": "525657242938",
        "chat_internal_api_url": "sm://525657242938/kene-api-url",
        "chat_internal_api_audience": "sm://525657242938/kene-api-url",
    },
    "staging": {
        "project_id": "ken-e-staging",
        "project_number": "391472102753",
        # Use the deterministic Cloud Run URL (service-projectnumber.region.run.app),
        # NOT the legacy hash URL held in the kene-api-url secret. The chat callback
        # mints an OIDC token whose `aud` is this value; the API verifies it against
        # CHAT_INTERNAL_OIDC_AUDIENCE, which the CD config sets to this same
        # deterministic form (deployment/cd/staging.yaml). A mismatch 401s the
        # engine->API side-table write, so status dots never populate.
        "chat_internal_api_url": "https://kene-api-staging-391472102753.us-central1.run.app",
        "chat_internal_api_audience": "https://kene-api-staging-391472102753.us-central1.run.app",
    },
    "prod": {
        "project_id": "ken-e-production",
        "project_number": "395770269870",
        # See the staging note above: must match CHAT_INTERNAL_OIDC_AUDIENCE in
        # deployment/cd/deploy-to-prod.yaml, else the engine->API OIDC call 401s.
        "chat_internal_api_url": "https://kene-api-prod-395770269870.us-central1.run.app",
        "chat_internal_api_audience": "https://kene-api-prod-395770269870.us-central1.run.app",
    },
}


def update_secret_manager(secret_name: str, secret_value: str, project_id: str) -> bool:
    """Update a secret in Google Secret Manager with a new value.

    Args:
        secret_name: Name of the secret (without project path)
        secret_value: New value for the secret
        project_id: GCP project ID

    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()

        # Build the secret name
        secret_path = f"projects/{project_id}/secrets/{secret_name}"

        # Add a new version with the updated value
        parent = secret_path
        payload = secret_value.encode("UTF-8")

        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": payload},
            }
        )

        logger.info(f"✅ Updated secret {secret_name} in Secret Manager")
        logger.info(f"   New version: {response.name}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to update secret {secret_name}: {e}")
        return False


def process_env_file(source_path: Path, dest_path: Path) -> None:
    """Process .env file to resolve Secret Manager references.

    Args:
        source_path: Path to source .env file
        dest_path: Path to write processed .env file
    """
    if not get_env_or_secret:
        # If we can't import the secrets utility, just copy as-is
        shutil.copy2(source_path, dest_path)
        logger.warning("Copying .env file without processing Secret Manager references")
        return

    logger.info("Processing .env file to resolve Secret Manager references")
    processed_lines = []

    with open(source_path) as f:
        for line in f:
            # Skip comments and empty lines
            if line.strip().startswith("#") or not line.strip():
                processed_lines.append(line)
                continue

            # Parse key=value pairs
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Check if this value needs Secret Manager resolution
                if value.startswith("sm://"):
                    try:
                        # Set env var temporarily to use get_env_or_secret
                        os.environ[key] = value
                        resolved_value = get_env_or_secret(key)
                        if resolved_value:
                            processed_lines.append(f"{key}={resolved_value}\n")
                            logger.info(f"Resolved Secret Manager reference for {key}")
                        else:
                            # Keep original if resolution failed
                            processed_lines.append(line)
                            logger.warning(
                                f"Failed to resolve Secret Manager reference for {key}"
                            )
                    except Exception as e:
                        logger.error(f"Error resolving {key}: {e}")
                        processed_lines.append(line)
                else:
                    # Keep non-secret values as-is
                    processed_lines.append(line)
            else:
                processed_lines.append(line)

    # Write processed .env file
    with open(dest_path, "w") as f:
        f.writelines(processed_lines)

    logger.info(f"Processed .env file written to {dest_path}")


def _append_chat_env_vars(env_config: dict, *dest_paths: Path) -> None:
    """Resolve and append CHAT_INTERNAL_API_URL/AUDIENCE to deployed .env files.

    Raises:
        RuntimeError: if chat_internal_api_url is configured but cannot be
            resolved to a concrete URL — refuses to ship an agent whose
            internal-OIDC bridge would silently point at a literal sm://
            reference. See CH-PRD-01.
    """
    url_ref = env_config.get("chat_internal_api_url", "")
    audience_ref = env_config.get("chat_internal_api_audience", "") or url_ref
    if not url_ref:
        logger.warning("chat_internal_api_url not in ENV_CONFIG; skipping")
        return

    if get_env_or_secret is None:
        raise RuntimeError(
            "shared.secrets.get_env_or_secret is unavailable, but "
            "chat_internal_api_url is configured. Fix the import or remove "
            "the chat config from ENV_CONFIG before deploying."
        )

    # Overwrite (not setdefault) so a stray shell export cannot mask the
    # env_config value and silently route resolution to the wrong secret.
    os.environ["CHAT_INTERNAL_API_URL"] = url_ref
    os.environ["CHAT_INTERNAL_API_AUDIENCE"] = audience_ref
    chat_url = get_env_or_secret("CHAT_INTERNAL_API_URL")
    chat_audience = get_env_or_secret("CHAT_INTERNAL_API_AUDIENCE")

    for label, value in (
        ("CHAT_INTERNAL_API_URL", chat_url),
        ("CHAT_INTERNAL_API_AUDIENCE", chat_audience),
    ):
        if not value or str(value).startswith("sm://"):
            raise RuntimeError(
                f"{label} did not resolve to a concrete URL (got: {value!r}). "
                "The agent would ship with a broken internal-OIDC bridge. "
                "Check that the kene-api-url secret exists in the target "
                "project and that the deployer has "
                "roles/secretmanager.secretAccessor on it."
            )

    for dest_path in dest_paths:
        if dest_path.exists():
            with open(dest_path, "a") as f:
                f.write(f"\nCHAT_INTERNAL_API_URL={chat_url}\n")
                f.write(f"CHAT_INTERNAL_API_AUDIENCE={chat_audience}\n")
            logger.info(f"Appended CHAT_INTERNAL_API_URL/AUDIENCE to {dest_path}")


def _resolve_existing_engine_id(project_number: str) -> str | None:
    """Return the canonical KEN-E engine resource name from Secret Manager.

    Returns None only when the secret genuinely does not exist yet (first deploy
    → the caller creates a new engine). A transient Secret Manager error
    (PermissionDenied, a 500, a timeout) is re-raised so the deploy aborts rather
    than being swallowed to None — which would bootstrap a duplicate engine and
    orphan the canonical one.
    """
    from google.api_core import exceptions as gcp_exceptions
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_number}/secrets/ken-e-engine-id/versions/latest"
    try:
        response = client.access_secret_version(request={"name": name})
    except gcp_exceptions.NotFound:
        logger.info(
            "No ken-e-engine-id secret yet (first deploy); will create a new engine"
        )
        return None
    return response.payload.data.decode("UTF-8").strip() or None


# Chat-tree deploy-manifest invariants (app/adk/requirements.txt). The manifest is
# kept comment-free on purpose: agent_engines.update/create reads it as a path and
# the Vertex SDK's requirements parser emits "Failed to parse constraint" warnings
# for full-line `#` comments, which bury real deploy errors in the build log. The
# rationale that used to live as inline comments is recorded here and ENFORCED by
# deployment/ci/scripts/verify_deploy_tree.py (Checks 5 & 6):
#
#   * google-adk[mcp]==2.0.0 — the agent is cloudpickled locally and unpickled on
#     the Agent Engine backend, so the manifest pin must match the build-env major
#     (a 1.34.1 venv bakes a 1.x pickle that fails to unpickle on a 2.0 backend).
#     The [mcp] extra is load-bearing: ADK 2.0 demoted `mcp` from a core dep to an
#     optional extra, and the GA specialist talks to its MCP server over SSE
#     (google.adk.tools.mcp_tool.McpToolset → mcp). Without it the deploy succeeds
#     but the GA specialist ModuleNotFoundErrors at runtime (invisible to CI, which
#     mocks MCP). This is the CHAT tree only; the strategy tree pins google-adk==1.34.1
#     via requirements-strategy.txt (AH-106 decoupling).
#   * google-cloud-aiplatform[adk,agent_engines]==<uv.lock version> — must be PINNED
#     to the exact aiplatform that app/adk/uv.lock resolves. deploy_ken_e cloudpickles
#     the agent with the LOCKED aiplatform's AdkApp wrapper (module path
#     vertexai.agent_engines.templates.adk); an unpinned manifest installs a newer
#     aiplatform in the container where that module has moved, so the engine fails to
#     unpickle at boot → opaque "400 The Reasoning Engine failed to be updated"
#     (the AH-121 staging-deploy failure). Check 6 asserts manifest == uv.lock.
CHAT_ADK_VERSION_PREFIX = "2."


def _require_local_adk_version(expected_prefix: str) -> None:
    """Abort unless the locally-installed google-adk matches ``expected_prefix``.

    Symmetric with the strategy tree's guard (deploy_with_sys_version.py): the
    agent is cloudpickled locally and unpickled on the Agent Engine backend, so
    the build env's ADK major must match the manifest pin. Run the chat deploy
    from the repo's default 2.0 venv.
    """
    try:
        installed = importlib.metadata.version("google-adk")
    except importlib.metadata.PackageNotFoundError:
        logger.error("❌ google-adk is not installed in this environment")
        sys.exit(1)
    if not installed.startswith(expected_prefix):
        logger.error(
            "❌ ADK build-env mismatch: the chat tree must be built from a "
            "google-adk==%sx venv, but this environment has google-adk==%s.\n"
            "   Run the chat deploy from the repo's default (2.0) venv.",
            expected_prefix,
            installed,
        )
        sys.exit(1)
    logger.info(
        "✅ Local google-adk==%s matches the chat tree pin (%sx)",
        installed,
        expected_prefix,
    )


def deploy_ken_e() -> str | None:
    """Deploy the KEN-E chat agent to Agent Engine."""

    # Guard: the chat tree must be built from a 2.0 venv (cloudpickle skew).
    _require_local_adk_version(CHAT_ADK_VERSION_PREFIX)

    # Save current directory
    original_dir = os.getcwd()

    # Create temporary deployment directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        logger.info(f"Created temporary directory: {temp_path}")

        # Assemble the deploy tree (agents/, shared/, app/adk sub-packages,
        # requirements.txt) via the extracted helper so CI can exercise the
        # same packaging logic without triggering an actual deploy.
        assemble_deploy_tree(temp_path, copy_env=True)

        # Guard: agents/ must be present or the deployed artifact is broken.
        if not (temp_path / "agents").exists():
            return None

        # Process environment-specific .env file (resolve sm:// references)
        env_mapping = {"dev": "development", "staging": "staging", "prod": "production"}
        env_name = env_mapping.get(os.getenv("_TARGET_ENV", "dev"), "dev")
        env_file = Path(f".env.{env_name}")

        if not env_file.exists():
            logger.warning(f"⚠️  {env_file} not found, trying .env")
            env_file = Path(".env")

        if env_file.exists():
            logger.info(
                f"Using {env_file} for {os.getenv('_TARGET_ENV', 'dev')} environment"
            )
            process_env_file(env_file, temp_path / ".env")
            logger.info("Processed and copied .env file to root")
            # Also copy to agents directory for runtime loading
            process_env_file(env_file, temp_path / "agents" / ".env")
            logger.info("Copied .env file to agents/ directory for runtime loading")
            # Wire CHAT_INTERNAL_API_URL and CHAT_INTERNAL_API_AUDIENCE for agent callbacks
            target_env_key = os.getenv("_TARGET_ENV", "dev")
            _append_chat_env_vars(
                ENV_CONFIG[target_env_key],
                temp_path / ".env",
                temp_path / "agents" / ".env",
            )
        else:
            logger.error("❌ No .env file found")
            sys.exit(1)

        # Change to temp directory for deployment
        os.chdir(temp_path)

        # Initialize Vertex AI
        project_id = os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        staging_bucket = f"gs://{project_id}-adk-staging"

        vertexai.init(
            project=project_id,
            location=location,
            staging_bucket=staging_bucket,
        )

        # Assemble the KEN-E agent hierarchy from Firestore config.
        # The import is inside the try block so deploy-tree packaging regressions
        # (ImportError) are caught alongside documented build_hierarchy() failure
        # modes, instead of crashing the process before the typed handler runs.
        sys.path.insert(0, str(Path.cwd()))

        try:
            from agents.agent_factory import build_hierarchy

            from app.adk.agents.agent_factory.config_loader import (
                ConfigNotFoundError,
                FirestoreConnectionError,
            )
            from app.adk.agents.agent_factory.mcp import MCPSchemaError
            from app.adk.agents.agent_factory.roster import RosterCapExceededError

            ken_e_agent = build_hierarchy()

            # Register the Chat side-table callbacks on the root agent. Without
            # this, last_agent_started_at / last_agent_message_at are never
            # stamped, so every session derives to "idle" and the sidebar status
            # dots + active/needs-review counts stay empty (CH-PRD-01 §5.1
            # last-mile wiring; the callbacks are root-only-guarded internally).
            from app.adk.agents.chat_callbacks import (
                attach_chat_side_table_callbacks,
            )

            attach_chat_side_table_callbacks(ken_e_agent)
            logger.info(
                "✅ Wired chat side-table callbacks onto root agent "
                "(before/after_agent_callback)"
            )
        except (
            ImportError,
            ConfigNotFoundError,
            FirestoreConnectionError,
            MCPSchemaError,
            RosterCapExceededError,
            ValueError,
        ) as exc:
            logger.error("❌ Failed to build ken_e_agent: %s", exc, exc_info=True)
            return None

        logger.info(f"✅ Loaded agent: {type(ken_e_agent)}")

        # Compaction: Summarizes older conversation events to stay within token limits
        # Caching: Caches static content (instructions, tools) for cost/latency savings
        logger.info("Configuring context compaction and caching...")
        compaction_summarizer = LlmEventSummarizer(llm=Gemini(model="gemini-2.5-flash"))
        compaction_config = EventsCompactionConfig(
            summarizer=compaction_summarizer,
            compaction_interval=5,  # Compact every 5 user invocations
            overlap_size=1,  # Include 1 prior invocation for context continuity
            token_threshold=50000,  # Also compact when session exceeds 50K tokens
            event_retention_size=10,  # Keep last 10 raw events un-compacted
        )

        adk_app = App(
            name="ken_e_chatbot",
            root_agent=ken_e_agent,
            plugins=[ReflectAndRetryToolPlugin(max_retries=2)],
            events_compaction_config=compaction_config,
            context_cache_config=ContextCacheConfig(
                min_tokens=2048,  # Cache if static content exceeds this threshold
                ttl_seconds=600,  # 10 min cache lifetime (good for chat sessions)
                cache_intervals=5,  # Max reuses before cache refresh
            ),
        )
        logger.info("✅ Created App with EventsCompactionConfig and ContextCacheConfig")

        # Enable GCP Agent Engine telemetry (traces, logs, prompt/response capture)
        # See: https://docs.cloud.google.com/agent-builder/agent-engine/manage/tracing
        # Production does not capture message content to protect user data privacy
        # (mirrors .env.production). Dev/staging capture content for debugging and
        # MER-E evaluation.
        os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")
        _capture_content = "false" if os.getenv("_TARGET_ENV") == "prod" else "true"
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", _capture_content
        )

        # Wrap with AdkApp for deployment (pass App object, not agent directly)
        app = agent_engines.AdkApp(app=adk_app, enable_tracing=True)
        logger.info(f"✅ Created AdkApp with tracing enabled: {type(app)}")

        # Generate deployment name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        deployment_name = f"ken-e-chat-agent-{timestamp}"

        # Deploy: update existing engine (preserves sessions) or create new one
        logger.info(f"📦 Deploying {deployment_name}...")

        try:
            # Resolve the existing engine ID directly from Secret Manager. Reading
            # it directly (instead of via get_env_or_secret, which swallows every
            # error to None) lets us tell a genuine first-deploy (secret absent →
            # create) apart from a transient Secret Manager error (→ abort): a blip
            # must never be mistaken for "no engine" and bootstrap a duplicate that
            # orphans the canonical one.
            target_env = os.getenv("_TARGET_ENV", "dev")
            project_number = ENV_CONFIG[target_env]["project_number"]
            existing_engine_id = _resolve_existing_engine_id(project_number)

            if existing_engine_id:
                existing_engine_id = existing_engine_id.strip()
                logger.info(
                    f"Found existing engine: {existing_engine_id}, updating in place..."
                )
                # Let an update failure propagate (the outer handler returns None →
                # exit 1). Do NOT fall back to creating a new engine: a transient
                # 500 from reasoningEngines polling often fires after the update has
                # already succeeded server-side, so a fallback create would orphan a
                # fresh engine (the secret still points at the original) and pile up
                # duplicates that push the API's 500 rate higher.
                deployed_engine = agent_engines.update(
                    resource_name=existing_engine_id,
                    agent_engine=app,
                    requirements="requirements.txt",
                    display_name=deployment_name,
                    description="KEN-E chat agent for company news and analytics",
                    extra_packages=["agents", "shared", "app"],
                )
                logger.info("✅ Updated existing engine (sessions preserved)")
            else:
                # Bootstrap path: no engine ID in Secret Manager yet (first deploy).
                logger.info("No existing engine ID found; creating new engine...")
                deployed_engine = agent_engines.create(
                    agent_engine=app,
                    requirements="requirements.txt",
                    display_name=deployment_name,
                    description="KEN-E chat agent for company news and analytics",
                    extra_packages=["agents", "shared", "app"],
                )
                logger.info("✅ Created new engine")

            logger.info(f"Engine ID: {deployed_engine.resource_name}")

            engine_id = deployed_engine.resource_name

            # Save deployment info
            deployment_info = f"""Deployment: {deployment_name}
Timestamp: {timestamp}
Engine ID: {engine_id}
Project: {project_id}
Location: {location}
"""

            # Write to deployment log in logs directory
            logs_dir = Path(original_dir) / "agents" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "ken_e_deployment.txt"
            with open(log_file, "w") as f:
                f.write(deployment_info)

            logger.info(f"Deployment info saved to: {log_file}")

            # Update Secret Manager with the engine ID
            logger.info("📝 Updating Secret Manager...")
            secret_updated = update_secret_manager(
                secret_name="ken-e-engine-id",
                secret_value=engine_id,
                project_id=project_number,
            )

            if secret_updated:
                logger.info("✅ Secret Manager updated successfully")
            else:
                logger.warning("⚠️  Failed to update Secret Manager")

            print("\n" + "=" * 70)
            print("🎉 KEN-E CHAT AGENT DEPLOYMENT SUCCESSFUL!")
            print("=" * 70)
            print(f"Engine ID: {engine_id}")
            print(
                f"Python Version: {__import__('sys').version_info.major}.{__import__('sys').version_info.minor}"
            )
            print("=" * 70)

            return engine_id

        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            import traceback

            traceback.print_exc()
            return None
        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Deploy KEN-E agent to Vertex AI")
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Target environment (dev, staging, or prod). Default: dev",
    )
    parser.add_argument(
        "--location",
        default="us-central1",
        help="Vertex AI location (default: us-central1)",
    )
    args = parser.parse_args()

    # Get configuration for target environment
    env_config = ENV_CONFIG[args.env]

    # Set environment variables from config
    os.environ["VERTEX_AI_PROJECT_ID"] = env_config["project_id"]
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = env_config["project_id"]
    os.environ["VERTEX_AI_LOCATION"] = args.location
    os.environ["_TARGET_ENV"] = args.env

    logger.info("=" * 70)
    logger.info("Deploying KEN-E Chat Agent")
    logger.info(f"Environment: {args.env.upper()}")
    logger.info(f"Project: {env_config['project_id']} ({env_config['project_number']})")
    logger.info(f"Location: {args.location}")
    logger.info("=" * 70)

    result = deploy_ken_e()
    sys.exit(0 if result else 1)
