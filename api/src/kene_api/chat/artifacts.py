"""Canonical artifact-save path for all agent tools.

Every artifact created by KEN-E agent tools should go through
``register_artifact``. It ensures the file lands in both:

  1. GCS — via ADK ``ToolContext.save_artifact``
  2. Firestore — a ``ChatArtifactIndex`` row under
     ``accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}``
     plus an atomic ``artifact_count`` increment on the parent session document.

GCS path format — the session-scoped form of ``GcsArtifactService._get_blob_name``
(the ``user:``-namespaced filename branch is not handled here):
    ``gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}``

Artifact ID (deterministic, collision-resistant):
    ``sha256("{session_id}|{filename}|{version}")[:32]``
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, NamedTuple

import backoff
from google.api_core.exceptions import (
    AlreadyExists,
    DeadlineExceeded,
    ServiceUnavailable,
)
from google.cloud import firestore
from google.genai import types as genai_types

from ..dependencies import get_firestore_client
from ..models.chat import ChatArtifactIndex

if TYPE_CHECKING:
    from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


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

    Mirrors the session-scoped branch of ``GcsArtifactService._get_blob_name`` so
    callers can reconstruct the URI without holding a reference to the service
    instance. Does not handle the ``user:``-namespaced filename special case.
    """
    return f"gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}"


def parse_gcs_path(path: str) -> ParsedArtifactPath | None:
    """Parse a canonical GCS artifact URI into its components.

    Returns ``None`` if the path does not conform to the expected format.
    """
    if not path.startswith("gs://"):
        return None
    # Strip scheme; split into bucket + 5 path segments
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


# ---------------------------------------------------------------------------
# Artifact ID derivation
# ---------------------------------------------------------------------------


def _artifact_id(session_id: str, filename: str, version: int) -> str:
    """Deterministic 32-hex-char artifact ID: sha256(session_id|filename|version)[:32]."""
    key = f"{session_id}|{filename}|{version}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Firestore write helpers
# ---------------------------------------------------------------------------


def _artifact_doc_path(account_id: str, session_id: str, artifact_id: str) -> str:
    return f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}"


def _session_doc_path(account_id: str, session_id: str) -> str:
    return f"accounts/{account_id}/chat_sessions/{session_id}"


@backoff.on_exception(
    backoff.expo,
    (ServiceUnavailable, DeadlineExceeded),
    max_tries=3,
    base=0.5,
    jitter=backoff.full_jitter,
)
def _write_artifact_batch(
    db: firestore.Client,
    account_id: str,
    session_id: str,
    artifact_data: dict[str, Any],
    artifact_id: str,
) -> None:
    """Write artifact row + increment side-table counter in a single batch.

    Uses ``create()`` semantics so a duplicate call raises ``AlreadyExists``
    rather than overwriting and double-incrementing the counter.
    """
    artifact_ref = db.document(_artifact_doc_path(account_id, session_id, artifact_id))
    session_ref = db.document(_session_doc_path(account_id, session_id))

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
# Bucket resolution
# ---------------------------------------------------------------------------


def _resolve_bucket(artifact_service: Any) -> str:
    """Resolve the GCS bucket name from the artifact service or environment."""
    if artifact_service is not None and hasattr(artifact_service, "bucket_name"):
        return str(artifact_service.bucket_name)
    environment = os.getenv("ENVIRONMENT", "development").lower()
    return f"ken-e-{environment}-files-us"


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

    Args:
        tool_context: ADK ``ToolContext`` for the current invocation.
        filename: Filename for the artifact (e.g. ``"report.pdf"``).
        content: ADK ``Part`` containing ``inline_data`` (bytes + mime_type).
        created_by_tool: Name of the calling agent tool.

    Returns:
        A ``ChatArtifactIndex`` with all provenance fields populated.

    Raises:
        ValueError: If the content has no inline_data.
        RuntimeError: If account_id is absent from session state — the blob is
            written but cannot be indexed.
        ServiceUnavailable | DeadlineExceeded: After retry exhaustion on
            transient Firestore errors. The GCS blob is already saved, leaving a
            blob with no Firestore row until the GCS-orphan reconciliation job
            (a separate job, not the ADK-session scan) sweeps it.
    """
    # TODO(chat-telemetry): emit Weave span on success/failure
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
        # GCS blob just written would be orphaned (invisible in the UI). Fail loud
        # rather than return a success-shaped result that hides the orphan.
        logger.error(
            "chat.artifact.no_account_id",
            extra={"session_id": session_id, "artifact_filename": filename},
        )
        raise RuntimeError(
            f"register_artifact: no account_id in session state for session "
            f"{session_id}; the GCS blob was written but cannot be indexed"
        )

    db = get_firestore_client()
    artifact_data = index.model_dump()

    try:
        await asyncio.to_thread(
            _write_artifact_batch,
            db,
            account_id,
            session_id,
            artifact_data,
            art_id,
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
        # AlreadyExists but doc unreadable (concurrent delete race).
        # GCS write succeeded; return locally-built index without logging
        # "registered" (this was not a first write).
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
