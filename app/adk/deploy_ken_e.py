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
    },
    "staging": {
        "project_id": "ken-e-staging",
        "project_number": "391472102753",
    },
    "prod": {
        "project_id": "ken-e-production",
        "project_number": "395770269870",
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


def deploy_ken_e() -> str | None:
    """Deploy the KEN-E chat agent to Agent Engine."""

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
            # Resolve existing engine ID from Secret Manager using target env's project
            target_env = os.getenv("_TARGET_ENV", "dev")
            project_number = ENV_CONFIG[target_env]["project_number"]
            os.environ.setdefault(
                "KEN_E_ENGINE_ID", f"sm://{project_number}/ken-e-engine-id"
            )

            existing_engine_id = None
            if get_env_or_secret:
                existing_engine_id = get_env_or_secret("KEN_E_ENGINE_ID")

            deployed_engine = None
            if existing_engine_id:
                existing_engine_id = existing_engine_id.strip()
                logger.info(
                    f"Found existing engine: {existing_engine_id}, updating in place..."
                )
                try:
                    deployed_engine = agent_engines.update(
                        resource_name=existing_engine_id,
                        agent_engine=app,
                        requirements="requirements.txt",
                        display_name=deployment_name,
                        description="KEN-E chat agent for company news and analytics",
                        extra_packages=["agents", "shared", "app"],
                    )
                    logger.info("✅ Updated existing engine (sessions preserved)")
                except Exception as update_error:
                    logger.warning(
                        f"Failed to update existing engine: {update_error}. "
                        "Falling back to creating a new engine."
                    )

            if deployed_engine is None:
                logger.info("Creating new engine...")
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
