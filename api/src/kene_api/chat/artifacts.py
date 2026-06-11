"""API-side artifact READ helpers + re-exports of the canonical write path.

The canonical WRITE path — ``register_artifact`` (GCS blob + Firestore
``ChatArtifactIndex`` row), plus the ``ChatArtifactIndex`` shape and the
path/bucket helpers — lives in ``shared/chat_artifacts.py`` so the Agent Engine
deployment (which does not package ``kene_api``) can import it. See
DESIGN-REVIEW-LOG: relocating the wrapper to ``shared/`` closed the packaging gap
that previously made agent-side persistence silently no-op.

This module:
  * re-exports the write-path symbols from ``shared`` so existing API callers
    (``from ..chat.artifacts import register_artifact`` / ``ChatArtifactIndex`` /
    ``parse_gcs_path`` / ``_resolve_bucket`` / ``_artifact_id`` …) keep working;
  * keeps the API-only READ helpers — ``list_artifacts``,
    ``fetch_visualization_spec``, ``generate_artifact_signed_url`` — which need a
    GCS storage client and the signed-URL bucket allowlist (read-only concerns
    that the agent runtime never touches).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore, storage

from shared.chat_artifacts import (  # noqa: F401  (re-exported for API callers)
    VEGALITE_MIME,
    ChatArtifactIndex,
    ParsedArtifactPath,
    _artifact_id,
    _resolve_bucket,
    build_gcs_path,
    parse_gcs_path,
    register_artifact,
)

from ..dependencies import get_firestore_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Storage client (module singleton — matches get_firestore_client pattern)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_storage_client() -> storage.Client:
    """Return a module-cached GCS client (read path: download + sign URLs)."""
    return storage.Client()


# ---------------------------------------------------------------------------
# Artifact read helpers
# ---------------------------------------------------------------------------


_MAX_ARTIFACTS_PER_SESSION = 200

# Buckets this service is authorised to sign URLs for. Validated before every
# signing call to prevent a tampered Firestore row from issuing signed URLs
# for buckets outside the system's control. These are the REAL bucket names per
# environment (prod is `ken-e-files-us`, not `ken-e-production-files-us`); the
# `-eu` variants are included for the future data-residency path.
_ALLOWED_GCS_BUCKETS: frozenset[str] = frozenset(
    {
        "ken-e-dev-files-us",
        "ken-e-dev-files-eu",
        "ken-e-staging-files-us",
        "ken-e-staging-files-eu",
        "ken-e-files-us",
        "ken-e-files-eu",
    }
)


def list_artifacts(account_id: str, session_id: str) -> list[ChatArtifactIndex]:
    """Read artifact metadata rows for a session, ordered by created_at DESC.

    Uses a path-scoped subcollection read (not collection-group) because the
    caller already holds ``account_id`` from the side-table ownership check,
    making the full Firestore path available. This avoids relying on the
    collection-group composite index and is simpler.

    Malformed documents (those that fail ``ChatArtifactIndex`` validation) are
    dropped with a warning log keyed on ``artifact_id`` rather than raising,
    matching the ``chat/todos.py`` precedent for agent-authored data.

    Returns:
        List of ``ChatArtifactIndex`` sorted by ``created_at`` descending
        (capped at ``_MAX_ARTIFACTS_PER_SESSION`` rows).
        Returns an empty list for an empty subcollection.
    """
    db = get_firestore_client()
    col_ref = (
        db.collection(f"accounts/{account_id}/chat_sessions/{session_id}/artifacts")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(_MAX_ARTIFACTS_PER_SESSION)
    )
    docs = col_ref.get()
    results: list[ChatArtifactIndex] = []
    for doc in docs:
        raw = doc.to_dict()
        if raw is None:
            continue
        try:
            results.append(ChatArtifactIndex(**raw))
        except Exception:
            artifact_id = raw.get("artifact_id", doc.id)
            logger.warning(
                "chat.artifact.malformed_row",
                extra={"artifact_id": artifact_id, "session_id": session_id},
            )
    return results


def _blob_ref(index: ChatArtifactIndex) -> tuple[str, str]:
    """Resolve ``(bucket_name, blob_name)`` from an artifact's ``gcs_path``.

    Raises ``ValueError`` if the path is malformed or names a bucket outside the
    system allowlist — a tampered Firestore row must never address a bucket
    outside the system's control.
    """
    parsed = parse_gcs_path(index.gcs_path)
    if parsed is None:
        raise ValueError(
            f"malformed gcs_path {index.gcs_path!r} for artifact_id={index.artifact_id}"
        )

    # Blob name (path within bucket): everything after "gs://{bucket}/".
    # Format: {app_name}/{user_id}/{session_id}/{filename}/{version}
    blob_name = (
        f"{parsed.app_name}/{parsed.user_id}/{parsed.session_id}"
        f"/{parsed.filename}/{parsed.version}"
    )
    # Bucket is the second path segment of the GCS URI after "gs://".
    bucket_name = index.gcs_path[len("gs://") :].split("/", 1)[0]

    if bucket_name not in _ALLOWED_GCS_BUCKETS:
        raise ValueError(
            f"bucket {bucket_name!r} is not in the system allowlist for "
            f"artifact_id={index.artifact_id}"
        )
    return bucket_name, blob_name


def fetch_visualization_spec(index: ChatArtifactIndex) -> dict[str, Any] | None:
    """Download and JSON-parse a persisted Vega-Lite chart spec from GCS.

    Used by the history path to re-render inline charts after a reload. Returns
    ``None`` (drop-with-warning) on any failure — a malformed path, a bucket
    outside the allowlist, a GCS error, or non-JSON content — so one bad blob
    never fails the whole history response.
    """
    try:
        bucket_name, blob_name = _blob_ref(index)
    except ValueError as exc:
        logger.warning(
            "chat.artifact.spec_fetch_skipped",
            extra={"artifact_id": index.artifact_id, "reason": str(exc)},
        )
        return None

    try:
        client = _get_storage_client()
        raw = client.bucket(bucket_name).blob(blob_name).download_as_bytes()
        spec = json.loads(raw)
    except Exception as exc:
        logger.warning(
            "chat.artifact.spec_fetch_failed",
            extra={"artifact_id": index.artifact_id, "error": str(exc)},
        )
        return None

    if not isinstance(spec, dict):
        logger.warning(
            "chat.artifact.spec_not_object",
            extra={"artifact_id": index.artifact_id},
        )
        return None
    return spec


def generate_artifact_signed_url(
    index: ChatArtifactIndex,
    *,
    now: datetime,
) -> tuple[str, datetime]:
    """Generate a V4 signed GCS URL for an artifact (10-minute TTL).

    Args:
        index: The artifact metadata row from Firestore.
        now: The current UTC datetime (injected for testability).

    Returns:
        ``(signed_url, expires_at)`` where ``expires_at = now + 10 min``.

    Raises:
        ValueError: If ``index.gcs_path`` cannot be parsed or if the GCS
            signing call raises a ``GoogleAPICallError``. The endpoint layer
            catches this to implement the drop-with-warning pattern.
    """
    bucket_name, blob_name = _blob_ref(index)

    client = _get_storage_client()
    bucket_obj = client.bucket(bucket_name)
    blob = bucket_obj.blob(blob_name)

    ttl = timedelta(minutes=10)
    try:
        signed_url: str = blob.generate_signed_url(
            version="v4",
            expiration=ttl,
            method="GET",
        )
    except GoogleAPICallError as exc:
        raise ValueError(
            f"generate_artifact_signed_url: signing failed for artifact_id="
            f"{index.artifact_id}: {exc}"
        ) from exc

    return signed_url, now + ttl
