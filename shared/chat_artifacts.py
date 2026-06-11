"""Cross-runtime canonical artifact-save path (CH-PRD-05 / AH-143).

Lives in ``shared/`` — like ``shared/token_accounting`` — so BOTH the API
container and the Agent Engine deployment import it without sys.path trickery.
Agent tools (e.g. ``create_visualization``) call :func:`register_artifact` to
persist an artifact to GCS (via ADK ``ToolContext.save_artifact``) AND record an
independent Firestore ``ChatArtifactIndex`` provenance row. The Firestore row is
the durable, compaction-immune index the chat UI reads — it survives agent
redeploys and session-event compaction (GCS holds the blob; Firestore holds the
reference).

Previously this lived in ``api/src/kene_api/chat/artifacts.py``; the Agent Engine
deploy does not package ``kene_api``, so the agent-side import silently failed and
nothing persisted. Relocating here closes that gap (see DESIGN-REVIEW-LOG).

The API-only READ helpers (signed URLs, spec fetch, listing) stay in
``api/src/kene_api/chat/artifacts.py`` and re-export the shapes/helpers here.

GCS path format (session-scoped form of ``GcsArtifactService._get_blob_name``):
    ``gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}``

Artifact ID (deterministic, collision-resistant):
    ``sha256("{session_id}|{filename}|{version}")[:32]``

Dependency note: this module intentionally avoids ``backoff`` (a tiny manual
retry is used instead) so it imports cleanly in the Agent Engine runtime, whose
``requirements.txt`` does not list ``backoff``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Any, NamedTuple

from google.api_core.exceptions import (
    AlreadyExists,
    DeadlineExceeded,
    ServiceUnavailable,
)
from google.cloud import firestore
from google.genai import types as genai_types
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)

# MIME type written by ``create_visualization`` for Vega-Lite chart blobs.
VEGALITE_MIME = "application/vnd.vegalite.v6+json"

# Environment → GCS files bucket. The names do NOT follow one pattern: dev and
# staging are ``ken-e-{env}-files-us``, but production is ``ken-e-files-us`` (no
# ``production`` segment). Keep in sync with ENV_CONFIG[...]["artifact_bucket"]
# in app/adk/deploy_ken_e.py (which configures the agent's GcsArtifactService).
_ENV_ARTIFACT_BUCKET: dict[str, str] = {
    "development": "ken-e-dev-files-us",
    "dev": "ken-e-dev-files-us",
    "staging": "ken-e-staging-files-us",
    "production": "ken-e-files-us",
    "prod": "ken-e-files-us",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Artifact provenance model (moved from kene_api.models.chat; re-exported there)
# ---------------------------------------------------------------------------


class ChatArtifactIndex(BaseModel):
    """Metadata row for one artifact stored by GcsArtifactService.

    No creator field — created_by_tool=None is reserved for future user uploads
    (no user-upload surface in v1). Non-null in v1 (agent-created artifacts only).
    """

    artifact_id: str  # sha256(session_id|filename|version)[:32]
    session_id: str
    filename: str
    mime_type: str
    size_bytes: int
    version: int  # ADK artifact version (0..N)
    gcs_path: str  # gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}
    created_by_tool: str | None = None  # agent tool name; None = user upload (latent v2)
    created_at: datetime = Field(default_factory=_now_utc)


# ---------------------------------------------------------------------------
# Pure path helpers
# ---------------------------------------------------------------------------


class ParsedArtifactPath(NamedTuple):
    """Decomposed GCS artifact path."""

    app_name: str
    user_id: str
    session_id: str
    filename: str
    version: int


def build_gcs_path(
    app_name: str,
    user_id: str,
    session_id: str,
    filename: str,
    version: int,
    *,
    bucket: str,
) -> str:
    """Build the canonical GCS URI for an artifact.

    Mirrors the session-scoped branch of ``GcsArtifactService._get_blob_name``.
    Does not handle the ``user:``-namespaced filename special case.
    """
    return f"gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}"


def parse_gcs_path(path: str) -> ParsedArtifactPath | None:
    """Parse a canonical GCS artifact URI into its components, or None if malformed."""
    if not path.startswith("gs://"):
        return None
    without_scheme = path[len("gs://") :]
    parts = without_scheme.split("/", 6)
    if len(parts) != 6:
        return None
    _bucket, app_name, user_id, session_id, filename, version_str = parts
    try:
        version = int(version_str)
    except ValueError:
        return None
    return ParsedArtifactPath(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        filename=filename,
        version=version,
    )


def _artifact_id(session_id: str, filename: str, version: int) -> str:
    """Deterministic 32-hex-char artifact ID: sha256(session_id|filename|version)[:32]."""
    key = f"{session_id}|{filename}|{version}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _resolve_bucket(artifact_service: Any) -> str:
    """Resolve the GCS bucket name from the artifact service or environment.

    Prefers the configured artifact service's ``bucket_name`` (set by the agent's
    GcsArtifactService); falls back to the per-environment map.
    """
    if artifact_service is not None and hasattr(artifact_service, "bucket_name"):
        return str(artifact_service.bucket_name)
    environment = os.getenv("ENVIRONMENT", "development").lower()
    return _ENV_ARTIFACT_BUCKET.get(environment, "ken-e-dev-files-us")


# ---------------------------------------------------------------------------
# Firestore client + write helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_firestore_client() -> firestore.Client:
    """Module-cached Firestore client.

    Mirrors ``kene_api.dependencies.get_firestore_client`` but is self-contained
    so the Agent Engine runtime (which does not package ``kene_api``) can use it.
    Falls back to the ambient project when ``GOOGLE_CLOUD_PROJECT_ID`` is unset.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    return firestore.Client(project=project_id) if project_id else firestore.Client()


def _artifact_doc_path(account_id: str, session_id: str, artifact_id: str) -> str:
    return f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}"


def _session_doc_path(account_id: str, session_id: str) -> str:
    return f"accounts/{account_id}/chat_sessions/{session_id}"


_RETRYABLE: tuple[type[Exception], ...] = (ServiceUnavailable, DeadlineExceeded)


def _write_artifact_batch(
    db: firestore.Client,
    account_id: str,
    session_id: str,
    artifact_data: dict[str, Any],
    artifact_id: str,
) -> None:
    """Write artifact row + increment side-table counter in a single batch.

    Uses ``create()`` semantics so a duplicate call raises ``AlreadyExists``
    rather than overwriting and double-incrementing the counter. Retries up to 3
    times on transient Firestore errors via a small manual backoff (no ``backoff``
    dependency — see module docstring). ``AlreadyExists`` is not retried.
    """
    artifact_ref = db.document(_artifact_doc_path(account_id, session_id, artifact_id))
    session_ref = db.document(_session_doc_path(account_id, session_id))

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            batch = db.batch()
            batch.create(artifact_ref, artifact_data)
            batch.update(
                session_ref,
                {
                    "artifact_count": firestore.Increment(1),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            batch.commit()
            return
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(0.5 * (2**attempt))
    if last_exc is not None:
        raise last_exc


def _read_existing_artifact(
    db: firestore.Client,
    account_id: str,
    session_id: str,
    artifact_id: str,
) -> ChatArtifactIndex | None:
    """Read back an existing artifact row (idempotency path)."""
    doc = db.document(_artifact_doc_path(account_id, session_id, artifact_id)).get()
    if not doc.exists:
        return None
    return ChatArtifactIndex(**doc.to_dict())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def register_artifact(
    tool_context: ToolContext,
    filename: str,
    content: genai_types.Part,
    *,
    created_by_tool: str | None,
) -> ChatArtifactIndex:
    """Save an artifact to GCS and index it in Firestore.

    1. Calls ``tool_context.save_artifact`` — ADK writes the blob to GCS.
    2. Derives a deterministic ``artifact_id`` from (session_id, filename, version).
    3. Writes a ``ChatArtifactIndex`` document under
       ``accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}``
       and atomically increments ``artifact_count`` on the parent session doc.
    4. Idempotent: a duplicate call returns the existing row without
       double-incrementing the counter.

    Raises:
        ValueError: If the content has no inline_data.
        RuntimeError: If account_id is absent from session state — the blob is
            written but cannot be indexed.
        ServiceUnavailable | DeadlineExceeded: After retry exhaustion on
            transient Firestore errors.
    """
    if created_by_tool is not None and len(created_by_tool) == 0:
        raise ValueError("created_by_tool must be a non-empty string or None")
    if "|" in filename:
        raise ValueError(
            "filename must not contain '|' (reserved as artifact_id separator)"
        )
    if content.inline_data is None:
        raise ValueError("register_artifact requires content with inline_data")

    # Step 1 — persist to GCS via ADK
    version: int = await tool_context.save_artifact(filename, content)  # type: ignore[union-attr]

    # Extract context from ToolContext
    invocation_ctx = tool_context._invocation_context  # type: ignore[union-attr]
    app_name: str = invocation_ctx.app_name
    user_id: str = tool_context.user_id  # type: ignore[union-attr]
    session_id: str = tool_context.session.id  # type: ignore[union-attr]
    account_id: str | None = tool_context.state.get("account_id")  # type: ignore[union-attr]

    # Step 2 — build metadata
    bucket = _resolve_bucket(getattr(invocation_ctx, "artifact_service", None))
    gcs_path = build_gcs_path(
        app_name, user_id, session_id, filename, version, bucket=bucket
    )
    raw_bytes: bytes = content.inline_data.data or b""
    mime_type: str = (
        content.inline_data.mime_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    art_id = _artifact_id(session_id, filename, version)
    index = ChatArtifactIndex(
        artifact_id=art_id,
        session_id=session_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=len(raw_bytes),
        version=version,
        gcs_path=gcs_path,
        created_by_tool=created_by_tool,
    )

    # Step 3 — persist Firestore index + side-table increment
    if account_id is None:
        # No account_id in session state — the artifact cannot be indexed, so the
        # GCS blob just written would be orphaned. Fail loud rather than hide it.
        logger.error(
            "chat.artifact.no_account_id",
            extra={"session_id": session_id, "artifact_filename": filename},
        )
        raise RuntimeError(
            f"register_artifact: no account_id in session state for session "
            f"{session_id}; the GCS blob was written but cannot be indexed"
        )

    db = _get_firestore_client()
    artifact_data = index.model_dump()

    try:
        await asyncio.to_thread(
            _write_artifact_batch, db, account_id, session_id, artifact_data, art_id
        )
    except AlreadyExists:
        # Idempotency: blob already indexed; return existing row without
        # double-incrementing the counter.
        existing = await asyncio.to_thread(
            _read_existing_artifact, db, account_id, session_id, art_id
        )
        if existing is not None:
            logger.info(
                "chat.artifact.idempotent_skip",
                extra={"artifact_id": art_id, "session_id": session_id},
            )
            return existing
        logger.warning(
            "chat.artifact.race_window_fallback",
            extra={"artifact_id": art_id, "session_id": session_id},
        )
        return index

    logger.info(
        "chat.artifact.registered",
        extra={
            "artifact_id": art_id,
            "session_id": session_id,
            "account_id": account_id,
            "artifact_filename": filename,
            "version": version,
            "size_bytes": len(raw_bytes),
            "mime_type": mime_type,
            "gcs_path": gcs_path,
            "created_by_tool": created_by_tool,
        },
    )
    return index
