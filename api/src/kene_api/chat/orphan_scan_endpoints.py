"""HTTP endpoint adapters for chat orphan-scan CLI orchestrators.

Thin wrappers that:
1. Resolve runtime clients (Firestore, GCS, VertexAiSessionService) from
   the existing API singletons / env vars.
2. Call the scan orchestrators defined in ``api/scripts/``.
3. Return the summary dict unchanged — callers decide how to surface it.

No flag gate: ``chat_v2_enabled`` does NOT guard these maintenance endpoints.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Path bootstrap: makes chat_artifact_orphan_scan and
# chat_adk_session_orphan_scan importable from api/scripts/.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from chat_adk_session_orphan_scan import scan_for_adk_session_orphans  # noqa: E402
from chat_artifact_orphan_scan import scan_for_gcs_blob_orphans  # noqa: E402

from ..dependencies import get_firestore_client as _get_firestore_client  # noqa: E402
from .artifacts import _get_storage_client  # noqa: E402


async def run_gcs_orphan_scan() -> dict[str, int]:
    """Invoke the GCS blob orphan reconciliation scan.

    Runs in a thread executor so the blocking I/O does not stall the
    FastAPI event loop.  Returns the summary dict from
    ``scan_for_gcs_blob_orphans`` unchanged; ``errored > 0`` is reflected
    in the dict but does NOT raise an exception — callers return HTTP 200.
    """
    db = _get_firestore_client()
    storage_client = _get_storage_client()
    return await asyncio.to_thread(
        scan_for_gcs_blob_orphans,
        db,
        storage_client,
    )


async def run_adk_session_orphan_scan(*, dry_run: bool = False) -> dict[str, int]:
    """Invoke the ADK-session orphan reconciliation scan.

    Resolves a ``VertexAiSessionService`` from the same env vars used by
    ``AgentEngineClient`` in the chat router.  GCS client is passed so
    tombstone cleanup can also remove artifact blobs.

    Returns the summary dict unchanged; ``errored > 0`` does NOT raise.
    """
    from google.adk.sessions import (
        VertexAiSessionService,  # type: ignore[import-untyped]
    )

    db = _get_firestore_client()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
    vertex_project = os.getenv("VERTEX_AI_PROJECT_ID", project_id)
    vertex_location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    engine_id_full = os.getenv("KEN_E_ENGINE_ID") or os.getenv(
        "VERTEX_AI_AGENT_ENGINE_ID", ""
    )
    agent_engine_id = engine_id_full.split("/")[-1] if engine_id_full else ""
    session_service: Any = VertexAiSessionService(
        project=vertex_project,
        location=vertex_location,
        agent_engine_id=agent_engine_id,
    )
    storage_client = _get_storage_client()

    return await asyncio.to_thread(
        scan_for_adk_session_orphans,
        db,
        session_service,
        storage_client,
        dry_run=dry_run,
    )
