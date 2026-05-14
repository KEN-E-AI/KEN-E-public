#!/usr/bin/env python3
"""Migrate MCP server configs from YAML to Firestore.

Reads ``app/adk/mcp_config/config/mcp_servers.yaml`` and writes each server
to the ``mcp_server_configs/{server_id}`` Firestore collection. The document
shape is ``MCPServerFirestoreConfig`` (see
``api/src/kene_api/models/mcp_server_models.py``) with registry-level fields
derived per Sprint 6 Decision A:

* ``integration_type`` defaults to ``"mcp"`` (every existing entry is MCP)
* ``hosting`` derived from connection type: stdio → ``"self"``, sse → ``"provider"``
* ``specialist_categories`` wraps the singular ``category`` as ``[category]``
* ``metadata`` initialized with ``v1.0.0``, current UTC timestamps, and
  ``updated_by="migration_script"``

**Secrets are stored as literal ``${VAR}`` strings** — not resolved — so
rotation remains an env/Secret-Manager concern rather than a Firestore write.

Usage:
    # Dry run (no writes)
    uv run python -m app.adk.mcp_config.scripts.migrate_mcp_to_firestore \\
        --project-id ken-e-dev --dry-run

    # Live migration (idempotent: overwrites existing docs)
    uv run python -m app.adk.mcp_config.scripts.migrate_mcp_to_firestore \\
        --project-id ken-e-dev

Design refs:
* Decision A (schema): https://www.notion.so/34830fd653028158bb4be8b22622bcb8
* docs/design/mcp-architecture.md §6 (migration rules)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


DEFAULT_YAML_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "mcp_servers.yaml"
)

COLLECTION = "mcp_server_configs"


def read_yaml_servers_raw(
    yaml_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Read the raw YAML servers block without running env-var resolution.

    Returns the ``servers`` mapping with literal ``${VAR}`` strings intact,
    so the Firestore payload preserves them.
    """
    path = yaml_path or DEFAULT_YAML_PATH
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("servers", {})


def _derive_hosting(connection_type: str) -> str:
    if connection_type == "stdio":
        return "self"
    if connection_type == "sse":
        return "provider"
    raise ValueError(f"Unknown connection_type: {connection_type!r}")


def build_firestore_payload(
    server_id: str,
    raw: dict[str, Any],
    now_iso: str | None = None,
) -> dict[str, Any]:
    """Transform a single raw YAML server entry into a Firestore doc payload.

    This function is pure (no Firestore, no env resolution) so tests can
    exercise the derivation rules without mocking anything.

    Args:
        server_id: YAML key (becomes the Firestore doc ID and the ``name``)
        raw: Raw YAML mapping for this server
        now_iso: Optional timestamp override (for deterministic tests).
            Defaults to current UTC time.

    Returns:
        Dict matching the ``MCPServerFirestoreConfig`` schema.
    """
    timestamp = now_iso or datetime.now(timezone.utc).isoformat()

    connection = dict(raw["connection"])
    connection_type = connection.get("connection_type")
    if not isinstance(connection_type, str):
        raise ValueError(f"Server '{server_id}' missing connection.connection_type")

    payload: dict[str, Any] = {
        "name": server_id,
        "description": raw.get("description", ""),
        "integration_type": "mcp",
        "hosting": _derive_hosting(connection_type),
        "specialist_categories": [raw.get("category", "uncategorized")],
        "tool_count": raw.get("tool_count", 0),
        "estimated_tokens": raw.get("estimated_tokens", 1000),
        "keywords": list(raw.get("keywords", [])),
        "connection": connection,
        "auth_type": raw.get("auth_type"),
        "enabled": raw.get("enabled", True),
        "metadata": {
            "version": "v1.0.0",
            "variant_name": "baseline",
            "experiment_id": "baseline",
            "created_at": timestamp,
            "updated_at": timestamp,
            "updated_by": "migration_script",
            "notes": (
                "Initial migration from app/adk/mcp_config/config/"
                "mcp_servers.yaml (Sprint 6 Story 1.1.4-2)."
            ),
        },
    }

    return payload


def migrate(
    project_id: str,
    dry_run: bool,
    yaml_path: Path | None = None,
) -> int:
    """Run the migration. Returns the number of docs written (or would-be written)."""
    raw_servers = read_yaml_servers_raw(yaml_path)
    if not raw_servers:
        logger.error("No servers found in YAML — nothing to migrate")
        return 0

    # Build and validate all payloads before any writes happen.
    payloads: dict[str, dict[str, Any]] = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    for server_id, raw in raw_servers.items():
        try:
            payload = build_firestore_payload(server_id, raw, now_iso=now_iso)
        except Exception as e:
            logger.error(f"Server '{server_id}' failed payload build: {e}")
            raise
        payloads[server_id] = payload

    logger.info("Built %d server payloads", len(payloads))

    if dry_run:
        for server_id, payload in payloads.items():
            logger.info(
                "[DRY RUN] Would write %s/%s: hosting=%s, enabled=%s, "
                "connection_type=%s",
                COLLECTION,
                server_id,
                payload["hosting"],
                payload["enabled"],
                payload["connection"]["connection_type"],
            )
        return len(payloads)

    # Lazy import so --dry-run works without GCP creds.
    from google.cloud import firestore

    db = firestore.Client(project=project_id)
    written = 0
    for server_id, payload in payloads.items():
        try:
            db.collection(COLLECTION).document(server_id).set(payload)
            written += 1
            logger.info("✅ Wrote %s/%s", COLLECTION, server_id)
        except Exception as e:
            logger.error("❌ Failed to write %s/%s: %s", COLLECTION, server_id, e)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate MCP server configs from YAML to Firestore "
        "(Sprint 6 Story 1.1.4-2)"
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="GCP project ID (e.g., ken-e-dev, ken-e-staging, ken-e-production)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without touching Firestore",
    )
    parser.add_argument(
        "--yaml-path",
        type=Path,
        default=None,
        help=f"Override YAML source path (default: {DEFAULT_YAML_PATH})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("MCP YAML → Firestore migration")
    logger.info("Project: %s", args.project_id)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("YAML source: %s", args.yaml_path or DEFAULT_YAML_PATH)
    logger.info("-" * 60)

    written = migrate(
        project_id=args.project_id,
        dry_run=args.dry_run,
        yaml_path=args.yaml_path,
    )

    logger.info("-" * 60)
    if args.dry_run:
        logger.info("✅ Dry run complete. Would write %d docs.", written)
    else:
        logger.info("✅ Migration complete. Wrote %d docs.", written)
        logger.info(
            "Next step: set MCP_CONFIG_SOURCE=firestore in the relevant "
            ".env file and redeploy."
        )

    return 0 if written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
